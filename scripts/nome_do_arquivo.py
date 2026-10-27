from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

"""
EXTRATOR DE SEQUÊNCIAS COMPLETAS DOMINANTES (TRILHAS PROCESSUAIS)
Agrupa o ciclo de vida completo do processo para mostrar os caminhos 
mais recorrentes de ponta a ponta na vara.
"""

from collections import Counter
import pandas as pd

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ASSUNTOS_ALVO = [
    "Anulação de Débito Fiscal",
    "Multas e demais Sanções",
    "Valor da Execução",
]

print("=" * 80)
print("EXTRAINDO AS TRILHAS PROCESSUAIS MAIS COMUNS (DE PONTA A PONTA)")
print("=" * 80)

df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")


def assunto_bate(assunto):
  assunto_lower = assunto.strip().lower()
  for alvo in ASSUNTOS_ALVO:
    if alvo.lower() in assunto_lower:
      return alvo
  return None


df["assunto_alvo"] = df["assunto"].apply(assunto_bate)

for assunto_idx, assunto in enumerate(ASSUNTOS_ALVO, 1):
  print(f"\n[{assunto_idx}] Assunto: {assunto}")

  df_assunto = df[df["assunto_alvo"] == assunto].copy()
  df_assunto = df_assunto.dropna(subset=["movimento_atual"])
  df_assunto = df_assunto[
      df_assunto["movimento_atual"].astype(str).str.strip() != ""
  ]

  if len(df_assunto) < 10:
    print("    Dados insuficientes.")
    continue

  # Agrupar cada processo em uma sequência ordenada de movimentos
  sequencias = []
  for proc_id, grupo in df_assunto.groupby("num_processo"):
    grupo = grupo.sort_values("posicao")
    # Transforma a lista de movimentos em uma tupla imutável para contagem
    seq_tuple = tuple(grupo["movimento_atual"].tolist())
    sequencias.append(seq_tuple)

  # Contar quais foram as trilhas completas mais repetidas na base
  contador_trilhas = Counter(sequencias)
  top_trilhas = contador_trilhas.most_common(5)  # Top 5 trilhas mais comuns

  print(f"    Total de processos analizados: {len(sequencias)}")
  print("    Principais Trilhas Completas Encontradas:")

  for rank, (trilha, freq) in enumerate(top_trilhas, 1):
    pct = (freq / len(sequencias)) * 100
    print(f"\n      Trilha #{rank} ({freq} processos | {pct:.1f}% da base):")
    for passo, mov in enumerate(trilha, 1):
      print(f"        [{passo}] {mov}")

print("\n" + "=" * 80)
print("✓ ANÁLISE DE TRILHAS CONCLUÍDA!")
print("=" * 80)
