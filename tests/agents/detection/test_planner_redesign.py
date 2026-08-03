"""Tests for the planner/summariser/sandwich/worker redesign.

Covers the deterministic pieces (assembly, coverage-repair, chunking, cross-section challenge) plus
the summariser fidelity guard with a mocked LLM. The LLM-driven planner/worker calls themselves are
exercised end-to-end elsewhere; here we lock the logic that must be correct regardless of the model.
"""
from __future__ import annotations

import json

from agents.detection.planning import (
    ReviewPlan,
    WorkerAssignment,
    _ensure_coverage,
    _fallback_plan,
    _sanitize,
)
from agents.detection.sandwich import build_sandwich, open_review_chunks, render_sandwich
from agents.detection.verify import verify_and_tier


def _sections() -> list[dict]:
    return [
        {"heading": "S0 Specification", "text": "assay limit 98.0-102.0%", "tables": [], "page_start": 1, "page_end": 1},
        {"heading": "S1 Method", "text": "some prose", "tables": [{"kind": "grid", "headers": ["a"], "rows": [["1"]]}], "page_start": 2, "page_end": 2},
        {"heading": "S2 Batch", "text": "assay result 104.2%", "tables": [], "page_start": 3, "page_end": 3},
    ]


def _summaries(sections: list[dict]) -> list[dict]:
    return [
        {"section_index": i, "heading": s["heading"], "summary": f"SUM{i}", "tables": s["tables"], "page_start": 0, "page_end": 0}
        for i, s in enumerate(sections)
    ]


class TestSandwich:
    def test_focused_full_context_summarised(self):
        sections = _sections()
        sw = build_sandwich(sections, _summaries(sections), [2])
        assert sw["focused_section_indices"] == [2]
        roles = {s["section_index"]: s["role"] for s in sw["sections"]}
        assert roles == {0: "context", 1: "context", 2: "focused"}

        focused = next(s for s in sw["sections"] if s["role"] == "focused")
        assert focused["text"] == "assay result 104.2%"          # full text kept verbatim
        assert "summary" not in focused

        ctx0 = next(s for s in sw["sections"] if s["section_index"] == 0)
        assert ctx0["summary"] == "SUM0"                          # summary swapped in
        assert "text" not in ctx0

    def test_context_tables_carried_verbatim(self):
        sections = _sections()
        sw = build_sandwich(sections, _summaries(sections), [0])
        ctx1 = next(s for s in sw["sections"] if s["section_index"] == 1)
        assert ctx1["tables"] == sections[1]["tables"]           # tables never degraded on context

    def test_two_focused_sections(self):
        sections = _sections()
        sw = build_sandwich(sections, _summaries(sections), [0, 2])
        focused = [s["section_index"] for s in sw["sections"] if s["role"] == "focused"]
        assert focused == [0, 2]

    def test_render_is_valid_json(self):
        sections = _sections()
        sw = build_sandwich(sections, _summaries(sections), [0])
        parsed = json.loads(render_sandwich(sw))
        assert parsed["focused_section_indices"] == [0]
        assert len(parsed["sections"]) == 3

    def test_open_review_chunks_pairs(self):
        assert open_review_chunks(3) == [[0, 1], [2]]
        assert open_review_chunks(4) == [[0, 1], [2, 3]]
        assert open_review_chunks(0) == []


class TestPlanSanitizeAndCoverage:
    def test_clamps_out_of_range_and_caps_focus(self):
        plan = ReviewPlan(workers=[WorkerAssignment(focused_section_indices=[0, 1, 2, 99])])
        out = _sanitize(plan, n_sections=3)
        assert out.workers[0].focused_section_indices == [0, 1]   # 99 dropped, capped to 2

    def test_drops_worker_with_no_valid_sections(self):
        plan = ReviewPlan(workers=[WorkerAssignment(focused_section_indices=[99])])
        assert _sanitize(plan, n_sections=3).workers == []

    def test_ensure_coverage_fills_every_gap(self):
        plan = ReviewPlan(workers=[WorkerAssignment(focused_section_indices=[0])])
        out = _ensure_coverage(plan, n_sections=3)
        covered: set[int] = set()
        for w in out.workers:
            covered.update(w.focused_section_indices)
        assert covered == {0, 1, 2}

    def test_fallback_plan_covers_all_within_cap(self):
        out = _fallback_plan(5)
        covered: set[int] = set()
        for w in out.workers:
            covered.update(w.focused_section_indices)
        assert covered == {0, 1, 2, 3, 4}
        assert all(len(w.focused_section_indices) <= 2 for w in out.workers)


