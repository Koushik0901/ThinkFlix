from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


def read_input(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return normalize_text(path.read_text(encoding="utf-8"))
    if suffix == ".pdf":
        return normalize_text(_read_pdf(path))
    raise ValueError(f"Unsupported input format: {path.suffix}")


def _read_pdf(path: Path) -> str:
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for PDF input. Install project dependencies first.")
    chunks: list[str] = []
    with fitz.open(path) as document:
        title = document.metadata.get("title") if document.metadata else None
        chunks.append(f"# {title or path.stem}")
        chunks.append(f"Source file: {path}")
        chunks.append(f"Page count: {document.page_count}")
        for page_index, page in enumerate(document, start=1):
            page_chunks = [f"## Page {page_index}"]
            page_text = page.get_text("text").strip()
            if page_text:
                page_chunks.append(page_text)
            for table_index, rows in enumerate(_extract_page_tables(page), start=1):
                markdown = rows_to_markdown_table(rows)
                if markdown:
                    page_chunks.append(f"### Table {table_index} on Page {page_index}")
                    page_chunks.append(markdown)
            chunks.append("\n\n".join(page_chunks))
    return "\n\n".join(chunks)


def _extract_page_tables(page) -> list[list[list[str]]]:
    with contextlib.redirect_stdout(io.StringIO()):
        tables = page.find_tables().tables
    return [table.extract() for table in tables]


def rows_to_markdown_table(rows: list[list[str | None]]) -> str:
    cleaned_rows = [[_clean_table_cell(cell) for cell in row] for row in rows if row]
    if not cleaned_rows:
        return ""
    width = max(len(row) for row in cleaned_rows)
    normalized_rows = [row + [""] * (width - len(row)) for row in cleaned_rows]
    header = normalized_rows[0]
    body = normalized_rows[1:] or [[""] * width]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _clean_table_cell(cell: str | None) -> str:
    if cell is None:
        return ""
    text = re.sub(r"\s+", " ", str(cell)).strip()
    return text.replace("|", r"\|")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 3500) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        next_len = current_len + len(paragraph) + 2
        if current and next_len > max_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len = next_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks
