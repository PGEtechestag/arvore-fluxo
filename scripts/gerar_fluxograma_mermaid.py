from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

"""
MINERAÇÃO DE PROCESSOS - FLUXOGRAMA COM TODAS AS ROTAS

Gera um Mermaid.js mostrando:
  - TODOS os nós (não só o caminho principal)
  - Bifurcações em cada posição (top 3-4 opções)
  - Frequência de cada rota
  - Porcentagem de probabilidade
  - Agrupado em macro-etapas
"""

import pandas as pd
import numpy as np
from collections import defaultdict, Counter

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

print("="*80)
print("MINERAÇÃO DE PROCESSOS - TODAS AS ROTAS")
print("="*80)

# ============================================================================
# 1. CARREGAR E FILTRAR
# ============================================================================

df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")
df_filtrado = df[df['assunto'].str.contains('Valor da Execução', case=False, na=False)].copy()
df_filtrado = df_filtrado.sort_values(['num_processo', 'posicao'])

print(f"\n[1] Dados filtrados:")
print(f"    Processos: {df_filtrado['num_processo'].nunique()}")
print(f"    Eventos: {len(df_filtrado)}")

# ============================================================================
# 2. SIMPLIFICAR MOVIMENTOS
# ============================================================================

def simplificar_movimento(movimento):
    if pd.isna(movimento) or not isinstance(movimento, str):
        return "Outro"
    
    mov_lower = movimento.lower().strip()
    
    if "expedição" in mov_lower:
        if "conclusão" in mov_lower or "decisão" in mov_lower:
            return "Expedição+Decisão"
        return "Expedição"
    elif "publicação" in mov_lower:
        return "Publicação"
    elif "remessa" in mov_lower:
        return "Remessa"
    elif "petição" in mov_lower or "contestação" in mov_lower:
        return "Petição"
    elif "conclusão" in mov_lower:
        return "Conclusão"
    elif "ato ordinatório" in mov_lower:
        return "Ato Ordinatório"
    elif "execução" in mov_lower or "cumprimento" in mov_lower:
        return "Execução"
    elif "recebimento" in mov_lower:
        return "Recebimento"
    elif "extinção" in mov_lower or "trânsito" in mov_lower:
        return "Encerramento"
    else:
        return "Administrativo"

df_filtrado['mov_simp'] = df_filtrado['movimento_atual'].apply(simplificar_movimento)

# ============================================================================
# 3. EXTRAIR FREQUÊNCIA POR POSIÇÃO
# ============================================================================

print(f"\n[2] Analisando todas as rotas possíveis...")

# Dicionário: posicao -> {movimento -> frequencia}
frequencia_por_posicao = defaultdict(Counter)
tamanhos = []

for proc_id, grupo in df_filtrado.groupby('num_processo'):
    grupo = grupo.sort_values('posicao')
    movimentos = grupo['mov_simp'].tolist()
    tamanhos.append(len(movimentos))
    
    for posicao, movimento in enumerate(movimentos, 1):
        frequencia_por_posicao[posicao][movimento] += 1

max_posicoes = max(frequencia_por_posicao.keys()) if frequencia_por_posicao else 0
print(f"    Máximo de posições: {max_posicoes}")
print(f"    Média: {np.mean(tamanhos):.1f}")

# ============================================================================
# 4. CONTAR TRANSIÇÕES (para probabilidades)
# ============================================================================

print(f"\n[3] Calculando transições e probabilidades...")

# transicoes[movimento_anterior][movimento_proximo] = count
transicoes = defaultdict(Counter)

for proc_id, grupo in df_filtrado.groupby('num_processo'):
    grupo = grupo.sort_values('posicao')
    movimentos = grupo['mov_simp'].tolist()
    
    for i in range(len(movimentos) - 1):
        mov_atual = movimentos[i]
        mov_proximo = movimentos[i + 1]
        transicoes[mov_atual][mov_proximo] += 1

# ============================================================================
# 5. GERAR MERMAID COM TODAS AS ROTAS
# ============================================================================

print(f"\n[4] Gerando código Mermaid com todas as rotas...")

mermaid_code = "graph TD\n"
mermaid_code += '    Start(["<b>INÍCIO</b><br/>Execução<br/>Valor"])\n\n'

# Rastrear nós criados para evitar duplicatas
nos_criados = {}  # (posicao, movimento) -> id_unico

# Posição 1
print(f"\n    Posição 1 (Raiz):")
top_pos1 = frequencia_por_posicao[1].most_common(5)
ids_pos1 = []

