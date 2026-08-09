---
phase: "06"
plan: "04"
subsystem: llm-reliability-integration
tags: [reliability, on-prem-guard, guided-decode, d15, d16, d08, strict-coerce]
dependency_graph:
  requires: ["06-01", "06-03"]
  provides: ["D-16-guard", "D-08-guided-decode", "D-15-dispatch-hint", "D-15-strict-coerce"]
  affects: ["06-05", "06-06", "phase-7-verifier"]
tech_stack:
  added: []
  patterns:
    - "function-local import to prevent circular imports (reliability ↔ structured ↔ client)"
    - "deny-first substring guard before allow-list exact check (defense-in-depth)"
    - "auto-inject guided decode at single wiring point (all tool calls inherit)"
key_files:
  created: []
  modified:
    - src/llm/client.py
    - src/agents/review/registry.py
    - src/llm/structured.py
    - tests/unit/test_on_prem_guard.py
    - tests/unit/test_reliability.py
    - tests/unit/test_config_verifier.py
decisions:
  - "Function-local imports used in both client.py (reliability functions) and structured.py (strict_coerce) to break the circular import chain: client → reliability → structured → client"
  - "D-16 guard at get_client(model=) level only — internal callers (chat_completion_full, chat_completion_tools) call get_client() without model arg; model-id validation does not apply to implicit resolution via get_settings().resolved_llm_model"
  - "Deny-first substring check runs BEFORE exact allow-list: catches new external model naming variants without allow-list updates"
  - "databricks-claude-opus-4-8 confirmed as the LIVE one-string-away misconfiguration surface; added as an explicit test target"
metrics:
  duration_minutes: 45
  completed_date: "2026-08-09"
  tasks_completed: 4
  files_modified: 6
---

# Phase 06 Plan 04: Reliability Integration (client.py + registry.py + structured.py) Summary

Wire the reliability module (Plan 03) into three integration points: D-16 on-prem guard with deny-first substring check in client.py, guided decode auto-inject in chat_completion_tools, field-level reprompt import in registry.dispatch, and strict_coerce additive insertion in structured.py before pydantic validate.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0 (pre) | Remove 5 stale xfail markers | f21eace | tests/unit/test_config_verifier.py |
| 1 | client.py D-16 guard + deny-first + guided decode | 0850806 | src/llm/client.py, tests/unit/test_on_prem_guard.py, tests/unit/test_reliability.py |
| 2 | registry.dispatch field-level hint (D-15) | 1774ea2 | src/agents/review/registry.py |
| 3 | structured.py strict_coerce before model_validate (D-15) | a2c6886 | src/llm/structured.py |

## What Was Built

### Task 0: Stale xfail Marker Removal (test_config_verifier.py)
Removed 5 `@pytest.mark.xfail(...)` decorators from `tests/unit/test_config_verifier.py`:
1. `test_verifier_model_role_resolves_nemotron`
2. `test_lineage_nemotron_is_nemotron_on_llama`
3. `test_lineage_llama_is_llama`
4. `test_verifier_max_repair_calls_default_is_1`
5. `test_nemotron_in_detector_models`

All 6 tests in test_config_verifier.py now pass (0 xpassed, 0 xfail).

### Task 1: client.py — D-16 Allow-List Guard + Deny-First + Guided Decode

**D-16 on-prem guard — `get_client(model=...)`:**
- Added `model: str | None = None` parameter to `get_client`
- Imported `ON_PREM_ALLOW_LIST` from `config.py` at module level (single source of truth; FIX 4; no frozenset literal in client.py)
- Layer 1 (deny-first): `_EXTERNAL_FAMILY_SUBSTRINGS = ("claude", "gpt", "gemini")` — case-insensitive substring match before the allow-list check. Catches `databricks-claude-opus-4-8` (a LIVE endpoint in this workspace), `claude-3-opus-custom`, `gpt-4o-local-fork`, etc.
- Layer 2 (exact allow-list): `model not in ON_PREM_ALLOW_LIST` → ValueError with self-documenting message citing 21 CFR Part 11

**D-08 guided decode auto-inject — `chat_completion_tools`:**
- Added `extra_body: dict | None = None` and `guided_model_cls: type[BaseModel] | None = None` parameters
- Function-local imports of `supports_guided_json` and `build_guided_extra_body` from `llm.reliability` (prevents circular import: `client.py → reliability.py → structured.py → client.py`)
- Auto-inject: `if extra_body is None and guided_model_cls is not None → supports_guided_json probe → build_guided_extra_body(guided_model_cls)` → `kwargs["extra_body"]`
- Explicit caller-supplied `extra_body` always wins (caller override)
- `build_guided_extra_body_from_tools` does NOT exist (Pitfall 7 guard)

