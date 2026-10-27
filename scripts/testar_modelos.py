from pathlib import Path
import os
ROOT = Path(__file__).resolve().parent.parent
TABELAS = ROOT / 'outputs_json' / 'tabelas'
RELATORIOS = ROOT / 'outputs_json' / 'relatorios'
MODELOS = ROOT / 'outputs_json' / 'modelos'

"""
TESTE DOS MODELOS EM NOVOS PROCESSOS

O QUE FAZ:
  1. Carrega os dois modelos treinados (movimento + tempo)
  2. Pega um processo novo do CSV de teste
  3. Para cada posição do processo, faz a previsão
  4. Compara com o que realmente aconteceu
  5. Mostra acurácia da previsão

COMO USAR:
  python3 testar_modelos.py
"""

import pandas as pd
import numpy as np
from catboost import CatBoostClassifier, CatBoostRegressor

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

print("[1] Carregando modelos treinados...")
modelo_mov = CatBoostClassifier()
modelo_mov.load_model(str(MODELOS / "modelo_movimento.cbm"))

modelo_tempo = CatBoostRegressor()
modelo_tempo.load_model(str(MODELOS / "modelo_tempo.cbm"))
print("    ✓ Modelos carregados")

print("\n[2] Carregando dados de teste...")
df = pd.read_csv(TABELAS / "tabela_posicao_tempo_processos.csv")
print(f"    Total de eventos: {len(df)}")

# Pega os 20% de teste (mesmos que foram usados no treino)
np.random.seed(42)
processos_unicos = df["num_processo"].unique()
np.random.shuffle(processos_unicos)
split_idx = int(len(processos_unicos) * 0.8)
teste_proc = set(processos_unicos[split_idx:])

df_teste = df[df["num_processo"].isin(teste_proc)].copy()
print(f"    Eventos de teste: {len(df_teste)}")

# ============================================================================
# TESTAR EM ALGUNS PROCESSOS ESPECÍFICOS
# ============================================================================
print("\n[3] Selecionando processos de teste...")
processos_exemplo = list(teste_proc)[:3]  # Primeiros 3 processos de teste

features = ["posicao", "movimento_atual", "orgao_julgador", "assunto", "classe"]

for proc_num in processos_exemplo:
    print("\n" + "="*80)
    print(f"PROCESSO: {proc_num}")
    print("="*80)
    
    df_proc = df_teste[df_teste["num_processo"] == proc_num].sort_values("posicao")
    
    if len(df_proc) < 2:
        print("  (menos de 2 eventos, pulando)")
        continue
    
    acertos = 0
    total = 0
    erros_tempo = []
    
    # Para cada evento do processo (começando da posição 2)
    for i in range(1, len(df_proc)):
        linha = df_proc.iloc[i]
        posicao = linha["posicao"]
        movimento_real = linha["movimento_atual"]
        tempo_real = linha["dias_desde_anterior"]
        
        # Prepare features
        X_novo = pd.DataFrame([{
            "posicao": linha["posicao"],
            "movimento_atual": linha["movimento_atual"],
            "orgao_julgador": linha["orgao_julgador"],
            "assunto": linha["assunto"],
            "classe": linha["classe"],
        }])
        
        # Previsão
        pred_mov = modelo_mov.predict(X_novo)[0]
        pred_proba = modelo_mov.predict_proba(X_novo)[0]
        confianca = max(pred_proba) * 100
        
        pred_tempo = modelo_tempo.predict(X_novo)[0]
        
        # Resultado
        acertou_mov = (pred_mov == movimento_real)
        erro_tempo = abs(pred_tempo - tempo_real)
        
        if acertou_mov:
            acertos += 1
        total += 1
        erros_tempo.append(erro_tempo)
        
        simbolo = "✓" if acertou_mov else "✗"
        print(f"\n  Posição {int(posicao)} {simbolo}")
        print(f"    Movimento previsto: {pred_mov} ({confianca:.0f}% confiança)")
        print(f"    Movimento real:     {movimento_real}")
        print(f"    Tempo previsto:     {pred_tempo:.0f} dias")
        print(f"    Tempo real:         {tempo_real:.0f} dias (erro: {erro_tempo:.0f}d)")
    
    # Resumo do processo
    if total > 0:
        acuracia_proc = acertos / total * 100
        mae_proc = sum(erros_tempo) / len(erros_tempo)
        print(f"\n  RESUMO DO PROCESSO:")
        print(f"    Acurácia: {acuracia_proc:.0f}% ({acertos}/{total} acertos)")
        print(f"    MAE (tempo): {mae_proc:.1f} dias")

# ============================================================================
# TESTE GERAL EM TODOS OS TESTES
# ============================================================================
print("\n\n" + "="*80)
print("TESTE GERAL EM TODOS OS 20% DE TESTE")
print("="*80)

# Prepare X_test (posição >= 2)
df_eval = df_teste[df_teste["posicao"] > 1].copy()

X_eval = df_eval[features].copy()
y_mov_real = df_eval["movimento_atual"].copy()
y_tempo_real = df_eval["dias_desde_anterior"].copy()

# Previsões
y_mov_pred = modelo_mov.predict(X_eval)
y_tempo_pred = modelo_tempo.predict(X_eval)

# Métricas
acertos = (y_mov_pred == y_mov_real).sum()
total = len(y_mov_real)
acuracia = acertos / total * 100

mae_tempo = abs(y_tempo_real - y_tempo_pred).mean()
mediana_erro_tempo = abs(y_tempo_real - y_tempo_pred).median()

print(f"\nAcurácia geral (movimento): {acuracia:.2f}% ({acertos}/{total})")
print(f"MAE (tempo em dias): {mae_tempo:.1f} dias")
print(f"Mediana de erro (tempo): {mediana_erro_tempo:.1f} dias")

# ============================================================================
# FEATURE IMPORTANCE
# ============================================================================
print("\n" + "="*80)
print("IMPORTÂNCIA DAS FEATURES")
print("="*80)

feat_imp = modelo_mov.get_feature_importance()
for feat, imp in sorted(zip(features, feat_imp), key=lambda x: x[1], reverse=True):
    print(f"  {feat:<20s} {imp:6.2f}%")

print("\n✓ Teste concluído!")
