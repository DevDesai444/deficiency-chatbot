---
phase: 03-drive-loop-spike-go-no-go
plan: 03
subsystem: llm
tags: [openai, databricks, tools, schemas]
requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: grounded tool contracts
provides:
  - Tool-calling chat turn client
  - Databricks-legal pydantic tool-schema derivation
  - Dependency hygiene for the loop path
affects: [phase-03, agent-loop, budget]
tech-stack:
  added: []
  patterns: [sibling LLM client entry points, derived tool schemas]
key-files:
  created:
    - tests/unit/test_tool_schema_derivation.py
  modified:
    - src/llm/client.py
    - src/llm/structured.py
    - pyproject.toml
    - .planning/STATE.md
key-decisions:
  - "Tool turns are a sibling client path and do not alter chat_completion_full."
  - "Tool schemas inline refs before reusing the hardened sanitizer."
requirements-completed: [AGENT-01]
duration: 0h
completed: 2026-08-03
---

# Phase 03 Plan 03: Tool-Calling Transport Summary

**LLM transport can now return tool calls, raw assistant messages, and measured usage while deriving legal tool schemas from pydantic models.**

## Performance

- **Duration:** existing task commit plus final task completions in this session
- **Started:** 2026-08-03
- **Completed:** 2026-08-03
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `ChatTurn` and `chat_completion_tools()` with the same retry/rate-limit handling used by `chat_completion_full`.
- Added `_inline_refs`, `tool_schema_for_databricks`, and `build_tool_schema` beside the existing structured-output path.
- Removed dead AutoGen pins, raised the OpenAI SDK floor to `>=2.40`, and corrected the stale STATE premise about the detector redesign.

## Task Commits

1. **Task 1: Add tool-calling chat turn client** - `3e4f0e8`
2. **Task 2: Derive Databricks tool schemas** - `4e68d0f`
3. **Task 3: Clean loop dependency hygiene** - `b2c7a25`

## Files Created/Modified

- `src/llm/client.py` - Adds `ChatTurn` and `chat_completion_tools()`.
- `src/llm/structured.py` - Adds Databricks-legal tool schema derivation.
- `tests/unit/test_tool_schema_derivation.py` - Asserts prohibited schema keys are removed, including a negative control.
- `pyproject.toml` - Removes AutoGen pins and raises the OpenAI SDK floor.
- `.planning/STATE.md` - Records that the detector redesign is committed and left as the baseline arm.

## Decisions Made

The response-format path remains unchanged; tool schemas use a sibling derivation path because Databricks prohibits `$ref` in tool schemas while response format still preserves `$defs`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Later loop and registry plans can call the model with `tools=` and derive endpoint-safe tool definitions from the same pydantic models that validate tool arguments.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
