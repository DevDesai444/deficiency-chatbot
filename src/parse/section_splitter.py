from __future__ import annotations

import re

from parse.pdf import PageContent, PDFDocument
from schemas.documents import (
    ChunkGroup,
    CTDSection,
    ExtractedTable,
    ParsedSection,
)

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
    (re.compile(r"3\.2\.\s*P\.1\b", re.IGNORECASE), CTDSection.P_1_DESCRIPTION),
    (re.compile(r"3\.2\.\s*P\.2\b", re.IGNORECASE), CTDSection.P_2_DEVELOPMENT),
    (re.compile(r"3\.2\.\s*P\.3\b", re.IGNORECASE), CTDSection.P_3_MANUFACTURE),
    (re.compile(r"3\.2\.\s*P\.4\.1\b", re.IGNORECASE), CTDSection.P_4_1_SPECIFICATION),
    (re.compile(r"3\.2\.\s*P\.4\.2\b", re.IGNORECASE), CTDSection.P_4_2_ANALYTICAL_PROCEDURES),
    (re.compile(r"3\.2\.\s*P\.4\.3\b", re.IGNORECASE), CTDSection.P_4_3_VALIDATION),
    (re.compile(r"3\.2\.\s*P\.4\.4\b", re.IGNORECASE), CTDSection.P_4_4_BATCH_ANALYSES),
    (re.compile(r"3\.2\.\s*P\.4\.5\b", re.IGNORECASE), CTDSection.P_4_5_JUSTIFICATION),
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


def _detect_from_toc(toc: list[tuple[int, str, int]]) -> CTDSection:
    for _level, title, _page in toc:
        section = detect_ctd_section(title)
        if section != CTDSection.UNKNOWN:
            return section
    return CTDSection.UNKNOWN


def _detect_from_headers(pages: list[PageContent], sample_pages: int = 5) -> CTDSection:
    """Scan running headers of first few pages for CTD section."""
    for page in pages[:sample_pages]:
        first_lines = page.text[:500]
        section = detect_ctd_section(first_lines)
        if section != CTDSection.UNKNOWN:
            return section
    return CTDSection.UNKNOWN


def classify_document(doc: PDFDocument) -> CTDSection:
    section = _detect_from_toc(doc.toc)
    if section != CTDSection.UNKNOWN:
        return section

    section = _detect_from_headers(doc.pages)
    if section != CTDSection.UNKNOWN:
        return section

    section = detect_ctd_section(doc.filename)
    return section


_INTERNAL_SECTION_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)*)\s+(.+)",
    re.MULTILINE,
)


def _split_by_internal_sections(
    pages: list[PageContent],
    ctd_section: CTDSection,
) -> list[ParsedSection]:
    """Split document body into internal numbered sections (1.x.x style)."""
    full_text = "\n".join(p.text for p in pages)

    all_tables: list[ExtractedTable] = []
    for p in pages:
        all_tables.extend(p.tables)

    headings: list[tuple[int, str, str]] = []
    for match in _INTERNAL_SECTION_RE.finditer(full_text):
        num = match.group(1)
        title = match.group(2).strip()
        if len(num.split(".")) <= 4 and len(title) < 150:
            headings.append((match.start(), num, title))

    if not headings:
        return [
            ParsedSection(
                section_id=ctd_section,
                heading=ctd_section.value,
                text=full_text,
                tables=all_tables,
                page_start=pages[0].page_number if pages else 0,
                page_end=pages[-1].page_number if pages else 0,
            )
        ]

    sections: list[ParsedSection] = []
    for i, (start_pos, num, title) in enumerate(headings):
        end_pos = headings[i + 1][0] if i + 1 < len(headings) else len(full_text)
        section_text = full_text[start_pos:end_pos].strip()

        section_tables = [
            t for t in all_tables
            if title.lower() in (t.title or "").lower()
            or num in (t.title or "")
        ]

        sections.append(
            ParsedSection(
                section_id=ctd_section,
                heading=f"{num} {title}",
                text=section_text,
                tables=section_tables,
                page_start=pages[0].page_number,
                page_end=pages[-1].page_number,
            )
        )

    leftover_tables = [t for t in all_tables if not any(t in s.tables for s in sections)]
    if leftover_tables and sections:
        sections[-1].tables.extend(leftover_tables)

    return sections


def _skip_cover_and_history(pages: list[PageContent]) -> list[PageContent]:
    """Heuristic: skip page 1 (cover/approval) and last pages if they look like change history."""
    if len(pages) <= 2:
        return pages

    body = pages[1:]

    while len(body) > 1:
        last_text = body[-1].text.lower()
        if any(kw in last_text for kw in ["change history", "revision history", "version history"]):
            body = body[:-1]
        else:
            break

    return body


def split_document(doc: PDFDocument) -> list[ParsedSection]:
    ctd_section = classify_document(doc)
    body_pages = _skip_cover_and_history(doc.pages)
    return _split_by_internal_sections(body_pages, ctd_section)


def group_sections(
    sections: list[ParsedSection],
    max_sections_per_group: int = 5,
) -> list[ChunkGroup]:
    groups: list[ChunkGroup] = []
    for i in range(0, len(sections), max_sections_per_group):
        batch = sections[i : i + max_sections_per_group]
        groups.append(
            ChunkGroup(
                group_id=f"group_{i // max_sections_per_group}",
                sections=batch,
            )
        )
    return groups
