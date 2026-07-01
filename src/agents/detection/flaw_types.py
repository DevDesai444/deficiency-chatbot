"""Reference catalog of known deficiency categories.

The LLM dynamically selects which categories are relevant for each document —
this catalog provides the vocabulary, not the routing logic.
"""
from __future__ import annotations

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


def format_flaw_catalog() -> str:
    lines = []
    for name, desc in FLAW_TYPE_DEFINITIONS.items():
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)
