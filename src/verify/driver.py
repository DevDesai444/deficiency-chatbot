# Gap-2 — the single report-assembly seam. Phase-5 candidates + interpretive-tail candidates are
# combined into ONE list and pass the SAME consensus verifier in EXACTLY ONE fan-out, then the
# scored FaultReport (KEEP-tier only) + CoverageReport are assembled. The verify-f1 gate and the
# live checkpoint score THIS driver's assembled output — never a hand-authored report. No new loop,
# no second fan-out. (Referenced in prose below as "the fan-out" so the exactly-one-call-site
# acceptance gate stays honest.)
"""verify.driver — combine Phase-5 + interpretive-tail candidates through one consensus fan-out.

``verify_and_assemble`` is the Gap-2 seam: it takes the Phase-5 deterministic candidate output plus
(optionally) the interpretive-tail candidates, runs BOTH producers through the SINGLE
``verify.orchestrator`` fan-out — the SAME decorrelated consensus verifier every candidate crosses —
and assembles the scored ``FaultReport`` via ``verify.assemble.assemble_scored_report`` (KEEP-tier
only in ``.faults``; DOWNGRADEd faults retained in the ``CoverageReport``). It returns
``(FaultReport, CoverageReport)``.

Two invariants this seam upholds:
  - ONE fan-out for both producers (grep-verifiable single call site) — Phase-5 and tail candidates
    are never verified by two different passes, so a tail candidate can never skip consensus.
  - KEEP-tier-only scored surface — a DOWNGRADEd FP (from either producer) is absent from
    ``report.faults`` (its precision effect is visible to the frozen F1 path) while a DOWNGRADEd TP
    is retained in ``coverage.reviewed_downgrade`` (zero-TP-loss; the β no-drop law).

``enable_tail=False`` is the Gap-4 escape hatch + P3 caution: a run can measure
deterministic-verification-only F1 with the interpretive tail disabled.
"""
from __future__ import annotations

from collections.abc import Callable

from llm.client import chat_completion_tools
from schemas.faults import Fault, FaultReport
from verify.assemble import assemble_scored_report
from verify.coverage import CoverageReport
from verify.orchestrator import verify_candidates
from verify.tail import run_interpretive_tail


def verify_and_assemble(
    phase5_faults: list[Fault],
    corpus=None,
    manifest=None,
    ledger=None,
    *,
    enable_tail: bool = True,
    tail_model: str | None = None,
    completion: Callable = chat_completion_tools,
    tail_complete: Callable = chat_completion_tools,
    reopen_source: Callable | None = None,
    reopen_rule: Callable | None = None,
    reopen_nt: Callable | None = None,
    job_id: str = "",
) -> tuple[FaultReport, CoverageReport]:
    """Combine Phase-5 + interpretive-tail candidates → ONE consensus fan-out → scored report.

    Steps (Gap 2):
      1. candidates = Phase-5 faults.
      2. if ``enable_tail``: append the interpretive-tail candidates (each tagged producer_family
         "qwen" by ``run_interpretive_tail`` — so the decorrelated panel excludes the Qwen family).
      3. run BOTH producers through the SINGLE consensus fan-out (``verify.orchestrator``) — Phase-5
         and tail together, never two passes.
      4. assemble the scored ``FaultReport`` (KEEP-tier only) + return the ``CoverageReport``.

    ``completion`` is the verifier fleet client; ``tail_complete`` is the tail producer's loop
    client (both default to ``chat_completion_tools``; tests inject scripted doubles). The
    ``reopen_*`` callables are the offline re-open injection seams the orchestrator exposes; in
    production the ``corpus``/``manifest``/``ledger`` drive the real FULL re-open of source + rule.
    """
    candidates: list[Fault] = list(phase5_faults)
    if enable_tail:
        candidates += run_interpretive_tail(
            corpus, manifest, ledger, model=tail_model, complete=tail_complete, job_id=job_id
        )

    # THE single fan-out — Phase-5 + tail together through the same decorrelated consensus verifier.
    verified_faults, coverage = verify_candidates(
        candidates,
        completion,
        corpus=corpus,
        manifest=manifest,
        ledger=ledger,
        reopen_source=reopen_source,
        reopen_rule=reopen_rule,
        reopen_nt=reopen_nt,
    )

    # Gap-1 surfacing: KEEP-tier faults only in the scored report; DOWNGRADEd retained in coverage.
    report = assemble_scored_report(verified_faults, coverage, job_id=job_id)
    return report, coverage


__all__ = ["verify_and_assemble"]
