from __future__ import annotations

import json

from json_repair import repair_json

from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS, format_flaw_catalog
from llm.client import chat_completion
from llm.prompts import DOCUMENT_CLASSIFIER, FLAW_TYPE_SELECTOR
from llm.structured import _extract_json_blob
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


def _find_balanced_array(text: str) -> str:
    """Return the first bracket-balanced ``[...]`` span in ``text``.

    Walks the string tracking nesting depth so we do not fall for prose that
    contains a second bracket pair (``["a"]. Skipped: [none]``). Respects
    string literals so brackets inside a JSON string do not throw off the
    counter. Returns ``""`` when no balanced span is found.
    """
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:i + 1]
    return ""


def _extract_json_array(response: str) -> str:
    """Prefer the first bracket-balanced JSON array in ``response``.

    Falls back to :func:`_extract_json_blob` when no balanced array is present.
    """
    if not response:
        return ""

    stripped = response.strip()

    if "```" in stripped:
        blob = _extract_json_blob(stripped)
        balanced = _find_balanced_array(blob)
        if balanced:
            return balanced
        if blob.startswith("["):
            return blob
        return blob

    balanced = _find_balanced_array(stripped)
    if balanced:
        return balanced

    return _extract_json_blob(stripped)


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

    extracted = _extract_json_array(response)
    selected = None
    if extracted:
        try:
            selected = json.loads(extracted)
        except json.JSONDecodeError:
            try:
                repaired = repair_json(extracted)
                selected = json.loads(repaired) if isinstance(repaired, str) else repaired
            except Exception:
                selected = None

    if isinstance(selected, list) and all(isinstance(s, str) for s in selected):
        return selected

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
