"""retrieval.hybrid.reciprocal_rank_fusion -- the public RRF formula, hand-verified (D-RB5).

score = sum(1/(k+rank_i)), 1-based rank, k=60 -- no library, no LanceDB (superseded D-RB2/D-RB5).
"""
from __future__ import annotations

import pytest

from retrieval.hybrid import reciprocal_rank_fusion


def test_rrf_matches_hand_computed_formula_and_orders_descending():
    # list1 = ["a","b","c"] -> a rank1, b rank2, c rank3
    # list2 = ["c","a"]     -> c rank1, a rank2
    result = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a"]], k=60)
    scores = dict(result)

    assert scores["a"] == pytest.approx(1.0 / 61 + 1.0 / 62)
    assert scores["c"] == pytest.approx(1.0 / 63 + 1.0 / 61)
    assert scores["b"] == pytest.approx(1.0 / 62)

    # a (rank1 in both) outranks c (rank3 then rank1), which outranks b (rank2, only one list)
    ids_in_order = [item_id for item_id, _score in result]
    assert ids_in_order.index("a") < ids_in_order.index("c") < ids_in_order.index("b")

    # sorted descending by score -- never ascending, never unsorted
    all_scores = [s for _id, s in result]
    assert all_scores == sorted(all_scores, reverse=True)


def test_rrf_empty_rankings_returns_empty_list_never_raises():
    assert reciprocal_rank_fusion([[], []]) == []
    assert reciprocal_rank_fusion([]) == []


def test_rrf_id_in_only_one_ranking_is_not_dropped():
    result = reciprocal_rank_fusion([["x"], []], k=60)
    scores = dict(result)
    assert "x" in scores
    assert scores["x"] == pytest.approx(1.0 / 61)


def test_rrf_default_k_is_60():
    # confirms the default k parameter itself is 60 (D-RB5's locked constant), not just a
    # value some caller happens to pass -- calling with no explicit k must match k=60 exactly.
    result_default = reciprocal_rank_fusion([["only"]])
    result_explicit = reciprocal_rank_fusion([["only"]], k=60)
    assert dict(result_default)["only"] == pytest.approx(dict(result_explicit)["only"])
    assert dict(result_default)["only"] == pytest.approx(1.0 / 61)
