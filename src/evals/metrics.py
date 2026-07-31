"""Per-stage + by-family metrics computed from a scored detector run (EVAL-02).

Five per-stage metrics -- `retrieval_recall_at_k`, `parse_fidelity`, `anchor_rate`, `verifier`,
`end_to_end` -- plus end-to-end precision/recall broken down by all four failure families,
computed deterministically from `evals.match.score`. No LLM anywhere in this module; the only
non-`evals.*` import is the typed `FaultReport`/`Tier` shape from `schemas.faults`.

Checker note W1: `anchor_rate` must be a REAL computed number whenever `source_text` is supplied
(never a permanent sentinel) -- see `_anchor_rate` below. Checker note W3: all five per-stage
metrics must be surfaced SEPARATELY in CLI output, not folded only into the by-family table --
see `format_table` below.
"""
from __future__ import annotations

import re

from evals.match import score
from evals.schema import EvalSet, FailureFamily
from schemas.faults import FaultReport, Tier

# Numeric/identifier token >=4 chars total, mirroring `agents.detection.verify._anchored`'s own
# `len(n) >= 4` verbatim-anchoring floor -- applied PER-TOKEN (not to the whole evidence string)
# so a composite, multi-citation Fault.evidence field can still be credited if ANY ONE of its
# cited numbers/identifiers verbatim-resolves in the real source document.
_EVIDENCE_TOKEN_RE = re.compile(r"[0-9][0-9./]{3,}")

# Section/table numbers for the retrieval-coverage proxy (e.g. "20" from "Table 20", "1.4.9" from
# a dotted subsection hint). Deliberately permissive (no minimum length) -- this is a Phase-0
# coverage proxy, not the anchor-token matcher's strict distinctiveness filter.
_SECTION_TOKEN_RE = re.compile(r"\d+(?:\.\d+)*")


def _evidence_tokens(evidence: str) -> list[str]:
    return _EVIDENCE_TOKEN_RE.findall((evidence or "").lower())


def _section_tokens(text: str) -> set[str]:
    return set(_SECTION_TOKEN_RE.findall(text or ""))


