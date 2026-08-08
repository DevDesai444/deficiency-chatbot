from __future__ import annotations

import json

from agents.review.loop import run_review
from agents.review.prompts import SYSTEM_PROMPT
from agents.review.registry import ToolRegistry
from agents.review.budget import BudgetLedger
from agents.review.telemetry import TurnLog
from llm.client import ChatTurn
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str, page: int = 1, order: int = 0) -> dict:
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _turn(*calls, finish_reason: str = "tool_calls") -> ChatTurn:
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
        finish_reason=finish_reason,
        tool_calls=list(calls),
        raw_message={"role": "assistant", "content": None, "tool_calls": raw_calls},
        prompt_tokens=10,
        completion_tokens=2,
        cached_tokens=4,
        usage_present=True,
    )


def _stop_turn(content: str = "") -> ChatTurn:
    return ChatTurn(
        content=content,
        finish_reason="stop",
        tool_calls=[],
        raw_message={"role": "assistant", "content": content},
        prompt_tokens=7,
        completion_tokens=1,
        usage_present=True,
    )


def _review_parts(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block("Intro Heading. The assay method validation omits impurity specificity detail.")],
        outline_headings=["Intro Heading."],
        title="Assay Validation",
    )
    ledger = RetrievalLedger()
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    return corpus, ledger, budget, telemetry, registry


def test_loop_issues_dispatches_and_terminates(tmp_path):
    corpus, ledger, budget, telemetry, registry = _review_parts(tmp_path)
    c1 = make_tool_call("open_doc", {"doc_id": "d1"})
    c2 = make_tool_call("get_section", {"doc_id": "d1", "heading": "Intro Heading"})
    client = ScriptedChatClient([_turn(c1), _turn(c2), _stop_turn("done")])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "completed"
    assert result.report.stop_reason == "completed"
    assert getattr(ledger, "_issued")
    assert any(m.get("role") == "tool" and "Assay Validation" in m.get("content", "") for m in result.messages)
    assert any(m.get("role") == "tool" and "assay method validation" in m.get("content", "") for m in result.messages)


def test_loop_returns_a_faultreport_with_stop_reason_set(tmp_path):
    corpus, ledger, budget, telemetry, registry = _review_parts(tmp_path)
    client = ScriptedChatClient([_stop_turn("complete")])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.report.stop_reason == "completed"
    assert result.report.budget_exhausted is False
    assert result.report.faults == result.findings


def test_a_dispatch_exception_does_not_crash_the_run(tmp_path):
    corpus, ledger, budget, telemetry, registry = _review_parts(tmp_path)

    def raising_call(name: str, raw_args: str):
        raise RuntimeError("forced dispatch failure")

    broken = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    setattr(broken, "dispatch", raising_call)
    client = ScriptedChatClient([_turn(make_tool_call("open_doc", {"doc_id": "d1"}))])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, broken)

    assert result.aborted is True
    assert result.stop_reason == "aborted"
    assert result.report.stop_reason == "aborted"
    assert "forced dispatch failure" in result.error


def test_finish_reason_error_marks_the_run_aborted(tmp_path):
    corpus, ledger, budget, telemetry, registry = _review_parts(tmp_path)
    client = ScriptedChatClient(
        [
            ChatTurn(
                content="",
                finish_reason="error",
                tool_calls=[],
                raw_message={},
                usage_present=False,
            )
        ]
    )

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.aborted is True
    assert result.stop_reason == "aborted"
    assert result.report.budget_exhausted is False


def test_cross_document_pending_is_not_retried(tmp_path):
    corpus, ledger, budget, telemetry, registry = _review_parts(tmp_path)

    calls: list[tuple[str, str]] = []
    original_call = registry.dispatch

    def counted_call(name: str, raw_args: str):
        calls.append((name, raw_args))
        return original_call(name, raw_args)

    setattr(registry, "dispatch", counted_call)
    args = {"doc_id": "d1", "ref_text": "Module 5"}
    client = ScriptedChatClient([_turn(make_tool_call("follow_reference", args)), _stop_turn("done")])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert result.stop_reason == "completed"
    assert calls == [("follow_reference", json.dumps(args, sort_keys=True))]
    tool_contents = "\n".join(m["content"] for m in result.messages if m.get("role") == "tool")
    # Wave 5 (B4 fix, RULING A): follow_reference no longer returns the
    # _CROSS_DOC_PENDING sentinel. An unresolvable cross-doc ref now returns the real
    # typed status "UNRESOLVED_REF". The test's intent is unchanged: the ref is handled
    # exactly once (asserted above), not retried, and not rejected.
    assert "UNRESOLVED_REF" in tool_contents
    assert "REJECTED" not in tool_contents


def test_corpus_data_never_enters_the_system_message(tmp_path):
    corpus, ledger, budget, telemetry, registry = _review_parts(tmp_path)
    client = ScriptedChatClient([_stop_turn("done")])

    run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert client.seen_messages[0][0]["content"] == SYSTEM_PROMPT
    assert "Assay Validation" not in client.seen_messages[0][0]["content"]
    assert any("Assay Validation" in m["content"] for m in client.seen_messages[0] if m["role"] == "user")
