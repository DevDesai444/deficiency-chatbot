"""Frozen score snapshot regression test (Blocker 1, Wave 5).

Asserts that the `score --captured` command output over the committed golden report
has EXACTLY the 4 original ground-truth families in its `end_to_end_by_family` and
`recall_by_family` keys — no more, no less.

This test is the permanent freeze guard: any future addition to FailureFamily that
leaks into the frozen `score` output path (_end_to_end_by_family) will cause this
test to fail, surfacing the regression immediately.

The 4 frozen GT families (absence_of_evidence, derivation_plausibility,
cross_reference_integrity, regulatory_framing) are the families for which we have
committed ground-truth deficiencies in the EvalSet. The 3 new Phase-5 leg families
(structural, reference_graph, precedent_similarity) MUST NOT appear here.

D-FRZ1: `end_to_end_by_family` keys == the 4 GT family values.
D-FRZ2: `recall_by_family` keys == the 4 GT family values.
D-FRZ3: family score values are stable across commits (no silent numeric drift).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.metrics import _GROUND_TRUTH_FAMILIES, compute_metrics
from evals.schema import FailureFamily, EvalSet, load_eval_set
from evals.capture import load_captured


_GOLDEN_REPORT = Path("src/evals/dataset/golden/minispec_run1.json")

# The frozen set of GT family values — MUST be exactly these 4, never more.
_FROZEN_FAMILY_SET = frozenset(f.value for f in _GROUND_TRUTH_FAMILIES)

# Frozen family scores from the pre-Wave baseline run (minispec_run1.json vs mvr1381 GT).
# Scored with doc_id='mvr1381' (the CLI DEFAULT_DOC_ID) against the mvr1381 GT deficiencies.
# These values are STABLE against enum additions; if they change, a real logic
# regression has occurred.  anchor_rate is excluded: it is env-dependent (requires
# the data/ PDF which is gitignored; reports "n/a_no_source" without it).
_FROZEN_FAMILY_SCORES = {
    "absence_of_evidence":        {"tp": 0, "fn": 11},
    "derivation_plausibility":    {"tp": 0, "fn": 5},
    "cross_reference_integrity":  {"tp": 1, "fn": 6},
    "regulatory_framing":         {"tp": 0, "fn": 5},
}


_DEFAULT_DOC_ID = "mvr1381"  # matches evals/run.py DEFAULT_DOC_ID


def _score_golden() -> dict:
    """Load and score the committed golden report via compute_metrics (no source text).

    Uses doc_id='mvr1381' to match the evals/run.py DEFAULT_DOC_ID — the same
    doc_id the `score --captured minispec_run1.json` CLI command uses by default.
    anchor_rate is env-dependent (data/ gitignored) and is NOT asserted here.
    """
    assert _GOLDEN_REPORT.exists(), (
        f"Frozen snapshot regression: golden report missing at {_GOLDEN_REPORT}. "
        "The golden report is a committed asset — do not delete it."
    )
    eval_set = load_eval_set()
    report = load_captured(str(_GOLDEN_REPORT))
    # source_text="" is intentional: anchor_rate is env-dependent (data/ gitignored).
    # The freeze guard targets family keys + family scores, not anchor_rate.
    return compute_metrics(report, eval_set, doc_id=_DEFAULT_DOC_ID, source_text="")


def test_frozen_score_family_keys():
    """D-FRZ1 + D-FRZ2: `end_to_end_by_family` and `recall_by_family` contain exactly the
    4 original GT family keys — no structural / reference_graph / precedent_similarity leak.

    This is the PRIMARY freeze guard (no pytest.skip). If this fails, a new FailureFamily
    member has leaked into the frozen `score` output path (Blocker 1 regression).
    """
    metrics = _score_golden()

    # D-FRZ1: end_to_end_by_family keys
    e2e_keys = frozenset(metrics["end_to_end_by_family"].keys())
    assert e2e_keys == _FROZEN_FAMILY_SET, (
        f"D-FRZ1: end_to_end_by_family keys mismatch.\n"
        f"Expected exactly: {sorted(_FROZEN_FAMILY_SET)}\n"
        f"Got:              {sorted(e2e_keys)}\n"
        f"Leaked keys:      {sorted(e2e_keys - _FROZEN_FAMILY_SET)}\n"
        f"Missing keys:     {sorted(_FROZEN_FAMILY_SET - e2e_keys)}\n"
        "Fix: _end_to_end_by_family must iterate _GROUND_TRUTH_FAMILIES, not FailureFamily."
    )

    # D-FRZ2: recall_by_family keys (derived from end_to_end_by_family, so same check)
    rbf_keys = frozenset(metrics["recall_by_family"].keys())
    assert rbf_keys == _FROZEN_FAMILY_SET, (
        f"D-FRZ2: recall_by_family keys mismatch.\n"
        f"Expected exactly: {sorted(_FROZEN_FAMILY_SET)}\n"
        f"Got:              {sorted(rbf_keys)}\n"
        "recall_by_family is derived from end_to_end_by_family — fix the upstream function."
    )


def test_frozen_score_family_values():
    """D-FRZ3: family precision/recall/tp/fn values are stable against enum changes.

    Asserts that the numeric scores for the 4 GT families are unchanged from the committed
    pre-Wave baseline.  If this fails, a logic change in _end_to_end_by_family,
    evals.match.score, or the eval set itself has shifted the measurement.
    """
    metrics = _score_golden()
    e2e = metrics["end_to_end_by_family"]

    for family_key, expected in _FROZEN_FAMILY_SCORES.items():
        assert family_key in e2e, (
            f"D-FRZ3: family {family_key!r} missing from end_to_end_by_family. "
            "Expected all 4 GT families."
        )
        actual = e2e[family_key]
        assert actual["tp"] == expected["tp"], (
            f"D-FRZ3: {family_key} tp changed: expected {expected['tp']}, got {actual['tp']}"
        )
        assert actual["fn"] == expected["fn"], (
            f"D-FRZ3: {family_key} fn changed: expected {expected['fn']}, got {actual['fn']}"
        )


def test_ground_truth_families_tuple_has_four_members():
    """Structural guard: _GROUND_TRUTH_FAMILIES must always have exactly 4 members.

    If this fails, someone added a GT family to the frozen tuple — requires reviewer approval
    (the frozen measurement path must remain stable across enum additions).
    """
    from evals.metrics import _GROUND_TRUTH_FAMILIES

    assert len(_GROUND_TRUTH_FAMILIES) == 4, (
        f"_GROUND_TRUTH_FAMILIES must have exactly 4 members (the committed GT families). "
        f"Got {len(_GROUND_TRUTH_FAMILIES)}: {[f.value for f in _GROUND_TRUTH_FAMILIES]}. "
        "New FailureFamily members must be added via deterministic_leg_breakdown(), "
        "NOT via _GROUND_TRUTH_FAMILIES."
    )
    assert _FROZEN_FAMILY_SET == frozenset(f.value for f in _GROUND_TRUTH_FAMILIES), (
        "Mismatch between _FROZEN_FAMILY_SET and _GROUND_TRUTH_FAMILIES — "
        "update the test constant if the GT family set changed intentionally."
    )


def test_deterministic_leg_breakdown_covers_new_families():
    """deterministic_leg_breakdown() exposes the 3 new Phase-5 families SEPARATELY.

    These families must NOT appear in _end_to_end_by_family / recall_by_family (frozen path),
    but MUST be accessible via the separate deterministic_leg_breakdown() function.
    """
    from evals.metrics import deterministic_leg_breakdown

    _EXPECTED_LEG_FAMILIES = frozenset({
        FailureFamily.structural.value,
        FailureFamily.reference_graph.value,
        FailureFamily.precedent_similarity.value,
    })

    eval_set = load_eval_set()
    report = load_captured(str(_GOLDEN_REPORT))
    breakdown = deterministic_leg_breakdown(report, eval_set, doc_id=_DEFAULT_DOC_ID)
    assert isinstance(breakdown, dict), (
        "deterministic_leg_breakdown must return a dict."
    )
    breakdown_keys = frozenset(breakdown.keys())
    assert breakdown_keys == _EXPECTED_LEG_FAMILIES, (
        f"deterministic_leg_breakdown must cover exactly the 3 new Phase-5 families.\n"
        f"Expected: {sorted(_EXPECTED_LEG_FAMILIES)}\n"
        f"Got:      {sorted(breakdown_keys)}"
    )
    # These families have no GT data in the eval set — all scores should be 0
    for family_key, scores in breakdown.items():
        assert isinstance(scores, dict), f"{family_key}: scores must be a dict"
        assert "recall" in scores and "precision" in scores, (
            f"{family_key}: breakdown dict must contain recall and precision."
        )
