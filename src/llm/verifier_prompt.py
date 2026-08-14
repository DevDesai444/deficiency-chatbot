"""Canonical verifier elicitation prompt for the β verifier (Phase 6 probe + Phase 7 agent).

The β verifier judges each deterministic candidate deficiency KEEP | DOWNGRADE. Weak
open-weights models (Llama 3.3 70B, Qwen MoE), given a candidate framed as a "finding",
default to agreement (confirmation bias) and rubber-stamp everything KEEP — providing zero
precision. This prompt supplies general *skeptical-reviewer discipline* that makes the model
actually test the allegation against the literal evidence.

ANTI-OVERFITTING LAW (β): this prompt is model-agnostic AND corpus-agnostic. It contains NO
submission-, document-, corpus-, or fault-family-specific content (no plate/MIN/MEAN, no
CTD-section literals, no eval-set identifiers). It encodes only the general discipline a good
FDA/ICH reviewer applies to any allegation. The two-sided D-06b gate (KEEP-recall floor AND
DOWNGRADE-rate floor) guards against the opposite failure — an over-skeptical prompt that
DOWNGRADEs real deficiencies fails the KEEP-recall floor.

RECALL INVARIANT (β): DOWNGRADE never removes a candidate; it only lowers confidence
(downgrade-never-drop, enforced in code, Phase 7). The prompt states this so the model
scrutinizes hard without fearing it will erase a true positive.

The same prompt the D-06 probe gate tests is the prompt the Phase 7 verifier ships, so the
gate measures production elicitation rather than a throwaway test string.
"""
from __future__ import annotations

from typing import Literal

# Invariant-aligned verifier discipline. No corpus-, document-, or fault-family-specific text.
#
# The prompt SPECIFIES the downgrade-never-drop invariant (Phase 7): a candidate is KEPT unless
# the verifier can AFFIRMATIVELY DISPROVE it from the evidence. "Unsure" and "not fully proven"
# both resolve to KEEP — only demonstrated FALSENESS earns a DOWNGRADE. This is the correct spec
# of the verifier's job and it is what makes weak open-weights models discriminate per-item
# instead of following a global prompt lean: an earlier "DOWNGRADE unless the span fully proves
# the violation" framing inverted the invariant and drove blanket-DOWNGRADE on truncated spans
# (D-06b keep-recall floor caught it). The aggregate examples name a GENERAL class of numeric
# structural checks (any computed value vs. its source numbers), not this corpus.
_CORE = (
    "You are an FDA/ICH regulatory VERIFIER applying a strict evidentiary rule: a candidate "
    "deficiency is KEPT unless you can AFFIRMATIVELY DISPROVE it from the evidence.\n"
    "Default to KEEP. Emit DOWNGRADE ONLY when the source span itself lets you positively "
    "demonstrate the candidate is FALSE — for example:\n"
    " - the span DIRECTLY CONTRADICTS the claim (it states the opposite of what the candidate "
    "alleges), or\n"
    " - the candidate is INTERNALLY INCONSISTENT: it cites a computed or aggregate value "
    "(e.g. a min, mean, max, count, or sum) that does not follow from the numbers actually "
    "present in the span, or that mixes values from unrelated cells or rows so the computation "
    "is invalid.\n"
    "If you are unsure, or the span merely lacks full context, KEEP — do NOT downgrade for lack "
    "of proof. DOWNGRADE requires proof of FALSENESS, not absence of proof. Downgrade never "
    "removes a finding; it only lowers confidence. Ground your verdict in a verbatim substring "
    "of the source span."
)


def _thinking_directive(thinking_mode: str, family: str) -> str:
    """Return the per-family reasoning soft-switch line for the given mode.

    The switch token is model-family-specific: Qwen uses ``/think`` · ``/no_think``,
    Nemotron uses ``detailed thinking on`` · ``detailed thinking off``, and Llama has no
    soft switch (a plain instruction elicits reasoning for the "on" mode; "off" is empty).
    An unknown family falls back to the Llama behaviour.
    """
    if family == "qwen":
        return "/think\n" if thinking_mode == "on" else "/no_think\n"
    if family.startswith("nemotron"):
        return "detailed thinking on\n" if thinking_mode == "on" else "detailed thinking off\n"
    # llama / unknown: no soft-switch token
    return "Think step by step, then answer.\n" if thinking_mode == "on" else ""


def verifier_system_prompt(thinking_mode: Literal["on", "off"] = "off", model: str | None = None) -> str:
    """Return the verifier system prompt for the given thinking mode and target model.

    ``model`` (a Databricks endpoint id) selects the correct reasoning soft-switch via
    MODEL_LINEAGE. When ``model`` is None the family is unknown → Llama-style behaviour.
    ``on`` elicits reasoning before the verdict; ``off`` asks for a direct verdict.
    Discrimination discipline (``_CORE``) is identical across modes and models.
    """
    family = ""
    if model:
        from config import MODEL_LINEAGE  # function-local: avoid import cycle
        family = MODEL_LINEAGE.get(model, "")
    return _thinking_directive(thinking_mode, family) + _CORE
