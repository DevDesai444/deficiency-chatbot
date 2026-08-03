"""Stage 3, part 1 — the planner (Prompt ①).

One LLM call reads the whole structured document and returns a review plan: how to split the
sections among specialist workers (1-2 sections each, by judgement) and which suspected faults to
route to which worker. Suspicions are leads, not a checklist — every worker still reviews its
section(s) as a full specialist. A deterministic coverage-repair guarantees every section is owned
by at least one specialist even if the model under-assigns, so the plan can never create a blind spot.
"""
from __future__ import annotations

import json
import re

import structlog
from pydantic import BaseModel, Field

from agents.detection.prompts import PLANNER
from config import get_settings
from llm.structured import structured_call

log = structlog.get_logger()

_MAX_FOCUS = 2
_MAX_WORKERS = 12


class SuspicionEvidence(BaseModel):
    section_index: int = Field(default=-1, description="The section this quote comes from.")
    quote: str = Field(default="", description="Verbatim quote from that section.")


class Suspicion(BaseModel):
    claim: str = Field(description="The suspected deficiency, one line.")
    reasoning: str = Field(default="", description="Why it is suspected.")
    cross_section: bool = Field(default=False, description="True if it spans more than one section.")
    evidence: list[SuspicionEvidence] = Field(default_factory=list)


class WorkerAssignment(BaseModel):
    focused_section_indices: list[int] = Field(default_factory=list, description="1-2 section indices this worker owns.")
    instruction: str = Field(default="", description="The domain or lens this worker should focus on.")
    suspicions: list[Suspicion] = Field(default_factory=list)


class ReviewPlan(BaseModel):
    workers: list[WorkerAssignment] = Field(default_factory=list)


def _doc_json_for_planner(sections: list[dict], char_budget: int = 300_000) -> str:
    """Render the WHOLE document as JSON for the planner — no section is ever dropped (unlike a
    worker's bounded sandwich), because the planner is the one component that must see everything to
    route cross-section suspicions. Each section goes out as {section_index, heading, text, tables};
    tables carry the numbers that reveal intersections. Only if the doc is enormous do we drop prose
    (heading + tables kept) — never a whole section."""
    def obj(i: int, s: dict, with_text: bool) -> dict:
        o = {"section_index": i, "heading": s.get("heading", ""), "tables": s.get("tables", [])}
        if with_text:
            o["text"] = s.get("text", "")
        return o

    full = json.dumps([obj(i, s, True) for i, s in enumerate(sections)], ensure_ascii=False)
    if len(full) <= char_budget:
        return full
    log.warning("planner_doc_over_budget_dropping_prose", chars=len(full), sections=len(sections))
    return json.dumps([obj(i, s, False) for i, s in enumerate(sections)], ensure_ascii=False)


def _fallback_plan(n_sections: int) -> ReviewPlan:
    workers: list[WorkerAssignment] = []
    for start in range(0, n_sections, _MAX_FOCUS):
        idx = list(range(start, min(start + _MAX_FOCUS, n_sections)))
        workers.append(WorkerAssignment(focused_section_indices=idx, instruction="Full specialist review of this region."))
    return ReviewPlan(workers=workers)


def _sanitize(plan: ReviewPlan, n_sections: int) -> ReviewPlan:
    """Clamp indices to range, cap focus at 2, drop empty workers. Never lets a hallucinated index
    reach the assembler."""
    clean: list[WorkerAssignment] = []
    for w in plan.workers:
        idx: list[int] = []
        for i in w.focused_section_indices:
            if 0 <= i < n_sections and i not in idx:
                idx.append(i)
        idx = idx[:_MAX_FOCUS]
        if not idx:
            continue
        clean.append(WorkerAssignment(focused_section_indices=idx, instruction=w.instruction, suspicions=w.suspicions))
    return ReviewPlan(workers=clean[:_MAX_WORKERS])


