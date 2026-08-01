"""Stage 3, part 2 — the two-pass worker fan-out.

Pass 1: planner-assigned SPECIALISTS — each owns 1-2 sections (full), carries the suspicions the
planner routed to it, precedent-seeded, and reviews as a full domain specialist.
Pass 2: blank-slate OPEN REVIEWERS — a mechanical sweep of every section (1-2 at a time), no
suspicions, primed to flag anything. This pass does not depend on the planner, so a bad plan cannot
create a blind spot.

Every section is therefore reviewed by >=1 specialist AND >=1 open reviewer; the union goes to
Stage 4 (verify + challenge), which dedups. All calls run in one thread pool.
"""
from __future__ import annotations

import concurrent.futures
import json

import structlog
from pydantic import BaseModel, Field

from agents.detection.prompts import WORKER_OPEN, WORKER_SPECIALIST
from agents.detection.sandwich import build_sandwich, open_review_chunks, render_sandwich
from config import get_settings
from llm.structured import structured_call
from schemas.faults import EvidenceClass, Fault, Tier
from schemas.flaws import Severity

log = structlog.get_logger()

_MAX_WORKERS = 10


class WorkerFinding(BaseModel):
    title: str = Field(description="One-line statement of the deficiency.")
    detail: str = Field(default="", description="What is wrong and why, argued from the evidence.")
    evidence: str = Field(default="", description="Verbatim value/cell/sentence — from a focused section, or a verbatim table cell from any section.")
    section: str = Field(default="", description="Section heading or number the fault sits in.")
    page: int = 0
    table_ref: str = Field(default="", description="Table it concerns, e.g. 'Table 16'; empty if none.")
    rule_cited: str = Field(default="", description="The specific rule/criterion it violates, e.g. 'ICH Q2'.")
    cited_section_indices: list[int] = Field(default_factory=list, description="Every section index this finding relates, when it spans sections.")
    severity: Severity = Severity.MEDIUM


class SuspicionVerdict(BaseModel):
    claim: str = Field(default="", description="The routed suspicion this verdict answers.")
    verdict: str = Field(default="unclear", description="confirmed | refuted | unclear")
    # `verdict: confirmed` only says the claim is TRUE — and a planner claim is often a neutral
    # check ("Table 1 requires NMT 33%, Table 8 shows 18.9%"), whose truth means the document is
    # COMPLIANT. Minting a fault from that reported compliance as a deficiency, so the decision to
    # raise a fault hangs on this separate, explicit assertion instead.
    deficiency_exists: bool = Field(
        default=False,
        description="True ONLY if a real deficiency exists that an FDA reviewer would raise. False if the data complies.",
    )
    evidence: str = Field(default="", description="The passage that decides it.")


class WorkerOutput(BaseModel):
    findings: list[WorkerFinding] = Field(default_factory=list)
    suspicion_verdicts: list[SuspicionVerdict] = Field(default_factory=list)


def _precedents_for(assignment, sections: list[dict]):
    heads = " ".join(sections[i].get("heading", "") for i in assignment.focused_section_indices if i < len(sections))
    query = f"{assignment.instruction} {heads}".strip()
    if not query:
        return []
    # Lazy import: keeps the sentence-transformers/torch chain out of package import time — it
    # only loads when precedents are actually fetched during a real run.
    from retrieval.knowledge_base import find_similar_deficiencies
    try:
        return find_similar_deficiencies(query, top_k=3)
    except Exception as exc:  # noqa: BLE001 - precedent retrieval is best-effort
        log.warning("precedent_retrieval_failed", error=str(exc)[:200])
        return []


def _finding_to_fault(f: WorkerFinding, source: str, precedents) -> Fault:
    return Fault(
        title=(f.title or "").strip(),
        detail=f.detail,
        severity=f.severity,
        evidence=f.evidence,
        section=f.section,
        page=f.page,
        table_ref=f.table_ref,
        guidance_refs=[f.rule_cited] if f.rule_cited else [],
        cited_section_indices=f.cited_section_indices,
        source=source,
        precedents=list(precedents),
        evidence_class=EvidenceClass.MODEL_JUDGMENT,
        tier=Tier.ADVISORY,
    )


