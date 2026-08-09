---
phase: "06"
plan: "04-ADDENDUM"
subsystem: on-prem-guard
tags: [security, d-16, on-prem, 21cfr-part11, structural-invariant]
dependency_graph:
  requires: [06-04-PLAN]
  provides: [SC1-structural-proof, embeddings-guard, serving-guard, no-arg-guard]
  affects: [src/llm/client.py, src/databricks/serving.py, src/retrieval/vector_search.py, src/config.py]
tech_stack:
  added: []
  patterns: [deny-first-then-allow-list, resolve-before-guard, single-construction-site]
key_files:
  created:
    - tests/unit/test_no_raw_openai_construction.py
  modified:
    - src/llm/client.py
    - src/databricks/serving.py
    - src/retrieval/vector_search.py
    - src/config.py
    - tests/unit/test_on_prem_guard.py
decisions:
  - "Layer 2 (allow-list) is Databricks-only; Layer 1 (deny-first substring) fires in all environments"
  - "databricks-bge-large-en added to ON_PREM_ALLOW_LIST — embeddings carry submission text"
  - "Structural scan test excludes comment-only and docstring lines via stripped-prefix heuristic"
metrics:
  duration: "~25 min"
  completed: "2026-08-09"
  tasks: 1
  files_changed: 6
---

# Phase 06 Plan 04 ADDENDUM: D-16 Structural Invariant — On-Prem Guard Centralization Summary

**One-liner:** Centralized all `OpenAI(` construction to `src/llm/client.py` and made SC1 ("no external LLM endpoint called — holds BY CONSTRUCTION") a grep-verifiable invariant guarding no-arg calls, serving path, and embeddings path.

## What Was Done

### Problem Statement (from reviewer ruling B)

Four gaps survived 06-04 wave 3:

1. `get_client(model=None)` skipped both the deny-first check and the allow-list check entirely — any code calling it without a model arg bypassed the guard.
2. `chat_completion_full` and `chat_completion_tools` called `get_client()` (no arg), then used `model or s.resolved_llm_model` as the API call model — the checked path diverged from the called path.
3. `src/databricks/serving.py` `get_llm_client()` raw-constructed two `OpenAI(...)` clients, bypassing the guard entirely.
4. `src/retrieval/vector_search.py` `_embed_databricks()` raw-constructed an `OpenAI(...)` client for the Databricks BGE embeddings endpoint, bypassing the guard. Embeddings carry raw submission text — they are in scope for the 21 CFR Part 11 data boundary.

### Changes Made

**`src/config.py`**
- Added `"databricks-bge-large-en"` to `ON_PREM_ALLOW_LIST` explicitly (embeddings endpoint in scope for 21 CFR Part 11 — carries raw submission text; not a chat-completion model so not in `DETECTOR_MODELS`).

**`src/llm/client.py`**
- `get_client()`: resolve `model=None` to `get_settings().resolved_llm_model` BEFORE the guard runs. Layer 1 (deny-first substring: `claude`, `gpt`, `gemini`) now fires in ALL environments (local Ollama + Databricks). Layer 2 (exact allow-list check) fires only when `is_databricks=True` — in local dev, Ollama is localhost by construction so any non-external model name is on-prem.
- Removed the redundant `s = get_settings()` call inside the singleton construction block (already called at function top).
- `chat_completion_full`: computes `resolved_model = model or s.resolved_llm_model` first, then calls `get_client(resolved_model)` — the guard and the API call now see the same concrete model id.
- `chat_completion_tools`: same pattern — `resolved_model` computed first, passed into `get_client(resolved_model)`.

**`src/databricks/serving.py`**
- Removed both raw `OpenAI(...)` construction sites from `get_llm_client()`.
- `get_llm_client()` now returns `get_client()` (the guarded singleton from `llm.client`). Import changed from `from openai import OpenAI` to `from llm.client import get_client`.
- Construction params (base_url, api_key, timeout) are identical — the singleton in `client.py` already uses the same params. This is routing-only.

**`src/retrieval/vector_search.py`**
- Removed raw `OpenAI(...)` construction from `_embed_databricks()`.
- Added `_DATABRICKS_EMBEDDING_MODEL = "databricks-bge-large-en"` constant.
- `_embed_databricks()` now calls `get_client(_DATABRICKS_EMBEDDING_MODEL)` (function-local import to avoid circular import risk), then `.embeddings.create(model=_DATABRICKS_EMBEDDING_MODEL, ...)`. **Embedding values unchanged** — same endpoint, same model id, same params.

