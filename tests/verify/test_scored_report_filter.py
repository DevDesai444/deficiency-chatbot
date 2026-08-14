# Gap-1 — the report-assembly filter feeds the FROZEN F1 path only KEEP-tier faults.
"""Gap 1 anti-proxy-gate test (VERIFY-01/02/03, Plan 07-03 Task 3).

``evals.metrics._end_to_end`` scores ``report.faults`` AS-IS, so if a DOWNGRADEd false positive were
left in ``report.faults`` it would still count as a full FP and F1 would be UNCHANGED by
verification — a NO-OP verifier passes. This test drives ``verify_candidates`` so ONE labeled FP and
ONE labeled TP are DOWNGRADEd, assembles the scored report with ``assemble_scored_report``, scores it
through the frozen ``_end_to_end`` path, and asserts BOTH halves:

  (a) the DOWNGRADEd FP is NOT counted as an FP (fp strictly lower than scoring the pre-filter report
      where every verified fault is present);
  (b) the DOWNGRADEd TP is STILL retained — its dedup_key is in ``downgraded_dedup_keys(coverage)``
      and, via presence in report.faults + coverage.reviewed_downgrade, the zero-TP-loss accounting
      still credits it as matched, so no baseline TP is lost by the filter.

A NO-OP verifier (never DOWNGRADEs) fails half (a); a DROP-EVERYTHING verifier loses the TP and
fails half (b).
"""
from __future__ import annotations

from evals.metrics import _end_to_end
from evals.schema import EvalSet, FailureFamily, GroundTruthDeficiency
from schemas.faults import FaultReport
from verify.assemble import assemble_scored_report, downgraded_dedup_keys
from verify.orchestrator import verify_candidates

from tests.verify.conftest import (
    ScriptedFleetClient,
    labeled_fp_candidate,
    labeled_tp_candidate,
    make_verdict_turn,
)

_DOC_ID = "docA"

# The TP evidence carries the verbatim anchor the GT keys on; the FP evidence carries a distinct,
# non-GT number so a DOWNGRADEd FP is a genuine non-fault the matcher never credits.
_TP_ANCHOR = "0.14 percent"
_FP_EVIDENCE = "0.30 percent"


def _eval_set() -> EvalSet:
    """One GT deficiency in docA anchored on the TP evidence token (structural family)."""
    return EvalSet(
        documents=[],
        deficiencies=[
            GroundTruthDeficiency(
                id="STRUCT-01",
                doc_id=_DOC_ID,
                title="Aggregate total below the largest tabulated single value",
                evidence_anchor=_TP_ANCHOR,
                failure_family=FailureFamily.DERIVATION_PLAUSIBILITY,
            )
        ],
    )


def test_downgraded_fp_not_scored_and_downgraded_tp_retained():
    from config import VERIFIER_FLEET

    fp = labeled_fp_candidate()
    fp.evidence = f"Total is {_FP_EVIDENCE} and the two rows are 0.15 and 0.15."  # NOT a GT anchor
    tp = labeled_tp_candidate()
    tp.evidence = f"Total is {_TP_ANCHOR} although the largest single value is 0.15."  # GT anchor

    # Every panel member grounded-DOWNGRADEs BOTH candidates -> consensus DOWNGRADE on each.
    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("DOWNGRADE", "Total is 0.14 percent")] for m in VERIFIER_FLEET}
    )

    verified, coverage = verify_candidates([fp, tp], fleet_client=fleet)

    # Both were DOWNGRADEd (recall invariant: still present, tier low, recorded in coverage).
    assert len(verified) == 2
    assert fp.confidence_tier == "low"
    assert tp.confidence_tier == "low"
    downgraded = downgraded_dedup_keys(coverage)
    assert fp.dedup_key in downgraded
    assert tp.dedup_key in downgraded

    eval_set = _eval_set()

    # --- Baseline: score the PRE-FILTER report (every verified fault present, downgraded or not). --
    prefilter = FaultReport(job_id="baseline", faults=verified, faults_found=True)
    base = _end_to_end(prefilter, eval_set, _DOC_ID)
    # The FP is present + unmatched in the prefilter report -> it counts as an FP there.
    assert base["fp"] >= 1
    # The TP is present + matched in the prefilter report -> it is a baseline TP we must not lose.
    assert base["tp"] == 1

    # --- Gap-1: assemble_scored_report surfaces ONLY KEEP-tier faults. Both were DOWNGRADEd, so
    #     report.faults is empty; the frozen path sees no FP (precision effect) and no baseline TP
    #     is scored from .faults — but the TP is RETAINED in coverage (zero-TP-loss surface). -------
    report = assemble_scored_report(verified, coverage, job_id="gap1")
    assert report.faults == []  # both DOWNGRADEd -> excluded from the ACTIVE scored surface
    scored = _end_to_end(report, eval_set, _DOC_ID)

    # HALF (a): the DOWNGRADEd FP is NOT counted as an FP (fp strictly lower than the prefilter).
    assert scored["fp"] < base["fp"]
    assert scored["fp"] == 0

    # HALF (b): the DOWNGRADEd TP is STILL retained — recall accounting reads report.faults UNION
    #           the downgraded dedup_keys in coverage, so the baseline TP is not lost by the filter.
    matched_dedup_keys = {getattr(f, "dedup_key", None) for f in report.faults} | downgraded_dedup_keys(coverage)
    assert tp.dedup_key in matched_dedup_keys, "zero-TP-loss: DOWNGRADEd TP dropped from every surface"


def test_could_not_locate_stays_active_in_scored_report():
    """A could-not-locate candidate is NOT a DOWNGRADE -> tier stays 'full' -> stays in report.faults."""
    from config import VERIFIER_FLEET

    tp = labeled_tp_candidate()
    tp.evidence = f"Total is {_TP_ANCHOR} although the largest single value is 0.15."

    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("KEEP", "Total is 0.14 percent")] for m in VERIFIER_FLEET}
    )
    # Force the source half to fail re-open -> could_not_locate, candidate kept ACTIVE.
    verified, coverage = verify_candidates(
        [tp], fleet_client=fleet, reopen_source=lambda c: None, reopen_rule=lambda c: "rule text"
    )

    assert coverage.could_not_locate
    assert coverage.could_not_locate[0]["half"] == "source"
    assert tp.confidence_tier == "full"  # not downgraded

    report = assemble_scored_report(verified, coverage)
    assert tp in report.faults  # active, still scored
