"""Verifier fan-out orchestrator (Wave 1 seam; consolidation/coverage land in Plan 03).

This module provides the thin fan-out seam the Wave-0 decorrelation + write-disabled tests target:
per candidate it derives the producer family, selects a DECORRELATED panel (``panel.panel_for``),
and issues one isolated ``verifier.verify_once`` call per panel member. Each verifier sees ONLY
claim + re-opened source + rule (never the producer's chain-of-thought) and is offered only
read-only tools — both enforced inside ``verifier.verify_once``.

The full consolidate/dedup + consensus + coverage-report wiring is Plan 03. Here we keep the
surface minimal: the fan-out that proves decorrelation (VERIFY-03) and write-disability (VERIFY-01)
in code. NO candidate is ever removed — this module only reads candidates and collects verdicts.
"""
from __future__ import annotations

from typing import Callable

import structlog

from config import MODEL_LINEAGE
from verify.panel import panel_for
from verify.verifier import verify_once

log = structlog.get_logger()

# The set of known lineage families (values of MODEL_LINEAGE) a producer tag may name.
_KNOWN_FAMILIES = frozenset(MODEL_LINEAGE.values())


def producer_family_of(candidate) -> str | None:
    """Derive the producer's model family from the candidate, or None for a deterministic leg.

    Decorrelation tags a model-produced candidate with its family; deterministic recall legs
    (oracle/checklist/structural) have no model producer -> None -> any fleet mix is valid.

    The interpretive tail records its producer in ``Fault.source`` as ``"reviewer:{family}:..."``
    (e.g. ``"reviewer:qwen:3.2.P.4.3"``). We read the family token from that tag against the known
    lineage families in ``config.MODEL_LINEAGE`` — no hardcoded family literal.
    """
    source = getattr(candidate, "source", "") or ""
    for token in source.split(":"):
        if token in _KNOWN_FAMILIES:
            return token
    return None


def _reopen_source(candidate) -> str:
    """Placeholder source-text supplier for the fan-out seam (Plan 03 wires get_section).

    Returns the claim's own cited evidence text if present, else empty. It deliberately never
    returns ``candidate.detail`` (the producer's reasoning) — decorrelation-in-code.
    """
    return getattr(candidate, "evidence", "") or ""


def verify_candidates(
    candidates: list,
    fleet_client: Callable,
    *,
    reopen_source: Callable = _reopen_source,
    reopen_rule: Callable | None = None,
) -> dict[str, list]:
    """Fan out each candidate over its decorrelated panel; return per-candidate verdicts.

    ``fleet_client`` is the completion callable (``chat_completion_tools`` in production, a scripted
    fleet double in tests). ``reopen_source``/``reopen_rule`` supply the re-opened full text the
    verifier judges (Plan 03 wires these to get_section/read_guideline). This seam performs NO
    consolidation and removes NO candidate.
    """
    results: dict[str, list] = {}
    for idx, candidate in enumerate(candidates):
        family = producer_family_of(candidate)
        panel = panel_for(family)
        source_text = reopen_source(candidate)
        rule_text = reopen_rule(candidate) if reopen_rule is not None else ""
        key = getattr(candidate, "dedup_key", None) or f"candidate:{idx}"
        verdicts = []
        for model in panel:
            verdicts.append(
                verify_once(candidate, source_text, rule_text, model, completion=fleet_client)
            )
        results[key] = verdicts
    return results
