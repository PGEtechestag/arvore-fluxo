# -*- coding: utf-8 -*-
"""Árvore de fluxo por assunto — direto dos JSONs brutos (outputs_json).

Lê TODOS os JSONs de processo, SEPARA por `assunto` e recria a árvore de
fluxo (usando o mesmo motor gráfico de `arvore_fluxo_multas.py`) apenas para
os assuntos mais comuns — por padrão os 3 principais. Depois, para focar
nos "ademais", basta rodar com --top N ou --assuntos "...".

Pipeline replicado (mesma lógica de assuntot.py + processar_transicoes.py):
  JSON -> movimentações agrupadas por data -> eventos do MESMO dia são
  colapsados num bloco único ("Expedição de documento + Conclusão") ->
  sequência ordenada cronologicamente -> (posicao, movimento, data).

Uso:
  py arvore_fluxo_top3.py                        # top 3 assuntos
  py arvore_fluxo_top3.py --top 5                # top 5
  py arvore_fluxo_top3.py --assuntos "Garantias Constitucionais;Pagamento"
  py arvore_fluxo_top3.py --min-n 5 --max-depth 8

Saídas (visualizacoes/imagens/):
  arvore_fluxo_<slug>.png / .svg + arvore_fluxo_<slug>_dados.csv
"""
import argparse
import gc
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
JSON_DIR = BASE_DIR.parent / "outputs_json"
OUT_IMG = BASE_DIR / "imagens"

# Motor gráfico compartilhado (construir_arvore / montar_grafo / desenhar /
# exportar) — mesmo usado nas árvores de multas e débito fiscal.
sys.path.insert(0, str(BASE_DIR))
import arvore_fluxo_multas as motor  # noqa: E402

IGNORAR = {"catboost_info", "__pycache__"}

# Nomes "amigáveis" para os assuntos mais comuns (fallback = slug genérico)
SLUGS = {
    "Multas e demais Sanções": "multas",
    "Anulação de Débito Fiscal": "debito_fiscal",
    "Valor da Execução / Cálculo / Atualização": "valor_execucao",
}


def slug(assunto):
    """Nome de arquivo seguro/legível a partir do assunto."""
    if assunto in SLUGS:
        return SLUGS[assunto]
    s = unicodedata.normalize("NFKD", assunto).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s[:60] or "assunto"


def montar_trilha(movs):
    """{data 'DD/MM/AAAA': [[mov, detalhe], ...]} -> [(pos, movimento, iso)].

    Une os movimentos do mesmo dia num bloco "A + B" e ordena por data,
    exatamente como faz o processar_transicoes.py.
    """
    itens = []
    for data_str, eventos in movs.items():
        try:
            data_dt = datetime.strptime(data_str, "%d/%m/%Y")
        except (ValueError, TypeError):
            continue
        nomes = [e[0] for e in eventos if e and e[0]]
        nomes = list(dict.fromkeys(nomes))          # remove duplicatas do dia
        if nomes:
            itens.append((data_dt, " + ".join(nomes)))
    itens.sort(key=lambda x: x[0])                  # mais antigo -> mais recente
    return [(i + 1, mov, dta.strftime("%Y-%m-%d"))
            for i, (dta, mov) in enumerate(itens)]


def ler_assuntos():
    """Varre os JSONs e devolve {assunto: {num_processo: [trilha]}}.

    Cada trilha é [(posicao, movimento, data_iso), ...] ordenada por data.
    """
    por_assunto = defaultdict(dict)
    lidos = erros = 0
    for base, dirs, arquivos in os.walk(JSON_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORAR]
        for nome in arquivos:
            if not nome.lower().endswith(".json"):
                continue
            caminho = Path(base) / nome
            try:
                with open(caminho, encoding="utf-8") as f:
                    conteudo = json.load(f)
            except Exception:
                erros += 1
                continue
            dados = conteudo.get("dados") or {}
            if not isinstance(dados, dict) or not dados.get("num_processo"):
                continue                                # não é arquivo de processo
            assunto = (dados.get("assunto") or "").strip()
            movs = conteudo.get("movimentacoes") or {}
            if not assunto or not isinstance(movs, dict) or not movs:
                continue
            trilha = montar_trilha(movs)
            if trilha:
                por_assunto[assunto][dados["num_processo"]] = trilha
                lidos += 1
    return dict(por_assunto), lidos, erros


