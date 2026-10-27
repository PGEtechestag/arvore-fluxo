# -*- coding: utf-8 -*-
"""Teia em camadas por posição — Multas e demais Sanções (com métricas de tempo).

Gera a árvore de fluxo DETALHADA (estilo teia), camada a camada, mostrando a
progressão passo a passo dos processos (Posição 1, 2, 3, ...) e todas as
ramificações relevantes até seus desfechos.

Regras implementadas:
  1. ESTRUTURA EM CAMADAS — cada nível y corresponde a uma `posicao` do CSV;
     cada nó é um movimento observado naquela posição, com nº de processos e %.
  2. IDENTIFICAÇÃO DE CONCLUSÃO — regex exata r"\bconclusão\b" (case-insensitive,
     palavra inteira, inclusive em movimentos combinados com '+'); nós de
     conclusão são quadrados vermelhos; nós finais (último movimento do
     processo) recebem borda destacada.
  3. MÉTRICAS TEMPORAIS — média de dias de cada transição (data do movimento
     de origem → data do movimento de destino), exibida nas arestas fortes,
     e resumo global (posições médias; dias início → 1ª conclusão) no título.
  4. VISUALIZAÇÃO LIMPA — networkx + matplotlib, rótulos quebrados com
     textwrap, arestas com largura/alpha ∝ volume, poda de ramos raros
     (top-K por camada + nº mínimo de processos) configurável via CLI.

Uso:
  py teia_camadas_tempo.py                 # teia completa podada (padrão)
  py teia_camadas_tempo.py --ate 10        # limita a profundidade
  py teia_camadas_tempo.py --topk 8 --min-n 3

Saídas (visualizacoes/imagens/):
  - teia_camadas_multas.png / .svg + teia_camadas_multas_dados.csv
"""
import argparse
import csv
import os
import re
import statistics
import textwrap
from collections import Counter, defaultdict
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "outputs_json", "tabelas",
                    "tabela_posicao_tempo_processos.csv")
OUT_IMG = os.path.join(BASE_DIR, "imagens")
ASSUNTO_ALVO = "Multas e demais Sanções"

RE_CONCLUSAO = re.compile(r"(?i)\bconclusão\b")

COR_CONCLUSAO = "#B71C1C"
COR_CORRENTE = "#B45309"
COR_INICIO = "#37474F"
COR_DESFECHO = "#1B5E20"

# ----------------------------------------------------------------------------
# 1) CARGA: {proc: [(posicao, movimento, data_iso), ...] ordenado por posicao}
# ----------------------------------------------------------------------------
def carregar_trilhas():
    trilhas = defaultdict(list)
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["assunto"].strip() == ASSUNTO_ALVO:
                trilhas[r["num_processo"]].append(
                    (int(r["posicao"]), r["movimento_atual"], r["data_movimento"]))
    for lista in trilhas.values():
        lista.sort(key=lambda x: x[0])
    return dict(trilhas)


def rotulo(texto, largura=18, max_linhas=3):
    """Quebra/encurta o rótulo para não poluir a visualização."""
    t = re.sub(r"\s+", " ", texto).strip()
    linhas = textwrap.wrap(t, width=largura)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1][: largura - 1].rstrip() + "…"
    return "\n".join(linhas)


