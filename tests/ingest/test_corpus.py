"""Tests for the corpus orchestrator (Plan 09 / INGEST-01/03, SC1, D-09/D-16).

NOTE: builds test PDFs with a mid-page multi-line text box (not conftest.write_corpus_tree, whose
single top line gets marked role="page_header" and dropped by the serializer -> empty canonical;
that Plan-01 fixture limitation is flagged in the SUMMARY). Rename invariance is proven by
byte-copying A's files to renamed paths in B, guaranteeing identical bytes for BOTH formats
(python-docx zip timestamps make two separate generations non-identical).
"""
from __future__ import annotations

import shutil
from io import BytesIO
from pathlib import Path

import docx
import fitz
import pytest

import ingest.classify as classify
from ingest.corpus import ingest_corpus


@pytest.fixture(autouse=True)
def _no_creds(monkeypatch):
    """No Databricks creds -> deterministic, endpoint-free (no OCR, no LLM escalation)."""
    monkeypatch.setattr(
        classify, "get_settings",
        lambda: type("S", (), {"databricks_host": "", "databricks_token": ""})(),
    )


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(72, 200, 540, 720), text, fontsize=11)  # mid-page body, not a header
    data = doc.tobytes()
    doc.close()
    return data


def _docx_bytes(text: str) -> bytes:
    d = docx.Document()
    d.add_paragraph(text)
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def _write(root, spec: dict[str, str]) -> Path:
    root = Path(root)
    cache: dict[tuple, bytes] = {}
    for rel, content in spec.items():
        ext = Path(rel).suffix.lower()
        key = (content, ext)
        if key not in cache:
            cache[key] = _pdf_bytes(content) if ext == ".pdf" else _docx_bytes(content)
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(cache[key])
    return root


_A = {
    "m3/quality/spec.pdf": "3.2.S.4.1 Drug Substance Specification acceptance criteria limit assay",
    "m3/methods/val.docx": "validation specificity linearity accuracy precision robustness",
}
_RENAMES = {"m3/quality/spec.pdf": "Renamed Top/AAA.pdf", "m3/methods/val.docx": "zzz/deep/nest/BBB.docx"}


def _class_by_hash(index):
    return {d.content_hash: (d.classification.family_guess if d.classification else "")
            for d in index.manifest.documents if d.content_hash}


def test_rename_folders_invariant(tmp_path):
    a_root = _write(tmp_path / "A", _A)
    b_root = tmp_path / "B"
    for src_rel, dst_rel in _RENAMES.items():
        dst = b_root / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a_root / src_rel, dst)   # byte-identical copy -> same content-hash
    a = ingest_corpus(a_root, cache_dir=str(tmp_path / "ca"))
    b = ingest_corpus(b_root, cache_dir=str(tmp_path / "cb"))
    # identical file bytes -> identical content-hash set + identical per-hash classification (D-09)
    assert set(_class_by_hash(a)) == set(_class_by_hash(b))
    assert _class_by_hash(a) == _class_by_hash(b)
    assert "3.2.S.4.1" in _class_by_hash(a).values()   # the spec PDF classified by content


def test_walk_uncapped_and_unsupported(tmp_path):
    root = _write(tmp_path / "corpus", {
        "a/b/c/d/e/deep_spec.pdf": "3.2.S.4.1 specification acceptance criteria limit",
        "top.docx": "validation accuracy precision specificity",
    })
    (root / "sheet.xlsx").write_bytes(b"PK\x03\x04 not really xlsx")  # unsupported extension
    index = ingest_corpus(root, cache_dir=str(tmp_path / "cache"))
    status = {d.filename: d.status for d in index.manifest.documents}
    assert status["deep_spec.pdf"] == "parsed"    # uncapped depth walked
    assert status["top.docx"] == "parsed"
    assert status["sheet.xlsx"] == "unsupported"  # unsupported row, not a crash
    assert "parse_failed" not in set(status.values())


def test_one_bad_file_never_aborts(tmp_path):
    root = _write(tmp_path / "corpus", {
        "good/spec.pdf": "3.2.S.4.1 specification acceptance criteria limit assay",
    })
    (root / "corrupt.pdf").write_bytes(b"%PDF-1.4 broken not a real pdf body")  # corrupt PDF
    (root / "legacy.doc").write_bytes(b"\xd0\xcf\x11\xe0 old binary doc")        # unsupported .doc
    index = ingest_corpus(root, cache_dir=str(tmp_path / "cache"))
    status = {d.filename: d.status for d in index.manifest.documents}
    assert status["spec.pdf"] == "parsed"           # good doc still ingested
    assert status["corrupt.pdf"] == "parse_failed"  # bad file -> row, never aborts (D-16)
    assert status["legacy.doc"] == "unsupported"
    assert index.manifest.counts.get("parsed", 0) >= 1