def _to_faults(out: WorkerOutput, source: str, precedents, suspicions) -> list[Fault]:
    faults: list[Fault] = []
    for f in out.findings:
        if not (f.title or "").strip():
            continue
        faults.append(_finding_to_fault(f, source, precedents))

    # A suspicion becomes a fault only when the worker asserts an actual deficiency — not merely
    # that the planner's claim was true. Carry the section indices it spans so the grounded
    # challenge can see both halves of a cross-section fault.
    by_claim = {(s.claim or "").strip().lower(): s for s in suspicions}
    for v in out.suspicion_verdicts:
        if (v.verdict or "").strip().lower() != "confirmed" or not v.deficiency_exists:
            continue
        susp = by_claim.get((v.claim or "").strip().lower())
        cited = [e.section_index for e in susp.evidence if e.section_index >= 0] if susp else []
        planner_ev = " | ".join(e.quote for e in susp.evidence if e.quote) if susp else ""
        faults.append(
            Fault(
                title=(v.claim or "Confirmed suspected deficiency").strip(),
                detail=(susp.reasoning if susp else ""),
                evidence=(v.evidence or planner_ev),
                source=f"{source}:suspicion",
                precedents=list(precedents),
                cited_section_indices=cited,
                evidence_class=EvidenceClass.MODEL_JUDGMENT,
                tier=Tier.ADVISORY,
            )
        )
    return faults


def _cross_section_focus(assignment, n_sections: int) -> list[int]:
    """The worker's own sections PLUS any section a cross-section suspicion cites — so both halves
    of an intersection fault are rendered FULL in the sandwich, not one full + one summary."""
    focus = list(assignment.focused_section_indices)
    for suspicion in assignment.suspicions:
        if not suspicion.cross_section:
            continue
        for ev in suspicion.evidence:
            if 0 <= ev.section_index < n_sections and ev.section_index not in focus:
                focus.append(ev.section_index)
    return focus


def _run_specialist(assignment, sections, summaries, doc_desc, model):
    precedents = _precedents_for(assignment, sections)
    sandwich = build_sandwich(sections, summaries, _cross_section_focus(assignment, len(sections)))
    suspicions_json = json.dumps([s.model_dump() for s in assignment.suspicions], ensure_ascii=False, indent=1)
    system = WORKER_SPECIALIST.format(doc_desc=doc_desc, instruction=assignment.instruction or "Full specialist review.")
    user = (
        "SANDWICH (only role=focused sections are yours to review in depth; role=context are summaries):\n"
        f"{render_sandwich(sandwich)}\n\n"
        f"SUSPICIONS routed to you (confirm or refute each — they are leads, not a limit):\n{suspicions_json}"
    )
    inst, failure = structured_call(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model_cls=WorkerOutput,
        model=model,
        temperature=0.0,
        max_tokens=2560,
        repair_context="worker:specialist",
    )
    label = "specialist:" + ",".join(str(i) for i in assignment.focused_section_indices)
    return (_to_faults(inst, label, precedents, assignment.suspicions) if inst else []), failure


def _run_open_reviewer(chunk, sections, summaries, doc_desc, model):
    sandwich = build_sandwich(sections, summaries, chunk)
    system = WORKER_OPEN.format(doc_desc=doc_desc)
    user = (
        "SANDWICH (only role=focused sections are yours to review; role=context are summaries):\n"
        f"{render_sandwich(sandwich)}"
    )
    inst, failure = structured_call(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model_cls=WorkerOutput,
        model=model,
        temperature=0.0,
        max_tokens=2560,
        repair_context="worker:open",
    )
    label = "reviewer:" + ",".join(str(i) for i in chunk)
    return (_to_faults(inst, label, [], []) if inst else []), failure


def run_workers(sections, summaries, plan, doc_desc, model=None):
    model = model or get_settings().detector_model
    faults: list[Fault] = []
    failures = []
    if not sections:
        return faults, failures
    chunks = open_review_chunks(len(sections))
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = [pool.submit(_run_specialist, w, sections, summaries, doc_desc, model) for w in plan.workers]
        futures += [pool.submit(_run_open_reviewer, c, sections, summaries, doc_desc, model) for c in chunks]
        for fut in concurrent.futures.as_completed(futures):
            try:
                fs, failure = fut.result()
                faults.extend(fs)
                if failure is not None:
                    failures.append(failure)
            except Exception as exc:  # noqa: BLE001 - one dead worker must not sink the fan-out
                log.warning("worker_failed", error=str(exc)[:200])
    return faults, failures
