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
from typing import Literal

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


class RetrievalHit(BaseModel):
    """One sub-threshold retrieval hit recorded on a CoverageAbsenceAnchor (D-GATE2).

    Stores the span the search surfaced together with the score that fell below the run's
    recorded threshold, so the Phase-7 verifier can RE-RUN the negative rather than trust a
    frozen snapshot.
    """

    span_id: SpanID = Field(description="D-GATE2: the span-ID a below-threshold search_corpus hit surfaced.")
    score: float = Field(description="D-THR: the retrieval score that fell below the recorded threshold.")


class CoverageAbsenceAnchor(BaseModel):
    """The submission half of an absence-typed finding (D-GATE1).

    A never-mentioned / whole-section absence has no single submission text span, so instead of a
    submission_span_id the finding carries this typed anchor: the exact enumerate inputs + the
    sub-threshold retrieval evidence + the manifest span-IDs proving the search space. Everything
    needed for the Phase-7 verifier to RE-RUN "was this searched and found lacking?" (D-GATE2) --
    the negative is independently reproducible, not a recorded assertion.
    """

    profile: list[str] = Field(default_factory=list, description="D-GATE2: content-derived submission profiles enumerated.")
    family: str = Field(default="", description="The CTD family the absent requirement belongs to.")
    requirement_id: str = Field(default="", description="The requirement_index entry id that was searched-for and found lacking.")
    threshold: float = Field(default=0.0, description="D-THR: the recorded retrieval threshold this run used.")
    sub_threshold_hits: list[RetrievalHit] = Field(default_factory=list, description="D-GATE2: the top-k search_corpus hits that fell below threshold, so a verifier RE-RUNS the negative.")
    manifest_span_ids: list[SpanID] = Field(default_factory=list, description="Manifest span-IDs proving the search space (what was enumerated/searched).")
    claim_span_id: SpanID | None = Field(default=None, description="D-ABS4: the unsupported narrative-claim CORPUS span when one exists (mvr/MS-03), else None.")


class StructuralAnchor(BaseModel):
    """D-STR3: re-derivable structural inconsistency anchor (sibling of CoverageAbsenceAnchor).

    Carries one claim span + N basis span-IDs + relation enum + expected-vs-actual values.
    Re-derivable: the Phase-7 verifier re-runs the computation, never trusts the snapshot.
    Cells resolved via tables.py (table_id,row,col)->SpanID; each basis span validated
    against its own store (CORPUS vs RULEBOOK).
    """

    claim_span_id: SpanID = Field(
        description="D-STR3: the span of the cell that contains the claimed aggregate/summary value.")
    basis_span_ids: list[SpanID] = Field(
        default_factory=list,
        description="D-STR3: spans of the cells whose values were combined to derive the expected value.")
    relation: Literal["EQUALS", "LEQ", "GEQ", "SUM", "MAX", "MIN", "MEAN"] = Field(
        description="D-STR3: the arithmetic relation that must hold between basis values and the claim.")
    expected_value: str = Field(
        default="",
        description="D-STR3: the re-derived expected value (deterministic computation over basis spans).")
    actual_value: str = Field(
        default="",
        description="D-STR3: the value actually found in the claim span.")
    comparison_store: Literal["CORPUS", "RULEBOOK"] = Field(
        default="CORPUS",
        description="D-STR3: which store the basis spans live in (CORPUS for intra-doc; RULEBOOK for spec limits).")
    scoping_confidence: Literal["full", "low"] = Field(
        default="full",
        description="D-ABS2: 'low' when a basis cell is not cleanly addressable; over-emit rather than drop.")


