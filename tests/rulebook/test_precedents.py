"""Tests for src/rulebook/precedents.py -- D-PREC audited precedent ingestion (Task 4).

Runs against the REAL vendored file `rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm`
(Task 3's committed output, this SAME plan) -- not a synthetic fixture, since the exact counts
below (385 chunks, 83 forward-filled rows) are THIS dataset's, per 02-PRECEDENT-AUDIT.md's
completed audit. `ingest_precedents` defaults to the REAL `rulebook.store` backend, so running
this suite populates the real local precedent chunk store -- exactly Task 4's intent (D-PREC
requires ingestion NOW, per the audit's "Coverage-gap finding (actioned)").
"""
from __future__ import annotations

import pytest

from ingest.anchors import open_span
from rulebook.precedents import get_provenance, ingest_precedents
from rulebook.store import read_chunk_nt

_XLSM_PATH = "rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm"


@pytest.fixture(scope="module")
def chunks():
    return ingest_precedents(_XLSM_PATH)


def test_ingest_precedents_dedupes_to_385_chunks(chunks):
    assert len(chunks) == 385


def test_duplicated_text_chunk_has_multi_row_provenance(chunks):
    multi_row = [c for c in chunks if len(get_provenance(c.doc_id)) >= 2]
    assert multi_row, "expected at least one deduped chunk with >=2 provenance rows (80 dup groups exist)"


def test_forward_fill_stamps_anda_inferred(chunks):
    all_provenance = [row for c in chunks for row in get_provenance(c.doc_id)]

    inferred_count = sum(1 for row in all_provenance if row["anda_inferred"] == 1)
    assert inferred_count == 83

    assert any(row["anda_inferred"] == 0 for row in all_provenance)
    assert all(row["anda_number"] for row in all_provenance)  # every row is non-empty post-fill


def test_precedent_chunk_reopens_byte_exact(chunks):
    for chunk in chunks:
        nt = read_chunk_nt(chunk.doc_id)
        assert nt is not None
        raw, canonical = open_span(chunk.span, nt, chunk.doc_id)
        assert canonical == nt.canonical  # same grounding contract rule chunks get
        assert raw
