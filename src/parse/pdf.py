from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz
import structlog

from parse.layout import RawLine, group_lines_into_blocks, mark_header_footer
from parse.ocr import is_scanned_page, ocr_page
from schemas.documents import ExtractedTable, LayoutBlock, LayoutFigure

log = structlog.get_logger()

# An image covering less than this fraction of the page is a logo, not a figure.
_MIN_FIGURE_COVERAGE = 0.03
_PAGE_LABEL_RE = re.compile(r"page\s+(\d+)\s+of\s+\d+", re.IGNORECASE)
_CAPTION_RE = re.compile(r"\b(figure|appendix|table)\b", re.IGNORECASE)


@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[ExtractedTable] = field(default_factory=list)
    blocks: list[LayoutBlock] = field(default_factory=list)
    figures: list[LayoutFigure] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    rotation: int = 0
    source: str = "pymupdf"       # "pymupdf" | "rapidocr" | "rapidocr-fallback"
    is_scanned: bool = False
    page_label: str = ""          # the printed "Page X of Y" label, if present


@dataclass
class PDFDocument:
    filename: str
    page_count: int
    toc: list[tuple[int, str, int]]
    pages: list[PageContent]


def _rotated_bbox(bbox, page: fitz.Page) -> tuple[float, float, float, float]:
    """Map an unrotated PyMuPDF bbox into the page's displayed (rotated) space.

    get_text/find_tables/get_image_info return unrotated coordinates, but page.rect and
    the OCR path (get_pixmap) are in displayed space. Converting here keeps all geometry
    in one coordinate system. A no-op when the page is not rotated.
    """
    if page.rotation == 0:
        return tuple(bbox)
    rect = fitz.Rect(bbox) * page.rotation_matrix
    rect.normalize()
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def extract_tables(page: fitz.Page) -> list[ExtractedTable]:
    results: list[ExtractedTable] = []
    finder = page.find_tables()
    for table in finder.tables:
        raw = table.extract()
        if not raw or len(raw) < 2:
            continue

        headers = [str(cell or "").strip() for cell in raw[0]]
        rows = [
            [str(cell or "").strip() for cell in row]
            for row in raw[1:]
        ]

        title = ""
        bbox = table.bbox
        above_rect = fitz.Rect(bbox[0], max(0, bbox[1] - 30), bbox[2], bbox[1])
        above_text = page.get_text("text", clip=above_rect).strip()
        if above_text and len(above_text) < 200:
            title = above_text

        results.append(
            ExtractedTable(
                title=title,
                headers=headers,
                rows=rows,
                page=page.number + 1,
                kind="grid",
                bbox=_rotated_bbox(bbox, page),
                n_cols=len(headers),
                n_rows=len(rows) + 1,
                source_pages=[page.number + 1],
                confidence=1.0,
            )
        )
    return results


def _join_spans(spans: list[dict]) -> str:
    """Join a line's spans, inserting a space where they are visually separated.

    PyMuPDF splits a line into style runs; "1.4.2" and "Linearity" (different fonts) are
    two spans with a gap between them and no space of their own, so a naive join fuses
    them. Insert a space when spans don't touch.
    """
    parts: list[str] = []
    prev_x1 = None
    for sp in spans:
        text = sp.get("text", "")
        if not text:
            continue
        x0 = sp["bbox"][0]
        if prev_x1 is not None and x0 - prev_x1 > 1.0:
            if parts and not parts[-1].endswith(" ") and not text.startswith(" "):
                parts.append(" ")
        parts.append(text)
        prev_x1 = sp["bbox"][2]
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _digital_lines(page: fitz.Page, tables: list[ExtractedTable]) -> list[RawLine]:
    """Build one RawLine per visual line from the embedded text, skipping table content."""
    table_rects = [fitz.Rect(t.bbox) for t in tables if t.bbox]
    lines: list[RawLine] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type", 0) != 0:  # 0 = text, 1 = image
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = _join_spans(spans)
            if not text:
                continue
            bbox = _rotated_bbox(line["bbox"], page)
            center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
            if any(r.contains(fitz.Point(center)) for r in table_rects):
                continue  # this line belongs to a table, not the prose
            main = max(spans, key=lambda sp: len(sp["text"]))
            lines.append(
                RawLine(
                    text=text,
                    bbox=bbox,
                    confidence=1.0,
                    font=str(main.get("font", "")),
                    size=float(main.get("size", 0.0)),
                    bold=bool(int(main.get("flags", 0)) & (1 << 4)),
                )
            )
    return lines


