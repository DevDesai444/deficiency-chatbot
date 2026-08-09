---
phase: "06"
plan: "05-DEPLOY-FIX"
subsystem: nemotron-deploy
tags: [vllm, databricks-serving, mlflow-pyfunc, on-prem, deploy-fix]
dependency_graph:
  requires: [06-05-DEPLOY-RESEARCH.md]
  provides: [working-nemotron-deploy-script, dual-identity-fix]
  affects: [notebooks/deploy_nemotron.py, src/databricks/serving.py, src/config.py]
tech_stack:
  added: []
  patterns: [mlflow-pyfunc-entrypoint, relative-artifact-key-paths, databricks-endpoint-name-routing]
key_files:
  modified:
    - notebooks/deploy_nemotron.py
    - src/databricks/serving.py
    - src/config.py
    - tests/unit/test_config_verifier.py
decisions:
  - "verifier_model returns endpoint name defpredict-nemotron not vLLM served-model-name"
  - "DETECTOR_MODELS keeps both endpoint name and served-model-name entries for allow-list coverage"
  - "_is_capacity_denial broadened to include workload_type not-supported tier-rejection"
metrics:
  duration: "~15 minutes"
  completed: "2026-08-09"
  tasks_completed: 1
  files_modified: 4
---

# Phase 06 Plan 05-DEPLOY-FIX: Nemotron Deploy Fix Summary

**One-liner:** Fixed two hard deploy bugs (Volume path in vLLM entrypoint; probe model= must be endpoint name) plus config dual-identity, fallback rider broadening, and test updates so a subsequent register+deploy stands up a working Nemotron endpoint.

---

## What Was Fixed

### Bug A: /Volumes path in vLLM entrypoint (Risk 2 — already materialized)

**Root cause:** `VLLM_CMD` and `VLLM_CMD_BF16` used `--model {NEMOTRON_VOLUME_DIR}` (absolute `/Volumes/defpredict/main/artifacts/nemotron-49b`). Databricks serving containers have no FUSE mount for `/Volumes/` — vLLM would fail at startup with "model path not found", endpoint reaches FAILED state.

**Fix:** Both commands changed to `--model model_dir` (the MLflow artifact key name, which is the relative path the serving container sees). Same fix applied to `--tool-parser-plugin`: `{NEMOTRON_VOLUME_DIR}/llama_nemotron_toolcall_parser_no_streaming.py` → `model_dir/llama_nemotron_toolcall_parser_no_streaming.py`.

The `artifacts={"model_dir": NEMOTRON_VOLUME_DIR}` upload is unchanged — that copies the 93GB weights into the MLflow artifact store during `register_model()`.

### Bug B: probe() model= routing through Databricks (Risk 3 — already materialized)

**Root cause:** All three probe calls used `model=SERVED_MODEL_NAME` (`"nemotron-super-49b-v1_5"`). Databricks serving gateway routes by endpoint name, not vLLM served-model-name. These calls would fail with 404/"model not found" from the Databricks proxy.

**Fix:** All probe calls changed to `model=ENDPOINT_NAME` (`"defpredict-nemotron"`). Probe 1, Probe 2 (turn_on + turn_off), Probe 3 — all four call sites updated.

### Fix B: Dual-identity — serving.py + config.py

- `serving._DB_MODELS["nemotron"]`: `"nemotron-super-49b-v1_5"` → `"defpredict-nemotron"` (the routable endpoint name)
- `config.verifier_model`: returns `"defpredict-nemotron"` on Databricks (was `"nemotron-super-49b-v1_5"`)
- `config.DETECTOR_MODELS`: added `"defpredict-nemotron"` entry; kept `"nemotron-super-49b-v1_5"` entry (for direct vLLM access / legacy references and allow-list coverage)
- `config.MODEL_LINEAGE`: added `"defpredict-nemotron": "nemotron-on-llama"`; kept `"nemotron-super-49b-v1_5"` entry
- `ON_PREM_ALLOW_LIST` (derived from DETECTOR_MODELS): now covers `"defpredict-nemotron"` so D-16 guard does not reject the verifier's own endpoint

### Fix C: wait_for_ready default timeout

`timeout_minutes` default: 30 → 60. First cold start requires H100 cluster allocation + 93GB artifact load; 30 minutes was insufficient.

### Fix D: Fallback Rider broadening (Risk 4)

`_is_capacity_denial()` now includes `"not supported"` and `"workload_type"` in its keyword list. A workspace without `GPU_XLARGE_8` enrollment returns a `workload_type not supported` error — this now falls through the Fallback Rider rows instead of crashing.

### Fix E: register_model() docstring

Added prominent note about the 93GB upload happening at `log_model()` time, `databricks-sdk >= 0.102.0` requirement, and recommendation to run from a Databricks notebook.

---

## Tests Updated

**`tests/unit/test_config_verifier.py`** — assertions updated:
- `test_verifier_model_role_resolves_nemotron` → `test_verifier_model_role_resolves_endpoint_name`: asserts `"defpredict-nemotron"`
- Added `test_lineage_endpoint_name_is_nemotron_on_llama` for the routable id
- `test_lineage_served_model_name_is_nemotron_on_llama` kept (served-model-name entry preserved)
- `test_nemotron_in_detector_models` → `test_endpoint_name_in_detector_models`: asserts `"defpredict-nemotron"` in DETECTOR_MODELS
- Added `test_endpoint_name_in_allow_list`: asserts `"defpredict-nemotron"` in ON_PREM_ALLOW_LIST

**`tests/unit/test_on_prem_guard.py`** — no changes. `test_allowed_nemotron_does_not_raise` uses `"nemotron-super-49b-v1_5"` which is still in DETECTOR_MODELS and ON_PREM_ALLOW_LIST. `test_allow_list_covers_detector_models` superset invariant still passes.

---

## Commits

| Hash | Description |
|------|-------------|
| eaa2220 | fix(06-05): Nemotron deploy bugs — Volume paths, probe model=, fallback rider, dual-identity |

---

## What Was NOT Changed

Per the addendum constraints:
- `SERVED_MODEL_NAME = "nemotron-super-49b-v1_5"` stays (correct vLLM `--served-model-name`)
- `artifacts={"model_dir": NEMOTRON_VOLUME_DIR}` stays (upload source path is correct)
- D-16 guard not weakened; D-11/D-12/D-15 behavior untouched
- No live deploy performed; no metered action taken
- STATE.md / ROADMAP.md untouched

---

## Deviations from Plan

None — all fixes applied exactly as specified in the addendum.

---

## Known Stubs

None.

---

## Threat Flags

None. No new network endpoints, auth paths, or schema changes introduced.

---

## Self-Check: PASSED

- [x] deploy_nemotron.py: VLLM_CMD/BF16 use `--model model_dir` and `--tool-parser-plugin model_dir/...`; all probe calls use `model=ENDPOINT_NAME`; wait_for_ready default=60; `_is_capacity_denial` includes "not supported"/"workload_type"; AST parse OK
- [x] serving.py: `_DB_MODELS["nemotron"] == "defpredict-nemotron"`
- [x] config.py: `verifier_model` returns `"defpredict-nemotron"`; DETECTOR_MODELS + MODEL_LINEAGE + ON_PREM_ALLOW_LIST all include `"defpredict-nemotron"`
- [x] test_config_verifier.py: assertions updated to endpoint name; new endpoint-name tests added
- [x] Unit suite: 119 passed, 12 skipped, 0 failures
- [x] test_nemotron_probe.py: collects (6 deselected = integration skips, expected)
- [x] Commit eaa2220 exists and does not include STATE.md or ROADMAP.md
