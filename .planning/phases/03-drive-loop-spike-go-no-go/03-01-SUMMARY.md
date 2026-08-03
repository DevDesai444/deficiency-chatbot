---
phase: 03-drive-loop-spike-go-no-go
plan: 01
subsystem: ingest
tags: [pdf, parser, cache, retrieval-gate]
requires:
  - phase: 02-retrieval-navigation-tools-rulebook
    provides: SC4 retrieval-gate baseline and P2 queue item
provides:
  - OCR-less scanned PDF fallback now preserves embedded text blocks
  - Parser version participates in ingest cache keys
  - P2 retrieval baseline shift disclosure
affects: [phase-03, retrieval, grounding]
tech-stack:
  added: []
  patterns: [parser-versioned cache invalidation]
key-files:
  created:
    - .planning/phases/03-drive-loop-spike-go-no-go/03-P2-BASELINE-SHIFT.md
  modified:
    - src/parse/pdf.py
    - src/ingest/store.py
    - src/ingest/corpus.py
    - tests/tools/conftest.py
    - tests/ingest/test_store.py
    - tests/unit/test_parse.py
key-decisions:
  - "The retrieval-gate regression is recorded as a measurement result; baseline JSON files remain frozen."
requirements-completed: [GROUND-01]
duration: 0h
completed: 2026-08-03
---

# Phase 03 Plan 01: P2 Parser Fallback and Cache Invalidation Summary

**OCR-less scanned PDF fallback now preserves embedded text blocks and cache keys include parser identity.**

## Performance

- **Duration:** existing task commits plus final disclosure in this session
- **Started:** 2026-08-03
- **Completed:** 2026-08-03
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added `PARSER_VERSION = "pymupdf-blocks/2"` and recovered `_digital_blocks` / `_digital_figures` on the `rapidocr-fallback` branch.
- Changed `cache_key` to require `parser_version`, updating corpus and test call sites so parser changes hard-miss stale cache entries.
- Rebuilt the local ingest cache for the three eval documents with `__pymupdf-blocks_2` suffixes and documented the post-P2 retrieval-gate measurement.

## Task Commits

1. **Task 1: Recover scanned fallback text layer** - `d2deff6`
2. **Task 2: Version parser cache keys** - `f99a7f6`
3. **Task 3: Disclose P2 retrieval shift** - `baca08a`

## Files Created/Modified

- `src/parse/pdf.py` - Preserves fallback embedded text blocks and exposes parser version.
- `src/ingest/store.py` - Requires parser version in cache keys.
- `src/ingest/corpus.py` - Passes `PARSER_VERSION` into cache lookup/write paths.
- `tests/ingest/test_store.py` - Asserts parser-version bumps invalidate cache.
- `tests/unit/test_parse.py` - Asserts scanned-with-text fallback yields blocks.
- `.planning/phases/03-drive-loop-spike-go-no-go/03-P2-BASELINE-SHIFT.md` - Records measured retrieval shift.

## Decisions Made

The committed retrieval baselines were not edited. The post-P2 retrieval gate failed with `mvr1381` at 6/12 hard anchors, so the result is preserved in the disclosure rather than hidden by ratcheting.

## Deviations from Plan

None - plan executed exactly as written, except the measured result contradicted the hypothesis that P2 would improve the hard subset. The contradiction is documented as the plan output.

## Issues Encountered

The live retrieval-gate path attempted Databricks OCR because local credentials were present. The measurement was rerun with OCR forced offline (`ocr_page -> None`) to match the D-RB6 local path.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Wave 2 can build on parser-versioned cache identity. The retrieval-gate failure remains a Phase 3 measurement concern, not a silent baseline update.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