class TestWorkerConversion:
    def test_confirmed_suspicion_becomes_cross_section_fault(self):
        from agents.detection.planning import Suspicion, SuspicionEvidence
        from agents.detection.workers import SuspicionVerdict, WorkerOutput, _to_faults

        susp = Suspicion(
            claim="Assay exceeds its limit",
            reasoning="limit in S0, result in S2",
            cross_section=True,
            evidence=[SuspicionEvidence(section_index=0, quote="98.0-102.0%"), SuspicionEvidence(section_index=2, quote="104.2%")],
        )
        out = WorkerOutput(
            findings=[],
            suspicion_verdicts=[SuspicionVerdict(claim="Assay exceeds its limit", verdict="confirmed",
                                                 deficiency_exists=True, evidence="104.2% vs 98.0-102.0%")],
        )
        faults = _to_faults(out, "specialist:2", [], [susp])
        assert len(faults) == 1
        assert faults[0].cited_section_indices == [0, 2]
        assert "assay exceeds its limit" in faults[0].title.lower()

    def test_refuted_and_unclear_suspicions_are_not_faults(self):
        from agents.detection.workers import SuspicionVerdict, WorkerOutput, _to_faults

        out = WorkerOutput(
            findings=[],
            suspicion_verdicts=[SuspicionVerdict(claim="x", verdict="refuted"), SuspicionVerdict(claim="y", verdict="unclear")],
        )
        assert _to_faults(out, "s", [], []) == []

    def test_finding_carries_rule_into_guidance_refs(self):
        from agents.detection.workers import WorkerFinding, WorkerOutput, _to_faults

        out = WorkerOutput(findings=[WorkerFinding(title="LOQ missing", evidence="no LOQ", rule_cited="ICH Q2")])
        faults = _to_faults(out, "reviewer:0", [], [])
        assert len(faults) == 1
        assert "ICH Q2" in faults[0].guidance_refs

    def test_untitled_worker_finding_is_not_silently_dropped(self):
        from agents.detection.workers import WorkerFinding, WorkerOutput, _to_faults

        out = WorkerOutput(findings=[
            WorkerFinding(
                title="",
                detail="Table 20 Maximum theoretical plates 11477 contradicts row value 12601.",
                evidence="Maximum 11477; In-house Equivalency Study 12601",
                rule_cited="Table 20 Maximum summary cell",
            )
        ])

        faults = _to_faults(out, "specialist:17", [], [])

        assert len(faults) == 1
        assert faults[0].title
        assert "11477" in faults[0].title


class TestChallengeIntersectionAware:
    def test_sections_for_includes_cited_indices(self):
        from agents.detection.challenge import _sections_for
        from schemas.faults import Fault

        sections = [{"heading": "S0", "tables": []}, {"heading": "S1", "tables": []}, {"heading": "S2", "tables": []}]
        picked = _sections_for(Fault(title="x", cited_section_indices=[0, 2]), sections)
        assert sections[0] in picked and sections[2] in picked
        assert sections[1] not in picked


