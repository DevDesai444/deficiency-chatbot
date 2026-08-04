from __future__ import annotations

import json

from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.prompts import NUDGE
from agents.review.registry import ToolRegistry
from agents.review.telemetry import RunSummary, TurnLog, capture_provenance, read_turns
from llm.client import ChatTurn
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _stop_turn(prompt_tokens: int = 10) -> ChatTurn:
    return ChatTurn(
        content="done",
        finish_reason="stop",
        tool_calls=[],
        raw_message={"role": "assistant", "content": "done"},
        prompt_tokens=prompt_tokens,
        completion_tokens=1,
        usage_present=True,
    )


def _turn(*calls) -> ChatTurn:
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
        prompt_tokens=10,
        completion_tokens=1,
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


def _summary(tmp_path, budget, ledger):
    records, malformed = read_turns(tmp_path / "turns.jsonl")
    return RunSummary.from_turns(
        provenance=capture_provenance(
            run_index=1,
            model_id="databricks-meta-llama-3-3-70b-instruct",
            corpus_content_hash="corpus-sha",
            run_completed=True,
        ),
        records=records,
        malformed_trailing_turn_lines=malformed,
        budget_ledger=budget,
        retrieval_ledger=ledger,
        max_continuations_permitted=budget.max_continuations,
        stop_reason=budget.stop_reason(),
    )


def test_nudge_on_premature_stop(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, max_continuations=1)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([_stop_turn(), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "completed"
    assert budget.continuations == 1
    assert client.seen_messages[1][-1] == {"role": "user", "content": NUDGE}


def test_nudge_bounded_by_dr(tmp_path):
    # dr_grace_turns=0 isolates the DR<->nudge interaction from the R2 (03-19) grace window,
    # which has its own coverage in tests/agents/review/test_dr_grace.py.
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, dr_window=1, max_continuations=5, dr_grace_turns=0)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([_stop_turn(), _turn(make_tool_call("open_doc", {"doc_id": "missing"})), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "diminishing-returns"
    assert budget.which_bound == "diminishing_returns"


def test_nudge_bounded_by_cap(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, dr_window=10, max_continuations=2)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([_stop_turn(), _stop_turn(), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "completed"
    assert budget.continuations == 2
    assert budget.which_bound == "max_continuations"


def test_continuation_telemetry(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, max_continuations=1)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([_stop_turn(prompt_tokens=23), _stop_turn()])

    run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)
    summary = _summary(tmp_path, budget, ledger)

    assert summary.continuation_count == 1
    assert summary.max_continuations_permitted == 1
    assert summary.tokens_at_each_attempted_stop == [24]
    assert summary.findings_before_after_each_nudge == [(0, 0)]


def test_zero_continuations_is_recorded_as_unproven_not_validated(tmp_path):
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999, max_continuations=0)
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path, budget=budget)
    client = ScriptedChatClient([_stop_turn()])

    run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)
    summary = _summary(tmp_path, budget, ledger)

    assert summary.continuation_count == 0
    assert summary.tokens_at_each_attempted_stop == []
