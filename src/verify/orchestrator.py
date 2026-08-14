"""Verifier fan-out orchestrator (VERIFY-01 / VERIFY-02 / VERIFY-03).

Per candidate this module: consolidates Phase-5 Faults by ``Fault.dedup_key`` (merge, never drop),
derives the producer family, re-opens the FULL source (``tools.get_section``) and FULL rule
(``tools.read_guideline``) — never a truncated ≤500-char excerpt — selects a DECORRELATED panel
(``panel.panel_for``), issues one isolated ``verifier.verify_once`` call per panel member (each
verifier sees ONLY claim + re-opened source + rule, never the producer's chain-of-thought, and is
offered only read-only tools — both enforced inside ``verifier.verify_once``), applies the
code-gated ``consensus`` invariant and, on DOWNGRADE, LOWERS the candidate's confidence IN PLACE —
never removing it. It emits an honest ``CoverageReport`` (reviewed_keep / reviewed_downgrade /
could_not_locate — NO positive-pass field).

RECALL INVARIANT (β law, VERIFY-01): no path here deletes/pops/removes a candidate. A DOWNGRADE
only mutates ``confidence``/``confidence_tier``; the output list length always equals the number of
unique dedup_key groups (>= number of true candidates). ``test_invariant_no_drop`` asserts this in
code, and a static guard asserts no list-removal verb appears anywhere in ``src/verify/``.

RE-OPEN (VERIFY-02): when a live ``corpus``/``manifest``/``ledger`` are supplied, source+rule are
re-opened in FULL via ``get_section``/``read_guideline``; a ``ToolRejected``/``None`` on EITHER half
lands the candidate in ``coverage.could_not_locate`` — reviewed-but-not-gradeable: confidence NOT
raised, candidate NOT dropped, ``confidence_tier`` left ``"full"`` (a could-not-locate is NOT a
DOWNGRADE, so it stays ACTIVE in the scored report). Tests inject ``reopen_source``/``reopen_rule``/
``reopen_nt`` callables directly instead of a corpus, exercising the same seam offline.
"""
from __future__ import annotations

from typing import Callable

import structlog

from config import MODEL_LINEAGE
from schemas.llm import VERDICT
from tools.errors import ToolRejected
from verify.consensus import consensus
from verify.coverage import CoverageReport, consolidate
from verify.grounding import is_grounded
from verify.panel import panel_for
from verify.verifier import verify_once

log = structlog.get_logger()

# Re-export the single source of truth for consolidation (verify.coverage) so callers/tests that
# reach for ``orchestrator.consolidate`` and ``coverage.consolidate`` get the SAME merge-never-drop
# grouping — there is exactly one consolidation implementation.
__all__ = ["family_of", "producer_family_of", "consolidate", "verify_candidates", "CoverageReport"]

# The set of known lineage families (values of MODEL_LINEAGE) a producer tag may name.
_KNOWN_FAMILIES = frozenset(MODEL_LINEAGE.values())

# The general confidence-lowering factor applied on a consensus DOWNGRADE. This is a GENERAL,
# documented constant (a monotone confidence discount) — NOT a corpus/submission-specific token.
# It never zeroes or drops the candidate; it only lowers confidence and flags the tier "low".
_DOWNGRADE_CONFIDENCE_FACTOR = 0.5


def family_of(candidate) -> str | None:
    """Derive the producer's model family from the candidate, or None for a deterministic leg.

    Deterministic recall legs (oracle/checklist/structural/reference/precedent) have no model
    producer -> None -> any cross-family fleet mix is valid. The interpretive tail (Plan 04)
    records its producer in ``Fault.source`` as ``"reviewer:{family}:..."``; we read the family
    token against ``config.MODEL_LINEAGE`` values — no hardcoded family literal. ``family_of`` is
    the accessor Plan 04 tags a tail candidate for so ``panel_for`` excludes its own family.
    """
    source = getattr(candidate, "source", "") or ""
    for token in source.split(":"):
        if token in _KNOWN_FAMILIES:
            return token
    return None


