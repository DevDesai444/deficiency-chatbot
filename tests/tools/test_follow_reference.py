"""Tests for follow_reference (Phase 2 Plan 01 Task 3, D-FR; Phase 5 Plan 07 B4 fix).

Wave 5 B4 fix: follow_reference no longer returns _CROSS_DOC_PENDING.
  - Same-document outline resolution is unchanged.
  - Unresolved references return {"status": "UNRESOLVED_REF"} (NOT the sentinel).
  - Cross-doc edges in the edges DB return {"status": "resolved_cross_doc"}.
  - The _CROSS_DOC_PENDING constant is retained in the module for Plan-06 run.py
    back-compat import (so run.py can probe whether cross-doc is wired), but is
    NEVER returned by any follow_reference code path.

Ruling 7 (db_path): ALL follow_reference calls in this file pass db_path= explicitly.
B4 integration test: builds two-doc corpus via conftest helpers (offline, no embedding
model required), plants an edge via rulebook.edges.add_edge, confirms
follow_reference(db_path=...) resolves to "resolved_cross_doc".
"""
from __future__ import annotations

import inspect
import json

import pytest

from rulebook.edges import add_edge, get_edges
from schemas.documents import SpanID
from tests.tools.conftest import build_corpus_index
from tools.follow_reference import _CROSS_DOC_PENDING, follow_reference

# Sentinel string (retained in module for run.py probe; NEVER returned at runtime)
_PENDING = _CROSS_DOC_PENDING


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


# ---------------------------------------------------------------------------
# Existing test: updated for Wave 5 (UNRESOLVED_REF replaces _CROSS_DOC_PENDING)
# ---------------------------------------------------------------------------

def test_same_doc_resolves_and_unresolved_returns_unresolved_ref(tmp_path, fresh_ledger):
    """Same-doc resolution still works; unresolved → UNRESOLVED_REF (not the sentinel).

    Wave 5 update: the third assertion (cross-doc unresolved) now expects
    {"status": "UNRESOLVED_REF"} instead of {"status": _CROSS_DOC_PENDING}.

    Ruling 7: all follow_reference calls pass db_path= explicitly.
    """
    db_path = str(tmp_path / "edges_empty.db")
    body = "First Heading text here. Some content. Second Heading text here. More content."
    corpus = build_corpus_index(
        tmp_path, "d1", [_block(body)],
        outline_headings=["First Heading text here.", "Second Heading text here."],
    )

    # same-document resolution: case-insensitive substring match against the outline label
    resolved = follow_reference(corpus, "d1", "second heading", fresh_ledger, db_path=db_path)
    assert resolved["doc_id"] == "d1"
    assert resolved["resolved"] is True
    assert resolved["label"] == "Second Heading text here."
    assert "span_id" in resolved
    span = SpanID.model_validate(resolved["span_id"])
    assert fresh_ledger.was_issued(span) is True   # resolved span-ID is recorded, citable later

    # a reference that does not match anything in THIS doc's outline -> UNRESOLVED_REF
    # (Wave 5 B4 fix: was _CROSS_DOC_PENDING, now UNRESOLVED_REF)
    unresolved = follow_reference(
        corpus, "d1", "Nonexistent Section Nowhere In This Doc", fresh_ledger, db_path=db_path,
    )
    assert unresolved["status"] == "UNRESOLVED_REF"
    assert unresolved["doc_id"] == "d1"
    assert unresolved != {}
    assert unresolved is not None

    # a doc_id with no cached substrate at all (the "genuinely cross-document" case) ->
    # UNRESOLVED_REF (never a silent empty/None, never the pending sentinel)
    cross_doc = follow_reference(corpus, "unknown-doc-id", "anything at all", fresh_ledger, db_path=db_path)
    assert cross_doc["status"] == "UNRESOLVED_REF"
    assert cross_doc["doc_id"] == "unknown-doc-id"
    assert cross_doc != {}
    assert cross_doc is not None


# ---------------------------------------------------------------------------
# Ruling 7 enforcement: db_path parameter exists in signature
# ---------------------------------------------------------------------------

def test_follow_reference_db_path_parameter_exists():
    """Ruling 7: db_path is an explicit named parameter in follow_reference's signature."""
    sig = inspect.signature(follow_reference)
    params = list(sig.parameters.keys())
    assert "db_path" in params, (
        f"Ruling 7: 'db_path' not in follow_reference signature. Got: {params}"
    )
    assert "span_start" in params, (
        f"B4 fix: 'span_start' not in follow_reference signature. Got: {params}"
    )
    # db_path must have a default (so existing call sites need no modification)
    db_path_param = sig.parameters["db_path"]
    assert db_path_param.default is not inspect.Parameter.empty, (
        "Ruling 7: db_path must have a default value so existing call sites remain valid"
    )
    # span_start must have a default of None
    span_start_param = sig.parameters["span_start"]
    assert span_start_param.default is None, (
        "B4: span_start must default to None"
    )


# ---------------------------------------------------------------------------
# Ruling A-ii: sentinel NEVER returned across resolvable / unresolvable / not-ingested
# ---------------------------------------------------------------------------

