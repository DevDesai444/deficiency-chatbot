"""Reading-order document serializer -- the format-neutral substrate primitive (D-31).

`blocks_to_text` (parse/layout.py:452) and `_reading_order_text` (detection/checklists.py:48)
both flatten a document into reading-order text and THROW the offsets away. The span-anchor
substrate needs those offsets: this serializer produces the SAME reading-order raw stream AND
records, for every table's origin cell, the exact char range its text occupies -- so Plan 06
can mint a span-ID for each addressable cell (INGEST-05).

The stream is RAW (pre-normalization). Plan 03's normalizer consumes it; Plan 06 converts
these raw cell ranges to canonical ranges via `normalize.raw_range_to_canon`.

Determinism (D-31): the same document dict always serializes to byte-identical text and an
identical cell-range map. `SERIALIZER_VERSION` stamps the scheme; bumping it MUST invalidate
the on-disk cache (Plan 07), because every stored offset is defined relative to this ordering.
"""
from __future__ import annotations

# Reading-order flatten: pages by page_number, blocks by reading_order (headers/footers
# dropped), then tables row-major with covered merged coords skipped. Cells within a row
# join with "\t", every other unit with "\n"; ranges cover cell text only, never separators.
# Bump ONLY when this ordering/separator scheme changes -- it invalidates every cached offset.
SERIALIZER_VERSION = "reading-order-cells/1"

_DROP_ROLES = ("page_header", "page_footer")


def serialize_document(doc: dict) -> tuple[str, dict[str, list[int]]]:
    """Flatten `doc` (an extract_pdf/extract_docx dict) to raw reading-order text + cell ranges.

    Returns `(raw_serialized_text, cell_ranges)` where `cell_ranges` maps
    `"{table_index},{row},{col}"` (over the grid: row 0 = headers, rows 1.. = rows) to
    `[start, end]`, the char span of that ORIGIN cell's text in the raw stream. A covered
    (non-origin) merged coordinate -- a key in the table's `merged_origins` -- is skipped:
    its text was already emitted at the origin, so it gets no range and is not duplicated.
    """
    pieces: list[str] = []
    cell_ranges: dict[str, list[int]] = {}
    pos = 0
    first = True

    def append(text: str) -> tuple[int, int]:
        nonlocal pos
        start = pos
        pieces.append(text)
        pos += len(text)
        return start, pos

    def sep(s: str) -> None:
        nonlocal pos
        pieces.append(s)
        pos += len(s)

    table_index = 0
    for page in sorted(doc.get("pages", []), key=lambda p: p.get("page_number", 0)):
        blocks = [b for b in page.get("blocks", []) if b.get("role") not in _DROP_ROLES]
        for block in sorted(blocks, key=lambda b: b.get("reading_order", 0)):
            text = block.get("text") or ""
            if not first:
                sep("\n")
            first = False
            append(text)

        for table in page.get("tables", []):
            merged = table.get("merged_origins", {}) or {}
            grid = [list(table.get("headers", []))] + [list(r) for r in (table.get("rows") or [])]

            title = table.get("title") or ""
            if title:
                if not first:
                    sep("\n")
                first = False
                append(title)

            for r, row in enumerate(grid):
                row_started = False
                for c, cell in enumerate(row):
                    if f"{r},{c}" in merged:
                        continue  # covered coord -- origin already emitted (D-31), no duplicate
                    if not first and not row_started:
                        sep("\n")   # new row: separate from the previous unit
                    elif row_started:
                        sep("\t")   # within-row cells: tab-separated (mirror blocks_to_text)
                    first = False
                    row_started = True
                    start, end = append(str(cell if cell is not None else ""))
                    cell_ranges[f"{table_index},{r},{c}"] = [start, end]
            table_index += 1

    return "".join(pieces), cell_ranges
