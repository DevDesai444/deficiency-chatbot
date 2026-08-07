"""Tests for tools.emit_finding: issue_cached_span + emit_structural_finding (Phase 5, Plan 01).

Ruling 1 composition test: proves that a cache-derived span + issue_cached_span bridges the
gap between deterministic detectors (which use fresh RetrievalLedger() objects) and the emit
gate (which requires ledger.was_issued() == True before accepting any span).

The core fix: without issue_cached_span, deterministic detectors in Plans 03/04/05 would fail
because emit gates check ledger.was_issued() BEFORE accepting any span.

Also provides test stubs for emit_structural_finding that Wave-2 plans fill out.
"""
from __future__ import annotations

import pytest

from ingest.anchors import mint_span
from ingest.normalize import normalize
from ingest.serialize import SERIALIZER_VERSION, serialize_document
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import Fault, StructuralAnchor
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_structural_finding, issue_cached_span
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _nt_from_cache(cache: dict) -> NormalizedText:
    return NormalizedText(
        canonical=cache["canonical"], raw_serialized=cache["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
        normalizer_version=cache["normalizer_version"],
        serializer_version=cache["serializer_version"],
    )


# ---------------------------------------------------------------------------
# Ruling 1 composition test — the Wave-1 gate
# ---------------------------------------------------------------------------

def test_issue_cached_span_enables_emit_gate(tmp_path):
    """Ruling 1 composition test: proves cache-derived span passes emit gate end-to-end.

    The core fix: without issue_cached_span, deterministic detectors using fresh
    RetrievalLedger() would fail because emit gates check ledger.was_issued() BEFORE
    accepting any span.

    Proof sequence:
      1. Build a real corpus cache entry
      2. Create a fresh, empty ledger (no prior record_span calls)
      3. Verify ledger starts EMPTY (span not issued)
      4. Call issue_cached_span -> verify returns SpanID (not ToolRejected)
      5. Verify ledger.was_issued() is now True AFTER issue_cached_span
      6. Call emit_structural_finding -> verify returns Fault (not ToolRejected)
    """
    doc_text = (
        "Analytical validation summary. Method validation per ICH Q2(R1). "
        "NMT 0.15% for any single impurity. Accuracy demonstrated at all levels."
    )
    corpus = build_corpus_index(tmp_path, "test-doc", [_block(doc_text)])
    cache = corpus.cached_entry("test-doc")
    assert cache is not None, "corpus cache must exist after build_corpus_index"

    nt = _nt_from_cache(cache)

    # Mint a span pointing to a substring in the cached text
    text_to_cite = "NMT 0.15% for any single impurity"
    start = nt.canonical.index(text_to_cite)
    end = start + len(text_to_cite)
    claim_span_id = mint_span(nt.canonical, start, end, "test-doc", nt.normalizer_version)

    # Fresh, empty ledger — simulates a deterministic detector
    ledger = RetrievalLedger()

    # Step 3: verify ledger starts EMPTY
    assert not ledger.was_issued(claim_span_id), (
        "ledger must start empty — confirms the gap that issue_cached_span bridges"
    )

    # Step 4: call issue_cached_span — this is the Ruling 1 bridge
    result = issue_cached_span(ledger, claim_span_id, nt)
    assert not isinstance(result, ToolRejected), (
        f"issue_cached_span must succeed on a byte-exact cached span, got: {result}"
    )
    assert isinstance(result, SpanID), (
        f"issue_cached_span must return SpanID on success, got: {type(result)}"
    )

    # Step 5: verify ledger now considers span issued (Ruling 1)
    assert ledger.was_issued(claim_span_id), (
        "Ruling 1: after issue_cached_span, ledger.was_issued must be True"
    )

    # Step 6: emit_structural_finding must accept the span (no ToolRejected)
    anchor = StructuralAnchor(
        claim_span_id=claim_span_id,
        basis_span_ids=[claim_span_id],  # simplest valid anchor: claim IS the basis
        relation="EQUALS",
        expected_value="0.15%",
        actual_value="0.18%",
    )
    fault = emit_structural_finding(
        corpus=corpus,
        rule_span_id=None,  # D-STR6: nullable for pure arithmetic checks
        structural_anchor=anchor,
        ledger=ledger,
        title="Impurity limit exceeded",
        detail="Compound B (0.18%) exceeds NMT 0.15% stated in the specification.",
    )
    assert isinstance(fault, Fault), (
        f"Ruling 1: emit_structural_finding must return Fault after issue_cached_span, got {fault}"
    )
    assert fault.leg_tag == "STRUCTURAL", f"leg_tag must be STRUCTURAL, got {fault.leg_tag}"
    assert fault.tier.value == "verified", f"Ruling 2: tier must be 'verified', got {fault.tier}"
    assert fault.evidence_class.value == "code_verified", (
        f"Ruling 2: evidence_class must be 'code_verified', got {fault.evidence_class}"
    )
    assert fault.dedup_key is not None, "dedup_key must be set (D-CON1)"
    assert fault.confidence_tier is not None, "confidence_tier must be set (D-ENV1)"


def test_issue_cached_span_rejects_hash_mismatch(tmp_path):
    """issue_cached_span returns ToolRejected when span hash does not match the stored text."""
    from ingest.anchors import short_hash

    corpus = build_corpus_index(tmp_path, "test-doc", [_block("Real submission text here.")])
    cache = corpus.cached_entry("test-doc")
    nt = _nt_from_cache(cache)

    start = nt.canonical.index("Real")
    end = start + len("Real submission")
    # Create a span with a WRONG hash (tampered)
    tampered_span = SpanID(
        doc_id="test-doc", start=start, end=end,
        hash=short_hash("completely different text", nt.normalizer_version),
    )
    ledger = RetrievalLedger()
    result = issue_cached_span(ledger, tampered_span, nt)
    assert isinstance(result, ToolRejected), (
        "issue_cached_span must return ToolRejected on hash mismatch"
    )
    assert result.reason_code == "not_byte_exact", (
        f"reason_code must be 'not_byte_exact', got {result.reason_code}"
    )
    # Verify ledger was NOT updated after rejection
    assert not ledger.was_issued(tampered_span), (
        "ledger must not record a span that failed byte-exact validation"
    )


def test_emit_structural_finding_null_rule_span_accepted(tmp_path):
    """D-STR6: emit_structural_finding accepts rule_span_id=None for pure arithmetic checks."""
    doc_text = "Stability data. Total impurities 0.12%. Component A 0.18%. Sum exceeds total."
    corpus = build_corpus_index(tmp_path, "test-doc", [_block(doc_text)])
    cache = corpus.cached_entry("test-doc")
    nt = _nt_from_cache(cache)

    claim_text = "Total impurities 0.12%"
    start = nt.canonical.index("Total impurities")
    end = start + len(claim_text)
    claim_span = mint_span(nt.canonical, start, end, "test-doc", nt.normalizer_version)

    ledger = RetrievalLedger()
    issue_cached_span(ledger, claim_span, nt)

    anchor = StructuralAnchor(
        claim_span_id=claim_span,
        basis_span_ids=[claim_span],
        relation="SUM",
        expected_value="0.28%",
        actual_value="0.12%",
    )
    fault = emit_structural_finding(
        corpus=corpus,
        rule_span_id=None,  # D-STR6: pure aggregate check, no rule span
        structural_anchor=anchor,
        ledger=ledger,
    )
    assert isinstance(fault, Fault), (
        f"D-STR6: emit_structural_finding must succeed with rule_span_id=None, got {fault}"
    )


def test_emit_structural_finding_empty_basis_rejected(tmp_path):
    """emit_structural_finding returns ToolRejected when no basis spans pass validation."""
    corpus = build_corpus_index(tmp_path, "test-doc", [_block("Some text for testing.")])
    cache = corpus.cached_entry("test-doc")
    nt = _nt_from_cache(cache)

    text = "Some text"
    start = nt.canonical.index(text)
    end = start + len(text)
    claim_span = mint_span(nt.canonical, start, end, "test-doc", nt.normalizer_version)

    ledger = RetrievalLedger()
    issue_cached_span(ledger, claim_span, nt)

    # Anchor with NO basis spans
    anchor = StructuralAnchor(
        claim_span_id=claim_span,
        basis_span_ids=[],  # empty -> unanchored_structural
        relation="MAX",
        expected_value="0.18%",
        actual_value="0.12%",
    )
    result = emit_structural_finding(
        corpus=corpus,
        rule_span_id=None,
        structural_anchor=anchor,
        ledger=ledger,
    )
    assert isinstance(result, ToolRejected), (
        "emit_structural_finding must return ToolRejected with no basis spans"
    )
    assert result.reason_code == "unanchored_structural", (
        f"reason_code must be 'unanchored_structural', got {result.reason_code}"
    )


# ---------------------------------------------------------------------------
# Gate tests for Wave-2 (Plan 05-03)
# ---------------------------------------------------------------------------

def test_fabricated_claim_span_rejected(tmp_path):
    """A SpanID fabricated for a non-existent doc must be rejected by emit_structural_finding.

    Tests the 'wrong_store' path: claim_span_id.doc_id does not resolve in the corpus
    (corpus.cached_entry returns None). The emit gate must return ToolRejected.
    """
    from ingest.anchors import short_hash
    from ingest.normalize import NORMALIZER_VERSION

    # Build a real corpus with a known doc_id
    corpus = build_corpus_index(tmp_path, "real-doc", [_block("Real corpus text.")])

    # Fabricate a span for a doc_id that does NOT exist in the corpus
    fabricated_span = SpanID(
        doc_id="nonexistent-doc",  # not in corpus
        start=0,
        end=4,
        hash=short_hash("fake", NORMALIZER_VERSION),
    )

    ledger = RetrievalLedger()
    # Do NOT call issue_cached_span — span is both fabricated and unissued

    anchor = StructuralAnchor(
        claim_span_id=fabricated_span,
        basis_span_ids=[fabricated_span],
        relation="SUM",
        expected_value="0.28%",
        actual_value="0.12%",
    )
    result = emit_structural_finding(
        corpus=corpus,
        rule_span_id=None,
        structural_anchor=anchor,
        ledger=ledger,
    )
    assert isinstance(result, ToolRejected), (
        f"Fabricated span for non-existent doc must be ToolRejected, got {type(result)}"
    )
    assert result.reason_code == "wrong_store", (
        f"reason_code must be 'wrong_store', got {result.reason_code!r}"
    )


def test_merged_cell_dedup_abstains(tmp_path):
    """All basis_span_ids resolve to the same span after dedup -> ToolRejected (unanchored_structural).

    Pitfall 2 (merged cells): when multiple basis span_ids all have the same
    (doc_id, start, end) — as happens with merged table cells — emit_structural_finding
    deduplicates them to a single span and requires >= 1 independent basis span.
    If after deduplication there are zero issued basis spans, the emit gate returns
    ToolRejected(reason_code='unanchored_structural').

    This test provides an anchor with basis_span_ids=[] (empty after dedup):
    """
    doc_text = "Stability data table with merged cells."
    corpus = build_corpus_index(tmp_path, "merged-doc", [_block(doc_text)])
    cache = corpus.cached_entry("merged-doc")
    nt = _nt_from_cache(cache)

    claim_text = "Stability data"
    start = nt.canonical.index(claim_text)
    end = start + len(claim_text)
    claim_span = mint_span(nt.canonical, start, end, "merged-doc", nt.normalizer_version)

    ledger = RetrievalLedger()
    issue_cached_span(ledger, claim_span, nt)

    # Empty basis_span_ids -> no independent basis after dedup -> unanchored_structural
    anchor = StructuralAnchor(
        claim_span_id=claim_span,
        basis_span_ids=[],  # empty = all merged to zero independent cells
        relation="SUM",
        expected_value="0.28%",
        actual_value="0.12%",
    )
    result = emit_structural_finding(
        corpus=corpus,
        rule_span_id=None,
        structural_anchor=anchor,
        ledger=ledger,
    )
    assert isinstance(result, ToolRejected), (
        f"Empty basis after dedup must return ToolRejected, got {type(result)}"
    )
    assert result.reason_code == "unanchored_structural", (
        f"reason_code must be 'unanchored_structural', got {result.reason_code!r}"
    )
