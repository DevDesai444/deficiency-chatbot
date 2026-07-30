"""Unit tests for the ground-truth eval-set schema and loader."""
from __future__ import annotations

from evals.schema import Confidence, FailureFamily, load_eval_set


class TestLoadEvalSet:
    def test_loads_without_error(self):
        eval_set = load_eval_set()
        assert eval_set is not None

    def test_mvr1381_tuning_set_has_exactly_28_deficiencies(self):
        """The canonical estradiol tuning set (doc_id=mvr1381) stays pinned at
        exactly 28 -- scoped by doc_id, not a raw total, because Plan 00-02's
        breadth expansion intentionally adds further *.deficiencies.json files
        that `load_eval_set()` globs in alongside this one (see
        tests/evals/test_breadth.py for the >=34 whole-set assertion).
        """
        eval_set = load_eval_set()
        mvr1381_deficiencies = [d for d in eval_set.deficiencies if d.doc_id == "mvr1381"]
        assert len(mvr1381_deficiencies) == 28

    def test_every_deficiency_has_a_non_empty_evidence_anchor(self):
        eval_set = load_eval_set()
        for deficiency in eval_set.deficiencies:
            assert deficiency.evidence_anchor.strip() != "", (
                f"{deficiency.id} has an empty evidence_anchor"
            )

    def test_family_set_covers_all_four_failure_families(self):
        eval_set = load_eval_set()
        assert eval_set.families() == {
            FailureFamily.ABSENCE_OF_EVIDENCE,
            FailureFamily.DERIVATION_PLAUSIBILITY,
            FailureFamily.CROSS_REFERENCE_INTEGRITY,
            FailureFamily.REGULATORY_FRAMING,
        }

    def test_exactly_two_tp_required(self):
        eval_set = load_eval_set()
        assert len(eval_set.tp_required()) == 2

    def test_at_least_eight_certain_confidence(self):
        eval_set = load_eval_set()
        certain_count = sum(
            1 for d in eval_set.deficiencies if d.confidence == Confidence.CERTAIN
        )
        assert certain_count >= 8

    def test_tp_required_anchors_contain_the_two_pinned_findings(self):
        eval_set = load_eval_set()
        tp_anchors = {d.id: d.evidence_anchor for d in eval_set.tp_required()}
        assert any("11477" in anchor for anchor in tp_anchors.values()), tp_anchors
        assert any("0.15" in anchor for anchor in tp_anchors.values()), tp_anchors

    def test_documents_registry_contains_mvr1381(self):
        eval_set = load_eval_set()
        doc_ids = {doc.doc_id for doc in eval_set.documents}
        assert "mvr1381" in doc_ids
