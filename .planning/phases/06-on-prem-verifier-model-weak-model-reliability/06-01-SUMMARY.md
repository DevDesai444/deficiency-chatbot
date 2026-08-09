---
phase: 06-on-prem-verifier-model-weak-model-reliability
plan: "01"
subsystem: test-scaffold
tags: [wave-0, nyquist, tdd, test-shells, d-14-baseline, reliability]
dependency_graph:
  requires: []
  provides:
    - "Wave-0 test scaffold: 7 pytest-collectable files before any implementation"
    - "D-14 Phase-3 baseline literals pinned (QWEN_POST_REPAIR_RATE=0.80, LLAMA_V1_POST_REPAIR_RATE=0.0)"
    - "Per-class DiscriminationAccuracyMetric shape (D-06b amendment 2026-08-09)"
    - "MATCHED_GT_IDS loaded from beta-measurement-summary.json (not hardcoded duplicate)"
    - "pytest.mark.integration registered in pyproject.toml"
  affects:
    - tests/unit/test_reliability.py
    - tests/unit/test_on_prem_guard.py
    - tests/unit/test_verdict_schema.py
    - tests/unit/test_config_verifier.py
    - tests/integration/test_nemotron_probe.py
    - tests/evals/test_verifier_probe.py
    - tests/evals/test_reliability_baseline.py
    - .planning/phases/06-on-prem-verifier-model-weak-model-reliability/06-VALIDATION.md
tech_stack:
  added: []
  patterns:
    - "Runtime importlib guard pattern: import inside test body, not at module level — keeps collection clean when modules don't exist yet"
    - "D-14 frozen-baseline literal pattern: module-level constants + self-documenting test that asserts exact values"
    - "MATCHED_GT_IDS from JSON: _load_matched_gt_ids() at module level with assert len==6"
key_files:
  created:
    - tests/unit/test_reliability.py
    - tests/unit/test_on_prem_guard.py
    - tests/unit/test_verdict_schema.py
    - tests/unit/test_config_verifier.py
    - tests/integration/test_nemotron_probe.py
    - tests/evals/test_verifier_probe.py
    - tests/evals/test_reliability_baseline.py
  modified:
    - .planning/phases/06-on-prem-verifier-model-weak-model-reliability/06-VALIDATION.md
    - pyproject.toml
decisions:
  - "Used runtime importlib guards (import inside test body) instead of module-level pytest.importorskip to ensure test items are collected even when target modules are absent"
  - "Registered pytest.mark.integration in pyproject.toml and excluded from default addopts to keep unit test fast-path clean"
  - "test_config_verifier.py created as the actual file name (plan had test_config.py as old name in Wave 0 checklist — corrected)"
metrics:
  duration_seconds: 532
  completed_date: 2026-08-09
  tasks_completed: 3
  files_created: 7
  files_modified: 3
---

# Phase 06 Plan 01: Wave-0 Test Scaffold Summary

Wave-0 test scaffold complete: 7 pytest-collectable shells for Phase 6 reliability/verifier work, D-14 Phase-3 baseline numbers pinned as literals, and 06-VALIDATION.md flipped to `nyquist_compliant: true`.

## What Was Built

Seven test files created as failing-but-collectable shells enforcing test-first discipline for Phase 6. All 46 test items collect via `pytest --collect-only` before any implementation code lands.

### Task 1: Unit test shells (4 files, 34 items)

**tests/unit/test_reliability.py** (13 items) — RELIABILITY-01/02/03 + D-09 + D-12:
- `test_guided_probe_caches`: detect-once invariant (single network round-trip)
- `test_guided_probe_bad_request_returns_false`: BadRequestError fail-safe
- `test_guided_probe_generic_exception_returns_false`: generic exception fail-safe
- `TestStrictCoerce` (8 cases): numeric/bool coercion + FIX 6 annotation-aware check (`test_str_numeric_field_not_coerced` — str field must NOT be coerced to int)
- `test_field_level_error_format`: field-name + type in reprompt message (RELIABILITY-02)
- `test_no_fabricated_verdict`: (None, ParseFailed) on malformed input (D-12)

