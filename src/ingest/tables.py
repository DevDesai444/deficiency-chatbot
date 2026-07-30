"""Table-cell addressing: (table_id, row, col) -> canonical span-ID, merged coords sharing one span.

Every reconstructed table cell is addressable two ways (D-31): it is serialized into the canonical
text so it carries an ordinary span-ID, AND it is resolvable through a (table_id,row,col) index.
Every coordinate a merged cell spans resolves to the SAME span-ID (the origin's), so Phase 4's
X1/X2 cell comparisons and Phase 5's "recompute over two verbatim cells" have a substrate.

The serializer (Plan 02) already emitted, for each ORIGIN cell, its RAW char range keyed by the
table's POSITIONAL index. This module converts each raw range to a canonical range (Plan 03
offset map) and mints a span-ID (Plan 06 anchors), then fans merged coverage out to the origin span.

PDF best-effort caveat (Pitfall 4): PyMuPDF's find_tables loses merge metadata, so PDF merged-cell
addressability is best-effort. This module only builds the index it is GIVEN -- it never fabricates
merge info; the caller (Plan 09) marks a PDF table's tier `unavailable`/best-effort in the manifest.
"""
from __future__ import annotations

from schemas.documents import NormalizedText, SpanID

from ingest.anchors import mint_span
from ingest.normalize import raw_range_to_canon


def build_table_index(
    nt: NormalizedText,
    tables: list[dict],
    cell_ranges: dict[str, list[int]],
    doc_id: str,
) -> dict[str, SpanID]:
    """Build the `(table_id,row,col) -> SpanID` index (deterministic, version-stamped, D-31).

    `tables` must be in the SAME order the serializer walked them (its positional index `ti` keys
    `cell_ranges`). Origin cells get a minted canonical span; every covered merged coordinate maps
    to its origin's span so many coordinates resolve to ONE span-ID.
    """
    index: dict[str, SpanID] = {}
    for ti, table in enumerate(tables):
        table_id = table.get("table_id", f"t{ti}")
        # 1. ORIGIN cells: raw serializer range -> canonical range -> minted span-ID.
        prefix = f"{ti},"
        for key, (raw_s, raw_e) in cell_ranges.items():
            if not key.startswith(prefix):
                continue
            _, r, c = key.split(",")
            cs, ce = raw_range_to_canon(nt.offset_map, raw_s, raw_e)
            index[f"{table_id},{r},{c}"] = mint_span(nt.canonical, cs, ce, doc_id, nt.normalizer_version)
        # 2. COVERED merged coords -> the SAME span-ID as their origin (D-31).
        for coord, origin in (table.get("merged_origins") or {}).items():
            r, c = coord.split(",")
            orow, ocol = origin[0], origin[1]
            origin_key = f"{table_id},{orow},{ocol}"
            if origin_key in index:
                index[f"{table_id},{r},{c}"] = index[origin_key]
    return index
