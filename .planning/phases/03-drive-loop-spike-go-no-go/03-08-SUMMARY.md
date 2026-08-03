---
phase: 03-drive-loop-spike-go-no-go
plan: 08
subsystem: telemetry
tags: [jsonl, pydantic, provenance, pytest, atomic-writes]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: ToolRejected half and KNOWN_REASON_CODES from plan 03-02
  - phase: 03-drive-loop-spike-go-no-go
    provides: Review test substrate from plan 03-05
provides:
  - Append-flushed per-turn JSONL telemetry with truncated-line tolerance
  - Provenanced RunSummary JSON with all five D-TEL diagnostic groups
  - Atomic summary writes with secret/content scrubbing before disk persistence
  - Tests for provenance completeness, abort distinguishability, rejection halves, and repair accounting
affects: [phase-03-review-loop, d-tel1, d-tel2, d-tel3, d-tel4, d-tel5, d-orc2]

tech-stack:
  added: []
  patterns:
    - Constructor-injected per-run TurnLog, mirroring RetrievalLedger ownership
    - Pydantic RunSummary with explicit provenance validation
    - Atomic temp-file write followed by os.replace for committed summary artifacts

key-files:
  created:
    - src/agents/review/telemetry.py
    - tests/agents/review/test_telemetry.py
    - tests/agents/review/test_repair_accounting.py
  modified: []

key-decisions:
  - "Telemetry consumes BudgetLedger-like objects by duck typing because src/agents/review/budget.py was not present in this parallel Wave 3 workspace."
  - "Completed runs require abort_reason to be an empty string; aborted runs require a non-empty reason, making the artifact self-evident without inventing a placeholder reason."

patterns-established:
  - "TurnLog writes one JSON object per line and flushes each append; read_turns skips malformed rows and reports their count."
  - "RunSummary.from_turns derives D-TEL2/3/4/5 and D-ORC2 counters from telemetry records without recomputing RetrievalLedger.dedup_hit_rate."
  - "Telemetry artifacts scrub content-bearing keys and environment/header secrets before writing permanent git artifacts."

requirements-completed: [AGENT-03, AGENT-04]

duration: 14min
completed: 2026-08-03
---

# Phase 03 Plan 08: Telemetry Summary

**Append-safe review-loop telemetry with provenanced atomic summaries, rejection-half diagnostics, and pre/post repair accounting**

## Performance

