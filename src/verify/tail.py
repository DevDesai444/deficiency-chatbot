# VERIFY-04 — the interpretive tail: a Qwen agentic producer whose grounded candidates cross the
# SAME consensus verifier as every deterministic leg. This is the narrow, precision-gated place the
# P3 hand-rolled loop still earns its keep (the P3 NO-GO is the governing caution): the tail never
# bypasses consensus and never runs its own verifier fan-out — the driver (verify.driver) owns the
# single verify_candidates fan-out. tail.py PRODUCES tagged, already-grounded candidates only.
"""Interpretive tail (VERIFY-04).

``run_interpretive_tail`` reuses the EXISTING Phase-3 hand-rolled review loop
(``agents.review.loop.run_review``) on a **Qwen** producer to surface grounded deficiencies no
deterministic rule expresses. It builds no new agent loop — it drives the same ``run_review`` the
``agent-run`` subcommand drives, under a TIGHTER general budget (precision-scoped, not the P3
recall run's wide ceiling). Every candidate ``run_review`` returns was already emitted through the
byte-exact ``emit_finding`` grounding gate (open_span / HashMismatch), so this module does NOT
re-ground; it only TAGS each finding with its producer family "qwen" — writing the family marker
that ``verify.orchestrator.family_of`` reads — so the decorrelated panel
(``verify.panel.panel_for``) excludes the Qwen lineage when the driver verifies these candidates.

Producer family = "qwen" (CONTEXT lock). The tag is recorded in ``Fault.source`` as
``"reviewer:qwen:<detail>"``; ``family_of`` scans the colon tokens against ``config.MODEL_LINEAGE``
values (no hardcoded family literal in the orchestrator) and returns "qwen". The on-prem law is
enforced downstream: ``run_review`` -> ``chat_completion_tools`` -> ``llm.client.get_client``
checks the resolved endpoint against ``config.ON_PREM_ALLOW_LIST`` (T-07-12).
"""
from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

import structlog

from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import TurnLog
from config import MODEL_LINEAGE, VERIFIER_FLEET, resolve_detector_model
from llm.client import chat_completion_tools
from schemas.faults import Fault

log = structlog.get_logger()

# The producer family the tail runs on (CONTEXT lock). Read against MODEL_LINEAGE values — never a
# corpus/submission-specific constant; a lineage tag that config.py owns.
_TAIL_FAMILY = "qwen"

# TIGHT, GENERAL ceilings for the precision-scoped tail (documented general defaults, NOT
# corpus-tuned). Smaller than the P3 recall run's wide budget because the tail is not chasing
# breadth — it surfaces the few interpretive candidates the deterministic legs cannot express, and
# each one still has to survive the consensus verifier. Overridable via the ``budget`` argument.
_TAIL_MAX_TOKENS = 60_000
_TAIL_MAX_WALL_CLOCK_S = 300.0
_TAIL_MAX_TURNS = 16


def _resolve_qwen_model(model: str | None) -> str:
    """Resolve a Qwen-lineage producer endpoint, allow-list-validated, lineage-asserted.

    If ``model`` is given it must resolve (via ``resolve_detector_model`` — the on-prem allow-list
    gate) to an endpoint whose ``MODEL_LINEAGE`` is "qwen". Otherwise pick the first Qwen-lineage
    member of ``VERIFIER_FLEET`` (env-overridable config, no hardcoded endpoint literal). Raises if
    no Qwen endpoint is configured, so the tail never silently runs on a non-Qwen family (which
    would break decorrelation — the panel excludes the PRODUCER family).
    """
    if model is not None:
        resolved = resolve_detector_model(model)
        if MODEL_LINEAGE.get(resolved) != _TAIL_FAMILY:
            raise ValueError(
                f"interpretive tail requires a {_TAIL_FAMILY!r}-lineage producer; "
                f"{resolved!r} has lineage {MODEL_LINEAGE.get(resolved)!r}"
            )
        return resolved
    for endpoint in VERIFIER_FLEET:
        if MODEL_LINEAGE.get(endpoint) == _TAIL_FAMILY:
            return endpoint
    raise ValueError(
        f"no {_TAIL_FAMILY!r}-lineage endpoint in VERIFIER_FLEET; cannot run the interpretive tail"
    )


