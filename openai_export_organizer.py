#!/usr/bin/env python3
"""Organiza exportações da OpenAI em estrutura legível para usuário final."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import zipfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ItemRelatorio:
    categoria: str
    subpasta: str
    nome_original: str
    nome_final: str
    origem: str


KEYWORD_TO_FOLDER = {
    "conversation": "conversas",
    "message": "conversas",
    "chat": "conversas",
    "usage": "uso",
    "token": "uso",
    "billing": "financeiro",
    "invoice": "financeiro",
    "payment": "financeiro",
    "subscription": "perfil",
    "account": "perfil",
    "profile": "perfil",
    "preference": "perfil",
}


class OpenAIExportOrganizer:
    def __init__(self, source: Path, output: Path, dry_run: bool = False) -> None:
        self.source = source
        self.output = output
        self.dry_run = dry_run
        self.report_items: list[ItemRelatorio] = []
        self._tmp_dir: tempfile.TemporaryDirectory[str] | None = None

    def run(self) -> None:
        working_dir = self._prepare_input()
        files = [p for p in working_dir.rglob("*") if p.is_file()]

        if not files:
            print("Nenhum arquivo encontrado na exportação.")
            return

        self.output.mkdir(parents=True, exist_ok=True)
        self._process_conversations_file(files)

        # copia o restante com nomes amigáveis
        for file_path in files:
            if file_path.name.lower() == "conversations.json":
                continue
            self._copy_generic_file(file_path)

        if not self.dry_run:
            self._write_csv_report()
            self._write_json_summary()

        print(f"Concluído. Itens processados: {len(self.report_items)}")
        if self._tmp_dir is not None:
            self._tmp_dir.cleanup()

    def _prepare_input(self) -> Path:
        if self.source.is_file() and self.source.suffix.lower() == ".zip":
            self._tmp_dir = tempfile.TemporaryDirectory(prefix="openai_export_")
            extracted = Path(self._tmp_dir.name)
            with zipfile.ZipFile(self.source, "r") as zf:
                zf.extractall(extracted)
            print(f"Origem ZIP detectada: {self.source}")
            return extracted
        return self.source

    def _process_conversations_file(self, files: list[Path]) -> None:
        conversations_path = next(
            (p for p in files if p.name.lower() == "conversations.json"), None
        )
        if not conversations_path:
            return

        try:
            payload = json.loads(conversations_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("Aviso: conversations.json inválido, mantendo arquivo bruto.")
            self._copy_generic_file(conversations_path)
            return

        if not isinstance(payload, list):
            self._copy_generic_file(conversations_path)
            return

        for index, conv in enumerate(payload, start=1):
            self._export_single_conversation(conv, index, conversations_path)

    def _export_single_conversation(
        self, conversation: dict[str, Any], index: int, source_file: Path
    ) -> None:
        title = self._extract_title(conversation) or f"conversa_{index:04d}"
        date_key = self._extract_conversation_date(conversation)
        safe_title = self._slugify(title)

        folder = self.output / "conversas" / date_key
        json_name = f"{index:04d}_{safe_title}.json"
        md_name = f"{index:04d}_{safe_title}.md"

        self._write_file(folder / json_name, json.dumps(conversation, ensure_ascii=False, indent=2))
        self._write_file(folder / md_name, self._conversation_to_markdown(conversation, title))

        self.report_items.append(
            ItemRelatorio("conversas", date_key, source_file.name, md_name, str(source_file))
        )

    def _copy_generic_file(self, file_path: Path) -> None:
        relative_name = self._slugify(file_path.stem)
        category = self._categorize(file_path.name)
        date_folder = self._mtime_year_month(file_path)
        output_folder = self.output / category / date_folder

        friendly_name = f"{category}_{relative_name}{file_path.suffix.lower()}"
        destination = self._resolve_collision(output_folder / friendly_name)

        if self.dry_run:
            print(f"[DRY-RUN] {file_path} -> {destination}")
        else:
            output_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, destination)

        self.report_items.append(
            ItemRelatorio(category, date_folder, file_path.name, destination.name, str(file_path))
        )

    def _write_file(self, destination: Path, content: str) -> None:
        destination = self._resolve_collision(destination)
        if self.dry_run:
            print(f"[DRY-RUN] criar {destination}")
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def _categorize(self, filename: str) -> str:
        lower = filename.lower()
        for key, folder in KEYWORD_TO_FOLDER.items():
            if key in lower:
                return folder
        if lower.endswith((".json", ".jsonl")):
            return "dados_json"
        if lower.endswith((".csv", ".tsv", ".xlsx")):
            return "planilhas"
        return "outros"

    def _mtime_year_month(self, file_path: Path) -> str:
        try:
            return datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC).strftime("%Y-%m")
        except OSError:
            return "sem_data"

    def _extract_title(self, conversation: dict[str, Any]) -> str | None:
        title = conversation.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
        return None

    def _extract_conversation_date(self, conversation: dict[str, Any]) -> str:
        candidates = [conversation.get("create_time"), conversation.get("update_time")]
        for candidate in candidates:
            parsed = self._parse_timestamp(candidate)
            if parsed:
                return parsed.strftime("%Y-%m")

        mapping = conversation.get("mapping")
        if isinstance(mapping, dict):
            for node in mapping.values():
                if not isinstance(node, dict):
                    continue
                parsed = self._parse_timestamp(node.get("create_time"))
                if parsed:
                    return parsed.strftime("%Y-%m")

        return "sem_data"

    def _parse_timestamp(self, value: Any) -> datetime | None:
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=UTC)
            except (OSError, ValueError):
                return None

        if isinstance(value, str) and value.strip():
            text = value.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                return None

        return None

    def _conversation_to_markdown(self, conversation: dict[str, Any], title: str) -> str:
        lines = [f"# {title}", ""]
        messages = self._extract_messages(conversation)

        if not messages:
            lines.append("_Sem mensagens identificáveis nesse item de conversa._")
            return "\n".join(lines)

        for idx, message in enumerate(messages, start=1):
            role = message.get("role", "desconhecido")
            text = message.get("text", "").strip() or "(sem conteúdo textual)"
            lines.append(f"## {idx:03d} · {role}")
            lines.append("")
            lines.append(text)
            lines.append("")

        return "\n".join(lines)

    def _extract_messages(self, conversation: dict[str, Any]) -> list[dict[str, str]]:
        mapping = conversation.get("mapping")
        if not isinstance(mapping, dict):
            return []

        raw_messages: list[tuple[float, dict[str, str]]] = []
        for node in mapping.values():
            if not isinstance(node, dict):
                continue
            msg = node.get("message")
            if not isinstance(msg, dict):
                continue

            author = msg.get("author") if isinstance(msg.get("author"), dict) else {}
            role = author.get("role") if isinstance(author, dict) else "desconhecido"
            content = msg.get("content") if isinstance(msg.get("content"), dict) else {}
            parts = content.get("parts") if isinstance(content, dict) else None

            text = ""
            if isinstance(parts, list):
                text = "\n".join(str(p) for p in parts if p is not None)

            created = msg.get("create_time")
            timestamp = float(created) if isinstance(created, (int, float)) else float("inf")
            raw_messages.append((timestamp, {"role": str(role), "text": text}))

        raw_messages.sort(key=lambda item: item[0])
        return [item[1] for item in raw_messages]

    def _resolve_collision(self, destination: Path) -> Path:
        if not destination.exists():
            return destination

        index = 1
        while True:
            candidate = destination.with_name(
                f"{destination.stem}_{index}{destination.suffix}"
            )
            if not candidate.exists():
                return candidate
            index += 1

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower())
        slug = slug.strip("_")
        return slug[:80] or "sem_nome"

    def _write_csv_report(self) -> None:
        report_file = self.output / "relatorio_organizacao.csv"
        with report_file.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(["categoria", "subpasta", "nome_original", "nome_final", "origem"])
            for item in self.report_items:
                writer.writerow(
                    [item.categoria, item.subpasta, item.nome_original, item.nome_final, item.origem]
                )

    def _write_json_summary(self) -> None:
        summary: dict[str, int] = {}
        for item in self.report_items:
            summary[item.categoria] = summary.get(item.categoria, 0) + 1

        (self.output / "resumo.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Organiza exportação de dados da OpenAI em estrutura legível"
    )
    parser.add_argument("origem", help="Pasta da exportação ou arquivo ZIP")
    parser.add_argument("destino", help="Pasta de saída para arquivos organizados")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gerar arquivos")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    source = Path(args.origem).expanduser().resolve()
    output = Path(args.destino).expanduser().resolve()

    if not source.exists():
        raise FileNotFoundError(f"Origem não encontrada: {source}")

    organizer = OpenAIExportOrganizer(source=source, output=output, dry_run=args.dry_run)
    organizer.run()


if __name__ == "__main__":
    main()