**tests/unit/test_on_prem_guard.py** (9 items) — MODEL-01 / D-16 / FIX 4:
- 3 forbidden-model tests (claude, gpt-5, gemini): raise ValueError with "on-prem allow-list"
- 2 deny-substring tests (FIX 4): substring match catches claude/gpt variants not in explicit list
- 3 allow-list tests: Llama 70B, Nemotron 49B, None passthrough
- `test_allow_list_covers_detector_models`: ON_PREM_ALLOW_LIST >= DETECTOR_MODELS keys (FIX 4 single-source-of-truth)

**tests/unit/test_verdict_schema.py** (6 items) — D-07:
- KEEP + DOWNGRADE validation
- Enum case-sensitivity rejection
- Confidence out-of-range rejection
- `test_guided_schema_is_databricks_legal`: no prohibited keys (reuses inline walk logic)
- `test_guided_schema_is_stable`: byte-stability of guided_json cache key

**tests/unit/test_config_verifier.py** (6 items) — D-17 / FIX 4:
- verifier_model, MODEL_LINEAGE, verifier_max_repair_calls (xfail — Plan 02)
- nemotron in DETECTOR_MODELS (xfail — Plan 02)
- `test_on_prem_allow_list_imported_from_config`: ON_PREM_ALLOW_LIST is frozenset from config (FIX 4)

### Task 2: Integration + eval shells (3 files, 12 items)

**tests/integration/test_nemotron_probe.py** (5 items) — MODEL-02 / D-18 / D-06a:
All marked `@pytest.mark.integration` + `@pytest.mark.skipif(True, reason="D-20 gate")`.
- `test_nemotron_tool_call_returns_structured_tool_calls`: Pitfall 1 check (tool_calls not in content)
- `test_thinking_on_inflates_completion_tokens[on/off]`: data-collection parametrized (no tautology)
- `test_thinking_mode_token_split_is_detected`: definitive D-18 assertion (ON tokens > OFF)
- `test_tool_call_round_trip_verdict`: VERDICT guided_json round-trip conformance (D-06a)

**tests/evals/test_verifier_probe.py** (4 items) — D-06a / D-06b / D-18 (amended 2026-08-09):
- `MATCHED_GT_IDS` loaded from `beta-measurement-summary.json` via `_load_matched_gt_ids()` (not a hardcoded duplicate literal)
- `test_matched_gt_ids_loaded_from_json`: PASSES immediately — asserts 6 IDs + spot-checks A-09 + MS-01
- `DiscriminationAccuracyMetric`: per-class floors (KEEP-recall AND DOWNGRADE-rate), two-sided tripwire (`downgrade_ratio >= 0.90` and `keep_ratio >= 0.95`)
- `test_all_downgrade_stub_fails`: documents that all-DOWNGRADE stub MUST fail (skip pending full implementation)

**tests/evals/test_reliability_baseline.py** (3 items) — D-14:
Module-level literals (pinned 2026-08-08):
```
LLAMA_V1_PRE_REPAIR_RATE  = 0.0
LLAMA_V1_POST_REPAIR_RATE = 0.0
QWEN_PRE_REPAIR_RATE      = 0.0
QWEN_POST_REPAIR_RATE     = 0.80
```
- `test_baseline_numbers_are_locked_as_literals`: PASSES immediately — self-documenting freeze guard
- `test_post_hardening_llama_rate_below_baseline`: skip pending Wave 3
- `test_post_hardening_qwen_rate_below_baseline`: skip pending Wave 3

### Task 3: 06-VALIDATION.md flip

