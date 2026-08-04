"""S5 (v3): force oracle engagement.

Evidence: run_oracles surfaced 0/0/0 across all three v2 runs, yet C-01/C-02 are exactly the
profile the oracles target. The prompt now directs run_oracles first; the coverage reminder
counts an un-called oracle (or an unaddressed lead) as unaddressed coverage.
"""
from __future__ import annotations

from agents.review.budget import BudgetLedger
from agents.review.loop import _coverage_reminder, run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import TurnLog, read_turns
from ingest.manifest import CoverageManifest, DocEntry
from llm.client import ChatTurn
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _turn(*calls) -> ChatTurn:
    raw = [{"id": c.id, "type": "function",
            "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]
    return ChatTurn(content="", finish_reason="tool_calls", tool_calls=list(calls),
                    raw_message={"role": "assistant", "content": None, "tool_calls": raw},
                    prompt_tokens=10, completion_tokens=2, usage_present=True)


def test_scripted_8_turn_run_contains_run_oracles(tmp_path):
    corpus = build_corpus_index(
        tmp_path, "d1",
        [_block("Intro Heading. The assay method validation omits impurity specificity detail.")],
        outline_headings=["Intro Heading."],
    )
    ledger = RetrievalLedger()
    budget = BudgetLedger(max_tokens=10**9, max_wall_clock_s=10**9, max_turns=8, dr_window=20)
    telemetry = TurnLog(tmp_path / "t.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)

    script = [
        _turn(make_tool_call("run_oracles", {"doc_id": "d1"})),
        _turn(make_tool_call("open_doc", {"doc_id": "d1"})),
        _turn(make_tool_call("get_section", {"doc_id": "d1", "heading": "Intro Heading"})),
        _turn(make_tool_call("search_corpus", {"query": "impurity a"})),
        _turn(make_tool_call("search_corpus", {"query": "impurity b"})),
        _turn(make_tool_call("search_corpus", {"query": "impurity c"})),
        _turn(make_tool_call("search_corpus", {"query": "impurity d"})),
        _turn(make_tool_call("search_corpus", {"query": "impurity e"})),
    ]
    run_review(corpus, corpus.manifest, ledger, budget, telemetry, ScriptedChatClient(script), registry)

    records, _ = read_turns(tmp_path / "t.jsonl")
    oracle_calls = [r for r in records if r["record_type"] == "tool_call" and r.get("tool") == "run_oracles"]
    assert len(oracle_calls) >= 1


def test_coverage_reminder_flags_an_uncalled_oracle():
    manifest = CoverageManifest(documents=[DocEntry(doc_id="d1", filename="d1.pdf", content_hash="x")])

    class _Ledger:  # minimal stub: d1 has been opened (a span issued), but no finding, no oracle
        _issued = {("d1", 0, 5)}

    result = _coverage_reminder(manifest, _Ledger(), [], oracle_called=False, oracle_leads_surfaced=0)
    assert result is not None
    message, _unopened, _uncovered = result
    assert "run_oracles has not been called" in message


def test_coverage_reminder_flags_unused_oracle_leads():
    manifest = CoverageManifest(documents=[DocEntry(doc_id="d1", filename="d1.pdf", content_hash="x")])

    class _Ledger:
        _issued = {("d1", 0, 5)}

    # oracle called, 4 leads surfaced, 0 findings -> unused leads flagged even though d1 opened
    result = _coverage_reminder(manifest, _Ledger(), [], oracle_called=True, oracle_leads_surfaced=4)
    assert result is not None
    message, _u, _c = result
    assert "Oracle leads surfaced=4" in message