def _digital_blocks(page: fitz.Page, tables: list[ExtractedTable]) -> list[LayoutBlock]:
    blocks = group_lines_into_blocks(_digital_lines(page, tables), page.number + 1)
    return mark_header_footer(blocks, page.rect.height)


def _digital_figures(page: fitz.Page, blocks: list[LayoutBlock]) -> list[LayoutFigure]:
    page_area = abs(page.rect)
    if page_area <= 0:
        return []
    figures: list[LayoutFigure] = []
    for info in page.get_image_info():
        rect = fitz.Rect(info["bbox"])
        if abs(rect) / page_area < _MIN_FIGURE_COVERAGE:
            continue  # a logo, not a figure
        figures.append(
            LayoutFigure(
                bbox=_rotated_bbox(info["bbox"], page),
                page=page.number + 1,
                caption=_nearest_caption_block(blocks, tuple(rect)),
                image_ref=f"xref:{info.get('xref', '')}",
                confidence=1.0,
            )
        )
    return figures


def _nearest_caption_block(blocks: list[LayoutBlock], bbox: tuple[float, float, float, float]) -> str:
    candidates = [b for b in blocks if _CAPTION_RE.search(b.text) and len(b.text) < 200]
    if not candidates:
        return ""
    top, bottom = bbox[1], bbox[3]

    def distance(b: LayoutBlock) -> float:
        by0, by1 = b.bbox[1], b.bbox[3]
        if by1 <= top:
            return top - by1
        if by0 >= bottom:
            return by0 - bottom
        return 0.0

    return min(candidates, key=distance).text.strip()


def _detect_page_label(text: str) -> str:
    match = _PAGE_LABEL_RE.search(text)
    return match.group(1) if match else ""


def extract_pdf(path: str | Path) -> PDFDocument:
    path = Path(path)
    doc = fitz.open(str(path))

    toc = [(level, title, page_num) for level, title, page_num in doc.get_toc()]

    pages: list[PageContent] = []
    ocr_count = 0
    for page in doc:
        tables = extract_tables(page)
        scanned = is_scanned_page(page)
        blocks: list[LayoutBlock] = []
        figures: list[LayoutFigure] = []
        source = "pymupdf"

        if scanned:
            source = "rapidocr"
            ocr_result = ocr_page(page)
            if ocr_result is not None:
                text, ocr_tables, blocks, figures = ocr_result
                # find_tables() finds nothing on a scan (grid lines are pixels, not
                # vectors), so these reconstructed tables are all this page has.
                tables = tables + ocr_tables
                ocr_count += 1
            else:
                source = "rapidocr-fallback"
                text = page.get_text("text")
        else:
            text = page.get_text("text")
            blocks = _digital_blocks(page, tables)
            figures = _digital_figures(page, blocks)

        pages.append(
            PageContent(
                page_number=page.number + 1,
                text=text,
                tables=tables,
                blocks=blocks,
                figures=figures,
                width=page.rect.width,
                height=page.rect.height,
                rotation=page.rotation,
                source=source,
                is_scanned=scanned,
                page_label=_detect_page_label(text),
            )
        )

    if ocr_count:
        log.info("ocr_pages", count=ocr_count, filename=path.name)

    result = PDFDocument(
        filename=path.name,
        page_count=len(doc),
        toc=toc,
        pages=pages,
    )
    doc.close()
    return result
