"""Composition tests for Phase 03 Plan 10's boundary-crossing audit.

Each test here starts with a real producer output from the audit table and feeds it through the
real consumer chain. The point is to catch the boundary failure class where each side is green in
isolation but the committed intermediate shape does not actually compose.
"""
from __future__ import annotations

import pytest

from agents.review.spanref import SPAN_REF_RE, parse_span_ref
from ingest.manifest import CoverageManifest
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.faults import Fault
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_finding
from tools.errors import ToolRejected
from tools.get_section import get_section
from tools.ledger import RetrievalLedger
from tools.read_guideline import read_guideline
from agents.review.oracles_tool import run_oracles_tool


def _block(text: str, page: int = 1, order: int = 0) -> dict:
    return {"text": text, "page": page, "reading_order": order, "lines": []}


@pytest.fixture(scope="module")
def _ecfr_store():
    """Build the real committed eCFR snapshot into the local offline rulebook store."""
    from rulebook.build import build_ecfr

    errors = [r for r in build_ecfr(update_manifest=False) if "error" in r]
    assert not errors, f"eCFR build fixture hit vendoring errors: {errors}"
    yield


def test_oracle_lead_reopened_becomes_an_accepted_finding(_ecfr_store, tmp_path):
    """Boundary-crossing audit chain #2 (Pitfall 9).

    Plan 03-09 proves the gate rejects an un-re-opened oracle lead; this proves the positive path
    composes: the lead's own locating hint drives get_section, whose issued span-ID is parsed and
    accepted by emit_finding.

    If this boundary were wrong, oracle-lead conversion telemetry could report zero accepted
    findings for a reason unrelated to the review agent's behavior.
    """
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [
            _block(
                "3.2.S.4.3 Analytical Method Validation. The analytical evaluation threshold "
                "AET level is 22.727 ug/g in the method summary. Later the AET level is 25.0 "
                "ug/g for the same unit."
            )
        ],
        outline_headings=["3.2.S.4.3 Analytical Method Validation."],
    )
    ledger = RetrievalLedger()

    leads = run_oracles_tool(corpus, "d1", ledger)
    assert isinstance(leads, dict)
    lead = next(
        lead
        for lead in leads["positive_leads"]
        if lead["check"] == "cross_reference_aet"
    )

    rendered = get_section(corpus, "d1", ledger, heading=lead["heading_hint"])
    assert isinstance(rendered, str)
    refs = SPAN_REF_RE.findall(rendered)
    assert refs
    submission_span = parse_span_ref(
        refs[0], corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="submission",
    )
    assert not isinstance(submission_span, ToolRejected), submission_span

    rule_text = read_guideline(CoverageManifest(), ledger, citation="21 CFR 211.194", max_chars=200_000)
    assert isinstance(rule_text, str)
    rule_refs = SPAN_REF_RE.findall(rule_text)
    assert rule_refs
    rule_span = parse_span_ref(
        rule_refs[0], corpus, DEFAULT_RULEBOOK_CACHE_DIR, expect="rule",
    )
    assert not isinstance(rule_span, ToolRejected), rule_span

    fault = emit_finding(
        corpus,
        submission_span,
        rule_span,
        ledger,
        verdict="gap",
        title=lead["claim"],
        detail=lead["quoted_text"],
        rule_citation="21 CFR 211.194",
    )

    assert not isinstance(fault, ToolRejected), fault
    assert isinstance(fault, Fault)
    assert fault.submission_span_id is not None
    assert fault.rule_span_id is not None
