# api-cnj — Leitor de Árvore de Fluxo Processual

Projeto de análise de **movimentações processuais** (DataJud/CNJ) que reconstrói a
**árvore de fluxo** dos processos por assunto, com métricas de volume, prazos e
probabilidades de transição (Cadeia de Markov de 1ª ordem).

O **leitor de árvore de fluxo** (app web) está em **`webapp/`** — é o ponto de
entrada principal.

---

## 🚀 Rodar o leitor de árvore de fluxo (principal)

```powershell
pip install -r requirements.txt
py webapp/app.py
```

Abre em **http://localhost:5000**.

| Rota | O que faz |
|---|---|
| `GET /` | Frontend (`index.html`) com a rede vis-network |
| `GET /api/assuntos` | Ranking de assuntos (nº de processos) |
| `GET /api/arvore?assunto=<nome>&min_n=<n>&max_depth=<n>` | Nós/arestas + `P(v\|u)` de Markov |
| `POST /api/recarregar` | Limpa o cache e relê os JSONs |

O cache fica em `webapp/.cache/dados.pkl` (reconstruído automaticamente).

---

## 📁 Estrutura do projeto

```
api-cnj/
├── webapp/                    ⭐ PRINCIPAL — leitor de árvore de fluxo
│   ├── app.py                 Backend Flask (API JSON + serve o front)
│   ├── index.html             Frontend (Tailwind + vis-network)
│   └── .cache/                Cache em disco (dados.pkl)
│
├── visualizacoes/             Motor de árvore + análises estáticas
│   ├── arvore_fluxo_top3.py   CLI: gera árvores dos assuntos mais comuns
│   ├── arvore_fluxo_multas.py Motor gráfico (trie + grafo + Markov)
│   ├── arvore_fluxo_debito_fiscal.py
│   ├── teia_camadas_tempo.py  Visualização em camadas (teia)
│   ├── analise_rotas.py       Extração de sequências por assunto
│   ├── gera_relatorio.py      Relatório HTML/PDF
│   ├── diagnostico.py         Diagnóstico estrutural da árvore
│   ├── medir_escala.py        Métricas de escala
│   ├── rotas_por_assunto.json Dados agregados
│   ├── relatorio_arvores.html
│   └── imagens/               PNG/SVG/CSV gerados
│
├── scripts/                   Scripts de análise e ML (execução pontual)
│   ├── assuntot.py            Consolida os 3 assuntos-alvo
│   ├── processar_transicoes.py Gera tabela posição→movimento→tempo
│   ├── contar_assuntos.py     Ranking de assuntos
│   ├── analise_tempo_movi.py  Tempo entre transições
│   ├── analise_multas.py      Árvore do fluxo inicial (multas)
│   ├── nome_do_arquivo.py     Trilhas completas dominantes
│   ├── cont_frequencia.py     PDF de frequência por assunto
│   ├── gerar_arvore_graphviz.py  Árvore .dot (Graphviz)
│   ├── gerar_fluxograma_mermaid.py Fluxograma Mermaid/HTML
│   └── testar_modelos.py      Testa modelos CatBoost
│
├── outputs_json/              DADOS (gerado — fora do git)
│   ├── 04 FAZENDA PUBLICA DE CENTRAL/          ⛔ PROTEGIDO
│   ├── 08 FAZENDA PUBLICA DE CENTRAL/          ⛔ PROTEGIDO
│   ├── 13 FAZENDA PUBLICA DE CENTRAL/          ⛔ PROTEGIDO
│   ├── SETOR DE EXECUCOES FAZENDA PUBLICA DE CENTRAL/  ⛔ PROTEGIDO
│   ├── tabelas/               CSVs derivados (tabela_posicao_tempo_processos.csv)
│   ├── relatorios/            .txt/.md de análise
│   ├── modelos/               Modelos CatBoost (.cbm)
│   └── imagens/
│
├── resultados/                Saídas consolidadas por assunto
│   ├── multas/                matrizes, funis, rotas mais frequentes
│   └── debito_fiscal/
│
├── logs/                      Logs de execução (stdout/stderr)
│   ├── visualizacoes/
│   └── webapp/
│
├── docs/                      Documentos e exemplos
├── config.yaml                Configuração do coletor DataJud
└── requirements.txt
```

---

## 🔒 Pastas protegidas — não apagar

As pastas abaixo, dentro de `outputs_json/`, contêm os **JSONs brutos de processo**
alimentam o motor (`arvore_fluxo_top3.py`) e o backend (`webapp/app.py`):

- `04 FAZENDA PUBLICA DE CENTRAL/`
- `08 FAZENDA PUBLICA DE CENTRAL/`
- `13 FAZENDA PUBLICA DE CENTRAL/`
- `SETOR DE EXECUCOES FAZENDA PUBLICA DE CENTRAL/`

Jamais devem ser apagadas, movidas ou sobrescritas. Os caches
(`webapp/.cache/`, `visualizacoes/.cache_arvore/`) **podem** ser apagados —
são reconstruídos automaticamente.

---

## 🔁 Pipeline de dados

```
outputs_json/<órgão>/<ano>/*.json     (JSONs brutos do DataJud)
        │
        ├─► scripts/assuntot.py         → outputs_json/tabelas/processos_top3_consolidados.csv
        │        └─► scripts/processar_transicoes.py → outputs_json/tabelas/tabela_posicao_tempo_processos.csv
        │
        ├─► webapp/app.py                → lê os JSONs direto (árvore por assunto, Markov)
        │
        └─► visualizacoes/arvore_fluxo_top3.py → imagens/ (PNG+SVG+CSV)
```

O `webapp` **não** depende do pipeline de CSV — lê os JSONs diretamente.

---

## 📊 Métricas do modelo de Markov

Cada aresta carrega `P(v|u) = peso(u→v) / processos(u)` e cada nó:

- `prob_entrada` — chance de chegar ao nó
- `p_saida` — chance de o processo **continuar** adiante
- `p_parada` — chance de **encerrar** ali (= `1 − p_saida`)

---

## ⚙️ Dependências

```
requests>=2.31    # coletor DataJud
flask>=3.0        # backend do leitor de árvore
```

Extras (opcionais, para scripts de análise/ML): `matplotlib`, `networkx`,
`pandas`, `numpy`, `catboost`, `reportlab`, `scikit-learn`.

---

## 📌 Observações

- `config.yaml` ainda referencia caminhos da máquina original
  (`C:/Users/marli/Downloads/...`) — ajuste `entrada`/`saida` para coletar dados.
- A chave da API DataJud é lida da variável de ambiente `DATAJUD_API_KEY`.
- Documentação da API: https://datajud-wiki.cnj.jus.br/api-publica/
