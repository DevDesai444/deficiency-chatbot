"""The fault-detection layer entry point.

Runs the four stages over the structured document and returns a FaultReport:
  Stage 1 oracles + Stage 2 checklists (deterministic, unconditional)  ┐
  Stage 3 selection → specialists + open reviewers (parallel)          ├→ Stage 4 verify+tier
"""
from __future__ import annotations

import concurrent.futures
import time

import structlog

from agents.detection.challenge import challenge_faults
from agents.detection.checklists import run_checklists
from agents.detection.ctd import describe_document, detect_ctd_section
from agents.detection.oracles import run_oracles
from agents.detection.planning import run_planner
from agents.detection.summarise import summarise_sections
from agents.detection.verify import verify_and_tier
from agents.detection.workers import run_workers
from agents.event_bus import emit_sync
from config import DETECTOR_MODELS, resolve_detector_model
from schemas.faults import FaultReport

log = structlog.get_logger()


def _leading_text(doc: dict, pages: int = 3) -> str:
    parts: list[str] = []
    for page in doc.get("pages", [])[:pages]:
        for block in page.get("blocks", []):
            parts.append(block.get("text") or "")
    return " ".join(parts)


def run_detection(
    doc: dict, sections: list[dict], groups: list[dict], job_id: str = "", model: str | None = None
) -> FaultReport:
    start = time.time()
    detector_model = resolve_detector_model(model)
    ctd = detect_ctd_section(_leading_text(doc) or doc.get("filename", ""))
    doc_desc = describe_document(ctd)
    emit_sync(job_id, "detection", "layer_start", "Detection", f"Reviewing {doc_desc}")
    emit_sync(
        job_id, "detection", "agent_message", "Detection",
        f"Model: {DETECTOR_MODELS.get(detector_model, detector_model)}",
    )

    # Stage 1 + 2 — deterministic, run unconditionally on the full doc.
    oracle_faults = run_oracles(doc)
    checklist_faults = run_checklists(doc, ctd)
    emit_sync(
        job_id, "detection", "oracle_complete", "Oracles",
        f"{len(oracle_faults)} code-verified, {len(checklist_faults)} checklist findings",
    )

    # Stage 3 — planner ∥ summariser (concurrent), then the two-pass worker fan-out.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        plan_future = pool.submit(run_planner, sections, doc, detector_model)
        summary_future = pool.submit(summarise_sections, sections, detector_model)
        plan = plan_future.result()
        summaries = summary_future.result()

    focused_headings: list[str] = []
    for w in plan.workers:
        for i in w.focused_section_indices:
            if i < len(sections):
                heading = sections[i].get("heading", "")
                if heading and heading not in focused_headings:
                    focused_headings.append(heading)
    routed = sum(len(w.suspicions) for w in plan.workers)
    emit_sync(
        job_id, "detection", "selection", "Planner",
        f"{len(plan.workers)} specialist workers, {routed} suspicions routed",
    )
    for w in plan.workers:
        emit_sync(
            job_id, "detection", "agent_spawned",
            "specialist:" + ",".join(str(i) for i in w.focused_section_indices),
            (w.instruction or "")[:80],
        )
    agent_faults, failures = run_workers(sections, summaries, plan, doc_desc, model=detector_model)

    # Stage 4 — verify + tier + dedup, then the grounded challenge (scores, never vetoes).
    faults = verify_and_tier(oracle_faults + checklist_faults + agent_faults, doc)
    faults = challenge_faults(faults, sections, doc, model=detector_model)
    emit_sync(job_id, "detection", "agent_message", "Challenge", "Grounded-challenge pass complete")
    emit_sync(
        job_id, "detection", "layer_complete", "Detection",
        f"{len(faults)} faults surfaced ({len(failures)} worker parse failures)",
    )
    log.info("detection_complete", faults=len(faults), workers=len(plan.workers), seconds=round(time.time() - start, 1))

    return FaultReport(
        job_id=job_id,
        faults=faults,
        faults_found=bool(faults),
        domains_checked=focused_headings,
        parse_failures=failures,
        analysis_seconds=round(time.time() - start, 1),
    )
