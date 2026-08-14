# Gap-2 — the single report-assembly driver seam.
"""Gap 2 driver test (VERIFY-01/02/03/04, Plan 07-04 Task 2).

``verify_and_assemble`` combines Phase-5 candidates + interpretive-tail candidates into ONE list,
runs BOTH producers through the SINGLE consensus fan-out (``verify_candidates``), and assembles the
scored ``FaultReport`` (KEEP-tier only) + ``CoverageReport``. This test drives it OFFLINE
(``ScriptedFleetClient`` + a scripted ``run_interpretive_tail``) and asserts:

  - returns ``(FaultReport, CoverageReport)``;
  - a labeled FP the panel DOWNGRADEs is ABSENT from ``report.faults`` yet its dedup_key IS in
    ``downgraded_dedup_keys(coverage)`` (FP not scored + retained for audit);
  - a labeled TP the panel DOWNGRADEs is RETAINED (in ``downgraded_dedup_keys``) so the gate's
    zero-TP-loss check can still credit it;
  - ``enable_tail=False`` yields a report with NO qwen-tagged fault; ``enable_tail=True`` includes
    the scripted tail candidate (surviving as KEEP) in ``report.faults``;
  - ``verify_candidates`` is invoked EXACTLY ONCE (single fan-out — Gap 2 seam).
"""
from __future__ import annotations

from unittest.mock import patch

from agents.review.loop import ReviewResult
from schemas.faults import FaultReport
from verify.assemble import downgraded_dedup_keys
from verify.coverage import CoverageReport
from verify.orchestrator import family_of

from tests.verify.conftest import (
    ScriptedFleetClient,
    labeled_fp_candidate,
    labeled_tp_candidate,
    make_normalized_text,
    make_verdict_turn,
    mint_span_over,
)


def _grounded_tail_finding():
    """A grounded tail finding as run_review would return it (pre-retag)."""
    from schemas.faults import Fault

    nt = make_normalized_text("The linearity r-squared of 0.991 is characterized as acceptable.")
    span = mint_span_over(nt, "linearity r-squared of 0.991")
    return Fault(
        title="Linearity acceptance criterion may be interpretive",
        leg_tag=None,
        submission_span_id=span,
        evidence="The linearity r-squared of 0.991 is characterized as acceptable.",
        dedup_key="docA:secTAIL:null",
        confidence=0.35,
        confidence_tier="full",
        source="reviewer:3.2.P.4.3",
    )


def _scripted_run_review(*args, **kwargs):
    """A scripted run_review that never takes a model turn — returns one grounded finding."""
    return ReviewResult(findings=[_grounded_tail_finding()])


def _all_keep_fleet():
    from config import VERIFIER_FLEET

    return ScriptedFleetClient(
        script={m: [make_verdict_turn("KEEP", "any grounding span")] for m in VERIFIER_FLEET}
    )


def test_downgraded_fp_excluded_downgraded_tp_retained_single_fanout():
    """A DOWNGRADEd FP leaves report.faults; a DOWNGRADEd TP is retained; ONE fan-out."""
    from config import VERIFIER_FLEET

    fp = labeled_fp_candidate()
    fp.evidence = "Total is 0.30 percent and the two rows are 0.15 and 0.15."  # NOT a GT anchor
    tp = labeled_tp_candidate()
    tp.evidence = "Total is 0.14 percent although the largest single value is 0.15."

    # Every panel member grounded-DOWNGRADEs -> consensus DOWNGRADE on each Phase-5 candidate.
    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("DOWNGRADE", "Total is 0.14 percent")] for m in VERIFIER_FLEET}
    )

    from verify import driver as driver_mod

    with patch.object(driver_mod, "verify_candidates", wraps=driver_mod.verify_candidates) as spy:
        report, coverage = driver_mod.verify_and_assemble(
            [fp, tp],
            enable_tail=False,  # deterministic-verification-only for this assertion
            completion=fleet,
            reopen_source=lambda c: c.evidence,
            reopen_rule=lambda c: "cited rule text",
        )
        # Gap 2: exactly ONE consensus fan-out for the combined candidate list.
        assert spy.call_count == 1

    assert isinstance(report, FaultReport)
    assert isinstance(coverage, CoverageReport)

    downgraded = downgraded_dedup_keys(coverage)
    # FP: DOWNGRADEd -> excluded from the scored surface, retained in coverage (audit).
    assert fp.dedup_key in downgraded
    assert fp not in report.faults
    # TP: DOWNGRADEd -> excluded from .faults but retained (zero-TP-loss surface).
    assert tp.dedup_key in downgraded
    retained = {getattr(f, "dedup_key", None) for f in report.faults} | downgraded
    assert tp.dedup_key in retained


def test_enable_tail_toggle_controls_qwen_candidate():
    """enable_tail=False -> no qwen fault; enable_tail=True -> the KEEP tail candidate is scored."""
    from verify import driver as driver_mod

    # --- tail disabled: no qwen-tagged fault in the assembled report ---
    report_off, _ = driver_mod.verify_and_assemble(
        [],
        enable_tail=False,
        completion=_all_keep_fleet(),
        reopen_source=lambda c: getattr(c, "evidence", "") or "src",
        reopen_rule=lambda c: "rule",
    )
    assert all(family_of(f) != "qwen" for f in report_off.faults)

    # --- tail enabled: the scripted tail candidate survives KEEP and appears (tagged qwen) ---
    with patch.object(driver_mod, "run_interpretive_tail") as tail_stub:
        from verify.tail import _tag_producer_family  # retag exactly as production does

        tail_stub.return_value = [_tag_producer_family(_grounded_tail_finding(), "qwen")]
        report_on, _ = driver_mod.verify_and_assemble(
            [],
            enable_tail=True,
            completion=_all_keep_fleet(),
            reopen_source=lambda c: getattr(c, "evidence", "") or "src",
            reopen_rule=lambda c: "rule",
        )

    qwen_faults = [f for f in report_on.faults if family_of(f) == "qwen"]
    assert len(qwen_faults) == 1, "the KEEP-tier tail candidate must be scored, tagged qwen"