**`tests/unit/test_no_raw_openai_construction.py`** (new)
- Structural scan test: scans all `*.py` files under `src/`, filters out import lines, comment-only lines, and docstring-marker lines (heuristic: stripped line starts with `#`, `"`, `'`, `*`, `>`), asserts any surviving `OpenAI(` hit is ONLY in `src/llm/client.py`.
- A future module constructing its own client will FAIL this test whatever its purpose.

**`tests/unit/test_on_prem_guard.py`** (extended)
- Added ADDENDUM tests per reviewer ruling B:
  - **(i)** `test_serving_get_llm_client_with_forbidden_default_raises`: monkeypatches `resolved_llm_model` to `"databricks-claude-opus-4-8"`, asserts `serving.get_llm_client()` raises `ValueError`.
  - **(ii)** `test_no_arg_get_client_forbidden_default_raises`: same patch, asserts `get_client()` (no arg) raises.
  - **(iii-a)** `test_allowed_llm_id_via_get_client_passes`: Llama 70B id passes guard.
  - **(iii-b)** `test_allowed_embeddings_id_via_get_client_passes`: `"databricks-bge-large-en"` passes guard.
  - **(v-a)** `test_forbidden_embeddings_id_raises`: `"databricks-gpt-embeddings-large"` raises via Layer 1.
  - **(v-b)** `test_on_prem_embeddings_id_in_allow_list`: asserts `"databricks-bge-large-en"` is in `ON_PREM_ALLOW_LIST`.
  - `reset_client_singleton` fixture: saves/restores the `_client` singleton around tests that need to test construction.
- Updated `test_none_model_does_not_raise` docstring to describe the new behavior (resolves default, checks it via Layer 1; in local dev Layer 2 is skipped).

## Success Criteria Verification

- [x] `grep -rnE "OpenAI\(" src/ | grep -v "import OpenAI\|AsyncOpenAI"` returns ONLY `src/llm/client.py` lines (lines 148, 154 — the singleton construction).
- [x] `get_client()` resolves the concrete default before the guard; `chat_completion_full` and `chat_completion_tools` pass resolved model into `get_client()`.
- [x] `serving.get_llm_client()` returns `get_client()` — no raw `OpenAI(` in serving.py.
- [x] `_embed_databricks()` routes through `get_client("databricks-bge-large-en")` — no raw `OpenAI(` in vector_search.py; `"databricks-bge-large-en"` in `ON_PREM_ALLOW_LIST`.
- [x] `test_no_raw_openai_construction.py::test_openai_construction_only_in_client_py` passes and would fail if raw `OpenAI(` added outside client.py.
- [x] Tests (i)-(v) present and passing.
- [x] `pytest tests/unit/ -x -q` exits 0 — 117 passed, 12 pre-existing skips.
- [x] Embedding values unchanged — routing-only change, same endpoint and params.
- [x] STATE.md and ROADMAP.md untouched.

## Deviations from Ruling

### Layer 2 (allow-list) scoped to is_databricks=True

The reviewer ruling said "run the deny-first + allow-list check on that concrete id" without an environment gate. However, applying the allow-list in local dev would reject `"mistral:7b-instruct"` (the Ollama default) since it is not a Databricks endpoint name — breaking local dev entirely.

**Resolution:** Layer 2 (allow-list) fires only when `is_databricks=True`. In local dev, Ollama's serving URL is `localhost` by construction — no data leaves the machine regardless of the model name. Layer 1 (deny-first substring check for `claude`/`gpt`/`gemini`) fires in all environments, which is the critical guard: it catches the one-string-away misconfiguration (e.g., accidentally setting `llm_model=gpt-4o` in a local `.env`).

This preserves the ruling's intent (guard the concrete resolved id; catch external family names) without breaking local dev.

## Commits

- `669c717`: fix(06-04-addendum): centralize OpenAI( to client.py; guard no-arg + embeddings paths

## Self-Check: PASSED

- `src/llm/client.py` — exists and is the only file with `OpenAI(` construction.
- `tests/unit/test_no_raw_openai_construction.py` — exists and passes.
- `tests/unit/test_on_prem_guard.py` — extended with 6 new tests, all passing.
- `src/config.py` — `"databricks-bge-large-en"` present in `ON_PREM_ALLOW_LIST`.
- Commit `669c717` exists in git log.
- 117 unit tests pass, 0 new failures.
