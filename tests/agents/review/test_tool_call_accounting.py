"""Regression: BudgetLedger.total_tool_calls + typed JSONL rows reconcile (reviewer leg fix).

The live smoke run in plan 03-18 surfaced `total_tool_calls: 0` in a run that dispatched
tools across four turns: the loop emitted only `turn` rows (never `tool_call` / `rejection`
rows the summary builder consumes) and BudgetLedger exposed no count property, so
telemetry fell back to a JSONL-derived count of 0. This test drives the REAL loop through a
real ToolRegistry and asserts the two legs now reconcile:

  (a) summary.total_tool_calls == every dispatch that passed arg-validation
  (b) JSONL carries one tool_call row per non-rejected dispatch and one rejection row per
      ToolRejected, and (tool_call rows + rejection rows) == total_tool_calls
  (c) rejections_by_code_half carries the (reason_code, half) key
  (d) the D-BUD3 identical-args breaker still trips on breaker_repeat=3 -- proving the count
      property reads the SAME _tool_calls list the breaker reads

The rejected call here is a loop-side parse_span_ref rejection (half=""); the gate-half
(submission/rule) matrix is covered by tests/agents/review/test_repair_accounting.py.
"""
from __future__ import annotations

from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import RunSummary, TurnLog, capture_provenance, read_turns
from llm.client import ChatTurn
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _turn(*calls) -> ChatTurn:
    raw_calls = [
        {"id": c.id, "type": "function",
         "function": {"name": c.function.name, "arguments": c.function.arguments}}
        for c in calls
    ]
    return ChatTurn(
        content="", finish_reason="tool_calls", tool_calls=list(calls),
        raw_message={"role": "assistant", "content": None, "tool_calls": raw_calls},
        prompt_tokens=10, completion_tokens=2, cached_tokens=0, usage_present=True,
    )


def _stop_turn() -> ChatTurn:
    return ChatTurn(
        content="done", finish_reason="stop", tool_calls=[],
        raw_message={"role": "assistant", "content": "done"},
        prompt_tokens=7, completion_tokens=1, usage_present=True,
    )


def _parts(tmp_path):
    corpus = build_corpus_index(
        tmp_path, "d1",
        [_block("Intro Heading. The assay method validation omits impurity specificity detail.")],
        outline_headings=["Intro Heading."],
        title="Assay Validation",
    )
    ledger = RetrievalLedger()
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    return corpus, ledger, budget, telemetry, registry


def test_tool_call_and_rejection_rows_reconcile_with_ledger_total(tmp_path):
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path)

    clean1 = make_tool_call("open_doc", {"doc_id": "d1"})
    clean2 = make_tool_call("get_section", {"doc_id": "d1", "heading": "Intro Heading"})
    # Arg-valid emit_finding whose submission span-ref is out of range -> parse_span_ref
    # rejects it AFTER record_tool_call already counted the dispatch.
    rejected = make_tool_call("emit_finding", {
        "submission_span_id": "[d1:0:99999]",
        "rule_span_id": "[d1:0:4]",
        "verdict": "gap", "title": "t", "detail": "d",
    })
    client = ScriptedChatClient([_turn(clean1), _turn(clean2), _turn(rejected), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    records, malformed = read_turns(tmp_path / "turns.jsonl")
    assert malformed == 0
    summary = RunSummary.from_turns(
        provenance=capture_provenance(
            run_index=1, model_id="databricks-meta-llama-3-3-70b-instruct",
            corpus_content_hash="corpus-sha", run_completed=True,
        ),
        records=records,
        budget_ledger=budget,
        retrieval_ledger=ledger,
        stop_reason=result.stop_reason,
    )

    tool_call_rows = [r for r in records if r["record_type"] == "tool_call"]
    rejection_rows = [r for r in records if r["record_type"] == "rejection"]

    # (a) ledger truth: three dispatches passed arg-validation (2 clean + 1 gate-rejected).
    assert budget.total_tool_calls == 3
    assert summary.total_tool_calls == 3
    # (b) row types: 2 tool_call + 1 rejection, reconciling to the ledger total.
    assert len(tool_call_rows) == 2
    assert len(rejection_rows) == 1
    assert len(tool_call_rows) + len(rejection_rows) == summary.total_tool_calls
    # (c) the (reason_code, half) key is present.
    assert "span_ref_out_of_range|" in summary.rejections_by_code_half
    assert sum(summary.rejections_by_code_half.values()) == 1
    # A1 (03-19 prereg v2): provenance records the code HEAD and working-tree cleanliness so
    # all 3 scored runs are provably at one identical, clean HEAD.
    assert "code_head_sha" in summary.provenance
    assert "working_tree_dirty" in summary.provenance
    assert isinstance(summary.provenance["working_tree_dirty"], bool)


def test_identical_REJECTED_calls_trip_breaker_repeat_three(tmp_path):
    corpus, ledger, budget, telemetry, registry = _parts(tmp_path)

    # S1 (v3): the identical-args breaker fires only on REJECTED identical calls. Three
    # identical emit_finding calls with an out-of-range span are each gate-rejected; the
    # pre-call breaker check trips on the 4th turn. (Identical SUCCESSFUL repeats do not trip
    # -- covered by tests/agents/review/test_breaker_rejected_only.py.)
    reject = lambda: make_tool_call("emit_finding", {
        "submission_span_id": "[d1:0:99999]", "rule_span_id": "[d1:0:4]",
        "verdict": "gap", "title": "t", "detail": "d"})
    client = ScriptedChatClient([_turn(reject()), _turn(reject()), _turn(reject()), _turn(reject())])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert budget.breaker_repeat == 3
    assert budget.breaker_tripped() == "identical_args"
    assert result.stop_reason == "breaker"
