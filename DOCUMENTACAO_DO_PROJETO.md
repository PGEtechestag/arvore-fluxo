# Documentação do projeto — Coleta DataJud

## 1. Ideia do projeto

Este projeto foi criado para transformar uma pasta de arquivos JSON recebidos do sistema judicial em uma coleta estruturada de processos públicos disponíveis na **API Pública do DataJud/CNJ**.

O ponto de partida foram os JSONs locais das varas de Fazenda Pública. Eles são usados como referência para descobrir, na base do DataJud, qual é o código do órgão julgador correspondente. A partir desse código, o programa consulta todos os processos públicos daquele órgão em cada ano solicitado e grava um JSON por processo.

Em resumo, o fluxo é:

```text
JSONs locais de referência
        ↓
identificação de um processo consultável
        ↓
descobrimento do código do órgão no DataJud
        ↓
consulta paginada por ano de ajuizamento
        ↓
JSONs organizados por vara e ano + checkpoint de retomada
```

Essa estratégia foi adotada porque o nome de uma vara, por si só, não é uma chave segura de consulta na API. O código de `orgaoJulgador` retornado pelo próprio DataJud é a referência mais confiável para buscar todos os processos vinculados à unidade.

## 2. De onde saímos

O projeto recebeu arquivos JSON em pastas de entrada, como `4ª Vara de Fazenda Pública` e, posteriormente, em `Entradas`, com referências de outras unidades. Esses arquivos não são modificados pelo programa.

Havia três necessidades principais:

1. localizar a unidade correta no DataJud a partir dos dados já disponíveis;
2. baixar os processos públicos por ano sem depender de uma consulta manual processo a processo;
3. permitir a retomada segura se a conexão ou a API falhassem no meio da coleta.

## 3. O que foi construído

Foi implementado um programa Python com uma arquitetura simples, separada por responsabilidade:

| Componente | Responsabilidade |
| --- | --- |
| `run.py` | Ponto de entrada na linha de comando; lê argumentos e inicia a coleta. |
| `config.yaml` | Define tribunal, anos, caminhos e parâmetros da API. |
| `src/datajud_pipeline/config.py` | Carrega e valida a configuração. |
| `src/datajud_pipeline/api/client.py` | Faz chamadas à API com autenticação, tempo limite e novas tentativas. |
| `src/datajud_pipeline/api/discovery.py` | Descobre código e nome do órgão julgador a partir de um processo conhecido. |
| `src/datajud_pipeline/api/collector.py` | Busca as páginas de processos, prepara os dados e grava os arquivos. |
| `src/datajud_pipeline/state.py` | Mantém o checkpoint local da execução. |
| `src/datajud_pipeline/pipeline.py` | Coordena descoberta, coleta, erros e relatório final. |
| `tests/` | Testes automatizados das regras mais importantes. |

Também foram incluídos `start.bat`, para facilitar a execução no Windows, e `pipeline.log`, para registrar detalhes técnicos de cada rodada.

## 4. Passo a passo do funcionamento

### Passo 1 — Receber e preservar os dados de entrada

O programa recebe uma pasta com JSONs de uma vara, ou uma pasta superior que contenha várias varas. Ele apenas lê esses arquivos; não os renomeia, altera ou remove.

Isso preserva a origem da informação e permite repetir a coleta sem perder a referência inicial.

### Passo 2 — Encontrar uma referência válida

O programa lê os números de processo dos JSONs locais e prioriza os mais recentes. Para cada número, remove a formatação e realiza uma consulta pontual na API do DataJud.

Nem todo processo presente na entrada está necessariamente disponível na base pública. Por isso, se uma referência não for encontrada, o programa continua tentando os próximos JSONs, em vez de encerrar a execução.

Essa foi uma correção importante após a primeira referência examinada não retornar resultado no DataJud. A ausência de um processo na API não significa que a vara não exista; significa apenas que aquela referência não está indexada ou exposta na consulta pública.

### Passo 3 — Descobrir o código do órgão julgador

Quando uma referência é localizada, a resposta da API informa:

- `orgaoJulgador.codigo`: identificador usado na coleta;
- `orgaoJulgador.nome`: nome retornado pelo DataJud.

O código é salvo no checkpoint e reutilizado nas próximas etapas. Isso evita repetir a descoberta desnecessariamente e reduz chamadas à API.

### Passo 4 — Consultar processos por ano

Para cada ano solicitado, a consulta filtra simultaneamente:

- o código do órgão julgador;
- a data de ajuizamento entre 1º de janeiro e 31 de dezembro do ano.

A API é consultada em páginas de até 100 processos. A paginação usa `search_after`, que é mais adequada do que avançar por páginas numeradas em conjuntos grandes e diminui o risco de repetir ou pular registros durante a coleta.

### Passo 5 — Preparar e gravar cada resultado

Cada processo retornado é salvo em:

```text
OUTPUTS/<nome da vara>/<ano>/<numero do processo>.json
```

O arquivo contém duas seções:

- `dados`: metadados públicos do processo devolvidos pela API;
- `movimentacoes`: movimentações agrupadas pela data, facilitando leitura e análises posteriores.

