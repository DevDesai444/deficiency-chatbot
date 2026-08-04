"""S4 (v3): every 8 turns the loop injects a code-computed coverage reminder as a user
message (dynamic content in a MESSAGE, never the cached prefix), and logs the injection.

Targets clause (b): the v2 median runs were never steered back to findable evidence.
"""
from __future__ import annotations

from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import RunSummary, TurnLog, capture_provenance, read_turns
from tests.agents.review.conftest import ForcedRunaway
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def test_coverage_reminder_injected_and_logged(tmp_path):
    corpus = build_corpus_index(
        tmp_path, "d1",
        [_block("Intro Heading. The assay method validation omits impurity specificity detail.")],
        outline_headings=["Intro Heading."], title="Assay Validation",
    )
    ledger = RetrievalLedger()
    # dr_window=20 neutralizes the productivity-based DR stop so this test isolates the
    # every-8-turns reminder cadence (re-searching a 1-doc corpus is otherwise unproductive).
    budget = BudgetLedger(max_tokens=10**9, max_wall_clock_s=10**9, max_turns=12, dr_window=20)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)

    # ForcedRunaway varies its search query each turn: productive (no DR) and never identical
    # (no breaker), so the run advances to the max-turns backstop and past the turn-8 reminder.
    run_review(corpus, corpus.manifest, ledger, budget, telemetry, ForcedRunaway(), registry)

    records, _ = read_turns(tmp_path / "turns.jsonl")
    reminders = [r for r in records if r["record_type"] == "coverage_reminder"]
    assert len(reminders) >= 1, "expected a coverage reminder by turn 8"

    summary = RunSummary.from_turns(
        provenance=capture_provenance(run_index=1, corpus_content_hash="x", run_completed=True),
        records=records, budget_ledger=budget,
    )
    assert summary.coverage_reminder_count == len(reminders)
    assert summary.coverage_reminder_turns == [r["turn_index"] for r in reminders]


def test_coverage_reminder_is_not_in_the_static_prefix(tmp_path):
    """COST-01: the reminder is a runtime message, so the rendered prefix never contains it."""
    from agents.review.loop import render_prefix
    corpus = build_corpus_index(tmp_path, "d1", [_block("Alpha text.")])
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=RetrievalLedger())
    assert "Coverage check" not in render_prefix(registry)
