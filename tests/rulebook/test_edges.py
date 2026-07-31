"""Tests for src/rulebook/edges.py -- the generic (src_id, dst_id, edge_type,
provenance_span_id) edge table (D-RB3). Offline, no network (D-RB6); every test uses a
tmp_path-scoped SQLite db, never the shared data/defpredict.db file.
"""
from __future__ import annotations

import pytest

from rulebook.edges import add_edge, get_edges
from schemas.documents import SpanID


def _provenance(doc_id: str = "rule-doc", start: int = 0, end: int = 10, hash_: str = "deadbeef") -> str:
    return SpanID(doc_id=doc_id, start=start, end=end, hash=hash_).model_dump_json()


def test_add_edge_then_get_edges_by_edge_type(tmp_path):
    db_path = str(tmp_path / "edges.db")
    span_json = _provenance()

    add_edge(
        src_id="3.2.P.7",
        dst_id="Q1-STABILITY",
        edge_type="family_requires_requirement",
        provenance_span_id=span_json,
        db_path=db_path,
    )

    rows = get_edges(edge_type="family_requires_requirement", db_path=db_path)

    assert rows == [("3.2.P.7", "Q1-STABILITY", "family_requires_requirement", span_json)]


def test_get_edges_filters_by_any_subset_of_src_dst_type(tmp_path):
    db_path = str(tmp_path / "edges.db")
    add_edge("3.2.P.7", "Q1-STABILITY", "family_requires_requirement", _provenance("d1"), db_path=db_path)
    add_edge("3.2.S.4.1", "Q6A-SPEC", "family_requires_requirement", _provenance("d2"), db_path=db_path)
    add_edge(
        "drug-product-profile", "3.2.P.7", "profile_requires_family", _provenance("d3"), db_path=db_path
    )

    # no filters -> all rows
    assert len(get_edges(db_path=db_path)) == 3
    # src_id only
    by_src = get_edges(src_id="3.2.P.7", db_path=db_path)
    assert len(by_src) == 1 and by_src[0][1] == "Q1-STABILITY"
    # dst_id only
    by_dst = get_edges(dst_id="3.2.P.7", db_path=db_path)
    assert len(by_dst) == 1 and by_dst[0][0] == "drug-product-profile"
    # edge_type only
    by_type = get_edges(edge_type="family_requires_requirement", db_path=db_path)
    assert len(by_type) == 2
    # combination of all three
    exact = get_edges(
        src_id="3.2.P.7", dst_id="Q1-STABILITY", edge_type="family_requires_requirement", db_path=db_path
    )
    assert len(exact) == 1


def test_re_adding_same_key_upserts_provenance_not_duplicate(tmp_path):
    db_path = str(tmp_path / "edges.db")
    add_edge("3.2.P.7", "Q1-STABILITY", "family_requires_requirement", _provenance("d1"), db_path=db_path)

    new_prov = _provenance("d2")
    add_edge("3.2.P.7", "Q1-STABILITY", "family_requires_requirement", new_prov, db_path=db_path)

    rows = get_edges(
        src_id="3.2.P.7", dst_id="Q1-STABILITY", edge_type="family_requires_requirement", db_path=db_path
    )
    assert len(rows) == 1
    assert rows[0][3] == new_prov


def test_add_edge_rejects_empty_provenance(tmp_path):
    db_path = str(tmp_path / "edges.db")

    with pytest.raises(ValueError):
        add_edge("3.2.P.7", "Q1-STABILITY", "family_requires_requirement", "", db_path=db_path)

    assert get_edges(db_path=db_path) == []


def test_every_row_from_get_edges_has_nonempty_provenance(tmp_path):
    db_path = str(tmp_path / "edges.db")
    add_edge("a", "b", "t1", _provenance("d1"), db_path=db_path)
    add_edge("c", "d", "t2", _provenance("d2"), db_path=db_path)

    rows = get_edges(db_path=db_path)

    assert len(rows) == 2
    assert all(r[3] for r in rows)
