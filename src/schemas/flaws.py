from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from schemas.documents import CTDSection


class FlawCategory(StrEnum):
    SPEC_INCOMPLETE = "spec_incomplete"
    SPEC_MISMATCH = "spec_mismatch"
    SPEC_LIMITS_MISSING = "spec_limits_missing"
    METHOD_NOT_VALIDATED = "method_not_validated"
    METHOD_SPECIFICITY = "method_specificity"
    METHOD_ACCURACY = "method_accuracy"
    METHOD_LINEARITY = "method_linearity"
    METHOD_ROBUSTNESS = "method_robustness"
    METHOD_LOD_LOQ = "method_lod_loq"
    IMPURITY_LIMITS = "impurity_limits"
    IMPURITY_QUALIFICATION = "impurity_qualification"
    IMPURITY_IDENTIFICATION = "impurity_identification"
    STABILITY_DESIGN = "stability_design"
    STABILITY_DATA_INSUFFICIENT = "stability_data_insufficient"
    STABILITY_OUT_OF_TREND = "stability_out_of_trend"
    CONTAINER_CLOSURE_INADEQUATE = "container_closure_inadequate"
    CONTAINER_EXTRACTABLES = "container_extractables"
    BATCH_DATA_MISSING = "batch_data_missing"
    BATCH_INCONSISTENCY = "batch_inconsistency"
    PROCESS_VALIDATION = "process_validation"
    PROCESS_CONTROLS = "process_controls"
    REFERENCE_STANDARD = "reference_standard"
    COA_DISCREPANCY = "coa_discrepancy"
    DISSOLUTION_METHOD = "dissolution_method"
    DISSOLUTION_PROFILE = "dissolution_profile"
    EXCIPIENT_COMPATIBILITY = "excipient_compatibility"
    POLYMORPHIC_FORM = "polymorphic_form"
    PARTICLE_SIZE = "particle_size"
    GENERAL_CMC = "general_cmc"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SimilarDeficiency(BaseModel):
    anda_number: str = ""
    product_name: str = ""
    deficiency_text: str = ""
    similarity_score: float = 0.0


class Corroboration(BaseModel):
    agent_name: str
    agrees: bool
    reasoning: str = ""


class FlawFinding(BaseModel):
    category: FlawCategory
    section_id: CTDSection
    description: str
    evidence: str = ""
    severity: Severity = Severity.MEDIUM
    corroborations: list[Corroboration] = Field(default_factory=list)
    similar_deficiencies: list[SimilarDeficiency] = Field(default_factory=list)


class FlawReport(BaseModel):
    """Layer 2 output → Layer 3 input."""
    flaws_found: bool
    findings: list[FlawFinding] = Field(default_factory=list)
    consensus_summary: str = ""
    agents_participated: list[str] = Field(default_factory=list)
    consensus_rounds: int = 0
