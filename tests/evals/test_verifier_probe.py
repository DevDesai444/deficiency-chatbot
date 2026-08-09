"""DeepEval harness shells for D-06a / D-06b / D-14 / D-18 — Nemotron verifier probe.

Shape requirements (D-06b amendment 2026-08-09):
  1. MATCHED_GT_IDS is LOADED from beta-measurement-summary.json (not a hardcoded
     duplicate literal). The JSON is the single source of truth.
  2. load_probe_samples() asserts len(keep_expected) == 6.
  3. DiscriminationAccuracyMetric expresses per-class floors (KEEP-recall AND
     DOWNGRADE-rate), NOT pooled correct/total.
  4. test_all_downgrade_stub_fails shell asserts that an all-DOWNGRADE stub verifier
     MUST FAIL the suite (two-sided tripwire: downgrade_ratio >= 0.90).

All live-endpoint tests are marked @pytest.mark.integration and skipped pending
Nemotron deployment (D-20 gate). The two invariant tests (test_matched_gt_ids_loaded
_from_json and test_baseline_numbers_are_locked_as_literals) run immediately.

DeepEval import is guarded: if deepeval is not installed, all DeepEval-dependent
tests are skipped at runtime (not at collection time). pytest --collect-only always
exits 0 regardless of whether deepeval is installed.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Beta-measurement source of truth
# ---------------------------------------------------------------------------

BETA_SUMMARY_PATH = Path(
    ".planning/phases/05-deterministic-structural-cross-document-recall"
    "/beta-measurement/beta-measurement-summary.json"
)


def _load_matched_gt_ids() -> frozenset:
    """Load KEEP-expected IDs from the canonical JSON source.

    Do NOT duplicate this as a hardcoded literal — the JSON is the single
    source of truth. Any discrepancy between this set and the JSON means
    the probe labels are wrong.
    """
    summary = json.loads(BETA_SUMMARY_PATH.read_text())
    ids: set = set()
    for doc_data in summary.get("docs", {}).values():
        ids.update(doc_data.get("matched_gt_ids", []))
    return frozenset(ids)


# Load at module level so tests can inspect it
MATCHED_GT_IDS: frozenset = _load_matched_gt_ids()


# ---------------------------------------------------------------------------
# DeepEval import guard — runtime only, never at collection time
# ---------------------------------------------------------------------------

def _require_deepeval():
    """Import deepeval or skip the calling test if not installed."""
    try:
        return importlib.import_module("deepeval")
    except ImportError:
        pytest.skip("deepeval not installed — run: pip install deepeval==4.1.4")


def _require_deepeval_metrics():
    """Import deepeval.metrics or skip."""
    try:
        return importlib.import_module("deepeval.metrics")
    except ImportError:
        pytest.skip("deepeval not installed — run: pip install deepeval==4.1.4")


def _require_deepeval_test_case():
    """Import deepeval.test_case or skip."""
    try:
        return importlib.import_module("deepeval.test_case")
    except ImportError:
        pytest.skip("deepeval not installed — run: pip install deepeval==4.1.4")


# ---------------------------------------------------------------------------
# Probe sample loader (Wave 3 implementation target)
# ---------------------------------------------------------------------------

def load_probe_samples():
    """Load probe samples from the beta-measurement dataset.

    Returns (keep_expected, downgrade_expected) tuple where:
      - keep_expected: list of candidate IDs from MATCHED_GT_IDS (KEEP-labeled)
      - downgrade_expected: list of known-planted-bad candidate IDs (DOWNGRADE-labeled)

    Invariant: len(keep_expected) == 6 (5 mvr1381 + 1 minispec matched GT IDs).
    If this assertion fails, beta-measurement-summary.json has changed or the load
    logic is wrong.
    """
    # KEEP-expected = the 6 matched GT IDs loaded from JSON
    keep_expected = sorted(MATCHED_GT_IDS)
    assert len(keep_expected) == 6, (
        f"Expected 6 KEEP-expected IDs (5 mvr1381 + 1 minispec); "
        f"got {len(keep_expected)}: {keep_expected}. "
        "If Phase 5 re-ran with more matches, update D-05 in 06-CONTEXT.md "
        "and re-confirm the known-planted-bad subset."
    )

    # DOWNGRADE-expected = known-planted-bad subset (hand-verified confirmed-false FPs)
    # The 97 UNRESOLVED_REF candidates are EXCLUDED from the scored denominator.
    # This list is populated in Wave 3 when the labeled probe dataset is committed.
    downgrade_expected: list = []  # placeholder until Wave 3 labeling

    return keep_expected, downgrade_expected


# ---------------------------------------------------------------------------
# DeepEval metric stubs
# ---------------------------------------------------------------------------

class ConformanceRateMetric:
    """D-06a: ≥98% machine-parsable VERDICT post-repair, per thinking mode.

    Full implementation in Plan 06 Task 1 after Plan 05 (Nemotron live).
    This is a shell — BaseMetric will be used in the real implementation.
    """
    threshold = 0.98
    name = "conformance_rate"
    score: float = 0.0

    def measure(self, test_case) -> float:
        raise NotImplementedError(
            "Implement after Plan 03 (reliability.py) + Plan 05 (Nemotron live)"
        )

    def is_successful(self) -> bool:
        return self.score >= self.threshold


class DiscriminationAccuracyMetric:
    """D-06b (amended 2026-08-09): TWO SEPARATE hard assertions over the defensible labeled subset.

    Scored denominator = known-good (6 matched-GT) union known-planted-bad (hand-verified
    confirmed-false FPs). The unverified 'unmatched-but-not-confirmed-false' middle
    (97 UNRESOLVED_REF + fn_gt_ids tail) is EXCLUDED from scoring.

    Two independent hard assertions (both must pass):
      - KEEP-recall floor: keep_correct / 6 >= 0.80 (recall-critical)
      - DOWNGRADE-rate floor: downgrade_correct / |known-planted-bad| >= 0.80 (precision)

    Two-sided tripwire: sets score=0.0 if keep_ratio >= 0.95 (blanket-KEEP)
    OR downgrade_ratio >= 0.90 (blanket-DOWNGRADE — the 6:109 recall-destroying case).
    Both directions tested by test_all_downgrade_stub_fails.

    Implementation note: keep_ratio and downgrade_ratio in the tripwire refer to the
    FRACTION of the scored pool labeled as KEEP or DOWNGRADE by the verifier — NOT the
    per-class accuracy. A verifier that emits DOWNGRADE for everything has downgrade_ratio=1.0
    which fires the tripwire, setting score=0.0 and failing is_successful().
    """
    threshold = 0.80  # each per-class floor independently
    name = "discrimination_accuracy"
    score: float = 0.0

    def measure(self, test_case) -> float:
        raise NotImplementedError(
            "Implement in Plan 06 Task 1 after Plan 05 (Nemotron live)"
        )

    def is_successful(self) -> bool:
        # In full implementation: BOTH keep_recall >= 0.80 AND downgrade_rate >= 0.80
        # and NEITHER tripwire fired (keep_ratio < 0.95 AND downgrade_ratio < 0.90)
        return self.score >= self.threshold


# ---------------------------------------------------------------------------
# Invariant tests — run immediately (no live endpoint required)
# ---------------------------------------------------------------------------

def test_matched_gt_ids_loaded_from_json():
    """Invariant: MATCHED_GT_IDS is loaded from the JSON source and has exactly 6 entries.

    If this fails, the beta-measurement-summary.json has changed or load_probe_samples
    would be operating on a corrupted KEEP-expected set.
    """
    assert len(MATCHED_GT_IDS) == 6, (
        f"Expected 6 matched-GT IDs (5 mvr1381 + 1 minispec); got {len(MATCHED_GT_IDS)}: "
        f"{sorted(MATCHED_GT_IDS)}. If Phase 5 re-ran with more matches, update D-05 in "
        "06-CONTEXT.md and re-confirm the known-planted-bad subset."
    )
    assert "MS-01" in MATCHED_GT_IDS, "minispec MS-01 must be in KEEP-expected"
    assert "A-09" in MATCHED_GT_IDS, "mvr1381 A-09 must be in KEEP-expected"


def test_all_downgrade_stub_fails():
    """D-06b tripwire test: a stub verifier that always returns DOWNGRADE MUST FAIL the suite.

    This test proves the two-sided tripwire (downgrade_ratio >= 0.90 fires and sets
    score=0.0) catches the recall-destroying verifier — the exact failure mode the
    cross-AI review caught 2026-08-09: a near-constant-DOWNGRADE model scoring ~0.94
    on pooled correct/total over the 6:109 split, passing the old bar while getting
    0/6 real deficiencies right.

    Implement in Plan 06 Task 1: create an all-DOWNGRADE stub verifier, run it through
    DiscriminationAccuracyMetric, assert is_successful() returns False.
    """
    pytest.skip(
        "Pending: DiscriminationAccuracyMetric full implementation in Plan 06 Task 1"
    )


# ---------------------------------------------------------------------------
# Live-endpoint tests — require Nemotron + deepeval
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("thinking_mode", ["on", "off"])
def test_verifier_conformance_and_discrimination(thinking_mode):
    """Gate: conformance >=98% AND discrimination >=80% per-class floors, both modes.

    Full implementation in Wave 3 after:
      - Plan 03: reliability.py (strict_coerce, coerce_and_validate)
      - Plan 05: Nemotron live endpoint (D-20 gate passed)
      - Plan 06 Task 1: DiscriminationAccuracyMetric.measure() implemented
    """
    pytest.skip("Pending: Nemotron live endpoint required (Plan 05)")
