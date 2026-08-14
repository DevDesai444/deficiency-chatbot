"""Verifier fan-out orchestrator (Wave 1 seam).

Per candidate this module: derives the producer family, selects a DECORRELATED panel
(``panel.panel_for``), issues one isolated ``verifier.verify_once`` call per panel member (each
verifier sees ONLY claim + re-opened source + rule, never the producer's chain-of-thought, and is
offered only read-only tools — both enforced inside ``verifier.verify_once``), then applies the
code-gated ``consensus`` invariant and, on DOWNGRADE, LOWERS the candidate's confidence IN PLACE —
never removing it. It also exposes ``consolidate`` (group by ``Fault.dedup_key``, merge-never-drop).

RECALL INVARIANT (β law, VERIFY-01): no path here deletes/pops/removes a candidate. A DOWNGRADE
only mutates ``confidence``/``confidence_tier``; the output list length always equals the input
length. ``test_invariant_no_drop`` asserts this in code, and a static guard asserts no drop verb
appears in ``src/verify/``.

NOTE (Wave-1 seam / Plan-03 handoff): the full get_section/read_guideline re-open of source+rule and
the byte-exact corpus re-resolution of each surfaced ``grounding_span`` are wired by Plan 03. Here,
groundedness is computed via ``grounding.is_grounded`` when a NormalizedText for the candidate is
resolvable, and otherwise falls back to "the model returned a non-empty grounding_span" (the VERDICT
schema already enforces a non-blank span). ``consensus`` stays STRICT on the grounded bool it is
handed — this seam only decides how that bool is computed, it never loosens the consensus rule.
"""
from __future__ import annotations

from typing import Callable

import structlog

from config import MODEL_LINEAGE
from schemas.llm import VERDICT
from verify.consensus import consensus
from verify.grounding import is_grounded
from verify.panel import panel_for
from verify.verifier import verify_once

log = structlog.get_logger()

# The set of known lineage families (values of MODEL_LINEAGE) a producer tag may name.
_KNOWN_FAMILIES = frozenset(MODEL_LINEAGE.values())

# The general confidence-lowering factor applied on a consensus DOWNGRADE. This is a GENERAL,
# documented constant (a monotone confidence discount) — NOT a corpus/submission-specific token.
# It never zeroes or drops the candidate; it only lowers confidence and flags the tier "low".
_DOWNGRADE_CONFIDENCE_FACTOR = 0.5


def producer_family_of(candidate) -> str | None:
    """Derive the producer's model family from the candidate, or None for a deterministic leg.

    Deterministic recall legs (oracle/checklist/structural) have no model producer -> None -> any
    fleet mix is valid. The interpretive tail records its producer in ``Fault.source`` as
    ``"reviewer:{family}:..."``; we read the family token against ``config.MODEL_LINEAGE`` values —
    no hardcoded family literal.
    """
    source = getattr(candidate, "source", "") or ""
    for token in source.split(":"):
        if token in _KNOWN_FAMILIES:
            return token
    return None


class _CandidateGroup:
    """A consolidation group: a shared ``dedup_key`` + its merged member Faults (merge, never drop)."""

    def __init__(self, dedup_key: str):
        self.dedup_key = dedup_key
        self.members: list = []


def consolidate(candidates: list) -> list:
    """Group candidates by ``Fault.dedup_key`` (VERIFY-02). MERGE, never drop.

    Two Faults with the same dedup_key land in one group (count preserved across members); distinct
    keys stay separate. Returns a list of groups, each exposing ``.dedup_key`` + ``.members``.
    """
    groups: dict[str, _CandidateGroup] = {}
    for c in candidates:
        key = getattr(c, "dedup_key", None)
        if not key:
            span = getattr(c, "submission_span_id", None)
            key = f"{span.doc_id}:{span.start}:null" if span is not None else f"candidate:{id(c)}"
        groups.setdefault(key, _CandidateGroup(key)).members.append(c)  # MERGE, never drop
    return list(groups.values())


def _grounded_of(verdict, candidate, nt) -> bool:
    """Whether a verdict counts as grounded. Byte-exact via is_grounded when nt is available,
    else falls back to a non-empty grounding_span (Plan-03 wires the corpus re-open)."""
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


def verify_candidates(
    candidates: list,
    fleet_client: Callable,
    *,
    reopen_source: Callable | None = None,
    reopen_rule: Callable | None = None,
    reopen_nt: Callable | None = None,
) -> list:
    """Fan out each candidate over its decorrelated panel; apply consensus; return the SAME list.

    Output length == input length (never dropped). On a consensus DOWNGRADE the candidate object is
    mutated in place (confidence lowered, ``confidence_tier="low"``); otherwise it is untouched.

    ``fleet_client`` is the completion callable (``chat_completion_tools`` in production; a scripted
    fleet double in tests). ``reopen_source``/``reopen_rule`` supply the re-opened full text the
    verifier judges; ``reopen_nt`` supplies the NormalizedText for byte-exact grounding
    re-resolution — Plan 03 wires all three to get_section/read_guideline over the real corpus.
    """
    for candidate in candidates:
        family = producer_family_of(candidate)
        panel = panel_for(family)
        source_text = reopen_source(candidate) if reopen_source is not None else (getattr(candidate, "evidence", "") or "")
        rule_text = reopen_rule(candidate) if reopen_rule is not None else ""
        nt = reopen_nt(candidate) if reopen_nt is not None else None

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
            log.info("consensus_downgrade", dedup_key=getattr(candidate, "dedup_key", None), agreeing=agreeing)

    return candidates  # SAME objects, same length — downgrade-never-drop
