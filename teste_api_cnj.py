"""
Coleta de processos do TJSP na API Pública do DataJud (CNJ).

Busca processos de um ORGAO JULGADOR especifico (pelo codigo numerico)
ajuizados em um ANO especifico, e salva um .json por processo em:

    outputs_json/<orgao_julgador>/<ano>/<numero_processo>.json

IMPORTANTE - limitacoes da API publica do DataJud:
A API so devolve METADADOS do processo (classe, assuntos, orgao julgador,
datas) e a lista de MOVIMENTOS (codigo + nome padronizado + complementos
tabelados). Ela NAO devolve partes, nome do juiz, foro por extenso,
situacao do processo, valor da causa nem o teor integral de despachos e
decisoes. Por isso o JSON gerado e mais enxuto do que
json_processo_exemplo.json (que parece vir de raspagem do e-SAJ), mas
segue a mesma logica de organizacao: dados do processo + movimentacoes
agrupadas por data.

Documentacao: https://datajud-wiki.cnj.jus.br/api-publica/
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Carrega as variaveis do arquivo .env (se existir) para o ambiente
load_dotenv()

# ===============================
# CONFIG (variaveis de ambiente)
# ===============================
# A chave da API NAO fica hardcoded aqui: vem de DATAJUD_API_KEY no .env
# (ou nas variaveis de ambiente do sistema).
API_KEY = os.getenv("DATAJUD_API_KEY")
TRIBUNAL_ALIAS = os.getenv("DATAJUD_TRIBUNAL_ALIAS", "api_publica_tjsp")  # TJSP - Tribunal de Justica de Sao Paulo
BASE_URL = os.getenv(
    "DATAJUD_BASE_URL",
    f"https://api-publica.datajud.cnj.jus.br/{TRIBUNAL_ALIAS}/_search",
)

if not API_KEY:
    print("[ERRO] Variavel DATAJUD_API_KEY nao definida.")
    print("       Copie .env.example para .env e preencha com sua chave, ou")
    print("       exporte a variavel no ambiente do sistema.")
    sys.exit(1)

OUTPUT_DIR = Path("outputs_json")
CHECKPOINT_DIR = Path("checkpoints")
ERROS_LOG = "erros.log"

PAGE_SIZE = 100          # tamanho de cada pagina (search_after)
TIMEOUT_REQ = 60
MAX_RETRIES = 6
SLEEP_ENTRE_PAGINAS = 0.3  # pequena cortesia entre requisicoes


# ===============================
# LOG
# ===============================
def log_erro(msg: str):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROS_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {msg}\n")


# ===============================
# CHECKPOINT (para retomar coleta longa)
# ===============================
def checkpoint_path(codigo_orgao: int, ano: int) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"orgao_{codigo_orgao}_ano_{ano}.json"

def carregar_checkpoint(codigo_orgao: int, ano: int) -> dict | None:
    p = checkpoint_path(codigo_orgao, ano)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_checkpoint(codigo_orgao: int, ano: int, payload: dict):
    with open(checkpoint_path(codigo_orgao, ano), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ===============================
# QUERY / FETCH (DataJud - Elasticsearch)
# ===============================
def montar_query(codigo_orgao: int, ano: int, search_after: list | None = None) -> dict:
    body = {
        "size": PAGE_SIZE,
        "query": {
            "bool": {
                "must": [
                    {"match": {"orgaoJulgador.codigo": codigo_orgao}},
                    {
                        "range": {
                            "dataAjuizamento": {
                                "gte": f"{ano}-01-01T00:00:00.000Z",
                                "lt": f"{ano + 1}-01-01T00:00:00.000Z",
                            }
                        }
                    },
                ]
            }
        },
        # @timestamp garante ordenacao estavel; numeroProcesso.keyword desempata
        # (numeroProcesso e um campo "text" - Elasticsearch nao permite sort
        # direto nele, exige o subcampo .keyword)
        "sort": [
            {"@timestamp": {"order": "asc"}},
            {"numeroProcesso.keyword": {"order": "asc"}},
        ],
    }
    if search_after:
        body["search_after"] = search_after
    return body


def buscar_pagina(payload: dict) -> dict:
    headers = {
        "Authorization": f"ApiKey {API_KEY}",
        "Content-Type": "application/json",
    }

    ultimo_erro = None
    for tentativa in range(MAX_RETRIES):
        try:
            resp = requests.post(BASE_URL, headers=headers, data=json.dumps(payload), timeout=TIMEOUT_REQ)
        except requests.RequestException as e:
            ultimo_erro = e
            espera = 2 ** tentativa
            print(f"[REDE] erro={e!r} tentativa={tentativa+1}/{MAX_RETRIES} aguardando {espera}s...")
            time.sleep(espera)
            continue

        if resp.status_code == 429 or resp.status_code >= 500:
            espera = 2 ** tentativa
            print(f"[HTTP {resp.status_code}] tentativa={tentativa+1}/{MAX_RETRIES} aguardando {espera}s...")
            time.sleep(espera)
            continue

        resp.raise_for_status()
        data = resp.json()

        # a API pode responder HTTP 200 mesmo com parte dos shards falhando
        # (cluster sobrecarregado) - nesse caso a pagina vem incompleta e
        # NAO pode ser tratada como se fosse o fim dos resultados.
        shards = data.get("_shards", {})
        if shards.get("failed", 0) > 0:
            espera = 2 ** tentativa
            print(f"[SHARDS] {shards.get('failed')}/{shards.get('total')} shards falharam "
                  f"tentativa={tentativa+1}/{MAX_RETRIES} aguardando {espera}s...")
            time.sleep(espera)
            continue

        return data

    raise RuntimeError(f"Excedeu tentativas ({MAX_RETRIES}) ao consultar a API. Ultimo erro: {ultimo_erro!r}")


# ===============================
# TRANSFORMACAO: _source (DataJud) -> JSON de saida
# ===============================
def formatar_numero_processo(numero: str) -> str:
    """NNNNNNN-DD.AAAA.J.TR.OOOO (mascara padrao CNJ), se tiver 20 digitos."""
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) != 20:
        return numero
    return f"{digitos[0:7]}-{digitos[7:9]}.{digitos[9:13]}.{digitos[13:14]}.{digitos[14:16]}.{digitos[16:20]}"


def formatar_data_hora(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(iso_str, fmt)
        except ValueError:
            continue
    return None


def montar_complemento(mov: dict) -> str:
    partes = []
    for c in mov.get("complementosTabelados") or []:
        descricao = c.get("descricao")
        nome = c.get("nome")
        if descricao and nome:
            partes.append(f"{descricao}: {nome}")
        elif nome:
            partes.append(nome)
    return "; ".join(partes)


def transformar_processo(source: dict) -> dict:
    classe = source.get("classe") or {}
    orgao = source.get("orgaoJulgador") or {}
    sistema = source.get("sistema") or {}
    formato = source.get("formato") or {}
    assuntos = source.get("assuntos") or []

    movimentos = sorted(
        source.get("movimentos") or [],
        key=lambda m: m.get("dataHora") or "",
        reverse=True,  # mais recente primeiro, igual ao exemplo
    )

    movimentacoes: dict[str, list] = {}
    for mov in movimentos:
        dt = formatar_data_hora(mov.get("dataHora"))
        chave = dt.strftime("%d/%m/%Y") if dt else "data_desconhecida"
        movimentacoes.setdefault(chave, []).append([
            mov.get("nome"),
            montar_complemento(mov),
        ])

    return {
        "dados": {
            "id_datajud": source.get("id"),
            "num_processo": formatar_numero_processo(source.get("numeroProcesso")),
            "num_processo_sem_formatacao": source.get("numeroProcesso"),
            "tribunal": source.get("tribunal"),
            "grau": source.get("grau"),
            "classe": classe.get("nome"),
            "codigo_classe": classe.get("codigo"),
            "assunto": assuntos[0].get("nome") if assuntos else None,
            "outros_assuntos": [a.get("nome") for a in assuntos[1:]],
            "orgao_julgador": orgao.get("nome"),
            "codigo_orgao_julgador": orgao.get("codigo"),
            "codigo_municipio_ibge": orgao.get("codigoMunicipioIBGE"),
            "sistema": sistema.get("nome"),
            "formato": formato.get("nome"),
            "data_ajuizamento": source.get("dataAjuizamento"),
            "data_hora_ultima_atualizacao": source.get("dataHoraUltimaAtualizacao"),
            "nivel_sigilo": source.get("nivelSigilo"),
        },
        "movimentacoes": movimentacoes,
    }


# ===============================
# SALVAR JSON (ATOMICO)
# ===============================
def sanitizar_nome_pasta(nome: str) -> str:
    nome = (nome or "orgao_desconhecido").strip()
    nome = re.sub(r'[\\/:*?"<>|]+', "_", nome)
    nome = re.sub(r"\s+", " ", nome)
    return nome[:150] or "orgao_desconhecido"


def salvar_json_atomic(out_path: Path, dados: dict):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    tmp_path.replace(out_path)


# campos de "dados" que sao metadados/controle e podem mudar (ou passar a
# existir, por causa de uma mudanca no proprio script) sem que o processo em
# si seja outro - nao contam para dizer se dois registros sao "diferentes"
CAMPOS_IGNORADOS_NA_COMPARACAO = {"id_datajud", "data_hora_ultima_atualizacao"}


def comparar_processos(existente: dict, novo: dict) -> str:
    """Compara o conteudo de um processo ja salvo com um recem-baixado.
    Retorna 'identico' ou uma descricao de quais blocos diferem."""
    dados_e = {k: v for k, v in (existente.get("dados") or {}).items() if k not in CAMPOS_IGNORADOS_NA_COMPARACAO}
    dados_n = {k: v for k, v in (novo.get("dados") or {}).items() if k not in CAMPOS_IGNORADOS_NA_COMPARACAO}
    mov_e = existente.get("movimentacoes")
    mov_n = novo.get("movimentacoes")

    if dados_e == dados_n and mov_e == mov_n:
        return "identico"
    diffs = []
    if dados_e != dados_n:
        diffs.append("dados")
    if mov_e != mov_n:
        diffs.append("movimentacoes")
    return "diferente:" + ",".join(diffs)


def resolver_caminho_duplicado(out_path: Path, processo: dict) -> Path:
    """out_path ja existe em disco. Se o conteudo salvo for identico ao novo,
    retorna o mesmo out_path (sobrescreve sem problema, e um no-op). Se for
    diferente - ex: mesmo numeroProcesso mas grau/classe/orgao distintos,
    tipico de recurso ou redistribuicao - retorna um caminho alternativo
    para NAO perder nenhum dos dois registros."""
    with open(out_path, "r", encoding="utf-8") as f:
        existente = json.load(f)

    resultado = comparar_processos(existente, processo)
    if resultado == "identico":
        print(f"[DUPLICADO-IGUAL] {out_path.name} -> conteudo identico ja salvo, mantido")
        return out_path

    grau = processo["dados"].get("grau") or "semgrau"
    novo_path = out_path.with_name(f"{out_path.stem}__{grau}{out_path.suffix}")
    if novo_path.exists():
        with open(novo_path, "r", encoding="utf-8") as f:
            existente2 = json.load(f)
        if comparar_processos(existente2, processo) == "identico":
            print(f"[DUPLICADO-IGUAL] {novo_path.name} -> conteudo identico ja salvo, mantido")
            return novo_path
        contador = 2
        while novo_path.exists():
            novo_path = out_path.with_name(f"{out_path.stem}__{grau}_{contador}{out_path.suffix}")
            contador += 1

    msg = f"DIVERGENTE numeroProcesso={out_path.stem} motivo={resultado} salvo_como={novo_path.name}"
    print(f"[DIVERGENTE] {out_path.name}: {resultado} -> salvando separado como {novo_path.name}")
    log_erro(msg)
    return novo_path


# ===============================
# COLETA PRINCIPAL
# ===============================
def coletar(codigo_orgao: int, ano: int):
    ck = carregar_checkpoint(codigo_orgao, ano)
    search_after = ck.get("search_after") if ck else None

    # so faz sentido herdar o contador do checkpoint se tambem temos de onde
    # retomar (search_after); um checkpoint "done"/antigo sem search_after
    # significa que a busca vai recomecar do zero, entao o contador tambem deve
    total_baixados = ck.get("total_baixados", 0) if (ck and search_after) else 0

    if ck and search_after:
        print(f"[RETOMANDO] orgao={codigo_orgao} ano={ano} ja baixados={total_baixados}")
    elif ck:
        print(f"[REINICIANDO] orgao={codigo_orgao} ano={ano} (checkpoint anterior sem ponto de retomada, comecando do zero)")

    pasta_orgao = None  # descoberta a partir do primeiro resultado

    while True:
        payload = montar_query(codigo_orgao, ano, search_after)
        data = buscar_pagina(payload)

        hits_info = data.get("hits", {})
        hits = hits_info.get("hits", [])
        total_geral = hits_info.get("total", {}).get("value", "?")

        if not hits:
            break

        for hit in hits:
            source = hit.get("_source", {})
            numero_raw = source.get("numeroProcesso") or hit.get("_id") or "sem_numero"

            try:
                if pasta_orgao is None:
                    orgao_nome = (source.get("orgaoJulgador") or {}).get("nome") or f"orgao_{codigo_orgao}"
                    pasta_orgao = sanitizar_nome_pasta(orgao_nome)

                processo = transformar_processo(source)
                numero_fmt = processo["dados"]["num_processo"]

                out_path = OUTPUT_DIR / pasta_orgao / str(ano) / f"{numero_fmt}.json"
                if out_path.exists():
                    out_path = resolver_caminho_duplicado(out_path, processo)

                salvar_json_atomic(out_path, processo)

                total_baixados += 1
                print(f"[OK] ({total_baixados}/{total_geral}) {numero_fmt} -> {out_path}")

            except Exception as e:
                msg = f"ERRO ao processar/salvar numeroProcesso={numero_raw} erro={repr(e)}"
                print(f"[ERRO] {msg}")
                log_erro(msg)

            # sort do ultimo hit processado vira o proximo search_after
            search_after = hit.get("sort")

        salvar_checkpoint(codigo_orgao, ano, {
            "status": "in_progress",
            "codigo_orgao": codigo_orgao,
            "ano": ano,
            "search_after": search_after,
            "total_baixados": total_baixados,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })

        if len(hits) < PAGE_SIZE:
            break

        time.sleep(SLEEP_ENTRE_PAGINAS)

    salvar_checkpoint(codigo_orgao, ano, {
        "status": "done",
        "codigo_orgao": codigo_orgao,
        "ano": ano,
        "total_baixados": total_baixados,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })
    print(f"[DONE] orgao={codigo_orgao} ano={ano} total_baixados={total_baixados}")


# ===============================
# MAIN
# ===============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coleta processos do TJSP na API publica do DataJud por orgao julgador + ano.")
    parser.add_argument("--codigo-orgao", type=int, required=True, help="Codigo numerico do orgao julgador (orgaoJulgador.codigo).")
    parser.add_argument("--ano", type=int, required=True, help="Ano de ajuizamento dos processos a coletar.")
    args = parser.parse_args()

    coletar(args.codigo_orgao, args.ano)