def _ensure_coverage(plan: ReviewPlan, n_sections: int) -> ReviewPlan:
    """Every section must be owned by >=1 specialist; add fallback workers for any gap. Coverage
    beats the worker cap — a blind spot is worse than an extra call."""
    covered: set[int] = set()
    for w in plan.workers:
        covered.update(w.focused_section_indices)
    missing = [i for i in range(n_sections) if i not in covered]
    for start in range(0, len(missing), _MAX_FOCUS):
        idx = missing[start:start + _MAX_FOCUS]
        plan.workers.append(WorkerAssignment(focused_section_indices=idx, instruction="Full specialist review of this region (coverage fill)."))
    return plan


def _section_table_text(section: dict) -> str:
    chunks: list[str] = [section.get("heading", ""), section.get("text", "")]
    for table in section.get("tables", []) or []:
        chunks.append(str(table.get("title", "")))
        chunks.extend(str(h) for h in (table.get("headers") or []))
        for row in table.get("rows") or []:
            chunks.extend(str(c) for c in row)
    return " ".join(c for c in chunks if c)


def _route_suspicion(plan: ReviewPlan, section_index: int, suspicion: Suspicion) -> None:
    claim_key = suspicion.claim.strip().lower()
    for worker in plan.workers:
        if any(s.claim.strip().lower() == claim_key for s in worker.suspicions):
            return
    for worker in plan.workers:
        if section_index in worker.focused_section_indices:
            worker.suspicions.append(suspicion)
            return
    plan.workers.append(
        WorkerAssignment(
            focused_section_indices=[section_index],
            instruction="Full specialist review of this table-derived suspected deficiency.",
            suspicions=[suspicion],
        )
    )


def _clean_cell(cell) -> str:
    return re.sub(r"\s+", " ", str(cell or "")).strip()


