"""Cut a parsed document into CTD sections from its structured layout.

The parser hands us pages of geometry-aware blocks (paragraphs that keep their lines),
tables, and figures. This module decides section boundaries from that structure rather
than by regex on flattened text, which is what let data rows like "6920.93 Intercept"
masquerade as headings.

Heading detection is a fallback chain:
  1. TOC anchor -- if the PDF has a bookmark outline, match each numbered section entry
     to its heading block. Strongest and free.
  2. Geometry + numbering -- otherwise, a block is a heading only if it is short/isolated
     and its number fits a real section scheme (so "6920.93" is rejected).

Tables and figures attach to whichever section their position falls in, and grid tables
that continue across a page break are stitched back into one.
"""
from __future__ import annotations

import re

from parse.pdf import PDFDocument
from schemas.documents import (
    ChunkGroup,
    CTDSection,
    ExtractedTable,
    LayoutBlock,
    LayoutFigure,
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


def _detect_from_headers(pages, sample_pages: int = 5) -> CTDSection:
    """Scan running headers of first few pages for CTD section."""
    for page in pages[:sample_pages]:
        section = detect_ctd_section(page.text[:500])
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

    return detect_ctd_section(doc.filename)


# --- heading detection -------------------------------------------------------
# A section number, optionally followed by a trailing dot, then the title. The
# optional "\.?" accepts the common "1. Purpose" / "3.1. Scope" heading style.
_TOC_SECTION_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+)")
_DATA_ROW_RE = re.compile(r"^[\d\.\-\+\s×xX%μµ]")


def _toc_section_entries(toc: list[tuple[int, str, int]]) -> list[tuple[str, str, int]]:
    """TOC entries that are numbered sections ("1.4.2 Linearity"), not Table/Figure lists."""
    entries = []
    for _level, title, page in toc:
        match = _TOC_SECTION_RE.match(title)
        if match:
            entries.append((match.group(1), match.group(2).strip(), page))
    return entries


def _match_heading_block(by_page: dict[int, list[tuple[int, LayoutBlock]]], num: str, page: int) -> int | None:
    """Find the body-block index whose text begins with this section number, near `page`."""
    pat = re.compile(r"^\s*" + re.escape(num) + r"\.?(?![\d.])")
    for candidate_page in (page, page + 1, page - 1):
        for idx, block in by_page.get(candidate_page, []):
            if pat.match(block.text):
                return idx
    return None


def _toc_anchors(doc: PDFDocument, body_blocks: list[LayoutBlock]) -> list[tuple[int, str, str]]:
    entries = _toc_section_entries(doc.toc)
    if not entries:
        return []

    by_page: dict[int, list[tuple[int, LayoutBlock]]] = {}
    for idx, block in enumerate(body_blocks):
        by_page.setdefault(block.page, []).append((idx, block))

    anchors: list[tuple[int, str, str]] = []
    seen_num: set[str] = set()
    seen_idx: set[int] = set()
    for num, title, page in entries:
        if num in seen_num:
            continue
        idx = _match_heading_block(by_page, num, page)
        if idx is not None and idx not in seen_idx:
            anchors.append((idx, num, title))
            seen_num.add(num)
            seen_idx.add(idx)
    anchors.sort(key=lambda a: a[0])
    return anchors


def _plausible_section_number(num: str) -> bool:
    parts = num.split(".")
    if not 1 <= len(parts) <= 4:
        return False
    for part in parts:
        if not part.isdigit() or int(part) > 50:
            return False  # 6920.93 / 281.39 are data, not section numbers
    return True


def _geometry_headings(body_blocks: list[LayoutBlock]) -> list[tuple[int, str, str]]:
    """Fallback when there is no usable TOC: numbering + geometry, rejecting data rows."""
    headings: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for idx, block in enumerate(body_blocks):
        if len(block.text) > 120 or len(block.lines) > 2:
            continue  # a heading is short and not a wrapped paragraph
        match = _TOC_SECTION_RE.match(block.text)
        if not match:
            continue
        num, title = match.group(1), match.group(2).strip()
        if not _plausible_section_number(num) or num in seen:
            continue
        if _DATA_ROW_RE.match(title) or not any(c.isalpha() for c in title):
            continue
        first_alpha = next((c for c in title if c.isalpha()), "")
        if first_alpha and not first_alpha.isupper():
            continue
        seen.add(num)
        headings.append((idx, num, title))
    return headings


def _find_headings(doc: PDFDocument, body_blocks: list[LayoutBlock]) -> list[tuple[int, str, str]]:
    anchors = _toc_anchors(doc, body_blocks)
    if len(anchors) >= 2:
        return anchors
    return _geometry_headings(body_blocks)


# --- cross-page table stitching ----------------------------------------------
def _norm_row(cells: list[str]) -> list[str]:
    return [c.strip().lower() for c in cells]


def _can_stitch(a: ExtractedTable, last_page: int, last_bbox, b: ExtractedTable, page_heights: dict[int, float]) -> bool:
    """Whether grid `b` continues `a`, checked against a's LAST fragment (page/bbox).

    Using the last fragment (not a.bbox, which stays at the first fragment for section
    positioning) keeps the bottom-of-page and column-alignment checks correct across a
    3rd+ page.
    """
    if a.kind != "grid" or b.kind != "grid" or not last_bbox or not b.bbox:
        return False
    if b.page != last_page + 1 or b.title:
        return False
    if a.n_cols == 0 or a.n_cols != b.n_cols:
        return False
    if abs(last_bbox[0] - b.bbox[0]) > 20 or abs(last_bbox[2] - b.bbox[2]) > 20:
        return False  # columns must line up
    top_height = page_heights.get(last_page, 0.0)
    if top_height and last_bbox[3] < top_height * 0.80:
        return False  # the last fragment must reach the bottom of its page
    bottom_height = page_heights.get(b.page, 0.0)
    if bottom_height and b.bbox[1] > bottom_height * 0.30:
        return False  # b must start at the top of its page
    return True


