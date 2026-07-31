"""Shared Wave-0 test scaffolding for the Phase-2 tools suite (mirrors tests/ingest/conftest.py's
discipline: every tests/tools/* test imports fixtures/builders from here, entirely offline).

Provides:
  * `fresh_ledger`      -- a brand-new, per-test `RetrievalLedger()`.
  * `make_doc_dict`     -- re-exported directly from tests.ingest.conftest (import it, never
                            duplicate it) for building fixture corpus documents.
  * `build_corpus_index` -- a real, persisted single-document `CorpusIndex` built entirely
                            offline (no PDF/DOCX file I/O, no classification/LLM escalation) by
                            routing through the SAME Phase-1 substrate functions
                            `ingest_corpus()` itself calls, so `CorpusIndex.cached_entry()`'s
                            shape is byte-identical to a real ingest run (never a hand-rolled
                            fake cache dict).
"""
from __future__ import annotations

import pytest

from ingest.anchors import mint_span
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest, DocEntry, OutlineEntry
from ingest.normalize import NORMALIZER_VERSION, normalize
from ingest.serialize import SERIALIZER_VERSION, serialize_document
from ingest.store import cache_key, write_doc_cache
from ingest.tables import build_table_index
from tests.ingest.conftest import (
    make_doc_dict,  # noqa: F401 -- re-exported for tests/tools/* fixture builders
)
from tools.ledger import RetrievalLedger


@pytest.fixture
def fresh_ledger() -> RetrievalLedger:
    return RetrievalLedger()


def build_corpus_index(
    tmp_path, doc_id: str, blocks, tables=None, outline_headings=None,
    filename: str = "doc.pdf", title: str = "Test Document",
) -> CorpusIndex:
    """Build + persist a real single-document `CorpusIndex` fixture.

    `blocks`/`tables` feed `make_doc_dict` (the exact `extract_pdf`-shaped dict); the resulting
    doc is run through the real `serialize_document` -> `normalize` -> `build_table_index`
    pipeline `ingest_corpus()` itself uses, then cached exactly as `write_doc_cache` expects, so
    `CorpusIndex.cached_entry(doc_id)` returns a genuine cache entry, never a stand-in shape.

    `outline_headings` (optional) is an ordered list of heading strings that must appear
    verbatim in the rendered canonical text (put them inside a block's text); each becomes an
    `OutlineEntry` spanning its first occurrence, mirroring `ingest.corpus._build_outline`'s own
    best-effort match. Classification is left `None` -- Phase 2's tools never need it.
    """
    tables = tables or []
    doc = make_doc_dict(blocks, tables, filename=filename)
    raw, cell_ranges = serialize_document(doc)
    nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
    table_index = build_table_index(nt, tables, cell_ranges, doc_id)

    outline: list[OutlineEntry] = []
    for heading in outline_headings or []:
        pos = nt.canonical.find(heading)
        pos = max(pos, 0)
        span = mint_span(nt.canonical, pos, pos + len(heading), doc_id, nt.normalizer_version)
        outline.append(OutlineEntry(span=span, label=heading))

    entry = DocEntry(
        doc_id=doc_id, filename=filename, content_hash=f"testhash-{doc_id}",
        status="parsed", structure="outlined" if outline else "flat",
        tables="addressable" if table_index else "unavailable",
        classification=None, title=title, outline=outline,
        normalizer_version=nt.normalizer_version, serializer_version=nt.serializer_version,
    )

    cache_dir = str(tmp_path / "cache")
    key = cache_key(entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION)
    write_doc_cache(cache_dir, key, {
        "canonical": nt.canonical, "raw_serialized": nt.raw_serialized,
        "offset_map": [r.model_dump() for r in nt.offset_map],
        "normalizer_version": nt.normalizer_version, "serializer_version": nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in table_index.items()},
        "doc_entry": entry.model_dump(),
    })
    manifest = CoverageManifest(documents=[entry])
    return CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)
