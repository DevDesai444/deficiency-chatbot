"""Tests for follow_reference (Phase 2 Plan 01 Task 3, D-FR)."""
from __future__ import annotations

from schemas.documents import SpanID
from tests.tools.conftest import build_corpus_index
from tools.follow_reference import follow_reference

_PENDING = "cross_document_resolution_pending_phase_4"


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def test_same_doc_resolves_cross_doc_typed_stub(tmp_path, fresh_ledger):
    body = "First Heading text here. Some content. Second Heading text here. More content."
    corpus = build_corpus_index(
        tmp_path, "d1", [_block(body)],
        outline_headings=["First Heading text here.", "Second Heading text here."],
    )

    # same-document resolution: case-insensitive substring match against the outline label
    resolved = follow_reference(corpus, "d1", "second heading", fresh_ledger)
    assert resolved["doc_id"] == "d1"
    assert resolved["resolved"] is True
    assert resolved["label"] == "Second Heading text here."
    assert "span_id" in resolved
    span = SpanID.model_validate(resolved["span_id"])
    assert fresh_ledger.was_issued(span) is True   # resolved span-ID is recorded, citable later

    # a reference that does not match anything in THIS doc's outline -> typed pending stub
    unresolved = follow_reference(
        corpus, "d1", "Nonexistent Section Nowhere In This Doc", fresh_ledger,
    )
    assert unresolved == {
        "doc_id": "d1",
        "ref_text": "Nonexistent Section Nowhere In This Doc",
        "status": _PENDING,
    }
    assert unresolved != {}
    assert unresolved is not None

    # a doc_id with no cached substrate at all (the "genuinely cross-document" case) -> the
    # SAME typed stub, never a silent empty/None result
    cross_doc = follow_reference(corpus, "unknown-doc-id", "anything at all", fresh_ledger)
    assert cross_doc["status"] == _PENDING
    assert cross_doc["doc_id"] == "unknown-doc-id"
    assert cross_doc != {}
    assert cross_doc is not None
