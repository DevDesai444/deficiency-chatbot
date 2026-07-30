"""Shared Wave-0 test scaffolding for the Phase-1 ingestion suite.

Every `tests/ingest/*` test imports its fixtures/builders from here so the whole
suite runs OFFLINE and endpoint-free (01-VALIDATION.md): no Databricks OCR, no
LLM creds, only deterministic in-memory fixtures.

Provides:
  * `offline`  -- monkeypatch parse.ocr to the no-Databricks OCR fallback.
  * `no_llm`   -- `offline` plus the same no-creds patch for llm.client, so the
                  classifier's LLM-escalation tier (Plan 08) degrades to
                  deterministic-only under test.
  * `_block` / `_grid` -- minimal block/table dict builders (mirrors
                  tests/unit/test_section_splitter.py).
  * `make_doc_dict` -- factory returning the EXACT dict `parse.pdf.extract_pdf`
                  emits, so ingest tests can feed the converged document model
                  without touching a real PDF.
  * `merged_table` -- an ExtractedTable dict (kind="grid") carrying the new
                  `table_id` + `merged_origins` fields, so serialize/table tests
                  can feed a merged table WITHOUT the DOCX parser.
  * `write_corpus_tree` -- writes an arbitrarily-nested tmp tree of real,
                  parseable PDF + DOCX files (byte-identical across paths that
                  share a content key) for the SC1 rename-folders invariant.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
import pytest
from docx import Document


# --- no-creds fixtures -------------------------------------------------------
@pytest.fixture
def offline(monkeypatch):
    """Force the no-Databricks OCR fallback so tests are fast and deterministic."""
    from config import Settings
    import parse.ocr as ocrmod

    monkeypatch.setattr(
        ocrmod, "get_settings", lambda: Settings(databricks_host="", databricks_token="")
    )


@pytest.fixture
def no_llm(monkeypatch):
    """`offline` + no-creds llm.client, so the classifier LLM tier degrades to deterministic."""
    from config import Settings

    empty = lambda: Settings(databricks_host="", databricks_token="")  # noqa: E731
    import parse.ocr as ocrmod

    monkeypatch.setattr(ocrmod, "get_settings", empty)
    # llm.client binds `get_settings` into its own namespace (from config import get_settings);
    # patch it there. raising=False keeps this robust if the classifier lands elsewhere later.
    import llm.client as clientmod

    monkeypatch.setattr(clientmod, "get_settings", empty, raising=False)


# --- block / table dict builders (mirror test_section_splitter.py) -----------
def _block(text, page=1, order=0):
    """A minimal body-block dict; split_document reads text/page/reading_order via .get()."""
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _grid(page, y0, y1, headers, rows, title=""):
    """A grid ExtractedTable dict (no merges)."""
    return {
        "kind": "grid", "title": title, "headers": headers, "rows": rows, "pairs": [],
        "page": page, "bbox": (72, y0, 540, y1), "n_cols": len(headers), "n_rows": len(rows) + 1,
        "source_pages": [page], "continues_from": False, "continues_to": False,
    }


def merged_table(headers, rows, merged_origins, page=1, title="", table_id="t0", y0=100, y1=200):
    """An ExtractedTable dict carrying table_id + merged_origins (Plan 02 schema fields).

    `merged_origins` maps "r,c" (a COVERED non-origin coordinate, row/col over the
    grid) -> [origin_row, origin_col]. Origin coordinates are NOT keys.
    """
    return {
        "kind": "grid", "title": title, "headers": headers, "rows": rows, "pairs": [],
        "page": page, "bbox": (72, y0, 540, y1), "n_cols": len(headers), "n_rows": len(rows) + 1,
        "source_pages": [page], "continues_from": False, "continues_to": False,
        "table_id": table_id, "merged_origins": merged_origins,
    }


# --- document-dict factory (EXACT extract_pdf shape) -------------------------
def make_doc_dict(blocks, tables, filename="doc.pdf", page_count=1, toc=None):
    """Return the exact dict parse.pdf.extract_pdf emits, with blocks/tables on page 1.

    Shape (see src/parse/pdf.py:197-258):
        {filename, page_count, toc:[...],
         pages:[{page_number, page_label, width, height, rotation, source,
                 is_scanned, blocks, tables, figures}]}
    """
    return {
        "filename": filename,
        "page_count": page_count,
        "toc": list(toc or []),
        "pages": [
            {
                "page_number": 1,
                "page_label": "",
                "width": 612.0,
                "height": 792.0,
                "rotation": 0,
                "source": "pymupdf",
                "is_scanned": False,
                "blocks": list(blocks),
                "tables": list(tables),
                "figures": [],
            }
        ],
    }


# --- real-file corpus-tree builder (SC1 rename-folders invariant) ------------
def _make_doc_bytes(content: str, ext: str) -> bytes:
    """Generate a real, parseable one-page PDF or DOCX whose body contains `content`.

    Generated ONCE per (content, ext) by the caller and byte-copied to every path
    that references the key, so identical content produces byte-identical files
    across differently-named layouts (the SC1 rename-folders invariant proves
    CLASSIFICATION does not change under renaming; a stub that fails to parse
    would never reach classification -- so these must be real documents).
    """
    if ext == ".pdf":
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), content)
        data = doc.tobytes()
        doc.close()
        return data
    if ext == ".docx":
        document = Document()
        document.add_paragraph(content)
        buf = BytesIO()
        document.save(buf)
        return buf.getvalue()
    raise ValueError(f"write_corpus_tree: unsupported extension {ext!r} (want .pdf/.docx)")


def write_corpus_tree(root, spec: dict[str, str]):
    """Write a nested tree of real PDF/DOCX files under `root`.

    `spec` maps a relative path (e.g. "m3/quality/spec.pdf", "Renamed/AAA.docx")
    to a CONTENT KEY (a string that becomes the document body). Paths sharing a
    content key + extension get BYTE-IDENTICAL files (single generation, copied),
    so a renamed layout is byte-for-byte equal to its original where the content
    keys match. Returns the root Path.
    """
    root = Path(root)
    cache: dict[tuple[str, str], bytes] = {}
    for rel, content in spec.items():
        rel_path = Path(rel)
        ext = rel_path.suffix.lower()
        key = (content, ext)
        if key not in cache:
            cache[key] = _make_doc_bytes(content, ext)
        dest = root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(cache[key])
    return root
