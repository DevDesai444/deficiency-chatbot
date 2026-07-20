from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import fitz
import structlog
from parse.ocr import is_scanned_page, ocr_page
from schemas.documents import ExtractedTable

log = structlog.get_logger()

@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[ExtractedTable] = field(default_factory=list)

@dataclass
class PDFDocument:
    filename: str
    page_count: int
    toc: list[tuple[int, str, int]]
    pages: list[PageContent]

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
            )
        )
    return results


def extract_pdf(path: str | Path) -> PDFDocument:
    path = Path(path)
    doc = fitz.open(str(path))

    toc = [(level, title, page_num) for level, title, page_num in doc.get_toc()]

    pages: list[PageContent] = []
    ocr_count = 0
    for page in doc:
        tables = extract_tables(page)
        if is_scanned_page(page):
            ocr_result = ocr_page(page)
            if ocr_result is not None:
                text, ocr_tables = ocr_result
                # find_tables() finds nothing on a scan (the grid lines are pixels,
                # not vectors), so these reconstructed tables are all this page has.
                tables = tables + ocr_tables
                ocr_count += 1
            else:
                text = page.get_text("text")
        else:
            text = page.get_text("text")
        pages.append(
            PageContent(
                page_number=page.number + 1,
                text=text,
                tables=tables,
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
