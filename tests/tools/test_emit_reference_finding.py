"""Tests for tools.emit_finding.emit_reference_finding (Phase 5, Plan 01).

emit_reference_finding is directly importable (added in Plan 01 Task 1a), so these tests
use direct imports rather than pytest.importorskip. Test bodies that need Wave-2
rulebook.references logic are skipped; the import tests run immediately.

Proves (Wave-0):
  (a) emit_reference_finding is importable and callable with correct signature
  (b) a valid corpus span + ReferenceAnchor produces Fault(leg_tag='REFERENCE',
      tier=Tier.VERIFIED, evidence_class=EvidenceClass.CODE_VERIFIED) — Ruling 2
  (c) unanchored_reference: src_span with hash mismatch returns ToolRejected
"""
from __future__ import annotations

import pytest

from ingest.anchors import mint_span, short_hash
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import EvidenceClass, Fault, ReferenceAnchor, Tier
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_reference_finding
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
# (a) import check
# ---------------------------------------------------------------------------

def test_emit_reference_finding_importable():
    """emit_reference_finding must be importable and callable (Plan 01 Task 1a)."""
    assert callable(emit_reference_finding), (
        "emit_reference_finding must be importable from tools.emit_finding"
    )


# ---------------------------------------------------------------------------
# (b) full candidate path: valid src span -> Fault with correct enum values
# ---------------------------------------------------------------------------

def test_reference_finding_full_candidate(tmp_path):
    """Ruling 2: emit_reference_finding returns Fault with Tier.VERIFIED + CODE_VERIFIED."""
    doc_text = (
        "The analytical method per ICH Q2(R1) demonstrates linearity. "
        "See Analytical Procedures Table 1 for impurity results (NMT 0.15%)."
    )
    corpus = build_corpus_index(tmp_path, "src-doc", [_block(doc_text)])
    cache = corpus.cached_entry("src-doc")
    nt = _nt_from_cache(cache)

    src_text = "See Analytical Procedures Table 1"
    start = nt.canonical.index(src_text)
    end = start + len(src_text)
    src_span = mint_span(nt.canonical, start, end, "src-doc", nt.normalizer_version)

    ledger = RetrievalLedger()
    anchor = ReferenceAnchor(
        src_span_id=src_span,
        dst_span_id=None,
        edge_type="textual_ref",
        anomaly="ABSENT_TARGET",
    )
    result = emit_reference_finding(
        corpus=corpus,
        reference_anchor=anchor,
        ledger=ledger,
        title="Referenced target absent from submission",
        detail="The referenced 'Table 1 in Analytical Procedures' was not found in the corpus.",
    )
    assert isinstance(result, Fault), (
        f"emit_reference_finding must return Fault on valid src_span, got: {result}"
    )
    assert result.leg_tag == "REFERENCE", f"leg_tag must be 'REFERENCE', got {result.leg_tag}"
    assert result.tier == Tier.VERIFIED, (
        f"Ruling 2: tier must be Tier.VERIFIED (str 'verified'), got {result.tier}"
    )
    assert result.evidence_class == EvidenceClass.CODE_VERIFIED, (
        f"Ruling 2: evidence_class must be CODE_VERIFIED, got {result.evidence_class}"
    )
    assert result.dedup_key is not None, "D-CON1: dedup_key must be set"
    assert result.confidence_tier is not None, "D-ENV1: confidence_tier must be set"
    assert result.reference_anchor is not None, "reference_anchor must be attached"


# ---------------------------------------------------------------------------
# (c) unanchored_reference: hash-mismatched src_span rejected
# ---------------------------------------------------------------------------

def test_reference_finding_unanchored_rejected(tmp_path):
    """unanchored_reference: src_span with hash mismatch returns ToolRejected."""
    doc_text = "Stability results referenced from Module 3.2.P.8.3."
    corpus = build_corpus_index(tmp_path, "src-doc", [_block(doc_text)])
    cache = corpus.cached_entry("src-doc")
    nt = _nt_from_cache(cache)

    start = nt.canonical.index("Module 3.2")
    end = start + len("Module 3.2")
    # Create span with WRONG hash
    tampered_span = SpanID(
        doc_id="src-doc", start=start, end=end,
        hash=short_hash("completely wrong text", nt.normalizer_version),
    )
    ledger = RetrievalLedger()
    anchor = ReferenceAnchor(
        src_span_id=tampered_span,
        dst_span_id=None,
        edge_type="textual_ref",
        anomaly="UNRESOLVED_REF",
    )
    result = emit_reference_finding(
        corpus=corpus,
        reference_anchor=anchor,
        ledger=ledger,
    )
    assert isinstance(result, ToolRejected), (
        "emit_reference_finding must return ToolRejected on hash-mismatch src_span"
    )
    assert result.reason_code == "unanchored_reference", (
        f"reason_code must be 'unanchored_reference', got {result.reason_code}"
    )


def test_reference_finding_value_contradiction_low_confidence(tmp_path):
    """D-REF3: VALUE_CONTRADICTION with scoping_confidence='low' propagates to Fault."""
    doc_text = "NMT 0.15% specification for single impurities as validated."
    corpus = build_corpus_index(tmp_path, "doc-a", [_block(doc_text)])
    cache = corpus.cached_entry("doc-a")
    nt = _nt_from_cache(cache)

    start = nt.canonical.index("NMT 0.15%")
    end = start + len("NMT 0.15%")
    src_span = mint_span(nt.canonical, start, end, "doc-a", nt.normalizer_version)

    ledger = RetrievalLedger()
    anchor = ReferenceAnchor(
        src_span_id=src_span,
        dst_span_id=None,
        edge_type="value_crossref",
        anomaly="VALUE_CONTRADICTION",
        scoping_confidence="low",  # D-REF3: label-match only, no edge
    )
    result = emit_reference_finding(
        corpus=corpus,
        reference_anchor=anchor,
        ledger=ledger,
    )
    assert isinstance(result, Fault), (
        f"D-REF3: low-confidence VALUE_CONTRADICTION must still emit Fault, got {result}"
    )
    assert result.confidence_tier == "low", (
        f"D-REF3: scoping_confidence='low' must propagate to Fault.confidence_tier, got {result.confidence_tier}"
    )