# Backwards-compatible alias (the Wave-1 name); ``family_of`` is the accessor Plan 04 reads.
producer_family_of = family_of


def _grounded_of(verdict, candidate, nt) -> bool:
    """Whether a verdict counts as grounded. Byte-exact via is_grounded when nt is available,
    else falls back to a non-empty grounding_span (the VERDICT schema enforces a non-blank span)."""
    if not isinstance(verdict, VERDICT):
        return False
    if verdict.verdict.value != "DOWNGRADE":
        return False
    if nt is not None:
        return is_grounded(candidate, nt, verdict.grounding_span)
    return bool(verdict.grounding_span and verdict.grounding_span.strip())


def _apply_downgrade(candidate) -> None:
    """Lower confidence + flag tier low, IN PLACE. NEVER removes the candidate (recall invariant)."""
    current = getattr(candidate, "confidence", 0.0) or 0.0
    candidate.confidence = current * _DOWNGRADE_CONFIDENCE_FACTOR
    candidate.confidence_tier = "low"


def _reopen_full_source(candidate, corpus, ledger) -> str | None:
    """Re-open the FULL submission source for a candidate via get_section (never truncated).

    Uses the candidate's submission span (or an absence anchor's claim span) to read the full
    surrounding section. Returns the annotated text, or None on any ToolRejected/missing span —
    which the caller records as a could_not_locate(half="source") and KEEPS the candidate.
    """
    from tools.get_section import get_section

    span = getattr(candidate, "submission_span_id", None)
    if span is None:
        anchor = getattr(candidate, "absence_anchor", None)
        span = getattr(anchor, "claim_span_id", None) if anchor is not None else None
    if span is None:
        return None
    # FULL section re-open around the span — NOT a ≤500-char excerpt. max_chars bounds a single
    # page; an oversized section returns a ToolRejected carrying a handle (paged forward below),
    # never a silent truncation.
    result = get_section(corpus, span.doc_id, ledger, start=span.start, end=span.end)
    if isinstance(result, ToolRejected):
        # Oversized -> page forward via the issued handle to assemble the FULL text (never truncate).
        handle = getattr(result, "handle", None)
        if handle is None:
            return None
        pages: list[str] = []
        preview = getattr(result, "preview", None)
        if preview:
            pages.append(preview)
        for _ in range(64):  # generous page cap; loop exits on the STILL_CURRENT sentinel
            page = get_section(corpus, span.doc_id, ledger, handle=handle)
            if isinstance(page, ToolRejected) or "[STILL_CURRENT]" in page:
                break
            pages.append(page)
        return "\n".join(pages) if pages else None
    return result


def _reopen_full_rule(candidate, manifest, ledger) -> str | None:
    """Re-open the FULL cited rule text via read_guideline(citation=...). None on ToolRejected."""
    from tools.read_guideline import read_guideline

    rule_span = getattr(candidate, "rule_span_id", None)
    citation = None
    if rule_span is not None:
        citation = rule_span.doc_id
    else:
        refs = getattr(candidate, "guidance_refs", None) or []
        citation = refs[0] if refs else None
    if not citation:
        return None
    result = read_guideline(manifest, ledger, citation=citation)
    if isinstance(result, ToolRejected):
        handle = getattr(result, "handle", None)
        if handle is None:
            return None
        pages = []
        preview = getattr(result, "preview", None)
        if preview:
            pages.append(preview)
        for _ in range(64):
            page = read_guideline(manifest, ledger, handle=handle)
            if isinstance(page, ToolRejected) or "[STILL_CURRENT]" in page:
                break
            pages.append(page)
        return "\n".join(pages) if pages else None
    if isinstance(result, list):
        # enumerate mode should not happen with a citation; treat as not-located.
        return None
    return result


