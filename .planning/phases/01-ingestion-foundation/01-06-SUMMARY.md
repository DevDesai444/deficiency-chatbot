---
phase: 01-ingestion-foundation
plan: 06
subsystem: api
tags: [span-id, anchors, re-open, hash, table-index, merged-cells, blake2b]

requires:
  - phase: 01-ingestion-foundation
    provides: "normalize + offset map (Plan 03); serialize cell_ranges (Plan 02); SpanID type (Plan 02); merged_origins (Plans 02/04)"
provides:
  - "ingest.anchors: mint_span / open_span (D-21 re-open/verify) / short_hash / HashMismatch — returns BOTH raw+canonical or fails"
  - "ingest.tables.build_table_index: (table_id,row,col) -> SpanID; merged coords share the origin span (D-31)"
affects: [01-07, 01-09]

tech-stack:
  added: []
  patterns:
    - "Content-addressed identity: span-ID = canonical char range + blake2b(canonical_substr + normalizer_version); geometry NEVER in identity (D-19)"
    - "Re-open returns both sides or raises HashMismatch — never a silently-wrong citation"

key-files:
  created:
    - src/ingest/anchors.py
    - src/ingest/tables.py
    - tests/ingest/test_anchors.py
    - tests/ingest/test_tables.py
  modified: []

key-decisions:
  - "open_span verifies span.doc_id, then re-hashes canonical[start:end] against span.hash, THEN renders raw via canon_range_to_raw — so tamper / wrong-version / wrong-doc all raise HashMismatch before any substring is returned."
  - "build_table_index maps the serializer's POSITIONAL table index (ti, used in cell_ranges keys) to each table's table_id, mints origin-cell spans from raw->canonical ranges, then fans merged coverage out to the origin span (many coords -> one SpanID)."
  - "Hash over the CANONICAL substring + normalizer_version (RESEARCH Open-Q1) — clean drift detection; no geometry ever enters the identity module (grep-enforced)."

patterns-established:
  - "The two grounding primitives are ingestion-owned (Phase 1 builds the substrate); Phase 2's navigation tools call them (D-21)."

requirements-completed: []  # INGEST-04 re-open primitive + INGEST-05 cell index landed; full delivery gated on the corpus assembly (Plan 09).

duration: ~35min
completed: 2026-07-30
---

# Phase 1 · Plan 06: Anchors + Table Cell Addressing — Summary

**Built the two grounding primitives Phase 2 rests on: the re-open/verify primitive (`open_span` returns both the raw citation and canonical substring, or raises `HashMismatch`) and the `(table_id,row,col)` cell index where every coordinate a merge spans resolves to one origin span-ID — both first consumers of the RISK-1 offset map, and both round-trip byte-exact.**

## Performance
- **Duration:** ~35 min · **Tasks:** 2 · **Files:** 4 created

## Task Commits
1. **Task 1: anchors (mint/open/HashMismatch)** — `5c00e92` (feat)
2. **Task 2: tables (cell index)** — `ac3ad0d` (feat)

## Verification (every acceptance command run via `.venv/bin/python`)
- `test_reopen_and_hash_mismatch` → passes: whole-doc + "specification" spans re-open byte-exact on BOTH sides; the dropped hyphen+newline appears on the RAW side (D-22); tamper / wrong normalizer version / wrong doc_id each raise `HashMismatch`.
- `test_merged_resolves_identically` → passes: `idx["t0,0,1"] == idx["t0,0,0"]` (covered coord shares the origin span); every origin cell re-opens to its exact text; the covered coord re-opens to the ORIGIN text.
- `test_serialization_deterministic` → passes: two builds yield identical `(table_id,row,col)->SpanID` maps and identical offsets.
- Geometry grep on `anchors.py` (`bbox|page|rotation`, non-comment) → **0** (identity module is geometry-free, D-19; reworded a docstring that had tripped it).
- `HashMismatch`/`open_span` and `raw_range_to_canon`/`merged_origins` greps pass.
- Full `pytest tests/ingest/` → **36 passed** (no regression) — the anchors/tables round-trips are additional live validation of the Plan-03 offset map.

## Files
- `src/ingest/anchors.py` — span-ID mint + re-open/verify.
- `src/ingest/tables.py` — cell addressing index.
- `tests/ingest/test_anchors.py`, `tests/ingest/test_tables.py` — 4 tests.
