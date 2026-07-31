"""Tests for ICH vendoring (Task 3, RULES-02) -- the copyright-notice-absence-in-source
guarantee: Q3A(R2)/Q3B(R2)/Q6A predate ICH's "Legal notice" convention and embed ZERO
occurrences of "copyright" in their own PDF text, yet every persisted ich-* chunk still carries
the full ICH_LEGAL_NOTICE (Pitfall 4) -- applied uniformly as a stored constant, never scraped
per-PDF.

Runs against the REAL vendored PDFs (Task 3's committed rulebook/ich/*.pdf) and the REAL
persisted chunk store (this plan's live build) -- not synthetic fixtures, since Pitfall 4 is a
property of these actual source documents.
"""
from __future__ import annotations

from ingest.serialize import serialize_document
from parse.pdf import extract_pdf
from rulebook.build import ICH_GUIDELINES, ICH_LEGAL_NOTICE
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


def test_ich_chunk_carries_notice_even_when_source_pdf_lacks_it():
    chunks_by_doc_id = {c.doc_id: c for c in all_chunks()}

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


def test_every_ich_chunk_carries_the_notice_exactly():
    ich_chunks = [c for c in all_chunks() if c.source == "ich"]
    assert len(ich_chunks) == 4  # Q2(R2), Q3A(R2), Q3B(R2), Q6A
    for chunk in ich_chunks:
        assert chunk.license == ICH_LEGAL_NOTICE
