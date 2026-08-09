---
phase: "06-on-prem-verifier-model-weak-model-reliability"
plan: "03"
subsystem: "reliability"
tags: ["reliability", "verdict-model", "on-prem-guard", "coercion", "guided-json", "D-07", "D-08", "D-09", "D-10", "D-11", "D-12", "D-13", "D-15", "D-16", "D-17"]
dependency_graph:
  requires:
    - "06-01"  # Wave-0 test shells were created here
  provides:
    - "06-04"  # Plan 04 wires reliability.py into client.py / registry.py
    - "06-05"  # Plan 05 live probe suite uses reliability + verifier_model config
  affects:
    - "src/schemas/llm.py"
    - "src/llm/reliability.py"
    - "src/config.py"
    - "src/databricks/serving.py"
tech_stack:
  added:
    - "src/llm/reliability.py — new shared reliability module (D-15)"
    - "VerdictChoice(str, Enum) + VERDICT(BaseModel) in schemas/llm.py (D-07)"
    - "ON_PREM_ALLOW_LIST frozenset in config.py (D-16 single source of truth)"
    - "MODEL_LINEAGE dict in config.py (D-17)"
  patterns:
    - "instance XOR ParseFailed typed-sentinel return contract (D-12)"
    - "detect-once capability probe with module-level cache (D-09)"
    - "annotation-aware strict coercion (FIX 6 — str fields never coerced to int)"
    - "field-level ValidationError reprompt messages (RELIABILITY-02)"
key_files:
  created:
    - "src/llm/reliability.py"
  modified:
    - "src/schemas/llm.py"
    - "src/config.py"
    - "src/databricks/serving.py"
decisions:
  - "D-07: VERDICT model with VerdictChoice enum (KEEP|DOWNGRADE), confidence[0,1], rationale, grounding_span"
  - "D-09: detect-once probe cached per served-model-name; fail-safe on BadRequestError and generic Exception"
  - "D-11: strict_coerce annotation-aware — numeric/bool coercion only when field annotation matches; enums pass-through"
  - "D-12: coerce_and_validate returns VERDICT XOR ParseFailed; never fabricates a verdict"
  - "D-13: FIX 5 — coerce_and_validate has no live LLM call; ParseFailed.reason carries reprompt for Phase 7 caller"
  - "D-15: reliability.py is single shared module for both registry.dispatch and structured.py"
  - "D-16: ON_PREM_ALLOW_LIST defined once in config.py (frozenset from DETECTOR_MODELS); client.py imports it"
  - "D-17: verifier_model property returns nemotron-super-49b-v1_5 on Databricks; MODEL_LINEAGE tags all on-prem endpoints"
  - "FIX 6: _is_numeric_annotation / _is_bool_annotation helpers guard coercion by annotation type, not value heuristic"
metrics:
  duration: "~30 minutes"
  completed: "2026-08-09"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
---

# Phase 06 Plan 03: Shared Reliability Module + VERDICT Model + Config Additions Summary

**One-liner:** VERDICT pydantic model with strict enum enforcement; reliability.py with annotation-aware strict coercion, detect-once guided-json probe, field-level reprompt formatters, and XOR ParseFailed contract; verifier_model/MODEL_LINEAGE/ON_PREM_ALLOW_LIST single-sourced in config.py; Nemotron endpoint id in serving.py.

## What Was Built

### Task 1: VERDICT model + reliability.py (commit c4346bb)

**src/schemas/llm.py** — added immediately after ParseFailed:
- `VerdictChoice(str, Enum)` with KEEP and DOWNGRADE values (case-sensitive; D-11)
- `VERDICT(BaseModel)` with four fields: `verdict: VerdictChoice`, `confidence: float = Field(ge=0.0, le=1.0)`, `rationale: str`, `grounding_span: str`

**src/llm/reliability.py** (318 lines, new file) — D-15 shared reliability module:
- `supports_guided_json(client, model)` — detect-once capability probe (D-09); caches per served-model-name; catches BadRequestError (unsupported) and generic Exception (fail-safe)
- `build_guided_extra_body(model_cls)` — routes through `tool_schema_for_databricks` (never raw `model_json_schema`); produces `{"structured_outputs": {"json": schema}}`
- `_is_numeric_annotation(annotation)` — FIX 6 helper; returns True for int/float including Optional[int/float]
- `_is_bool_annotation(annotation)` — FIX 6 helper; returns True for bool including Optional[bool]
- `strict_coerce(raw_args, model_cls)` — annotation-aware lossless coercion (D-11): numeric-string to number only when annotation is int/float; bool-string only when bool; enum fields pass-through with near-misses logged; single-key wrapper unwrap when key == class name
- `format_field_level_reprompt(error, model_cls)` — builds field-level ValidationError reprompt with field name and expected type (RELIABILITY-02)
- `format_field_level_reprompt_from_json(err_json, model_cls)` — companion for callers holding a JSON error string (registry.py path; D-15)
- `coerce_and_validate(raw_args, model_cls, retries_remaining=1)` — D-12/D-13: accepts dict or JSON string; returns (instance, None) XOR (None, ParseFailed); no live LLM call; layer="reliability-L3" when retries remain, "reliability-L4" when exhausted

