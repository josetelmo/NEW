#!/usr/bin/env python3
"""Organiza arquivos de exportação de conta da OpenAI em uma estrutura útil."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Categoria:
    nome: str
    pasta: str


CATEGORIAS_CONHECIDAS = {
    "conversations": Categoria("Conversa", "conversas"),
    "chat": Categoria("Conversa", "conversas"),
    "messages": Categoria("Conversa", "conversas"),
    "billing": Categoria("Financeiro", "financeiro"),
    "invoice": Categoria("Financeiro", "financeiro"),
    "payment": Categoria("Financeiro", "financeiro"),
    "usage": Categoria("Uso", "uso"),
    "model": Categoria("Uso", "uso"),
    "api": Categoria("Uso", "uso"),
    "profile": Categoria("Perfil", "perfil"),
    "account": Categoria("Perfil", "perfil"),
    "subscription": Categoria("Perfil", "perfil"),
}


class OrganizadorExportOpenAI:
    def __init__(self, origem: Path, destino: Path, modo_simulacao: bool = False) -> None:
        self.origem = origem
        self.destino = destino
        self.modo_simulacao = modo_simulacao
        self.arquivos_movidos = 0

    def executar(self) -> None:
        arquivos = list(self._listar_arquivos(self.origem))
        if not arquivos:
            print("Nenhum arquivo foi encontrado para organizar.")
            return

        self.destino.mkdir(parents=True, exist_ok=True)
        for arquivo in arquivos:
            categoria = self._detectar_categoria(arquivo)
            ano_mes = self._detectar_ano_mes(arquivo)
            pasta_final = self.destino / categoria.pasta / ano_mes
            destino_arquivo = pasta_final / arquivo.name
            self._mover_arquivo(arquivo, destino_arquivo)

        print(f"Organização concluída. Total de arquivos processados: {self.arquivos_movidos}")

    def _listar_arquivos(self, pasta: Path) -> Iterable[Path]:
        for caminho in pasta.rglob("*"):
            if caminho.is_file():
                yield caminho

    def _detectar_categoria(self, arquivo: Path) -> Categoria:
        nome = arquivo.stem.lower()
        for palavra, categoria in CATEGORIAS_CONHECIDAS.items():
            if palavra in nome:
                return categoria

        if arquivo.suffix.lower() in {".json", ".jsonl"}:
            return Categoria("Dados JSON", "dados_json")
        if arquivo.suffix.lower() in {".csv", ".tsv"}:
            return Categoria("Planilhas", "planilhas")

        return Categoria("Outros", "outros")

    def _detectar_ano_mes(self, arquivo: Path) -> str:
        try:
            timestamp = arquivo.stat().st_mtime
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m")
        except OSError:
            return "sem_data"

    def _mover_arquivo(self, origem: Path, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino = self._resolver_colisao(destino)

        if self.modo_simulacao:
            print(f"[DRY-RUN] {origem} -> {destino}")
        else:
            shutil.copy2(origem, destino)
            print(f"Copiado: {origem.name} -> {destino}")

        self.arquivos_movidos += 1

    def _resolver_colisao(self, destino: Path) -> Path:
        if not destino.exists():
            return destino

        indice = 1
        while True:
            novo_nome = f"{destino.stem}_{indice}{destino.suffix}"
            candidato = destino.with_name(novo_nome)
            if not candidato.exists():
                return candidato
            indice += 1


def extrair_zip(zip_path: Path, pasta_saida: Path) -> Path:
    pasta_extraida = pasta_saida / f"extraido_{zip_path.stem}"
    pasta_extraida.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(pasta_extraida)

    return pasta_extraida


def gerar_relatorio_csv(pasta_destino: Path) -> Path:
    relatorio = pasta_destino / "relatorio_organizacao.csv"

    with relatorio.open("w", newline="", encoding="utf-8") as arquivo_csv:
        writer = csv.writer(arquivo_csv)
        writer.writerow(["categoria", "subpasta_data", "arquivo"])

        for arquivo in sorted(pasta_destino.rglob("*")):
            if not arquivo.is_file() or arquivo == relatorio:
                continue

            relativo = arquivo.relative_to(pasta_destino)
            partes = relativo.parts
            if len(partes) >= 3:
                writer.writerow([partes[0], partes[1], partes[-1]])
            elif len(partes) == 2:
                writer.writerow([partes[0], "sem_data", partes[-1]])
            else:
                writer.writerow(["raiz", "sem_data", partes[-1]])

    return relatorio


def salvar_resumo_json(pasta_destino: Path) -> Path:
    resumo = {}
    for categoria in pasta_destino.iterdir():
        if not categoria.is_dir():
            continue

        total = sum(1 for arquivo in categoria.rglob("*") if arquivo.is_file())
        resumo[categoria.name] = total

    caminho = pasta_destino / "resumo.json"
    caminho.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Organiza arquivos de exportação da OpenAI por categoria e data"
    )
    parser.add_argument(
        "origem",
        help="Pasta ou arquivo .zip da exportação",
    )
    parser.add_argument(
        "destino",
        help="Pasta onde os arquivos organizados serão salvos",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra as ações sem copiar os arquivos",
    )
    return parser


def main() -> None:
    parser = criar_parser()
    args = parser.parse_args()

    origem = Path(args.origem).expanduser().resolve()
    destino = Path(args.destino).expanduser().resolve()

    if not origem.exists():
        raise FileNotFoundError(f"Origem não encontrada: {origem}")

    origem_processamento = origem
    if origem.is_file() and origem.suffix.lower() == ".zip":
        origem_processamento = extrair_zip(origem, destino)
        print(f"ZIP extraído em: {origem_processamento}")

    organizador = OrganizadorExportOpenAI(
        origem=origem_processamento,
        destino=destino,
        modo_simulacao=args.dry_run,
    )
    organizador.executar()

    if not args.dry_run:
        relatorio = gerar_relatorio_csv(destino)
        resumo = salvar_resumo_json(destino)
        print(f"Relatório CSV salvo em: {relatorio}")
        print(f"Resumo JSON salvo em: {resumo}")


if __name__ == "__main__":
    main()
