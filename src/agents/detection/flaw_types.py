"""Maps CTD section types to relevant deficiency categories for dynamic agent routing."""
from __future__ import annotations

from schemas.documents import CTDSection

FLAW_TYPE_DEFINITIONS: dict[str, str] = {
    "Specification/CoA": "Incomplete specifications, missing acceptance criteria, CoA discrepancies",
    "Method/Validation": "Analytical method not validated, missing validation parameters (LOD, LOQ, linearity, etc.)",
    "Impurities": "Missing impurity limits, unqualified impurities, incomplete identification",
    "Stability": "Insufficient stability data, out-of-trend results, inadequate study design",
    "Dissolution": "Missing dissolution method, incomplete profiles, inadequate discriminatory power",
    "Container/Closure": "Inadequate container closure system, missing extractables/leachables data",
    "Manufacturing Process": "Process validation gaps, inadequate in-process controls, scale-up issues",
    "Development Report": "Incomplete formulation justification, missing QbD elements",
    "Batch Data": "Missing batch records, inconsistent results, reconciliation issues",
    "Characterization": "Incomplete characterization, missing justification for specifications",
    "Excipients": "Excipient compatibility issues, missing functional characterization",
    "Reference Standards": "Missing reference standard characterization or certificates",
    "Elemental Impurities": "Missing elemental impurity risk assessment or data",
}

SECTION_TO_FLAW_TYPES: dict[CTDSection, list[str]] = {
    CTDSection.S_4_1_SPECIFICATION: [
        "Specification/CoA", "Impurities", "Characterization",
    ],
    CTDSection.S_4_2_ANALYTICAL_PROCEDURES: [
        "Method/Validation", "Specification/CoA",
    ],
    CTDSection.S_4_3_VALIDATION: [
        "Method/Validation", "Specification/CoA", "Impurities",
    ],
    CTDSection.S_4_4_BATCH_ANALYSES: [
        "Batch Data", "Specification/CoA", "Impurities",
    ],
    CTDSection.S_7_STABILITY: [
        "Stability", "Specification/CoA", "Container/Closure",
    ],
    CTDSection.P_2_DEVELOPMENT: [
        "Development Report", "Excipients", "Dissolution",
    ],
    CTDSection.P_3_MANUFACTURE: [
        "Manufacturing Process", "Batch Data",
    ],
    CTDSection.P_4_1_SPECIFICATION: [
        "Specification/CoA", "Dissolution", "Impurities",
    ],
    CTDSection.P_4_3_VALIDATION: [
        "Method/Validation", "Dissolution",
    ],
    CTDSection.P_6_CONTAINER_CLOSURE: [
        "Container/Closure", "Elemental Impurities",
    ],
    CTDSection.P_7_STABILITY: [
        "Stability", "Container/Closure", "Dissolution",
    ],
}

DEFAULT_FLAW_TYPES = [
    "Specification/CoA", "Method/Validation", "Impurities", "Stability",
]


def get_relevant_flaw_types(section: CTDSection) -> list[str]:
    return SECTION_TO_FLAW_TYPES.get(section, DEFAULT_FLAW_TYPES)
