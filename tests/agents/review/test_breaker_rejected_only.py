"""S1 (v3): the identical-args breaker counts ONLY identical calls whose result was REJECTED.

Forensic: run 3 (v2) died at turn 21 with stop_reason=breaker while healthy -- successful
identical repeats (neutralized by COST-04's dedup stub) were tripping the identical-args
breaker. S1 restricts it to rejected repeats. The same_class breaker is unchanged.
"""
from __future__ import annotations

from agents.review.budget import BudgetLedger


def _ledger(**kw) -> BudgetLedger:
    return BudgetLedger(max_tokens=10**9, max_wall_clock_s=10**9, **kw)


def test_three_identical_successful_calls_do_NOT_trip():
    b = _ledger(breaker_repeat=3)
    for _ in range(3):
        b.record_tool_call("get_section", {"doc_id": "d1", "heading": "Intro"})
    assert b.breaker_tripped() == ""  # successful repeats are dedup-neutralized, never fatal


def test_three_identical_rejected_calls_trip():
    b = _ledger(breaker_repeat=3)
    for _ in range(3):
        b.record_tool_call("emit_finding", {"submission_span_id": "[d1:0:9]"})
        b.record_rejection("not_byte_exact", "submission",
                           tool="emit_finding", args={"submission_span_id": "[d1:0:9]"})
    assert b.breaker_tripped() == "identical_args"


def test_two_rejected_then_one_success_of_same_args_still_below_threshold():
    b = _ledger(breaker_repeat=3)
    args = {"submission_span_id": "[d1:0:9]"}
    for _ in range(2):
        b.record_rejection("not_byte_exact", "submission", tool="emit_finding", args=args)
    b.record_tool_call("emit_finding", args)  # a success does not add to the rejected count
    assert b.breaker_tripped() == ""


def test_same_class_breaker_is_unchanged():
    b = _ledger(breaker_same_class=4)
    for i in range(4):
        b.record_rejection("not_retrieved_this_session", "rule", tool="emit_finding", args={"n": i})
    assert b.breaker_tripped() == "same_class"
