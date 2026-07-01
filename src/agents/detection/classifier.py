from __future__ import annotations

from llm.client import chat_completion
from llm.prompts import DOCUMENT_CLASSIFIER
from parse.section_splitter import detect_ctd_section
from schemas.documents import CTDSection


def classify_document_type(text_excerpt: str) -> tuple[CTDSection, str]:
    """Use LLM to classify the document's CTD section and type."""
    rule_based = detect_ctd_section(text_excerpt)
    if rule_based != CTDSection.UNKNOWN:
        return rule_based, _section_to_label(rule_based)

    response = chat_completion(
        messages=[
            {"role": "system", "content": DOCUMENT_CLASSIFIER},
            {"role": "user", "content": text_excerpt[:2000]},
        ],
        max_tokens=100,
    )

    parts = response.strip().split("|")
    section_code = parts[0].strip() if parts else ""
    doc_type = parts[1].strip() if len(parts) > 1 else "Unknown"

    section = detect_ctd_section(section_code)
    return section, doc_type


def _section_to_label(section: CTDSection) -> str:
    labels = {
        CTDSection.S_4_1_SPECIFICATION: "Raw Material Specification",
        CTDSection.S_4_2_ANALYTICAL_PROCEDURES: "Analytical Procedures",
        CTDSection.S_4_3_VALIDATION: "Analytical Method Validation",
        CTDSection.S_4_4_BATCH_ANALYSES: "Batch Analysis Report",
        CTDSection.S_7_STABILITY: "Stability Study Report",
        CTDSection.P_2_DEVELOPMENT: "Pharmaceutical Development Report",
        CTDSection.P_3_MANUFACTURE: "Manufacturing Process Description",
        CTDSection.P_4_1_SPECIFICATION: "Drug Product Specification",
        CTDSection.P_4_3_VALIDATION: "Drug Product Method Validation",
        CTDSection.P_6_CONTAINER_CLOSURE: "Container Closure System",
        CTDSection.P_7_STABILITY: "Drug Product Stability",
    }
    return labels.get(section, section.value)
