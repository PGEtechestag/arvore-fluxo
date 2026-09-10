# -*- coding: utf-8 -*-
"""Diagnóstico estrutural das árvores geradas (níveis, nós, arestas)."""
from collections import Counter
from analise_rotas import load_data, ASSUNTOS


def montar(seqs, n_camadas=4, topk=5):
    n = len(seqs)
    levels = [[("Início do processo", n)]]
    for d in range(1, n_camadas + 1):
        alcance = [s for s in seqs.values() if len(s) >= d]
        dist = Counter(s[d - 1] for s in alcance)
        levels.append(dist.most_common(topk))
    desfechos = Counter(s[-1] for s in seqs.values() if s).most_common(4)
    levels.append(desfechos)

    arestas = []
    for mov, peso in levels[1]:
        arestas.append((0, "Início do processo", mov, peso, 0))
    for d in range(1, n_camadas):
        pares = Counter()
        for s in seqs.values():
            if len(s) >= d + 1:
                pares[(s[d - 1], s[d])] += 1
        filhos_ok = {m for m, _ in levels[d + 1]}
        pais_ok = {m for m, _ in levels[d]}
        for (pa, fi), peso in pares.items():
            if pa in pais_ok and fi in filhos_ok:
                arestas.append((d, pa, fi, peso, 0))
    desf_ok = {m for m, _ in desfechos}
    for d in range(1, n_camadas + 1):
        par_fim = Counter()
        for s in seqs.values():
            if len(s) >= d and s[-1] in desf_ok:
                par_fim[(s[d - 1], s[-1])] += 1
        pais_ok = {m for m, _ in levels[d]}
        for (pa, fi), peso in par_fim.items():
            if pa in pais_ok:
                arestas.append((d, pa, fi, peso, 1))
    return levels, arestas


def main():
    sequencias = load_data()
    for assunto in ASSUNTOS:
        seqs = {k: v for k, v in sequencias.items() if k[1] == assunto}
        levels, arestas = montar(seqs)
        print("=" * 70)
        print(assunto, "| n =", len(seqs))
        for lv, nos in enumerate(levels):
            rot = "RAIZ" if lv == 0 else ("DESFECHO" if lv == len(levels) - 1 else f"POS {lv}")
            mostra = "; ".join(f"{m[:44]} ({c})" for m, c in nos[:5])
            print(f"  [{rot}] {len(nos)} nós | {mostra}")
        n_norm = sum(1 for a in arestas if a[4] == 0)
        n_fim = sum(1 for a in arestas if a[4] == 1)
        print(f"  arestas normais={n_norm}, desfecho={n_fim}")
        cobertura = sum(c for m, c in levels[1]) / len(seqs) * 100
        print(f"  cobertura 1ª posição (top5): {cobertura:.1f}%")


if __name__ == "__main__":
    main()