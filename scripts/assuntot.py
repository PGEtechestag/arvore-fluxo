import json
from pathlib import Path
import pandas as pd
import os

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'


# Ajuste para o caminho real da sua pasta principal onde estão as varas
pasta_raiz = Path(__file__).resolve().parent.parent / "outputs_json"

ASSUNTOS_ALVO = [
    "Anulação de Débito Fiscal",
    "Multas e demais Sanções",
    "Valor da Execução / Cálculo / Atualização",
]

dados_consolidados = []
assuntos_encontrados_geral = set()

print("Varredura iniciada...")

for arquivo_json in pasta_raiz.rglob("*.json"):
  try:
    with open(arquivo_json, "r", encoding="utf-8") as f:
      conteudo = json.load(f)
      dados_proc = conteudo.get("dados", {})
      assunto = dados_proc.get("assunto")

      if assunto:
        assuntos_encontrados_geral.add(assunto)

      # Verificação flexível (ignora maiúsculas/minúsculas e espaços extras)
      if assunto and any(
          alvo.strip().lower() in assunto.strip().lower()
          for alvo in ASSUNTOS_ALVO
      ):
        orgao_julgador = dados_proc.get("orgao_julgador", "Desconhecido")
        num_processo = dados_proc.get("num_processo")
        classe = dados_proc.get("classe")
        data_ajuizamento = dados_proc.get("data_ajuizamento")
        movimentacoes = conteudo.get("movimentacoes", {})

        dados_consolidados.append({
            "num_processo": num_processo,
            "orgao_julgador": orgao_julgador,
            "assunto": assunto,
            "classe": classe,
            "data_ajuizamento": data_ajuizamento,
            "movimentacoes": movimentacoes,
        })
  except Exception as e:
    print(f"Erro no arquivo {arquivo_json}: {e}")

print(f"\n--- DIAGNÓSTICO ---")
print(
    "Assuntos únicos encontrados em todos os JSONs lidos:",
    assuntos_encontrados_geral,
)
print(f"Total de processos salvos após o filtro: {len(dados_consolidados)}")

df_processos = pd.DataFrame(dados_consolidados)


# Converte a lista consolidada em DataFrame
df_processos = pd.DataFrame(dados_consolidados)

# Salva em um arquivo CSV limpo na sua pasta de trabalho
df_processos.to_csv(TABELAS / "processos_top3_consolidados.csv",
                       index=False, encoding="utf-8-sig")

print(f"Base salva com sucesso! Total de registros: {len(df_processos)}")

# Mostra as primeiras 5 linhas completas
print(df_processos.head())

# Mostra as colunas que você tem disponíveis
print("\nColunas da sua base:")
print(df_processos.columns.tolist())
# Conta quantos processos existem para cada um dos 3 assuntos
contagem_assuntos = df_processos['assunto'].value_counts()
print("\nContagem por assunto:")
print(contagem_assuntos)
# Conta quantos processos temos por órgão julgador
contagem_varas = df_processos['orgao_julgador'].value_counts()
print("\nContagem por órgão julgador:")
print(contagem_varas)
# Escolha o índice de um processo (ex: o primeiro, índice 0)
processo_exemplo = df_processos.iloc[0]

print(f"\nDetalhes do processo {processo_exemplo['num_processo']}:")
print(f"Assunto: {processo_exemplo['assunto']}")
print(f"Movimentações (primeiras 5 entradas):")

# O campo 'movimentacoes' é um dicionário, vamos ver uma prévia
movs = processo_exemplo['movimentacoes']
# Exibe as chaves (datas) e o primeiro movimento de cada
for data, detalhes in list(movs.items())[:5]:
    print(f"{data}: {detalhes[0][0]}")