After confirming `pytest --collect-only` exits 0 for all 7 files (46 items):
- `nyquist_compliant: false` → `nyquist_compliant: true`
- `wave_0_complete: false` → `wave_0_complete: true`
- `**Approval:** pending` → `**Approval:** approved 2026-08-08`
- All 7 Wave 0 Requirements checklist items changed from `[ ]` to `[x]`

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 831fd6d | test | Wave-0 unit test shells — reliability, guard, schema, config (34 items) |
| fe66a8a | test | Wave-0 integration + eval shells + D-14 baseline literals (12 items) |
| cebd86b | chore | Flip 06-VALIDATION.md to nyquist_compliant |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level import guard caused 0 items collected from test_reliability.py and test_verdict_schema.py**
- **Found during:** Task 1 collection check
- **Issue:** `pytest.importorskip("schemas.llm")` succeeds (module exists) but `VERDICT = schemas_mod.VERDICT` raises `AttributeError` at import time because VERDICT is not yet in schemas/llm.py. `pytest.skip(allow_module_level=True)` caused 0 test items to be collected from the file — violating the `≥18 items` acceptance criterion.
- **Fix:** Moved all imports that might fail into `_require_*()` helper functions called inside each test body. Collection is always clean; tests skip at runtime. Final count: 34 items from 4 unit files.
- **Files modified:** tests/unit/test_reliability.py, tests/unit/test_verdict_schema.py

**2. [Rule 2 - Missing config] pytest.mark.integration not registered**
- **Found during:** Task 2 collection check
- **Issue:** `PytestUnknownMarkWarning` for `pytest.mark.integration` — mark not registered in pyproject.toml markers list.
- **Fix:** Added `"integration: live-endpoint test requiring Databricks/Nemotron; deselected by default."` to `markers` and updated `addopts` to `-m 'not slow and not integration'`.
- **Files modified:** pyproject.toml

**3. [Rule 1 - Bug] test_config.py vs test_config_verifier.py naming**
- **Found during:** Task 3 (Wave 0 checklist flip)
- **Issue:** 06-VALIDATION.md Wave 0 checklist listed `tests/unit/test_config.py` but the actual file created is `tests/unit/test_config_verifier.py` (following the plan's `files_modified` frontmatter).
- **Fix:** Corrected the checklist entry during the flip.
- **Files modified:** 06-VALIDATION.md

## Verification Results

All 9 post-completion verification checks pass:

1. `pytest --collect-only` exits 0, 46 items across 7 files
2. `test_baseline_numbers_are_locked_as_literals` PASSED
3. `test_matched_gt_ids_loaded_from_json` PASSED (6 IDs from JSON)
4. `grep LLAMA_V1_POST_REPAIR_RATE = 0.0 tests/` FOUND
5. `grep QWEN_POST_REPAIR_RATE = 0.80 tests/` FOUND
6. `nyquist_compliant: true` in 06-VALIDATION.md
7. `grep -c test_guided_schema_is_stable tests/unit/test_verdict_schema.py` = 1
8. `grep -c test_all_downgrade_stub_fails tests/evals/test_verifier_probe.py` = 3
9. `grep -c test_allow_list_covers_detector_models tests/unit/test_on_prem_guard.py` = 1

## Known Stubs

All stubs are intentional per the plan:
- `DiscriminationAccuracyMetric.measure()`: raises `NotImplementedError` — implement in Plan 06 Task 1
- `ConformanceRateMetric.measure()`: raises `NotImplementedError` — implement after Plan 05 (Nemotron live)
- `load_probe_samples()` `downgrade_expected`: empty list — populate in Wave 3 labeling
- `test_all_downgrade_stub_fails`: `pytest.skip(...)` — pending DiscriminationAccuracyMetric full implementation
- All `test_post_hardening_*` tests: `pytest.skip(...)` — pending reliability.py + probe replay in Wave 3

## Threat Flags

None — this plan creates test files and updates a validation document only. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced.

## Self-Check: PASSED

Files exist:
- FOUND: tests/unit/test_reliability.py
- FOUND: tests/unit/test_on_prem_guard.py
- FOUND: tests/unit/test_verdict_schema.py
- FOUND: tests/unit/test_config_verifier.py
- FOUND: tests/integration/test_nemotron_probe.py
- FOUND: tests/evals/test_verifier_probe.py
- FOUND: tests/evals/test_reliability_baseline.py

Commits exist:
- FOUND: 831fd6d
- FOUND: fe66a8a
- FOUND: cebd86b
