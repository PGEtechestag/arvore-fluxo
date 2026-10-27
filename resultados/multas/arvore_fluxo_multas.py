# -*- coding: utf-8 -*-
"""Árvore de fluxo (hierárquica) — Início → desfechos — Multas e demais Sanções.

Diferença em relação à "teia": aqui cada ramo é um CAMINHO ÚNICO de andamentos
(árvore de prefixos/trie). Um nó só se repete quando dois processos seguem
exatamente a mesma sequência até ali — a árvore BIFURCA conforme os processos
divergem, sem mesclar nós de posições iguais em um só.

Regras:
  1. Sequências de cada processo ordenadas por `posicao`, a partir da raiz.
  2. Nó de "Conclusão" identificado por regex r"\bconclusão\b" (quadrado
     vermelho); desfecho (último movimento) recebe anel verde; demais são
     círculos laranja.
  3. Cada nó mostra nº de processos e %; cada aresta mostra "n | μ Xd" (dias
     médios da transição). O título resume o tempo global até a 1ª conclusão.
  4. Layout de árvore de verdade: x calculado por ordenação de folhas (DFS),
     y = profundidade. networkx + matplotlib, rótulos com textwrap.
  5. Poda de legibilidade: ramos com menos de `--min-n` processos são podados
     (os % continuam sobre o total de processos).

Uso:
  py arvore_fluxo_multas.py                 # árvore completa podada
  py arvore_fluxo_multas.py --min-n 5       # só ramos com 5+ processos
  py arvore_fluxo_multas.py --max-depth 8   # limita a profundidade

Saídas (visualizacoes/imagens/):
  - arvore_fluxo_multas.png / .svg + arvore_fluxo_multas_dados.csv
"""
import argparse
import csv
import os
import re
import statistics
import sys
import textwrap
from collections import defaultdict
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx

# Garante acentos no console mesmo com saída redirecionada (cp1252 etc.).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "multas_transiciones_posiciones.csv")
OUT_IMG = os.path.dirname(os.path.abspath(__file__))
ASSUNTO_ALVO = "Multas e demais Sanções"

RE_CONCLUSAO = re.compile(r"(?i)\bconclusão\b")

COR_CONCLUSAO = "#B71C1C"
COR_CORRENTE = "#B45309"
COR_INICIO = "#37474F"
COR_DESFECHO = "#1B5E20"


def carregar_trilhas():
    """{proc: [(posicion, movimiento, data_iso), ...] ordenado por posicion}."""
    trilhas = defaultdict(list)
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["asunto"].strip() == ASSUNTO_ALVO:
                trilhas[r["num_processo"]].append(
                    (int(r["posicion"]), r["movimiento_atual"], r["data_movimiento"]))
    for lista in trilhas.values():
        lista.sort(key=lambda x: x[0])
    return dict(trilhas)


def rotulo(texto, largura=16, max_linhas=3):
    """Quebra/encurta o rótulo para não poluir a visualização."""
    t = re.sub(r"\s+", " ", texto).strip()
    linhas = textwrap.wrap(t, width=largura)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1][: largura - 1].rstrip() + "…"
    return "\n".join(linhas)


