---
phase: 03-drive-loop-spike-go-no-go
plan: 05
subsystem: testing
tags: [pytest, fixtures, llm-test-doubles, ci, d-rb6]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: ChatTurn tool-call transport from plan 03-03
provides:
  - Review package marker for later drive-loop modules
  - Offline completion-callable test doubles for model-driven loop tests
  - Persisted multi-document CorpusIndex test builder
  - GitHub Actions pytest workflow with Databricks credentials absent
affects: [phase-03-review-loop, agent-01, agent-03, d-rb6]

tech-stack:
  added: [github-actions]
  patterns:
    - Dependency-injected completion callable for offline loop tests
    - Real persisted CorpusIndex fixtures reused from tests.tools.conftest
    - No-credentials pytest CI contract

key-files:
  created:
    - src/agents/review/__init__.py
    - tests/agents/review/__init__.py
    - tests/agents/review/conftest.py
    - tests/agents/review/test_conftest_smoke.py
    - .github/workflows/test.yml
  modified: []

key-decisions:
  - "Preserved later-plan ownership by making budget_ledger lazily import BudgetLedger when plan 03-07 lands."
  - "Added a narrow conftest smoke test so the multi-document fixture is proven in this plan's commit."

patterns-established:
  - "ScriptedChatClient: records deep-copied messages and tool schemas while replaying ChatTurn objects."
  - "ForcedRunaway: varies real search_corpus calls so budget ceilings, not identical-args breakers, end runaway tests."
  - "ReplayClient: turns committed JSONL transcripts into offline ChatTurn sequences."
  - "build_multi_corpus_index: composes the existing single-document fixture instead of hand-rolling cache entries."

requirements-completed: [AGENT-01, AGENT-03]

duration: 10min
completed: 2026-08-03
---

# Phase 03 Plan 05: Review Test Substrate Summary

**Offline review-loop test substrate with injectable ChatTurn clients, real multi-document corpus fixtures, and no-credentials pytest CI**

## Performance

- **Duration:** 10 min
- **Started:** 2026-08-03T09:22:21Z
- **Completed:** 2026-08-03T09:32:25Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Created the docstring-only `agents.review` package marker without adding later-plan source stubs.
- Added `ScriptedChatClient`, `ForcedRunaway`, `ReplayClient`, `make_tool_call`, fresh ledger fixtures, and `build_multi_corpus_index`.
- Added a smoke test proving a 3-document input returns a genuine persisted `CorpusIndex` with cache entries for each document.
- Added `.github/workflows/test.yml` so the full suite runs without Databricks credentials.

## Task Commits

Each task was committed atomically:

1. **Task 1: Review package markers** - `1b4ea3f` (feat)
2. **Task 2: Offline review fixtures** - `e816329` (test)
3. **Task 3: D-RB6 CI workflow** - `247cfcd` (ci)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agents/review/__init__.py` - Docstring-only package marker; no `run_review` stub.
- `tests/agents/review/__init__.py` - Empty review test package marker.
- `tests/agents/review/conftest.py` - Offline model doubles, tool-call helper, multi-document corpus builder, and per-test ledger fixtures.
- `tests/agents/review/test_conftest_smoke.py` - Smoke proof that the multi-document builder persists three real cache entries.
- `.github/workflows/test.yml` - GitHub Actions pytest workflow with D-RB6 credentials deliberately absent.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -c "import agents.review; print('ok')"` -> `ok`
- `ls src/agents/review/` -> exactly `__init__.py`
- `wc -c tests/agents/review/__init__.py` -> `0`
- `grep -c "class ScriptedChatClient\|class ForcedRunaway\|class ReplayClient" tests/agents/review/conftest.py` -> `3`
- `grep -c "def build_multi_corpus_index\|def make_tool_call" tests/agents/review/conftest.py` -> `2`
- `grep -c "monkeypatch" tests/agents/review/conftest.py` -> `0`
- `grep -c "Mock\|MagicMock\|patch(" tests/agents/review/conftest.py` -> `0`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/agents/review --collect-only -q` -> 1 test collected
- `.venv/bin/pytest tests/agents/review -q` -> 1 passed, 5 warnings
- `test -f .github/workflows/test.yml && grep -q "D-RB6" .github/workflows/test.yml && ! grep -q "DATABRICKS_HOST:\|DATABRICKS_TOKEN:" .github/workflows/test.yml && echo ok` -> `ok`
- `env -u DATABRICKS_HOST -u DATABRICKS_TOKEN .venv/bin/pytest -q` -> 369 passed, 11 skipped, 6 warnings in 279.08s

## Decisions Made

- Kept `src/agents/review/__init__.py` marker-only because `run_review` belongs to plan 03-13.
- Implemented `budget_ledger` as a lazy fixture that imports `agents.review.budget.BudgetLedger` once plan 03-07 creates it, avoiding a fake local budget class or an out-of-scope source module.
- Added `tests/agents/review/test_conftest_smoke.py` because the plan explicitly required a same-commit smoke proof for `build_multi_corpus_index`.

## Deviations from Plan

### Scope-Preserving Adjustments

**1. Lazy `budget_ledger` fixture**
- **Found during:** Task 2 (offline review fixtures)
- **Issue:** The plan required a `budget_ledger` fixture, but `src/agents/review/budget.py` and `BudgetLedger` are explicitly owned by plan 03-07.
- **Fix:** Added a per-test fixture name that lazily imports `BudgetLedger` when it exists and skips only tests that request it before plan 03-07 lands. This preserves dependency-injection shape without creating later-plan source.
- **Files modified:** `tests/agents/review/conftest.py`
- **Verification:** `PYTHONPATH=src .venv/bin/python -m pytest tests/agents/review --collect-only -q` collected without error; `.venv/bin/pytest tests/agents/review -q` passed.
- **Committed in:** `e816329`

**Total deviations:** 1 scope-preserving adjustment.
**Impact on plan:** No production scope creep. Later plan 03-07 can satisfy the fixture by adding the real `BudgetLedger`.

## Issues Encountered

- Import verification initially created `src/agents/review/__pycache__/`, which would have broken the "exactly `__init__.py`" acceptance criterion. The generated directory was removed and subsequent import verification used `PYTHONDONTWRITEBYTECODE=1`.
- Concurrent repo activity was observed: commit `29cf25b` for plan 03-04 landed between this plan's Task 2 and Task 3 commits. No conflict occurred and no unrelated files were reverted.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 03-06 through 03-14 can now import the review package, inject deterministic completion callables, build real multi-document corpora, and rely on CI to surface any test that starts requiring Databricks credentials.

## Self-Check: PASSED

- Created files exist: `src/agents/review/__init__.py`, `tests/agents/review/__init__.py`, `tests/agents/review/conftest.py`, `tests/agents/review/test_conftest_smoke.py`, `.github/workflows/test.yml`, this summary.
- Task commits found in git history: `1b4ea3f`, `e816329`, `247cfcd`.
- No accidental tracked-file deletions were reported by the per-task post-commit checks.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