def verify_candidates(
    candidates: list,
    fleet_client: Callable,
    *,
    corpus=None,
    manifest=None,
    ledger=None,
    reopen_source: Callable | None = None,
    reopen_rule: Callable | None = None,
    reopen_nt: Callable | None = None,
) -> tuple[list, CoverageReport]:
    """Fan each unique-dedup-key candidate over its decorrelated panel; apply consensus.

    Returns ``(verified_faults, CoverageReport)`` where ``len(verified_faults)`` equals the number
    of UNIQUE ``dedup_key`` groups (>= number of true candidates — never dropped). On a consensus
    DOWNGRADE the representative candidate object is mutated in place (confidence lowered,
    ``confidence_tier="low"``) and its dedup_key is recorded in ``reviewed_downgrade``; on KEEP the
    dedup_key is recorded in ``reviewed_keep`` (tier left ``"full"``). A source/rule that cannot be
    re-opened lands in ``could_not_locate`` and the candidate is KEPT unchanged (still ACTIVE).

    ``fleet_client`` is the completion callable (``chat_completion_tools`` in production; a scripted
    fleet double in tests). Two re-open modes:
      - production: pass ``corpus`` + ``manifest`` + ``ledger`` -> source+rule re-opened in FULL via
        ``get_section``/``read_guideline``;
      - test: inject ``reopen_source``/``reopen_rule``/``reopen_nt`` callables directly.
    """
    verified_faults: list = []
    reviewed_keep: list[str] = []
    reviewed_downgrade: list[dict] = []
    could_not_locate: list[dict] = []

    for group in consolidate(candidates):
        # Representative candidate for the group. Phase-5 emit already merged confidence/anchors;
        # we do NOT re-detect. Every member's existence is preserved: the representative is appended
        # once per unique dedup_key (no member is ever popped/removed — recall invariant).
        candidate = group.members[0]
        dedup_key = group.dedup_key
        family = family_of(candidate)
        panel = panel_for(family)

        # --- FULL re-open of both halves (VERIFY-02) ---------------------------------------------
        located = True
        if reopen_source is not None:
            source_text = reopen_source(candidate)
        elif corpus is not None and ledger is not None:
            source_text = _reopen_full_source(candidate, corpus, ledger)
        else:
            source_text = getattr(candidate, "evidence", "") or ""
        if source_text is None:
            could_not_locate.append({"dedup_key": dedup_key, "half": "source",
                                     "reason": "source span could not be re-opened"})
            located = False

        if reopen_rule is not None:
            rule_text = reopen_rule(candidate)
        elif manifest is not None and ledger is not None:
            rule_text = _reopen_full_rule(candidate, manifest, ledger)
        else:
            rule_text = ""
        # A rule half is only "could_not_locate" when we actually attempted a live re-open.
        if rule_text is None:
            could_not_locate.append({"dedup_key": dedup_key, "half": "rule",
                                     "reason": "cited rule could not be re-opened"})
            located = False

        if not located:
            # Reviewed-but-not-gradeable: KEEP as-is (confidence + tier unchanged), stays ACTIVE.
            verified_faults.append(candidate)
            continue

        nt = reopen_nt(candidate) if reopen_nt is not None else None

        # --- decorrelated, isolated fan-out ------------------------------------------------------
        panel_verdicts = []
        for model in panel:
            verdict = verify_once(candidate, source_text, rule_text, model, completion=fleet_client)
            panel_verdicts.append(
                {
                    "verdict": verdict.verdict.value if isinstance(verdict, VERDICT) else "KEEP",
                    "grounded": _grounded_of(verdict, candidate, nt),
                    "model": verdict.model if isinstance(verdict, VERDICT) else model,
                }
            )

        decision, agreeing = consensus(candidate, panel_verdicts, len(panel))
        if decision == "DOWNGRADE":
            _apply_downgrade(candidate)  # lower confidence IN PLACE — never remove (recall invariant)
            reviewed_downgrade.append({"dedup_key": dedup_key, "agreeing_verifiers": agreeing})
            log.info("consensus_downgrade", dedup_key=dedup_key, agreeing=agreeing)
        else:
            reviewed_keep.append(dedup_key)

        verified_faults.append(candidate)

    coverage = CoverageReport(
        reviewed_keep=reviewed_keep,
        reviewed_downgrade=reviewed_downgrade,
        could_not_locate=could_not_locate,
    )
    return verified_faults, coverage  # SAME objects; length == unique dedup_key groups — never dropped