def _tag_producer_family(fault: Fault, family: str) -> Fault:
    """Stamp the producer-family marker ``family_of`` reads into ``Fault.source``.

    Preserves any detail ``emit_finding`` already recorded (e.g. a CTD section) as the trailing
    token, so ``source`` reads ``"reviewer:<family>:<detail>"``. If the finding already carries a
    ``reviewer:<same-family>:`` marker it is left as-is (idempotent). NEVER re-grounds the finding
    — the byte-exact ``emit_finding`` gate already did that; this only writes the family tag.
    """
    existing = fault.source or ""
    detail = ""
    if existing:
        parts = existing.split(":")
        # Drop a leading producer tag ("reviewer"/"specialist"/…) + any family token it already
        # carried; keep the remaining detail so the CTD/section reference survives the retag.
        tail_tokens = [t for t in parts[1:] if t and MODEL_LINEAGE.get(t) is None and t != family]
        detail = ":".join(tail_tokens)
    fault.source = f"reviewer:{family}:{detail}" if detail else f"reviewer:{family}"
    return fault


def run_interpretive_tail(
    corpus,
    manifest,
    ledger,
    *,
    model: str | None = None,
    budget: BudgetLedger | None = None,
    complete: Callable = chat_completion_tools,
    telemetry: TurnLog | None = None,
    job_id: str = "",
) -> list[Fault]:
    """Produce grounded interpretive-tail Fault candidates via ``run_review`` on a Qwen model.

    Returns the tail candidates, each already grounded (emitted through ``emit_finding``) and TAGGED
    producer_family "qwen" (``verify.orchestrator.family_of`` returns "qwen", so
    ``verify.panel.panel_for`` excludes the Qwen lineage). Builds the loop collaborators exactly as
    ``evals.run.cmd_agent_run`` does — a ``BudgetLedger`` with TIGHT general ceilings, a ``TurnLog``,
    and a ``ToolRegistry`` exposing the read/search + ``emit_finding`` tools — and drives the SAME
    ``run_review`` loop (no new loop). Does NOT verify: the driver owns the single consensus
    fan-out; this function only emits the tagged candidates.
    """
    resolved_model = _resolve_qwen_model(model)
    ledger_budget = budget or BudgetLedger(
        max_tokens=_TAIL_MAX_TOKENS,
        max_wall_clock_s=_TAIL_MAX_WALL_CLOCK_S,
        max_turns=_TAIL_MAX_TURNS,
    )
    # TurnLog persists a JSONL row per turn; when the caller injects none, write to a scratch file
    # so a production tail run never corrupts the agent-run artifact tree (the driver run owns its
    # own artifacts). Offline tests inject a scripted ``complete`` so no live turn is ever taken.
    run_telemetry = telemetry or TurnLog(
        Path(tempfile.gettempdir()) / f"interpretive-tail-{job_id or 'run'}.jsonl"
    )
    registry = ToolRegistry(corpus=corpus, manifest=manifest, ledger=ledger, budget=ledger_budget)

    def _complete(messages: list[dict], tools: list[dict]):
        return complete(messages, tools, model=resolved_model, temperature=0.0)

    result = run_review(
        corpus, manifest, ledger, ledger_budget, run_telemetry, _complete, registry, job_id=job_id
    )

    tagged = [_tag_producer_family(f, _TAIL_FAMILY) for f in result.findings]
    log.info(
        "interpretive_tail",
        model=resolved_model,
        candidates=len(tagged),
        stop_reason=result.stop_reason,
    )
    return tagged


__all__ = ["run_interpretive_tail"]
