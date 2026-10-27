# Fluxograma Simplificado - Valor da Execução

Versão acadêmica com as principais rotas (top 2 por nível)

```mermaid
graph TD
    Start(["<b>INÍCIO</b><br/>Execução<br/>Valor da Execução"])

    A1["Administrativo<br/>(50%)"]
    Start --> A1
    A2["Recebimento<br/>(21%)"]
    Start --> A2

    %% Posição 2
    A1_1["Expedição+Decisão<br/>(38%)"]
    A1 --> A1_1
    A1_2["Remessa<br/>(28%)"]
    A1 --> A1_2
    A2_1["Expedição+Decisão<br/>(33%)"]
    A2 --> A2_1
    A2_2["Conclusão<br/>(30%)"]
    A2 --> A2_2

    %% Posição 3
    B1_1["Remessa<br/>(70%)"]
    A1_1 --> B1_1
    B1_2["Expedição<br/>(17%)"]
    A1_1 --> B1_2
    B2_1["Publicação<br/>(93%)"]
    A1_2 --> B2_1
    B2_2["Expedição<br/>(4%)"]
    A1_2 --> B2_2
    B1_1["Remessa<br/>(70%)"]
    A2_1 --> B1_1
    B1_2["Expedição<br/>(17%)"]
    A2_1 --> B1_2
    B2_1["Expedição<br/>(55%)"]
    A2_2 --> B2_1
    B2_2["Remessa<br/>(16%)"]
    A2_2 --> B2_2

    %% Posição 4
    C1_1["Publicação<br/>(93%)"]
    B1_1 --> C1_1
    C1_2["Expedição<br/>(4%)"]
    B1_1 --> C1_2
    C2_1["Remessa<br/>(24%)"]
    B1_2 --> C2_1
    C2_2["Ato Ordinatório<br/>(19%)"]
    B1_2 --> C2_2
    C1_1["Expedição<br/>(58%)"]
    B2_1 --> C1_1
    C1_2["Petição<br/>(25%)"]
    B2_1 --> C1_2
    C2_1["Remessa<br/>(24%)"]
    B2_2 --> C2_1
    C2_2["Ato Ordinatório<br/>(19%)"]
    B2_2 --> C2_2

    %% Posição 5
    D1_1["Expedição<br/>(58%)"]
    C1_1 --> D1_1
    D1_2["Petição<br/>(25%)"]
    C1_1 --> D1_2
    D2_1["Remessa<br/>(24%)"]
    C1_2 --> D2_1
    D2_2["Ato Ordinatório<br/>(19%)"]
    C1_2 --> D2_2
    D1_1["Publicação<br/>(93%)"]
    C2_1 --> D1_1
    D1_2["Expedição<br/>(4%)"]
    C2_1 --> D1_2
    D2_1["Ato Ordinatório<br/>(45%)"]
    C2_2 --> D2_1
    D2_2["Expedição<br/>(19%)"]
    C2_2 --> D2_2

    %% Posição 6
    E1_1["Remessa<br/>(24%)"]
    D1_1 --> E1_1
    E1_2["Ato Ordinatório<br/>(19%)"]
    D1_1 --> E1_2
    E2_1["Conclusão<br/>(35%)"]
    D1_2 --> E2_1
    E2_2["Expedição<br/>(27%)"]
    D1_2 --> E2_2
    E1_1["Publicação<br/>(93%)"]
    D2_1 --> E1_1
    E1_2["Expedição<br/>(4%)"]
    D2_1 --> E1_2
    E2_1["Ato Ordinatório<br/>(45%)"]
    D2_2 --> E2_1
    E2_2["Expedição<br/>(19%)"]
    D2_2 --> E2_2

    classDef inicio fill:#0ca30c,stroke:#333,stroke-width:3px,color:#fff,font-weight:bold
    classDef processo fill:#3987e5,stroke:#333,stroke-width:2px,color:#fff
    class Start inicio
```

## Análise Estatística

- **Processos analisados:** 284
- **Total de eventos:** 3415
- **Posição máxima:** 52
- **Posição média:** 12.0
