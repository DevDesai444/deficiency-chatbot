"""Tests for the zero-true-positives-lost CI gate (EVAL-03)."""
from __future__ import annotations

from evals.capture import golden_report
from evals.gate import GateResult, baseline_found_ids, check_gate, true_positives_lost
from evals.schema import load_eval_set

DOC_ID = "mvr1381"
BASELINE = {"C-01", "C-02"}


class TestBaselineFoundIds:
    def test_tp_required_ids_are_always_protected(self):
        eval_set = load_eval_set()
        assert baseline_found_ids(eval_set) == {"C-01", "C-02"}

    def test_extra_ids_are_unioned_in(self):
        eval_set = load_eval_set()
        assert baseline_found_ids(eval_set, extra={"Z-99"}) == {"C-01", "C-02", "Z-99"}


class TestCheckGatePassesOnGoldenRun:
    def test_golden_run_passes_for_the_pinned_baseline(self):
        g = check_gate(golden_report(), load_eval_set(), DOC_ID, BASELINE)
        assert isinstance(g, GateResult)
        assert g.ok is True
        assert g.lost == set()

    def test_golden_run_matched_set_contains_both_anchors(self):
        g = check_gate(golden_report(), load_eval_set(), DOC_ID, BASELINE)
        assert BASELINE <= g.matched

    def test_a_run_that_finds_more_than_baseline_still_passes(self):
        # Superset is fine -- only LOSING a previously-found TP fails the gate.
        g = check_gate(golden_report(), load_eval_set(), DOC_ID, {"C-01"})
        assert g.ok is True
        assert g.lost == set()


class TestCheckGateFailsWhenATrueDeficiencyDisappears:
    def test_doctored_report_missing_table20_evidence_loses_c01(self):
        # Every golden-run finding that could match C-01 cites "11477" verbatim (the Table 20
        # Maximum-theoretical-plates anchor) -- stripping every fault whose evidence contains it
        # removes ALL possible matches for C-01, simulating "the Table-20 finding disappeared"
        # without hand-picking indices that would silently go stale if the fixture is edited.
        original = golden_report()
        doctored_faults = [f for f in original.faults if "11477" not in f.evidence]
        assert len(doctored_faults) < len(original.faults), "fixture no longer contains a C-01 anchor"
        doctored = original.model_copy(update={"faults": doctored_faults})

        g = check_gate(doctored, load_eval_set(), DOC_ID, BASELINE)

        assert g.ok is False
        assert g.lost == {"C-01"}
        # C-02 (the 0.15% impurity) is untouched by removing the Table 20 findings.
        assert "C-02" in g.matched

    def test_true_positives_lost_alias_matches_gate_result_lost(self):
        original = golden_report()
        doctored_faults = [f for f in original.faults if "11477" not in f.evidence]
        doctored = original.model_copy(update={"faults": doctored_faults})

        lost = true_positives_lost(doctored, load_eval_set(), DOC_ID, BASELINE)

        assert lost == {"C-01"}

    def test_losing_both_anchors_names_both(self):
        original = golden_report()
        doctored_faults = [
            f for f in original.faults if "11477" not in f.evidence and "0.15" not in f.evidence
        ]
        doctored = original.model_copy(update={"faults": doctored_faults})

        g = check_gate(doctored, load_eval_set(), DOC_ID, BASELINE)

        assert g.ok is False
        assert g.lost == {"C-01", "C-02"}
