from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from schemas.flaws import FlawCategory, Severity


class Verdict(StrEnum):
    PASS = "pass"
    MINOR_REVISION = "minor_revision"
    DEEPER_REVIEW = "deeper_review"


class Correction(BaseModel):
    flaw_category: FlawCategory
    suggestion: str
    explanation: str
    priority: Severity = Severity.MEDIUM
    references: list[str] = Field(default_factory=list)


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
