"""Zero-true-positives-lost CI gate (EVAL-03).

A filter (a concession gate, a stricter tier threshold, a prompt change) can only ever REMOVE
findings from a run. The one invariant that must never silently regress is: a real deficiency
the detector already finds today must still be found tomorrow. This module is the code-enforced
version of that invariant -- not a prompt, not a convention (PITFALLS.md #4) -- so a regression
fails the build loudly and names exactly which deficiency disappeared.

Built entirely on `evals.match.score` (deterministic, no-LLM anchor matching); this module adds
no new matching logic of its own, only the baseline-vs-new-run subset comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from evals.match import score
from evals.schema import EvalSet
from schemas.faults import FaultReport


def baseline_found_ids(eval_set: EvalSet, extra: set[str] | None = None) -> set[str]:
    """The protected found-set the gate must never lose.

    Always includes every `tp_required` deficiency's id (the anchors the detector already
    finds today -- C-01, C-02 for `mvr1381`) unioned with `extra`: any further ids a committed
    baseline file has recorded as found (e.g. `src/evals/baseline/recall_by_family.json`'s
    `found_set`). A later phase's baseline can grow this set as recall improves; it can never
    shrink it without the gate catching the loss.
    """
    protected = {gt.id for gt in eval_set.tp_required()}
    if extra:
        protected |= set(extra)
    return protected


@dataclass
class GateResult:
    """Outcome of one gate check.

    `ok` is the single pass/fail signal (`ok == (lost == set())`, always -- there is no other
    way for the gate to fail). `lost` names exactly which protected ids disappeared, so a CI
    failure message is actionable, not just "gate failed". `matched` is the full matched-id set
    for this run (a superset of the baseline is fine -- finding MORE never fails the gate).
    """

    ok: bool
    lost: set[str] = field(default_factory=set)
    matched: set[str] = field(default_factory=set)


def check_gate(report: FaultReport, eval_set: EvalSet, doc_id: str, baseline_ids: set[str]) -> GateResult:
    """Score `report` against `doc_id`'s ground truth and compare the matched set to `baseline_ids`.

    Every baseline id still matched -> pass. Any baseline id NOT matched in this run -> fail,
    with `lost` naming exactly which one(s). A run that ALSO finds ids beyond the baseline
    passes -- only LOSING a previously-found true positive is a gate failure.
    """
    faults = [fault.model_dump() for fault in report.faults]
    doc_gts = [gt for gt in eval_set.deficiencies if gt.doc_id == doc_id]
    result = score(faults, doc_gts, doc_id)

    matched = result.matched_gt_ids
    lost = set(baseline_ids) - matched
    return GateResult(ok=not lost, lost=lost, matched=matched)


def true_positives_lost(report: FaultReport, eval_set: EvalSet, doc_id: str, baseline_ids: set[str]) -> set[str]:
    """Thin, named alias for the lost-id set -- the grep-able concept the gate protects.

    Equivalent to `check_gate(...).lost`; exists so callers/CI output can refer to "true
    positives lost" as a first-class, searchable concept rather than a dataclass field access.
    """
    return check_gate(report, eval_set, doc_id, baseline_ids).lost
