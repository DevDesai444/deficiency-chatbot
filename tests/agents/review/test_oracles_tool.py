"""Tests for run_oracles_tool's DETECT-03 seed-pass contract."""
from __future__ import annotations

from ingest.anchors import mint_span
from schemas.documents import NormalizedText, OffsetRun, SpanID
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from agents.detection import oracles as oracle_module
from agents.review.oracles_tool import run_oracles_tool


def _block(text: str, page: int = 1, order: int = 0) -> dict:
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _nt_from_cache(cache: dict) -> NormalizedText:
    return NormalizedText(
        canonical=cache["canonical"],
        raw_serialized=cache["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
        normalizer_version=cache["normalizer_version"],
        serializer_version=cache["serializer_version"],
    )


def _all_validation_except_loq() -> str:
    return (
        "3.2.S.4.3 Analytical Method Validation. Specificity was demonstrated. "
        "Linearity was acceptable. Limit of detection was established. Precision and "
        "repeatability were evaluated. Accuracy and recovery were acceptable. Robustness "
        "and ruggedness were assessed. System suitability was defined. Solution stability "
        "and stability of sample were evaluated."
    )


def _complete_seed_text() -> str:
    return (
        "3.2.S.4.3 Analytical Method Validation. Specificity, linearity, limit of detection, "
        "LOD, limit of quantitation, LOQ, precision, repeatability, accuracy, recovery, "
        "robustness, ruggedness, system suitability, solution stability, stability of standard, "
        "and stability of sample were all addressed. Reference standard RS-1 from USP used "
        "lot number L-123 with purity 99.8%, expiry 2027-01, and qualification by certificate "
        "of analysis. Stability data are available and the applicant committed to continue "
        "long-term stability studies for the first three production batches."
    )


def _absence_leads(result: dict, check: str | None = None) -> list[dict]:
    leads = result["absence_leads"]
    if check is None:
        return leads
    return [lead for lead in leads if lead["check"] == check]


def test_no_prerecorded_spans(tmp_path):
    """D-ORC2: the seed pass must not issue evidence the model has not re-opened."""
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block("AET level of 22.727 ug/g. Later the AET level is 25.0 ug/g.")],
        outline_headings=["AET level of 22.727 ug/g."],
    )
    ledger = RetrievalLedger()

    result = run_oracles_tool(corpus, "d1", ledger)

    assert isinstance(result, dict)
    assert result["leads_surfaced"] > 0, "vacuous: the fixture surfaced no leads"
    assert ledger._issued == set()

    cache = corpus.cached_entry("d1")
    nt = _nt_from_cache(cache)
    submission = mint_span(nt.canonical, 0, min(20, len(nt.canonical)), "d1", nt.normalizer_version)
    rule = SpanID(doc_id="rule-q", start=0, end=4, hash="unissued")
    rejection = emit_finding(corpus, submission, rule, ledger, verdict="gap")

    assert isinstance(rejection, ToolRejected)
    assert (rejection.reason_code, rejection.half) == ("not_retrieved_this_session", "submission")


def test_s9_s10_p10_leads(tmp_path):
    s9_corpus = build_corpus_index(
        tmp_path / "s9",
        "s9-doc",
        [_block(_all_validation_except_loq())],
        outline_headings=["3.2.S.4.3 Analytical Method Validation."],
    )
    s10_corpus = build_corpus_index(
        tmp_path / "s10",
        "s10-doc",
        [
            _block(
                "3.2.S.5 Reference Standards. Reference standard RS-1 used lot number L-123, "
                "purity 99.8%, and expiry 2027-01."
            )
        ],
        outline_headings=["3.2.S.5 Reference Standards."],
    )
    p10_corpus = build_corpus_index(
        tmp_path / "p10",
        "p10-doc",
        [_block("3.2.P.8 Stability. Stability data from accelerated and long-term stability studies are summarized.")],
        outline_headings=["3.2.P.8 Stability."],
    )

    s9 = run_oracles_tool(s9_corpus, "s9-doc", RetrievalLedger())
    s10 = run_oracles_tool(s10_corpus, "s10-doc", RetrievalLedger())
    p10 = run_oracles_tool(p10_corpus, "p10-doc", RetrievalLedger())

    assert [lead["expected_element"] for lead in _absence_leads(s9, "S9")] == ["limit of quantitation (LOQ)"]
    assert [lead["expected_element"] for lead in _absence_leads(s10, "S10")] == ["qualification"]
    assert [lead["expected_element"] for lead in _absence_leads(p10, "P10")] == ["stability commitment"]


def test_a_present_element_produces_no_absence_lead(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block(_complete_seed_text())],
        outline_headings=["3.2.S.4.3 Analytical Method Validation."],
    )

    result = run_oracles_tool(corpus, "d1", RetrievalLedger())

    assert isinstance(result, dict)
    assert result["absence_leads"] == []


def test_s10_synonyms_do_not_produce_a_false_absence(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [
            _block(
                "3.2.S.5 Reference Standards. Reference standard RS-1 uses batch number B-45, "
                "assigned potency 100.1%, re-test date 2027-02, and a certificate of analysis."
            )
        ],
        outline_headings=["3.2.S.5 Reference Standards."],
    )

    result = run_oracles_tool(corpus, "d1", RetrievalLedger())

    assert isinstance(result, dict)
    assert _absence_leads(result, "S10") == []


def test_leads_carry_no_span_id_field(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block(_all_validation_except_loq())],
        outline_headings=["3.2.S.4.3 Analytical Method Validation."],
    )

    result = run_oracles_tool(corpus, "d1", RetrievalLedger())

    assert isinstance(result, dict)
    for lead in result["positive_leads"] + result["absence_leads"]:
        assert "span_id" not in lead


def test_absence_lead_directs_the_agent_to_a_real_reopenable_span(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block(_all_validation_except_loq())],
        outline_headings=["3.2.S.4.3 Analytical Method Validation."],
    )

    result = run_oracles_tool(corpus, "d1", RetrievalLedger())

    assert isinstance(result, dict)
    assert result["absence_leads"]
    for lead in result["absence_leads"]:
        assert lead["expected_element"]
        assert lead["scope_searched"]
        assert lead["next_call"]
        assert "read_guideline" in lead["next_call"]
        assert "get_section" in lead["next_call"]


def test_a_failing_check_does_not_sink_the_battery(tmp_path, monkeypatch):
    def boom(doc: dict) -> list:
        msg = "forced check failure"
        raise RuntimeError(msg)

    monkeypatch.setattr(oracle_module, "ORACLES", [boom, oracle_module.cross_reference_consistency])
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block("AET level of 22.727 ug/g. Later the AET level is 25.0 ug/g.")],
        outline_headings=["AET level of 22.727 ug/g."],
    )

    result = run_oracles_tool(corpus, "d1", RetrievalLedger())

    assert isinstance(result, dict)
    assert result["positive_leads"]
    assert result["check_errors"] == [{"check": "boom", "error": "forced check failure"}]


def test_unknown_doc_id_is_a_typed_rejection(tmp_path):
    corpus = build_corpus_index(tmp_path, "d1", [_block("Some text.")])

    result = run_oracles_tool(corpus, "../not-a-real-doc", RetrievalLedger())

    assert isinstance(result, ToolRejected)
    assert result.reason_code == "not_found"
    assert result.half == ""
