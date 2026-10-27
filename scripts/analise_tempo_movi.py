from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

from collections import defaultdict
import numpy as np
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

print("[1] Carregando dados...")
df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")


def assunto_bate(assunto):
  assunto_lower = assunto.strip().lower()
  for alvo in ASSUNTOS_ALVO:
    if alvo.lower() in assunto_lower:
      return alvo
  return None


df["assunto_alvo"] = df["assunto"].apply(assunto_bate)
df_filtrado = df[df["assunto_alvo"].notna()].copy()
df_filtrado = df_filtrado.sort_values(["num_processo", "posicao"])

# Criar coluna do próximo movimento e do tempo até ele
df_filtrado["proximo_movimento"] = df_filtrado.groupby("num_processo")[
    "movimento_atual"
].shift(-1)
df_filtrado["tempo_ate_proximo"] = df_filtrado.groupby("num_processo")[
    "dias_desde_anterior"
].shift(-1)

# Filtrar apenas linhas válidas de transição com tempo conhecido
df_trans = df_filtrado.dropna(
    subset=["proximo_movimento", "tempo_ate_proximo"]
).copy()

# ============================================================================
# ANÁLISE DE TEMPO POR TRANSIÇÃO (Par: Movimento Atual -> Próximo Movimento)
# ============================================================================
print(
    "\n[2] Calculando estatísticas de tempo (Dias) entre os principais"
    " movimentos..."
)

with open(RELATORIOS / "analise_tempo_transicoes.txt", "w",
          encoding="utf-8") as f:
  f.write(
      "ANÁLISE DE DISTRIBUIÇÃO DE TEMPO ENTRE MOVIMENTOS (DIAS CORRIDOS)\n"
  )
  f.write("=" * 80 + "\n\n")

  for assunto in ASSUNTOS_ALVO:
    f.write(f"\n{'='*80}\n")
    f.write(f"ASSUNTO: {assunto.upper()}\n")
    f.write(f"{'='*80}\n\n")

    df_assunto = df_trans[df_trans["assunto_alvo"] == assunto]

    # Agrupar por par de transição (De -> Para)
    transicoes_tempo = defaultdict(list)
    for _, row in df_assunto.iterrows():
      par = (row["movimento_atual"], row["proximo_movimento"])
      dias = float(row["tempo_ate_proximo"])
      transicoes_tempo[par].append(dias)

    # Ordenar transições mais frequentes
    f.write(
        f"{'Movimento de Origem':<30} -> {'Próximo Movimento':<30} | {'Qtde':<5} |"
        f" {'Média (dias)':<12} | {'Mediana (dias)':<14} | {'Max':<5}\n"
    )
    f.write("-" * 105 + "\n")

    # Filtrar pares que aconteceram pelo menos 10 vezes para ter relevância estatística
    pares_relevantes = [
        (par, tempos)
        for par, tempos in transicoes_tempo.items()
        if len(tempos) >= 10
    ]
    # Ordenar por quantidade de ocorrências
    pares_relevantes.sort(key=lambda x: len(x[1]), reverse=True)

    for par, tempos in pares_relevantes[:15]:  # Top 15 transições mais comuns
      origem, destino = par
      qtd = len(tempos)
      media = np.mean(tempos)
      mediana = np.median(tempos)
      maximo = np.max(tempos)

      origem_trunc = origem[:28] if len(origem) > 28 else origem
      destino_trunc = destino[:28] if len(destino) > 28 else destino

      f.write(
          f"{origem_trunc:<30} -> {destino_trunc:<30} | {qtd:<5} |"
          f" {media:12.1f} | {mediana:14.1f} | {maximo:<5.0f}\n"
      )

    f.write("\n")

print("✓ Salvo com sucesso: analise_tempo_transicoes.txt")
print("\n" + "=" * 80)
print("✓ ANÁLISE DE TEMPO CONCLUÍDA!")
print("=" * 80)
print(
    "\n💡 Abra o arquivo 'analise_tempo_transicoes.txt' para ver quanto tempo"
    " cada transição demora em média!"
)