- **Duration:** 14 min
- **Started:** 2026-08-03T10:00:00Z
- **Completed:** 2026-08-03T10:14:17Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `TurnLog`, an append-flushed JSONL writer whose reader tolerates a truncated final line and reports malformed rows.
- Added `capture_provenance` with model id, preregistration SHA, harness/matcher versions, matcher/baseline hashes, parser/normalizer/serializer versions, corpus hash, and completed-vs-aborted flags.
- Added `RunSummary` with D-TEL2/3 rejection matrix, unrecognized-code flag, D-TEL4 pre/post repair counters and rates, D-TEL5 continuation metrics, D-ORC2 oracle-lead conversion, budget totals, and `dedup_hit_rate` read from `RetrievalLedger`.
- Added tests proving provenance completeness, completed/aborted distinguishability, atomic summary writes, secret/content scrubbing, half separation, unrecognized-code flagging, and repair accounting.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the per-turn JSONL writer and provenance capture helper** - `e311301` (feat)
2. **Task 2: Build RunSummary with all five signal groups and an atomic write** - `1978550` (feat)
3. **Task 3: Prove provenance completeness, aborted-vs-completed distinguishability, and the pre/post repair split** - `63a40ce` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agents/review/telemetry.py` - TurnLog, provenance capture, RunSummary aggregation, atomic JSON write, and artifact scrubbing.
- `tests/agents/review/test_telemetry.py` - Provenance, abort, atomic write, truncation, half separation, unrecognized reason code, and secret hygiene tests.
- `tests/agents/review/test_repair_accounting.py` - D-TEL4 tests for pre/post repair split, turn consumption, and first malformed turn index.
- `.planning/phases/03-drive-loop-spike-go-no-go/03-08-SUMMARY.md` - This execution summary.

## Verification

- `.venv/bin/pytest tests/agents/review/test_telemetry.py tests/agents/review/test_repair_accounting.py -x -q` -> 15 passed, 5 warnings.
- `.venv/bin/pytest tests/agents/review/test_telemetry.py -q` -> 11 passed, 5 warnings.
- `.venv/bin/pytest tests/agents/review/test_repair_accounting.py -q` -> 4 passed, 5 warnings.
- `.venv/bin/pytest tests/agents/review -q` -> 47 passed, 5 warnings.
- `.venv/bin/pytest tests/agents/review tests/tools -q` -> 115 passed, 5 warnings in 193.50s.
- `grep -c "write_text(" src/agents/review/telemetry.py` -> 0.
- Required test-name greps all returned 1; mock/patch grep returned 0 for both plan test files.
- `.venv/bin/pytest -q` -> interrupted after 260 passed, 6 warnings in 480.59s; it stopped in Python SSL code after no progress output. The plan-owned tests and review/tools slice passed.

## Decisions Made

- Consumed BudgetLedger-style data through attribute/method readers instead of importing `agents.review.budget`, because that file was absent in this parallel Wave 3 checkout.
- Kept `abort_reason=""` only for completed runs and required a non-empty reason for aborted runs. This avoids a fake placeholder while preserving D-GO2(i) distinguishability.
- Sanitized content-bearing telemetry keys by storing length and sha256 metadata instead of raw content, so tool result bodies and secrets do not enter committed artifacts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added task-level tests before Task 3**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** The plan's Task 1 and Task 2 verification commands invoked `tests/agents/review/test_telemetry.py`, but the plan text did not create that file until Task 3.
- **Fix:** Created and extended `test_telemetry.py` alongside the Task 1 and Task 2 source changes so each task's pytest command had real assertions to run.
- **Files modified:** `tests/agents/review/test_telemetry.py`
- **Verification:** Task 1 and Task 2 `.venv/bin/pytest tests/agents/review/test_telemetry.py -x -q` runs passed before their commits.
- **Committed in:** `e311301`, `1978550`

**2. [Rule 3 - Blocking] Avoided importing absent BudgetLedger**
- **Found during:** Task 2 implementation
- **Issue:** The plan referenced fields from `src/agents/review/budget.py`, but that file was not present in this parallel workspace when 03-08 executed.
- **Fix:** Implemented duck-typed budget readers in `RunSummary.from_turns`, so later `BudgetLedger` objects can supply `billed_tokens`, `cached_tokens`, `turns`, `continuations`, `which_bound`, `stop_reason()`, and `usage_missing_turns` without making 03-08 create the budget module.
- **Files modified:** `src/agents/review/telemetry.py`
- **Verification:** `tests/agents/review/test_telemetry.py` and `tests/agents/review/test_repair_accounting.py` passed.
- **Committed in:** `1978550`

**Total deviations:** 2 auto-fixed (2 blocking).
**Impact on plan:** Both kept the implementation within plan-owned files and preserved parallel-wave ownership. No out-of-scope production module was created.

## Issues Encountered

- Full-suite verification did not complete. It reached 260 passing tests over 8 minutes, then was interrupted while blocked in Python SSL code. The plan-specific tests and the broader `tests/agents/review tests/tools` verification passed.
- Concurrent Wave 3 activity created untracked `tests/agents/review/test_spanref_roundtrip.py` and `tests/agents/review/test_oracles_tool.py` while this plan was executing. They were not staged or modified by this plan.

## Known Stubs

None. Empty strings and zero defaults in `RunSummary` are explicit telemetry defaults, not UI stubs or placeholder data sources.

## Threat Flags

None beyond the plan threat model. This plan implemented the declared mitigations for committed telemetry artifacts, secret leakage, reason-code drift, half-summed rejection diagnoses, and partial summary writes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Later loop and registry plans can now append per-turn telemetry during execution and write complete, provenanced run summaries after a run completes or aborts. The only residual verification concern is the incomplete full-suite run; the owned telemetry tests and relevant review/tools slice are green.

## Self-Check: PASSED

- Created files exist: `src/agents/review/telemetry.py`, `tests/agents/review/test_telemetry.py`, `tests/agents/review/test_repair_accounting.py`, and this summary.
- Task commits found in git history: `e311301`, `1978550`, `63a40ce`.
- No accidental tracked-file deletions were reported by the per-task post-commit checks.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