def _dias(iso_a, iso_b):
    try:
        return (date.fromisoformat(iso_b) - date.fromisoformat(iso_a)).days
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------------
# 1) ÁRVORE DE PREFIXOS (trie): cada caminho único de andamentos = um ramo
# ----------------------------------------------------------------------------
def construir_arvore(trilhas, min_n=2, max_depth=None):
    """Insere cada sequência COMPLETA na trie, rastreando a origem inteira.

    Em vez de REMOVER ramos raros (o que faz o fluxo parecer que começa
    "do nada"), os filhos com < min_n processos são AGREGADOS em um único
    nó sintético "Outros (n processos em N rotas)" — o volume permanece
    contabilizado e o caminho continua legível de ponta a ponta.

    Se --max-depth for usado, o corte é marcado: o nó recebe truncado=True
    e exibe "+k posições não exibidas", nunca sumindo com o resto do ramo.

    Nó: {'n', 'conclusao', 'desfecho', 'outros', 'truncado', 'mov_origem',
         'filhos': {mov: no}, 'dias': {mov_filho: [dias das transições]}}
    Retorna (raiz, tempo_1concl, gatilhos).
    """
    raiz = {"n": len(trilhas), "conclusao": False, "desfecho": False,
            "outros": False, "truncado": False, "mov_origem": "",
            "filhos": {}, "dias": defaultdict(list)}
    for t in trilhas.values():
        limite = max_depth if max_depth else len(t)
        no = raiz
        for i, (pos, mov, dta) in enumerate(t):
            filho = no["filhos"].setdefault(mov, {
                "n": 0, "conclusao": bool(RE_CONCLUSAO.search(mov)),
                "desfecho": False, "outros": False, "truncado": False,
                "mov_origem": mov, "filhos": {}, "dias": defaultdict(list)})
            filho["n"] += 1
            if i > 0:
                d = _dias(t[i - 1][2], dta)     # dias da transição anterior→atual
                if d is not None and d >= 0:
                    no["dias"][mov].append(d)
            if i == len(t) - 1:
                filho["desfecho"] = True
            if i == limite - 1 and len(t) > limite:
                filho["truncado"] = True        # existem mais posições além
            no = filho

    # --- consolidação: agrega filhos raros em "Outros" (não apaga nada) ---
    def consolidar(no):
        raros = {m: f for m, f in no["filhos"].items()
                 if f["n"] < min_n and f["filhos"]}
        comuns = {m: f for m, f in no["filhos"].items() if m not in raros}
        if raros:
            tot = sum(f["n"] for f in raros.values())
            agg = {"n": tot, "conclusao": False, "desfecho": False,
                   "outros": True, "truncado": False,
                   "mov_origem": f"Outros ({len(raros)} rotas raras)",
                   "filhos": {}, "dias": defaultdict(list)}
            comuns["Outros"] = agg
        no["filhos"] = comuns
        for f in no["filhos"].values():
            consolidar(f)
    consolidar(raiz)

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

    # --- GATILHOS: movimentos ANTERIORES que mais levam à conclusão ---
    gat = defaultdict(lambda: {"n": 0, "dias": [], "profs": []})
    for t in trilhas.values():
        for i in range(1, len(t)):
            if RE_CONCLUSAO.search(t[i][1]):
                ant = t[i - 1][1]
                d = _dias(t[i - 1][2], t[i][2])
                gat[ant]["n"] += 1
                gat[ant]["profs"].append(t[i][0])
                if d is not None and d >= 0:
                    gat[ant]["dias"].append(d)
    gatilhos = []
    for mov, v in sorted(gat.items(), key=lambda kv: -kv[1]["n"])[:6]:
        gatilhos.append({
            "movimento": mov, "n": v["n"],
            "dias": statistics.mean(v["dias"]) if v["dias"] else None,
            "prof": statistics.mean(v["profs"]) if v["profs"] else 0,
        })
    return raiz, tempo, gatilhos


# ----------------------------------------------------------------------------
# 2) GRAFO networkx com LAYOUT DE ÁRVORE (x por ordenação de folhas, y = prof.)
# ----------------------------------------------------------------------------
def montar_grafo(raiz, x_step=1.0):
    """Converte a trie em DiGraph; cada nó = (profundidade, movimento, id)."""
    G = nx.DiGraph()
    pos = {}
    contador = [0]

    def registrar(no, mov, pai, prof, dias):
        nid = (prof, mov, id(no))
        G.add_node(nid, n=no["n"],
                   label=rotulo(mov) if prof > 0 else "Início do\nprocesso",
                   conclusao=no["conclusao"] if prof > 0 else False,
                   desfecho=no["desfecho"] if prof > 0 else False,
                   outros=no.get("outros", False),
                   truncado=no.get("truncado", False),
                   origem=no.get("mov_origem", mov))
        if pai is not None:
            G.add_edge(pai, nid, peso=no["n"], dias=dias)
        for mov_f, filho in no["filhos"].items():
            d_list = no["dias"].get(mov_f, [])
            dias_med = statistics.mean(d_list) if d_list else None
            registrar(filho, mov_f, nid, prof + 1, dias_med)
        return nid

    raiz_id = registrar(raiz, "Início do processo", None, 0, None)

    # x das folhas por DFS (colunas sequenciais); pais = média dos filhos
    def calcular_x(nid):
        filhos = list(G.successors(nid))
        if not filhos:
            pos[nid] = (contador[0] * x_step, -nid[0])
            contador[0] += 1
        else:
            for f in filhos:
                calcular_x(f)
            pos[nid] = (sum(pos[f][0] for f in filhos) / len(filhos), -nid[0])
    calcular_x(raiz_id)
    return G, pos


