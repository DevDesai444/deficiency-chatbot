"""GROUND-01 span-reference composition tests for the review loop.

These tests cross the boundary that unit tests on either side cannot cover: tool rendering,
loop-side parsing/re-minting, ledger issuance, and the same open_span hash check used by
emit_finding.
"""
from __future__ import annotations

import pytest

from agents.review.spanref import SPAN_REF_RE, parse_span_ref
from ingest.anchors import HashMismatch, mint_span, open_span
from ingest.manifest import CoverageManifest
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR, rulebook_nt_for
from schemas.documents import NormalizedText, OffsetRun
from schemas.faults import ComplianceVerdict, Fault
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_finding
from tools.errors import ToolRejected
from tools.follow_reference import follow_reference
from tools.get_section import get_section
from tools.ledger import RetrievalLedger
from tools.open_doc import open_doc
from tools.read_guideline import read_guideline
from tools.search_corpus import search_corpus

_OPEN_SPAN_COVERAGE = [
    "search_corpus -> open_span",
    "open_doc -> open_span",
    "get_section -> open_span",
    "read_guideline -> open_span",
    "follow_reference -> open_span",
]


def _block(text: str, page: int = 1, order: int = 0) -> dict:
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _corpus(tmp_path):
    body = (
        "3.2.S.5 Reference Standards or Materials. The submission describes reference "
        "standard qualification and impurity response factors. Section 3.2.S.6 Container "
        "Closure System cross references 3.2.S.5 for the same standard."
    )
    return build_corpus_index(
        tmp_path,
        "d1",
        [_block(body)],
        outline_headings=[
            "3.2.S.5 Reference Standards or Materials.",
            "Section 3.2.S.6 Container Closure System",
        ],
    )


