from __future__ import annotations

import structlog

from agents.correction.evaluator import evaluate_corrections
from agents.correction.suggestor import generate_corrections
from agents.event_bus import emit_sync
from config import get_settings
from schemas.corrections import RecommendationSet, Verdict
from schemas.flaws import FlawReport

log = structlog.get_logger()


def run_correction_loop(
    flaw_report: FlawReport,
    job_id: str,
) -> RecommendationSet:
    s = get_settings()
    inner_count = 0
    outer_count = 0

    if not flaw_report.flaws_found:
        emit_sync(job_id, "correction", "layer_complete", "", "No flaws to correct")
        return RecommendationSet(
            job_id=job_id,
            recommendations=[],
            flaws_found=False,
        )

    emit_sync(job_id, "correction", "agent_spawned", "Suggestor", "Generating recommendations")

    corrections = generate_corrections(flaw_report)
    best_corrections = corrections

    for outer in range(s.max_outer_loops + 1):
        outer_count = outer

        for inner in range(s.max_inner_loops):
            inner_count = inner + 1
            emit_sync(
                job_id, "correction", "loop_iteration", "Evaluator",
                f"Evaluating (inner loop {inner_count})",
            )

            evaluation = evaluate_corrections(corrections, flaw_report.consensus_summary)

            if evaluation.verdict == Verdict.PASS:
                emit_sync(job_id, "correction", "layer_complete", "", "Recommendations approved")
                return RecommendationSet(
                    job_id=job_id,
                    recommendations=corrections,
                    flaws_found=True,
                    inner_loop_count=inner_count,
                    outer_loop_count=outer_count,
                )

            if evaluation.verdict == Verdict.MINOR_REVISION:
                emit_sync(
                    job_id, "correction", "loop_iteration", "Suggestor",
                    f"Revising based on feedback (inner loop {inner_count})",
                )
                corrections = generate_corrections(flaw_report, evaluation.feedback)
                best_corrections = corrections
                continue

            if evaluation.verdict == Verdict.DEEPER_REVIEW:
                emit_sync(
                    job_id, "correction", "loop_iteration", "",
                    "Evaluator requests deeper review — would kick back to L1+L2",
                )
                break

        if outer < s.max_outer_loops:
            log.info("outer_loop_retry", outer=outer, job_id=job_id)
            emit_sync(
                job_id, "correction", "loop_iteration", "",
                f"Outer loop retry {outer + 1}",
            )

    emit_sync(job_id, "correction", "layer_complete", "", "Returning best-effort recommendations")
    return RecommendationSet(
        job_id=job_id,
        recommendations=best_corrections,
        flaws_found=True,
        inner_loop_count=inner_count,
        outer_loop_count=outer_count,
    )
