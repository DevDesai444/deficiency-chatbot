from __future__ import annotations

import time

import structlog

from agents.detection import run_detection
from agents.event_bus import emit_sync
from databricks.delta import create_job, update_job_status
from parse.pdf import extract_pdf
from parse.section_splitter import group_sections, split_document
from schemas.faults import FaultReport

log = structlog.get_logger()


def run_pipeline(pdf_path: str, job_id: str, model: str | None = None) -> FaultReport:
    log = structlog.get_logger().bind(job_id=job_id)
    start = time.time()
    emit_sync(job_id, "detection", "pipeline_start", "Orchestrator", "Starting analysis pipeline")

    try:
        create_job(job_id, pdf_path)
    except Exception:
        log.warning("job_creation_failed")

    update_job_status(job_id, "parsing")
    doc = extract_pdf(pdf_path)
    sections = split_document(doc)
    groups = group_sections(sections)
    log.info("parsed_document", pages=doc["page_count"], sections=len(sections), groups=len(groups))

    update_job_status(job_id, "detecting")
    report = run_detection(doc, sections, groups, job_id=job_id, model=model)
    report.job_id = job_id
    report.analysis_seconds = round(time.time() - start, 1)

    # Stored in the existing flaw_report column (no schema migration); exposed as `faults`.
    update_job_status(job_id, "complete", flaw_report=report.model_dump())

    emit_sync(
        job_id, "detection", "pipeline_complete", "Orchestrator",
        f"Analysis complete in {report.analysis_seconds:.1f}s — {len(report.faults)} faults",
    )
    log.info("pipeline_complete", faults=len(report.faults), seconds=report.analysis_seconds)

    return report
