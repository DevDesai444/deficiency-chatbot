---
phase: 03-drive-loop-spike-go-no-go
plan: 11
subsystem: review-loop
tags: [tool-registry, pydantic, databricks, grounding, pytest]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: Tool schema derivation from 03-03
  - phase: 03-drive-loop-spike-go-no-go
    provides: Span reference parsing from 03-06
  - phase: 03-drive-loop-spike-go-no-go
    provides: Oracle seed tool from 03-09
provides:
  - Seven flat pydantic tool argument models
  - Deterministic Databricks-legal tool schema list
  - ToolRegistry dispatch with pre/post repair accounting and teaching rejections
  - Schema legality tests for verdict enum, flat span IDs, D-RI2 citation optionality, and cache-stable schemas
affects: [phase-03-review-loop, agent-tool-boundary, telemetry, grounding]

tech-stack:
  added: []
  patterns:
    - Pydantic arg models as the single source for model-visible schemas and validation
    - Static module-constant tool descriptions for D-LOOP4 cache stability
    - Loop-side DispatchResult carrying rendered tool results plus repair layer and breaker key

key-files:
  created:
    - src/agents/review/registry.py
    - tests/agents/review/test_tool_schemas.py
    - .planning/phases/03-drive-loop-spike-go-no-go/03-11-SUMMARY.md
  modified: []

key-decisions:
  - "Span IDs cross the model boundary as flat strings and are resolved through parse_span_ref with explicit expected store."
  - "Tool descriptions are static module constants; corpus-specific data stays out of schemas."
  - "run_oracles_tool is imported lazily inside dispatch to avoid the existing direct-import cycle with tools.__init__."

patterns-established:
  - "ToolRegistry.schemas() returns the fixed seven-tool order: search_corpus, open_doc, get_section, read_guideline, follow_reference, emit_finding, run_oracles."
  - "render_rejection surfaces reason, hint, preview, and handle as the model-facing correction message."
  - "optional_param_near_miss tracks Pitfall-6 optional-argument shape drift without changing the locked D-RI2 surface."

requirements-completed: [AGENT-01, DETECT-04]

duration: 19 min
completed: 2026-08-03
---

# Phase 03 Plan 11: Tool Registry Summary

**Seven model-facing review tools now derive legal Databricks schemas from the same pydantic models that validate and dispatch their arguments.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-03T10:25:27Z
- **Completed:** 2026-08-03T10:44:04Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `ToolRegistry` with seven flat arg models and deterministic schema derivation through `build_tool_schema`.
- Implemented dispatch through existing tool functions, including `parse_structured` repair, explicit span-store resolution, budget hooks, and rendered `ToolRejected` feedback.
- Added 10 schema tests covering all Databricks restrictions, verdict enum enforcement, string span IDs, static schema determinism across corpora, required fields, and D-RI2 optional citation.
- Registered the Pitfall-6 optional-parameter near-miss counter and concrete 7-to-11-tool fallback text in `registry.py`.

## Task Commits

Each task's implementation is represented in the commits below:

