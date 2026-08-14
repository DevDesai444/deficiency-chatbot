"""The consensus gate — the downgrade-never-drop invariant, in CODE (β law, not a prompt).

Aggregates a panel's verdicts into a single decision. A candidate is DOWNGRADEd ONLY on affirmative
GROUNDED majority; everything else — lone downgrade, split vote, ungrounded downgrade, unsure,
parse-fail — collapses to KEEP. This is what makes a WEAK decorrelated verifier fleet raise
precision WITHOUT ever costing a true positive (CLAUDE.md RECALL INVARIANT):

  - a vote counts toward a DOWNGRADE only if it is DOWNGRADE **and grounded**;
  - ``len(grounded downgraders) * 2 > panel_size``  -> DOWNGRADE, else KEEP;
  - single-member decorrelated panel (``panel_size == 1``): a lone GROUNDED DOWNGRADE downgrades
    (documented single-member rule, RESEARCH Open Question 2) — still recall-safe: a lone
    ungrounded / unsure / KEEP vote -> KEEP.

This function NEVER removes a candidate. It returns only a decision string + the agreeing models;
the caller lowers ``confidence``/``confidence_tier`` on DOWNGRADE and KEEPS the Fault object. There
is no ``.pop``/``.remove``/``del`` of any candidate anywhere on this path (Pitfall 4).
"""
from __future__ import annotations

from typing import Literal

from schemas.llm import VERDICT, VerdictChoice


def _is_grounded_downgrade(v) -> tuple[bool, str]:
    """Normalize one panel verdict record -> (counts_as_grounded_downgrade, model).

    Accepts:
      - a dict ``{"verdict": "DOWNGRADE"|"KEEP", "grounded": bool, "model": str}`` (the panel-record
        form the orchestrator/tests pass after grounding.is_grounded has been evaluated), OR
      - a ``VERDICT`` object (``.verdict`` is a ``VerdictChoice``; grounding must be precomputed and
        attached as a ``grounded`` attribute since consensus is not handed the corpus here).
    Anything else (a plain ``"KEEP"`` string, a ParseFailed, None) contributes nothing.
    """
    if isinstance(v, dict):
        verdict = v.get("verdict")
        grounded = bool(v.get("grounded", False))
        model = v.get("model", "")
        is_downgrade = verdict == VerdictChoice.DOWNGRADE.value or verdict == VerdictChoice.DOWNGRADE
        return (is_downgrade and grounded), model
    if isinstance(v, VERDICT):
        grounded = bool(getattr(v, "grounded", False))
        is_downgrade = v.verdict == VerdictChoice.DOWNGRADE
        return (is_downgrade and grounded), v.model
    # "KEEP" string, ParseFailed, None, or any unreadable vote -> not a grounded downgrade.
    return False, getattr(v, "model", "") or ""


def consensus(
    candidate,
    verdicts: list,
    panel_size: int,
) -> tuple[Literal["KEEP", "DOWNGRADE"], list[str]]:
    """Aggregate panel verdicts into (decision, agreeing_models). NEVER removes a candidate.

    ``candidate`` is accepted for symmetry/logging (the invariant is candidate-independent here — a
    verdict's grounding is precomputed in the record). See the module docstring for the rule.
    """
    downgraders = [model for v in verdicts for counts, model in [_is_grounded_downgrade(v)] if counts]

    if panel_size == 1:
        # Single-member decorrelated panel (e.g. a Qwen-produced tail candidate leaves only 1 Llama):
        # a lone GROUNDED DOWNGRADE downgrades; a lone ungrounded/unsure/KEEP -> KEEP. Still
        # recall-safe: unsure never downgrades.
        decision: Literal["KEEP", "DOWNGRADE"] = "DOWNGRADE" if len(downgraders) == 1 else "KEEP"
        return decision, downgraders

    # Multi-member panel: affirmative GROUNDED majority (strictly more than half).
    if len(downgraders) * 2 > panel_size:
        return "DOWNGRADE", downgraders
    return "KEEP", downgraders
