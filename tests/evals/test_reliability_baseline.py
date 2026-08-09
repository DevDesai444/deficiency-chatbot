"""D-14 pinned Phase-3 baseline diff harness.

This file pins the Phase-3 malformed-arg rates as MODULE-LEVEL LITERALS before any
hardening code is written. The literals are the frozen baseline; any post-hardening
measurement must be arithmetically less than these numbers.

PURPOSE: Test-first contract for the "measurably reduced" claim in D-14. Writing
these constants NOW (before reliability.py exists) ensures the baseline is committed
as a frozen artifact, not a retro-fitted number.

D-14 HONESTY NOTE: The baseline diff in Plan 06 measures what strict_coerce RECOVERS
without a live LLM re-prompt (coercion-recovery smoke test, not a full retry-loop gate).
The corrective re-prompt message is produced by coerce_and_validate but the actual LLM
re-call is Phase 7 orchestrator policy.
"""
from __future__ import annotations

import pytest

# ===========================================================================
# D-14 PINNED PHASE-3 BASELINE — written 2026-08-08 BEFORE any hardening code
#
# Source: .planning/phases/03-drive-loop-spike-go-no-go/03-18-SUMMARY.md D-TEL4 section
# Llama 3.3 70B (v1 scored runs — 3 runs):
LLAMA_V1_PRE_REPAIR_RATE = 0.0    # pre_repair_malformed: 0/0/0 across 3 runs
LLAMA_V1_POST_REPAIR_RATE = 0.0   # post_repair_malformed: 0/0/0 across 3 runs
#
# Source: .planning/phases/03-drive-loop-spike-go-no-go/03-QWEN-FIDELITY-PROBE.md
# Qwen fidelity probe (1 probe run, 5 tool-call attempts):
QWEN_PRE_REPAIR_RATE = 0.0        # pre_repair_malformed: 0 out of 5 attempts
QWEN_POST_REPAIR_RATE = 0.80      # post_repair_malformed: 4 out of 5 = 80%
# Failure class: wholesale unrepairable read_guideline args (NOT optional-param near-misses)
#
# "Measurably reduced" = post-hardening rate arithmetically < these pins.
# ===========================================================================


# ---------------------------------------------------------------------------
# Self-documenting invariant — runs immediately, before any implementation
# ---------------------------------------------------------------------------

def test_baseline_numbers_are_locked_as_literals():
    """Assert that the D-14 baseline literal values are exactly as pinned.

    This test is the freeze guard for the baseline constants. If anyone edits
    LLAMA_V1_POST_REPAIR_RATE or QWEN_POST_REPAIR_RATE, this test fails
    immediately — surfacing that the frozen baseline has been tampered with.

    These values were pinned 2026-08-08 from committed Phase-3 run artifacts.
    Do NOT change them without a reviewer sign-off and a new baseline run.
    """
    assert LLAMA_V1_PRE_REPAIR_RATE == 0.0, (
        f"LLAMA_V1_PRE_REPAIR_RATE changed! Expected 0.0, got {LLAMA_V1_PRE_REPAIR_RATE}. "
        "Frozen baseline must not be edited without a reviewer sign-off."
    )
    assert LLAMA_V1_POST_REPAIR_RATE == 0.0, (
        f"LLAMA_V1_POST_REPAIR_RATE changed! Expected 0.0, got {LLAMA_V1_POST_REPAIR_RATE}. "
        "Frozen baseline must not be edited without a reviewer sign-off."
    )
    assert QWEN_PRE_REPAIR_RATE == 0.0, (
        f"QWEN_PRE_REPAIR_RATE changed! Expected 0.0, got {QWEN_PRE_REPAIR_RATE}. "
        "Frozen baseline must not be edited without a reviewer sign-off."
    )
    assert QWEN_POST_REPAIR_RATE == pytest.approx(0.80), (
        f"QWEN_POST_REPAIR_RATE changed! Expected 0.80, got {QWEN_POST_REPAIR_RATE}. "
        "Frozen baseline must not be edited without a reviewer sign-off."
    )


# ---------------------------------------------------------------------------
# Post-hardening delta tests — skipped until reliability.py + probe replay land
# ---------------------------------------------------------------------------

def test_post_hardening_llama_rate_below_baseline():
    """D-14: Llama post-hardening malformed rate must be < LLAMA_V1_POST_REPAIR_RATE.

    Baseline: LLAMA_V1_POST_REPAIR_RATE = 0.0 (already 0 — Llama was reliable
    before hardening). This test validates that hardening does NOT regress Llama.
    Expected outcome: post-hardening rate stays 0.0 (no regression).
    """
    pytest.skip("Pending: reliability.py + probe replay in Wave 3")


def test_post_hardening_qwen_rate_below_baseline():
    """D-14: Qwen post-hardening malformed rate must be < QWEN_POST_REPAIR_RATE (0.80).

    Baseline: QWEN_POST_REPAIR_RATE = 0.80 (4/5 wholesale unrepairable failures).
    This is the primary D-14 target: strict_coerce + field-level reprompt must
    measurably recover from Qwen's 80% malformed-arg failure rate.
    Expected outcome: post-hardening rate < 0.80 (ideally ≤ 0.20).
    """
    pytest.skip("Pending: reliability.py + probe replay in Wave 3")