def desenhar(G, pos, tempo, media_pos, total, png, svg, gatilhos=None,
             min_dias_label=3):
    prof_max = max(n[0] for n in G.nodes)
    folhas = sum(1 for n in G.nodes if G.out_degree(n) == 0)
    fig, ax = plt.subplots(figsize=(max(18, 0.62 * folhas + 8),
                                    3.4 + 1.6 * prof_max), dpi=140)

    # --- caminho dominante (segue sempre o filho mais volumoso até a folha) ---
    raiz_id = [n for n in G.nodes if n[0] == 0][0]
    dominantes = set()
    nid = raiz_id
    while G.out_degree(nid) > 0:
        nxt = max(G.successors(nid), key=lambda f: G.nodes[f]["n"])
        dominantes.add((nid, nxt))
        nid = nxt

    # --- arestas: largura ∝ volume; GATILHOS (→ conclusão) em vermelho; ---
    # --- caminho dominante em roxo e mais grosso; rótulo μ abaixo do nó   ---
    wmax = max((d["peso"] for _, _, d in G.edges(data=True)), default=1)
    for u, v, d in G.edges(data=True):
        frac = d["peso"] / wmax
        gatilho = G.nodes[v]["conclusao"]
        principal = (u, v) in dominantes
        cor = COR_CONCLUSAO if gatilho else ("#5E35B1" if principal else COR_CORRENTE)
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)], ax=ax, arrowstyle="-|>",
            arrowsize=5 + 6 * frac, edge_color=cor,
            alpha=(0.55 if gatilho else 0.9) * (0.4 + 0.6 * frac),
            width=(0.5 + 4.0 * frac) * (1.4 if principal else 1.0),
            min_source_margin=9, min_target_margin=11)

    # --- nós: círculos (andamento), quadrados (conclusão), anel (desfecho) ---
    circ = [n for n in G.nodes if not G.nodes[n]["conclusao"]]
    quad = [n for n in G.nodes if G.nodes[n]["conclusao"]]
    cores = [COR_INICIO if n[0] == 0 else
             "#9E9E9E" if G.nodes[n]["outros"] else
             plt.cm.Oranges(0.30 + 0.50 * min(1, n[0] / max(1, prof_max)))
             for n in circ]
    nx.draw_networkx_nodes(G, pos, nodelist=circ, node_color=cores, ax=ax,
                           node_size=460, edgecolors="white", linewidths=1.0)
    nx.draw_networkx_nodes(G, pos, nodelist=quad, node_shape="s",
                           node_color=COR_CONCLUSAO, ax=ax, node_size=500,
                           edgecolors="white", linewidths=1.2)
    fins = [n for n in circ if G.nodes[n]["desfecho"] and n[0] > 0]
    nx.draw_networkx_nodes(G, pos, nodelist=fins, node_color="none", ax=ax,
                           node_size=720, edgecolors=COR_DESFECHO,
                           linewidths=1.8, node_shape="o")

