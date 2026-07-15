from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from schemas.flaws import FlawCategory, Severity


class Verdict(StrEnum):
    PASS = "pass"
    MINOR_REVISION = "minor_revision"
    DEEPER_REVIEW = "deeper_review"


class Correction(BaseModel):
    """A recommendation the analyst can act on.

    Field descriptions reach the model: they are carried into the strict json_schema
    sent to the endpoint, and are the only place the shape of `explanation` is stated.
    """

    flaw_category: FlawCategory
    suggestion: str = Field(
        description=(
            "What to add or correct, specific enough to act on without rereading the "
            "finding. Name the data, section, or document."
        )
    )
    explanation: str = Field(
        description=(
            "Why this matters for the document under review, argued from the evidence "
            "in the finding. Never restate the suggestion. Never fill this from memory: "
            "if the finding carries no evidence, say what would need to be checked."
        )
    )
    priority: Severity = Severity.MEDIUM
    references: list[str] = Field(
        default_factory=list,
        description=(
            "Guidance named in the finding's own evidence, quoted as it appears there. "
            "Empty is the correct answer when the evidence names none — a citation "
            "recalled from memory rather than read is worse than no citation."
        ),
    )


class CorrectionList(BaseModel):
    """Object-rooted wrapper — Databricks strict json_schema requires an object at root."""
    corrections: list[Correction] = Field(default_factory=list)


class EvaluationOutput(BaseModel):
    """Strict-schema shape returned by the evaluator LLM."""
    verdict: Verdict
    feedback: str = ""


class Evaluation(BaseModel):
    verdict: Verdict
    feedback: str = ""
    corrections_reviewed: int = 0


class ParseFailed(BaseModel):
    """Typed sentinel — the frontend renders this as a needs-human-review card
    instead of receiving a raw LLM dump."""
    layer: str
    reason: str
    raw_output: str
    validation_error: str = ""
    requires_human_review: bool = True


class RecommendationSet(BaseModel):
    """Layer 3 output → Frontend."""
    job_id: str
    recommendations: list[Correction] = Field(default_factory=list)
    parse_failures: list[ParseFailed] = Field(default_factory=list)
    flaws_found: bool = True
    inner_loop_count: int = 0
    outer_loop_count: int = 0
    analysis_seconds: float = 0.0
