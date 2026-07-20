"""Rebuild page layout from RapidOCR word/line boxes.

RapidOCR returns one region per detected piece of text, each with a bounding box.
The serving endpoint used to throw the boxes away and join the texts with newlines,
which destroyed two things that matter for CMC documents:

  * spaces between words on the same visual line (tokens got fused), and
  * table structure -- every cell landed on its own line, empty cells vanished, and
    the surviving numbers silently shifted into the wrong columns.

This module takes the boxes back and reconstructs, using only geometry, so it works
for any document layout:

  1. group regions that share a horizontal band into lines (restores reading order
     and the spaces between words),
  2. find runs of "row-like" lines and rebuild them into tables by clustering the
     cell x-positions into columns -- a missing cell just leaves its column blank
     instead of shifting its neighbours over.

Every threshold is expressed in units of the median text height, so the logic is
independent of the render resolution (DPI) of the page image.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from schemas.documents import ExtractedTable

# All thresholds below are multiples of the median text height ("unit"), never raw
# pixels, so they hold at any DPI.
_LINE_OVERLAP = 0.4     # regions sharing >= this fraction of vertical overlap are one line
_COL_GAP = 1.6          # cell centres more than this*unit apart belong to different columns
_ROW_MIN_CELLS = 3      # a line with at least this many regions looks like a table row
_MIN_TABLE_COLS = 3     # a table needs at least this many columns...
_MIN_TABLE_ROWS = 2     # ...and at least this many rows
_MAX_TITLE_LEN = 200    # a preceding prose line this short becomes the table's title


@dataclass
class OCRRegion:
    """One piece of text RapidOCR recognized, with its axis-aligned bounding box."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float = 1.0

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def y_center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return max(1.0, self.y1 - self.y0)


@dataclass
class _Line:
    """A group of regions that share one horizontal band, left-to-right."""
    y0: float
    y1: float
    regions: list[OCRRegion]

    def text(self) -> str:
        return " ".join(r.text for r in self.regions if r.text).strip()


def _unit(regions: list[OCRRegion]) -> float:
    """The scale of the page: the median text height."""
    heights = [r.height for r in regions]
    return median(heights) if heights else 1.0


def _group_into_lines(regions: list[OCRRegion]) -> list[_Line]:
    """Cluster regions into visual lines by vertical overlap.

    Regions are visited top-to-bottom; each either extends the current line (if it
    overlaps it vertically) or starts a new one. Sorting by vertical centre keeps all
    of one line's cells adjacent, so comparing against the last line is enough.
    """
    ordered = sorted(regions, key=lambda r: (r.y_center, r.x0))
    lines: list[_Line] = []
    for r in ordered:
        line = lines[-1] if lines else None
        if line is not None:
            overlap = min(r.y1, line.y1) - max(r.y0, line.y0)
            unit = min(r.height, line.y1 - line.y0)
            same_line = unit > 0 and overlap / unit >= _LINE_OVERLAP
        else:
            same_line = False

        if same_line:
            line.regions.append(r)
            line.y0 = min(line.y0, r.y0)
            line.y1 = max(line.y1, r.y1)
        else:
            lines.append(_Line(y0=r.y0, y1=r.y1, regions=[r]))

    for line in lines:
        line.regions.sort(key=lambda r: r.x0)
    return lines


def _cluster_columns(regions: list[OCRRegion], unit: float) -> list[float]:
    """Find column centres by clustering cell x-centres with a gap threshold."""
    centers = sorted(r.x_center for r in regions)
    clusters: list[list[float]] = [[centers[0]]]
    for c in centers[1:]:
        if c - clusters[-1][-1] > _COL_GAP * unit:
            clusters.append([c])
        else:
            clusters[-1].append(c)
    return [sum(group) / len(group) for group in clusters]


def _build_grid(block: list[_Line], unit: float) -> list[list[str]] | None:
    """Turn a run of row-like lines into a rectangular grid, or None if it is not a table.

    Each region is dropped into the nearest column by its x-centre. A row that is
    missing a cell simply leaves that column empty -- nothing shifts over.
    """
    all_regions = [r for line in block for r in line.regions]
    col_centers = _cluster_columns(all_regions, unit)
    if len(col_centers) < _MIN_TABLE_COLS:
        return None

    grid: list[list[str]] = []
    for line in block:
        cells = [""] * len(col_centers)
        for r in line.regions:
            col = min(range(len(col_centers)), key=lambda i: abs(col_centers[i] - r.x_center))
            cells[col] = (cells[col] + " " + r.text).strip() if cells[col] else r.text
        grid.append(cells)
    return grid


def reconstruct_page(regions: list[OCRRegion], page_number: int = 0) -> tuple[str, list[ExtractedTable]]:
    """Rebuild readable text and structured tables from OCR regions.

    Returns the page text in reading order (table rows rendered as tab-separated
    cells so columns stay aligned) and a list of the tables detected on the page.
    """
    regions = [r for r in regions if r.text and r.text.strip()]
    if not regions:
        return "", []

    unit = _unit(regions)
    lines = _group_into_lines(regions)

    tables: list[ExtractedTable] = []
    text_parts: list[str] = []
    last_prose = ""
    i = 0
    while i < len(lines):
        # A table is a run of consecutive lines that each look like a row.
        if len(lines[i].regions) >= _ROW_MIN_CELLS:
            j = i
            while j < len(lines) and len(lines[j].regions) >= _ROW_MIN_CELLS:
                j += 1
            block = lines[i:j]
            grid = _build_grid(block, unit) if len(block) >= _MIN_TABLE_ROWS else None
            if grid is not None:
                title = last_prose if len(last_prose) <= _MAX_TITLE_LEN else ""
                tables.append(
                    ExtractedTable(
                        title=title,
                        headers=grid[0],
                        rows=grid[1:],
                        page=page_number,
                    )
                )
                for row in grid:
                    text_parts.append("\t".join(row).rstrip())
                last_prose = ""
                i = j
                continue
            # Row-like but not a real table -> keep the lines as prose.
            for line in block:
                text_parts.append(line.text())
            last_prose = block[-1].text()
            i = j
            continue

        line_text = lines[i].text()
        text_parts.append(line_text)
        if line_text:
            last_prose = line_text
        i += 1

    text = "\n".join(text_parts)
    return text, tables
