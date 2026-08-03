---
phase: 03-drive-loop-spike-go-no-go
plan: 04
subsystem: rulebook
tags: [requirement-index, ingestion, classification, grounding, rulebook]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: P2 parser/cache correction and baseline-shift disclosure from 03-01
  - phase: 02-retrieval-navigation-tools-rulebook
    provides: read_guideline, requirement index, rulebook store, verification queue
provides:
  - Real-ingestion classification proof for mvr1381 and spec32s41
  - Requirement-index integration test binding real classification to CFR requirement firing
  - Verification-queue item 5 direct citation lookup blocker record
affects: [phase-03-preregistration, absence_of_evidence, read_guideline, requirement-index]

tech-stack:
  added: []
  patterns:
    - Supplemental requirement applicability links through the existing generic edge table
    - Real PDF ingest integration test with rulebook build using update_manifest=False

key-files:
  created:
    - .planning/phases/03-drive-loop-spike-go-no-go/03-P1-CLASSIFICATION-PROOF.md
    - tests/rulebook/test_requirement_index_integration.py
  modified:
    - src/rulebook/requirement_index.py
    - tests/rulebook/test_requirement_index.py

key-decisions:
  - "Real ingestion classified mvr1381 as 3.2.S.4.2 and spec32s41 as 3.2.S.4.1, so the hardcoded 3.2.S.5 fixture assumption was replaced with supplemental links for both measured families."
  - "Verification-queue item 5 remains blocked under direct lookup_citation(entry.citation): 0/15 authored citation strings resolve against the real rulebook store."

patterns-established:
  - "Requirement applicability can add measured-family links without changing reviewed citations, rule_doc_ids, or triggers."
  - "Real-ingest tests disable manifest DB persistence and build rulebook fixtures with update_manifest=False."

requirements-completed: [GROUND-03]

duration: 31 min
completed: 2026-08-03
---

# Phase 03 Plan 04: P1 Classification Proof Summary

**Real-ingestion classification now drives the corrected-basis CFR requirement entries, while direct requirement citation lookup is recorded as a blocker.**

## Performance

- **Duration:** 31 min
- **Started:** 2026-08-03T09:22:27Z
- **Completed:** 2026-08-03T09:53:53Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Proved real `ingest_corpus` classifies `mvr1381` as `3.2.S.4.2` and `spec32s41` as `3.2.S.4.1`, not the fixture-assumed `3.2.S.5`.
- Added version-4 supplemental requirement-index links so `CFR-211160B-SOUND-BASIS` and `CFR-211194-CALCULATIONS` enumerate for both measured real families.
- Added `tests/rulebook/test_requirement_index_integration.py`, which builds a real two-PDF corpus through ingestion and passes without skipping.
- Documented that direct `lookup_citation(entry.citation)` resolves `0/15`, so verification-queue item 5 remains a named blocker under this plan's strict check.

## Task Commits

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Verify item 5 closure on real committed data | `29cf25b` | `.planning/phases/03-drive-loop-spike-go-no-go/03-P1-CLASSIFICATION-PROOF.md` |
| 2 | Prove real-ingestion classification drives requirement-index firing | `fe23e1e` | `src/rulebook/requirement_index.py`, `tests/rulebook/test_requirement_index.py`, `tests/rulebook/test_requirement_index_integration.py`, proof doc |
| 3 | Write final P1 classification proof document | `6a7a8ff` | `.planning/phases/03-drive-loop-spike-go-no-go/03-P1-CLASSIFICATION-PROOF.md` |

## Files Created/Modified

- `.planning/phases/03-drive-loop-spike-go-no-go/03-P1-CLASSIFICATION-PROOF.md` - Six-section measured proof with classification results, requirement firing, item-5 blocker, gate meaning, and post-P2 note.
- `src/rulebook/requirement_index.py` - Bumped `REQUIREMENT_INDEX_VERSION` to `"4"`, added supplemental links for the two CFR requirements, and fixed family filtering to follow edge linkage.
- `tests/rulebook/test_requirement_index_integration.py` - Real-ingest integration test over the two required PDFs.
- `tests/rulebook/test_requirement_index.py` - Updated the version assertion rationale to v4.

