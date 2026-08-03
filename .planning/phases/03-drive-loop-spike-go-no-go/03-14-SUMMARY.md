---
phase: 03-drive-loop-spike-go-no-go
plan: 14
subsystem: review-loop-budgeting
tags: [agent-03, agent-04, d-bud6, d-tel5]
key-files:
  - src/agents/review/loop.py
  - src/agents/review/budget.py
  - src/agents/review/telemetry.py
  - tests/agents/review/test_loop_budget.py
  - tests/agents/review/test_continuation_floor.py
  - tests/agents/review/test_runaway.py
metrics:
  focused_tests: 19
  review_suite_tests: 91
---

# 03-14 Summary

## Commits

| Commit | Description |
|---|---|
| `721be99` | Enforced pre-call stop conditions, AGENT-04 continuation nudging, continuation telemetry, and offline runaway coverage |

## What Changed

- `run_review` now checks hard ceilings, breaker, turn cap, and diminishing returns before each model call.
- No-tool-call stops are refused while `BudgetLedger.may_nudge()` permits continuation; the loop injects the module-constant `NUDGE`.
- Continuation telemetry records tokens at attempted stop and findings before/after each nudge.
- Rejection/success outcome accounting is owned by the loop, avoiding duplicate breaker signals from the registry.
- `BudgetLedger.wall_clock_s()` exposes elapsed time to `RunSummary`.
- Added loop-level tests for token ceiling, wall-clock ceiling, diminishing returns, both breaker modes, rejection turn accounting, continuation bounds, continuation telemetry, zero-continuation visibility, and D-BUD6 runaway behavior.

## Verification

- `PYTHONPATH=src .venv/bin/pytest tests/agents/review/test_loop_budget.py tests/agents/review/test_continuation_floor.py tests/agents/review/test_runaway.py -q` -> `19 passed, 5 warnings`
- `PYTHONPATH=src .venv/bin/pytest tests/agents/detection/test_no_eval_leakage.py tests/agents/review/test_prefix_stability.py tests/agents/review -q` -> `91 passed, 5 warnings`
- `env -u DATABRICKS_HOST -u DATABRICKS_TOKEN PYTHONPATH=src .venv/bin/pytest tests/agents/review/test_runaway.py -x -q` -> `6 passed, 5 warnings`

## Deviations

The D-BUD6 runaway driver uses varying `follow_reference` calls rather than `search_corpus` queries. This keeps the test deterministic and offline without loading the embedding stack while still exercising the real loop and real tool registry, and still proving the token/wall-clock ceilings return a re-scorable partial without tripping the identical-args breaker first.

## Self-Check

PASSED. No prompt module was edited in this plan; the leakage guard and prefix-stability tests remained green.
