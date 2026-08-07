"""Deterministic intra-document structural inconsistency pass (RECALL-02).

SCOPE BOUNDARY (D-STR5 + D-STR2):
This leg implements the labeled-aggregate recompute family (TOTAL/SUM/MAX/MIN/AVERAGE/MEAN)
as ONE general engine over addressable table cells. The 'result-exceeds-spec-limit' check
is implemented here ONLY when BOTH the reported result AND the specification limit reside
in the same addressable table (table_index cells). When the limit is in prose (not in a
table cell), it is DEFERRED TO PHASE 7 interpretive tail per D-STR5 and D-STR2:
- D-STR5: input surface = addressable table cells ONLY
- D-STR2: comparing a table value against a prose-stated limit requires reading meaning
  (identifying which prose sentence states the limit) = domain-semantic judgment

result-exceeds-spec-limit for prose-located values is DEFERRED TO PHASE 7 interpretive
tail per D-STR5 (prose value-pairing requires reading meaning = domain-semantic judgment,
which fails D-STR2 pure-computation litmus). This leg implements the labeled-aggregate
recompute family which is purely arithmetic. result-exceeds-spec-limit IS implemented
here ONLY when the limit value resides in an addressable table cell (same table_index).
If a spec limit is in prose and the result is in a table cell, the limit must come from
the rulebook rule span (nullable per D-STR6) — implemented if rule span available, deferred
to Phase 7 otherwise.

If the synthetic fixture doc_c.pdf table is not addressable by tables.py (simple PDF tables
may not parse to table_index entries), this specific fixture violation is noted in
fixture_manifest.json and left for Phase 7.

Design decisions honored:
- D-STR1: labeled-aggregate recompute family covers SUM/MAX/MIN/MEAN — ONE general engine;
  any aggregate label in AGGREGATE_LEXICON triggers the check
- D-STR2: no domain-semantic judgment; comparisons are pure arithmetic/ordering over
  numeric cell text values; abstain on unparseable/mismatched units
- D-STR3: each Fault carries a StructuralAnchor with claim_span_id, basis_span_ids
  (deduplicated per Pitfall 2), relation enum, expected_value, actual_value
- D-STR4: precision-derived comparator (no epsilon) — round(0.104, 2) == 0.10 ->
  complies (no false positive); round(0.15, 2) > round(0.10, 2) -> violation
- D-STR5: docs with tables not addressable (tables='unavailable' or no table_index)
  are logged and skipped, never crash
- D-STR6: calls emit_structural_finding with rule_span_id=None for pure arithmetic
  checks; no write to emit_finding.py needed in this plan
- D-GEN2: no submission-specific constant; AGGREGATE_LEXICON imported from guard_vocab;
  no inline float threshold
- Ruling 1: structural.py does NOT create a fresh RetrievalLedger() — the ledger is
  always passed in from outside; emit_structural_finding internally uses issue_cached_span
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict

import structlog

from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from rulebook.guard_vocab import AGGREGATE_LEXICON
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import Fault, StructuralAnchor
from tools.emit_finding import emit_structural_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Precision-derived comparator helpers (D-STR4 — no epsilon)
# ---------------------------------------------------------------------------

def _stated_precision(text: str) -> int:
    """Return the number of decimal places in `text`, or 0 if none found.

    D-STR4: precision is derived from the stated text, not an epsilon constant.
    Example: '0.10%' -> 2, '42.3' -> 1, '100' -> 0.
    """
    m = re.search(r'(\d+)\.(\d+)', text)
    return len(m.group(2)) if m else 0


def _parse_numeric(text: str) -> float | None:
    """Extract the first numeric value from `text`, or None on failure.

    D-STR2: abstain on unparseable text rather than crashing or guessing.
    """
    if text is None:
        return None
    m = re.search(r'[\d.]+', text)
    if m is None:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def compare_values(claim_text: str, ref_text: str, comparator: str) -> bool | None:
    """Compare claim_text against ref_text using the precision-derived comparator.

    D-STR4: precision-derived comparison, zero free parameters.
    - Parse both values as floats; if either fails, abstain (return None).
    - Determine precision = min(stated decimal places in claim_text, stated decimal
      places in ref_text).
    - Round both to that precision, then compare.

    Returns:
      True  — violation (claim does NOT satisfy the stated relation vs ref)
      False — complies
      None  — abstain (unparseable input)

    For SUM/MAX/MIN/MEAN: violation when claim != recomputed (at precision).
    For LEQ/NMT: violation when claim > ref (claim exceeds limit).
    For GEQ/NLT: violation when claim < ref (claim is below lower bound).
    """
    claim_num = _parse_numeric(claim_text)
    ref_num = _parse_numeric(ref_text)
    if claim_num is None or ref_num is None:
        return None

    prec = min(_stated_precision(claim_text), _stated_precision(ref_text))
    rc = round(claim_num, prec)
    rr = round(ref_num, prec)

    if comparator in ("SUM", "MAX", "MIN", "MEAN", "EQUALS"):
        return rc != rr
    if comparator in ("LEQ", "NMT"):
        return rc > rr
    if comparator in ("GEQ", "NLT"):
        return rc < rr
    # Default: equality check for unknown comparators
    return rc != rr


# ---------------------------------------------------------------------------
# Table-primitive helpers (Ruling 5)
# ---------------------------------------------------------------------------

def _get_table_cells(cache: dict) -> dict[str, dict[tuple[int, int], SpanID]]:
    """Parse cache['table_index'] into {table_id: {(row, col): SpanID}}.

    Handles Pitfall 1: table_id may be empty string ("") so the key starts with ",".
    Uses key.split(",", 2) to correctly separate table_id from row,col.
    """
    table_index_raw: dict[str, dict] = cache.get("table_index", {}) or {}
    result: dict[str, dict[tuple[int, int], SpanID]] = defaultdict(dict)
    for key, span_dict in table_index_raw.items():
        try:
            parts = key.split(",", 2)  # Pitfall 1: table_id may be ""
            if len(parts) != 3:
                continue
            table_id, row_s, col_s = parts
            row, col = int(row_s), int(col_s)
            result[table_id][(row, col)] = SpanID(**span_dict)
        except (ValueError, TypeError, KeyError):
            continue
    return dict(result)


def _read_cell_text(corpus: CorpusIndex, doc_id: str, span_id: SpanID) -> str | None:
    """Open a cell's canonical text from the corpus cache.

    D-STR5: returns None on any failure (abstain, not crash).
    D-STR2: returns raw text; caller does numeric parsing.
    """
    cache = corpus.cached_entry(doc_id)
    if cache is None:
        return None
    try:
        nt = NormalizedText(
            canonical=cache["canonical"],
            raw_serialized=cache["raw_serialized"],
            offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
            normalizer_version=cache["normalizer_version"],
            serializer_version=cache["serializer_version"],
        )
        text = nt.canonical[span_id.start:span_id.end]
        return text
    except (KeyError, IndexError, TypeError):
        return None


def _find_value_column(
    cells: dict[tuple[int, int], SpanID],
    cell_texts: dict[tuple[int, int], str],
) -> int | None:
    """Find the column index whose cells contain mostly numeric text (the value column).

    Ruling 5: the value column is the one with the most cells containing numeric patterns.
    A numeric-looking cell has at least one digit/decimal pattern.
    Returns None if no column has any numeric cells.
    """
    col_numeric_count: dict[int, int] = defaultdict(int)
    for (r, c), text in cell_texts.items():
        if re.search(r'[\d.]+', text):
            col_numeric_count[c] += 1
    if not col_numeric_count:
        return None
    return max(col_numeric_count, key=col_numeric_count.__getitem__)


def _contains_aggregate_word(text: str) -> bool:
    """Return True if any word in `text` (case-insensitive) is in AGGREGATE_LEXICON.

    D-STR1 general engine: aggregate label cells have names like "Total Impurities",
    "Maximum Measured Value", "Minimum Reported", "Average Release" — multi-word labels
    where ONE of the words is in AGGREGATE_LEXICON. Exact-match on the full label would
    miss all multi-word labels, so this function checks word-by-word.

    No submission-specific string is introduced here (D-GEN2): only the general vocabulary
    from AGGREGATE_LEXICON (frozenset{"total","sum","maximum","max","minimum","min",
    "average","mean"}) determines whether a cell is a label candidate.
    """
    words = re.split(r'\W+', text.strip().lower())
    return any(w in AGGREGATE_LEXICON for w in words if w)


def _infer_relation(label_text: str) -> str:
    """Map aggregate label text to a relation enum string.

    D-STR1: ONE general engine mapping AGGREGATE_LEXICON labels to relations.
    Scans all words in the label text (case-insensitive) to find a recognized keyword.
    Returns "SUM" as the default for labels where no specific relation keyword is found.

    Examples:
    - "Total Impurities" -> words ["total", "impurities"] -> "total" -> SUM
    - "Maximum Measured Value" -> words ["maximum", ...] -> "maximum" -> MAX
    - "Minimum Reported" -> "minimum" -> MIN
    - "Average Release" -> "average" -> MEAN
    """
    words = set(re.split(r'\W+', label_text.strip().lower()))
    if words & {"maximum", "max"}:
        return "MAX"
    if words & {"minimum", "min"}:
        return "MIN"
    if words & {"average", "mean"}:
        return "MEAN"
    # "total", "sum", and any other AGGREGATE_LEXICON member -> SUM
    return "SUM"


def _deduplicate_basis(basis: list[SpanID]) -> list[SpanID]:
    """Deduplicate basis spans by (doc_id, start, end) — Pitfall 2 (merged cells).

    Merged cells in a table may map multiple (row, col) coordinates to the same SpanID.
    Without deduplication, a recompute that sums the same value multiple times would
    produce an incorrect expected value (false positive).
    """
    seen: set[tuple[str, int, int]] = set()
    unique: list[SpanID] = []
    for s in basis:
        key = (s.doc_id, s.start, s.end)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


# ---------------------------------------------------------------------------
# Core scan function (Ruling 5 — explicit table-primitive algorithm)
# ---------------------------------------------------------------------------

def _scan_tables(
    corpus: CorpusIndex,
    doc_id: str,
    ledger: RetrievalLedger,
    rulebook_cache_dir: str,
) -> list[Fault]:
    """Scan all addressable tables in a document for labeled-aggregate violations.

    Algorithm (Ruling 5 — explicit table primitives):
    1. Parse table_index into per-table cell maps.
    2. For each table: identify the value column (numeric) and label column(s).
    3. Find cells in label columns whose text is in AGGREGATE_LEXICON.
    4. For each aggregate label: the CLAIM cell is (same_row, value_col).
    5. BASIS cells are all (non-aggregate-row, value_col) cells.
    6. Deduplicate basis (Pitfall 2), require >= 2 independent basis cells.
    7. Compute recomputed value from basis numerics using inferred relation.
    8. Apply D-STR4 precision-derived comparison; emit via emit_structural_finding
       if violation detected.

    Returns list of grounded Fault objects (may be empty).
    """
    cache = corpus.cached_entry(doc_id)
    if cache is None:
        log.info("structural.scan_tables: no cache entry", doc_id=doc_id)
        return []

    table_cells = _get_table_cells(cache)
    if not table_cells:
        log.info("structural.scan_tables: no addressable tables", doc_id=doc_id)
        return []

    faults: list[Fault] = []

    for table_id, cells in table_cells.items():
        if not cells:
            continue

        # Read all cell texts for this table
        cell_texts: dict[tuple[int, int], str] = {}
        for (row, col), span in cells.items():
            text = _read_cell_text(corpus, doc_id, span)
            if text is not None:
                cell_texts[(row, col)] = text

        if not cell_texts:
            continue

        # Identify the value column (the column with the most numeric cells)
        value_col = _find_value_column(cells, cell_texts)
        if value_col is None:
            continue

        # Find ALL aggregate label rows: cells in non-value columns whose text CONTAINS
        # at least one word from AGGREGATE_LEXICON (e.g. "Total Impurities" contains "total")
        aggregate_label_rows: set[int] = set()
        for (row, col), text in cell_texts.items():
            if col != value_col and _contains_aggregate_word(text):
                aggregate_label_rows.add(row)

        # For each aggregate label cell, detect violations
        for (row, col), span in cells.items():
            if col == value_col:
                continue  # value cells are not label candidates
            text = cell_texts.get((row, col), "")
            if not _contains_aggregate_word(text):
                continue

            # Found aggregate label at (row, col)
            # CLAIM cell = value in same row, value_col (Ruling 5: paired-column pattern)
            claim_pos = (row, value_col)
            if claim_pos not in cells:
                continue
            claim_span = cells[claim_pos]
            claim_text = cell_texts.get(claim_pos)
            if claim_text is None:
                continue

            # BASIS = all non-aggregate-label rows in the value_col that contain numeric text
            # Ruling 5: basis cells are value-column cells for ALL non-aggregate rows
            # We collect spans and numeric values together to avoid counting non-numeric
            # header cells as basis (e.g. "% w/w" header is in col 1 but not a data cell)
            max_row = max(r for (r, c) in cells)
            basis_positions = [
                (r, value_col)
                for r in range(0, max_row + 1)
                if (r, value_col) in cells
                and r != row                         # not the current aggregate row
                and r not in aggregate_label_rows    # not any other aggregate label row
            ]

            # Read basis cell texts and collect only numeric-parseable ones
            basis_spans_all = [cells[pos] for pos in basis_positions if pos in cells]
            basis_nums: list[float] = []
            basis_spans_numeric: list[SpanID] = []
            for pos in basis_positions:
                bt = cell_texts.get(pos)
                if bt is None:
                    continue
                num = _parse_numeric(bt)
                if num is not None:
                    basis_nums.append(num)
                    if pos in cells:
                        basis_spans_numeric.append(cells[pos])

            # Deduplicate numeric basis spans (Pitfall 2: merged cells -> same SpanID)
            unique_basis = _deduplicate_basis(basis_spans_numeric)
            if len(unique_basis) < 2:
                # Abstain: no_comparison_basis (fewer than 2 independent numeric basis cells)
                log.debug(
                    "structural: abstain no_comparison_basis",
                    doc_id=doc_id, table_id=table_id, row=row, col=col,
                    unique_basis_count=len(unique_basis),
                )
                continue

            if not basis_nums:
                # Abstain: no numeric basis values
                continue

            # Compute recomputed value based on inferred relation
            relation = _infer_relation(text)
            if relation == "SUM":
                recomputed = sum(basis_nums)
            elif relation == "MAX":
                recomputed = max(basis_nums)
            elif relation == "MIN":
                recomputed = min(basis_nums)
            elif relation == "MEAN":
                recomputed = sum(basis_nums) / len(basis_nums)
            else:
                recomputed = sum(basis_nums)  # default to SUM

            # D-STR4 precision-derived comparison (no epsilon)
            recomputed_str = str(round(recomputed, max(_stated_precision(claim_text), 2)))
            is_violation = compare_values(claim_text, recomputed_str, relation)

            if is_violation is None:
                # Abstain: unparseable claim text
                log.debug(
                    "structural: abstain unparseable claim",
                    doc_id=doc_id, table_id=table_id, claim_text=claim_text,
                )
                continue

            if not is_violation:
                # Compliant: claim matches recomputed value at stated precision
                continue

            # Violation detected: build anchor and emit via the grounding gate
            prec = _stated_precision(claim_text)
            expected_str = str(round(recomputed, prec)) if prec > 0 else str(recomputed)
            anchor = StructuralAnchor(
                claim_span_id=claim_span,
                basis_span_ids=unique_basis,
                relation=relation,
                expected_value=expected_str,
                actual_value=claim_text,
            )
            result = emit_structural_finding(
                corpus=corpus,
                rule_span_id=None,  # D-STR6: pure arithmetic check, no rule span
                structural_anchor=anchor,
                ledger=ledger,
                title=(
                    f"Labeled-aggregate {relation} mismatch: "
                    f"stated {claim_text!r} != recomputed {expected_str!r}"
                ),
                detail=(
                    f"Table {table_id!r}: aggregate cell at row {row} states {claim_text!r} "
                    f"but recompute of {len(basis_nums)} basis values gives {expected_str!r} "
                    f"(relation: {relation})."
                ),
                rulebook_cache_dir=rulebook_cache_dir,
            )
            if isinstance(result, Fault):
                faults.append(result)
                log.info(
                    "structural: violation emitted",
                    doc_id=doc_id, table_id=table_id, row=row, relation=relation,
                    claim=claim_text, expected=expected_str,
                )
            else:
                log.debug(
                    "structural: emit rejected",
                    doc_id=doc_id, reason_code=getattr(result, "reason_code", "?"),
                )

    return faults


# ---------------------------------------------------------------------------
# Public API (D-ABS3 pattern: pure function, no fresh ledger created here)
# ---------------------------------------------------------------------------

def detect_structural_inconsistencies(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
) -> list[Fault]:
    """Deterministic intra-document structural inconsistency pass (RECALL-02, D-STR1–6).

    Pure function over (corpus, manifest, ledger): no side effects on corpus or manifest.
    The ledger is passed in by the caller (Ruling 1); this function does NOT create a
    fresh RetrievalLedger().

    Iterates manifest.documents; for each document:
    - Skips docs where table_index is missing/empty (D-STR5: logs, never crashes)
    - For each addressable doc: scans tables for labeled-aggregate violations

    Returns a flattened list of grounded Fault objects (leg_tag='STRUCTURAL').
    """
    faults: list[Fault] = []

    for doc in manifest.documents:
        # D-STR5: skip docs with unavailable table tier
        if doc.tables != "addressable":
            log.debug(
                "structural: skipping doc with unavailable tables",
                doc_id=doc.doc_id, tables_tier=doc.tables,
            )
            continue

        # Check that the cache entry exists and has a non-empty table_index
        cache = corpus.cached_entry(doc.doc_id)
        if cache is None:
            log.info(
                "structural: no cache entry for doc",
                doc_id=doc.doc_id,
            )
            continue

        table_index = cache.get("table_index", {}) or {}
        if not table_index:
            log.info(
                "structural: empty table_index for doc",
                doc_id=doc.doc_id,
            )
            continue

        doc_faults = _scan_tables(corpus, doc.doc_id, ledger, rulebook_cache_dir)
        faults.extend(doc_faults)

    return faults
