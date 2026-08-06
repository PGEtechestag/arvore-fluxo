# api-cnj

Coleta de processos do **TJSP** na **API Pública do DataJud (CNJ)**.

O script busca os processos de um **órgão julgador específico** (pelo código
numérico) ajuizados em um **ano específico** e salva **um `.json` por processo** em:

```
outputs_json/<orgao_julgador>/<ano>/<numero_processo>.json
```

## ⚠️ Limitações da API pública do DataJud

A API só devolve **metadados** do processo (classe, assuntos, órgão julgador,
datas) e a lista de **movimentos** (código + nome padronizado + complementos
tabelados). Ela **não devolve** partes, nome do juiz, foro por extenso,
situação do processo, valor da causa nem o teor integral de despachos e
decisões.

Por isso o JSON gerado é mais enxuto do que um JSON vindo de raspagem do
e-SAJ, mas segue a mesma lógica de organização: **dados do processo +
movimentações agrupadas por data**.

- Documentação oficial: https://datajud-wiki.cnj.jus.br/api-publica/

## Pré-requisitos

- Python 3.10+
- Conta/chave de acesso à API pública do DataJud (CNJ)

## Instalação

```bash
# 1) Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 2) Instale as dependências
pip install -r requirements.txt

# 3) Configure as variáveis de ambiente
cp .env.example .env
# edite o .env e preencha DATAJUD_API_KEY com sua chave real
```

> **Nota:** o script lê `DATAJUD_API_KEY`, `DATAJUD_TRIBUNAL_ALIAS` e
> `DATAJUD_BASE_URL` do arquivo `.env` (via `python-dotenv`) ou das variáveis
> de ambiente do sistema. A chave **não** está hardcoded no código. Se a chave
> não for encontrada, o script aborta com uma mensagem orientando a configurar
> o `.env`.

## Uso

```bash
python teste_api_cnj.py --codigo-orgao <codigo> --ano <ano>
```

Exemplo:

```bash
python teste_api_cnj.py --codigo-orgao 7009 --ano 2023
```

| Argumento           | Tipo | Obrigatório | Descrição                                        |
|---------------------|------|-------------|--------------------------------------------------|
| `--codigo-orgao`    | int  | ✅          | Código numérico do órgão julgador (`orgaoJulgador.codigo`) |
| `--ano`             | int  | ✅          | Ano de ajuizamento dos processos a coletar        |

## Como funciona

1. Monta a query (Elasticsearch) filtrando por `orgaoJulgador.codigo` e o
   intervalo de `dataAjuizamento` do ano informado, paginada com `search_after`
   (100 registros por página).
2. Consulta a API (`POST .../_search`) com autenticação via `ApiKey`,
   com **retry** em caso de erro de rede, `HTTP 429/5xx` ou shards falhos
   (retirada exponencial).
3. Transforma o `_source` em um JSON enxuto (formata número do processo na
   máscara CNJ, datas e complementos de movimentos).
4. Salva cada processo em `outputs_json/<orgao>/<ano>/<numero>.json` de forma
   **atômica** (arquivo `.tmp` + `replace`).
5. Mantém um **checkpoint** em `checkpoints/orgao_<codigo>_ano_<ano>.json`,
   permitindo retomar a coleta longa de onde parou.
6. Trata casos de **processo duplicado** (mesmo número, grau/classe/órgão
   diferentes — típico de recurso/redistribuição) salvando em arquivo
   separado e registrando em `erros.log`.

## Estrutura de saída

```
outputs_json/
└── <orgao_julgador>/
    └── <ano>/
        └── NNNNNNN-DD.AAAA.T.J.OOOO.json   # um JSON por processo

checkpoints/
└── orgao_<codigo>_ano_<ano>.json            # ponto de retomada

erros.log                                    # erros de processamento/salvamento
```

Cada arquivo de processo contém (de forma resumida):

- `dados` — metadados do processo (classe, assuntos, órgão julgador, datas,
  grau, formato, sistema, numeração CNJ, etc.)
- `movimentacoes` — movimentos agrupados por data

## Arquivos do projeto

| Arquivo             | Finalidade                                        |
|---------------------|---------------------------------------------------|
| `teste_api_cnj.py`  | Script principal de coleta                         |
| `requirements.txt`  | Dependências Python (`requests`)                   |
| `.env.example`      | Modelo de configuração (chave da API) para commit  |
| `.env`              | Configuração real (não versionado, vide `.gitignore`) |
| `.gitignore`        | Arquivos ignorados pelo Git                        |
| `README.md`         | Este arquivo                                       |

## Licença / Observações

Uso sujeito aos termos e limites de utilização da API pública do CNJ. Respeite
a política de uso e os limites de requisição do serviço.