def _merge_tables(a: ExtractedTable, b: ExtractedTable) -> None:
    if b.headers and a.headers and _norm_row(b.headers) == _norm_row(a.headers):
        add_rows = b.rows  # B repeated the header -> drop the duplicate
    else:
        add_rows = ([b.headers] if b.headers else []) + b.rows  # B's first row is data
    a.rows.extend(add_rows)
    a.source_pages = list(a.source_pages) + list(b.source_pages or [b.page])
    a.continues_to = True
    a.n_rows = len(a.rows) + 1


def _stitch_cross_page_tables(tables: list[ExtractedTable], page_heights: dict[int, float]) -> list[ExtractedTable]:
    ordered = sorted(tables, key=lambda t: (t.page, t.bbox[1] if t.bbox else 0.0))
    result: list[ExtractedTable] = []
    last_frag: list[tuple[int, tuple | None]] = []  # (page, bbox) of the newest fragment merged
    for table in ordered:
        if result and _can_stitch(result[-1], last_frag[-1][0], last_frag[-1][1], table, page_heights):
            _merge_tables(result[-1], table)
            last_frag[-1] = (table.page, table.bbox)
        else:
            result.append(table)
            last_frag.append((table.page, table.bbox))
    return result


# --- assembly ----------------------------------------------------------------
def _kept_pages(doc: PDFDocument) -> set[int]:
    """Drop the cover/approval page 1, unless the document is tiny."""
    if doc.page_count <= 2:
        return {p.page_number for p in doc.pages}
    return {p.page_number for p in doc.pages if p.page_number > 1}


def _position(page: int, bbox) -> tuple[int, float]:
    return (page, bbox[1] if bbox else 0.0)


def _build_section(
    ctd: CTDSection,
    heading: str,
    blocks: list[LayoutBlock],
) -> ParsedSection:
    text = "\n".join(b.text for b in blocks if b.text)
    pages = [b.page for b in blocks]
    return ParsedSection(
        section_id=ctd,
        heading=heading,
        text=text,
        blocks=list(blocks),
        page_start=min(pages) if pages else 0,
        page_end=max(pages) if pages else 0,
    )


def _assign_items(items, section_starts: list[tuple[tuple[int, float], ParsedSection]], attr: str) -> None:
    """Attach each table/figure to the last section that starts at or before its position."""
    for item in items:
        pos = _position(item.page, getattr(item, "bbox", None))
        target = section_starts[0][1]
        for start_pos, section in section_starts:
            if start_pos <= pos:
                target = section
            else:
                break
        getattr(target, attr).append(item)


def split_document(doc: PDFDocument) -> list[ParsedSection]:
    ctd = classify_document(doc)
    kept = _kept_pages(doc)

    body_blocks = [
        b
        for page in doc.pages
        if page.page_number in kept
        for b in page.blocks
        if b.role not in ("page_header", "page_footer")
    ]
    body_blocks.sort(key=lambda b: (b.page, b.reading_order))

    page_heights = {p.page_number: p.height for p in doc.pages}
    tables = [t for page in doc.pages if page.page_number in kept for t in page.tables]
    figures = [f for page in doc.pages if page.page_number in kept for f in page.figures]
    tables = _stitch_cross_page_tables(tables, page_heights)

    if not body_blocks:
        # A document with no prose (e.g. tables/figures only) must still surface them.
        if not (tables or figures):
            return []
        section = ParsedSection(section_id=ctd, heading=ctd.value)
        section.tables = list(tables)
        section.figures = list(figures)
        item_pages = [t.page for t in tables] + [f.page for f in figures]
        section.page_start = min(item_pages) if item_pages else 0
        section.page_end = max(item_pages) if item_pages else 0
        return [section]

    headings = _find_headings(doc, body_blocks)
    if not headings:
        section = _build_section(ctd, ctd.value, body_blocks)
        _assign_items(tables, [(_position(body_blocks[0].page, body_blocks[0].bbox), section)], "tables")
        _assign_items(figures, [(_position(body_blocks[0].page, body_blocks[0].bbox), section)], "figures")
        return [section]

    sections: list[ParsedSection] = []
    section_starts: list[tuple[tuple[int, float], ParsedSection]] = []

    first_idx = headings[0][0]
    preamble = body_blocks[:first_idx]
    if sum(len(b.text) for b in preamble) > 200:
        pre_section = _build_section(ctd, f"{ctd.value} Main Specification", preamble)
        sections.append(pre_section)
        section_starts.append((_position(preamble[0].page, preamble[0].bbox), pre_section))

    for i, (start, num, title) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(body_blocks)
        sec_blocks = body_blocks[start:end]
        section = _build_section(ctd, f"{num} {title}", sec_blocks)
        sections.append(section)
        section_starts.append((_position(sec_blocks[0].page, sec_blocks[0].bbox), section))

    _assign_items(tables, section_starts, "tables")
    _assign_items(figures, section_starts, "figures")
    return sections


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
