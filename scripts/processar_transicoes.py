from datetime import datetime
from pathlib import Path
import pandas as pd
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'


# 1. Carregar a base consolidada criada no passo anterior
caminho_base = TABELAS / "processos_top3_consolidados.csv"
if not Path(caminho_base).exists():
  raise FileNotFoundError(
      "O arquivo consolidado não foi encontrado. Execute o passo anterior"
      " primeiro."
  )

df_processos = pd.read_csv(caminho_base)

# As movimentações foram salvas como string JSON ou dicionário, vamos garantir a leitura
import ast

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

linhas_transicao = []

print("Processando sequências de movimentos e colapsando eventos do mesmo dia...")

for _, row in df_processos.iterrows():
  num_proc = row["num_processo"]
  assunto = row["assunto"]
  orgao = row["orgao_julgador"]
  classe = row["classe"]

  # Carrega o dicionário de movimentações
  movs_raw = row["movimentacoes"]
  if isinstance(movs_raw, str):
    try:
      movs_dict = ast.literal_eval(movs_raw)
    except:
      continue
  else:
    movs_dict = movs_raw

  if not isinstance(movs_dict, dict) or not movs_dict:
    continue

  # 2. Organizar e ordenar cronologicamente por data (DD/MM/YYYY)
  movimentos_por_data = []
  for data_str, lista_eventos in movs_dict.items():
    try:
      # Converte a data para objeto datetime para ordenação correta
      data_dt = datetime.strptime(data_str, "%d/%m/%Y")

      # Extrai os nomes dos movimentos ocorridos nessa data
      nomes_movimentos = [evento[0] for evento in lista_eventos]

      movimentos_por_data.append({"data": data_dt, "movimentos": nomes_movimentos})
    except ValueError:
      # Ignora formatos de data inválidos se houver
      continue

  # Ordena do mais antigo para o mais recente
  movimentos_por_data = sorted(movimentos_por_data, key=lambda x: x["data"])

  # 3. Colapsar eventos-satélite do mesmo dia em um único bloco consolidado
  historico_limpo = []
  for item in movimentos_por_data:
    # Remove duplicatas no mesmo dia e une em uma string descritiva ou pega o principal
    movs_unicos = list(dict.fromkeys(item["movimentos"]))
    movimento_composto = " + ".join(movs_unicos)  # Ex: "Remessa + Publicação"

    historico_limpo.append({"data": item["data"], "movimento": movimento_composto})

  # 4. Gerar a tabela de Posição -> Movimento -> Tempo (Delta em dias)
  for i in range(len(historico_limpo)):
    atual = historico_limpo[i]

    if i == 0:
      dias_decorridos = 0  # Marco zero / primeiro evento
    else:
      anterior = historico_limpo[i - 1]
      delta = (atual["data"] - anterior["data"]).days
      dias_decorridos = max(
          0, delta
      )  # Garante que não haja dias negativos por inversão

    linhas_transicao.append({
        "num_processo": num_proc,
        "orgao_julgador": orgao,
        "assunto": assunto,
        "classe": classe,
        "posicao": i + 1,
        "movimento_atual": atual["movimento"],
        "data_movimento": atual["data"].strftime("%Y-%m-%d"),
        "dias_desde_anterior": dias_decorridos,
    })

# 5. Criar o DataFrame final da tabela de transições
df_transicoes = pd.DataFrame(linhas_transicao)

# Salvar a nova tabela pronta para o modelo
df_transicoes.to_csv(
    TABELAS / "tabela_posicao_tempo_processos.csv", index=False,
    encoding="utf-8-sig"
)

print("\nProcessamento concluído com sucesso!")
print(f"Total de linhas de transição geradas: {len(df_transicoes)}")
print("\nPrévia da tabela de transições:")
print(df_transicoes.head(10))