Os arquivos são gravados de forma atômica: primeiro em um arquivo temporário e depois no nome final. Se já existir um arquivo com o mesmo número, mas conteúdo diferente, o programa cria um sufixo (`_2`, `_3` etc.), evitando sobrescrita de dados.

### Passo 6 — Registrar o andamento para retomada

Após cada página salva, o programa atualiza `OUTPUTS/.pipeline_checkpoint.json` com o último marcador de paginação e o status da coleta.

Se houver interrupção de rede, fechamento do terminal ou erro temporário da API, uma nova execução pode continuar do ponto registrado, sem rebaixar o que já foi processado. Ao terminar um ano, o status passa a `concluido`.

### Passo 7 — Tratar instabilidades da API

As chamadas à API têm tempo limite e até cinco tentativas. Para erros transitórios — como limite de requisições ou falhas 5xx — a espera entre as tentativas aumenta progressivamente.

Se uma coleta falhar, a ocorrência é registrada no checkpoint e o pipeline faz uma nova tentativa ao final da rodada. Falhas que permanecerem exigem apenas uma nova execução quando o acesso à API estiver disponível.

## 5. Decisões e por que foram tomadas

| Decisão | Motivo |
| --- | --- |
| Usar JSONs locais apenas como referência | Preserva os arquivos originais e aproveita os números de processo já disponíveis. |
| Descobrir o órgão pelo DataJud | Evita depender de nomes que podem variar entre sistemas. |
| Filtrar por código do órgão e ano | Torna a coleta objetiva e reproduzível. |
| Paginar com `search_after` | Dá mais estabilidade à navegação por grandes resultados. |
| Manter um checkpoint em JSON | Permite retomar o trabalho sem necessidade de banco de dados. |
| Escrita atômica e sem sobrescrita | Protege contra arquivos incompletos e perda de versões diferentes. |
| Separar cliente, descoberta, coleta e estado | Facilita manutenção, teste e mudança de uma parte sem afetar as outras. |
| Incluir testes automatizados | Confirma regras críticas, como normalização do CNJ, formato dos dados e persistência do checkpoint. |

## 6. Situação observada nos arquivos atuais

O checkpoint existente registra coletas concluídas para:

| Unidade | Ano(s) concluído(s) | Código DataJud |
| --- | --- | --- |
| 4ª Vara de Fazenda Pública | 2023, 2024, 2025 e 2026 | `10555` |
| 8ª Vara de Fazenda Pública | 2023 | `10559` |
| UPEFAZ | 2023, 2024, 2025 e 2026 | `11647` |

No diretório `OUTPUTS`, há atualmente 319 arquivos para a 4ª Vara em 2023, 623 em 2024 e 81 em 2025; há também 400 arquivos da 8ª Vara em 2023. O ano marcado como concluído pode ter zero resultados quando a API não retorna processos para o filtro, o que é um resultado válido.

O mesmo checkpoint também registra falhas pendentes de conexão para a 13ª Vara e para anos ainda não concluídos da 8ª Vara. O erro gravado é de bloqueio de criação de conexão (`WinError 10013`), portanto não indica erro nos arquivos nem na regra de coleta. Com acesso à API restabelecido, basta executar novamente os anos desejados.

> Observação: o `README.md` descreve uma execução anterior e não representa integralmente o checkpoint e os diretórios atuais. Esta documentação usa o estado atualmente encontrado no projeto.

## 7. Como executar

No PowerShell, dentro da pasta do projeto:

```powershell
python -m pip install -r requirements.txt
python run.py --anos 2023 2024 2025 2026
```

Ou, no Windows:

```powershell
start.bat --anos 2023 2024 2025 2026
```

Para escolher explicitamente a entrada e a saída:

```powershell
python run.py --entrada "C:\Dados\Minha Vara" --saida "C:\Dados\Resultados" --anos 2025 2026
```

`--anos`, `--entrada` e `--saida` substituem os valores correspondentes de `config.yaml` apenas naquela execução.

## 8. Configuração e segurança

A configuração está em `config.yaml`. A chave da API pode ser fornecida por `DATAJUD_API_KEY`; se ela estiver definida no ambiente, tem prioridade sobre o valor configurado no arquivo.

Para reduzir exposição indevida, recomenda-se manter a chave fora de repositórios e compartilhamentos públicos e configurá-la no ambiente antes de executar:

```powershell
$env:DATAJUD_API_KEY = "sua_chave"
python run.py --anos 2026
```

Não apague `OUTPUTS/.pipeline_checkpoint.json` se desejar preservar a capacidade de retomada. Para refazer deliberadamente um ano, remova a pasta de saída daquele ano e a entrada correspondente no checkpoint, somente depois de confirmar que a coleta deverá ser refeita.

## 9. Como verificar o projeto

Os testes automatizados podem ser executados com:

```powershell
python -m pytest -q
```

Eles cobrem a normalização do número CNJ na descoberta, a transformação das movimentações, a persistência do checkpoint e a resolução de caminhos do comando de execução.

## 10. Limites da solução

O projeto coleta somente o que a API Pública do DataJud expõe. Ele não obtém conteúdo integral de decisões, documentos sigilosos, partes protegidas ou informações que não estejam publicadas pelo CNJ. Além disso, a completude dos resultados depende da indexação e da disponibilidade momentânea da API.