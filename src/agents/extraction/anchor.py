"""Deterministic verification that extracted spans occur in the source.

Anchoring only removes: a span the model invented is dropped, never rewritten.
No judgement about content lives here — only "did the document say this". Nothing
here may compare a value against a limit or know what a value means.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

import structlog

from schemas.documents import ExtractionFindingOut, SectionExtract

log = structlog.get_logger()

# Tolerance for rendering drift on string identity only — never an acceptance criterion.
_NEAR_MATCH_RATIO = 0.92

# Ratio dilution scales with span length, so a long quote carrying one wrong digit
# still clears the threshold. Digits get no tolerance: a drifted letter is noise, a
# drifted digit is a different value.
_DIGIT_RUN_RE = re.compile(r"\d[\d.,]*")

_PUNCT_FOLD = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "−": "-",
}


def normalize(text: str) -> str:
    if not text:
        return ""
    text = "".join(_PUNCT_FOLD.get(c, c) for c in text)
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def section_sources(section: dict) -> list[str]:
    """Every string the model was allowed to quote from, table cells included.

    Rows are contributed both cell-wise and joined: a quantity split across
    adjacent cells ("22.727" | "ug/g") anchors only against the joined form.
    """
    sources = [section.get("text", "")]
    for table in section.get("tables", []):
        sources.append(table.get("title", ""))
        if table.get("kind") == "key_value":
            for pair in table.get("pairs", []):
                label, value = pair.get("label", ""), pair.get("value", "")
                sources.extend([label, value, f"{label} {value}".strip()])
        else:
            headers = table.get("headers", [])
            sources.extend(headers)
            sources.append(" | ".join(headers))
            for row in table.get("rows", []):
                sources.extend(row)
                sources.append(" | ".join(row))
    return [s for s in sources if s]


def is_anchored(span: str, sources: list[str]) -> bool:
    needle = normalize(span)
    if not needle:
        return False
    haystacks = [normalize(s) for s in sources]
    if any(needle in h for h in haystacks):
        return True

    # Every numeric run must survive the exact-substring test above. Fuzzy matching
    # is for rendering drift in prose; it cannot adjudicate a quantity.
    if _DIGIT_RUN_RE.search(needle):
        return False

    # Window the haystack so a length mismatch cannot depress the ratio.
    for haystack in haystacks:
        if not haystack:
            continue
        step = max(len(needle) // 4, 1)
        for i in range(0, max(len(haystack) - len(needle), 0) + 1, step):
            window = haystack[i:i + len(needle)]
            if SequenceMatcher(None, needle, window).ratio() >= _NEAR_MATCH_RATIO:
                return True
    return False


def filter_anchored(
    extract: SectionExtract | None,
    section: dict,
) -> tuple[dict[str, str], list[ExtractionFindingOut], int]:
    """Drop key_values and findings whose quoted span is not in the source.

    Returns (kept_key_values, kept_findings, dropped_count). A finding with empty
    evidence is kept — there is nothing to verify, and dropping it would let
    anchoring suppress observations rather than just unverifiable quotes.
    """
    if extract is None:
        return {}, [], 0

    sources = section_sources(section)
    kept_values: dict[str, str] = {}
    dropped = 0

    for kv in extract.key_values:
        if is_anchored(kv.value, sources):
            kept_values[kv.label] = kv.value
        else:
            dropped += 1

    kept_findings: list[ExtractionFindingOut] = []
    for finding in extract.findings:
        if finding.evidence and not is_anchored(finding.evidence, sources):
            dropped += 1
            continue
        kept_findings.append(finding)

    if dropped:
        log.info(
            "unanchored_dropped",
            heading=section.get("heading", ""),
            count=dropped,
        )
    return kept_values, kept_findings, dropped
