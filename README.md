# Organizador de dados exportados da OpenAI

Ferramenta em Python para transformar o `.zip` de exportação da OpenAI em uma estrutura legível, com nomes amigáveis.

## Melhorias principais

- Lê exportação em **pasta** ou **arquivo ZIP**.
- Processa `conversations.json` e gera, para cada conversa:
  - um arquivo `.json` individual;
  - um arquivo `.md` com mensagens em ordem cronológica.
- Renomeia arquivos genéricos com padrão legível por categoria.
- Agrupa tudo por categoria e `YYYY-MM`.
- Gera:
  - `relatorio_organizacao.csv`;
  - `resumo.json`.

## Requisitos

- Python 3.9+

## Uso

```bash
python openai_export_organizer.py <origem_zip_ou_pasta> <pasta_saida>
```

### Simulação

```bash
python openai_export_organizer.py <origem_zip_ou_pasta> <pasta_saida> --dry-run
```

## Exemplo de saída

```text
saida/
  conversas/
    2025-11/
      0001_planejamento_de_viagem.md
      0001_planejamento_de_viagem.json
  uso/
    2025-11/
      uso_usage_2025_11.csv
  financeiro/
    2025-11/
      financeiro_billing_history.csv
  relatorio_organizacao.csv
  resumo.json
```