for rank, (mov, freq) in enumerate(top_pos1, 1):
    total = sum(frequencia_por_posicao[1].values())
    pct = freq / total * 100
    
    node_id = f"P1_{rank}"
    nos_criados[(1, mov)] = node_id
    ids_pos1.append((node_id, mov))
    
    label = f"{mov}<br/>({pct:.0f}% - {freq}x)"
    mermaid_code += f'    {node_id}["{label}"]\n'
    mermaid_code += f'    Start --> {node_id}\n'
    
    print(f"      {rank}. {mov}: {pct:.1f}% ({freq}x)")

mermaid_code += "\n"

# Próximas posições
for posicao in range(2, min(max_posicoes + 1, 8)):  # Limitar a 8 posições
    print(f"\n    Posição {posicao}:")
    mermaid_code += f"    %% Posição {posicao}\n"
    
    # Para cada movimento da posição anterior, achar os possíveis próximos
    for node_id_anterior, mov_anterior in ids_pos1 if posicao == 2 else []:
        if mov_anterior not in transicoes:
            continue
        
        # Top 3 próximos movimentos
        proximos = transicoes[mov_anterior].most_common(3)
        
        for rank, (mov_proximo, count) in enumerate(proximos, 1):
            total_transicoes = sum(transicoes[mov_anterior].values())
            prob = count / total_transicoes * 100
            
            # Filtro: só mostrar > 10%
            if prob < 10:
                continue
            
            # ID único para este nó
            node_key = (posicao, mov_proximo, mov_anterior)
            node_id = f"P{posicao}_{rank}"
            
            label = f"{mov_proximo}<br/>({prob:.0f}% | {count}x)"
            mermaid_code += f'    {node_id}["{label}"]\n'
            mermaid_code += f'    {node_id_anterior} --> {node_id}\n'
            
            print(f"      De '{mov_anterior}' → {mov_proximo}: {prob:.1f}%")
    
    # Atualizar ids_pos1 para a próxima iteração (SIMPLIFICADO - só top 2)
    if posicao < max_posicoes:
        new_ids = []
        for rank, (mov, freq) in enumerate(frequencia_por_posicao[posicao].most_common(2), 1):
            node_id = f"P{posicao}_{rank}"
            new_ids.append((node_id, mov))
        ids_pos1 = new_ids

mermaid_code += '\n    %% Estilos\n'
mermaid_code += '    classDef inicio fill:#0ca30c,stroke:#333,stroke-width:3px,color:#fff,font-weight:bold\n'
mermaid_code += '    classDef processo fill:#3987e5,stroke:#333,stroke-width:2px,color:#fff\n'
mermaid_code += '    class Start inicio\n'

# ============================================================================
# 6. VERSÃO SIMPLIFICADA (Apenas caminho principal + alternativas top 2)
# ============================================================================

print(f"\n[5] Gerando versão simplificada (para tese)...")

mermaid_simple = "graph TD\n"
mermaid_simple += '    Start(["<b>INÍCIO</b><br/>Execução<br/>Valor da Execução"])\n\n'

# Posição 1
pos1_top = frequencia_por_posicao[1].most_common(2)
ids_pos1_simple = []

for rank, (mov, freq) in enumerate(pos1_top, 1):
    total = sum(frequencia_por_posicao[1].values())
    pct = freq / total * 100
    
    node_id = f"A{rank}"
    ids_pos1_simple.append((node_id, mov))
    
    label = f"{mov}<br/>({pct:.0f}%)"
    mermaid_simple += f'    {node_id}["{label}"]\n'
    mermaid_simple += f'    Start --> {node_id}\n'

mermaid_simple += "\n"

# Próximas posições (apenas top 2 de cada)
for posicao in range(2, min(max_posicoes + 1, 7)):
    mermaid_simple += f"    %% Posição {posicao}\n"
    
    new_ids = []
    for prev_id, prev_mov in ids_pos1_simple:
        if prev_mov not in transicoes:
            continue
        
        proximos = transicoes[prev_mov].most_common(2)
        
        for rank, (mov_proximo, count) in enumerate(proximos, 1):
            total_trans = sum(transicoes[prev_mov].values())
            prob = count / total_trans * 100
            
            node_id = f"{chr(65+posicao-2)}{prev_id[-1]}_{rank}"
            label = f"{mov_proximo}<br/>({prob:.0f}%)"
            
            mermaid_simple += f'    {node_id}["{label}"]\n'
            mermaid_simple += f'    {prev_id} --> {node_id}\n'
            
            new_ids.append((node_id, mov_proximo))
    
    mermaid_simple += "\n"
    ids_pos1_simple = new_ids[:4]  # Limitar para não explodir