class ReferenceAnchor(BaseModel):
    """D-REF2: cross-reference edge + anomaly anchor (sibling of CoverageAbsenceAnchor).

    A single typed anchor carrying anomaly enum + src span + optional dst span(s).
    One re-derivation path, one verifier branch (D-REF2).
    """

    src_span_id: SpanID = Field(
        description="D-REF2: the span in the source document that contains the reference.")
    dst_span_id: SpanID | None = Field(
        default=None,
        description="D-REF2: the span in the target document the reference points to, if resolved.")
    edge_type: Literal["hyperlink", "textual_ref", "value_crossref"] = Field(
        description="D-REF1: the kind of reference edge connecting src to dst.")
    anomaly: Literal["UNRESOLVED_REF", "ABSENT_TARGET", "VALUE_CONTRADICTION"] = Field(
        description="D-REF2: the detected reference anomaly type.")
    scoping_confidence: Literal["full", "low"] = Field(
        default="full",
        description="D-REF3: 'low' for label-match-only contradictions (no confirmed edge); 'full' for edge-linked contradictions.")


class PrecedentAnchor(BaseModel):
    """D-PRC2: precedent similarity evidence anchor.

    The re-openable submission span (the grounded claim) + precedent chunk ids +
    similarity scores as attached supporting evidence. Grounding lives on the submission
    side; precedent text is never a finding source (D-RB2(5)).
    """

    submission_span_id: SpanID = Field(
        description="D-PRC2: the re-openable submission span the precedent similarity is anchored to.")
    precedent_doc_ids: list[str] = Field(
        default_factory=list,
        description="D-PRC2: IDs of the precedent corpus chunks with above-threshold similarity.")
    similarity_scores: list[float] = Field(
        default_factory=list,
        description="D-PRC4: cosine similarity scores for each precedent_doc_id (same order).")
    threshold: float = Field(
        default=0.0,
        description="D-PRC4: the absolute dense-cosine threshold used in this run (not a constant here — caller reads from baseline JSON).")
    anda_excluded: list[str] = Field(
        default_factory=list,
        description="D-PRC3: ANDA numbers filtered out of this retrieval (same-ANDA exclusion).")


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
    absence_anchor: CoverageAbsenceAnchor | None = Field(default=None, description="D-GATE1: the submission half for an absence-typed finding; mutually exclusive with a submission_span_id in practice.")

    # D-ENV1 FULL: Phase-5 typed anchor fields (additive — no existing field changed or removed)
    structural_anchor: StructuralAnchor | None = Field(
        default=None, description="D-STR3: re-derivable structural inconsistency anchor.")
    reference_anchor: ReferenceAnchor | None = Field(
        default=None, description="D-REF2: cross-reference edge + anomaly.")
    precedent_anchor: PrecedentAnchor | None = Field(
        default=None, description="D-PRC2: precedent similarity evidence.")
    leg_tag: Literal["ABSENCE", "STRUCTURAL", "REFERENCE", "PRECEDENT"] | None = Field(
        default=None, description="D-ENV1: which recall leg produced this Fault.")
    dedup_key: str | None = Field(
        default=None,
        description="D-CON1: dedup key '{doc_id}:{section_id}:{rule_id_or_null}'; rule_id is nullable for structural/precedent findings.")
    confidence_tier: Literal["full", "low"] | None = Field(
        default=None,
        description="D-ENV1: top-level confidence tier; 'low' = scoping-confidence flag, label-match-only, or precedent soft-lead. Required for D-CON1 ordering.")

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
    """The detection layer's output -> frontend."""

    job_id: str = ""
    faults: list[Fault] = Field(default_factory=list)
    faults_found: bool = False
    domains_checked: list[str] = Field(default_factory=list)
    parse_failures: list[ParseFailed] = Field(default_factory=list)
    analysis_seconds: float = 0.0
    stop_reason: str = Field(default="", description="AGENT-03/04: how the review loop ended -- completed | ceiling | diminishing-returns | max-turns | breaker. Empty on the legacy single-shot path.")
    budget_exhausted: bool = Field(default=False, description="AGENT-03: True when a hard ceiling ended the run, so a partial is never read as a complete review.")
