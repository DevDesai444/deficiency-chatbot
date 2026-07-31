"""Tests for the per-stage + by-family metrics engine (EVAL-02).

Pins the golden run's baseline (recall 2/28, reproducing docs/eval/MEASUREMENT.md WITHOUT an
LLM) and both checker-note fixes: W1 (anchor_rate is a real number when source_text is supplied,
never a permanent sentinel) and W3 (all five per-stage metrics are surfaced separately, not only
folded into the by-family table).

Plan 02-07 (SC4) adds `TestSearchCorpusRecallAtK` + `TestComputeMetricsCorpusAdditive` below,
exercising the real `search_corpus`-driven upgrade of the Phase-0 `_retrieval_recall_at_k` proxy.
These deliberately do NOT route through `golden_report()`/`compute_metrics(...)` with a non-empty
`FaultReport.faults` list for `mvr1381` -- `report.faults[i].cited_section_indices` is read by the
UNTOUCHED Phase-0 proxy (`_retrieval_recall_at_k`, line ~90) and that field does not exist on the
current (import-only, uncommitted-redesign) `schemas.faults.Fault` model, a PRE-EXISTING failure
unrelated to this plan (see `TestRetrievalRecallAtK`/most of `TestComputeMetricsBaseline` above,
already failing on `main` before this plan for the same reason). `schemas/faults.py` is
import-only for this plan -- not touched here.
"""
from __future__ import annotations

import numpy as np

from evals.capture import golden_report
from evals.match import _TOKEN_RE
from evals.metrics import _search_corpus_recall_at_k, compute_metrics, format_table, recall_by_family
from evals.schema import EvalSet, FailureFamily, GroundTruthDeficiency, load_eval_set
from schemas.faults import FaultReport
from tests.tools.conftest import build_corpus_index

DOC_ID = "mvr1381"
FIVE_PER_STAGE_KEYS = {
    "retrieval_recall_at_k",
    "parse_fidelity",
    "anchor_rate",
    "verifier",
    "end_to_end",
}


