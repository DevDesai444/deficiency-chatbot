"""Tests for the content classifier (Plan 08 / INGEST-01, D-01..D-10, D-27, D-29)."""
from __future__ import annotations

import pytest

import ingest.classify as classify
from ingest.classify import ClassifyResult, EscalationStats, classify_document
from ingest.normalize import normalize
from schemas.documents import DocClassification
from schemas.llm import ParseFailed


@pytest.fixture(autouse=True)
def _default_no_creds(monkeypatch):
    """Default every test to NO Databricks creds (env-independent) so the LLM tier is skipped
    unless a test explicitly opts in. Prevents real network calls when the dev env has creds."""
    monkeypatch.setattr(
        classify, "get_settings",
        lambda: type("S", (), {"databricks_host": "", "databricks_token": ""})(),
    )


def _nt(text: str):
    return normalize(text)


def test_regex_tier_on_literal_ctd_number():
    nt = _nt("This is section 3.2.S.4.1 Drug Substance Specification with limits.")
    r = classify_document(nt, doc_id="d1")
    assert r.tier == "regex"
    assert r.family_guess == "3.2.S.4.1"
    assert r.confidence > 0.9
    assert r.triggering_span is not None


def test_lexicon_tier_without_ctd_number():
    nt = _nt("Acceptance criteria and specification limits for assay and impurity are listed.")
    r = classify_document(nt, doc_id="d1")
    assert r.tier in ("lexicon", "regex")  # strong lexicon hits, no literal CTD number
    assert r.tier == "lexicon"
    assert r.family_guess and r.triggering_span is not None


def test_title_block_tier_flat_doc():
    # a flat doc whose only signal is its leading title line (D-28)
    nt = _nt("Drug Substance Specification, Product X, SPEC-001\nsome unrelated body prose here")
    r = classify_document(nt, doc_id="d1")
    assert r.family_guess  # classified from the leading text
    assert r.triggering_span is not None


def test_no_threshold_low_signal_still_returned():
    nt = _nt("Dear reviewer, please find the attached correspondence enclosed herewith.")
    r = classify_document(nt, doc_id="d1")  # no creds in test env -> LLM skipped -> free-form
    assert isinstance(r, DocClassification)
    assert r.label  # first-class free-form label, never dropped (D-02/D-03)


def test_signature_has_no_path_or_filename():
    import inspect
    ps = set(inspect.signature(classify_document).parameters)
    assert not (ps & {"path", "filename", "folder"}), ps


def test_offline_does_not_invoke_llm(monkeypatch):
    # no creds -> the LLM tier must be skipped; structured_call must NOT be called
    monkeypatch.setattr(classify, "get_settings",
                        lambda: type("S", (), {"databricks_host": "", "databricks_token": ""})())
    def _boom(*a, **k):
        raise AssertionError("structured_call must not run under no-creds")
    monkeypatch.setattr(classify, "structured_call", _boom)
    nt = _nt("Generic correspondence with no CTD or spec vocabulary at all zzz.")
    r = classify_document(nt, doc_id="d1")   # must not raise
    assert r.tier == "none"


def test_llm_escalation_yields_llm_tier(monkeypatch):
    monkeypatch.setattr(classify, "get_settings",
                        lambda: type("S", (), {"databricks_host": "h", "databricks_token": "t"})())
    monkeypatch.setattr(classify, "structured_call",
                        lambda *a, **k: (ClassifyResult(label="cover letter", family="3.2.R", confidence=0.6), None))
    nt = _nt("Generic correspondence with no CTD or spec vocabulary at all zzz.")
    r = classify_document(nt, doc_id="d1")
    assert r.tier == "llm" and r.family_guess == "3.2.R" and r.label == "cover letter"


def test_llm_parsefailed_falls_back(monkeypatch):
    monkeypatch.setattr(classify, "get_settings",
                        lambda: type("S", (), {"databricks_host": "h", "databricks_token": "t"})())
    monkeypatch.setattr(classify, "structured_call",
                        lambda *a, **k: (None, ParseFailed(layer="llm", reason="bad", raw_output="")))
    nt = _nt("Generic correspondence with no CTD or spec vocabulary at all zzz.")
    r = classify_document(nt, doc_id="d1")   # must not raise; falls back to free-form
    assert r.tier == "none"


def test_escalation_stats_fractions_sum_to_one():
    stats = EscalationStats()
    for text in ["3.2.S.4.1 spec", "acceptance criteria limit assay", "random prose here"]:
        classify_document(_nt(text), doc_id="d", stats=stats)
    rate = stats.escalation_rate()
    assert abs(sum(rate.values()) - 1.0) < 1e-9
    assert set(rate).issubset({"regex", "lexicon", "llm", "none"})
