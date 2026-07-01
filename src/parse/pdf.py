from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz

from schemas.documents import ExtractedTable


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
    for page in doc:
        text = page.get_text("text")
        tables = extract_tables(page)
        pages.append(
            PageContent(
                page_number=page.number + 1,
                text=text,
                tables=tables,
            )
        )

    result = PDFDocument(
        filename=path.name,
        page_count=len(doc),
        toc=toc,
        pages=pages,
    )
    doc.close()
    return result
