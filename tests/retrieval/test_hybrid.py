"""D-R5A: retrieval.hybrid RRF ceiling regression test + dense-score coverage verification.

These tests document WHY the old `score` field in search_corpus was a dead branch
(max RRF score 2/(60+1) = 0.0328 < 0.04 absence threshold) and confirm that the
D-R5A fix correctly stores the true dense cosine score for ALL fused chunk ids
(including lexical-only hits — Ruling 9 dense score coverage).
"""
from __future__ import annotations

from retrieval.hybrid import reciprocal_rank_fusion


def test_rrf_score_ceiling_below_absence_threshold():
    """D-R5A motivation: with k=60, max RRF score = 2/(60+1) ≈ 0.0328 < 0.04 threshold.

    When ranked_a and ranked_b both have the same item at rank 1, the maximum
    possible RRF score across N=2 lists is N/(k+1) = 2/61 ≈ 0.0328.
    absence.py used `top_score >= 0.04` with the old RRF score — a dead branch
    that was never True.  D-R5A replaces score with the dense cosine (0–1).
    """
    ranked_a = ["c1", "c2", "c3"]
    ranked_b = ["c1", "c2", "c3"]
    results = reciprocal_rank_fusion([ranked_a, ranked_b])
    max_score = max(score for _, score in results) if results else 0.0
    assert max_score <= 2 / 61 + 1e-9, f"RRF ceiling exceeded: {max_score}"
    ABSENCE_THRESHOLD = 0.04
    assert max_score < ABSENCE_THRESHOLD, (
        f"Dead branch confirmed: max RRF {max_score:.4f} < absence threshold {ABSENCE_THRESHOLD}"
    )


def test_rrf_ceiling_is_exactly_two_over_k_plus_one():
    """Algebraic proof: max score for N=2 identical-rank-1 lists, k=60, is 2/(60+1)."""
    expected_max = 2.0 / (60 + 1)
    results = reciprocal_rank_fusion([["top"], ["top"]], k=60)
    scores = dict(results)
    assert abs(scores["top"] - expected_max) < 1e-12


def test_dense_scores_cover_all_chunk_ids():
    """Ruling 9: dense_scores must cover all chunk_ids so lexical-only hits are not zeroed.

    Inspects search_corpus source to verify:
    - dense_scores is built with range(len(chunk_ids)) not just the dense_order subset
    - rrf_score is preserved as a separate field
    """
    import inspect
    import tools.search_corpus as m

    src = inspect.getsource(m)
    assert "dense_scores" in src, "dense_scores dict not found in search_corpus"
    assert "rrf_score" in src, "rrf_score field not found in search_corpus output"
    # Ruling 9: dense_scores must be built over range(len(chunk_ids)), not just dense_order
    # The key pattern: `for i in range(len(chunk_ids))`
    assert "range(len(chunk_ids))" in src, (
        "Ruling 9: dense_scores must be built over range(len(chunk_ids)) to cover ALL chunks, "
        "not just those in dense_order. Lexical-only hits must not be silently zeroed."
    )
    # Verify the correct variable name is used (all_scores, not the old `scores`)
    assert "all_scores" in src, (
        "D-R5A: cosine scores should be stored as all_scores to distinguish from old `scores`"
    )


def test_search_corpus_score_is_dense_cosine_not_rrf(tmp_path, monkeypatch):
    """D-R5A: search_corpus 'score' field must be the dense cosine (0-1), not the RRF score.

    The dense cosine for [1,0] query vs [1,0] doc embedding = 1.0.
    The RRF score for rank-1 with k=60 = 1/61 ≈ 0.0164.
    This test confirms score=1.0 (cosine) not score=0.0164 (RRF).
    """
    import numpy as np
    import tools.search_corpus as sc_module
    from tests.tools.conftest import build_corpus_index
    from tools.ledger import RetrievalLedger

    def _blk(text):
        return {"text": text, "page": 1, "reading_order": 0, "lines": []}

    corpus = build_corpus_index(
        tmp_path, "doc-score-test",
        [_blk("The stability protocol requires storage at 40C and 75% relative humidity.")],
    )
    # Mock embeddings: all chunks and query → [1, 0] → cosine = 1.0
    monkeypatch.setattr(sc_module, "embed_texts", lambda texts, batch_size=8: np.array(
        [[1.0, 0.0]] * len(texts), dtype=np.float32,
    ))
    monkeypatch.setattr(sc_module, "embed_query", lambda _t: np.array([1.0, 0.0], dtype=np.float32))

    ledger = RetrievalLedger()
    results = sc_module.search_corpus(corpus, "stability protocol", ledger, top_k=5)

    assert len(results) >= 1
    for r in results:
        # D-R5A: score is now cosine (=1.0 with mocked [1,0] embeddings), not RRF (≈0.0164)
        assert r["score"] > 0.9, (
            f"Expected dense cosine (~1.0), got {r['score']:.4f}. D-R5A not applied?"
        )
        # RRF score is preserved separately
        assert "rrf_score" in r
        assert r["rrf_score"] <= 2 / 61 + 1e-9, (
            f"rrf_score should be ≤ RRF ceiling 2/61, got {r['rrf_score']}"
        )
        # Score and rrf_score must be different (cosine >> RRF)
        assert r["score"] != r["rrf_score"]
