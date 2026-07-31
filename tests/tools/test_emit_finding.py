"""Tests for src/tools/emit_finding.py -- the dual byte-exact grounding gate (TOOLS-03, D-EF1,
Phase 2 Plan 05). Every test drives real Phase-1/Plan-02-01/02-02 primitives (mint_span,
open_span, build_corpus_index, fixture_chunk/write_chunk) end-to-end, entirely offline
(D-RB6) via tmp_path-scoped corpus + rulebook stores -- never a hand-rolled fake.

One behavior, one honestly-named test (plan-checker Blocker 1): this file replaces the
prior single combined test (test_rejects_not_unique_and_not_in_ledger_and_no_rule_citation,
which never actually tested uniqueness) with distinctly-named tests whose names accurately
map to what they check.
"""
from __future__ import annotations

from ingest.anchors import mint_span, open_span, short_hash
from rulebook.store import write_chunk
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import EvidenceClass, Fault
from tests.rulebook.conftest import fixture_chunk
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_finding
from tools.errors import ToolRejected


def _block(text, page=1, order=0):
    """A minimal body-block dict; mirrors tests/tools/test_contracts.py's helper."""
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
    (chunk, cache_dir). `cache_dir` is tmp_path-scoped -- feed it to emit_finding's
    rulebook_cache_dir so the rule span resolves against an isolated fixture store, never
    the shared data/ directory (D-RB6 offline test isolation)."""
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path, doc_id=doc_id, citation=citation, text=text)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)
    return chunk, cache_dir


# --- the central proof: fabrication is REJECTED, never emitted-then-caught -------------------


def test_fabricated_quote_cannot_be_emitted(tmp_path, fresh_ledger):
    text = "The assay method was validated using linear regression across five concentration levels."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("linear regression")
    end = start + len("linear regression")
    real_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(real_span)  # as if legitimately retrieved via get_section

    # Simulate the model retyping/paraphrasing the quote: SAME (doc_id,start,end) as the
    # real, issued span, but `hash` computed over an ALTERED substring (one character
    # changed, same length -- 'n' -> 'm').
    altered_text = "linear regressiom"
    tampered_span = SpanID(
        doc_id="sub-doc", start=start, end=end,
        hash=short_hash(altered_text, nt.normalizer_version),
    )

    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    result = emit_finding(
        corpus=corpus, submission_span_id=tampered_span, rule_span_id=rule_chunk.span,
        ledger=fresh_ledger, verdict="fails", rulebook_cache_dir=rulebook_cache_dir,
    )

    # Proof of REJECTION, not "emitted then caught": assert the return TYPE, not a
    # side-channel flag -- no Fault object is ever constructed on this path.
    assert isinstance(result, ToolRejected)
    assert result.reason_code == "not_byte_exact"
    assert not isinstance(result, Fault)


# --- the five independently-tested D-EF1 rejection paths -------------------------------------


def test_rejects_not_retrieved_this_session(tmp_path, fresh_ledger):
    text = "Container closure integrity was confirmed by dye ingress testing."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("dye ingress testing")
    end = start + len("dye ingress testing")
    # A syntactically valid, byte-exact span -- but never ledger.record_span-ed, i.e. the
    # model never actually retrieved it this session.
    never_issued_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)

    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    result = emit_finding(
        corpus=corpus, submission_span_id=never_issued_span, rule_span_id=rule_chunk.span,
        ledger=fresh_ledger, verdict="fails", rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert result.reason_code == "not_retrieved_this_session"


def test_rejects_no_rule_citation(tmp_path, fresh_ledger):
    text = "Batch records were reviewed for completeness prior to release."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("Batch records")
    end = start + len("Batch records")
    span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(span)

    result = emit_finding(
        corpus=corpus, submission_span_id=span, rule_span_id=None,
        ledger=fresh_ledger, verdict="fails",
    )

    assert isinstance(result, ToolRejected)
    assert result.reason_code == "no_rule_citation"


def test_rejects_wrong_store_rule_span_from_corpus(tmp_path, fresh_ledger):
    text = "The excipient compatibility study used forced degradation conditions."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("forced degradation")
    end = start + len("forced degradation")
    corpus_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(corpus_span)

    empty_rulebook_cache_dir = str(tmp_path / "empty_rulebook_cache")

    # A real, ISSUED corpus span passed where the RULE span belongs -- its doc_id resolves
    # only in the CORPUS store, never the RULEBOOK store.
    result = emit_finding(
        corpus=corpus, submission_span_id=corpus_span, rule_span_id=corpus_span,
        ledger=fresh_ledger, verdict="fails", rulebook_cache_dir=empty_rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert result.reason_code == "wrong_store"


def test_rejects_wrong_store_submission_span_from_rulebook(tmp_path, fresh_ledger):
    """The SYMMETRIC direction (plan-checker Warning 6): a submission_span_id whose doc_id
    only exists in the RULEBOOK store, never the CORPUS store."""
    # A real corpus that legitimately exists but does NOT contain the rulebook chunk's doc_id.
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block("Unrelated submission text.")])

    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    # A real, ISSUED rule span passed where the SUBMISSION span belongs.
    result = emit_finding(
        corpus=corpus, submission_span_id=rule_chunk.span, rule_span_id=rule_chunk.span,
        ledger=fresh_ledger, verdict="fails", rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, ToolRejected)
    assert result.reason_code == "wrong_store"


def test_span_id_unique_by_construction(tmp_path, fresh_ledger):
    """Proves TOOLS-03's `not_unique` rejection condition is structurally UNREACHABLE
    (plan-checker Blocker 1), not merely untested.

    Two spans over the IDENTICAL canonical substring ("specificity data") at DIFFERENT
    offsets -- same hash, different (start,end). The first occurrence is written plainly;
    the second uses the "fi" ligature glyph in its RAW source ("speciﬁcity data"),
    which the normalizer's explicit ligature fold expands to the SAME canonical
    "specificity data" (mirrors the already-proven normalize("ﬁle").canonical == "file"
    fixture in tests/ingest/test_normalize.py) -- so the CANONICAL text (and therefore the
    hash) is identical for both occurrences, but the RAW form genuinely differs. This lets a
    single assertion distinguish "resolved via span_b's own offset" from "resolved via
    span_a's offset (or any content/text-pattern search)", which plain string-content
    equality alone could never do when both occurrences read identically.
    """
    text = (
        "The specificity data supports selectivity for this analytical method. "
        "A separate review of the speciﬁcity data confirmed no interference from excipients."
    )
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    needle = "specificity data"
    start_a = nt.canonical.find(needle)
    start_b = nt.canonical.rfind(needle)
    assert start_a != -1 and start_b != -1 and start_a != start_b  # sanity: two real, distinct occurrences

    span_a = mint_span(nt.canonical, start_a, start_a + len(needle), "sub-doc", nt.normalizer_version)
    span_b = mint_span(nt.canonical, start_b, start_b + len(needle), "sub-doc", nt.normalizer_version)
    assert span_a.hash == span_b.hash  # identical canonical content -> identical hash
    assert span_a.start != span_b.start  # yet genuinely different locations by construction

    raw_a, canon_a = open_span(span_a, nt, "sub-doc")
    raw_b, canon_b = open_span(span_b, nt, "sub-doc")
    assert canon_a == canon_b == needle  # both independently resolve byte-exact, no ambiguity error
    assert raw_a != raw_b  # but their RAW source forms differ (plain text vs ligature glyph)
    assert raw_b == "speciﬁcity data"  # span_b's raw form retains the ligature glyph

    fresh_ledger.record_span(span_a)
    fresh_ledger.record_span(span_b)
    rule_chunk, rulebook_cache_dir = _build_rule(tmp_path)
    fresh_ledger.record_span(rule_chunk.span)

    result = emit_finding(
        corpus=corpus, submission_span_id=span_b, rule_span_id=rule_chunk.span,
        ledger=fresh_ledger, verdict="fails", rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, Fault)
    # Resolves to span_b's OWN offset specifically -- the ligature raw form -- not an
    # accidental match against span_a's plain-text raw form, proving offset-based
    # resolution, never a text-pattern search that could match either occurrence.
    assert result.evidence == raw_b
    assert result.evidence != raw_a


# --- the grounded success path ----------------------------------------------------------------


def test_success_path_constructs_grounded_fault(tmp_path, fresh_ledger):
    text = "The stability study covered 24 months at 25C/60pct RH with no protocol deviations."
    corpus = build_corpus_index(tmp_path, "sub-doc", [_block(text)])
    nt = _nt_from_cache(corpus.cached_entry("sub-doc"))

    start = nt.canonical.index("24 months at 25C/60pct RH")
    end = start + len("24 months at 25C/60pct RH")
    sub_span = mint_span(nt.canonical, start, end, "sub-doc", nt.normalizer_version)
    fresh_ledger.record_span(sub_span)

    rule_chunk, rulebook_cache_dir = _build_rule(
        tmp_path, doc_id="21-cfr-211.166", citation="21 CFR 211.166",
        text="Written stability testing procedures shall be established.",
    )
    fresh_ledger.record_span(rule_chunk.span)

    expected_raw, _ = open_span(sub_span, nt, "sub-doc")

    result = emit_finding(
        corpus=corpus, submission_span_id=sub_span, rule_span_id=rule_chunk.span,
        ledger=fresh_ledger, verdict="fails", requirement_id="REQ-STAB-01",
        rule_citation=rule_chunk.citation, title="Missing stability justification",
        detail="No long-term data beyond 24 months was provided.",
        rulebook_cache_dir=rulebook_cache_dir,
    )

    assert isinstance(result, Fault)
    assert result.evidence_class == EvidenceClass.QUOTE_ANCHORED
    assert result.evidence == expected_raw
    assert rule_chunk.citation in result.guidance_refs
    assert "REQ-STAB-01" in result.guidance_refs
