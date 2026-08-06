# api-cnj

Conjunto de utilitários em Python para trabalhar com a **API Pública do
DataJud (CNJ)** — o repositório de dados processuais do Poder Judiciário.
Foco atual na **Justiça Estadual** (Tribunais de Justiça / TJSP etc.).

O projeto é composto por três scripts:

1. **`teste_api_cnj.py`** — coleta em massa de processos de um **órgão julgador**
   ajuizados em um **ano** específico, salvando um `.json` por processo.
2. **`buscar_orgao_julgador.py`** — ajudante para **descobrir o código numérico**
   de um órgão julgador (vara/câmara) a partir de um termo de busca.
3. **`teste_conexao_datajud.py`** — teste mínimo de conectividade com a API
   (verifica se o endpoint responde e salva a resposta em `resposta_teste.json`).

Documentação oficial da API: https://datajud-wiki.cnj.jus.br/api-publica/

---

## ⚠️ Limitações da API pública do DataJud

A API devolve apenas **metadados** do processo (classe, assuntos, órgão
julgador, datas) e a lista de **movimentos** (código + nome padronizado +
complementos tabelados). Ela **não devolve** partes, nome do juiz, foro por
extenso, situação do processo, valor da causa nem o teor integral de despachos
e decisões.

Por isso o JSON gerado é mais enxuto do que um JSON vindo de raspagem do
e-SAJ, mas segue a mesma lógica de organização: **dados do processo +
movimentações agrupadas por data**.

---

## Pré-requisitos

- Python 3.10+
- Chave de acesso à API pública do DataJud (CNJ)

> **Importante:** atualmente a chave `API_KEY` está **hardcoded** nos três
> scripts (padrão `ApiKey <chave>` no header `Authorization`). Não há `.env`
> nem leitura de variáveis de ambiente — se quiser trocar a credencial, edite
> a constante `API_KEY` nos arquivos.

## Instalação

```bash
# 1) Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 2) Instale as dependências
pip install -r requirements.txt
```

Dependências: `requests>=2.31` (única dependência de runtime).

## Uso

### 1) Teste de conexão (sanidade)

```bash
python teste_conexao_datajud.py
```

Faz **uma única requisição** (sem retry) em
`api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search` buscando um processo
de exemplo e grava a resposta crua em `resposta_teste.json`. Útil para saber,
de forma rápida, se a rede/credencial estão ok antes de rodar coletas longas.

### 2) Descobrir o código do órgão julgador

```bash
# Modo interativo (pergunta o termo e a UF)
python buscar_orgao_julgador.py

# Modo direto por linha de comando
python buscar_orgao_julgador.py --termo "Vara de Fazenda Publica" --estado SP --tamanho 50
```

Como a API não tem endpoint dedicado para listar órgãos julgadores nem
agregações, o script faz uma **busca por texto** no campo `orgaoJulgador.nome`
e extrai, dos processos retornados, os pares únicos
`(codigo, nome, codigoMunicipioIBGE)` encontrados. Funciona para os 27
Tribunais de Justiça estaduais (há um mapeamento `UF -> alias do endpoint`).

> A lista não é exaustiva. Se aparecer mais de um resultado parecido, refine o
> termo (ex.: inclua o nome da comarca) ou aumente `--tamanho`.

| Argumento    | Tipo | Obrigatório | Descrição                                              |
|--------------|------|-------------|--------------------------------------------------------|
| `--termo`    | str  | opcional    | Texto a buscar no nome do órgão (se omitido, pergunta) |
| `--estado`   | str  | opcional    | UF do tribunal (ex.: SP, RJ, MG; se omitido, pergunta) |
| `--tamanho`  | int  | opcional    | Qtd. de processos a amostrar (default: 50)             |

### 3) Coletar processos de um órgão + ano

```bash
python teste_api_cnj.py --codigo-orgao <codigo> --ano <ano>
```

Exemplo:

```bash
python teste_api_cnj.py --codigo-orgao 7009 --ano 2023
```

| Argumento           | Tipo | Obrigatório | Descrição                                                        |
|---------------------|------|-------------|------------------------------------------------------------------|
| `--codigo-orgao`    | int  | ✅           | Código numérico do órgão julgador (`orgaoJulgador.codigo`)       |
| `--ano`             | int  | ✅           | Ano de ajuizamento dos processos a coletar                       |

---

## Como funciona a coleta (`teste_api_cnj.py`)

1. Monta a query (Elasticsearch) filtrando por `orgaoJulgador.codigo` e pelo
   intervalo de `dataAjuizamento` do ano informado, **paginada com
   `search_after`** (100 registros por página).
2. Consulta a API (`POST .../_search`) com autenticação via `ApiKey`, com
   **retry exponencial** em erro de rede, `HTTP 429/5xx` ou shards falhos.
3. Transforma o `_source` em um JSON enxuto (formata o número do processo na
   máscara CNJ, datas e complementos dos movimentos).
4. Salva cada processo em `outputs_json/<orgao>/<ano>/<numero>.json` de forma
   **atômica** (arquivo `.tmp` + `replace`).
5. Mantém um **checkpoint** em `checkpoints/orgao_<codigo>_ano_<ano>.json`,
   permitindo retomar a coleta longa de onde parou.
6. Trata casos de **processo duplicado** (mesmo número, mas grau/classe/órgão
   diferentes — típico de recurso/redistribuição), salvando em arquivo
   separado e registrando em `erros.log`.

Como a ordenação usa `@timestamp` + `numeroProcesso.keyword` (o campo
`numeroProcesso` é do tipo `text` no Elasticsearch e não aceita `sort`
direto), o `search_after` aponta para o último `hit` processado, garantindo
estabilidade na paginação.

---

## Estrutura de saída

```
outputs_json/
└── <orgao_julgador>/
    └── <ano>/
        └── NNNNNNN-DD.AAAA.T.J.OOOO.json   # um JSON por processo

checkpoints/
└── orgao_<codigo>_ano_<ano>.json            # ponto de retomada

erros.log                                    # erros de processamento/salvamento
resposta_teste.json                          # resposta crua do teste de conexão
```

Cada arquivo de processo contém (de forma resumida):

- `dados` — metadados do processo (classe, assuntos, órgão julgador, datas,
  grau, formato, sistema, numeração CNJ, etc.)
- `movimentacoes` — movimentos agrupados por data

---

## Arquivos do projeto

| Arquivo                          | Finalidade                                              |
|----------------------------------|---------------------------------------------------------|
| `teste_api_cnj.py`              | Coleta em massa de processos por órgão + ano            |
| `buscar_orgao_julgador.py`      | Descobre o código do órgão julgador por busca de nome   |
| `teste_conexao_datajud.py`      | Teste mínimo de conectividade com a API                 |
| `requirements.txt`              | Dependências Python (`requests>=2.31`)                  |
| `.gitignore`                    | Arquivos ignorados pelo Git                             |
| `README.md`                     | Este arquivo                                            |

---

## Licença / Observações

Uso sujeito aos termos e limites de utilização da API pública do CNJ. Respeite
a política de uso e os limites de requisição do serviço.