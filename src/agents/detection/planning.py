"""Stage 3, part 1 — the planner (Prompt ①).

One LLM call reads the whole structured document and returns a review plan: how to split the
sections among specialist workers (1-2 sections each, by judgement) and which suspected faults to
route to which worker. Suspicions are leads, not a checklist — every worker still reviews its
section(s) as a full specialist. A deterministic coverage-repair guarantees every section is owned
by at least one specialist even if the model under-assigns, so the plan can never create a blind spot.
"""
from __future__ import annotations

import json

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
        return _ensure_coverage(_fallback_plan(n), n)
    return _ensure_coverage(_sanitize(inst, n), n)