# --- rótulos curtos acima dos nós ---
    # --- rótulos curtos acima dos nós ---
    for n, data in G.nodes(data=True):
        x, y = pos[n]
        cor = ("#7F1D1D" if data["conclusao"] else
               "#1B5E20" if data["desfecho"] and n[0] > 0 else "#1F2937")

        # Pega a aresta que chega neste nó para descobrir os dias (se houver pai)
        preds = list(G.predecessors(n))
        dias_txt = ""
        if preds:
            edge_data = G.get_edge_data(preds[0], n)
            if edge_data and edge_data.get("dias") is not None:
                dias_txt = f"μ {edge_data['dias']:.0f}d"

        # 1. Texto principal (Nome + Quantidade + Porcentagem)
        txt_principal = f"{data['label']}\n({data['n']} | {100*data['n']/total:.0f}%)"
        if data["desfecho"] and n[0] > 0:
            txt_principal += " ◆fim"
        if data["truncado"]:
            txt_principal += " ⋯continua"
        if data["outros"]:
            txt_principal += " (rotas raras)"

        ax.text(x, y + 0.32, txt_principal, ha="center", va="bottom", fontsize=6.2,
                color="#555555" if data["outros"] else cor, linespacing=1.05,
                fontweight="bold" if data["outros"] else "normal")

        # 2. Texto secundário (Dias logo abaixo, em cor destacada, ex: roxo)
        if dias_txt:
            eh_gatilho = data["conclusao"]
            eh_dominante = any(v == n for u, v in dominantes)
            ax.text(x, y + 0.16, dias_txt, ha="center", va="bottom", fontsize=5.8,
                    color=COR_CONCLUSAO if eh_gatilho else
                    ("#311B92" if eh_dominante else "#A96403"),
                    weight="bold")

    # --- caixa dos principais GATILHOS pré-conclusão (volume e μ dias) ---
    if gatilhos:
        linhas = ["PRINCIPAIS GATILHOS PRÉ-CONCLUSÃO",
                  "(andamento anterior → volume | μ dias | prof. média)"]
        for g in gatilhos:
            mv = rotulo(g["movimento"], largura=34, max_linhas=1)
            d_txt = f"{g['dias']:.0f}d" if g["dias"] is not None else "—"
            linhas.append(f"• {mv}: {g['n']} | μ {d_txt} | pos. {g['prof']:.1f}")
        ax.text(0.01, 0.99, "\n".join(linhas), transform=ax.transAxes,
                fontsize=7.2, va="top", ha="left", linespacing=1.35,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#FDF3E7",
                          edgecolor=COR_CORRENTE, alpha=0.95))

    tempo_txt = (f"Tempo início → 1ª Conclusão (n={tempo['n']}): "
                 f"média {tempo['media']:.0f}d | mediana {tempo['mediana']:.0f}d | "
                 f"min {tempo['min']}d | max {tempo['max']}d") if tempo["n"] else ""
    
    ax.set_title(
        f"Árvore de Fluxo (Início → desfechos) — {ASSUNTO_ALVO}\n"
        f"{total} processos | média de {media_pos:.1f} posições | "
        f"profundidade máx. exibida: {prof_max}\n"
        f"ARESTAS: nº de processos | μ = dias médios da transição | "
        f"anel verde = desfecho\n{tempo_txt}",
        fontsize=12, pad=14)
    ax.legend(handles=[
        Line2D([0], [0], marker="o", linestyle="", color=plt.cm.Oranges(0.55),
               markersize=9, label="Andamento"),
        Line2D([0], [0], marker="s", linestyle="", color=COR_CONCLUSAO,
               markersize=9, label="Conclusão (gatilho em vermelho)"),
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="none",
               markeredgecolor=COR_DESFECHO, markersize=10,
               label="Desfecho (último movimento)"),
        Line2D([0], [0], marker="o", linestyle="", color="#9E9E9E",
               markersize=9, label="Outros (rotas raras agregadas)"),
        Line2D([0], [0], linestyle="-", color="#5E35B1", lw=2.8,
               label="Caminho dominante (maior volume)"),
        Line2D([0], [0], linestyle="-", color=COR_CORRENTE, lw=2.5,
               label="Transição: largura ∝ volume"),
    ], loc="lower right", fontsize=8, framealpha=0.92)
    ax.axis("off")
    fig.tight_layout()
    os.makedirs(os.path.dirname(png), exist_ok=True)
    fig.savefig(png, bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def exportar(G, base):
    """Nós e arestas (com dias médios) para CSV."""
    with open(base + "_dados.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tipo", "profundidade", "movimento", "processos",
                    "conclusao", "desfecho", "dias_medios_aresta"])
        for n, d in G.nodes(data=True):
            w.writerow(["no", n[0], re.sub(r"\s+", " ", n[1]), d["n"],
                        d["conclusao"], d["desfecho"], ""])
        for u, v, d in G.edges(data=True):
            w.writerow(["aresta", u[0], f"{u[1]} -> {v[1]}", d["peso"],
                        "", "", f"{d['dias']:.1f}" if d["dias"] is not None else ""])


def main():
    ap = argparse.ArgumentParser(description="Árvore de fluxo com métricas de tempo.")
    ap.add_argument("--min-n", type=int, default=2,
                    help="mín. de processos para o ramo ter nó próprio "
                         "(abaixo disso entra em 'Outros') — default 2, mais aberto")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="profundidade máx. (o corte é marcado com '⋯continua')")
    args = ap.parse_args()

    trilhas = carregar_trilhas()
    total = len(trilhas)
    print(f"[1] Assunto '{ASSUNTO_ALVO}': {total} processos.")
    if not total:
        raise SystemExit("Nenhum processo encontrado — verifique o assunto/CSV.")

    raiz, tempo, gatilhos = construir_arvore(trilhas, min_n=args.min_n,
                                             max_depth=args.max_depth)
    media_pos = sum(len(t) for t in trilhas.values()) / total
    print(f"[2] Árvore de prefixos montada (origem completa rastreada; "
          f"rotas com < {args.min_n} processos agregadas em 'Outros').")
    print(f"[3] Tempo início → 1ª Conclusão (n={tempo['n']}): "
          f"média={tempo['media']:.1f}d | mediana={tempo['mediana']:.0f}d | "
          f"mín={tempo['min']}d | máx={tempo['max']}d")
    print("[4] Principais gatilhos pré-conclusão (andamento → n | μ dias | pos.):")
    for g in gatilhos:
        d_txt = f"{g['dias']:.1f}d" if g["dias"] is not None else "—"
        print(f"    - {g['movimento'][:60]}: {g['n']} | μ {d_txt} | pos. {g['prof']:.1f}")

    G, pos = montar_grafo(raiz)
    print(f"[5] Árvore: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas.")

    base = os.path.join(OUT_IMG, "arvore_fluxo_multas")
    desenhar(G, pos, tempo, media_pos, total, base + ".png", base + ".svg",
             gatilhos=gatilhos)
    exportar(G, base)
    print(f"[6] Saídas: {base}.png/.svg + {base}_dados.csv")


if __name__ == "__main__":
    main()
