# Gap-1/Gap-2/Gap-3 — the verify-f1 phase gate, offline in all four ways.
"""verify-f1 gate offline test (VERIFY-01..04, Plan 07-04 Task 3).

The gate DRIVES ``verify.driver.verify_and_assemble`` (Gap 2) and grades end-to-end F1 vs the frozen
Phase-5 baseline + zero-TP-loss, HARD-FAILING an ``authored-*`` baseline on a real corpus run
(Gap 3). This test exercises the grading logic OFFLINE — no live endpoint, no live corpus:

  (1) a report that retains all baseline TPs with F1 >= baseline -> exit 0;
  (2) a report missing a baseline TP id (key absent from the downgraded union) -> nonzero + the
      lost id in the message;
  (3) a DOWNGRADEd-but-present TP (supplied via --downgraded) is counted as RETAINED -> exit 0
      (the zero-TP-loss union: a downgrade never reads as a lost TP);
  (4) Gap-3: an "authored-from-phase5-close-numbers" baseline + a simulated real-corpus run returns
      nonzero with the re-capture directive.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.run import cmd_verify_f1_gate
from evals.schema import EvalSet, FailureFamily, GroundTruthDeficiency
from schemas.faults import Fault, FaultReport

_DOC_ID = "docGATE"
_TP_ANCHOR = "0.14 percent"


def _eval_set(doc_paths=None) -> EvalSet:
    """One GT deficiency in docGATE anchored on the TP token; optional real doc rows for Gap-3."""
    docs = doc_paths or []
    return EvalSet(
        documents=docs,
        deficiencies=[
            GroundTruthDeficiency(
                id="TP-01",
                doc_id=_DOC_ID,
                title="Aggregate total below the largest tabulated single value",
                evidence_anchor=_TP_ANCHOR,
                failure_family=FailureFamily.DERIVATION_PLAUSIBILITY,
            )
        ],
    )


def _tp_fault() -> Fault:
    return Fault(
        title="Aggregate total below the largest single value",
        leg_tag="STRUCTURAL",
        evidence=f"Total is {_TP_ANCHOR} although the largest single value is 0.15.",
        dedup_key="docGATE:tp:null",
        confidence=0.6,
        confidence_tier="full",
        source="oracle:aggregate_recompute",
    )


def _write_report(tmp: Path, faults, name="report.json") -> str:
    report = FaultReport(job_id="drv", faults=list(faults), faults_found=bool(faults))
    p = tmp / name
    p.write_text(report.model_dump_json())
    return str(p)


def _baseline(tmp: Path, *, provenance: str, f1: float, matched=("TP-01",)) -> str:
    data = {
        "source": "phase5-frozen",
        "provenance": provenance,
        "end_to_end": {"precision": 0.5, "recall": 0.5, "f1": f1, "tp": 1, "fp": 1, "fn": 0},
        "matched_set": list(matched),
    }
    p = tmp / "baseline.json"
    p.write_text(json.dumps(data))
    return str(p)


def _args(**kw) -> argparse.Namespace:
    base = dict(
        baseline=None, doc_id=_DOC_ID, report=None, downgraded=None,
        no_tail=False, tail_model=None,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _patch_eval_set(monkeypatch, eval_set):
    # The gate imports load_eval_set from evals.schema inside the function body.
    monkeypatch.setattr("evals.schema.load_eval_set", lambda *a, **k: eval_set)


def test_pass_when_all_tps_retained_and_f1_meets_floor(tmp_path, monkeypatch, capsys):
    _patch_eval_set(monkeypatch, _eval_set())
    report = _write_report(tmp_path, [_tp_fault()])
    baseline = _baseline(tmp_path, provenance="test-synthetic", f1=0.0)
    rc = cmd_verify_f1_gate(_args(baseline=baseline, report=report))
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "PASS: verify-f1" in out


def test_fail_when_baseline_tp_lost(tmp_path, monkeypatch, capsys):
    _patch_eval_set(monkeypatch, _eval_set())
    # An EMPTY report loses TP-01 (and no downgraded surface carries it).
    report = _write_report(tmp_path, [])
    baseline = _baseline(tmp_path, provenance="test-synthetic", f1=0.0)
    rc = cmd_verify_f1_gate(_args(baseline=baseline, report=report))
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "lost baseline matched TP ids" in out
    assert "TP-01" in out


def test_downgraded_but_present_tp_counts_as_retained(tmp_path, monkeypatch, capsys):
    _patch_eval_set(monkeypatch, _eval_set())
    # The active report is EMPTY (the TP was DOWNGRADEd -> excluded from .faults), but the TP fault
    # is supplied on the retained-for-recall downgraded surface -> zero-TP-loss union credits it.
    report = _write_report(tmp_path, [])
    downgraded = tmp_path / "downgraded.json"
    downgraded.write_text(json.dumps([json.loads(_tp_fault().model_dump_json())]))
    baseline = _baseline(tmp_path, provenance="test-synthetic", f1=0.0)
    rc = cmd_verify_f1_gate(_args(baseline=baseline, report=report, downgraded=str(downgraded)))
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "PASS: verify-f1" in out


def test_gap3_authored_baseline_on_real_run_hard_fails(tmp_path, monkeypatch, capsys):
    # A real corpus run (no --report) with a doc whose path EXISTS on disk + an authored-* baseline.
    real_doc_path = tmp_path / "submission.pdf"
    real_doc_path.write_text("stub bytes")  # merely needs to EXIST for the corpus-present check
    from evals.schema import EvalDocument

    doc = EvalDocument(doc_id=_DOC_ID, path=str(real_doc_path), format="pdf", held_out=False)
    _patch_eval_set(monkeypatch, _eval_set(doc_paths=[doc]))

    baseline = _baseline(tmp_path, provenance="authored-from-phase5-close-numbers", f1=0.085714)
    rc = cmd_verify_f1_gate(_args(baseline=baseline))  # real run: no --report
    out = capsys.readouterr().out
    assert rc == 1, out
    assert "authored" in out
    assert "re-capture" in out
