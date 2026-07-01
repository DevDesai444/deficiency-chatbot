from __future__ import annotations

import time

import structlog

from agents.correction.loop import run_correction_loop
from agents.detection.group import run_flaw_detection
from agents.event_bus import emit_sync
from agents.extraction.group import run_extraction
from databricks.delta import create_job, update_job_status
from parse.pdf import extract_pdf
from parse.section_splitter import classify_document, group_sections, split_document
from schemas.corrections import RecommendationSet


def run_pipeline(pdf_path: str, job_id: str) -> RecommendationSet:
    log = structlog.get_logger().bind(job_id=job_id)
    start = time.time()
    emit_sync(job_id, "extraction", "agent_spawned", "Orchestrator", "Starting analysis pipeline")

    try:
        create_job(job_id, pdf_path)
    except Exception:
        log.warning("job_creation_failed")

    update_job_status(job_id, "extracting")

    doc = extract_pdf(pdf_path)
    ctd_section = classify_document(doc)
    sections = split_document(doc)
    groups = group_sections(sections)

    log.info(
        "parsed_document",
        pages=doc.page_count,
        sections=len(sections),
        groups=len(groups),
        ctd_section=ctd_section.value,
    )

    intermediate_report = run_extraction(
        groups=groups,
        document_name=doc.filename,
        document_type=ctd_section.value,
        job_id=job_id,
    )

    update_job_status(
        job_id, "detecting",
        intermediate_report=intermediate_report.model_dump(),
    )

    flaw_report = run_flaw_detection(
        intermediate_report=intermediate_report,
        document_section=ctd_section,
        job_id=job_id,
    )

    update_job_status(
        job_id, "correcting",
        flaw_report=flaw_report.model_dump(),
    )

    result = run_correction_loop(
        flaw_report=flaw_report,
        job_id=job_id,
    )

    elapsed = time.time() - start
    result.analysis_seconds = elapsed

    update_job_status(
        job_id, "complete",
        recommendations=result.model_dump(),
    )

    emit_sync(
        job_id, "extraction", "pipeline_complete", "Orchestrator",
        f"Analysis complete in {elapsed:.1f}s — {len(result.recommendations)} recommendations",
    )

    log.info(
        "pipeline_complete",
        flaws_found=result.flaws_found,
        recommendations=len(result.recommendations),
        seconds=round(elapsed, 1),
    )

    return result