def _dias(iso_a, iso_b):
    """Dias entre duas datas ISO (None se alguma for inválida)."""
    try:
        return (date.fromisoformat(iso_b) - date.fromisoformat(iso_a)).days
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------------
# 2) ESTRUTURA EM CAMADAS: nós por posição + arestas com volume e tempo médio
# ----------------------------------------------------------------------------
def construir_teia(trilhas, max_pos=None, topk=10, min_n=2):
    """Monta níveis (por posição) e arestas de transição.

    Poda de legibilidade (os % são sempre sobre o total de processos):
      topk  -> máx. de movimentos exibidos por camada;
      min_n -> mínimo de processos para um nó/aresta aparecer.

    Retorna:
      n_pos        — profundidade real usada
      niveis[p]    — [(movimento, n_proc, eh_ultimo), ...]
      arestas      — [(p, mov_pai, mov_filho, peso, dias_medios), ...]
      tempo_1concl — resumo {n, media, mediana, min, max} dias até a 1ª conclusão
    """
    total = len(trilhas)
    n_pos = max((len(t) for t in trilhas.values()), default=0)
    if max_pos:
        n_pos = min(n_pos, max_pos)

    # --- camadas: movimentos mais frequentes em cada posição ---
    niveis = []
    for p in range(1, n_pos + 1):
        alcancam = [t for t in trilhas.values() if len(t) >= p]
        dist = Counter(t[p - 1][1] for t in alcancam)
        camada = [(m, c) for m, c in dist.most_common(topk) if c >= min_n]
        niveis.append(camada)
    vivo = {m for m, _ in niveis[-1]} if niveis else set()

    # --- marca desfechos: último movimento do processo dentro das camadas ---
    marcados = []
    for p, camada in enumerate(niveis, start=1):
        linha = []
        for m, c in camada:
            eh_ultimo = any(len(t) == p and t[p - 1][1] == m for t in trilhas.values())
            linha.append((m, c, eh_ultimo))
        marcados.append(linha)

    # --- arestas: transições consecutivas reais + média de dias da transição ---
    arestas = []
    for p in range(n_pos):
        agg = defaultdict(lambda: [0, []])       # (pai, filho) -> [n, dias[]]
        for t in trilhas.values():
            if len(t) < p + 2:
                continue
            mov_a, mov_b = t[p][1], t[p + 1][1]
            d = _dias(t[p][2], t[p + 1][2])
            key = (mov_a, mov_b)
            if p == 0 or (mov_a in {m for m, _, _ in marcados[p - 1]}
                          and mov_b in {m for m, _, _ in marcados[p]}):
                agg[key][0] += 1
                if d is not None and d >= 0:
                    agg[key][1].append(d)
        for (mov_a, mov_b), (n, ds) in agg.items():
            if n < min_n:
                continue
            dias_med = statistics.mean(ds) if ds else None
            arestas.append((p + 1, mov_a, mov_b, n, dias_med))  # p+1 = pos_pai

    # --- tempo global até a 1ª conclusão ---
    dias_1concl = []
    for t in trilhas.values():
        for pos, mov, dta in t:
            if RE_CONCLUSAO.search(mov):
                d = _dias(t[0][2], dta)
                if d is not None and d >= 0:
                    dias_1concl.append(d)
                break
    tempo = {"n": len(dias_1concl)}
    if dias_1concl:
        tempo.update(media=statistics.mean(dias_1concl),
                     mediana=statistics.median(dias_1concl),
                     min=min(dias_1concl), max=max(dias_1concl))
    else:
        tempo.update(media=0, mediana=0, min=0, max=0)
    return n_pos, marcados, arestas, tempo

# ----------------------------------------------------------------------------
# 3) GRAFO networkx: nós = (posicao, movimento); arestas com peso e dias médios
# ----------------------------------------------------------------------------
def montar_grafo(niveis, arestas, total):
    G = nx.DiGraph()
    pos = {}
    for p, camada in enumerate(niveis, start=1):
        for i, (mov, n, eh_ultimo) in enumerate(camada):
            no = (p, mov)
            G.add_node(no, n=n, label=rotulo(mov),
                       conclusao=bool(RE_CONCLUSAO.search(mov)),
                       desfecho=eh_ultimo)
            pos[no] = (i - (len(camada) - 1) / 2.0, -p)
    for p, mov_a, mov_b, n, dias in arestas:
        u, v = (p, mov_a), (p + 1, mov_b)
        if u in G and v in G:
            G.add_edge(u, v, peso=n, dias=dias)
    # raiz virtual "Início" ligada aos movimentos da posição 1
    raiz = (0, "Início do processo")
    G.add_node(raiz, n=total, label="Início do\nprocesso",
               conclusao=False, desfecho=False)
    pos[raiz] = (0.0, 0)
    for (p, m), d in list(G.nodes(data=True)):
        if p == 1:
            G.add_edge(raiz, (1, m), peso=d["n"], dias=0.0)
    return G, pos