class TestArithmeticChallengeGate:
    """The precision guard: a claimed limit violation is refuted by RECOMPUTING the document's own
    cells, not by finding a passage. These are the real false positives from a live run — each one's
    value actually satisfies its criterion, and a quote could never have refuted them."""

    def _doc(self, text: str) -> dict:
        return {"pages": [{"blocks": [{"text": text}], "tables": []}]}

    def test_tailing_factor_inside_range_is_dropped(self):
        from agents.detection.challenge import ChallengeVerdict, _apply_verdict
        from agents.detection.verify import _doc_corpus
        from schemas.faults import Fault

        doc = self._doc("Tailing factor (0.9 - 1.5) ... Minimum 1.2")
        fault = Fault(title="Tailing factor minimum (1.2) contradicts lower limit of 0.9", confidence=0.5)
        verdict = ChallengeVerdict(
            refuted=False, claims_limit_violation=True,
            criterion_quote="0.9 - 1.5", observed_quote="1.2",
        )
        dropped = _apply_verdict(fault, verdict, _doc_corpus(doc))
        assert dropped is True
        assert "satisfies" in fault.challenge_note

    def test_rsd_under_nmt_limit_is_dropped(self):
        from agents.detection.challenge import ChallengeVerdict, _apply_verdict
        from agents.detection.verify import _doc_corpus
        from schemas.faults import Fault

        doc = self._doc("acceptance criterion NMT 10.0% ... 17 a-Estradiol RSD 9.1")
        fault = Fault(title="LOQ RSD for 17a-Estradiol exceeds NMT 10.0%", confidence=0.5)
        verdict = ChallengeVerdict(
            refuted=False, claims_limit_violation=True,
            criterion_quote="NMT 10.0%", observed_quote="9.1",
        )
        assert _apply_verdict(fault, verdict, _doc_corpus(doc)) is True

    def test_real_violation_survives(self):
        from agents.detection.challenge import ChallengeVerdict, _apply_verdict
        from agents.detection.verify import _doc_corpus
        from schemas.faults import Fault

        doc = self._doc("acceptance criterion NMT 0.25% ... result 0.30")
        fault = Fault(title="Result out of specification", confidence=0.5)
        verdict = ChallengeVerdict(
            refuted=False, claims_limit_violation=True,
            criterion_quote="NMT 0.25%", observed_quote="0.30",
        )
        # 0.30 > 0.25 -> the violation is real, the finding must NOT be dropped
        assert _apply_verdict(fault, verdict, _doc_corpus(doc)) is False
        assert fault.challenge_note == ""

    def test_invented_numbers_cannot_clear_a_finding(self):
        from agents.detection.challenge import ChallengeVerdict, _apply_verdict
        from agents.detection.verify import _doc_corpus
        from schemas.faults import Fault

        doc = self._doc("unrelated content with no such values")
        fault = Fault(title="Some value violates its limit", confidence=0.5)
        verdict = ChallengeVerdict(
            refuted=False, claims_limit_violation=True,
            criterion_quote="NMT 99.0%", observed_quote="1.0",   # not in the document
        )
        assert _apply_verdict(fault, verdict, _doc_corpus(doc)) is False

    def test_non_numeric_finding_is_untouched_by_the_arithmetic_path(self):
        from agents.detection.challenge import ChallengeVerdict, _apply_verdict
        from agents.detection.verify import _doc_corpus
        from schemas.faults import Fault

        doc = self._doc("some prose")
        fault = Fault(title="No commitment to continued monitoring", confidence=0.5)
        verdict = ChallengeVerdict(refuted=False, claims_limit_violation=False)
        assert _apply_verdict(fault, verdict, _doc_corpus(doc)) is False
        assert fault.confidence == 0.6   # unrefuted findings still get the small bump

    def test_summary_cell_contradiction_not_refuted_by_different_row_labels(self):
        from agents.detection.challenge import ChallengeVerdict, _apply_verdict
        from agents.detection.verify import _doc_corpus
        from schemas.faults import Fault

        doc = self._doc(
            "Table 20 System Suitability Results. Specificity 11400. Linearity 11477. "
            "In-house Equivalency Study 12601. Maximum theoretical plates 11477."
        )
        fault = Fault(
            title="Table 20 Maximum theoretical plates 11477 contradicts In-house Equivalency Study row 12601",
            detail="Maximum is a summary cell and cannot be lower than a row it summarizes.",
            evidence="Maximum theoretical plates 11477; In-house Equivalency Study 12601",
            confidence=0.5,
        )
        verdict = ChallengeVerdict(
            refuted=True,
            counter_evidence="Specificity 11400. Linearity 11477. In-house Equivalency Study 12601.",
            reasoning="These are different studies and are expected to differ.",
        )

        assert _apply_verdict(fault, verdict, _doc_corpus(doc)) is False
        assert fault.confidence == 0.6


