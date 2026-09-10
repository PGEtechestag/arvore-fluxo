# -*- coding: utf-8 -*-
"""Process Mining — fluxo do Início até a 1ª Conclusão (Multas e demais Sanções).

Metodologia:
  1. Filtra exclusivamente o assunto "Multas e demais Sanções".
  2. Ordena o histórico por `posicao` e corta a trajetória de cada processo
     no exato momento da PRIMEIRA "Conclusão" (detecção por palavra inteira,
     inclusive em movimentos combinados com '+', ex.: "... + Conclusão").
  3. Calcula a posição MÉDIA (profundidade média) dos caminhos cortados e
     limita a árvore exatamente a essa profundidade (rigor estatístico).
  4. Calcula as métricas de TEMPO (em dias) entre o início do processo e a
     primeira Conclusão: média, mediana, mínimo e máximo (via data_movimento).
  5. Gera a árvore de fluxo agregada com networkx + matplotlib (PNG/SVG),
     com rótulos curtos/quebrados para evitar sobreposição de texto, nós de
     conclusão em destaque e o resumo de tempo exibido no título.

Saídas (em visualizacoes/imagens/):
  - fluxo_primeira_conclusao_multas.png / .svg
  - fluxo_primeira_conclusao_multas_arestas.csv (nos/arestas agregados)
"""
import csv
import os
import re
import textwrap
from collections import Counter, defaultdict
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "outputs_json", "tabela_posicao_tempo_processos.csv")
OUT_IMG = os.path.join(BASE_DIR, "imagens")
ASSUNTO_ALVO = "Multas e demais Sanções"

# "Conclusão" como palavra inteira (não casa "Concluso", "Conclusões" etc.).
RE_CONCLUSAO = re.compile(r"(?i)\bconclusão\b")

COR_INICIO = "#37474F"
COR_CORRENTE = "#B45309"
COR_CONCLUSAO = "#B71C1C"


def carregar_caminhos():
    """Lê o CSV e devolve {num_processo: [(posicao, movimento, data_iso), ...]}.

    A lista já vem ordenada por `posicao` (trajetória do processo).
    """
    seqs = defaultdict(list)
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["assunto"].strip() == ASSUNTO_ALVO:
                seqs[r["num_processo"]].append(
                    (int(r["posicao"]), r["movimento_atual"], r["data_movimento"]))
    for lista in seqs.values():
        lista.sort(key=lambda x: x[0])
    return dict(seqs)


def cortar_na_primeira_conclusao(movimentos):
    """Retorna o prefixo INCLUSIVE o movimento da primeira Conclusão, ou None.

    `movimentos` pode ser a lista de strings ou de tuplas (pos, mov, data).
    """
    for i, mov in enumerate(movimentos):
        texto = mov if isinstance(mov, str) else mov[1]
        if RE_CONCLUSAO.search(texto):
            return movimentos[: i + 1]
    return None