### Task 2: config.py additions + serving.py Nemotron key (commit 4e65fb6)

**src/config.py** — four surgical additions:
- `verifier_max_repair_calls: int = 1` — D-13 config knob alongside `structured_output_max_repair_calls`
- `verifier_model` property — returns `"nemotron-super-49b-v1_5"` on Databricks, falls back to `detector_model` in local dev (D-17)
- Nemotron + fine-tunes added to `DETECTOR_MODELS` dict
- `MODEL_LINEAGE: dict[str, str]` — lineage tags: llama, qwen, nemotron-on-llama (D-17)
- `ON_PREM_ALLOW_LIST: frozenset[str] = frozenset(DETECTOR_MODELS.keys())` — single source of truth (D-16/FIX 4)

**src/databricks/serving.py** — one addition:
- `"nemotron": "nemotron-super-49b-v1_5"` in `_DB_MODELS` (D-01/D-03; resolve_model unchanged)

## Test Results

```
pytest tests/unit/test_reliability.py tests/unit/test_verdict_schema.py tests/unit/test_config_verifier.py -x -q
...................XXXXX.
20 passed, 5 xpassed in 0.39s

pytest tests/unit/test_on_prem_guard.py -v
9 skipped in 0.35s  (correctly stays skipped — Plan 06-04 wiring not yet done)
```

The 5 `xpassed` results are the `test_config_verifier.py` tests marked `@pytest.mark.xfail(strict=False, ...)` for the config.py additions this plan implements. xfail to xpass is correct: the implementation is in, the shells now pass.

## Deviations from Plan

**1. [Rule 2 — Missing critical functionality] coerce_and_validate accepts JSON strings**

- **Found during:** Task 1 — reading `test_no_fabricated_verdict`, which passes `bad_raw` as a JSON string
- **Issue:** The plan signature showed `raw_args: dict`, but the test passes a string. Without handling this, the test would fail on dict attribute access
- **Fix:** Extended `raw_args` type to `dict | str`; JSON string inputs are parsed via `_json.loads` before processing; JSON parse failure returns `ParseFailed(layer="reliability-L2")` so the XOR contract holds
- **Files modified:** `src/llm/reliability.py`
- **Commit:** c4346bb

**2. [Rule 2 — Missing critical functionality] Fine-tune model IDs added to DETECTOR_MODELS and ON_PREM_ALLOW_LIST**

- **Found during:** Task 2 — D-16 states ON_PREM_ALLOW_LIST >= DETECTOR_MODELS (single source); the fine-tune endpoints `defpredict-suggestor` and `defpredict-evaluator` are in `serving.py` but were absent from `DETECTOR_MODELS`. Without them, Plan 04's allow-list guard would reject calls to fine-tuned endpoints
- **Fix:** Added `defpredict-suggestor`, `defpredict-evaluator`, and `databricks-meta-llama-3-1-8b-instruct` to `DETECTOR_MODELS`; they flow into `ON_PREM_ALLOW_LIST` automatically
- **Files modified:** `src/config.py`
- **Commit:** 4e65fb6

## Known Stubs

None. All exported functions are fully implemented. VERDICT fields are required. ON_PREM_ALLOW_LIST is derived from the real DETECTOR_MODELS dict.

## Threat Flags

None beyond the threat model in the plan. No new network endpoints or auth paths introduced. The Nemotron endpoint id in `_DB_MODELS` is routing metadata only; the actual allow-list guard is Plan 06-04.

## Self-Check: PASSED

Files exist:
- `src/llm/reliability.py`: YES (318 lines, all 6 exports present)
- `src/schemas/llm.py`: YES (VERDICT + VerdictChoice added)
- `src/config.py`: YES (verifier_model property, MODEL_LINEAGE, ON_PREM_ALLOW_LIST, verifier_max_repair_calls added)
- `src/databricks/serving.py`: YES (nemotron key added)

Commits:
- c4346bb — feat(06-03): VERDICT model + reliability.py foundation
- 4e65fb6 — feat(06-03): config verifier_model + MODEL_LINEAGE + ON_PREM_ALLOW_LIST + serving Nemotron key

Invariants:
- `ON_PREM_ALLOW_LIST >= set(DETECTOR_MODELS)`: PASS
- `resolve_model("nemotron") == "nemotron-super-49b-v1_5"`: PASS
- No circular import on `import llm.reliability`: PASS
- `tool_schema_for_databricks(VERDICT)` is Databricks-legal: PASS (test_guided_schema_is_databricks_legal)
- `test_on_prem_guard.py` remains skipped (not green): PASS