def selecionar_assuntos(por_assunto, top, pedidos):
    """Assuntos-alvo: os pedidos (--assuntos) ou os `top` mais comuns."""
    if pedidos:
        alvos = [a.strip() for a in pedidos.split(";") if a.strip()]
        faltando = [a for a in alvos if a not in por_assunto]
        if faltando:
            print("    [aviso] não encontrados:", "; ".join(faltando))
        return [a for a in alvos if a in por_assunto]
    ranking = sorted(por_assunto.items(), key=lambda kv: -len(kv[1]))
    return [a for a, _ in ranking[:top]]


def gerar_arvore(assunto, trilhas, min_n, max_depth, indice):
    """Constrói e desenha a árvore de um assunto. Retorna (base, G, tempo)."""
    total = len(trilhas)
    media_pos = sum(len(t) for t in trilhas.values()) / total if total else 0
    motor.ASSUNTO_ALVO = assunto            # garante o título correto na figura
    raiz, tempo, gatilhos = motor.construir_arvore(trilhas, min_n=min_n,
                                                   max_depth=max_depth)
    G, pos = motor.montar_grafo(raiz)
    base = os.path.join(OUT_IMG, f"arvore_fluxo_{slug(assunto)}")
    print(f"[{indice}] {assunto}")
    print(f"     {total} processos | {G.number_of_nodes()} nós | "
          f"tempo até 1ª Conclusão: μ {tempo['media']:.1f}d "
          f"(mediana {tempo['mediana']:.0f}d, n={tempo['n']})")
    motor.desenhar(G, pos, tempo, media_pos, total,
                   base + ".png", base + ".svg", gatilhos=gatilhos)
    motor.exportar(G, base)
    print(f"     -> {base}.png/.svg + _dados.csv")
    return base, G, tempo


def main():
    ap = argparse.ArgumentParser(
        description="Recria a árvore de fluxo para os assuntos mais comuns.")
    ap.add_argument("--top", type=int, default=3,
                    help="quantos assuntos mais comuns gerar (default 3)")
    ap.add_argument("--assuntos", type=str, default=None,
                    help="assuntos específicos separados por ';' "
                         "(sobrepõe --top)")
    ap.add_argument("--min-n", type=int, default=2,
                    help="mín. de processos para o ramo ter nó próprio "
                         "(abaixo vira 'Outros') — default 2")
    ap.add_argument("--max-depth", type=int, default=None,
                    help="profundidade máx. (corte marcado com '⋯continua')")
    args = ap.parse_args()

    print(f"[1] Lendo JSONs em {JSON_DIR} ...")
    por_assunto, lidos, erros = ler_assuntos()
    print(f"    processos lidos: {lidos} (erros: {erros}) | "
          f"assuntos distintos: {len(por_assunto)}")

    ranking = sorted(por_assunto.items(), key=lambda kv: -len(kv[1]))
    print("[2] Ranking (top 10):")
    for i, (a, procs) in enumerate(ranking[:10], 1):
        print(f"    {i:>2}. {len(procs):>4}  {a}")

    alvos = selecionar_assuntos(por_assunto, args.top, args.assuntos)
    if not alvos:
        raise SystemExit("Nenhum assunto selecionado — verifique --top/--assuntos.")
    print("[3] Gerando árvores para:", "; ".join(alvos))

    os.makedirs(OUT_IMG, exist_ok=True)
    # Mantém só os assuntos-alvo e libera os demais (economiza memória para
    # desenhar figuras grandes).
    alvo_trilhas = {a: por_assunto[a] for a in alvos}
    por_assunto.clear()
    gc.collect()

    for i, assunto in enumerate(alvos, 1):
        try:
            gerar_arvore(assunto, alvo_trilhas[assunto], args.min_n,
                         args.max_depth, i + 3)
        except MemoryError:
            print(f"     [erro] memória insuficiente para desenhar "
                  f"'{assunto}' com --min-n {args.min_n}. "
                  f"Rode de novo com --min-n maior (ex.: 5) para podar mais.")
        alvo_trilhas[assunto] = None            # libera após desenhar
        gc.collect()

    print("[fim] Concluído. Saídas em", OUT_IMG)


if __name__ == "__main__":
    main()