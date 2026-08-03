"""The fault-detection layer's output types.

A `Fault` is one candidate deficiency surfaced to the analyst. It carries not just the
claim and its evidence but *how far we could stand behind it*: the `tier` (how confident),
the `evidence_class` (what kind of check backed it), and the precedent it matched. The
design rule is recall-biased — a Fault is only ever *downgraded*, never silently dropped,
except when a deterministic oracle proves it false (that Fault is filtered before this
report is built).
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from schemas.documents import SpanID
from schemas.flaws import FlawCategory, Severity, SimilarDeficiency
from schemas.llm import ParseFailed


class EvidenceClass(StrEnum):
    """What kind of check stands behind the finding — surfaced so the analyst never
    mistakes a model opinion for a code-verified fact."""

    CODE_VERIFIED = "code_verified"      # an oracle recomputed / compared cells
    CHECKLIST = "checklist"              # a required element was searched for and is absent
    QUOTE_ANCHORED = "quote_anchored"    # the cited evidence span exists verbatim in the doc
    MODEL_JUDGMENT = "model_judgment"    # LLM reasoning only, no oracle or anchor


class Tier(StrEnum):
    """Confidence tier. Recall lives in ADVISORY — nothing is hidden, only ranked."""

    VERIFIED = "verified"          # T1 — oracle-confirmed, or strong precedent + self-consistency
    CORROBORATED = "corroborated"  # T2 — >=1 real precedent, no hard oracle
    ADVISORY = "advisory"          # T3 — model judgment, incl. novel / out-of-distribution


class ComplianceVerdict(StrEnum):
    """DETECT-04 / D-VER2: the enumerated compliance verdict a finding carries beside its cited rule.

    Free text cannot be scored deterministically by the harness, compared across the 3 spike runs,
    or diffed against the baseline -- the same reason the reason-code registry is enumerated.

    `compliant` is DELIBERATELY UNREPRESENTABLE. verify.py::_concedes_compliance exists because a
    live run emitted 10 of 31 "faults" whose own title ended "compliant. No finding." Making a
    compliant verdict impossible to express is the code-gate version of that lesson -- the same
    discipline that makes reason_code="not_unique" structurally unreachable in emit_finding.
    """

    VIOLATION = "violation"    # the submission's text contradicts an explicit requirement of the cited rule
    GAP = "gap"                # the rule requires something the submission does not contain
    AMBIGUOUS = "ambiguous"    # the rule applies, but the submission is insufficient to determine compliance


class Fault(BaseModel):
    """One candidate deficiency."""

    title: str = Field(description="One-line statement of the deficiency.")
    detail: str = Field(default="", description="What is wrong and why it matters, argued from the evidence.")
    category: FlawCategory = FlawCategory.GENERAL_CMC
    severity: Severity = Severity.MEDIUM

    tier: Tier = Tier.ADVISORY
    evidence_class: EvidenceClass = EvidenceClass.MODEL_JUDGMENT
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    verdict: ComplianceVerdict | None = Field(default=None, description="DETECT-04: enumerated compliance verdict, set on the agent path by emit_finding.")
    rule_span_id: SpanID | None = Field(default=None, description="GROUND-03: the exact rule clause span this finding cites, re-openable by Phase 5's verifier.")
    submission_span_id: SpanID | None = Field(default=None, description="GROUND-01: the exact submission span this finding rests on, so the finding is fully re-openable.")

    evidence: str = Field(default="", description="Verbatim span or cell the finding rests on.")
    section: str = Field(default="", description="Section heading the fault sits in.")
    page: int = 0
    table_ref: str = Field(default="", description="Table the fault concerns, e.g. 'Table 16'.")

    source: str = Field(default="", description="What produced it, e.g. 'oracle:result_vs_limit', 'specialist:elemental_impurities', 'reviewer:1.4.6'.")
    guidance_refs: list[str] = Field(default_factory=list)
    precedents: list[SimilarDeficiency] = Field(default_factory=list)

    novel: bool = Field(default=False, description="No matching precedent in the KB.")
    out_of_distribution: bool = Field(default=False, description="Doc type the KB does not cover well (e.g. non-patch).")
    challenge_note: str = Field(default="", description="Grounded counter-evidence found by the challenge pass, if it lowered confidence.")
    cited_section_indices: list[int] = Field(default_factory=list, description="Section indices a cross-section finding references, so the grounded challenge can see every cited section.")


class FaultReport(BaseModel):
    """The detection layer's output → frontend."""

    job_id: str = ""
    faults: list[Fault] = Field(default_factory=list)
    faults_found: bool = False
    domains_checked: list[str] = Field(default_factory=list)
    parse_failures: list[ParseFailed] = Field(default_factory=list)
    analysis_seconds: float = 0.0
    stop_reason: str = Field(default="", description="AGENT-03/04: how the review loop ended -- completed | ceiling | diminishing-returns | max-turns | breaker. Empty on the legacy single-shot path.")
    budget_exhausted: bool = Field(default=False, description="AGENT-03: True when a hard ceiling ended the run, so a partial is never read as a complete review.")