mermaid_simple += '    classDef inicio fill:#0ca30c,stroke:#333,stroke-width:3px,color:#fff,font-weight:bold\n'
mermaid_simple += '    classDef processo fill:#3987e5,stroke:#333,stroke-width:2px,color:#fff\n'
mermaid_simple += '    class Start inicio\n'

# ============================================================================
# 7. SALVAR ARQUIVOS
# ============================================================================

# Versão detalhada
with open(RELATORIOS / "fluxograma_todas_rotas.md", "w",
          encoding="utf-8") as f:
    f.write("# Fluxograma Completo - Todas as Rotas\n\n")
    f.write("```mermaid\n")
    f.write(mermaid_code)
    f.write("```\n")

print(f"\n✓ Versão completa: fluxograma_todas_rotas.md")

# Versão simplificada (para tese)
with open(RELATORIOS / "fluxograma_valor_execucao_tese.md", "w",
          encoding="utf-8") as f:
    f.write("# Fluxograma Simplificado - Valor da Execução\n\n")
    f.write("Versão acadêmica com as principais rotas (top 2 por nível)\n\n")
    f.write("```mermaid\n")
    f.write(mermaid_simple)
    f.write("```\n\n")
    f.write("## Análise Estatística\n\n")
    f.write(f"- **Processos analisados:** {df_filtrado['num_processo'].nunique()}\n")
    f.write(f"- **Total de eventos:** {len(df_filtrado)}\n")
    f.write(f"- **Posição máxima:** {max_posicoes}\n")
    f.write(f"- **Posição média:** {np.mean(tamanhos):.1f}\n")

print(f"✓ Versão tese: fluxograma_valor_execucao_tese.md")

# HTML interativo
html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fluxograma - Todas as Rotas</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; border-bottom: 3px solid #0ca30c; padding-bottom: 20px; }}
        .tabs {{ display: flex; gap: 10px; margin: 20px 0; border-bottom: 2px solid #ddd; }}
        .tab-btn {{ padding: 10px 20px; border: none; background: #f0f0f0; cursor: pointer; border-radius: 5px 5px 0 0; font-weight: bold; }}
        .tab-btn.active {{ background: #3987e5; color: white; }}
        .tab-content {{ display: none; margin-top: 20px; }}
        .tab-content.active {{ display: block; }}
        .mermaid {{ background: #fafafa; padding: 20px; border-radius: 8px; overflow-x: auto; }}
        .info {{ background: #e3f2fd; padding: 15px; border-left: 4px solid #2196F3; margin: 20px 0; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Fluxograma de Processos - Valor da Execução</h1>
        
        <div class="info">
            <strong>Análise de Mineração de Processos</strong><br>
            Mostrando TODAS as rotas possíveis com frequências
        </div>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="mostrarTab('completo')">Completo (Todas as Rotas)</button>
            <button class="tab-btn" onclick="mostrarTab('tese')">Simplificado (Para Tese)</button>
        </div>
        
        <div id="completo" class="tab-content active">
            <h2>Fluxograma Completo</h2>
            <div class="mermaid">
{mermaid_code}
            </div>
        </div>
        
        <div id="tese" class="tab-content">
            <h2>Fluxograma Simplificado (Top 2 por Nível)</h2>
            <div class="mermaid">
{mermaid_simple}
            </div>
        </div>
    </div>
    
    <script>
        function mostrarTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
            mermaid.contentLoaderAsync();
        }}
        mermaid.contentLoaderAsync();
    </script>
</body>
</html>
"""

with open(RELATORIOS / "fluxograma_valor_execucao_interativo.html",
          "w", encoding="utf-8") as f:
    f.write(html)

print(f"✓ Versão HTML: fluxograma_valor_execucao_interativo.html")

print("\n" + "="*80)
print("✓ FLUXOGRAMAS GERADOS COM SUCESSO!")
print("="*80)
print("\nArquivos criados:")
print("  1. fluxograma_todas_rotas.md           (Todas as rotas - completo)")
print("  2. fluxograma_valor_execucao_tese.md   (Simplificado - para tese)")
print("  3. fluxograma_valor_execucao_interativo.html (Abra no navegador)")
print("\n💡 Use a versão 'tese' para sua dissertação")
