"""Per-agent-run budget ledger for AGENT-03 / AGENT-04 stop conditions.

Constructor-injected, never a module global (Security Domain V3, mirroring
tools/ledger.py): one instance per agent run. A BudgetLedger shared across runs would carry
run 1's spend into run 2 and corrupt the 3-run comparison D-GO2 rests on.

D-BUD5: the budget is PER-RUN, not per-document. A per-document budget would let an agent
exhaust itself on document 1 and skim the rest -- reproducing the 2/28 ceiling by a different
route while each document individually looked well-behaved. Tool results count because they
are the dominant token cost in a retrieval loop; wall-clock includes tool execution because
the ceiling bounds real elapsed cost, not model-thinking time alone.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from llm.client import ChatTurn


def _canonical_json(args: dict[str, Any]) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class BudgetLedger:
    """Every stop condition as code on a per-run object the model cannot bypass."""

    # configuration (frozen values land in 03-GO-NOGO-PREREGISTRATION.md per D-GO5)
    max_tokens: int
    max_wall_clock_s: float
    max_turns: int = 50
    dr_window: int = 3
    breaker_repeat: int = 3
    breaker_same_class: int = 4
    max_continuations: int = 5
    clock: Callable[[], float] = time.monotonic

    # accumulated
    billed_tokens: int = 0  # Pitfall 8: Sum(prompt_tokens + completion_tokens) is BILLED, not unique.
    cached_tokens: int = 0  # COST-01 visibility: Sum prompt_tokens_details.cached_tokens.
    turns: int = 0
    continuations: int = 0
    model_time_s: float = 0.0
    tool_execution_time_s: float = 0.0
    usage_missing_turns: int = 0
    started_at: float = 0.0
    which_bound: str = ""

    _productivity: list[bool] = field(default_factory=list, init=False, repr=False)
    _tool_calls: list[tuple[str, str]] = field(default_factory=list, init=False, repr=False)
    _rejections: list[tuple[str, str]] = field(default_factory=list, init=False, repr=False)
    _consecutive_rejections: list[tuple[str, str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.started_at == 0.0:
            self.started_at = self.clock()

    def record_turn(self, turn: ChatTurn) -> None:
        if turn.usage_present:
            self.billed_tokens += turn.prompt_tokens + turn.completion_tokens
            self.cached_tokens += turn.cached_tokens
        else:
            self.usage_missing_turns += 1
            self.billed_tokens += self._estimate_tokens(turn)
        self.turns += 1

    def record_productivity(self, new_span_ids: int, new_faults: int, new_requirement_ids: int) -> None:
        # D-BUD2 + Pitfall 4: read_guideline's ENUMERATE mode records NO spans
        # (read_guideline.py:45-57), so under D-BUD2's literal wording an enumerate turn is
        # unproductive -- and enumerate,enumerate,known-search would trip a dr_window of 3 during
        # the exact RULES-05 mechanism absence_of_evidence depends on. Hence the third clause.
        productive = new_span_ids > 0 or new_faults > 0 or new_requirement_ids > 0
        self._productivity.append(productive)
        if len(self._productivity) > self.dr_window:
            self._productivity = self._productivity[-self.dr_window :]

    def record_tool_call(self, tool: str, args: dict[str, Any]) -> None:
        self._tool_calls.append((tool, _canonical_json(args)))

    def record_rejection(self, reason_code: str, half: str) -> None:
        key = (reason_code, half)
        self._rejections.append(key)
        self._consecutive_rejections.append(key)

    def record_tool_success(self) -> None:
        """A non-rejected tool result resets D-BUD3's same-class rejection counter."""
        self._consecutive_rejections.clear()

    def record_model_time(self, seconds: float) -> None:
        self.model_time_s += max(0.0, seconds)

    def record_tool_time(self, seconds: float) -> None:
        self.tool_execution_time_s += max(0.0, seconds)

    def over_ceiling(self) -> bool:
        return self.billed_tokens >= self.max_tokens

    def over_wall_clock(self) -> bool:
        return self.clock() - self.started_at >= self.max_wall_clock_s

    def over_turns(self) -> bool:
        return self.turns >= self.max_turns

    def in_diminishing_returns(self) -> bool:
        if len(self._productivity) < self.dr_window:
            return False
        return not any(self._productivity[-self.dr_window :])

    def breaker_tripped(self) -> str:
        for key in set(self._tool_calls):
            if self._tool_calls.count(key) >= self.breaker_repeat:
                return "identical_args"

        if len(self._consecutive_rejections) >= self.breaker_same_class:
            window = self._consecutive_rejections[-self.breaker_same_class :]
            if len(set(window)) == 1:
                return "same_class"

        return ""

    def may_nudge(self) -> bool:
        if self.in_diminishing_returns():
            self.which_bound = "diminishing_returns"
            return False
        if self.continuations >= self.max_continuations:
            self.which_bound = "max_continuations"
            return False
        self.which_bound = ""
        return True

    def stop_reason(self) -> str:
        if self.over_ceiling() or self.over_wall_clock():
            return "ceiling"
        if self.breaker_tripped():
            return "breaker"
        if self.over_turns():
            return "max-turns"
        if self.in_diminishing_returns():
            return "diminishing-returns"
        return "completed"

    def wall_clock_s(self) -> float:
        return self.clock() - self.started_at

    def _estimate_tokens(self, turn: ChatTurn) -> int:
        text = turn.content or ""
        if not text and turn.raw_message:
            text = json.dumps(turn.raw_message, sort_keys=True, default=str)
        if not text and turn.tool_calls:
            text = json.dumps(turn.tool_calls, default=str)
        return max(1, len(text) // 4)