def desenhar(G, pos, n_pos, tempo, media_pos, total, png, svg,
             min_dias_label=3):
    fig, ax = plt.subplots(figsize=(24, 2.6 + 2.0 * n_pos), dpi=140)

    # --- arestas: largura/alpha ∝ volume; rótulo "n | μ dias" nas fortes ---
    wmax = max((d["peso"] for _, _, d in G.edges(data=True)), default=1)
    for u, v, d in G.edges(data=True):
        frac = d["peso"] / wmax
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)], ax=ax, arrowstyle="-|>",
            arrowsize=6 + 6 * frac, edge_color=COR_CORRENTE,
            alpha=0.20 + 0.65 * frac, width=0.5 + 4.0 * frac,
            connectionstyle="arc3,rad=0.10", min_source_margin=10,
            min_target_margin=12)
        if d["dias"] is not None and d["peso"] >= min_dias_label:
            xa, ya = pos[u]
            xb, yb = pos[v]
            # rótulo a 40% do trajeto + deslocamento perpendicular,
            # evitando amontoado próximo à camada de origem
            tx = xa + 0.40 * (xb - xa) + 0.14 * (yb - ya)
            ty = ya + 0.40 * (yb - ya) + 0.10 * (xa - xb)
            ax.text(tx, ty, f"{d['peso']} | μ {d['dias']:.0f}d",
                    fontsize=6.2, color="#6B3E03", alpha=0.85,
                    ha="center", va="center")

    # --- nós: círculos (andamento), quadrados (conclusão), anel p/ desfecho ---
    circ = [n for n in G.nodes if not G.nodes[n]["conclusao"]]
    quad = [n for n in G.nodes if G.nodes[n]["conclusao"]]
    cores = [COR_INICIO if n[0] == 0 else
             plt.cm.Oranges(0.30 + 0.50 * min(1, n[0] / max(1, n_pos)))
             for n in circ]
    nx.draw_networkx_nodes(G, pos, nodelist=circ, node_color=cores, ax=ax,
                           node_size=520, edgecolors="white", linewidths=1.0)
    nx.draw_networkx_nodes(G, pos, nodelist=quad, node_shape="s",
                           node_color=COR_CONCLUSAO, ax=ax, node_size=560,
                           edgecolors="white", linewidths=1.2)
    fins = [n for n in circ if G.nodes[n]["desfecho"] and n[0] > 0]
    nx.draw_networkx_nodes(G, pos, nodelist=fins, node_color="none", ax=ax,
                           node_size=800, edgecolors=COR_DESFECHO,
                           linewidths=1.8, node_shape="o")



    # --- rótulos curtos acima dos nós (textwrap evita sobreposição) ---
    for n, data in G.nodes(data=True):
        x, y = pos[n]
        cor = ("#7F1D1D" if data["conclusao"] else
               "#1B5E20" if data["desfecho"] and n[0] > 0 else "#1F2937")
        txt = f"{data['label']}\n({data['n']} | {100*data['n']/total:.0f}%)"
        if data["desfecho"] and n[0] > 0:
            txt += " ◆fim"
        ax.text(x, y + 0.30, txt, ha="center", va="bottom", fontsize=6.8,
                color=cor, linespacing=1.05)

    tempo_txt = (f"Tempo início → 1ª Conclusão (n={tempo['n']}): "
                 f"média {tempo['media']:.0f}d | mediana {tempo['mediana']:.0f}d | "
                 f"min {tempo['min']}d | max {tempo['max']}d") if tempo["n"] else ""
    ax.set_title(
        f"Teia em Camadas por Posição — {ASSUNTO_ALVO}\n"
        f"{total} processos | média de {media_pos:.1f} posições | teia até a posição {n_pos}\n"
        f"ARESTAS: nº de processos | μ = dias médios da transição | "
        f"anel verde = desfecho (último movimento)\n{tempo_txt}",
        fontsize=12, pad=14)
    ax.legend(handles=[
        Line2D([0], [0], marker="o", linestyle="", color=plt.cm.Oranges(0.55),
               markersize=9, label="Andamento (posição)"),
        Line2D([0], [0], marker="s", linestyle="", color=COR_CONCLUSAO,
               markersize=9, label="Conclusão"),
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="none",
               markeredgecolor=COR_DESFECHO, markersize=10,
               label="Desfecho (último movimento)"),
        Line2D([0], [0], linestyle="-", color=COR_CORRENTE, lw=2.5,
               label="Transição: largura ∝ volume"),
    ], loc="lower right", fontsize=8, framealpha=0.92)
    ax.axis("off")
    fig.tight_layout()
    os.makedirs(os.path.dirname(png), exist_ok=True)
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def exportar(niveis, arestas, base):
    """Exporta nós e arestas (com dias médios) para CSV."""
    with open(base + "_dados.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tipo", "posicao", "origem", "destino", "processos", "dias_medios"])
        for p, camada in enumerate(niveis, start=1):
            for m, n, eh_fim in camada:
                w.writerow(["no", p, m, "FIM" if eh_fim else "", n, ""])
        for p, a, b, n, d in arestas:
            w.writerow(["aresta", p, a, b, n, f"{d:.1f}" if d is not None else ""])


def main():
    ap = argparse.ArgumentParser(description="Teia em camadas com métricas de tempo.")
    ap.add_argument("--ate", type=int, default=None, help="profundidade máxima (posições)")
    ap.add_argument("--topk", type=int, default=10, help="máx. de nós por camada")
    ap.add_argument("--min-n", type=int, default=2, help="mín. de processos por nó/aresta")
    args = ap.parse_args()

    trilhas = carregar_trilhas()
    total = len(trilhas)
    print(f"[1] Assunto '{ASSUNTO_ALVO}': {total} processos.")

    n_pos, niveis, arestas, tempo = construir_teia(
        trilhas, max_pos=args.ate, topk=args.topk, min_n=args.min_n)
    media_pos = sum(len(t) for t in trilhas.values()) / total
    print(f"[2] Camadas montadas até a posição {n_pos} "
          f"(média de posições por processo: {media_pos:.1f}).")
    print(f"[3] Tempo início → 1ª Conclusão (n={tempo['n']}): "
          f"média={tempo['media']:.1f}d | mediana={tempo['mediana']:.0f}d | "
          f"mín={tempo['min']}d | máx={tempo['max']}d")

    G, pos = montar_grafo(niveis, arestas, total)
    print(f"[4] Grafo: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas.")

    base = os.path.join(OUT_IMG, "teia_camadas_multas")
    desenhar(G, pos, n_pos, tempo, media_pos, total, base + ".png", base + ".svg")
    exportar(niveis, arestas, base)
    print(f"[5] Saídas: {base}.png/.svg + {base}_dados.csv")


if __name__ == "__main__":
    main()
