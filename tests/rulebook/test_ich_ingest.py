"""Tests for ICH vendoring (Task 3, RULES-02) -- the copyright-notice-absence-in-source
guarantee: Q3A(R2)/Q3B(R2)/Q6A predate ICH's "Legal notice" convention and embed ZERO
occurrences of "copyright" in their own PDF text, yet every persisted ich-* chunk still carries
the full ICH_LEGAL_NOTICE (Pitfall 4) -- applied uniformly as a stored constant, never scraped
per-PDF.

OFFLINE (D-RB6): builds all 4 ICH chunks from the REAL, COMMITTED rulebook/ich/*.pdf snapshot
(Task 3's vendored files) via build_ich's local-file-first path (src/rulebook/build.py) into an
ISOLATED tmp_path_factory-scoped store -- NO network call, NO dependence on the shared default
data/ store. Not synthetic fixtures: Pitfall 4 is a property of these actual source documents.
A module-scoped fixture builds once; every test reads through all_chunks with an explicit
db_path. Source-PDF verification (part (a) of the first test) parses the real, committed PDF
bytes directly -- also fully offline, just not through the store.
"""
from __future__ import annotations

import pytest

from ingest.serialize import serialize_document
from parse.pdf import extract_pdf
from rulebook.build import ICH_GUIDELINES, ICH_LEGAL_NOTICE, build_ich
from rulebook.store import all_chunks

# The 3 pre-2015 guidelines confirmed (RESEARCH.md live full-text scan) to embed zero
# occurrences of "copyright" in their own source PDF -- Q2(R2) (2023) is excluded here since it
# DOES carry its own notice; the guarantee under test matters most for these notice-less three.
_NOTICE_LESS_DOC_IDS = ("ich-Q3A-R2", "ich-Q3B-R2", "ich-Q6A")


def _source_pdf_path(doc_id: str) -> str:
    short = doc_id.removeprefix("ich-")
    for guideline_id, _citation, _version, _url, rel_path in ICH_GUIDELINES:
        if guideline_id == short:
            return rel_path
    raise AssertionError(f"no ICH_GUIDELINES entry for {doc_id!r}")


@pytest.fixture(scope="module")
def ich_db_path(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("ich_rulebook")
    cache_dir = str(tmp_dir / "cache")
    db_path = str(tmp_dir / "rulebook_test.db")

    rows = build_ich(cache_dir=cache_dir, db_path=db_path, update_manifest=False)

    assert not any("error" in row for row in rows), f"build_ich reported an error offline: {rows}"
    return db_path


def test_ich_chunk_carries_notice_even_when_source_pdf_lacks_it(ich_db_path):
    chunks_by_doc_id = {c.doc_id: c for c in all_chunks(db_path=ich_db_path)}

    for doc_id in _NOTICE_LESS_DOC_IDS:
        # (a) the SOURCE PDF itself embeds zero occurrences of "copyright" -- re-verified here
        # against the actually-vendored, committed file (not asserted from memory of RESEARCH.md).
        path = _source_pdf_path(doc_id)
        parsed = extract_pdf(path)
        raw_text, _cell_ranges = serialize_document(parsed)
        assert "copyright" not in raw_text.lower(), (
            f"{doc_id}'s source PDF unexpectedly contains 'copyright' -- Pitfall 4 assumption changed"
        )

        # (b) the STORED chunk carries the notice anyway -- applied as a uniform constant, not
        # scraped per-PDF (build_ich always passes ICH_LEGAL_NOTICE as license_text).
        assert doc_id in chunks_by_doc_id, f"{doc_id} not found in the persisted chunk store"
        assert chunks_by_doc_id[doc_id].license == ICH_LEGAL_NOTICE


def test_every_ich_chunk_carries_the_notice_exactly(ich_db_path):
    ich_chunks = [c for c in all_chunks(db_path=ich_db_path) if c.source == "ich"]
    assert len(ich_chunks) == 4  # Q2(R2), Q3A(R2), Q3B(R2), Q6A
    for chunk in ich_chunks:
        assert chunk.license == ICH_LEGAL_NOTICE