**test_on_prem_guard.py:**
- Removed capability-keyed skip guard (`pytestmark = pytest.mark.skipif + _guard_implemented + import inspect`)
- Added `test_forbidden_live_claude_opus_endpoint_raises` for the LIVE `databricks-claude-opus-4-8` endpoint
- **10 tests run, 10 pass, 0 skipped**

**test_reliability.py:**
- Added `test_guided_tools_injects_extra_body` — D-08 wiring proof; captures kwargs passed to OpenAI mock and asserts `extra_body` with `structured_outputs` key is present

### Task 2: registry.py — Field-Level Hint (D-15)

Added `from llm.reliability import format_field_level_reprompt_from_json` at top of registry.py.

In `dispatch`, on the `post_repair_malformed` path:
```python
field_hint = format_field_level_reprompt_from_json(error, spec.model)
rejected = ToolRejected(..., hint=field_hint)
```

The generic `"send a JSON object matching this tool's schema exactly"` string is gone from the `hint=` assignment. No local `_build_field_hint` re-implementation (D-15 compliant).

### Task 3: structured.py — strict_coerce Before model_validate (D-15)

Inside `parse_structured`, immediately before `model_cls.model_validate(obj)`:
```python
from llm.reliability import strict_coerce  # noqa: PLC0415 — intentional function-local
obj = strict_coerce(obj, model_cls)  # D-15
```

Function-local import breaks the `reliability.py → structured.py → reliability.py` circle. The L1-L6 ladder is UNCHANGED — zero deletions, only 8 lines added.

## Caller Audit (D-16 guard coverage)

**`get_client(` call sites in src/:**
| File | Line | Model arg? | Guard coverage |
|------|------|-----------|----------------|
| src/llm/client.py:174 | `chat_completion_full` → `get_client()` | No (implicit) | NOT guarded — model resolved via `get_settings().resolved_llm_model`; guard only fires on explicit `get_client(model=...)` calls |
| src/llm/client.py:249 | `chat_completion_tools` → `get_client()` | No (implicit) | NOT guarded — same as above |

**`chat_completion_tools(` call sites in src/:**
| File | Line | Model arg? | Guard coverage |
|------|------|-----------|----------------|
| src/evals/run.py:634 | `chat_completion_tools(messages, tools, model=resolved_model, ...)` | Yes (resolved_model) | `resolved_model` comes from `resolve_detector_model()` which filters via `DETECTOR_MODELS` — functionally covered, but not via get_client(model=) guard |

**OpenAI client bypass (guard does NOT cover these paths — Phase 7 follow-up):**
| File | Bypass type | Risk |
|------|-------------|------|
| src/databricks/serving.py:20-30 | `get_llm_client()` creates OpenAI directly without D-16 guard | MEDIUM — uses `_DB_MODELS` dict which only contains on-prem IDs, but the guard is absent |
| src/retrieval/vector_search.py:24 | `client = OpenAI(...)` directly | LOW — embedding endpoint, not an LLM model route |

**Conclusion:** The D-16 guard at `get_client(model=...)` is the explicit-model-selection defense. The implicit model-resolution path (via `get_settings().resolved_llm_model`) and the `databricks/serving.py` bypass are NOT covered. These are noted as Phase 7 follow-ups. The guard correctly fires for all explicit model-id selections.

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `grep -c "from config import ON_PREM_ALLOW_LIST" src/llm/client.py` → 1 | PASS |
| `grep -c "frozenset" src/llm/client.py` → 0 | PASS |
| `grep -c "_EXTERNAL_FAMILY_SUBSTRINGS" src/llm/client.py` ≥ 1 | PASS (2) |
| `grep -c "supports_guided_json" src/llm/client.py` ≥ 1 | PASS (4) |
| `grep -c "build_guided_extra_body_from_tools" src/llm/client.py` → 0 | PASS |
| `grep -c "build_guided_extra_body" src/llm/client.py` ≥ 1 | PASS (7) |
| `grep -c "guided_model_cls" src/llm/client.py` ≥ 2 | PASS (6) |
| `grep -c "extra_body" src/llm/client.py` ≥ 2 | PASS (15) |
| `grep -c "regulated pharma" src/llm/client.py` ≥ 1 | PASS (1) |
| `grep -c "from llm.reliability import format_field_level_reprompt_from_json" src/agents/review/registry.py` → 1 | PASS |
| `grep -c "_build_field_hint" src/agents/review/registry.py` → 0 | PASS |
| `grep -c "field_hint" src/agents/review/registry.py` ≥ 2 | PASS (2) |
| `grep -c "strict_coerce" src/llm/structured.py` ≥ 2 | PASS (3) |
| `grep -c "^from llm.reliability import strict_coerce" src/llm/structured.py` → 0 | PASS |
| `python -c "from llm.structured import parse_structured; print('OK')"` exits 0 | PASS |
| `python -c "import llm.reliability; import llm.structured; print('OK')"` exits 0 | PASS |
| `grep -c "skipif" tests/unit/test_on_prem_guard.py` → 0 | PASS |
| `grep -c "_guard_implemented" tests/unit/test_on_prem_guard.py` → 0 | PASS |
| `pytest tests/unit/test_on_prem_guard.py -rs -q` → 10 passed, 0 skipped | PASS |
| `pytest tests/unit/ -x -q` exits 0 | PASS (110 passed, 12 skipped) |
| `grep -c "test_guided_tools_injects_extra_body" tests/unit/test_reliability.py` → 1 | PASS |
| `git diff src/llm/structured.py` shows ZERO deletions in ladder logic | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import — reliability module imports**

