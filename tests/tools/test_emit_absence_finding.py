"""Tests for src/tools/emit_finding.py::emit_absence_finding -- the absence-typed grounding
gate (D-GATE1/D-GATE2, Phase 4 Plan 04-02).

An absence finding has no single submission text span; its submission half is a typed
CoverageAbsenceAnchor (the enumerate inputs + sub-threshold retrieval hits + manifest span-IDs,
so the Phase-7 verifier RE-RUNS the negative). The RULE half stays byte-exact and UNCHANGED
(D-EF1). When a narrative-claim CORPUS span exists (D-ABS4 / mvr / MS-03) it is ALSO re-opened
byte-exact via the SAME open_span path.

Like tests/tools/test_emit_finding.py, every test drives real Phase-1/Plan-02 primitives
end-to-end, entirely offline (D-RB6) via tmp_path-scoped corpus + rulebook stores.

Proves (plan 04-02 Task 2):
  (a) real ledger-issued rule span + re-derivable anchor -> Fault(verdict==GAP, absence_anchor set,
      submission_span_id is None);
  (b) a fabricated (never-issued or hash-drifted) claim_span_id is REJECTED with half="submission"
      -- the fabricated anchor CANNOT be emitted;
  (c) rule_span_id=None -> reason_code="no_rule_citation", half="rule";
  (d) an anchor with empty requirement_id -> reason_code="unanchored_absence".
"""
from __future__ import annotations

from ingest.anchors import mint_span, short_hash
from rulebook.store import write_chunk
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import (
    ComplianceVerdict,
    CoverageAbsenceAnchor,
    EvidenceClass,
    Fault,
    RetrievalHit,
)
from tests.rulebook.conftest import fixture_chunk
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_absence_finding
from tools.errors import ToolRejected


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _nt_from_cache(cache: dict) -> NormalizedText:
    return NormalizedText(
        canonical=cache["canonical"], raw_serialized=cache["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
        normalizer_version=cache["normalizer_version"], serializer_version=cache["serializer_version"],
    )


def _build_rule(
    tmp_path, doc_id="21-cfr-211.166", citation="21 CFR 211.166",
    text="Written stability testing procedures shall be established.",
):
    """Persist a real rulebook chunk (Plan 02-02 fixture_chunk + write_chunk) and return
    (chunk, cache_dir), tmp_path-scoped for D-RB6 offline isolation."""
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path, doc_id=doc_id, citation=citation, text=text)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)
    return chunk, cache_dir


def _valid_anchor(requirement_id="Q2-SPECIFICITY", family="3.2.S.4.3", claim_span_id=None):
    return CoverageAbsenceAnchor(
        profile=["drug_substance"], family=family, requirement_id=requirement_id,
        threshold=0.2,
        sub_threshold_hits=[RetrievalHit(span_id=SpanID(doc_id="sub-doc", start=0, end=5, hash="deadbeef"), score=0.11)],
        manifest_span_ids=[SpanID(doc_id="sub-doc", start=0, end=5, hash="deadbeef")],
        claim_span_id=claim_span_id,
    )


# --- (a) success path: re-derivable anchor + byte-exact rule half -> Fault(GAP) ---------------


def test_absence_success_emits_gap_fault_with_anchor_and_no_submission_span(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Some unrelated submission text.")])
    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    anchor = _valid_anchor()
    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rule_citation=rule_chunk.citation, title="Absent specificity data",
        detail="No specificity data was found for the required family.",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, Fault)
    assert result.verdict is ComplianceVerdict.GAP
    assert result.evidence_class == EvidenceClass.CHECKLIST
    assert result.absence_anchor == anchor
    assert result.submission_span_id is None
    assert result.rule_span_id == rule_chunk.span
    assert rule_chunk.citation in result.guidance_refs
    assert "Q2-SPECIFICITY" in result.guidance_refs


def test_absence_success_with_valid_claim_span_reopens_byte_exact(tmp_path, fresh_ledger):
    """D-ABS4: when a narrative-claim CORPUS span exists (mvr / MS-03) it is ALSO attached and
    re-opened byte-exact via the SAME open_span path emit_finding uses."""
    text = "The specificity of the analytical method was fully demonstrated."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("fully demonstrated")
    end = start + len("fully demonstrated")
    claim_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(claim_span)  # legitimately retrieved via search_corpus

    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    anchor = _valid_anchor(claim_span_id=claim_span)
    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, Fault)
    assert result.verdict is ComplianceVerdict.GAP
    assert result.absence_anchor.claim_span_id == claim_span


