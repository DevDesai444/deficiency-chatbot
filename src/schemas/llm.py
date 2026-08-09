from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ParseFailed(BaseModel):
    """Typed sentinel — the frontend renders this as a needs-human-review card
    instead of receiving a raw LLM dump. Emitted by the defense-in-depth structured
    output path (llm.structured) when strict decoding + repair all fail."""

    layer: str
    reason: str
    raw_output: str
    validation_error: str = ""
    requires_human_review: bool = True


class VerdictChoice(str, Enum):
    """D-07 / D-11: enum values are NEVER coerced — off-value → ParseFailed.

    Values are case-sensitive: KEEP and DOWNGRADE are the only valid tokens.
    Any other string (e.g. 'keep', 'Keep', 'KEEP ') must reach ParseFailed,
    never be guessed or coerced.
    """

    KEEP = "KEEP"
    DOWNGRADE = "DOWNGRADE"


class VERDICT(BaseModel):
    """Minimal verifier verdict model — D-07.

    Phase 7 EXTENDS this model (add fields); it must NEVER redefine it.
    The schema derived by tool_schema_for_databricks(VERDICT) is the stable
    guided-decode target for both thinking modes.

    Note: grounding_span is required here; byte-exact re-resolution against the
    corpus is enforced in Phase 7 (before any finding is surfaced), not Phase 6.
    """

    verdict: VerdictChoice  # NEVER coerced (D-11); off-value → ParseFailed
    confidence: float = Field(ge=0.0, le=1.0)  # coercible: numeric-string→float (lossless)
    rationale: str  # why keep/downgrade (for regulatory reviewer; E6)
    grounding_span: str  # verbatim cited span the verdict rests on
