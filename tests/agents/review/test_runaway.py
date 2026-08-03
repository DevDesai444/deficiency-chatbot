from __future__ import annotations

import json

from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import TurnLog
from evals.capture import load_captured
from llm.client import ChatTurn
from schemas.faults import FaultReport
from tests.agents.review.conftest import make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


class ReferenceRunaway:
    """D-BUD6 driver: never stops and varies args so the breaker is not the gate."""

    def __init__(self, prompt_tokens: int = 4000, completion_tokens: int = 200):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.i = 0

    def __call__(self, messages: list[dict], tools: list[dict], **kw) -> ChatTurn:
        self.i += 1
        call = make_tool_call("follow_reference", {"doc_id": "d1", "ref_text": f"Module {self.i}"})
        return ChatTurn(
            content="",
            finish_reason="tool_calls",
            tool_calls=[call],
            raw_message={
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.function.name, "arguments": call.function.arguments},
                    }
                ],
            },
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            usage_present=True,
        )


class ClockedRunaway(ReferenceRunaway):
    def __init__(self, clock, seconds: float):
        super().__init__(prompt_tokens=1, completion_tokens=1)
        self.clock = clock
        self.seconds = seconds

    def __call__(self, messages: list[dict], tools: list[dict], **kw) -> ChatTurn:
        self.clock["now"] += self.seconds
        return super().__call__(messages, tools, **kw)


def _block(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _parts(tmp_path, budget: BudgetLedger):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block("Intro Heading. The validation package references Module 3 and Module 4.")],
        outline_headings=["Intro Heading."],
    )
    ledger = RetrievalLedger()
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    return corpus, ledger, telemetry, registry


def _run(tmp_path, budget: BudgetLedger, complete):
    corpus, ledger, telemetry, registry = _parts(tmp_path, budget)
    return run_review(corpus, corpus.manifest, ledger, budget, telemetry, complete, registry), budget


def test_runaway_trips_ceiling_and_returns_grounded_partial(tmp_path):
    budget = BudgetLedger(max_tokens=5_000, max_turns=1000, max_wall_clock_s=600)

    result, budget = _run(tmp_path, budget, ReferenceRunaway())

    assert result.stop_reason == "ceiling"
    assert budget.billed_tokens <= 8_400
    assert isinstance(result.report, FaultReport)
    assert all(f.evidence for f in result.report.faults)


def test_runaway_does_not_trip_the_breaker_first(tmp_path):
    budget = BudgetLedger(max_tokens=5_000, max_turns=1000, max_wall_clock_s=600, breaker_repeat=3)

    result, budget = _run(tmp_path, budget, ReferenceRunaway())

    assert result.stop_reason == "ceiling"
    assert budget.breaker_tripped() == ""


def test_runaway_wall_clock_variant(tmp_path):
    clock = {"now": 100.0}
    budget = BudgetLedger(
        max_tokens=1_000_000,
        max_turns=1000,
        max_wall_clock_s=5,
        clock=lambda: clock["now"],
    )

    result, _budget = _run(tmp_path, budget, ClockedRunaway(clock, 6))

    assert result.stop_reason == "ceiling"
    assert result.report.budget_exhausted is True


def test_runaway_partial_is_re_scorable(tmp_path):
    budget = BudgetLedger(max_tokens=5_000, max_turns=1000, max_wall_clock_s=600)
    result, _budget = _run(tmp_path, budget, ReferenceRunaway())
    path = tmp_path / "partial.json"

    path.write_text(result.report.model_dump_json())

    assert isinstance(load_captured(path), FaultReport)


def test_runaway_never_raises(tmp_path):
    budget = BudgetLedger(max_tokens=5_000, max_turns=1000, max_wall_clock_s=600)

    result, _budget = _run(tmp_path, budget, ReferenceRunaway())

    assert result.error == ""
    assert result.aborted is True


def test_runaway_is_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
    budget = BudgetLedger(max_tokens=5_000, max_turns=1000, max_wall_clock_s=600)

    result, _budget = _run(tmp_path, budget, ReferenceRunaway())

    assert result.stop_reason == "ceiling"