# --- (b) the central proof: a fabricated claim span CANNOT be emitted -------------------------


def test_absence_fabricated_claim_span_not_byte_exact_cannot_be_emitted(tmp_path, fresh_ledger):
    text = "The assay method was validated using linear regression across five levels."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("linear regression")
    end = start + len("linear regression")
    real_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(real_span)  # as if legitimately retrieved

    # SAME (doc_id,start,end) as the real, issued span, but hash over an ALTERED substring.
    tampered_claim = SpanID(
        doc_id="sub-doc", start=start, end=end,
        hash=short_hash("linear regressiom", nt.normalizer_version),
    )

    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    anchor = _valid_anchor(claim_span_id=tampered_claim)
    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    # Proof of REJECTION, not "emitted then caught": assert the return TYPE.
    assert isinstance(result, ToolRejected)
    assert not isinstance(result, Fault)
    assert result.half == "submission"
    assert result.reason_code in {"not_retrieved_this_session", "not_byte_exact"}


def test_absence_never_issued_claim_span_is_rejected(tmp_path, fresh_ledger):
    text = "Container closure integrity was confirmed by dye ingress testing."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("dye ingress testing")
    end = start + len("dye ingress testing")
    # byte-exact but never ledger.record_span-ed
    never_issued = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)

    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    anchor = _valid_anchor(claim_span_id=never_issued)
    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("not_retrieved_this_session", "submission")


# --- (c) the rule half stays byte-exact: no rule citation --------------------------------------


def test_absence_no_rule_citation_rejected(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Unrelated text.")])
    anchor = _valid_anchor()

    result = emit_absence_finding(
        corpus=corpus, rule_span_id=None, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("no_rule_citation", "rule")


def test_absence_rule_span_not_retrieved_this_session(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Unrelated text.")])
    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    # rule span byte-exact + in store, but NEVER issued this session
    anchor = _valid_anchor()

    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("not_retrieved_this_session", "rule")


def test_absence_rule_span_wrong_store_rejected(tmp_path, fresh_ledger):
    """A rule span whose doc_id does not resolve in the RULEBOOK store -> wrong_store, half=rule."""
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Some text about forced degradation.")])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))
    start = nt.canonical.index("forced degradation")
    end = start + len("forced degradation")
    corpus_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(corpus_span)

    empty_rulebook_cache_dir = str(tmp_path / "empty_rulebook_cache")
    anchor = _valid_anchor()

    result = emit_absence_finding(
        corpus=corpus, rule_span_id=corpus_span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=empty_rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("wrong_store", "rule")


def test_absence_rule_span_not_byte_exact_rejected(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Unrelated text.")])
    rule_chunk, rulebook_cache_dir = _build_rule(
        tmp_path, text="Laboratory controls shall include scientifically sound specifications.",
    )
    fresh_ledger.record_span(rule_chunk.span)
    tampered_rule_span = SpanID(
        doc_id=rule_chunk.span.doc_id, start=rule_chunk.span.start, end=rule_chunk.span.end,
        hash=short_hash("tampered rule text", "not-the-rule-normalizer"),
    )
    anchor = _valid_anchor()

    result = emit_absence_finding(
        corpus=corpus, rule_span_id=tampered_rule_span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("not_byte_exact", "rule")


# --- (d) the negative must be re-derivable: unanchored_absence --------------------------------


def test_absence_unanchored_empty_requirement_id_rejected(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Unrelated text.")])
    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    anchor = _valid_anchor(requirement_id="")  # missing the input needed to re-run the negative

    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("unanchored_absence", "submission")


def test_absence_unanchored_empty_family_rejected(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Unrelated text.")])
    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    anchor = _valid_anchor(family="")

    result = emit_absence_finding(
        corpus=corpus, rule_span_id=rule_chunk.span, absence_anchor=anchor,
        ledger=fresh_ledger, requirement_id="Q2-SPECIFICITY",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert (result.reason_code, result.half) == ("unanchored_absence", "submission")