def _blk(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


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


class TestSearchCorpusRecallAtK:
    """SC4: `_search_corpus_recall_at_k` -- the real `search_corpus`-driven upgrade, additive to
    the untouched Phase-0 `_retrieval_recall_at_k` proxy above. Uses a small REAL `CorpusIndex`
    (`tests.tools.conftest.build_corpus_index` -- the same offline substrate-routing fixture Plan
    02-04's own `tests/tools/test_search_corpus.py` uses) with the dense leg mocked to a fixed
    vector for speed/determinism; the real BM25 lexical leg + real `reciprocal_rank_fusion`
    combiner both still run for real.
    """

    SEARCH_DOC_ID = "sc07-doc"

    def _corpus(self, tmp_path, text: str):
        return build_corpus_index(tmp_path, self.SEARCH_DOC_ID, [_blk(text)])

    def _mock_dense(self, monkeypatch):
        import tools.search_corpus as sc_module

        monkeypatch.setattr(
            sc_module,
            "embed_texts",
            lambda texts, batch_size=8: np.array([[1.0, 0.0]] * len(texts), dtype=np.float32),
        )
        monkeypatch.setattr(
            sc_module, "embed_query", lambda text: np.array([1.0, 0.0], dtype=np.float32)
        )

    def test_na_no_gt_sentinel_when_doc_has_no_gt_items(self, tmp_path):
        eval_set = EvalSet(deficiencies=[])
        corpus = self._corpus(tmp_path, "Irrelevant content unrelated to any deficiency.")
        assert _search_corpus_recall_at_k(eval_set, self.SEARCH_DOC_ID, corpus) == "n/a_no_gt"

    def test_numeric_anchor_is_covered_and_classified_as_hard_subset(self, tmp_path, monkeypatch):
        """A numeric/identifier evidence_anchor (matches evals.match._TOKEN_RE, the SAME token
        pattern reused verbatim, not reinvented) is both covered AND counted in the hard subset."""
        self._mock_dense(monkeypatch)
        assert _TOKEN_RE.search("11477")  # sanity: this anchor IS the hard-subset pattern
        corpus = self._corpus(
            tmp_path, "Table 20 Maximum theoretical plates recorded as 11477 in the summary row."
        )
        gt = GroundTruthDeficiency(
            id="X-01",
            doc_id=self.SEARCH_DOC_ID,
            title="Table 20 Maximum theoretical plates cell disagreement",
            evidence_anchor="11477",
            failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
        )
        eval_set = EvalSet(deficiencies=[gt])

        result = _search_corpus_recall_at_k(eval_set, self.SEARCH_DOC_ID, corpus)

        assert result == {"overall": 1.0, "exact_identifier_subset": 1.0, "n": 1, "n_hard": 1}

    def test_word_anchor_is_covered_but_excluded_from_hard_subset(self, tmp_path, monkeypatch):
        self._mock_dense(monkeypatch)
        assert not _TOKEN_RE.search("control sample")  # sanity: NOT the hard-subset pattern
        corpus = self._corpus(tmp_path, "The control sample produced no reportable peak.")
        gt = GroundTruthDeficiency(
            id="X-02",
            doc_id=self.SEARCH_DOC_ID,
            title="No result reported for the control sample",
            evidence_anchor="control sample",
            failure_family=FailureFamily.ABSENCE_OF_EVIDENCE,
        )
        eval_set = EvalSet(deficiencies=[gt])

        result = _search_corpus_recall_at_k(eval_set, self.SEARCH_DOC_ID, corpus)

        assert result["overall"] == 1.0
        assert result["exact_identifier_subset"] == "n/a_no_hard_subset"
        assert result["n"] == 1
        assert result["n_hard"] == 0

    def test_hard_subset_is_computed_separately_from_a_mixed_gt_set(self, tmp_path, monkeypatch):
        """Two GT items -- one numeric (hard, findable), one word-anchored (soft, NOT present in
        the corpus at all) -- proves the hard-subset fraction is computed over ONLY the hard
        items, independent of the overall fraction being dragged down by the unfindable item."""
        self._mock_dense(monkeypatch)
        corpus = self._corpus(tmp_path, "Batch 20038 showed 0.3 percent degradation after storage.")
        hard_gt = GroundTruthDeficiency(
            id="X-03",
            doc_id=self.SEARCH_DOC_ID,
            title="Batch degradation figure reported",
            evidence_anchor="20038",
            failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
        )
        unfindable_soft_gt = GroundTruthDeficiency(
            id="X-04",
            doc_id=self.SEARCH_DOC_ID,
            title="Accuracy was never demonstrated for this batch",
            evidence_anchor="accuracy demonstration",
            failure_family=FailureFamily.ABSENCE_OF_EVIDENCE,
        )
        eval_set = EvalSet(deficiencies=[hard_gt, unfindable_soft_gt])

        result = _search_corpus_recall_at_k(eval_set, self.SEARCH_DOC_ID, corpus)

        assert result["n"] == 2
        assert result["n_hard"] == 1
        assert result["exact_identifier_subset"] == 1.0  # the hard item alone is covered
        assert result["overall"] == 0.5  # 1 of 2 total GT items covered

    def test_anchor_absent_from_corpus_is_not_covered(self, tmp_path, monkeypatch):
        self._mock_dense(monkeypatch)
        corpus = self._corpus(tmp_path, "This document mentions nothing relevant to any finding.")
        gt = GroundTruthDeficiency(
            id="X-05",
            doc_id=self.SEARCH_DOC_ID,
            title="A number that never appears anywhere in this document",
            evidence_anchor="99999",
            failure_family=FailureFamily.DERIVATION_PLAUSIBILITY,
        )
        eval_set = EvalSet(deficiencies=[gt])

        result = _search_corpus_recall_at_k(eval_set, self.SEARCH_DOC_ID, corpus)

        assert result["overall"] == 0.0
        assert result["exact_identifier_subset"] == 0.0


class TestComputeMetricsCorpusAdditive:
    """`compute_metrics`'s new optional `corpus` param is ADDITIVE, never breaking: omitting it
    (the default) reproduces the exact pre-existing dict shape; passing a corpus adds exactly one
    new key on top. Uses an EMPTY-faults `FaultReport` so `_retrieval_recall_at_k` (unmodified,
    still reads `fault.cited_section_indices` per-fault) never iterates a fault and so never hits
    the pre-existing, out-of-scope `cited_section_indices` AttributeError documented at the top of
    this file -- this test is about the additive `compute_metrics` contract, not about re-proving
    the Phase-0 proxy's own (already broken, already tracked) behavior.
    """

    SEARCH_DOC_ID = "sc07-additive-doc"

    def test_corpus_none_omits_the_new_key(self):
        empty_report = FaultReport(faults=[])
        eval_set = EvalSet(deficiencies=[])
        metrics = compute_metrics(empty_report, eval_set, self.SEARCH_DOC_ID)
        assert "search_corpus_recall_at_k" not in metrics
        assert set(metrics) == {
            "end_to_end",
            "end_to_end_by_family",
            "recall_by_family",
            "retrieval_recall_at_k",
            "parse_fidelity",
            "anchor_rate",
            "verifier",
        }

    def test_corpus_given_adds_the_new_key_without_removing_any_existing_key(self, tmp_path, monkeypatch):
        import tools.search_corpus as sc_module

        monkeypatch.setattr(
            sc_module,
            "embed_texts",
            lambda texts, batch_size=8: np.array([[1.0, 0.0]] * len(texts), dtype=np.float32),
        )
        monkeypatch.setattr(
            sc_module, "embed_query", lambda text: np.array([1.0, 0.0], dtype=np.float32)
        )
        corpus = build_corpus_index(
            tmp_path, self.SEARCH_DOC_ID, [_blk("Impurity level recorded at 0.15 percent in the table.")]
        )
        gt = GroundTruthDeficiency(
            id="Y-01",
            doc_id=self.SEARCH_DOC_ID,
            title="Impurity level table entry",
            evidence_anchor="0.15",
            failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
        )
        empty_report = FaultReport(faults=[])
        eval_set = EvalSet(deficiencies=[gt])

        metrics = compute_metrics(empty_report, eval_set, self.SEARCH_DOC_ID, corpus=corpus)

        assert "search_corpus_recall_at_k" in metrics
        assert metrics["search_corpus_recall_at_k"]["overall"] == 1.0
        # every pre-existing key is still present, byte-for-byte the same keys as the no-corpus call
        no_corpus_metrics = compute_metrics(empty_report, eval_set, self.SEARCH_DOC_ID)
        assert set(no_corpus_metrics) < set(metrics)

    def test_format_table_prints_the_new_key_only_when_present(self):
        empty_report = FaultReport(faults=[])
        eval_set = EvalSet(deficiencies=[])
        no_corpus_metrics = compute_metrics(empty_report, eval_set, self.SEARCH_DOC_ID)
        assert "search_corpus_recall_at_k" not in format_table(no_corpus_metrics)

        with_key_metrics = dict(no_corpus_metrics)
        with_key_metrics["search_corpus_recall_at_k"] = {
            "overall": 1.0, "exact_identifier_subset": 1.0, "n": 1, "n_hard": 1,
        }
        assert "search_corpus_recall_at_k" in format_table(with_key_metrics)


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
