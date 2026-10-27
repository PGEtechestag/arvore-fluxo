from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

"""
GERADOR DE DIAGRAMA EM ÁRVORE (FLUXO INICIAL ATÉ A 1ª CONCLUSÃO)
Assunto: Multas e demais Sanções
Gera um fluxograma visual em formato de árvore usando NetworkX e Matplotlib.
"""
from collections import Counter
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# 1. Carrega os dados com caminho absoluto
df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")

# 2. Filtra o assunto
assunto_alvo = "Multas e demais Sanções"
df_assunto = df[
    df["assunto"].astype(str).str.lower().str.contains(assunto_alvo.lower())
].copy()
df_assunto = df_assunto.dropna(subset=["movimento_atual"])
df_assunto["movimento_atual"] = (
    df_assunto["movimento_atual"].astype(str).str.strip()
)

# 3. Extrai as transições exatas do início até a 1ª conclusão
transicoes = []
for proc_id, grupo in df_assunto.groupby("num_processo"):
  grupo = grupo.sort_values("posicao")
  movimentos = grupo["movimento_atual"].tolist()

  caminho_ate_conclusao = []
  for mov in movimentos:
    caminho_ate_conclusao.append(mov)
    if "conclusão" in mov.lower():
      break

  # Se tiver pelo menos 2 passos ou mais até a conclusão, mapeia a transição Passo A -> Passo B
  for i in range(len(caminho_ate_conclusao) - 1):
    origem = caminho_ate_conclusao[i]
    destino = caminho_ate_conclusao[i + 1]
    transicoes.append((origem, destino))

# 4. Conta os pares mais frequentes para estruturar a árvore
contador_arestas = Counter(transicoes)
top_arestas = contador_arestas.most_common(12)  # Pega as principais conexões

# 5. Constrói o grafo em árvore
G = nx.DiGraph()
for (origem, destino), peso in top_arestas:
  G.add_edge(origem, destino, weight=peso)

# Configuração da visualização em árvore
plt.figure(figsize=(14, 8))
pos = nx.spring_layout(G, k=0.8, seed=42)

nx.draw_networkx_nodes(
    G, pos, node_size=3000, node_color="#ebf8ff", edgecolors="#2b6cb0", linewidths=2
)
nx.draw_networkx_edges(
    G,
    pos,
    edgelist=G.edges(),
    width=2,
    edge_color="#4a5568",
    arrowstyle="->",
    arrowsize=20,
)

# Formata os nomes dos nós para caberem melhor
labels = {node: node[:35] + ("..." if len(node) > 35 else "") for node in G.nodes()}
nx.draw_networkx_labels(
    G, pos, labels, font_size=8, font_family="sans-serif", font_weight="bold"
)

plt.title(
    f"Árvore de Fluxo Inicial (Início até a 1ª Conclusão)\n{assunto_alvo}",
    fontsize=12,
    fontweight="bold",
    pad=20,
)
plt.axis("off")
plt.tight_layout()

# Salva a imagem da árvore
plt.savefig(
    r"C:\Users\Íris\Desktop\api-cnj - Copia\outputs_json\arvore_fluxo_inicial_multas.png",
    dpi=300,
)
print(
    "[Sucesso] A árvore visual foi gerada e salva como"
    " 'arvore_fluxo_inicial_multas.png' na pasta outputs_json!"
)
