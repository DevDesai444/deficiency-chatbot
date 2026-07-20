"""Run a PDF through the real parsing pipeline (src/parse) and dump the raw parsed output.

Usage:
    .venv/bin/python scripts/dump_parsed_output.py "Sample Data/32s43-validation-related-compounds-method.pdf"

This is exactly the "Parsed Output" stage of the pipeline:
    PDF -> PyMuPDF text + table extraction (+ RapidOCR on Databricks for scanned pages) -> PageContent
It writes a plain-text dump next to the PDF's name in scratchpad and prints a summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Put src/ on the path so the real pipeline imports resolve.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from parse.pdf import extract_pdf  # noqa: E402


def dump(pdf_path: str, out_path: str) -> None:
    doc = extract_pdf(pdf_path)

    lines: list[str] = []
    w = lines.append

    w("=" * 80)
    w(f"PARSED OUTPUT for: {doc.filename}")
    w(f"page_count: {doc.page_count}")
    w(f"table of contents entries: {len(doc.toc)}")
    for level, title, page_num in doc.toc:
        w(f"    TOC  L{level}  p{page_num}  {title}")
    w("=" * 80)

    for page in doc.pages:
        w("")
        w("#" * 80)
        w(f"# PAGE {page.page_number}   ({len(page.text)} chars text, {len(page.tables)} tables)")
        w("#" * 80)
        w("--- RAW TEXT ---")
        w(page.text if page.text else "(no text extracted)")
        for i, table in enumerate(page.tables, 1):
            w("")
            w(f"--- TABLE {i} on page {page.page_number} ---")
            if table.title:
                w(f"title: {table.title}")
            w(f"headers: {table.headers}")
            for row in table.rows:
                w(f"row: {row}")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")

    total_chars = sum(len(p.text) for p in doc.pages)
    total_tables = sum(len(p.tables) for p in doc.pages)
    print(f"file:        {doc.filename}")
    print(f"pages:       {doc.page_count}")
    print(f"text chars:  {total_chars}")
    print(f"tables:      {total_tables}")
    print(f"toc entries: {len(doc.toc)}")
    print(f"dump written to: {out_path}")


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "Sample Data/32s43-validation-related-compounds-method.pdf"
    out = sys.argv[2] if len(sys.argv) > 2 else "/private/tmp/claude-502/-Users-DEVDESAI1-Desktop-INTERN-Amneal-deficiency-chatbot/975efdb0-c084-40e4-8467-3e6eccdf346f/scratchpad/parsed_output.txt"
    dump(pdf, out)
