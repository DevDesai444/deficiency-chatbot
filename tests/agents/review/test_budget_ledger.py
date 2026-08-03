from __future__ import annotations

from dataclasses import dataclass

from agents.review.budget import BudgetLedger
from llm.client import ChatTurn


@dataclass
class FakeClock:
    now: float = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _turn(
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
    content: str = "",
    usage_present: bool = True,
) -> ChatTurn:
    return ChatTurn(
        content=content,
        finish_reason="stop",
        tool_calls=[],
        raw_message={"role": "assistant", "content": content},
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        usage_present=usage_present,
    )


def test_token_ceiling_trips_on_billed_not_unique_tokens() -> None:
    ledger = BudgetLedger(max_tokens=600, max_wall_clock_s=60.0)

    ledger.record_turn(_turn(prompt_tokens=100, completion_tokens=10))
    ledger.record_turn(_turn(prompt_tokens=220, completion_tokens=10))
    ledger.record_turn(_turn(prompt_tokens=360, completion_tokens=10, cached_tokens=40))

    assert ledger.billed_tokens == 710
    assert ledger.billed_tokens > 3 * (100 + 10)
    assert ledger.billed_tokens > (360 + 10)
    assert ledger.cached_tokens == 40
    assert ledger.over_ceiling()


def test_wall_clock_ceiling_trips_with_injected_clock() -> None:
    clock = FakeClock()
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=5.0, clock=clock)

    clock.advance(4.9)
    assert not ledger.over_wall_clock()

    clock.advance(0.1)
    assert ledger.over_wall_clock()
    assert ledger.stop_reason() == "ceiling"


def test_turn_cap_trips_at_max_turns() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, max_turns=3)

    ledger.record_turn(_turn())
    ledger.record_turn(_turn())
    assert not ledger.over_turns()

    ledger.record_turn(_turn())
    assert ledger.over_turns()


def test_diminishing_returns_after_three_unproductive_turns() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, dr_window=3)

    ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)
    assert not ledger.in_diminishing_returns()

    ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)
    assert not ledger.in_diminishing_returns()

    ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)
    assert ledger.in_diminishing_returns()


def test_diminishing_returns_is_false_on_a_fresh_ledger() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0)

    assert not ledger.in_diminishing_returns()


def test_enumerate_turn_counts_as_productive() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, dr_window=3)

    ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=2)
    ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)
    ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)

    assert not ledger.in_diminishing_returns()


def test_reread_of_a_known_span_is_unproductive() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, dr_window=3)

    for _ in range(3):
        ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)

    assert ledger.in_diminishing_returns()


def test_breaker_trips_on_three_identical_tool_args() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, breaker_repeat=3)

    ledger.record_tool_call("search_corpus", {"query": "lod", "top_k": 5})
    ledger.record_tool_call("search_corpus", {"top_k": 5, "query": "lod"})
    assert ledger.breaker_tripped() == ""

    ledger.record_tool_call("search_corpus", {"query": "lod", "top_k": 5})
    assert ledger.breaker_tripped() == "identical_args"


def test_breaker_trips_on_four_consecutive_same_reason_code_half() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, breaker_same_class=4)

    for i in range(3):
        ledger.record_tool_call("emit_finding", {"attempt": i})
        ledger.record_rejection("not_byte_exact", "submission")
    assert ledger.breaker_tripped() == ""

    ledger.record_tool_call("emit_finding", {"attempt": 99})
    ledger.record_rejection("not_byte_exact", "submission")
    assert ledger.breaker_tripped() == "same_class"


def test_breaker_same_class_counter_resets_on_a_successful_call() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, breaker_same_class=4)

    for _ in range(3):
        ledger.record_rejection("not_byte_exact", "submission")
    ledger.record_tool_success()
    for _ in range(2):
        ledger.record_rejection("not_byte_exact", "submission")

    assert ledger.breaker_tripped() == ""


def test_may_nudge_is_blocked_by_diminishing_returns() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, dr_window=3)
    for _ in range(3):
        ledger.record_productivity(new_span_ids=0, new_faults=0, new_requirement_ids=0)

    assert not ledger.may_nudge()
    assert ledger.which_bound == "diminishing_returns"


def test_may_nudge_is_blocked_by_the_hard_cap() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, max_continuations=5)
    ledger.record_productivity(new_span_ids=1, new_faults=0, new_requirement_ids=0)
    ledger.continuations = 5

    assert not ledger.may_nudge()
    assert ledger.which_bound == "max_continuations"


def test_stop_reason_precedence() -> None:
    ceiling = BudgetLedger(max_tokens=1, max_wall_clock_s=60.0, max_turns=1, dr_window=1)
    ceiling.record_turn(_turn(prompt_tokens=1))
    ceiling.record_tool_call("search_corpus", {"query": "a"})
    ceiling.record_tool_call("search_corpus", {"query": "a"})
    ceiling.record_tool_call("search_corpus", {"query": "a"})
    ceiling.record_productivity(0, 0, 0)
    assert ceiling.stop_reason() == "ceiling"

    breaker = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, max_turns=1, dr_window=1)
    breaker.record_turn(_turn())
    breaker.record_tool_call("search_corpus", {"query": "a"})
    breaker.record_tool_call("search_corpus", {"query": "a"})
    breaker.record_tool_call("search_corpus", {"query": "a"})
    breaker.record_productivity(0, 0, 0)
    assert breaker.stop_reason() == "breaker"

    max_turns = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, max_turns=1, dr_window=1)
    max_turns.record_turn(_turn())
    max_turns.record_productivity(0, 0, 0)
    assert max_turns.stop_reason() == "max-turns"

    dr = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0, max_turns=50, dr_window=1)
    dr.record_productivity(0, 0, 0)
    assert dr.stop_reason() == "diminishing-returns"

    completed = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0)
    assert completed.stop_reason() == "completed"


def test_missing_usage_is_counted_and_never_silently_zero() -> None:
    ledger = BudgetLedger(max_tokens=10_000, max_wall_clock_s=60.0)

    ledger.record_turn(_turn(content="The provider omitted usage, but this turn still costs.", usage_present=False))

    assert ledger.usage_missing_turns == 1
    assert ledger.billed_tokens > 0
