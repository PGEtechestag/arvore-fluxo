"""
Helper para descobrir o codigo numerico de um orgao julgador (vara/camara)
em qualquer Tribunal de Justica estadual, usando a API Publica do DataJud
(CNJ).

A API nao tem um endpoint dedicado de "listar orgaos julgadores" nem
documenta suporte a agregacoes - entao esse script faz uma busca comum por
texto no campo orgaoJulgador.nome e extrai, dos processos retornados, os
pares (codigo, nome, municipio IBGE) unicos encontrados. Nao e uma lista
exaustiva de todos os orgaos, mas normalmente e suficiente pra achar o
codigo que voce quer (se aparecer mais de um resultado parecido, rode de
novo com um termo mais especifico, tipo incluindo a comarca).

Uso (interativo - pede o nome e o estado):
    python buscar_orgao_julgador.py

Uso (direto por linha de comando, sem prompts):
    python buscar_orgao_julgador.py --termo "Vara de Fazenda Publica" --estado SP --tamanho 50
"""

import argparse
import json
import time

import requests

API_KEY = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

# Justica Estadual - 27 Tribunais de Justica (UF -> alias do endpoint)
UF_PARA_ALIAS = {
    "AC": "tjac", "AL": "tjal", "AM": "tjam", "AP": "tjap", "BA": "tjba",
    "CE": "tjce", "DF": "tjdft", "ES": "tjes", "GO": "tjgo", "MA": "tjma",
    "MG": "tjmg", "MS": "tjms", "MT": "tjmt", "PA": "tjpa", "PB": "tjpb",
    "PE": "tjpe", "PI": "tjpi", "PR": "tjpr", "RJ": "tjrj", "RN": "tjrn",
    "RO": "tjro", "RR": "tjrr", "RS": "tjrs", "SC": "tjsc", "SE": "tjse",
    "SP": "tjsp", "TO": "tjto",
}

TIMEOUT_REQ = 30
MAX_RETRIES = 2  # deliberadamente baixo: isso e uma consulta pontual, nao uma coleta em lote


def montar_url(uf: str) -> str:
    alias = UF_PARA_ALIAS[uf]
    return f"https://api-publica.datajud.cnj.jus.br/api_publica_{alias}/_search"


def montar_query(termo: str, tamanho: int) -> dict:
    return {
        "size": tamanho,
        "_source": ["orgaoJulgador"],
        "query": {
            "match": {
                "orgaoJulgador.nome": {
                    "query": termo,
                    "operator": "and",
                }
            }
        },
    }


def buscar(url: str, payload: dict) -> dict:
    headers = {
        "Authorization": f"ApiKey {API_KEY}",
        "Content-Type": "application/json",
    }

    for tentativa in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=TIMEOUT_REQ)
        except requests.RequestException as e:
            if tentativa == MAX_RETRIES:
                raise
            print(f"[REDE] erro={e!r}, tentando novamente...")
            time.sleep(5)
            continue

        if resp.status_code == 429 or resp.status_code >= 500:
            if tentativa == MAX_RETRIES:
                resp.raise_for_status()
            print(f"[HTTP {resp.status_code}] API instavel, tentando novamente...")
            time.sleep(5)
            continue

        resp.raise_for_status()
        return json.loads(resp.content.decode("utf-8"))

    raise RuntimeError("Nao foi possivel completar a consulta.")


def pedir_termo() -> str:
    while True:
        termo = input("Nome (ou parte do nome) do orgao julgador: ").strip()
        if termo:
            return termo
        print("[ERRO] Digite algum texto para buscar.")


def pedir_estado() -> str:
    while True:
        estado = input("Estado (UF, ex: SP, RJ, MG): ").strip().upper()
        if estado in UF_PARA_ALIAS:
            return estado
        print(f"[ERRO] UF invalida: {estado!r}. Use uma sigla de estado valida, ex: SP.")


def main():
    parser = argparse.ArgumentParser(description="Descobre o codigo de orgaoJulgador em um TJ estadual a partir de um termo de busca.")
    parser.add_argument("--termo", help='Texto a buscar no nome do orgao julgador, ex: "Vara de Fazenda Publica". Se omitido, sera perguntado.')
    parser.add_argument("--estado", help="UF do tribunal (ex: SP, RJ, MG). Se omitido, sera perguntado.")
    parser.add_argument("--tamanho", type=int, default=50, help="Quantos processos amostrar para extrair orgaos (default: 50)")
    args = parser.parse_args()

    termo = args.termo.strip() if args.termo else pedir_termo()

    estado = args.estado.strip().upper() if args.estado else ""
    if estado and estado not in UF_PARA_ALIAS:
        print(f"[ERRO] UF invalida: {estado!r}.")
        estado = ""
    if not estado:
        estado = pedir_estado()

    url = montar_url(estado)
    payload = montar_query(termo, args.tamanho)
    data = buscar(url, payload)

    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {})

    if not hits:
        print(f"[SEM RESULTADOS] Nenhum processo encontrado em TJ{estado} com orgaoJulgador.nome contendo todos os termos de: {termo!r}")
        return

    vistos: dict[int, dict] = {}
    for hit in hits:
        orgao = (hit.get("_source") or {}).get("orgaoJulgador") or {}
        codigo = orgao.get("codigo")
        if codigo is None or codigo in vistos:
            continue
        vistos[codigo] = orgao

    print(f"\n[INFO] TJ{estado} | {len(hits)} processo(s) amostrado(s) de um total estimado de {total.get('value', '?')}.")
    print(f"[INFO] {len(vistos)} orgao(s) julgador(es) distinto(s) encontrado(s):\n")

    for codigo in sorted(vistos):
        orgao = vistos[codigo]
        print(f"  codigo={codigo:<8} municipio_ibge={orgao.get('codigoMunicipioIBGE')!s:<10} nome={orgao.get('nome')}")

    if len(vistos) > 1:
        print("\n[DICA] Mais de um orgao encontrado - refine o termo (ex: inclua a comarca) se precisar de um so.")


if __name__ == "__main__":
    main()
