"""Tests for the (table_id,row,col) cell index (Plan 06 Task 2 / INGEST-05, D-31)."""
from __future__ import annotations

from tests.ingest.conftest import make_doc_dict, merged_table

from ingest.anchors import open_span
from ingest.normalize import normalize
from ingest.serialize import serialize_document
from ingest.tables import build_table_index

_DOC_ID = "d1"


def _index_for(tables):
    doc = make_doc_dict([], tables)
    raw, cell_ranges = serialize_document(doc)
    nt = normalize(raw)
    idx = build_table_index(nt, tables, cell_ranges, _DOC_ID)
    return idx, nt


def test_merged_resolves_identically():
    # (0,1) is covered by origin (0,0); both must resolve to the SAME span-ID (D-31).
    tables = [merged_table(headers=["Merged", "COVERED"], rows=[["x", "y"]],
                          merged_origins={"0,1": [0, 0]}, table_id="t0")]
    idx, nt = _index_for(tables)
    assert idx["t0,0,1"] == idx["t0,0,0"]           # covered coord shares the origin span
    assert "t0,0,0" in idx and "t0,1,0" in idx and "t0,1,1" in idx
    # each origin cell re-opens to its exact text
    assert open_span(idx["t0,0,0"], nt, _DOC_ID)[1] == "Merged"
    assert open_span(idx["t0,1,1"], nt, _DOC_ID)[1] == "y"
    # the covered coord re-opens to the ORIGIN's text (not a separate cell)
    assert open_span(idx["t0,0,1"], nt, _DOC_ID)[1] == "Merged"


def test_serialization_deterministic():
    tables = [merged_table(headers=["A", "B"], rows=[["1", "2"]],
                          merged_origins={"1,1": [1, 0]}, table_id="t0")]
    idx1, _ = _index_for(tables)
    idx2, _ = _index_for(tables)
    assert set(idx1) == set(idx2)
    for k in idx1:
        assert idx1[k].model_dump() == idx2[k].model_dump()  # identical span-IDs + offsets
