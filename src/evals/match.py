"""Deterministic (no-LLM) matcher: detector `Fault` <-> ground-truth `GroundTruthDeficiency`.

Mirrors `agents.detection.verify`'s `_anchored` substring-anchoring discipline (a numeric/
identifier token must appear verbatim, after normalization, in the target text) so that scoring
is code-grounded: a paraphrased finding cannot be credited as a hit just because it is *about*
the same table or topic. This module never imports `agents.*` -- it works purely off `dict`
faults (bridge with `fault.model_dump()` at the call site) so the scorer has zero coupling to the
detection pipeline's internals.

Pure data + string module: no import of `agents.*`, no network access, no LLM calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from evals.schema import GroundTruthDeficiency

# Numeric/identifier runs (e.g. "11477", "0.15", "05/10/2016") -- min length 3 by construction
# (1 leading digit + >=2 more from the class). Word regex requires >=6 letters (e.g.
# "degradants") so short common words ("data", "table") never masquerade as a distinctive anchor.
_TOKEN_RE = re.compile(r"[0-9][0-9.\/]{2,}")
_WORD_RE = re.compile(r"[a-z]{6,}")


def _norm(s: str) -> str:
    """Lowercase, strip whitespace and `%` signs, so '0.15 %' and '0.15%' normalize identically."""
    return re.sub(r"\s+", "", (s or "").lower()).replace("%", "")


def _anchor_tokens(anchor: str) -> list[str]:
    """Split a GT `evidence_anchor` into its distinctive, matchable tokens.

    Only lowercases the anchor first -- deliberately does NOT run it through `_norm` as a whole,
    because `_norm` strips whitespace, which would merge a space-separated multi-number anchor
    (e.g. "11477 12601") into one unsplittable digit run. Lowercasing alone never merges tokens,
    so it is safe to apply to the full string before the regexes split it.
    """
    lowered = (anchor or "").lower()
    found = _TOKEN_RE.findall(lowered) + _WORD_RE.findall(lowered)

    seen: set[str] = set()
    tokens: list[str] = []
    for tok in found:
        if tok not in seen:
            seen.add(tok)
            tokens.append(tok)
    return tokens


def finding_text(fault: dict) -> str:
    """Normalized concatenation of the fields a finding could carry its anchor in."""
    return _norm(" ".join([fault.get("evidence", ""), fault.get("title", ""), fault.get("detail", "")]))


def matches(fault: dict, gt: GroundTruthDeficiency) -> bool:
    """True iff every distinctive anchor token of `gt` appears verbatim in `fault`'s text.

    Requires >=1 token (an anchor with none is never deterministically matchable -- it will
    always count as FN, which is correct: the matcher only credits what it can prove). When the
    anchor yields 2+ tokens, ALL must appear -- this is what stops a single common number (e.g.
    "0.6") from matching every deficiency that happens to share it.

    Does not check `gt.doc_id` -- that scoping happens in `score()`, which knows the run's
    `doc_id`; a bare `Fault` dict has no doc_id field of its own to compare against.
    """
    tokens = _anchor_tokens(gt.evidence_anchor)
    if not tokens:
        return False
    text = finding_text(fault)
    return all(tok in text for tok in tokens)


@dataclass
class MatchResult:
    """Deterministic match outcome for one detector run scored against one document's GT set."""

    matched_gt_ids: set[str] = field(default_factory=set)
    tp_findings: list[int] = field(default_factory=list)
    fp_findings: list[int] = field(default_factory=list)
    fn_gt_ids: set[str] = field(default_factory=set)


def score(faults: list[dict], gts: list[GroundTruthDeficiency], doc_id: str) -> MatchResult:
    """Score a run's findings against one document's ground truth, doc-scoped.

    Many-to-one collapse: N findings hitting the same GT id count as ONE true positive for
    recall (`matched_gt_ids` is a set, deduped by construction) -- this prevents a single real
    deficiency that the detector restates six different ways (a documented failure mode, see
    docs/eval/MEASUREMENT.md) from inflating recall. FP counting still sees every unmatched
    finding individually (`fp_findings` is per-finding-index), so noise is not hidden by the
    same dedup that protects recall.
    """
    doc_gts = [gt for gt in gts if gt.doc_id == doc_id]

    matched_gt_ids: set[str] = set()
    tp_findings: list[int] = []
    fp_findings: list[int] = []

    for idx, fault in enumerate(faults):
        hit = False
        for gt in doc_gts:
            if matches(fault, gt):
                matched_gt_ids.add(gt.id)
                hit = True
        if hit:
            tp_findings.append(idx)
        else:
            fp_findings.append(idx)

    fn_gt_ids = {gt.id for gt in doc_gts} - matched_gt_ids

    return MatchResult(
        matched_gt_ids=matched_gt_ids,
        tp_findings=tp_findings,
        fp_findings=fp_findings,
        fn_gt_ids=fn_gt_ids,
    )
