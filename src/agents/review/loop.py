"""Review loop mechanics for AGENT-01."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agents.review.budget import BudgetLedger
from agents.review.prompts import SYSTEM_PROMPT
from agents.review.registry import DispatchResult, ToolRegistry
from agents.review.telemetry import TurnLog
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from llm.client import ChatTurn
from schemas.faults import Fault, FaultReport
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger

CompleteFn = Callable[[list[dict], list[dict]], ChatTurn]


@dataclass
class ReviewResult:
    """Return object for a review run, preserving grounded partials on abort."""

    findings: list[Fault] = field(default_factory=list)
    stop_reason: str = ""
    report: FaultReport = field(default_factory=FaultReport)
    messages: list[dict] = field(default_factory=list)
    aborted: bool = False
    error: str = ""


def _span_keys(ledger: RetrievalLedger) -> set[tuple[str, int, int]]:
    return set(getattr(ledger, "_issued", set()))


def _call_id(call: object) -> str:
    if isinstance(call, dict):
        return str(call.get("id", ""))
    return str(getattr(call, "id", ""))


def _call_function(call: object) -> tuple[str, str]:
    if isinstance(call, dict):
        fn = call.get("function") or {}
        name = str(fn.get("name", ""))
        args = fn.get("arguments", "{}")
    else:
        fn = getattr(call, "function", None)
        name = str(getattr(fn, "name", ""))
        args = getattr(fn, "arguments", "{}")
    if isinstance(args, str):
        raw_args = args
    else:
        raw_args = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return name, raw_args


def _corpus_brief(corpus: CorpusIndex, manifest: CoverageManifest) -> str:
    rows = [
        "Corpus manifest for this review run.",
        f"Document count: {len(manifest.documents)}",
    ]
    families: set[str] = set()
    for doc in manifest.documents:
        classification = doc.classification.model_dump(mode="json") if doc.classification else None
        if isinstance(classification, dict):
            for key in ("family", "ctd_family", "document_family"):
                value = classification.get(key)
                if value:
                    families.add(str(value))
        rows.append(
            "Document: "
            f"doc_id={doc.doc_id}; title={doc.title}; filename={doc.filename}; "
            f"status={doc.status}; structure={doc.structure}; tables={doc.tables}"
        )
        if doc.outline:
            headings = "; ".join(o.label for o in doc.outline[:20])
            rows.append(f"Outline for {doc.doc_id}: {headings}")
    if families:
        rows.append("Detected families: " + ", ".join(sorted(families)))
    if not corpus.root:
        rows.append("Corpus root unavailable.")
    return "\n".join(rows)


def build_messages(corpus_brief: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": corpus_brief},
    ]


def _make_report(findings: list[Fault], stop_reason: str, elapsed: float) -> FaultReport:
    return FaultReport(
        faults=list(findings),
        faults_found=bool(findings),
        stop_reason=stop_reason,
        budget_exhausted=stop_reason == "ceiling",
        analysis_seconds=round(elapsed, 1),
    )


def _finalize(
    *,
    findings: list[Fault],
    stop_reason: str,
    messages: list[dict],
    started_at: float,
    aborted: bool = False,
    error: str = "",
) -> ReviewResult:
    report = _make_report(findings, stop_reason, time.monotonic() - started_at)
    return ReviewResult(
        findings=list(findings),
        stop_reason=stop_reason,
        report=report,
        messages=messages,
        aborted=aborted,
        error=error,
    )


def _count_requirement_ids(value: object, seen: set[str]) -> int:
    rows = value if isinstance(value, list) else []
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        requirement_id = str(row.get("requirement_id", ""))
        if requirement_id and requirement_id not in seen:
            seen.add(requirement_id)
            count += 1
    return count


def _record_dispatch_telemetry(telemetry: TurnLog, result: DispatchResult) -> None:
    if result.repair_layer in {"pre", "post"}:
        telemetry.repair(result.repair_layer, result.tool)
    if isinstance(result.raw_result, ToolRejected):
        telemetry.rejection(result.tool, result.raw_result.reason_code, result.raw_result.half)
    elif result.tool == "run_oracles" and isinstance(result.raw_result, list):
        telemetry.oracle_leads(len(result.raw_result))


def render_prefix(registry: Any) -> str:
    """Serialize the static provider prefix: system message plus tool schemas."""
    prefix = {
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        "tools": registry.schemas(),
    }
    return json.dumps(prefix, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def run_review(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    budget: BudgetLedger,
    telemetry: TurnLog,
    complete: CompleteFn,
    registry: ToolRegistry,
) -> ReviewResult:
    """Run the model-driven review loop over injected collaborators."""
    started_at = time.monotonic()
    findings: list[Fault] = []
    seen_requirement_ids: set[str] = set()
    messages = build_messages(_corpus_brief(corpus, manifest))
    tools = registry.schemas()

    while True:
        turn = complete(messages, tools)
        budget.record_turn(turn)
        telemetry.turn(
            index=budget.turns,
            finish_reason=turn.finish_reason,
            prompt_tokens=turn.prompt_tokens,
            completion_tokens=turn.completion_tokens,
            cached_tokens=turn.cached_tokens,
            usage_present=turn.usage_present,
        )

        if turn.finish_reason == "error":
            return _finalize(
                findings=findings,
                stop_reason="aborted",
                messages=messages,
                started_at=started_at,
                aborted=True,
                error="completion finish_reason=error",
            )

        hard_stop = budget.stop_reason()
        if hard_stop != "completed":
            return _finalize(
                findings=findings,
                stop_reason=hard_stop,
                messages=messages,
                started_at=started_at,
                aborted=hard_stop == "ceiling",
            )

        if not turn.tool_calls:
            return _finalize(
                findings=findings,
                stop_reason="completed",
                messages=messages,
                started_at=started_at,
            )

        messages.append(turn.raw_message)
        span_keys_before = _span_keys(ledger)
        findings_before = len(findings)
        requirements_before = len(seen_requirement_ids)

        for call in list(turn.tool_calls):
            call_id = _call_id(call)
            tool_name, raw_args = _call_function(call)
            try:
                result = registry.dispatch(tool_name, raw_args)
            except Exception as exc:  # noqa: BLE001 - an aborted run must return its partial.
                content = f"REJECTED[dispatch_exception] {type(exc).__name__}: {exc}"
                messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
                telemetry.turn(index=budget.turns, dispatch_exception=type(exc).__name__, tool=tool_name)
                budget.record_productivity(0, 0, 0)
                return _finalize(
                    findings=findings,
                    stop_reason="aborted",
                    messages=messages,
                    started_at=started_at,
                    aborted=True,
                    error=content,
                )

            _record_dispatch_telemetry(telemetry, result)
            if isinstance(result.raw_result, Fault):
                findings.append(result.raw_result)

            _count_requirement_ids(result.raw_result, seen_requirement_ids)
            messages.append({"role": "tool", "tool_call_id": call_id, "content": str(result.result)})

        new_spans = len(_span_keys(ledger) - span_keys_before)
        new_faults = len(findings) - findings_before
        new_requirements = len(seen_requirement_ids) - requirements_before
        budget.record_productivity(new_spans, new_faults, new_requirements)


__all__ = ["CompleteFn", "ReviewResult", "build_messages", "render_prefix", "run_review"]
