from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class CTDSection(StrEnum):
    S_1_GENERAL = "3.2.S.1"
    S_2_MANUFACTURE = "3.2.S.2"
    S_3_CHARACTERIZATION = "3.2.S.3"
    S_4_1_SPECIFICATION = "3.2.S.4.1"
    S_4_2_ANALYTICAL_PROCEDURES = "3.2.S.4.2"
    S_4_3_VALIDATION = "3.2.S.4.3"
    S_4_4_BATCH_ANALYSES = "3.2.S.4.4"
    S_4_5_JUSTIFICATION = "3.2.S.4.5"
    S_5_REFERENCE_STANDARDS = "3.2.S.5"
    S_6_CONTAINER_CLOSURE = "3.2.S.6"
    S_7_STABILITY = "3.2.S.7"
    P_1_DESCRIPTION = "3.2.P.1"
    P_2_DEVELOPMENT = "3.2.P.2"
    P_3_MANUFACTURE = "3.2.P.3"
    P_4_1_SPECIFICATION = "3.2.P.4.1"
    P_4_2_ANALYTICAL_PROCEDURES = "3.2.P.4.2"
    P_4_3_VALIDATION = "3.2.P.4.3"
    P_4_4_BATCH_ANALYSES = "3.2.P.4.4"
    P_4_5_JUSTIFICATION = "3.2.P.4.5"
    P_5_REFERENCE_STANDARDS = "3.2.P.5"
    P_6_CONTAINER_CLOSURE = "3.2.P.6"
    P_7_STABILITY = "3.2.P.7"
    P_8_APPENDICES = "3.2.P.8"
    A_FACILITIES = "3.2.A.1"
    A_ADVENTITIOUS = "3.2.A.2"
    R_REGIONAL = "3.2.R"
    UNKNOWN = "unknown"


class ExtractedTable(BaseModel):
    title: str = ""
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    page: int = 0


class ParsedSection(BaseModel):
    section_id: CTDSection = CTDSection.UNKNOWN
    heading: str = ""
    text: str = ""
    tables: list[ExtractedTable] = Field(default_factory=list)
    page_start: int = 0
    page_end: int = 0


class ChunkGroup(BaseModel):
    """Sections grouped for a single extraction agent."""
    group_id: str
    sections: list[ParsedSection]


class ExtractionFinding(BaseModel):
    section_id: CTDSection
    finding: str
    evidence: str = ""
    agent_name: str = ""


class SectionSummary(BaseModel):
    section_id: CTDSection
    summary: str
    key_values: dict[str, str] = Field(default_factory=dict)


class IntermediateReport(BaseModel):
    """Layer 1 output → Layer 2 input."""
    document_name: str
    document_type: str = ""
    sections: list[SectionSummary] = Field(default_factory=list)
    findings: list[ExtractionFinding] = Field(default_factory=list)
    consensus_notes: str = ""