## Decisions Made

- Kept reviewed entry citations, rule_doc_ids, and triggers unchanged; only family applicability linkage changed.
- Used supplemental family links for both measured real families because a single-family retag would leave either `mvr1381` or `spec32s41` uncovered.
- Recorded item 5 as a blocker instead of changing `read_guideline`, `lookup_citation`, or rulebook data in this plan.

## Verification

Commands run:

| Command | Result |
|---|---|
| `.venv/bin/pytest tests/tools/test_enumerate_fetch_emit_e2e.py -v` | `2 passed, 5 warnings in 82.38s` |
| `.venv/bin/pytest tests/tools/test_enumerate_fetch_emit_e2e.py -q` | `2 passed, 5 warnings in 41.62s` |
| independent `lookup_citation(entry.citation)` script | `TOTAL 0/15 resolved` against 605 store chunks |
| `.venv/bin/pytest tests/rulebook/test_requirement_index_integration.py -x -q` | `1 passed, 5 warnings in 172.96s` |
| `.venv/bin/pytest tests/rulebook/test_requirement_index.py -q` | `23 passed, 5 warnings in 40.75s` |
| `.venv/bin/pytest tests/rulebook tests/tools -q` | `125 passed, 5 warnings in 375.24s` |
| `.venv/bin/pytest -q` | `370 passed, 11 skipped, 6 warnings in 438.58s` |
| proof acceptance checks | File exists, six numbered sections, both CFR IDs, both measured families, one blocker marker, zero fill-marker tokens |

`git status --porcelain rulebook/manifest.yaml` reported ` M rulebook/manifest.yaml` before and after this plan. It was pre-existing dirty state and was not staged.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Supported two measured real families for the corrected-basis CFR requirements**
- **Found during:** Task 2
- **Issue:** The plan's re-tag branch assumed the real documents would share one replacement family. Real ingestion measured `mvr1381 = 3.2.S.4.2` and `spec32s41 = 3.2.S.4.1`; a single-family move would leave one document uncovered.
- **Fix:** Added supplemental `family_requires_requirement` links for both measured families using the existing edge-table model, updated family filtering to honor edge linkage, and bumped `REQUIREMENT_INDEX_VERSION` to `"4"`.
- **Files modified:** `src/rulebook/requirement_index.py`, `tests/rulebook/test_requirement_index.py`, `tests/rulebook/test_requirement_index_integration.py`, proof doc
- **Verification:** Target integration test passed without skipping; existing requirement-index suite passed.
- **Committed in:** `fe23e1e`

---

**Total deviations:** 1 auto-fixed (Rule 2)
**Impact on plan:** Narrow correctness adjustment inside the planned requirement-index linkage boundary. No baseline artifacts, `src/evals/match.py`, `rulebook/manifest.yaml`, citations, rule_doc_ids, or triggers were changed.

## Issues Encountered

- Verification-queue item 5 is not closed under direct `lookup_citation(entry.citation)`: all 15 authored citation strings returned `NOT_FOUND`. This is documented as a blocker in the proof for the 03-17 pre-registration gate.
- A first throwaway script invocation missed `PYTHONPATH=src`; rerun with the repo Python path succeeded. No code change was needed.

## Known Stubs

None. Stub scan only matched measured empty-list output (`targets_present=[]`) in the proof document, which records the pre-fix real-family enumeration result.

## Authentication Gates

None.

## Threat Flags

None. The classification-to-requirement and citation-to-store trust boundaries were already in this plan's threat model and were either mitigated by tests or recorded as a blocker.

## User Setup Required

None.

## Next Phase Readiness

Ready for later Phase 03 precondition work with one explicit caveat: the real classification linkage is proven, but the direct citation lookup path remains blocked and must be considered before interpreting any `absence_of_evidence` spike score.

## Self-Check: PASSED

- Found proof document: `.planning/phases/03-drive-loop-spike-go-no-go/03-P1-CLASSIFICATION-PROOF.md`
- Found integration test: `tests/rulebook/test_requirement_index_integration.py`
- Found task commits: `29cf25b`, `fe23e1e`, `6a7a8ff`
- Verification commands above completed successfully.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