def _nt_for(corpus, doc_id: str) -> NormalizedText:
    cache = corpus.cached_entry(doc_id)
    assert cache is not None
    return NormalizedText(
        canonical=cache["canonical"],
        raw_serialized=cache["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
        normalizer_version=cache["normalizer_version"],
        serializer_version=cache["serializer_version"],
    )


def _ref_from_span_dict(span: dict) -> str:
    return f"[{span['doc_id']}:{span['start']}:{span['end']}]"


def _assert_submission_refs_roundtrip(refs: list[str], corpus, ledger: RetrievalLedger) -> None:
    for ref in refs:
        span = parse_span_ref(ref, corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="submission")
        assert not isinstance(span, ToolRejected), span
        assert ledger.was_issued(span)
        raw, canonical = open_span(span, _nt_for(corpus, span.doc_id), span.doc_id)
        assert raw
        assert canonical


def _assert_rule_refs_roundtrip(refs: list[str], corpus, ledger: RetrievalLedger) -> None:
    for ref in refs:
        span = parse_span_ref(ref, corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="rule")
        assert not isinstance(span, ToolRejected), span
        assert ledger.was_issued(span)
        nt = rulebook_nt_for(span.doc_id)
        assert nt is not None
        raw, canonical = open_span(span, nt, span.doc_id)
        assert raw
        assert canonical


@pytest.fixture(scope="module")
def _ecfr_store():
    """Build the real committed eCFR snapshot into the local offline rulebook store."""
    from rulebook.build import build_ecfr

    errors = [r for r in build_ecfr(update_manifest=False) if "error" in r]
    assert not errors, f"eCFR build fixture hit vendoring errors: {errors}"
    yield


def test_search_corpus_rendered_span_survives_the_round_trip(tmp_path):
    """search_corpus: snippet -> parse -> re-mint -> was_issued -> open_span."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()

    results = search_corpus(corpus, "reference standard impurity", ledger, top_k=1)
    refs = SPAN_REF_RE.findall(results[0]["snippet"]) if results else []
    assert refs, "the test is vacuous if search_corpus rendered no span-IDs"

    _assert_submission_refs_roundtrip(refs, corpus, ledger)


def test_open_doc_outline_span_survives_the_round_trip(tmp_path):
    """open_doc: outline span dict -> parse -> re-mint -> was_issued -> open_span."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()

    result = open_doc(corpus, "d1", ledger)
    assert isinstance(result, dict)
    refs = [_ref_from_span_dict(row["span_id"]) for row in result["outline"]]
    assert refs, "the test is vacuous if open_doc exposed no outline span-IDs"

    _assert_submission_refs_roundtrip(refs, corpus, ledger)


def test_get_section_rendered_span_survives_the_round_trip(tmp_path):
    """get_section: annotated section -> parse -> re-mint -> was_issued -> open_span."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()

    result = get_section(corpus, "d1", ledger, heading="3.2.S.5")
    assert isinstance(result, str)
    refs = SPAN_REF_RE.findall(result)
    assert refs, "the test is vacuous if get_section rendered no span-IDs"

    _assert_submission_refs_roundtrip(refs, corpus, ledger)


def test_read_guideline_rendered_span_survives_the_round_trip(_ecfr_store, tmp_path):
    """read_guideline fetch mode: rule text -> parse -> re-mint -> was_issued -> open_span."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()

    result = read_guideline(CoverageManifest(), ledger, citation="21 CFR 211.166", max_chars=200_000)
    assert isinstance(result, str)
    refs = SPAN_REF_RE.findall(result)
    assert refs, "the test is vacuous if read_guideline rendered no span-IDs"

    _assert_rule_refs_roundtrip(refs[:3], corpus, ledger)


def test_follow_reference_resolved_span_survives_the_round_trip(tmp_path):
    """follow_reference resolved mode -> parse -> re-mint -> was_issued -> open_span."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()

    result = follow_reference(corpus, "d1", "3.2.S.5", ledger)
    assert result.get("resolved") is True
    refs = [_ref_from_span_dict(result["span_id"])]
    assert refs, "the test is vacuous if follow_reference resolved no span-ID"

    _assert_submission_refs_roundtrip(refs, corpus, ledger)


def test_rendered_span_reaches_emit_finding_and_produces_a_fault(_ecfr_store, tmp_path):
    """The loop chain: get_section -> SPAN_REF_RE -> parse_span_ref -> emit_finding -> Fault."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()

    section = get_section(corpus, "d1", ledger, heading="3.2.S.5")
    assert isinstance(section, str)
    submission_refs = SPAN_REF_RE.findall(section)
    assert submission_refs
    submission_span = parse_span_ref(
        submission_refs[0], corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="submission",
    )
    assert not isinstance(submission_span, ToolRejected), submission_span

    rule_text = read_guideline(CoverageManifest(), ledger, citation="21 CFR 211.166", max_chars=200_000)
    assert isinstance(rule_text, str)
    rule_refs = SPAN_REF_RE.findall(rule_text)
    assert rule_refs
    rule_span = parse_span_ref(rule_refs[0], corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="rule")
    assert not isinstance(rule_span, ToolRejected), rule_span

    fault = emit_finding(
        corpus,
        submission_span,
        rule_span,
        ledger,
        verdict="gap",
        title="Reference standard qualification gap",
        detail="Qualification evidence is missing.",
    )

    assert isinstance(fault, Fault), fault
    assert fault.submission_span_id is not None
    assert fault.rule_span_id is not None
    assert fault.verdict == ComplianceVerdict.GAP


def test_unresolvable_ref_is_not_span_invention(tmp_path):
    """Pitfall 1 guard: loop-side parse failures never masquerade as model span-invention."""
    corpus = _corpus(tmp_path)

    for bad in ["not-a-span", "[nosuchdoc:1:2]", "[d1:999999:1000000]"]:
        rej = parse_span_ref(bad, corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="submission")
        assert isinstance(rej, ToolRejected)
        assert rej.reason_code.startswith("span_ref_")
        assert rej.reason_code != "not_byte_exact"
        assert rej.half == ""


def test_store_separation_is_enforced(tmp_path):
    """Security Domain V4: a submission span cannot resolve as a rule span."""
    corpus = _corpus(tmp_path)
    ledger = RetrievalLedger()
    section = get_section(corpus, "d1", ledger, heading="3.2.S.5")
    assert isinstance(section, str)
    refs = SPAN_REF_RE.findall(section)
    assert refs

    rejected = parse_span_ref(refs[0], corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="rule")

    assert isinstance(rejected, ToolRejected)
    assert rejected.reason_code == "span_ref_unknown_doc"
    assert rejected.half == ""


def test_roundtrip_assertion_is_not_vacuous(tmp_path):
    """Negative control: a wrong normalizer version fails the real hash check."""
    corpus = _corpus(tmp_path)
    nt = _nt_for(corpus, "d1")
    start = nt.canonical.index("reference standard")
    end = start + len("reference standard")
    corrupted = mint_span(nt.canonical, start, end, "d1", "wrong-normalizer-version")

    with pytest.raises(HashMismatch):
        open_span(corrupted, nt, "d1")
