from __future__ import annotations

import json

from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS, format_flaw_catalog
from llm.client import chat_completion
from llm.prompts import DOCUMENT_CLASSIFIER, FLAW_TYPE_SELECTOR
from parse.section_splitter import detect_ctd_section
from schemas.documents import CTDSection, IntermediateReport


def classify_document_type(text_excerpt: str) -> tuple[CTDSection, str]:
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


def select_flaw_types(report: IntermediateReport) -> list[str]:
    """Ask the LLM which flaw categories to investigate for this document."""
    report_summary = (
        f"Document: {report.document_name}\n"
        f"Type: {report.document_type}\n"
        f"Sections: {', '.join(s.summary for s in report.sections)}\n"
        f"Consensus notes: {report.consensus_notes[:2000]}"
    )

    response = chat_completion(
        messages=[
            {
                "role": "system",
                "content": FLAW_TYPE_SELECTOR.format(flaw_catalog=format_flaw_catalog()),
            },
            {"role": "user", "content": report_summary},
        ],
        max_tokens=300,
    )

    try:
        start = response.index("[")
        end = response.rindex("]") + 1
        selected = json.loads(response[start:end])
        if isinstance(selected, list) and all(isinstance(s, str) for s in selected):
            return selected
    except (ValueError, json.JSONDecodeError):
        pass

    return list(FLAW_TYPE_DEFINITIONS.keys())[:4]


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