def estatisticas_tempo(cortados):
    """Dias entre o 1º andamento e o andamento da 1ª Conclusão de cada processo.

    `cortados` = {proc: [(pos, mov, data_iso), ...]} já cortado.
    Retorna (dias, resumo) onde resumo = dict com média, mediana, min e max.
    Andamentos sem data válida são ignorados (processo excluído da métrica).
    """
    dias = []
    for andamentos in cortados.values():
        try:
            d_ini = date.fromisoformat(andamentos[0][2])
            d_fim = date.fromisoformat(andamentos[-1][2])
        except (ValueError, TypeError, IndexError):
            continue          # data ausente/malformada: fora da estatística
        dias.append((d_fim - d_ini).days)
    ordenados = sorted(dias)
    n = len(ordenados)
    mediana = (ordenados[n // 2] if n % 2 else
               (ordenados[n // 2 - 1] + ordenados[n // 2]) / 2) if n else 0
    resumo = {
        "n": n,
        "media": sum(ordenados) / n if n else 0,
        "mediana": mediana,
        "min": min(ordenados) if n else 0,
        "max": max(ordenados) if n else 0,
    }
    return dias, resumo


def rotulo_curto(texto, largura=16, max_linhas=3):
    """Encurta e quebra o rótulo para não poluir a visualização."""
    texto = re.sub(r"\s+", " ", texto).strip()
    linhas = textwrap.wrap(texto, width=largura)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        linhas[-1] = linhas[-1][: largura - 1].rstrip() + "…"
    return "\n".join(linhas)

def construir_niveis(caminhos, profundidade, topk=12, min_n=2):
    """Agrega os caminhos cortados em níveis por posição.

    Por rigor estatístico e legibilidade, em cada nível mantém apenas os
    `topk` movimentos mais frequentes com ao menos `min_n` processos
    (a cauda rara é omitida da visualização; os percentuais são calculados
    sempre sobre o total de processos).
    Retorna (niveis, arestas):
      niveis[p]  = [(movimento, n_processos), ...] ordenado por frequência
      arestas    = [(nivel_pai, mov_pai, mov_filho, peso), ...]
    """
    niveis = [[("Início do processo", len(caminhos))]]
    for p in range(1, profundidade + 1):
        alcance = [s for s in caminhos.values() if len(s) >= p]
        dist = [(m, c) for m, c in Counter(s[p - 1] for s in alcance).most_common(topk)
                if c >= min_n]
        niveis.append(dist)

    arestas = []
    for mov, peso in niveis[1]:
        arestas.append((0, "Início do processo", mov, peso))
    for p in range(1, profundidade):
        trans = Counter()
        for s in caminhos.values():
            if len(s) >= p + 1:
                trans[(s[p - 1], s[p])] += 1
        pais = {m for m, _ in niveis[p]}
        filhos = {m for m, _ in niveis[p + 1]}
        for (pa, fi), w in trans.items():
            if pa in pais and fi in filhos:
                arestas.append((p, pa, fi, w))
    return niveis, arestas


def montar_grafo(niveis, arestas):
    """Monta o DiGraph networkx com layout em camadas (y = posição)."""
    G = nx.DiGraph()
    pos = {}
    for p, nos in enumerate(niveis):
        ordem = nos if p == 0 else sorted(nos, key=lambda x: -x[1])
        for i, (mov, n) in enumerate(ordem):
            no = (p, mov)
            G.add_node(no, n=n, label=rotulo_curto(mov),
                       conclusao=bool(RE_CONCLUSAO.search(mov)) if p > 0 else False)
            pos[no] = (i - (len(ordem) - 1) / 2.0, -p)
    for p, pa, fi, w in arestas:
        G.add_edge((p, pa), (p + 1, fi), peso=w)
    return G, pos


def desenhar(G, pos, niveis, profundidade, media, tempo, caminho_png, caminho_svg):
    total = niveis[0][0][1]
    fig, ax = plt.subplots(figsize=(22, 3 + 2.2 * profundidade), dpi=150)

    # --- arestas (curvadas, largura ∝ frequência) ---
    pesos = [d["peso"] for _, _, d in G.edges(data=True)]
    wmax = max(pesos, default=1)
    for (u, v, d) in G.edges(data=True):
        frac = d["peso"] / wmax
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)], ax=ax,
            arrowstyle="-|>", arrowsize=10 - 4 * (1 - frac),
            edge_color=COR_CORRENTE, alpha=0.25 + 0.6 * frac,
            width=0.6 + 4.5 * frac,
            connectionstyle="arc3,rad=0.12", min_source_margin=14,
            min_target_margin=16)

    # --- nós ---
    xs = [pos[n][0] for n in G.nodes]
    espalhamento = (max(xs) - min(xs)) if xs else 1.0
    tam = max(250, min(1300, 30000 / max(1, espalhamento)))
    concl = [n for n in G.nodes if G.nodes[n]["conclusao"]]
    outros = [n for n in G.nodes if not G.nodes[n]["conclusao"]]
    cmap = plt.cm.Oranges
    cores = {n: cmap(0.30 + 0.55 * (n[0] / max(1, profundidade))) for n in outros}
    nx.draw_networkx_nodes(G, pos, nodelist=outros, ax=ax, node_shape="o",
                           node_color=[cores[n] for n in outros],
                           edgecolors="white", linewidths=1.2, node_size=tam)
    nx.draw_networkx_nodes(G, pos, nodelist=concl, ax=ax, node_shape="s",
                           node_color=COR_CONCLUSAO, edgecolors="white",
                           linewidths=1.2, node_size=tam * 1.15)

    # --- rótulos curtos acima dos nós ---
    for n, data in G.nodes(data=True):
        x, y = pos[n]
        cor = "#7F1D1D" if data["conclusao"] else "#1F2937"
        ax.text(x, y + 0.34,
                f"{data['label']}\n({data['n']} | {100*data['n']/total:.0f}%)",
                ha="center", va="bottom", fontsize=7.2, color=cor, linespacing=1.05)

    titulo_tempo = (f"\nTempo início → 1ª Conclusão (dias): média {tempo['media']:.0f} | "
                    f"mediana {tempo['mediana']:.0f} | min {tempo['min']} | "
                    f"max {tempo['max']} (n={tempo['n']})"
                    if tempo else "")
    ax.set_title(
        f"Fluxo Início → 1ª Conclusão — {ASSUNTO_ALVO}\n"
        f"{total} processos | profundidade média = {media:.2f} posições "
        f"(árvore cortada em {profundidade})"
        + titulo_tempo,
        fontsize=13, pad=14)
    legenda = [
        Line2D([0], [0], marker="o", linestyle="", color=cmap(0.55), markersize=9,
               label="Movimento do fluxo"),
        Line2D([0], [0], marker="s", linestyle="", color=COR_CONCLUSAO, markersize=9,
               label="Conclusão (corte)"),
        Line2D([0], [0], linestyle="-", color=COR_CORRENTE, lw=2.5,
               label="Transição (largura ∝ nº de processos)"),
    ]
    ax.legend(handles=legenda, loc="lower right", fontsize=8, framealpha=0.9)
    ax.axis("off")
    fig.tight_layout()
    os.makedirs(os.path.dirname(caminho_png), exist_ok=True)
    fig.savefig(caminho_png, bbox_inches="tight", facecolor="white")
    fig.savefig(caminho_svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def exportar_csv(niveis, arestas, base):
    with open(base + "_nos.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["posicao", "movimento", "processos"])
        for p, nos in enumerate(niveis):
            for mov, n in nos:
                w.writerow([p, mov, n])
    with open(base + "_arestas.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pos_pai", "mov_pai", "pos_filho", "mov_filho", "processos"])
        for p, pa, fi, peso in arestas:
            w.writerow([p, pa, p + 1, fi, peso])



def main():
    caminhos = carregar_caminhos()
    print(f"[1] Assunto '{ASSUNTO_ALVO}': {len(caminhos)} processos no CSV.")

    cortados, sem_conclusao = {}, 0
    for proc, andamentos in caminhos.items():
        c = cortar_na_primeira_conclusao(andamentos)
        if c:
            cortados[proc] = c
        else:
            sem_conclusao += 1
    print(f"[2] Corte na 1ª Conclusão: {len(cortados)} processos cortados; "
          f"{sem_conclusao} sem Conclusão no histórico (excluídos da árvore).")

    profundidades = [len(s) for s in cortados.values()]
    media = sum(profundidades) / len(profundidades)
    profundidade = round(media)          # limite inteiro = posição média
    print(f"[3] Posição média até a 1ª Conclusão: {media:.2f} "
          f"(min={min(profundidades)}, max={max(profundidades)}) → "
          f"árvore limitada à profundidade {profundidade}.")

    # --- Métricas de tempo (dias): início do processo → 1ª Conclusão ---
    dias, tempo = estatisticas_tempo(cortados)
    print(f"[4] Tempo início → 1ª Conclusão (dias), n={tempo['n']}: "
          f"média={tempo['media']:.1f} | mediana={tempo['mediana']:.0f} | "
          f"mínimo={tempo['min']} | máximo={tempo['max']}")

    niveis, arestas = construir_niveis(
        {p: [mov for _, mov, _ in a] for p, a in cortados.items()},
        profundidade)
    G, pos = montar_grafo(niveis, arestas)
    print(f"[5] Grafo: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas.")

    base_img = os.path.join(OUT_IMG, "fluxo_primeira_conclusao_multas")
    desenhar(G, pos, niveis, profundidade, media, tempo,
             base_img + ".png", base_img + ".svg")
    exportar_csv(niveis, arestas, base_img)
    print(f"[6] Saídas salvas em: {base_img}.png/.svg (+ _nos.csv/_arestas.csv)")


if __name__ == "__main__":
    main()

