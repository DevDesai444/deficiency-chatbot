from __future__ import annotations

from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.budget import BudgetLedger
from agents.review.telemetry import TurnLog
from llm.client import ChatTurn
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str, page: int = 1, order: int = 0) -> dict:
    return {"text": text, "page": page, "reading_order": order, "lines": []}


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
        completion_tokens=2,
        usage_present=True,
    )


def _stop_turn() -> ChatTurn:
    return ChatTurn(
        content="done",
        finish_reason="stop",
        tool_calls=[],
        raw_message={"role": "assistant", "content": "done"},
        usage_present=True,
    )


def _run(tmp_path, script: list[ChatTurn]):
    corpus = build_corpus_index(
        tmp_path,
        "d1",
        [_block("Intro Heading. The method validation omits specificity detail.")],
        outline_headings=["Intro Heading."],
    )
    ledger = RetrievalLedger()
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    client = ScriptedChatClient(script)
    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)
    return result, client


def test_assistant_tool_calls_message_is_echoed_verbatim(tmp_path):
    turn = _turn(make_tool_call("open_doc", {"doc_id": "d1"}))
    result, _client = _run(tmp_path, [turn, _stop_turn()])

    assert result.messages[2] == turn.raw_message


def test_every_tool_message_id_matches_the_preceding_assistant_message(tmp_path):
    turn1 = _turn(make_tool_call("open_doc", {"doc_id": "d1"}))
    turn2 = _turn(make_tool_call("get_section", {"doc_id": "d1", "heading": "Intro Heading"}))
    result, _client = _run(tmp_path, [turn1, turn2, _stop_turn()])

    active_ids: set[str] = set()
    for message in result.messages:
        if message.get("role") == "assistant" and message.get("tool_calls"):
            active_ids = {call["id"] for call in message["tool_calls"]}
            continue
        if message.get("role") == "tool":
            assert message["tool_call_id"] in active_ids


def test_tool_result_content_is_a_string(tmp_path):
    turn = _turn(make_tool_call("open_doc", {"doc_id": "d1"}))
    result, _client = _run(tmp_path, [turn, _stop_turn()])

    tool_messages = [m for m in result.messages if m.get("role") == "tool"]
    assert tool_messages
    assert all(isinstance(m["content"], str) for m in tool_messages)


def test_rejection_is_rendered_with_its_hint(tmp_path):
    turn = _turn(make_tool_call("open_doc", {"doc_id": "missing"}))
    result, _client = _run(tmp_path, [turn, _stop_turn()])

    content = "\n".join(m["content"] for m in result.messages if m.get("role") == "tool")
    assert "REJECTED[" in content
    assert "HINT:" in content
    assert "call search_corpus" in content


def test_multiple_tool_calls_in_one_turn_each_get_their_own_tool_message(tmp_path):
    calls = [
        make_tool_call("open_doc", {"doc_id": "d1"}),
        make_tool_call("get_section", {"doc_id": "d1", "heading": "Intro Heading"}),
    ]
    result, _client = _run(tmp_path, [_turn(*calls), _stop_turn()])

    tool_messages = [m for m in result.messages if m.get("role") == "tool"]
    assert len(tool_messages) == 2
    assert {m["tool_call_id"] for m in tool_messages} == {call.id for call in calls}
