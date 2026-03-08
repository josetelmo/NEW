# Organizador de exportação de conta da OpenAI

Este projeto fornece um sistema em **Python** para organizar arquivos exportados da OpenAI.

## O que ele faz

- Aceita como origem uma **pasta** ou um **arquivo `.zip`** da exportação.
- Classifica os arquivos em categorias (`conversas`, `financeiro`, `uso`, `perfil`, etc.).
- Cria subpastas por **ano-mês** usando a data de modificação de cada arquivo.
- Evita sobrescrever arquivos com nomes iguais (gera sufixos `_1`, `_2`, ...).
- Gera ao final:
  - `relatorio_organizacao.csv` com todos os arquivos organizados.
  - `resumo.json` com quantidade de arquivos por categoria.

## Requisitos

- Python 3.9+

## Como usar

### 1) Organizar a partir de uma pasta

```bash
python openai_export_organizer.py ./minha_exportacao ./saida_organizada
```

### 2) Organizar a partir de um ZIP exportado

```bash
python openai_export_organizer.py ./openai_export.zip ./saida_organizada
```

### 3) Simular sem copiar arquivos

```bash
python openai_export_organizer.py ./minha_exportacao ./saida_organizada --dry-run
```

## Estrutura de saída (exemplo)

```text
saida_organizada/
  conversas/
    2026-02/
      conversations.json
  uso/
    2026-02/
      usage.csv
  financeiro/
    2026-02/
      billing_history.csv
  relatorio_organizacao.csv
  resumo.json
```