def test_follow_reference_sentinel_never_returned(tmp_path, fresh_ledger):
    """Ruling A-ii: _CROSS_DOC_PENDING NEVER appears in follow_reference output.

    Exercises three cases:
      1. Same-doc resolvable reference → resolved dict
      2. Same-doc unresolvable reference → UNRESOLVED_REF dict
      3. doc_id not ingested at all → UNRESOLVED_REF dict

    In ALL cases, the result must not contain the Phase-4 sentinel string.
    Ruling 7: all calls pass db_path= explicitly.
    """
    db_path = str(tmp_path / "edges_sentinel_test.db")
    body = "Introduction content. Section 2.3 Analysis. Conclusion."
    corpus = build_corpus_index(
        tmp_path, "sentinel_doc", [_block(body)],
        outline_headings=["Introduction content.", "Section 2.3 Analysis."],
    )

    def _assert_no_sentinel(result: dict, case: str) -> None:
        assert _PENDING not in str(result), (
            f"B4 fail ({case}): Phase-4 sentinel '{_PENDING}' found in result {result!r}. "
            "follow_reference must never return _CROSS_DOC_PENDING."
        )

    # Case 1: Resolvable same-doc reference
    result1 = follow_reference(corpus, "sentinel_doc", "section 2.3", fresh_ledger, db_path=db_path)
    _assert_no_sentinel(result1, "resolvable")
    assert result1.get("resolved") is True

    # Case 2: Unresolvable same-doc reference (not in outline)
    result2 = follow_reference(corpus, "sentinel_doc", "Section 99.99 Nonexistent", fresh_ledger, db_path=db_path)
    _assert_no_sentinel(result2, "unresolvable")
    assert result2["status"] == "UNRESOLVED_REF"

    # Case 3: doc_id not ingested (unknown doc)
    result3 = follow_reference(corpus, "not_ingested_doc_id", "anything", fresh_ledger, db_path=db_path)
    _assert_no_sentinel(result3, "not_ingested")
    assert result3["status"] == "UNRESOLVED_REF"


# ---------------------------------------------------------------------------
# B4: cross-doc edge resolution test (no mocks, offline)
# ---------------------------------------------------------------------------

def test_follow_reference_resolves_planted_cross_doc(tmp_path, fresh_ledger):
    """B4 integration test + Ruling 7: real cross-doc edge lookup.

    Builds two test docs offline (no embedding model needed):
      - doc_src: contains a reference to doc_dst
      - doc_dst: the target document

    Plants an edge from doc_src:0 → doc_dst:0 via add_edge (same key format as
    references.py: src_id = '{doc_id}:{span.start}').

    Then calls follow_reference(doc_id='doc_src', span_start=0, db_path=...) and
    asserts status == 'resolved_cross_doc'.

    This tests the REAL B4 edge-lookup code path in follow_reference without mocks.
    Ruling 7: db_path is passed explicitly.
    """
    db_path = str(tmp_path / "edges_b4.db")

    # Build two offline docs via conftest helper (no PDF/DOCX file I/O, no embeddings)
    src_body = "Quality Overview Summary. See doc_dst for Module details. NMT 0.18%."
    dst_body = "Module 3.2 details. Active substance specification table. Limit: 0.15%."
    corpus_src = build_corpus_index(
        tmp_path, "doc_src", [_block(src_body)], filename="doc_src.docx",
    )
    corpus_dst = build_corpus_index(
        tmp_path, "doc_dst", [_block(dst_body)], filename="doc_dst.pdf",
    )

    # Plant an edge: doc_src:0 → doc_dst:0 (matches the references.py src_id format)
    # provenance_span_id = JSON serialized SpanID dict (as references.py writes it)
    prov = json.dumps({"doc_id": "doc_src", "start": 0, "end": 80,
                       "normalizer_version": "v1", "text_hash": "abc"})
    add_edge(
        src_id="doc_src:0",
        dst_id="doc_dst:0",
        edge_type="textual_ref",
        provenance_span_id=prov,
        db_path=db_path,
    )

    # Verify the edge was written
    edges = get_edges(src_id="doc_src:0", db_path=db_path)
    assert edges, "Edge was not written to the DB"
    assert edges[0][1] == "doc_dst:0", f"dst_id mismatch: {edges[0][1]}"

    # follow_reference with span_start=0 must resolve to resolved_cross_doc
    result = follow_reference(
        corpus=corpus_src,
        doc_id="doc_src",
        ref_text="doc_dst Module details",
        ledger=fresh_ledger,
        span_start=0,          # Ruling 7: explicit span_start for exact edge-key lookup
        db_path=db_path,       # Ruling 7: explicit db_path
    )
    assert result["status"] == "resolved_cross_doc", (
        f"B4 fix: expected 'resolved_cross_doc', got {result['status']!r}. "
        "follow_reference must resolve cross-doc edges via the DB."
    )
    assert result.get("doc_id") == "doc_dst", (
        f"B4 fix: resolved doc_id should be 'doc_dst', got {result.get('doc_id')!r}"
    )
    assert _PENDING not in str(result), (
        f"B4 fix: Phase-4 sentinel must not appear in resolved result: {result!r}"
    )


def test_follow_reference_returns_unresolved_for_missing_ref(tmp_path, fresh_ledger):
    """Unresolved cross-doc reference (no matching edge in DB) → UNRESOLVED_REF.

    Not the Phase-4 sentinel, not a silent empty dict — a real typed status.
    Ruling 7: db_path is passed explicitly.
    """
    db_path = str(tmp_path / "edges_empty_missing.db")
    body = "Some content without matching outline entries."
    corpus = build_corpus_index(tmp_path, "doc_a", [_block(body)])

    result = follow_reference(
        corpus=corpus,
        doc_id="doc_a",
        ref_text="Module 3.2.P.5 Nonexistent",
        ledger=fresh_ledger,
        span_start=0,
        db_path=db_path,    # empty DB — no edges
    )
    assert result["status"] == "UNRESOLVED_REF", (
        f"Expected UNRESOLVED_REF for missing edge, got {result['status']!r}"
    )
    assert result["doc_id"] == "doc_a"
    assert _PENDING not in str(result), (
        "Phase-4 sentinel must NOT appear when reference is unresolved"
    )
    assert result != {}
    assert result is not None
