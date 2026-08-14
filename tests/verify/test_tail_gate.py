# VERIFY-04 — the interpretive tail is grounded (emit_finding), tagged qwen, and its decorrelated
# panel excludes the producer family. The tail PRODUCES tagged grounded candidates; the driver
# (Task 2) owns the single consensus fan-out — so this gate asserts the producer-family tag + the
# decorrelation panel, not a fan-out. The DOWNGRADE-not-drop path is asserted through the driver.
"""VERIFY-04 tail gate (Wave 3).

``run_interpretive_tail`` reuses the EXISTING Phase-3 ``run_review`` loop on a Qwen producer (no new
loop) and returns grounded candidates already emitted through ``emit_finding``. This test drives it
OFFLINE — ``run_review`` is replaced with a scripted double returning one grounded finding — and
asserts:
  (a) each tail candidate is tagged producer_family "qwen" (``family_of`` returns "qwen");
  (b) ``panel_for(family_of(candidate))`` contains NO qwen-lineage member (decorrelation — a
      correlated Qwen error cannot rubber-stamp a Qwen-produced candidate).
No live endpoint, no live fleet: the scripted ``run_review`` never takes a model turn.
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import make_normalized_text, mint_span_over


def _make_grounded_finding(source: str):
    """A grounded finding as ``run_review`` would return it (emit_finding already byte-exact ran).

    ``source`` is whatever the loop recorded; ``run_interpretive_tail`` retags it to the qwen family.
    Built with a real minted SpanID so it is structurally a genuine grounded Fault.
    """
    from schemas.faults import Fault

    nt = make_normalized_text("The linearity r-squared of 0.991 is characterized as acceptable.")
    span = mint_span_over(nt, "linearity r-squared of 0.991")
    return Fault(
        title="Linearity acceptance criterion may be interpretive",
        leg_tag=None,
        submission_span_id=span,
        dedup_key="docA:sec3:null",
        confidence=0.35,
        confidence_tier="full",
        source=source,
    )


def test_tail_candidate_tagged_qwen_and_panel_excludes_qwen(monkeypatch):
    tail = pytest.importorskip(
        "verify.tail",
        reason="src/verify/tail.py lands in Wave 3; tail-gate test flips on then.",
    )
    from config import MODEL_LINEAGE
    from verify.orchestrator import family_of
    from verify.panel import panel_for
    from agents.review.loop import ReviewResult

    # A scripted run_review: it returns a grounded finding WITHOUT the qwen tag, so we prove
    # run_interpretive_tail is what stamps the producer family. It never takes a model turn.
    def _scripted_run_review(corpus, manifest, ledger, budget, telemetry, complete, registry, job_id=""):
        return ReviewResult(findings=[_make_grounded_finding(source="reviewer:3.2.P.4.3")])

    monkeypatch.setattr("verify.tail.run_review", _scripted_run_review)

    # corpus/manifest/ledger are opaque to the scripted loop; a sentinel object is sufficient.
    class _Sentinel:
        pass

    candidates = tail.run_interpretive_tail(_Sentinel(), _Sentinel(), _Sentinel())

    assert len(candidates) == 1
    candidate = candidates[0]

    # (a) tagged producer_family "qwen": family_of reads the marker in Fault.source.
    assert family_of(candidate) == "qwen"

    # (b) the decorrelated panel excludes every qwen-lineage member.
    panel = panel_for(family_of(candidate))
    assert panel, "panel must never be empty"
    qwen_members = [m for m in panel if MODEL_LINEAGE.get(m) == "qwen"]
    assert qwen_members == [], f"tail panel must exclude the qwen producer family, saw {qwen_members}"