def _normalize_source(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def _precision_recall(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn}


def _end_to_end(report: FaultReport, eval_set: EvalSet, doc_id: str) -> dict:
    faults = [f.model_dump() for f in report.faults]
    result = score(faults, eval_set.deficiencies, doc_id)
    return _precision_recall(len(result.matched_gt_ids), len(result.fp_findings), len(result.fn_gt_ids))


def _end_to_end_by_family(report: FaultReport, eval_set: EvalSet, doc_id: str) -> dict:
    """Per-family precision/recall/tp/fp/fn -- the same finding list scored against each
    family's GT subset in turn, per family. All four family keys are always present (even a
    family with zero GT items in this doc would report precision=recall=0.0 via the
    `_precision_recall` zero-guard, never a KeyError)."""
    faults = [f.model_dump() for f in report.faults]
    by_family: dict[str, dict] = {}
    for family in FailureFamily:
        family_gts = [
            gt for gt in eval_set.deficiencies if gt.doc_id == doc_id and gt.failure_family == family
        ]
        result = score(faults, family_gts, doc_id)
        by_family[family.value] = _precision_recall(
            len(result.matched_gt_ids), len(result.fp_findings), len(result.fn_gt_ids)
        )
    return by_family


def _retrieval_recall_at_k(report: FaultReport, eval_set: EvalSet, doc_id: str):
    """Phase-0 proxy for retrieval-stage coverage.

    The current detector sees the whole document in one shot -- there is no explicit top-k
    retrieval stage to measure yet, so this reports section/table-number OVERLAP between each
    GT deficiency's `section_hint` and everything the run cited (`table_ref`, `cited_section_
    indices`, `domains_checked`) as a coarse "was this part of the document surfaced at all"
    signal, independent of whether the exact finding was made. Upgrades to true corpus recall@k
    once an explicit retrieval/navigation stage exists (Phase 2).
    """
    doc_gts = [gt for gt in eval_set.deficiencies if gt.doc_id == doc_id and gt.section_hint.strip()]
    if not doc_gts:
        return "n/a_phase0"

    surfaced: set[str] = set()
    for fault in report.faults:
        surfaced |= _section_tokens(fault.section) | _section_tokens(fault.table_ref)
        surfaced |= {str(i) for i in fault.cited_section_indices}
    for domain in report.domains_checked:
        surfaced |= _section_tokens(domain)

    covered = sum(1 for gt in doc_gts if _section_tokens(gt.section_hint) & surfaced)
    return covered / len(doc_gts)


def _search_corpus_recall_at_k(eval_set: EvalSet, doc_id: str, corpus, top_k: int = 10) -> dict | str:
    """Real corpus-recall@k (Phase 2 upgrade of the Phase-0 proxy, per _retrieval_recall_at_k's
    own docstring). Runs search_corpus once per non-held-out GT item for `doc_id`, checks
    whether a top-k result's span overlaps evidence_anchor in the correct doc_id. Reports the
    overall fraction AND the exact-identifier hard subset separately (D-SC4)."""
    from evals.match import _TOKEN_RE
    from tools.ledger import RetrievalLedger
    from tools.search_corpus import search_corpus

    doc_gts = [gt for gt in eval_set.deficiencies if gt.doc_id == doc_id]
    if not doc_gts:
        return "n/a_no_gt"

    def _covered(gt) -> bool:
        ledger = RetrievalLedger()
        results = search_corpus(corpus, gt.title, ledger, top_k=top_k)
        anchor_norm = re.sub(r"\s+", "", gt.evidence_anchor.lower())
        for r in results:
            if r["doc_id"] != doc_id:
                continue
            snippet_norm = re.sub(r"\s+", "", r["snippet"].lower())
            if anchor_norm in snippet_norm:
                return True
        return False

    hits = [(gt, _covered(gt)) for gt in doc_gts]
    overall = sum(1 for _gt, ok in hits if ok) / len(hits)

    hard = [(gt, ok) for gt, ok in hits if _TOKEN_RE.search(gt.evidence_anchor)]
    hard_recall = (sum(1 for _gt, ok in hard if ok) / len(hard)) if hard else "n/a_no_hard_subset"

    return {"overall": overall, "exact_identifier_subset": hard_recall, "n": len(hits), "n_hard": len(hard)}


def _parse_fidelity(report: FaultReport) -> dict:
    return {"parsed_ok": len(report.parse_failures) == 0, "parse_failures": len(report.parse_failures)}


def _anchor_rate(report: FaultReport, source_text: str):
    """Fraction of emitted findings whose evidence verbatim-resolves in the source document.

    W1 (checker note): this MUST be a real computed number whenever `source_text` is non-empty
    -- never a permanent sentinel. `source_text` is the caller's responsibility to provide (Plan
    00-04's `score`/baseline generation parses the non-held-out PDF once via `extract_pdf`,
    joining block text + table-cell text, and passes the join here). Only falls back to the
    `"n/a_no_source"` sentinel when the caller genuinely has nothing to check against.
    """
    if not source_text.strip():
        return "n/a_no_source"
    if not report.faults:
        return 0.0

    source_norm = _normalize_source(source_text)
    anchored = sum(
        1 for fault in report.faults if any(tok in source_norm for tok in _evidence_tokens(fault.evidence))
    )
    return anchored / len(report.faults)


def _verifier_metrics(report: FaultReport, eval_set: EvalSet, doc_id: str):
    """Challenge-stage precision/recall on the labeled run, using `tier` as the keep signal.

    A finding is "kept" when its tier cleared ADVISORY (i.e. corroborated by precedent or
    oracle-verified) -- CORROBORATED/VERIFIED. This is computed entirely from the single
    captured `FaultReport`; there is no separate pre-challenge snapshot in this fixture (verify.py
    drops findings before they ever reach the report), so this measures "would a stricter
    kept-tier threshold have preserved the true positives", not a literal before/after diff of
    the challenge pass. Falls back to `"n/a_phase0"` when the run has no GT to score against, no
    findings at all, nothing survives the tier filter, or nothing was ever a true positive to
    begin with -- i.e. whenever the precision/recall computation is not actually separable from
    this single snapshot.
    """
    faults = [f.model_dump() for f in report.faults]
    doc_gts = [gt for gt in eval_set.deficiencies if gt.doc_id == doc_id]
    if not doc_gts or not faults:
        return "n/a_phase0"

    kept_idx = [i for i, f in enumerate(report.faults) if f.tier != Tier.ADVISORY]
    if not kept_idx:
        return "n/a_phase0"

    all_result = score(faults, doc_gts, doc_id)
    tp_total = len(all_result.matched_gt_ids)
    if tp_total == 0:
        return "n/a_phase0"

    kept_faults = [faults[i] for i in kept_idx]
    kept_result = score(kept_faults, doc_gts, doc_id)
    tp_kept = len(kept_result.matched_gt_ids)
    fp_kept = len(kept_result.fp_findings)

    precision = tp_kept / (tp_kept + fp_kept) if (tp_kept + fp_kept) else 0.0
    recall = tp_kept / tp_total
    return {"precision": precision, "recall": recall}


def compute_metrics(
    report: FaultReport, eval_set: EvalSet, doc_id: str, source_text: str = "", corpus=None
) -> dict:
    """The full per-stage + by-family metrics dict for one scored detector run.

    `source_text` is the joined plain text of the (non-held-out) source document. Callers
    (Plan 00-04's `score`/baseline generation) parse it once via `extract_pdf` and join block +
    table-cell text (checker note W1). Without it, `anchor_rate` reports the `"n/a_no_source"`
    sentinel since there is nothing to verbatim-check finding evidence against; WITH it,
    `anchor_rate` is a real, code-computed number.

    `corpus` (optional, Phase 2/SC4) is an ingested `ingest.corpus.CorpusIndex` for `doc_id`. When
    supplied, an ADDITIONAL `"search_corpus_recall_at_k"` key is computed via
    `_search_corpus_recall_at_k` -- a real `search_corpus`-driven measurement -- alongside (never
    replacing) the existing `retrieval_recall_at_k` Phase-0 proxy key. `corpus=None` (the default)
    keeps every existing caller's signature/behavior byte-for-byte unchanged.
    """
    end_to_end = _end_to_end(report, eval_set, doc_id)
    end_to_end_by_family = _end_to_end_by_family(report, eval_set, doc_id)

    metrics = {
        "end_to_end": end_to_end,
        "end_to_end_by_family": end_to_end_by_family,
        "recall_by_family": {family: values["recall"] for family, values in end_to_end_by_family.items()},
        "retrieval_recall_at_k": _retrieval_recall_at_k(report, eval_set, doc_id),
        "parse_fidelity": _parse_fidelity(report),
        "anchor_rate": _anchor_rate(report, source_text),
        "verifier": _verifier_metrics(report, eval_set, doc_id),
    }
    if corpus is not None:
        metrics["search_corpus_recall_at_k"] = _search_corpus_recall_at_k(eval_set, doc_id, corpus)
    return metrics


def recall_by_family(report: FaultReport, eval_set: EvalSet, doc_id: str) -> dict:
    """Top-level accessor for the headline SC2 metric (also embedded in `compute_metrics()`)."""
    by_family = _end_to_end_by_family(report, eval_set, doc_id)
    return {family: values["recall"] for family, values in by_family.items()}


def format_table(metrics: dict) -> str:
    """Plain-text report for CLI output (`python -m evals.run score`, Plan 00-04).

    W3 (checker note): renders the by-family table AND all five per-stage metrics as their own,
    separately-labeled lines -- a human running `score` must be able to see parse_fidelity /
    anchor_rate / retrieval_recall_at_k / verifier / end_to_end individually, not only folded
    into the by-family table.
    """

    def _fmt(value) -> str:
        if isinstance(value, dict):
            return ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}" for k, v in value.items())
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    lines: list[str] = []

    lines.append("=== End-to-end by failure family ===")
    lines.append(f"{'family':<28}{'precision':>10}{'recall':>10}{'tp':>6}{'fp':>6}{'fn':>6}")
    for family, values in metrics["end_to_end_by_family"].items():
        lines.append(
            f"{family:<28}{values['precision']:>10.3f}{values['recall']:>10.3f}"
            f"{values['tp']:>6}{values['fp']:>6}{values['fn']:>6}"
        )

    lines.append("")
    lines.append("=== Per-stage metrics (SC2 -- all five reported separately) ===")
    lines.append(f"retrieval_recall_at_k : {_fmt(metrics['retrieval_recall_at_k'])}")
    if "search_corpus_recall_at_k" in metrics:
        lines.append(f"search_corpus_recall_at_k : {_fmt(metrics['search_corpus_recall_at_k'])}")
    lines.append(f"parse_fidelity        : {_fmt(metrics['parse_fidelity'])}")
    lines.append(f"anchor_rate           : {_fmt(metrics['anchor_rate'])}")
    lines.append(f"verifier              : {_fmt(metrics['verifier'])}")
    lines.append(f"end_to_end            : {_fmt(metrics['end_to_end'])}")

    lines.append("")
    lines.append("=== Recall by family (headline milestone metric) ===")
    for fam, recall in metrics["recall_by_family"].items():
        lines.append(f"{fam:<28}{recall:>10.3f}")

    return "\n".join(lines)
