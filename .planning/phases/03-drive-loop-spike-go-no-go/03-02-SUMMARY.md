---
phase: 03-drive-loop-spike-go-no-go
plan: 02
subsystem: grounding
tags: [tools, schemas, telemetry, verdicts]
requires:
  - phase: 02-retrieval-navigation-tools-rulebook
    provides: emit_finding grounding gate
provides:
  - ToolRejected half diagnostics and reason-code registry
  - ComplianceVerdict and grounded Fault span fields
  - emit_finding verdict validation and span persistence
affects: [phase-03, telemetry, verifier]
tech-stack:
  added: []
  patterns: [open reason-code registry, closed citation-half field]
key-files:
  created:
    - tests/tools/test_errors_registry.py
  modified:
    - src/tools/errors.py
    - src/tools/emit_finding.py
    - src/schemas/faults.py
    - src/evals/__init__.py
    - tests/tools/test_emit_finding.py
    - tests/tools/test_contracts.py
    - tests/unit/test_schemas.py
key-decisions:
  - "reason_code remains an open string, while citation half is a closed Literal."
  - "Invalid verdicts are rejected before Fault construction."
requirements-completed: [GROUND-01, GROUND-03, DETECT-04]
duration: 0h
completed: 2026-08-03
---

# Phase 03 Plan 02: Grounded Finding Contract Summary

**Grounded findings now carry scored verdicts plus re-openable rule and submission spans.**

## Performance

- **Duration:** existing task commits plus final task completion in this session
- **Started:** 2026-08-03
- **Completed:** 2026-08-03
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added `ToolRejected.half` and a single exported `KNOWN_REASON_CODES` registry.
- Added `ComplianceVerdict`, `Fault.verdict`, `Fault.rule_span_id`, `Fault.submission_span_id`, `FaultReport.stop_reason`, and `FaultReport.budget_exhausted`.
- Updated `emit_finding` so all citation-half failures name `submission` or `rule`, invalid verdicts reject structurally, and valid findings persist both spans.

## Task Commits

1. **Task 1: Add rejection diagnostics registry** - `d524c96`
2. **Task 2: Add grounded fault verdict schema** - `23db0c2`
3. **Task 3: Persist grounded finding verdicts** - `5fa0f4c`

## Files Created/Modified

- `src/tools/errors.py` - Adds half diagnostics and reason-code registry.
- `src/schemas/faults.py` - Adds verdict and span fields to fault schemas.
- `src/evals/__init__.py` - Adds harness and matcher version identities.
- `src/tools/emit_finding.py` - Populates half diagnostics, validates verdicts, persists spans.
- `tests/tools/test_emit_finding.py` - Covers all half-specific rejection paths and valid verdict persistence.
- `tests/tools/test_errors_registry.py` - Asserts registry shape and default half behavior.

## Decisions Made

`invalid_verdict` was added to the registry because `emit_finding` now emits it. The registry stays open to later tool codes, but current emitted codes must be registered.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Later telemetry and verifier plans can group rejection causes by `(reason_code, half)` and re-open both spans from every grounded fault.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
