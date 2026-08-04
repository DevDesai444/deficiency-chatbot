"""R2 (03-19 remediation): the diminishing-returns stop is armed only AFTER turn 5.

A rejection-heavy start must not guillotine exploration before it begins (runs 1 and 3 of
the 03-18 set stopped at DR on turn 7 with 0 findings after early `not_found` rejections).
The circuit breaker is intentionally unchanged and still fires during the grace window.
"""
from __future__ import annotations

from agents.review.budget import BudgetLedger


def _ledger(**kw) -> BudgetLedger:
    return BudgetLedger(max_tokens=10**9, max_wall_clock_s=10**9, **kw)


def test_default_grace_is_five_turns():
    assert _ledger().dr_grace_turns == 5


def test_dr_suppressed_during_grace_then_arms_after_turn_5():
    b = _ledger(dr_window=3)
    for _ in range(3):
        b.record_productivity(0, 0, 0)  # fill the window with unproductive turns

    for t in range(1, 6):  # run-turns 1..5 are within grace
        b.turns = t
        assert b.in_diminishing_returns() is False, f"DR should be suppressed at turn {t}"
        assert b.stop_reason() != "diminishing-returns"

    b.turns = 6  # past grace
    assert b.in_diminishing_returns() is True
    assert b.stop_reason() == "diminishing-returns"


def test_breaker_still_fires_within_the_grace_window():
    b = _ledger(breaker_repeat=3)
    b.turns = 2  # within the DR grace window
    for _ in range(3):
        b.record_tool_call("search_corpus", {"query": "impurity"})
    assert b.breaker_tripped() == "identical_args"
    assert b.stop_reason() == "breaker"  # breaker is not grace-gated


def test_grace_does_not_change_the_pure_window_predicate_at_turns_zero():
    """The synthetic turns==0 ledger (used by the existing window-predicate unit tests)
    keeps its contract: 3 unproductive records => in_diminishing_returns is True."""
    b = _ledger(dr_window=3)
    assert b.turns == 0
    for _ in range(3):
        b.record_productivity(0, 0, 0)
    assert b.in_diminishing_returns() is True
