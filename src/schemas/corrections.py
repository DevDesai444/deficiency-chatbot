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


class Evaluation(BaseModel):
    verdict: Verdict
    feedback: str = ""
    corrections_reviewed: int = 0


class RecommendationSet(BaseModel):
    """Layer 3 output → Frontend."""
    job_id: str
    recommendations: list[Correction] = Field(default_factory=list)
    flaws_found: bool = True
    inner_loop_count: int = 0
    outer_loop_count: int = 0
    analysis_seconds: float = 0.0
