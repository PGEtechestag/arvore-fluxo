# Visualizações — Rotas de Movimentação por Assunto

Análise das sequências reais de movimentações processuais (ponta a ponta) a partir de
`outputs_json/tabela_posicao_tempo_processos.csv`, com foco em três assuntos:

| Assunto | Processos | Média posições | Mediana |
|---|---|---|---|
| Anulação de Débito Fiscal | 261 | 22,9 | 20 |
| Multas e demais Sanções | 404 | 14,1 | 11 |
| Valor da Execução / Cálculo / Atualização | 284 | 12,0 | 10 |

## Arquivos gerados

- `imagens/arvore_*.png` e `.svg` — árvore de fluxo real de cada assunto
  (1ª a 4ª movimentação com percentuais por nó/aresta + desfechos tracejados).
- `relatorio_arvores.html` — relatório acadêmico completo (abrir no navegador).
- `relatorio_arvores.pdf` — versão PDF do relatório (4 páginas A4).
- `rotas_por_assunto.json` — dados agregados (funil por posição, transições,
  caminhos completos, desfechos).
- `analise_rotas.py` — extração de sequências e estatísticas.
- `gera_arvores.py` — monta e exporta as árvores (PNG/SVG).
- `gera_relatorio.py` — monta `relatorio_arvores.html` e `relatorio_arvores.pdf`.
- `diagnostico.py` — diagnóstico estrutural da árvore (níveis, nós, arestas, cobertura).

## Reproduzir

```powershell
cd visualizacoes
py analise_rotas.py          # regera rotas_por_assunto.json
py gera_arvores.py           # regera imagens/imagens (PNG+SVG)
py gera_relatorio.py         # regera HTML + PDF
```

Dependências: `pandas/matplotlib` (opcionais para análise) e `reportlab` (PDF).
As árvores usam apenas `matplotlib` + biblioteca padrão.

## Regra de leitura da árvore

- Cada caixa = um **movimento** observado em uma **posição**; o número e o percentual
  são a fração do total de processos do assunto que passaram por aquele caminho.
- Arestas contínuas = transições consecutivas realmente observadas (largura ∝ frequência).
- Tracejado = ligação da 4ª posição aos **desfechos** mais comuns.
- As ramificações exibidas cobrem ~85% do ingresso (1ª posição); variações raras
  foram omitidas para legibilidade.