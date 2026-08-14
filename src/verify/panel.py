"""Decorrelation panel selection (VERIFY-03).

A candidate is verified by a fleet of models whose FAMILY differs from whatever produced the
candidate — a correlated error in one family (agreeableness/familial bias) then cannot
rubber-stamp the other. Deterministic legs (no model producer) get any fleet mix; an
interpretive-tail candidate produced by a Qwen reviewer gets a panel with no Qwen-lineage model.

Pure config lookup over ``config.MODEL_LINEAGE`` + ``config.VERIFIER_FLEET`` — NO hardcoded model
names (the fleet + lineage are env-overridable and guarded by ``test_config_verifier``). The panel
is never empty: if one family owns the whole fleet, we fall back to the full fleet and log, so a
missing decorrelated verifier never silently drops the candidate from review.
"""
from __future__ import annotations

import structlog

from config import MODEL_LINEAGE, VERIFIER_FLEET

log = structlog.get_logger()


def panel_for(producer_family: str | None) -> tuple[str, ...]:
    """Return the decorrelated verifier panel for a candidate's producer family.

    - ``producer_family is None`` (deterministic candidate — no model producer): the full
      ``VERIFIER_FLEET`` is valid; any cross-family mix is acceptable.
    - otherwise: exclude every fleet member whose ``MODEL_LINEAGE`` equals ``producer_family``.
      If that would leave the panel empty (a single family owns the whole fleet), fall back to the
      full fleet and log a warning — the panel is NEVER empty (a candidate always gets reviewed).
    """
    if producer_family is None:
        return VERIFIER_FLEET
    panel = tuple(m for m in VERIFIER_FLEET if MODEL_LINEAGE.get(m, "") != producer_family)
    if not panel:
        log.warning(
            "decorrelation_fallback_full_fleet",
            producer_family=producer_family,
            reason="producer family owns the entire fleet; no cross-family verifier available",
            fleet=list(VERIFIER_FLEET),
        )
        return VERIFIER_FLEET
    return panel