- **Found during:** Task 1 implementation
- **Issue:** `client.py` module-level imports of `supports_guided_json` / `build_guided_extra_body` from `reliability.py` would close the circular import chain: `client.py → reliability.py → structured.py → client.py` (structured.py imports `chat_completion_full` from client.py)
- **Fix:** Used function-local imports of reliability functions inside `chat_completion_tools` (identical pattern to how Task 3 handles `strict_coerce` in `structured.py`)
- **Files modified:** src/llm/client.py
- **Commit:** 0850806

**2. [Rule 1 - Precision] grep-gate failures in test strings in comments**

- **Found during:** Task 1 acceptance criteria verification
- **Issue:** Comments in client.py docstrings contained `frozenset` (the word "frozenset literal") and `build_guided_extra_body_from_tools` (the forbidden helper name in the Pitfall 7 note), causing the grep acceptance criteria to fail (grep -c counts ALL occurrences including comments)
- **Fix:** Replaced "duplicate frozenset literal" with "duplicate set literal" in docstring; replaced "build_guided_extra_body_from_tools MUST NOT exist" with "Any raw-schema helper bypassing this is explicitly forbidden" in docstring
- **Files modified:** src/llm/client.py
- **Commit:** 0850806

**3. [Plan addition] Live endpoint deny test added (reviewer constraint)**

- **Found during:** Task 1 — reviewer's sharpened constraint
- **Issue:** The original 9 tests in test_on_prem_guard.py did not include a test against the confirmed-live endpoint `databricks-claude-opus-4-8`
- **Fix:** Added `test_forbidden_live_claude_opus_endpoint_raises` — tests that the deny-first substring check blocks the real one-string-away misconfiguration surface
- **Files modified:** tests/unit/test_on_prem_guard.py
- **Commit:** 0850806

## Phase 7 Follow-ups (recorded, not fixed — out of scope)

1. **`src/databricks/serving.py:get_llm_client()`** creates an OpenAI client directly without the D-16 guard. Uses `_DB_MODELS` dict which only maps to on-prem IDs, but the guard is absent. Phase 7 should either use `get_client()` from `llm.client` or add the guard here.

2. **`src/retrieval/vector_search.py`** creates an OpenAI client for embedding endpoint — not an LLM model route but guard is absent. Low risk; note for Phase 7 audit.

3. **`chat_completion_full` / `chat_completion_tools`** call `get_client()` WITHOUT a model arg — implicit model resolution via `get_settings().resolved_llm_model` bypasses the D-16 guard. Only explicit `get_client(model=...)` calls are guarded. Phase 7 could route implicit resolution through the guard if a model arg is always available.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: guard-bypass | src/databricks/serving.py | `get_llm_client()` creates OpenAI client bypassing D-16 guard — covered by _DB_MODELS but no explicit guard |

## Known Stubs

None — all implemented functions are wired to production logic.

## Self-Check: PASSED

Files exist:
- src/llm/client.py: FOUND
- src/agents/review/registry.py: FOUND
- src/llm/structured.py: FOUND
- tests/unit/test_on_prem_guard.py: FOUND
- tests/unit/test_reliability.py: FOUND
- tests/unit/test_config_verifier.py: FOUND

Commits exist:
- f21eace: FOUND (test: remove 5 stale xfail markers)
- 0850806: FOUND (feat: client.py D-16 + guided decode)
- 1774ea2: FOUND (feat: registry.dispatch field-level hint)
- a2c6886: FOUND (feat: structured.py strict_coerce)
