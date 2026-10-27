from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

"""
ÁRVORE COM CORTE DE 3% E LIMITE DE 5 NÍVEIS PARA LEGIBILIDADE
"""

from collections import Counter, defaultdict
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

df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")


def assunto_bate(assunto):
  assunto_lower = assunto.strip().lower()
  for alvo in ASSUNTOS_ALVO:
    if alvo.lower() in assunto_lower:
      return alvo
  return None


df["assunto_alvo"] = df["assunto"].apply(assunto_bate)

for assunto_idx, assunto in enumerate(ASSUNTOS_ALVO, 1):
  print(f"\n[{assunto_idx}] Gerando árvore visual: {assunto}")

  df_assunto = df[df["assunto_alvo"] == assunto].copy()
  df_assunto = df_assunto.sort_values(["num_processo", "posicao"])

  if len(df_assunto) < 10:
    continue

  n_procs = df_assunto["num_processo"].nunique()
  
  # Trava de segurança gráfica (5 níveis no máximo para não estourar a tela)
  max_prof = 5

  # Mapear transições
  transicoes = defaultdict(Counter)
  for proc_id, grupo in df_assunto.groupby("num_processo"):
    grupo = grupo.sort_values("posicao")
    movimentos = grupo["movimento_atual"].tolist()
    for i in range(len(movimentos) - 1):
      transicoes[movimentos[i]][movimentos[i + 1]] += 1

  dot_lines = []
  dot_lines.append("digraph {")
  dot_lines.append("    rankdir=LR;")
  dot_lines.append("    splines=true;")
  dot_lines.append("    nodesep=0.3;")
  dot_lines.append("    ranksep=1.0;")
  dot_lines.append(
      '    node [shape=box, style="rounded,filled", fontname="Arial",'
      ' fillcolor="#e7f5ff", color="#1c7ed6", margin="0.15,0.1"];'
  )
  dot_lines.append('    edge [fontname="Arial", fontsize=8, color="#868e96"];')
  dot_lines.append("")

  dot_lines.append(
      f'    RAIZ [label="{assunto}\\n({n_procs} processos)", fillcolor="#3b5bdb",'
      ' fontcolor=white, fontsize=11];'
  )
  dot_lines.append("")

  freq_inicial = df_assunto["movimento_atual"].value_counts()
  top_iniciais = freq_inicial.head(4)
  node_counter = [0]


  def adicionar_ramo(mov_anterior, parent_node_id, profundidade):
    if profundidade > max_prof:
      return
    if mov_anterior not in transicoes or not transicoes[mov_anterior]:
      return

    total_origem = sum(transicoes[mov_anterior].values())
    proximos = transicoes[mov_anterior].most_common(3) # Top 3 opções

    for mov_proximo, count in proximos:
      if pd.isna(mov_proximo):
        continue
      mov_proximo_str = str(mov_proximo)
      prob = (count / total_origem) * 100

      # CORTE SOLICITADO: Ignora caminhos abaixo de 3%
      if prob < 3:  
        continue

      node_counter[0] += 1
      node_id = f"n{node_counter[0]}"
      mov_display = (
          mov_proximo_str[:22] + "..."
          if len(mov_proximo_str) > 22
          else mov_proximo_str
      )

      if prob > 70:
        cor = "#2b8a3e"
      elif prob > 40:
        cor = "#1864ab"
      elif prob > 20:
        cor = "#f59f00"
      else:
        cor = "#c92a2a"

      dot_lines.append(
          f'    {node_id} [label="Pos {profundidade}\\n{mov_display}\\n{prob:.1f}%'
          f' ({count}x)", fillcolor="{cor}", fontcolor=white];'
      )
      dot_lines.append(
          f'    {parent_node_id} -> {node_id} [label="{prob:.1f}%"];'
      )

      adicionar_ramo(mov_proximo_str, node_id, profundidade + 1)


  pos1_nodes = []
  for rank, (mov, freq) in enumerate(top_iniciais.items(), 1):
    if pd.isna(mov):
      continue
    mov_str = str(mov)
    prob = (freq / len(df_assunto)) * 100
    
    if prob < 3:
      continue

    node_counter[0] += 1
    node_id = f"p1_n{rank}"
    mov_display = mov_str[:22] + "..." if len(mov_str) > 22 else mov_str

    dot_lines.append(
        f'    {node_id} [label="Pos 1\\n{mov_display}\\n{prob:.1f}%'
        f' ({freq}x)", fillcolor="#1864ab", fontcolor=white];'
    )
    dot_lines.append(f'    RAIZ -> {node_id} [label="{prob:.1f}%", penwidth=2];')
    pos1_nodes.append((node_id, mov_str))

  dot_lines.append("")
  for node_id_pos1, mov_pos1 in pos1_nodes:
    adicionar_ramo(mov_pos1, node_id_pos1, profundidade=2)

  dot_lines.append("}")

  filename_base = f"arvore_3_porcento_{assunto_idx}"
  dot_path = f"{filename_base}.dot"

  with open(dot_path, "w", encoding="utf-8") as f:
    f.write("\n".join(dot_lines))

  print(f"    ✓ Arquivo DOT gerado com sucesso: {dot_path}")

print("\nConcluído! Abra os arquivos .dot no GraphvizOnline.")