class TestNonDeficiencyGate:
    """Findings that concede compliance in their own words are not deficiencies. Verbatim titles /
    details from a live run that shipped 18 of 35 such 'faults' — the model wrote 'This is not a
    finding.' into the detail and reported it anyway, so the gate lives in code, not the prompt."""

    def _doc(self) -> dict:
        return {"pages": [{"blocks": [{"text": "x"}], "tables": []}]}

    def test_drops_live_compliance_statements(self):
        from schemas.faults import Fault

        cases = [
            ("Table 1 requires LOD RSD NMT 33.0% ... all <=33%. Valid.",
             "All RSD values at LOD are well below 33% acceptance limit. No deficiency."),
            ("LOD RSD values in Table 8 exceed the acceptance criterion",
             "18.9% is within the criterion of NMT 33.0%. This is not a finding. (Verification: 18.9% <= 33.0% -> compliant.)"),
            ("Equivalency study reports Estrone as ND by in-house method",
             "Therefore reporting N/A is appropriate. No violation of specification or equivalency criterion exists."),
            ("System suitability minimum theoretical plates is 9792",
             "9792 > 7000, so this is not a deficiency. This is not a finding."),
        ]
        faults = [Fault(title=t, detail=d) for t, d in cases]
        assert verify_and_tier(faults, self._doc()) == []

    def test_keeps_real_findings_that_merely_quote_compliance_words(self):
        from schemas.faults import Fault

        # A genuine finding often argues AGAINST a compliance claim; it must survive.
        f = Fault(
            title="Table 20 Maximum theoretical plates contradicts its own rows",
            detail=("The report states the system suitability criteria were met and every value is "
                    "within limit, but Maximum is given as 11477 while the rows above contain 12601."),
        )
        out = verify_and_tier([f], self._doc())
        assert len(out) == 1

    def test_oracle_findings_are_never_dropped(self):
        from schemas.faults import EvidenceClass, Fault, Tier

        f = Fault(
            title="Result out of specification",
            detail="No violation of the range was assumed; recomputed 0.30 vs NMT 0.25%.",
            evidence_class=EvidenceClass.CODE_VERIFIED,
            tier=Tier.VERIFIED,
        )
        out = verify_and_tier([f], self._doc())
        assert len(out) == 1 and out[0].evidence_class == EvidenceClass.CODE_VERIFIED


class TestSuspicionRequiresDeficiency:
    """A 'confirmed' suspicion means the CLAIM is true — which for a neutral check means the document
    is compliant. Only an explicit deficiency_exists may mint a fault."""

    def test_confirmed_but_compliant_makes_no_fault(self):
        from agents.detection.planning import Suspicion
        from agents.detection.workers import SuspicionVerdict, WorkerOutput, _to_faults

        susp = [Suspicion(claim="Table 8 RSDs are under NMT 33.0%", reasoning="All values comply.")]
        out = WorkerOutput(suspicion_verdicts=[
            SuspicionVerdict(claim="Table 8 RSDs are under NMT 33.0%", verdict="confirmed",
                             deficiency_exists=False, evidence="18.9%")
        ])
        assert _to_faults(out, "specialist:8,2", [], susp) == []

    def test_confirmed_with_deficiency_makes_a_fault(self):
        from agents.detection.planning import Suspicion
        from agents.detection.workers import SuspicionVerdict, WorkerOutput, _to_faults

        susp = [Suspicion(claim="Table 20 Maximum contradicts its rows", reasoning="Max says 11477, rows hold 12601.")]
        out = WorkerOutput(suspicion_verdicts=[
            SuspicionVerdict(claim="Table 20 Maximum contradicts its rows", verdict="confirmed",
                             deficiency_exists=True, evidence="Maximum 11477")
        ])
        faults = _to_faults(out, "specialist:17,2", [], susp)
        assert len(faults) == 1 and "Maximum" in faults[0].title


class TestTrailingConcessionGate:
    """Verbatim titles from a live run whose own verdict is 'compliant. No finding.' — and, crucially,
    the real finding from the SAME run that must survive because it concedes compliance as a PREMISE
    before showing the contradiction."""

    def _doc(self) -> dict:
        return {"pages": [{"blocks": [{"text": "x"}], "tables": []}]}

    def test_drops_trailing_compliance_verdicts(self):
        from schemas.faults import Fault

        titles = [
            "Table 1 (page 9) reports USP method theoretical plates as 5656 and in-house as 12601 — both exceed their criteria. Compliant. No finding.",
            "LOQ RSD for 17 a-Estradiol (9.1%) is under the NMT 10.0% criterion — compliant. No finding.",
            "Table 1 (page 8) reports drift as 4.5% at 72h, which is within the +/-10.0% criterion — compliant.",
            "Equivalency study reports USP impurity values as N/A, which is intentional and correct.",
        ]
        assert verify_and_tier([Fault(title=t) for t in titles], self._doc()) == []

    def test_keeps_the_real_contradiction_that_concedes_compliance_first(self):
        from schemas.faults import Fault

        # The genuine Table 20 defect: every value passes its limit, yet the Maximum cell is wrong.
        f = Fault(
            title="Table 20's Maximum theoretical plates (11477) contradicts higher value reported in In-house Equivalency Study row (12601)",
            detail=("Every individual value is within the limits, and the Mean of 11041 matches. But the "
                    "In-house Equivalency Study row reports 12601, which exceeds the stated maximum of 11477 — "
                    "an internal contradiction in the same table."),
        )
        out = verify_and_tier([f], self._doc())
        assert len(out) == 1, "the real cross-table contradiction must survive the concession gate"

