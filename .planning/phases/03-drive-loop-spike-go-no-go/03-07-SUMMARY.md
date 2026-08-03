---
phase: 03-drive-loop-spike-go-no-go
plan: 07
subsystem: agents
tags: [budget-ledger, stop-conditions, pytest, agent-loop]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: Review package scaffold and ChatTurn transport from plans 03-03 and 03-05
provides:
  - BudgetLedger per-run accumulator for AGENT-03 and AGENT-04 stop conditions
  - Unit proof for token, wall-clock, turn, diminishing-returns, breaker, and nudge bounds
affects: [phase-03-review-loop, agent-03, agent-04, d-bud2, d-bud3, d-bud4, d-bud5]

tech-stack:
  added: []
  patterns:
    - Constructor-injected per-run accumulator mirroring RetrievalLedger
    - Injectable clock for deterministic wall-clock tests
    - Named stop predicates with fixed stop-reason precedence

key-files:
  created:
    - src/agents/review/budget.py
    - tests/agents/review/test_budget_ledger.py
  modified: []

key-decisions:
  - "BudgetLedger uses provider billed-token totals when present and a declared non-zero estimate when usage is missing."
  - "Breaker telemetry returns named reasons so later loop reports can distinguish identical args from same-class rejections."
  - "Continuation gating records which bound blocked nudging: diminishing_returns or max_continuations."

patterns-established:
  - "BudgetLedger: pure injected accumulator with no I/O and no loop imports."
  - "Budget stop tests: isolate arithmetic and predicates before loop wiring lands."

requirements-completed: [AGENT-03, AGENT-04]

duration: 34min
completed: 2026-08-03
---

# Phase 03 Plan 07: Budget Ledger Summary

**Per-run BudgetLedger enforcing AGENT-03 and AGENT-04 stop conditions as code, with isolated unit coverage for every bound**

## Performance

- **Duration:** 34 min
- **Started:** 2026-08-03T09:42:00Z
- **Completed:** 2026-08-03T10:16:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `BudgetLedger` with token, wall-clock, turn, diminishing-returns, circuit-breaker, nudge-floor, and stop-reason predicates.
- Implemented billed-token accounting, cached-token tracking, missing-usage estimates, canonical tool-call keys, and same-class rejection reset semantics.
- Added 14 unit tests proving every stop condition in isolation, including the Pitfall-4 enumerate productivity clause and both AGENT-04 nudge bounds.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build BudgetLedger with every stop condition as a method** - `3745292` (feat)
2. **Task 2: Unit-prove every stop condition in isolation** - `d447f35` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agents/review/budget.py` - Per-run budget accumulator and stop-condition predicates.
- `tests/agents/review/test_budget_ledger.py` - Isolated unit tests for ceilings, DR, breakers, nudge bounds, stop precedence, and missing usage.

## Verification

- `grep -c "class BudgetLedger" src/agents/review/budget.py` -> `1`
- `grep -c "def over_ceiling\|def over_wall_clock\|def over_turns\|def in_diminishing_returns\|def breaker_tripped\|def may_nudge\|def stop_reason" src/agents/review/budget.py` -> `7`
- `PYTHONPATH=src .venv/bin/python -c "from agents.review.budget import BudgetLedger as B; b=B(max_tokens=1,max_wall_clock_s=1.0); assert (b.max_turns,b.dr_window,b.breaker_repeat,b.breaker_same_class,b.max_continuations)==(50,3,3,4,5), (b.max_turns,b.dr_window,b.breaker_repeat,b.breaker_same_class,b.max_continuations); print('ok')"` -> `ok`
- `grep -v '^ *#' src/agents/review/budget.py | grep -c "open(\|Path(\|structlog\|print("` -> `0`
- `grep -v '^ *#' src/agents/review/budget.py | grep -c "SYSTEM_PROMPT\|prompt\b"` -> `0`
- `grep -c "clock" src/agents/review/budget.py` -> `7`
- `grep -c "D-BUD2\|D-BUD3\|D-BUD4\|D-BUD5\|Pitfall 4\|Pitfall 8" src/agents/review/budget.py` -> `5`
- `.venv/bin/pytest tests/agents/review/test_budget_ledger.py -x -q` -> `14 passed, 5 warnings in 0.02s`
- `grep -c "def test_" tests/agents/review/test_budget_ledger.py` -> `14`
- `grep -c "def test_enumerate_turn_counts_as_productive" tests/agents/review/test_budget_ledger.py` -> `1`
- `grep -c "def test_may_nudge_is_blocked_by_diminishing_returns\|def test_may_nudge_is_blocked_by_the_hard_cap" tests/agents/review/test_budget_ledger.py` -> `2`
- `grep -c "time.sleep" tests/agents/review/test_budget_ledger.py` -> `0`
- `grep -c "Mock\|MagicMock\|patch(" tests/agents/review/test_budget_ledger.py` -> `0`
- `.venv/bin/pytest tests/agents/review tests/tools -x -q` -> `87 passed, 5 warnings in 85.78s`
- `.venv/bin/pytest -q` -> `403 passed, 11 skipped, 6 warnings in 708.74s`

## Decisions Made

- Used a pure dataclass accumulator instead of adding loop-level behavior; later plans wire these predicates into the real turn loop.
- Added `record_tool_success()` so the same-class rejection breaker can reset on a successful tool result, as required by D-BUD3.
- Kept missing-provider-usage accounting deliberately non-zero and counted in `usage_missing_turns` so a missing usage object cannot silently disable the ceiling.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Concurrent Wave 3 work left unrelated dirty files and additional pytest processes in the worktree. Only the 03-07 owned files were staged, and the full suite was allowed to finish rather than interrupting other agents.

## Known Stubs

None. The stub-pattern scan only matched a test helper initializing `tool_calls=[]`; no production stub or unwired UI data path was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 03-13 and 03-14 can inject `BudgetLedger` into the review loop and rely on named predicate outputs for telemetry, continuation-floor decisions, and forced-runaway stop-condition tests.

## Self-Check: PASSED

- Created files exist: `src/agents/review/budget.py`, `tests/agents/review/test_budget_ledger.py`, and this summary.
- Task commits found in git history: `3745292`, `d447f35`.
- No accidental tracked-file deletions were reported by the per-task post-commit checks.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
