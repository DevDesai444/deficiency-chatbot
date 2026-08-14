"""The Gap-1 report-assembly seam: which SURFACE a verified fault appears on (never whether it exists).

``evals.metrics._end_to_end`` scores ``report.faults`` AS-IS — every fault in that list, regardless
of ``confidence_tier``. So a DOWNGRADEd-but-still-present false positive would count as a FULL FP and
F1 would be identical before and after verification: a NO-OP verifier passes the gate (Gap 1). This
helper closes that proxy-gate by surfacing ONLY KEEP-tier (active) faults in the scored
``FaultReport.faults``; DOWNGRADEd faults (``confidence_tier == "low"``) are excluded from ``.faults``
so a downgrade actually LOWERS the FP count the frozen path sees.

Nothing is silently dropped (the β no-drop law): a DOWNGRADEd fault is already recorded in
``CoverageReport.reviewed_downgrade`` (the audit trail the orchestrator wrote), so it stays VISIBLE
to the human AND countable by the zero-TP-loss recall accounting (``downgraded_dedup_keys``). This
helper NEVER deletes a Fault — it only decides whether a fault appears on the ACTIVE surface
(``report.faults``, scored for precision) or the DOWNGRADED surface (coverage, retained for recall).

A ``could_not_locate`` candidate keeps ``confidence_tier == "full"`` (a could-not-locate is NOT a
DOWNGRADE), so it STAYS in ``report.faults`` — reviewed-but-not-gradeable, still active.
"""
from __future__ import annotations

from schemas.faults import FaultReport
from verify.coverage import CoverageReport


def downgraded_dedup_keys(coverage: CoverageReport) -> set[str]:
    """The dedup_keys DOWNGRADEd by consensus — the zero-TP-loss accessor Plan 04 reads.

    A downgraded-but-present true positive is still "matched" for recall accounting: the F1
    zero-TP-loss check reads ``report.faults`` (active) UNION these keys (downgraded, retained in
    coverage) so no baseline TP is lost merely because it was moved to the downgraded surface.
    """
    return {row["dedup_key"] for row in coverage.reviewed_downgrade if "dedup_key" in row}


def assemble_scored_report(
    verified_faults: list,
    coverage: CoverageReport,
    *,
    job_id: str = "",
) -> FaultReport:
    """Build the scored ``FaultReport`` — KEEP-tier faults ONLY in ``.faults`` (Gap-1 filter).

    ``active`` = faults whose ``confidence_tier != "low"`` (KEEP-tier + could-not-locate — the
    findings the frozen F1 path scores). DOWNGRADEd faults (tier ``"low"``) are NOT added to
    ``.faults``; they are already retained in ``coverage.reviewed_downgrade`` (audit trail), so
    nothing is silently dropped: ``len(active) + len(downgraded present in coverage)`` accounts for
    every verified fault. This helper NEVER deletes a Fault — a downgrade changes SURFACE, not
    existence (the β no-drop law).
    """
    active = [f for f in verified_faults if getattr(f, "confidence_tier", None) != "low"]
    return FaultReport(
        job_id=job_id,
        faults=active,
        faults_found=bool(active),
    )
