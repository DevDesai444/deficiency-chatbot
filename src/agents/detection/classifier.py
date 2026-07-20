from __future__ import annotations

import json
import re

import structlog
from json_repair import repair_json

from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS, format_flaw_catalog
from agents.event_bus import emit_sync
from llm.client import chat_completion
from llm.prompts import DOCUMENT_CLASSIFIER, FLAW_TYPE_SELECTOR
from llm.structured import _extract_json_blob
from schemas.documents import CTDSection, IntermediateReport

log = structlog.get_logger()

# CTD-section detection lives here (a detection-layer concern); the parse pipeline no
# longer classifies documents.
_CTD_PATTERNS: list[tuple[re.Pattern, CTDSection]] = [
    (re.compile(r"3\.2\.\s*S\.4\.1\b", re.IGNORECASE), CTDSection.S_4_1_SPECIFICATION),
    (re.compile(r"3\.2\.\s*S\.4\.2\b", re.IGNORECASE), CTDSection.S_4_2_ANALYTICAL_PROCEDURES),
    (re.compile(r"3\.2\.\s*S\.4\.3\b", re.IGNORECASE), CTDSection.S_4_3_VALIDATION),
    (re.compile(r"3\.2\.\s*S\.4\.4\b", re.IGNORECASE), CTDSection.S_4_4_BATCH_ANALYSES),
    (re.compile(r"3\.2\.\s*S\.4\.5\b", re.IGNORECASE), CTDSection.S_4_5_JUSTIFICATION),
    (re.compile(r"3\.2\.\s*S\.1\b", re.IGNORECASE), CTDSection.S_1_GENERAL),
    (re.compile(r"3\.2\.\s*S\.2\b", re.IGNORECASE), CTDSection.S_2_MANUFACTURE),
    (re.compile(r"3\.2\.\s*S\.3\b", re.IGNORECASE), CTDSection.S_3_CHARACTERIZATION),
    (re.compile(r"3\.2\.\s*S\.5\b", re.IGNORECASE), CTDSection.S_5_REFERENCE_STANDARDS),
    (re.compile(r"3\.2\.\s*S\.6\b", re.IGNORECASE), CTDSection.S_6_CONTAINER_CLOSURE),
    (re.compile(r"3\.2\.\s*S\.7\b", re.IGNORECASE), CTDSection.S_7_STABILITY),
    (re.compile(r"3\.2\.\s*P\.4\.1\b", re.IGNORECASE), CTDSection.P_4_1_SPECIFICATION),
    (re.compile(r"3\.2\.\s*P\.4\.2\b", re.IGNORECASE), CTDSection.P_4_2_ANALYTICAL_PROCEDURES),
    (re.compile(r"3\.2\.\s*P\.4\.3\b", re.IGNORECASE), CTDSection.P_4_3_VALIDATION),
    (re.compile(r"3\.2\.\s*P\.4\.4\b", re.IGNORECASE), CTDSection.P_4_4_BATCH_ANALYSES),
    (re.compile(r"3\.2\.\s*P\.4\.5\b", re.IGNORECASE), CTDSection.P_4_5_JUSTIFICATION),
    (re.compile(r"3\.2\.\s*P\.1\b", re.IGNORECASE), CTDSection.P_1_DESCRIPTION),
    (re.compile(r"3\.2\.\s*P\.2\b", re.IGNORECASE), CTDSection.P_2_DEVELOPMENT),
    (re.compile(r"3\.2\.\s*P\.3\b", re.IGNORECASE), CTDSection.P_3_MANUFACTURE),
    (re.compile(r"3\.2\.\s*P\.5\b", re.IGNORECASE), CTDSection.P_5_REFERENCE_STANDARDS),
    (re.compile(r"3\.2\.\s*P\.6\b", re.IGNORECASE), CTDSection.P_6_CONTAINER_CLOSURE),
    (re.compile(r"3\.2\.\s*P\.7\b", re.IGNORECASE), CTDSection.P_7_STABILITY),
    (re.compile(r"3\.2\.\s*P\.8\b", re.IGNORECASE), CTDSection.P_8_APPENDICES),
    (re.compile(r"3\.2\.\s*A\.1\b", re.IGNORECASE), CTDSection.A_FACILITIES),
    (re.compile(r"3\.2\.\s*A\.2\b", re.IGNORECASE), CTDSection.A_ADVENTITIOUS),
    (re.compile(r"3\.2\.\s*R\b", re.IGNORECASE), CTDSection.R_REGIONAL),
]


def detect_ctd_section(text: str) -> CTDSection:
    for pattern, section in _CTD_PATTERNS:
        if pattern.search(text):
            return section
    return CTDSection.UNKNOWN


def classify_document_type(text_excerpt: str) -> tuple[CTDSection, str]:
    rule_based = detect_ctd_section(text_excerpt)
    if rule_based != CTDSection.UNKNOWN:
        return rule_based, section_label(rule_based)

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


def _clean_selection(selected: object) -> list[str]:
    """Drop only structurally unusable entries from the LLM's picks, preserving order.

    FLAW_TYPE_SELECTOR invites categories outside the catalog, so a name absent from
    FLAW_TYPE_DEFINITIONS is a valid answer — make_flaw_agent falls back to the raw
    name. Duplicates go because SelectorGroupChat participants must be uniquely named.
    """
    if not isinstance(selected, list):
        return []

    cleaned: list[str] = []
    for entry in selected:
        if not isinstance(entry, str):
            continue
        name = entry.strip()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


def select_flaw_types(report: IntermediateReport, job_id: str = "") -> list[str]:
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

    cleaned = _clean_selection(selected)
    if cleaned:
        return cleaned

    # An unusable selection means every specialist looks. Picking a dict-ordered
    # subset would be this module inventing routing the LLM declined to supply.
    fallback = list(FLAW_TYPE_DEFINITIONS.keys())
    log.warning(
        "flaw_type_selection_fallback",
        response=response[:200],
        count=len(fallback),
    )
    if job_id:
        emit_sync(
            job_id, "detection", "parse_repair", "",
            f"Flaw category selection unusable — checking all {len(fallback)} categories",
        )
    return fallback


def describe_document(section: CTDSection) -> str:
    """Name the document in words the model can reason about.

    A bare "3.2.S.4.1" in the report JSON is a code an 8B does not reliably decode,
    which leaves the scope guard in FLAW_DETECTION_AGENT unable to fire — it cannot
    judge what "does not matter for this document" without knowing what the document
    is. Substance/product follows from CTD numbering, not from any requirement. This
    states what the document IS; it never states what belongs in it.
    """
    if section is CTDSection.UNKNOWN:
        return "unidentified CTD section"
    if section.value.startswith("3.2.S"):
        subject = "drug substance"
    elif section.value.startswith("3.2.P"):
        subject = "drug product"
    else:
        subject = "regional or appendix material"
    return f"{section.value} — {section_label(section)} ({subject})"


def section_label(section: CTDSection) -> str:
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