1. **Task 1: Define the seven arg models and derive their schemas** - `a2e5b81` (feat)
2. **Task 2: Implement dispatch with repair accounting and rejection rendering** - `a2e5b81` (feat)
3. **Task 3: Assert schema restrictions and Pitfall-6 fallback** - `aff9efb` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agents/review/registry.py` - New tool registry, flat arg models, schema list, dispatch, rejection rendering, budget hooks, and Pitfall-6 counter/fallback.
- `tests/agents/review/test_tool_schemas.py` - New 10-test schema legality and contract suite.
- `.planning/phases/03-drive-loop-spike-go-no-go/03-11-SUMMARY.md` - Plan completion record.

## Verification

| Command | Result |
|---|---|
| `grep -c "class SearchCorpusArgs\|class OpenDocArgs\|class GetSectionArgs\|class ReadGuidelineArgs\|class FollowReferenceArgs\|class EmitFindingArgs\|class RunOraclesArgs" src/agents/review/registry.py` | `7` |
| `grep -c ": SpanID" src/agents/review/registry.py` | `0` |
| `grep -c "submission_span_id: str\|rule_span_id: str" src/agents/review/registry.py` | `2` |
| `grep -c "verdict: ComplianceVerdict" src/agents/review/registry.py` | `1` |
| `PYTHONPATH=src .venv/bin/python - <<'PY' ... ToolRegistry.schemas ... assert_databricks_legal ... PY` | `7` schemas; all legal |
| Task 2 grep checks | `dispatch/render_rejection=2`; `parse_structured=2`; `expect="submission"=1`; `expect="rule"=1`; `hint/preview/handle=6`; no range slicing/truncation; no `raise`; repair/turn markers `9` |
| `.venv/bin/pytest tests/agents/review/test_repair_accounting.py -x -q` | `4 passed, 5 warnings in 0.41s` |
| `PYTHONPATH=src .venv/bin/python - <<'PY' ... render_rejection ... PY` | `render ok` |
| `.venv/bin/pytest tests/agents/review/test_tool_schemas.py -x -q` | `10 passed, 5 warnings in 0.21s` |
| `.venv/bin/pytest tests/agents/review/test_tool_schemas.py::test_verdict_enum -x -q` | `1 passed, 5 warnings in 0.09s` |
| Task 3 grep checks | verdict test `1`; `assert_databricks_legal` used `2`; no local `_walk` redefinition; D-RI2 test `1`; deterministic schema test `1`; `optional_param_near_miss` `5`; fallback block `1`; concrete fallback tool names `2` |
| `.venv/bin/pytest tests/agents/review tests/tools -q` | `125 passed, 5 warnings in 120.49s` |
| `.venv/bin/pytest tests/agents/review tests/unit -q` | `127 passed, 11 skipped, 6 warnings in 10.67s` |
| `.venv/bin/pytest tests/agents/review tests/unit tests/tools -q` | `195 passed, 11 skipped, 6 warnings in 106.02s` |
| `.venv/bin/pytest -q` | `427 passed, 11 skipped, 6 warnings in 408.34s` |

## Decisions Made

- Used string-only `submission_span_id` and `rule_span_id` fields in `EmitFindingArgs`; dispatch converts them to store-specific `SpanID`s via `parse_span_ref`.
- Returned rendered strings from dispatch so future loop code can append tool results directly without reinterpreting object shapes.
- Kept schema descriptions as static constants and proved schema bytes are identical across different corpora.
- Preserved the locked `read_guideline(citation=None)` enumerate surface and covered it with an explicit regression test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Avoided direct `run_oracles_tool` import cycle**
- **Found during:** Task 1 (registry import/schema derivation)
- **Issue:** Importing `agents.review.oracles_tool` directly triggers a pre-existing cycle: `oracles_tool -> tools.errors -> tools.__init__ -> agents.review.oracles_tool`.
- **Fix:** `ToolRegistry` imports `run_oracles_tool` lazily only when dispatching the `run_oracles` tool.
- **Files modified:** `src/agents/review/registry.py`
- **Verification:** `PYTHONPATH=src .venv/bin/python` imported `ToolRegistry` and derived all seven schemas successfully.
- **Committed in:** `a2e5b81`

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** Scope stayed inside `registry.py`; the seventh tool remains dispatchable without changing shared `tools.__init__` during parallel Wave 4 work.

## Issues Encountered

- An initial broad pytest run was started concurrently with another broad run and hit a shared `data/rulebook_cache` temp-file race in `test_spanref_roundtrip.py`. The same gate passed when rerun sequentially, and no code change was required.
- The production registry work for Tasks 1 and 2 landed in one commit because dispatch depends directly on the same validating arg models and schema registry created in Task 1.

## Known Stubs

None. Stub scan found only intentional empty-string defaults for optional `rule_citation` and `requirement_id` metadata in `EmitFindingArgs`; these are not UI placeholders or unwired data sources.

## Authentication Gates

None.

## Threat Flags

None. The new model-authored JSON, span-ID boundary, rejection-message, and static-schema surfaces are the plan-registered trust boundaries and are covered by tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 03-13 and 03-14 can consume `ToolRegistry.schemas()` for the static tool prefix and call `dispatch()` for repaired, budget-accounted tool results. Telemetry can read `repair_layer`, rejection code/half, and `optional_param_near_miss` without inventing a second accounting path.

## Self-Check: PASSED

- Found created files: `src/agents/review/registry.py`, `tests/agents/review/test_tool_schemas.py`, `.planning/phases/03-drive-loop-spike-go-no-go/03-11-SUMMARY.md`
- Found task commits in git history: `a2e5b81`, `aff9efb`
- Full suite and plan-level verification commands above passed.
- No accidental tracked-file deletions were reported after task commits.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
