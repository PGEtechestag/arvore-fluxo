# -*- coding: utf-8 -*-
"""Analisa as sequências reais de movimentações por assunto a partir do CSV."""
import csv
import json
import os
from collections import Counter, OrderedDict, defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "outputs_json", "tabelas",
                    "tabela_posicao_tempo_processos.csv")
OUT_JSON = os.path.join(BASE_DIR, "rotas_por_assunto.json")

ASSUNTOS = ["Anulação de Débito Fiscal", "Multas e demais Sanções", "Valor da Execução / Cálculo / Atualização"]


def load_data():
    """Lê o CSV agrupando as posições por processo+assunto."""
    sequencias = defaultdict(list)          # (processo, assunto) -> lista de (posicao, movimento)
    rows = defaultdict(list)                # (processo, assunto) -> lista de dicts ordenados
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key = (r["num_processo"], r["assunto"])
            sequencias[key].append((int(r["posicao"]), r["movimento_atual"], r["data_movimento"]))
            rows[key].append(r)
    # ordena por posicao e reduz a lista de movimentos
    out = {}
    for key, lista in sequencias.items():
        lista.sort(key=lambda x: x[0])
        out[key] = [m for _, m, _ in lista]
    return out


def mediana(vals):
    vals = sorted(vals)
    n = len(vals)
    if n % 2 == 1:
        return vals[n // 2]
    return (vals[n // 2 - 1] + vals[n // 2]) / 2


def analyze(sequencias):
    resultado = {}
    for assunto in ASSUNTOS:
        seqs = {k: v for k, v in sequencias.items() if k[1] == assunto}
        n_proc = len(seqs)
        compr = [len(v) for v in seqs.values()]

        primeiros = Counter()
        ultimos = Counter()
        transicoes = Counter()
        caminhos = Counter()

        for seq in seqs.values():
            if not seq:
                continue
            primeiros[seq[0]] += 1
            ultimos[seq[-1]] += 1
            caminhos[" > ".join(seq)] += 1
            for a, b in zip(seq, seq[1:]):
                transicoes[(a[:80], b[:80])] += 1

        # Funil por posição: quantos processos chegam a cada profundidade
        # e quais são os movimentos mais comuns lá (sobre quem chega).
        funil = []
        max_pos = max(compr) if compr else 0
        for p in range(1, max_pos + 1):
            alcance = [s for s in seqs.values() if len(s) >= p]
            dist = Counter(s[p - 1] for s in alcance)
            funil.append({
                "posicao": p,
                "n_alcance": len(alcance),
                "pct_retencao": round(100 * len(alcance) / n_proc, 1) if n_proc else 0,
                "top_movimentos": [(m, c, round(100 * c / len(alcance), 1))
                                   for m, c in dist.most_common(6)],
            })

        resultado[assunto] = {
            "n_processos": n_proc,
            "media_posicoes": round(sum(compr) / n_proc, 1) if n_proc else 0,
            "mediana_posicoes": mediana(compr) if n_proc else 0,
            "primeiro_movimento": {k: v for k, v in primeiros.most_common(12)},
            "ultimo_movimento": {k: v for k, v in ultimos.most_common(12)},
            "transicoes_top": [(list(k), v) for k, v in transicoes.most_common(25)],
            "caminhos_top": [{ "seq": k.split(" > "), "n": v,
                              "pct": round(100 * v / n_proc, 1)}
                             for k, v in caminhos.most_common(20)],
            "funil_por_posicao": funil,
        }
    return resultado


def main():
    sequencias = load_data()
    res = analyze(sequencias)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)

    # impressão resumida
    for assunto, d in res.items():
        print("=" * 60)
        print(f"[{assunto}]  n={d['n_processos']}  media={d['media_posicoes']}  mediana={d['mediana_posicoes']}")
        print("  PRIMEIROS:", list(d["primeiro_movimento"].items())[:6])
        print("  ULTIMOS:", list(d["ultimo_movimento"].items())[:6])
        print("  FUNIL (pos | retenção % | top movimentos):")
        for f in d["funil_por_posicao"][:10]:
            t = "; ".join(f"{m} ({p}%)" for m, c, p in f["top_movimentos"][:3])
            print(f"    pos {f['posicao']:>2} | {f['pct_retencao']:>6}% | {t[:140]}")

        print("  TRANSICOES TOP 12:")
        for (a, b), v in d["transicoes_top"][:12]:
            print(f"    {a}  ->  {b}   ({v})")
        print("  CAMINHOS (seq completa) TOP 10:")
        for c in d["caminhos_top"][:10]:
            print("    ", " > ".join(c["seq"])[:150], f" -> {c['n']} ({c['pct']}%)")
    print("\nJSON salvo em:", OUT_JSON)


if __name__ == "__main__":
    main()