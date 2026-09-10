# -*- coding: utf-8 -*-
"""Mede a escala da teia completa por assunto (nós, ramos, rotas únicas)."""
import json
from collections import Counter

from analise_rotas import load_data, ASSUNTOS

OUT = r"c:\Users\Íris\Desktop\api-cnj - Copia\visualizacoes\escala_teia.json"


def main():
    sequencias = load_data()
    report = {}
    for assunto in ASSUNTOS:
        seqs = [s for k, s in sequencias.items() if k[1] == assunto]
        n = len(seqs)
        compr = [len(s) for s in seqs]
        max_pos = max(compr) if compr else 0

        # nós distintos por posição
        nos_por_pos = []
        for p in range(1, max_pos + 1):
            alcance = [s for s in seqs if len(s) >= p]
            dist = Counter(s[p - 1] for s in alcance)
            nos_por_pos.append({
                "posicao": p,
                "n_alcance": len(alcance),
                "n_distintos": len(dist),
                "top5_cobrem_pct": round(100 * sum(c for _, c in dist.most_common(5)) / len(alcance), 1),
                "top10_cobrem_pct": round(100 * sum(c for _, c in dist.most_common(10)) / len(alcance), 1),
                "singleton_ramos": sum(1 for _, c in dist.items() if c == 1),
            })
        total_nos = sum(v["n_distintos"] for v in nos_por_pos)

        # arestas distintas / transições
        transicoes = Counter()
        rotas = Counter()
        for s in seqs:
            rotas[" > ".join(s)] += 1
            for a, b in zip(s, s[1:]):
                transicoes[(a, b)] += 1

        singletons = sum(1 for v in rotas.values() if v == 1)
        # rotas com ocorrencia >=2 (% de processos em rotas repetidas)
        proc_repetidos = sum(v for v in rotas.values() if v >= 2)

        report[assunto] = {
            "n_processos": n,
            "media_posicoes": round(sum(compr) / n, 1),
            "mediana_posicoes": sorted(compr)[n // 2] if n % 2 else
                                (sorted(compr)[n // 2 - 1] + sorted(compr)[n // 2]) / 2,
            "max_posicoes": max_pos,
            "dist_comprimento": {
                "min": min(compr), "q1": sorted(compr)[n // 4],
                "q2": sorted(compr)[n // 2], "q3": sorted(compr)[3 * n // 4],
                "max": max(compr)},
            "total_nos_distintos": total_nos,
            "total_arestas_distintas": len(transicoes),
            "nos_por_posicao": nos_por_pos,
            "rotas_unicas": len(rotas),
            "rotas_singleton": singletons,
            "pct_processos_em_rota_unica": round(100 * singletons / n, 1),
            "pct_processos_em_rotas_repetidas": round(100 * proc_repetidos / n, 1),
            "top_rotas": [{"seq_curta": " > ".join(s)[:140], "n": v}
                          for s, v in rotas.most_common(5)],
        }
        print("=" * 80)
        d = report[assunto]
        print(f"[{assunto}] n={n} max={max_pos} nos_distintos={total_nos} "
              f"arestas={len(transicoes)}")
        print(f"  rotas_unicas={len(rotas)} singleton={singletons} "
              f"({d['pct_processos_em_rota_unica']}%) repetidas={proc_repetidos} "
              f"({d['pct_processos_em_rotas_repetidas']}%)")
        print("  comprimento:", d["dist_comprimento"])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("salvo:", OUT)


if __name__ == "__main__":
    main()