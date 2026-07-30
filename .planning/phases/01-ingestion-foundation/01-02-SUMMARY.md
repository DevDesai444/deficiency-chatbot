---
phase: 01-ingestion-foundation
plan: 02
subsystem: api
tags: [pydantic, schema, serializer, security, zip-bomb, offsets, span-id]

requires:
  - phase: 01-ingestion-foundation
    provides: "Plan 01 conftest builders (make_doc_dict, merged_table) that the serializer tests feed"
provides:
  - "Span-anchor substrate types: SpanID, OffsetRun, NormalizedText, DocClassification (the interface every later phase grounds on)"
  - "Geometry-optional document model (bbox/page nullable on LayoutBlock/LayoutFigure/ExtractedTable) so DOCX nulls geometry"
  - "ExtractedTable.table_id + merged_origins fields (D-31 table addressing substrate)"
  - "ingest.serialize.serialize_document -> (raw reading-order text, per-cell char ranges) + SERIALIZER_VERSION"
  - "ingest.limits: byte/page/entry/ratio caps + zip-bomb + zip-slip guards + path-safe resolver (LimitExceeded)"
affects: [01-03, 01-04, 01-06, 01-07, 01-09]

tech-stack:
  added: []
  patterns:
    - "Interface-first substrate: types + serializer + limits defined once so downstream plans build against a fixed contract"
    - "Reading-order serializer retains offsets (blocks_to_text/_reading_order_text throw them away)"
    - "limits.py is the single choke point every parse path crosses before the heavy parse (D-16)"

key-files:
  created:
    - src/ingest/serialize.py
    - src/ingest/limits.py
    - tests/ingest/test_serialize.py
    - tests/ingest/test_limits.py
  modified:
    - src/schemas/documents.py
    - src/schemas/__init__.py

key-decisions:
  - "Geometry widened to Optional on LayoutBlock/LayoutFigure AND ExtractedTable.page (the pre-execution reconciliation) — ExtractedTable(page=None) now validates, so Plan 04's DOCX table constructor won't hit a ValidationError outside its file scope."
  - "Serializer keys cell_ranges by POSITIONAL table index ({ti},{r},{c}) exactly as Plan 02's behavior spec dictates; Plan 06 maps table_id -> positional index when building the (table_id,row,col) index."
  - "docx_zip_guard triggers on entry-count OR total-uncompressed OR per-entry compression ratio, and rejects zip-slip (.. / absolute) entry names before docx.Document() ever opens the archive."

patterns-established:
  - "Ingest test imports: `from tests.ingest.conftest import ...` (package path) — required because tests/ingest is a package (__init__.py), so pytest loads the conftest as tests.ingest.conftest, not top-level `conftest`."

requirements-completed: []  # INGEST-04/05 substrate LANDED here but not fully delivered: INGEST-04 also needs normalize+anchors (Plans 03/06), INGEST-05 also needs the (table_id,row,col) index (Plan 06).

duration: ~35min
completed: 2026-07-30
---

# Phase 1 · Plan 02: Substrate Types + Serializer + Security Limits — Summary

**Laid the interface-first substrate: the span-ID/canonical-text type layer, a geometry-optional document model, an offset-retaining reading-order serializer, and the `limits.py` guard every parse path crosses before touching an untrusted file.**

## Performance
- **Duration:** ~35 min
- **Tasks:** 3 completed
- **Files:** 4 created, 2 modified

## Accomplishments
- `schemas/documents.py`: added `SpanID`/`OffsetRun`/`NormalizedText`/`DocClassification`; added `table_id`+`merged_origins` to `ExtractedTable`; made `bbox`/`page` optional on `LayoutBlock`/`LayoutFigure` and `ExtractedTable.page` (D-20) — PDF defaults unchanged. Barrel (`schemas/__init__.py`) re-exports the four new types.
- `ingest/serialize.py`: `serialize_document(doc) -> (raw_text, cell_ranges)` — reading-order flatten that RETAINS each origin cell's exact char range and skips covered merged coords (D-31); `SERIALIZER_VERSION` stamps the scheme.
- `ingest/limits.py`: `check_file_limits`, `docx_zip_guard` (entry/size/ratio + zip-slip), `safe_resolve` (path/symlink escape) — all raising typed `LimitExceeded` with a manifest `.reason`.

## Task Commits
1. **Task 1: schema substrate + geometry-optional** — `8866d80` (feat)
2. **Task 2: reading-order serializer** — `b23de6b` (feat)
3. **Task 3: security limits guard** — `987885b` (feat)

## Verification (every acceptance command run via `.venv/bin/python`, `PYTHONPATH=src` for bare imports)
- Schema: `SpanID(...)`, `ExtractedTable(page=None, merged_origins=...)`, `LayoutBlock(bbox=None, page=None)` all validate → OK; `from parse.pdf import extract_pdf` still imports; barrel exports resolve; SpanID/NormalizedText round-trip; existing `tests/unit/test_schemas.py` → 20 passed.
- Serializer: `pytest tests/ingest/test_serialize.py` → 5 passed; `SERIALIZER_VERSION`/`merged_origins` greps pass; determinism (`first == second`) asserted.
- Limits: `pytest tests/ingest/test_limits.py` → 9 passed; `MAX_UNCOMPRESSED_BYTES`/`safe_resolve`/`LimitExceeded` greps pass; zip-slip + symlink-escape tests present.
- Combined: `pytest tests/ingest/test_serialize.py tests/ingest/test_limits.py` → 14 passed.

## Deviations
- **Test import path** (Task 2/3): the plan's literal `from conftest import ...` cannot resolve because `tests/ingest` is a package (Plan 01 created `tests/ingest/__init__.py`), so pytest imports the conftest as `tests.ingest.conftest`. Used the correct package path `from tests.ingest.conftest import ...`. Builders remain in `conftest.py` (Plan 01 acceptance greps unaffected). This is the pattern all later ingest test files must use.

## Files Created/Modified
- `src/schemas/documents.py`, `src/schemas/__init__.py` — substrate types + geometry-optional widening.
- `src/ingest/serialize.py`, `src/ingest/limits.py` — the two format-neutral primitives.
- `tests/ingest/test_serialize.py`, `tests/ingest/test_limits.py` — 14 tests.

## Issues Encountered
- The `from conftest import` collection error (fixed as above). No other issues; none of the 13 staged redesign files were touched (`faults.py` remains staged/modified, untouched).