def _first_number(cell: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", cell.replace(",", ""))
    return float(match.group(0)) if match else None


def _row_label(row: list) -> str:
    return _clean_cell(row[0]) if row else ""


def _table_name(table: dict) -> str:
    return _clean_cell(table.get("title") or "A table")


def _header_name(headers: list, index: int) -> str:
    if 0 <= index < len(headers):
        return _clean_cell(headers[index])
    return f"column {index + 1}"


def _is_summary_label(label: str) -> bool:
    return bool(re.search(r"\b(?:minimum|maximum|mean|average|total)\b", label, flags=re.IGNORECASE))


def _summary_suspicions(section_index: int, table: dict) -> list[Suspicion]:
    rows = table.get("rows") or []
    headers = table.get("headers") or []
    out: list[Suspicion] = []
    for row in rows:
        label = _row_label(row)
        if not re.search(r"\bmaximum\b", label, flags=re.IGNORECASE):
            continue
        for col, cell in enumerate(row[1:], start=1):
            summary_value = _first_number(_clean_cell(cell))
            if summary_value is None:
                continue
            candidates: list[tuple[float, str, str]] = []
            for other in rows:
                other_label = _row_label(other)
                if other is row or _is_summary_label(other_label) or other_label.lower().startswith("reference"):
                    continue
                if col >= len(other):
                    continue
                other_cell = _clean_cell(other[col])
                other_value = _first_number(other_cell)
                if other_value is not None:
                    candidates.append((other_value, other_label, other_cell))
            if not candidates:
                continue
            observed_value, observed_label, observed_cell = max(candidates, key=lambda x: x[0])
            if observed_value <= summary_value:
                continue
            column = _header_name(headers, col)
            table_name = _table_name(table)
            out.append(
                Suspicion(
                    claim=(
                        f"{table_name} states {label} for {column} as {_clean_cell(cell)}, "
                        f"but row {observed_label} reports {observed_cell}; the summary cell appears wrong."
                    ),
                    reasoning="A Maximum summary cell cannot be lower than one of the values it summarizes.",
                    cross_section=False,
                    evidence=[
                        SuspicionEvidence(section_index=section_index, quote=f"{label} {column} {_clean_cell(cell)}"),
                        SuspicionEvidence(section_index=section_index, quote=f"{observed_label} {column} {observed_cell}"),
                    ],
                )
            )
    return out


def _limit_terms(label: str) -> set[str]:
    generic = {"any", "the", "and", "method", "result", "results", "single", "largest", "estradiol"}
    return {
        token
        for token in re.findall(r"[A-Za-z]{4,}", label.lower())
        if token not in generic
    }


def _section_nmt_limits(section: dict) -> list[tuple[str, float, str]]:
    limits: list[tuple[str, float, str]] = []
    for table in section.get("tables", []) or []:
        for row in table.get("rows") or []:
            for cell in row:
                text = _clean_cell(cell)
                for match in re.finditer(r"([^:\n\r•]{4,120}?)\s*:\s*NMT\s*(\d+(?:\.\d+)?)\s*%", text, flags=re.IGNORECASE):
                    label = _clean_cell(match.group(1))
                    limits.append((label, float(match.group(2)), match.group(0)))
    return limits


def _spec_exceedance_suspicions(section_index: int, section: dict) -> list[Suspicion]:
    limits = _section_nmt_limits(section)
    if not limits:
        return []
    out: list[Suspicion] = []
    seen: set[tuple[str, str]] = set()
    for table in section.get("tables", []) or []:
        for row in table.get("rows") or []:
            label = _row_label(row)
            label_terms = _limit_terms(label)
            if not label_terms:
                continue
            for limit_label, limit_value, limit_quote in limits:
                if not (_limit_terms(limit_label) & label_terms):
                    continue
                for cell in row[1:]:
                    result_cell = _clean_cell(cell)
                    if re.search(r"\bNMT\b|\bNLT\b", result_cell, flags=re.IGNORECASE):
                        continue
                    result_value = _first_number(result_cell)
                    if result_value is None or result_value <= limit_value:
                        continue
                    key = (label.lower(), limit_label.lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    table_name = _table_name(table)
                    out.append(
                        Suspicion(
                            claim=(
                                f"{table_name} reports {label} as {result_cell}, while the applicable "
                                f"{limit_label} criterion is {limit_quote}; the result appears above its limit."
                            ),
                            reasoning="A reported result above a not-more-than specification limit is a suspected deficiency.",
                            cross_section=False,
                            evidence=[
                                SuspicionEvidence(section_index=section_index, quote=f"{label} {result_cell}"),
                                SuspicionEvidence(section_index=section_index, quote=limit_quote),
                            ],
                        )
                    )
    return out


def _seed_table_suspicions(plan: ReviewPlan, sections: list[dict]) -> ReviewPlan:
    """Seed bounded table leads the planner prompt is meant to route, without minting faults.

    These are suspicion leads only. Workers still confirm/refute them and `_to_faults` only emits a
    fault when a real deficiency is asserted. The guard closes the observed failure mode where a valid
    plan covered the TP-bearing sections but routed zero suspicions for obvious table contradictions.
    """
    for i, section in enumerate(sections):
        for table in section.get("tables", []) or []:
            for suspicion in _summary_suspicions(i, table):
                _route_suspicion(plan, i, suspicion)
        for suspicion in _spec_exceedance_suspicions(i, section):
            _route_suspicion(plan, i, suspicion)
    return plan


def run_planner(sections: list[dict], doc: dict, model: str | None = None) -> ReviewPlan:
    model = model or get_settings().detector_model
    n = len(sections)
    if n == 0:
        return ReviewPlan(workers=[])
    inst, failure = structured_call(
        messages=[
            {"role": "system", "content": PLANNER},
            {"role": "user", "content": f"Document: {doc.get('filename', '')}\n\n{_doc_json_for_planner(sections)}"},
        ],
        model_cls=ReviewPlan,
        model=model,
        temperature=0.0,
        max_tokens=2048,
        repair_context="planner",
    )
    if inst is None:
        log.warning("planner_failed_using_fallback", reason=(failure.reason if failure else ""))
        return _seed_table_suspicions(_ensure_coverage(_fallback_plan(n), n), sections)
    return _seed_table_suspicions(_ensure_coverage(_sanitize(inst, n), n), sections)
