---
phase: 03-drive-loop-spike-go-no-go
plan: 06
subsystem: grounding
tags: [spanref, grounding, retrieval-ledger, pytest, rulebook]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: ToolRejected half/reason-code registry and ComplianceVerdict/Fault span fields from 03-02
  - phase: 03-drive-loop-spike-go-no-go
    provides: Review package scaffold and real multi-document test fixtures from 03-05
provides:
  - Store-explicit parse/mint path for rendered span references
  - Loop-side span_ref rejection codes distinct from emit_finding gate rejections
  - GROUND-01 composition test covering all five rendering tools
affects: [phase-03-review-loop, grounding, emit_finding, telemetry, go-no-go-diagnosis]

tech-stack:
  added: []
  patterns:
    - Store-explicit span reference parsing with required expect parameter
    - Loop-side ToolRejected sentinels with half empty
    - Boundary-crossing pytest composition over real persisted corpus primitives

key-files:
  created:
    - src/agents/review/spanref.py
    - tests/agents/review/test_spanref_roundtrip.py
  modified:
    - src/tools/errors.py

key-decisions:
  - "parse_span_ref requires expect='submission' or expect='rule' and never falls through to the other store."
  - "Loop-side span reference failures use span_ref_* reason codes with half='' so they cannot be counted as D-TEL3 gate rejections."
  - "The round-trip test converts open_doc/follow_reference span dictionaries into the same bracketed ref string before parsing, matching their existing tool contract."

patterns-established:
  - "Rendered refs are parsed by agents.review.spanref only, then re-minted through ingest.anchors.mint_span using the owning store's normalizer_version."
  - "GROUND-01 composition tests assert render -> parse -> was_issued -> open_span across all five tools with non-vacuity guards."

requirements-completed: [GROUND-01]

duration: 19 min
completed: 2026-08-03
---

# Phase 03 Plan 06: Span Reference Round-Trip Summary

**Store-explicit span reference parsing now re-mints model-visible span IDs through one path and proves every tool-issued reference re-opens byte-exact.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-03T09:59:05Z
- **Completed:** 2026-08-03T10:17:47Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `agents.review.spanref.parse_span_ref` as the single loop-side conversion from `[doc_id:start:end]` into a full `SpanID`.
- Registered `span_ref_unparseable`, `span_ref_unknown_doc`, and `span_ref_out_of_range` in `KNOWN_REASON_CODES`.
- Added a 9-test GROUND-01 composition suite covering `search_corpus`, `open_doc`, `get_section`, `read_guideline`, and `follow_reference`.
- Proved loop-side failures are distinct from `not_byte_exact`, store separation is enforced, and a wrong normalizer version fails the real hash check.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build spanref.py as the single parse/mint path** - `10d09b4` (feat)
2. **Task 2: Ship GROUND-01 round-trip composition test** - `09a943c` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agents/review/spanref.py` - Single parser/re-minter for rendered span references with expected-store resolution.
- `src/tools/errors.py` - Added the three loop-side `span_ref_*` reason codes.
- `tests/agents/review/test_spanref_roundtrip.py` - Real composition tests across all five tools plus emit gate and negative controls.

## Verification

Commands run:

| Command | Result |
|---|---|
| `PYTHONPATH=src .venv/bin/python -c "from agents.review.spanref import parse_span_ref, SPAN_REF_RE; ...; print('ok')"` | `ok` |
| Task 1 grep acceptance checks | `def parse_span_ref=1`; `mint_span=2`; `short_hash/blake2b/SpanID(` = `0`; `half=""=1`; `ToolRejected(` = `1`; `half="submission"/"rule"` = `0`; `raise ` = `0`; `NORMALIZER_VERSION=0` |
| `.venv/bin/pytest tests/agents/review/test_spanref_roundtrip.py -x -q` | `9 passed, 5 warnings in 6.16s` |
| `.venv/bin/pytest tests/agents/review/test_spanref_roundtrip.py::test_unresolvable_ref_is_not_span_invention -x -q` | `1 passed, 5 warnings in 0.06s` |
| Task 2 grep acceptance checks | all five tool names present; `assert refs=6`; mock markers `0`; required named tests `3`; `open_span=15` |
| `.venv/bin/pytest tests/agents/review tests/tools -q` | `96 passed, 5 warnings in 107.53s` |
| `.venv/bin/pytest -q` | `416 passed, 11 skipped, 6 warnings in 691.27s` |
| `grep -c "raise " src/agents/review/spanref.py` | `0` |

## Decisions Made

- Required the caller to pass the expected store because resolving against whichever store answers first would violate Security Domain V4.
- Used `mint_span` exclusively for re-minting; `spanref.py` does not construct `SpanID` by hand or compute hashes inline.
- Kept all loop-side rejections at `half=""`; only `emit_finding` owns citation-half classification.
- Converted `open_doc` and `follow_reference` span dictionaries to bracketed refs inside the test before parsing, because those two tools expose `span_id` dictionaries rather than inline text markers.

## Deviations from Plan

### Scope-Preserving Adjustments

**1. Existing tool result shape differs for two of the five tools**
- **Found during:** Task 2 (round-trip composition test)
- **Issue:** The plan described all five tools as rendering bracketed span-ID strings. In the actual code, `open_doc` and resolved `follow_reference` expose `span_id` dictionaries while recording those spans in the ledger.
- **Fix:** The test converts those dictionaries to the same `[doc_id:start:end]` string before calling `parse_span_ref`, preserving the model-visible ID contract and exercising the single parser path.
- **Files modified:** `tests/agents/review/test_spanref_roundtrip.py`
- **Verification:** New composition suite passed; grep checks confirm all five tools and non-vacuity guards are present.
- **Committed in:** `09a943c`

**Total deviations:** 1 scope-preserving adjustment.
**Impact on plan:** No production scope creep. The adjustment aligns the test with the committed Phase-2 tool contracts while preserving GROUND-01 coverage.

## Issues Encountered

- Full-suite verification ran concurrently with other Wave 3 pytest processes, extending runtime to 11m31s. It completed successfully.
- `rulebook/manifest.yaml` and several unrelated files were already dirty or created by parallel work; none were staged or modified by this plan.

## Known Stubs

None. Stub scan only matched the required `half=""` sentinel in `spanref.py`.

## Authentication Gates

None.

## Threat Flags

None. The new model-authored span reference, store separation, and loop-vs-gate diagnosis surfaces were all covered by the plan threat model and tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 03-07 and later can call `parse_span_ref` for submission and rule refs without reimplementing parsing, hash minting, or store selection. Telemetry can classify `span_ref_*` failures separately from `emit_finding` gate failures.

## Self-Check: PASSED

- Found created files: `src/agents/review/spanref.py`, `tests/agents/review/test_spanref_roundtrip.py`, `.planning/phases/03-drive-loop-spike-go-no-go/03-06-SUMMARY.md`
- Found task commits in git history: `10d09b4`, `09a943c`
- Verification commands above completed successfully.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
