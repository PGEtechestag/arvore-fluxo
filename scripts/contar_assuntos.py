# -*- coding: utf-8 -*-
"""Conta os ASSUNTOS mais comuns nos JSONs de processos (outputs_json).

Varre todos os *.json das pastas de órgãos/anos e ranqueia o campo
`dados.assunto` (somando também `dados.outros_assuntos`), com recorte por
órgão julgador e por ano (pasta). Serve para descobrir quais fluxos existem
além de "Multas e demais Sanções" e "Anulação de Débito Fiscal".

Uso:
  py contar_assuntos.py                 # top 40 no console
  py contar_assuntos.py --top 100       # mostra mais linhas

Saídas (mesma pasta):
  - assuntos_contagem.csv   (ano, orgao_julgador, assunto, processos)
  - assuntos_resumo.txt     (tabela pronta para leitura)
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

RAIZ = Path(__file__).resolve().parent.parent / "outputs_json"
IGNORAR = {"catboost_info", "__pycache__", "outputs"}


def parse_ano(pasta_ano):
    """'2023' -> 2023 (ou None se não for ano)."""
    try:
        return int(str(pasta_ano).strip()[:4])
    except (ValueError, TypeError):
        return None


def varrer():
    """{(ano, orgao, assunto): n_processos} + totais auxiliares."""
    por_chave = defaultdict(set)          # -> conjunto de num_processo
    orgaos = set()
    anos = set()
    json_lidos = 0
    json_erro = 0

    for base, dirs, arquivos in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for nome in arquivos:
            if not nome.lower().endswith(".json"):
                continue
            caminho = Path(base) / nome
            try:
                with open(caminho, encoding="utf-8") as f:
                    conteudo = json.load(f)
            except Exception:
                json_erro += 1
                continue
            dados = conteudo.get("dados", {}) or {}
            # ignora arquivos que não são de processo (ex.: rotas/escala)
            if not isinstance(dados, dict) or not dados.get("num_processo"):
                continue
            json_lidos += 1
            proc = dados["num_processo"]
            orgao = (dados.get("orgao_julgador") or "DESCONHECIDO").strip()
            # ano = pasta relativa (ex.: '04 FAZENDA .../2023')
            rel = caminho.relative_to(RAIZ).parts
            ano = parse_ano(rel[1]) if len(rel) > 1 else None
            # fallback: ano embutido no nº do processo (.2024.)
            if ano is None and "." in str(proc):
                partes = str(proc).split(".")
                if len(partes) > 1 and partes[1].isdigit():
                    ano = int(partes[1])

            assuntos = []
            principal = (dados.get("assunto") or "").strip()
            if principal:
                assuntos.append(principal)
            for extra in (dados.get("outros_assuntos") or []):
                extra = (extra or "").strip()
                if extra and extra not in assuntos:
                    assuntos.append(extra)
            if not assuntos:
                assuntos = ["(sem assunto)"]

            orgaos.add(orgao)
            if ano is not None:
                anos.add(ano)
            for a in assuntos:
                por_chave[(ano, orgao, a)].add(proc)

    return por_chave, orgaos, anos, json_lidos, json_erro


def main():
    ap = argparse.ArgumentParser(description="Ranking de assuntos nos JSONs.")
    ap.add_argument("--top", type=int, default=40, help="linhas exibidas no console")
    args = ap.parse_args()

    por_chave, orgaos, anos, lidos, erro = varrer()

    # --- Agregado geral: processos únicos por assunto ---
    procs_por_assunto = defaultdict(set)
    for (ano, orgao, assunto), procs in por_chave.items():
        procs_por_assunto[assunto] |= procs
    geral = Counter({a: len(p) for a, p in procs_por_assunto.items()})
    total_procs = len(set().union(*procs_por_assunto.values())) if procs_por_assunto else 0

    linhas = []
    linhas.append("=" * 78)
    linhas.append("ASSUNTOS MAIS COMUNS — base: JSONs de processos (outputs_json)")
    linhas.append(f"JSONs lidos: {lidos} (com erro: {erro}) | "
                  f"processos distintos: {total_procs} | assuntos distintos: {len(geral)}")
    linhas.append(f"Anos: {sorted(a for a in anos if a)} | Órgãos: {len(orgaos)}")
    linhas.append("=" * 78)
    linhas.append("")
    linhas.append(f"{'#':>3}  {'ASSUNTO':<52} {'PROCS':>7} {'%':>7}")
    linhas.append("-" * 78)
    for i, (assunto, n) in enumerate(geral.most_common(args.top), 1):
        pct = 100.0 * n / total_procs if total_procs else 0
        linhas.append(f"{i:>3}  {assunto[:52]:<52} {n:>7} {pct:>6.1f}%")
    linhas.append("-" * 78)

    # --- Por órgão julgador ---
    linhas.append("")
    linhas.append("POR ÓRGÃO JULGADOR (top 10 assuntos de cada)")
    for orgao in sorted(orgaos):
        c = Counter()
        for (ano, o, assunto), procs in por_chave.items():
            if o == orgao:
                c[assunto] += len(procs)
        linhas.append("")
        linhas.append(f"### {orgao}")
        for assunto, n in c.most_common(10):
            linhas.append(f"    {n:>6}  {assunto[:60]}")

    # --- Por ano ---
    linhas.append("")
    linhas.append("POR ANO (top 10 assuntos de cada)")
    for ano in sorted(a for a in anos if a):
        c = Counter()
        for (a, orgao, assunto), procs in por_chave.items():
            if a == ano:
                c[assunto] += len(procs)
        linhas.append("")
        linhas.append(f"### {ano}")
        for assunto, n in c.most_common(10):
            linhas.append(f"    {n:>6}  {assunto[:60]}")

    texto = "\n".join(linhas)
    print(texto)

    with open(RAIZ / "assuntos_resumo.txt", "w", encoding="utf-8") as f:
        f.write(texto + "\n")

    with open(RAIZ / "assuntos_contagem.csv", "w", encoding="utf-8-sig",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(["ano", "orgao_julgador", "assunto", "processos"])
        for (ano, orgao, assunto), procs in sorted(
                por_chave.items(), key=lambda kv: -len(kv[1])):
            w.writerow([ano if ano else "", orgao, assunto, len(procs)])

    print(f"\nSaídas: {RAIZ / 'assuntos_contagem.csv'} + assuntos_resumo.txt")


if __name__ == "__main__":
    main()
