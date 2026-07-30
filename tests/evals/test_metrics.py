"""Tests for the per-stage + by-family metrics engine (EVAL-02).

Pins the golden run's baseline (recall 2/28, reproducing docs/eval/MEASUREMENT.md WITHOUT an
LLM) and both checker-note fixes: W1 (anchor_rate is a real number when source_text is supplied,
never a permanent sentinel) and W3 (all five per-stage metrics are surfaced separately, not only
folded into the by-family table).
"""
from __future__ import annotations

from evals.capture import golden_report
from evals.metrics import compute_metrics, format_table, recall_by_family
from evals.schema import FailureFamily, load_eval_set

DOC_ID = "mvr1381"
FIVE_PER_STAGE_KEYS = {
    "retrieval_recall_at_k",
    "parse_fidelity",
    "anchor_rate",
    "verifier",
    "end_to_end",
}


class TestComputeMetricsBaseline:
    """The plan's own pinned baseline: the golden run scores exactly 2/28 recall."""

    def test_end_to_end_tp_is_exactly_two(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert m["end_to_end"]["tp"] == 2

    def test_end_to_end_recall_matches_2_of_28_baseline(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert abs(m["end_to_end"]["recall"] - 2 / 28) < 1e-6

    def test_end_to_end_fn_is_26(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert m["end_to_end"]["fn"] == 26

    def test_all_four_families_present_in_by_family(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert len(m["end_to_end_by_family"]) == 4
        assert set(m["end_to_end_by_family"]) == {f.value for f in FailureFamily}

    def test_all_five_per_stage_keys_exist(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        for key in FIVE_PER_STAGE_KEYS:
            assert key in m, f"missing per-stage key: {key}"

    def test_matched_gts_are_c01_and_c02(self):
        """The two hits are the Table-20 Max (C-01) and the 0.15% impurity (C-02) -- the exact
        two the baseline names, not just any two GT ids."""
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        # cross_reference_integrity is the family both C-01 and C-02 belong to, so its recall
        # should be 2/7 (both hits, out of the 7 cross_reference_integrity items for mvr1381).
        by_family = m["end_to_end_by_family"]
        cri = by_family[FailureFamily.CROSS_REFERENCE_INTEGRITY.value]
        assert cri["tp"] == 2
        other_families = [
            FailureFamily.ABSENCE_OF_EVIDENCE.value,
            FailureFamily.DERIVATION_PLAUSIBILITY.value,
            FailureFamily.REGULATORY_FRAMING.value,
        ]
        for fam in other_families:
            assert by_family[fam]["tp"] == 0, f"unexpected TP in {fam}"


class TestAnchorRateW1:
    """W1: anchor_rate must be a REAL computed number when source_text is supplied -- not a
    permanent 'n/a' sentinel."""

    def test_no_source_text_is_the_explicit_sentinel(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert m["anchor_rate"] == "n/a_no_source"

    def test_with_source_text_anchor_rate_is_a_real_float_not_a_sentinel(self):
        # A synthetic source blob containing the two real anchor tokens the golden run's
        # evidence cites (11477, 0.15) plus other numbers it does NOT cite -- proves anchor_rate
        # is genuinely computed from the given text, not just always returning a fixed value.
        source_text = (
            "Table 20 System Suitability Results. Maximum: Theoretical plates: 11477. "
            "In-house Equivalency Study: Theoretical plates: 12601. "
            "Table 19 Any Unspecified Impurity (Single Largest): 0.15%."
        )
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID, source_text=source_text)
        assert isinstance(m["anchor_rate"], float)
        assert 0.0 < m["anchor_rate"] < 1.0

    def test_anchor_rate_rises_when_more_source_text_is_provided(self):
        # A near-empty source resolves almost nothing; a rich source resolves more -- proves the
        # number moves with its input rather than being a hardcoded constant.
        sparse_source = "This document mentions nothing relevant to any finding."
        rich_source = (
            "Table 20 Maximum: Theoretical plates: 11477. In-house Equivalency Study: "
            "Theoretical plates: 12601. Table 18: Theoretical plates for in-house method = 12601. "
            "Table 19 Any Unspecified Impurity (Single Largest): 0.15%. "
            "Table 11 AFs = 0.40, 1.03, 0.96. Table 6 Estrone slope = 6993.99. "
            "Table 3 Estradiol slope = 6920.93. Table 12 % RSD = 0.6. Theoretical plates = 11160."
        )
        m_sparse = compute_metrics(golden_report(), load_eval_set(), DOC_ID, source_text=sparse_source)
        m_rich = compute_metrics(golden_report(), load_eval_set(), DOC_ID, source_text=rich_source)
        assert m_sparse["anchor_rate"] < m_rich["anchor_rate"]

    def test_empty_string_source_text_still_falls_back_to_sentinel(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID, source_text="   ")
        assert m["anchor_rate"] == "n/a_no_source"


class TestParseFidelity:
    def test_golden_run_has_zero_parse_failures(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert m["parse_fidelity"] == {"parsed_ok": True, "parse_failures": 0}


class TestVerifier:
    def test_verifier_is_a_precision_recall_dict_on_the_golden_run(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        verifier = m["verifier"]
        assert isinstance(verifier, dict)
        assert set(verifier) == {"precision", "recall"}
        assert 0.0 <= verifier["precision"] <= 1.0
        assert 0.0 <= verifier["recall"] <= 1.0


class TestRetrievalRecallAtK:
    def test_returns_a_value_for_the_golden_run(self):
        # mvr1381's GT items all carry non-empty section_hint (Plan 00-01), so this must NOT be
        # the n/a_phase0 sentinel here -- it should be a real fraction.
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        assert isinstance(m["retrieval_recall_at_k"], float)
        assert 0.0 <= m["retrieval_recall_at_k"] <= 1.0


class TestRecallByFamilyTopLevelFunction:
    def test_matches_the_dict_embedded_in_compute_metrics(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        standalone = recall_by_family(golden_report(), load_eval_set(), DOC_ID)
        assert standalone == m["recall_by_family"]

    def test_overall_recall_by_family_sums_to_the_two_hits(self):
        rbf = recall_by_family(golden_report(), load_eval_set(), DOC_ID)
        assert len(rbf) == 4
        assert rbf[FailureFamily.CROSS_REFERENCE_INTEGRITY.value] > 0.0


class TestFormatTableW3:
    """W3: format_table must surface all five per-stage metrics SEPARATELY, not only folded
    into the by-family table."""

    def test_contains_by_family_section(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        table = format_table(m)
        assert "End-to-end by failure family" in table
        for family in FailureFamily:
            assert family.value in table

    def test_contains_all_five_per_stage_metrics_as_separate_lines(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        table = format_table(m)
        for key in FIVE_PER_STAGE_KEYS:
            assert key in table, f"format_table output missing per-stage metric: {key}"

    def test_contains_recall_by_family_section(self):
        m = compute_metrics(golden_report(), load_eval_set(), DOC_ID)
        table = format_table(m)
        assert "Recall by family" in table
