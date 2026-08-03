from __future__ import annotations

import json
from dataclasses import dataclass

from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import TurnLog
from llm.client import ChatTurn
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


@dataclass
class FakeClock:
    now: float = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class AdvancingClient(ScriptedChatClient):
    def __init__(self, script: list[ChatTurn], clock: FakeClock, seconds: float):
        super().__init__(script)
        self.clock = clock
        self.seconds = seconds

    def __call__(self, messages: list[dict], tools: list[dict], **kw) -> ChatTurn:
        self.clock.advance(self.seconds)
        return super().__call__(messages, tools, **kw)


def _block(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _turn(*calls, prompt_tokens: int = 10, completion_tokens: int = 2) -> ChatTurn:
    raw_calls = [
        {
            "id": call.id,
            "type": "function",
            "function": {"name": call.function.name, "arguments": call.function.arguments},
        }
        for call in calls
    ]
    return ChatTurn(
        content="",
        finish_reason="tool_calls",
        tool_calls=list(calls),
        raw_message={"role": "assistant", "content": None, "tool_calls": raw_calls},
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        usage_present=True,
    )


def _stop_turn(prompt_tokens: int = 1) -> ChatTurn:
    return ChatTurn(
        content="done",
        finish_reason="stop",
        tool_calls=[],
        raw_message={"role": "assistant", "content": "done"},
        prompt_tokens=prompt_tokens,
        completion_tokens=0,
        usage_present=True,
    )


def _parts(tmp_path, *, budget: BudgetLedger | None = None):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block("Intro Heading. The method validation omits specificity detail.")],
        outline_headings=["Intro Heading."],
    )
    ledger = RetrievalLedger()
    budget = budget or BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    return corpus, ledger, budget, telemetry, registry


def test_token_ceiling(tmp_path):
    budget = BudgetLedger(max_tokens=50, max_wall_clock_s=999)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([_turn(make_tool_call("open_doc", {"doc_id": "d1"}), prompt_tokens=60)])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "ceiling"
    assert result.report.budget_exhausted is True
    assert result.report.faults == result.findings


def test_wallclock_ceiling(tmp_path):
    clock = FakeClock()
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=5, clock=clock)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = AdvancingClient([_turn(make_tool_call("open_doc", {"doc_id": "d1"}))], clock, 6)

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "ceiling"
    assert result.report.budget_exhausted is True


def test_diminishing_returns(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, dr_window=3, breaker_repeat=99)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    calls = [make_tool_call("open_doc", {"doc_id": "d1"}) for _ in range(3)]
    client = ScriptedChatClient([_turn(call) for call in calls])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "diminishing-returns"
    assert not budget.over_ceiling()


def test_enumerate_productivity_prevents_diminishing_returns():
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, dr_window=3)
    budget.record_productivity(0, 0, 2)
    budget.record_productivity(0, 0, 0)
    budget.record_productivity(0, 0, 0)

    assert not budget.in_diminishing_returns()


def test_breaker_identical_args(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, breaker_repeat=3, breaker_same_class=99)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    args = {"doc_id": "missing"}
    client = ScriptedChatClient([_turn(make_tool_call("open_doc", args)) for _ in range(3)])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "breaker"
    assert budget.breaker_tripped() == "identical_args"


def test_breaker_same_class(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, dr_window=10, breaker_same_class=4)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([
        _turn(make_tool_call("open_doc", {"doc_id": f"missing-{i}"}))
        for i in range(4)
    ])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "breaker"
    assert budget.breaker_tripped() == "same_class"


def test_rejection_consumes_a_turn(tmp_path):
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path)
    client = ScriptedChatClient([_turn(make_tool_call("open_doc", {"doc_id": "missing"})), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert budget.turns >= 2
    assert any("REJECTED[" in m.get("content", "") for m in result.messages if m.get("role") == "tool")


def test_pre_repair_does_not_consume_a_turn(tmp_path):
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path)
    raw_args = '{"doc_id":"d1","heading":"Intro Heading"}'
    client = ScriptedChatClient([_turn(make_tool_call("get_section", json.loads(raw_args))), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "completed"
    records = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text().splitlines()]
    assert not [r for r in records if r.get("record_type") == "repair" and r.get("layer") == "pre"]
