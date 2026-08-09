# Phase 6: On-Prem Verifier Model + Weak-Model Reliability — Pattern Map

**Mapped:** 2026-08-08
**Files analyzed:** 10 (5 new, 5 modified + deployment artifact)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/llm/reliability.py` (NEW) | utility / middleware | request-response | `src/llm/structured.py` (L1–L6 defense, `parse_structured`, `ParseFailed` sentinel) + `src/llm/client.py` (`BadRequestError`→degrade) | exact: same defense-in-depth, same sentinel contract, same `BadRequestError` probe pattern |
| `src/schemas/llm.py` (MODIFY — add VERDICT) | model | transform | existing `ParseFailed` model in same file + `src/tools/errors.py` (`ToolRejected`) | exact: both are typed sentinels/result models with pydantic, enum fields, and the `instance XOR sentinel` return contract |
| `src/llm/client.py` (MODIFY — `chat_completion_tools` + `get_client`) | middleware / client | request-response | existing `chat_completion_full` `BadRequestError`→degrade + existing `get_client` factory; `src/config.py` `resolve_detector_model` allow-list | exact: same retry/degrade pattern in the same file; same allow-list pattern in config |
| `src/config.py` (MODIFY — `verifier_model` property + Nemotron in `DETECTOR_MODELS`) | config | transform | existing `moderator_model` / `detector_model` role properties + existing `DETECTOR_MODELS` dict + `resolve_detector_model` | exact: same property pattern, same dict+resolver pattern |
| `src/databricks/serving.py` (MODIFY — add `nemotron` key) | service / config | request-response | existing `_DB_MODELS` map + `resolve_model` | exact: identical pattern, add one key |
| `src/agents/review/registry.py` (MODIFY — `dispatch` field-level hint) | middleware / dispatcher | event-driven | existing `dispatch` → `ToolRejected` path, existing `hint` field in `ToolRejected`, `_direct_validate` | exact: extends the existing `hint=` kwarg from generic string to field-level message |
| `notebooks/deploy_nemotron.py` (NEW) | utility / deployment | batch | `notebooks/deploy_adapters.py` (`mlflow`, `httpx`, `deploy_endpoint`, `GPU_XLARGE_8` endpoint creation) | role-match: same MLflow + Databricks endpoint creation shape, different model type (pyfunc vs transformers) |
| `tests/unit/test_reliability.py` (NEW) | test | transform | `tests/unit/test_llm_client.py` + `tests/unit/test_tool_schema_derivation.py` | role-match: same unit-test structure (import target, `SimpleNamespace` mocks, assert contracts) |
| `tests/unit/test_on_prem_guard.py` (NEW) | test | request-response | `tests/unit/test_llm_client.py` + `src/config.py` `resolve_detector_model` pattern | role-match: tests the allow-list guard in `get_client` |
| `tests/evals/test_verifier_probe.py` (NEW) | test / eval | batch | `tests/evals/test_gate.py` + `tests/evals/test_frozen_score_snapshot.py` | role-match: same DeepEval / rate-assert eval structure |

---

## Pattern Assignments

---

### `src/llm/reliability.py` (NEW — utility, request-response)

**Primary analog:** `src/llm/structured.py` (L1–L6 defense) + `src/llm/client.py` (BadRequestError→degrade)
**Secondary analog:** `src/tools/errors.py` (`ToolRejected` sentinel) for the `ParseFailed` XOR contract

**Imports pattern** — copy the import block shape from `src/llm/structured.py` lines 1–28 and `src/llm/client.py` lines 1–11:
```python
from __future__ import annotations

from enum import Enum
from typing import TypeVar

import structlog
from openai import BadRequestError, OpenAI
from pydantic import BaseModel, ValidationError

from llm.structured import tool_schema_for_databricks
from schemas.llm import ParseFailed, VERDICT

log = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

# Module-level capability cache — detect-once per served-model-name (D-09)
_guided_cache: dict[str, bool] = {}
```

**Capability probe pattern** — mirrors `chat_completion_full` `BadRequestError`→degrade (lines 135–144 of `client.py`):
```python
# src/llm/client.py lines 135–144: the BadRequestError→degrade that D-09 mirrors
except BadRequestError as exc:
    if response_format is not None and "response_format" in kwargs:
        log.warning("response_format_rejected_falling_back", error=str(exc)[:200])
        kwargs.pop("response_format", None)
        response_format = None
        continue
    log.error("llm_bad_request", error=str(exc))
    raise
```
Translate into the D-09 cache probe: catch `BadRequestError` → `_guided_cache[model] = False`, catch generic `Exception` → also False (fail-safe). Never re-probe on the hot path — the cache key is `model` (served-model-name string), not the endpoint URL.

**Strict lossless coercion pattern** — coercion allow-list is the entire core of this module. The enum-field detection mirrors `src/tools/errors.py` `reason_code: str` design (open str, NOT a closed Literal) and the `ToolRejected.hint` field pattern. Structlog counters mirror the `log.warning` style in `structured.py` lines 138–139 and `client.py` lines 139–141:
```python
# Structlog counter pattern (from structured.py line 139 / client.py line 139):
log.warning("response_format_rejected_falling_back", error=str(exc)[:200])
log.warning("moderator_rescue_called", model=model_cls.__name__)  # line 277

# Apply the SAME counter pattern for near-misses:
log.warning("coercion_enum_near_miss_rejected",
            field=field_name, value=value, valid_values=list(valid))
log.info("coercion_numeric_string", field=field_name, value=value)
log.info("coercion_wrapper_unwrap", model=model_cls.__name__, key=k)
```

**Typed-sentinel contract** — copy from `structured.py` lines 313–347 (`structured_call` → returns `instance XOR ParseFailed`):
```python
# src/llm/structured.py lines 313–347: the XOR contract to replicate
def structured_call(...) -> tuple[T | None, ParseFailed | None]:
    """Top-level entry point ... instance XOR parse_failure — never a raw text leak."""
    instance, failure, raw = call_structured(...)
    if instance is not None:
        return instance, None
    repaired, repair_failure = repair_with_moderator(...)
    if repaired is not None:
        return repaired, None
    return None, repair_failure or failure  # L6: sentinel

# reliability.py replicates this contract for tool-call turns:
# coerce_and_validate(...) -> tuple[VERDICT | None, ParseFailed | None]
# Never: (verdict_instance, parse_failure) — exactly one is non-None
```

**Bounded retry pattern** — mirrors `structured_output_max_repair_calls` guard in `structured.py` lines 255–264:
```python
# src/llm/structured.py lines 255–264: the repair-calls guard
def repair_with_moderator(...):
    s = get_settings()
    if s.structured_output_max_repair_calls <= 0:
        return None, ParseFailed(
            layer="L5",
            reason="moderator repair disabled by config",
            ...
        )
```
The `reliability.py` retry cap follows the same config-knob pattern: `s.verifier_max_repair_calls` (default 1, mirrors `structured_output_max_repair_calls`). Each retry call counts toward the run budget — same "honest accounting" discipline.

**Field-level error formatter** — the `hint` field in `ToolRejected` (errors.py line 24, `hint: str = ""`) is the insertion point. Current `dispatch` sets `hint="send a JSON object matching this tool's schema exactly"` (registry.py line 233). The upgrade to field-level follows the `ValidationError.errors()` API already used implicitly by `parse_structured` (structured.py line 178):
```python
# src/llm/structured.py line 178: existing ValidationError surface
except ValidationError as exc:
    return None, exc.json(indent=None)

# reliability.py upgrades this to per-field messages:
for e in error.errors():
    loc = ".".join(str(x) for x in e["loc"])
    msg = e["msg"]
    # → "Field 'confidence': Input should be a valid number [error_type=float_type]"
```

---

### `src/schemas/llm.py` (MODIFY — add `VERDICT` model)

**Primary analog:** existing `ParseFailed` in the same file (lines 1–16) + `ToolRejected` in `src/tools/errors.py` (lines 13–38)

**Existing `ParseFailed` model** (lines 1–16 of `src/schemas/llm.py`):
```python
from __future__ import annotations
from pydantic import BaseModel

class ParseFailed(BaseModel):
    """Typed sentinel — the frontend renders this as a needs-human-review card..."""
    layer: str
    reason: str
    raw_output: str
    validation_error: str = ""
    requires_human_review: bool = True
```

**VERDICT model placement:** add immediately after `ParseFailed` in the same file. Use `str, Enum` pattern (matches the `ComplianceVerdict` / `StrEnum` pattern in `src/schemas/faults.py` as used by `EmitFindingArgs`). The class uses `Field(ge=0.0, le=1.0)` for `confidence` — same `pydantic.Field` constraint style as `SearchCorpusArgs.top_k = Field(default=10, description=...)` in registry.py line 78.

**Enum-field pattern** — mirrors `ComplianceVerdict` used in `EmitFindingArgs` (registry.py line 107). The enum value must be `str, Enum` so pydantic serializes it as the string value (not the name). Use `class VerdictChoice(str, Enum)` consistent with the existing `StrEnum` usage across the codebase.

**What Phase 7 must NOT do:** redefine the `VERDICT` class. It must subclass or extend it. The `VERDICT` placed here is the fixed base shape that `tool_schema_for_databricks(VERDICT)` derives a stable guided schema from.

---

### `src/llm/client.py` (MODIFY — two insertion points)

**Primary analog:** the existing functions in this file — `chat_completion_tools` (lines 164–221) for the `extra_body` passthrough and `get_client` (lines 70–86) for the allow-list guard.

**`extra_body` passthrough insertion point** — `chat_completion_tools` signature (lines 164–171):
```python
# CURRENT (src/llm/client.py lines 164–171):
def chat_completion_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_choice: str = "auto",
) -> ChatTurn:
```
Add `extra_body: dict | None = None` to the signature. Thread it into `kwargs` the same way `response_format` is threaded in `chat_completion_full` (lines 124–126):
```python
# src/llm/client.py lines 124–126: the conditional-kwarg pattern to copy:
if response_format is not None:
    kwargs["response_format"] = response_format
# Analogous for extra_body:
if extra_body is not None:
    kwargs["extra_body"] = extra_body
```

**On-prem allow-list guard insertion point** — `get_client` (lines 70–86):
```python
# CURRENT (src/llm/client.py lines 70–86):
def get_client() -> OpenAI:
    global _client
    if _client is None:
        s = get_settings()
        if s.is_databricks:
            _client = OpenAI(
                base_url=f"{s.databricks_host}/serving-endpoints",
                api_key=s.databricks_token,
                timeout=120.0,
            )
        else:
            _client = OpenAI(
                base_url=s.llm_base_url,
                api_key="not-needed",
                timeout=120.0,
            )
    return _client
```
The guard is a pre-construction check added at the top of `get_client`, accepting an optional `model: str | None = None` parameter (D-16). Fail-loud with `ValueError` — same style as the existing `ToolRejected` `reason` string pattern in errors.py:
```python
# Precedent: src/config.py lines 102–107 (resolve_detector_model allow-list):
def resolve_detector_model(model: str | None) -> str:
    if model and model in DETECTOR_MODELS:
        return model
    return get_settings().detector_model

# D-16 guard uses the same allow-list check but RAISES instead of falling back:
if model is not None and model not in _ON_PREM_ALLOW_LIST:
    raise ValueError(
        f"Model {model!r} is not in the on-prem allow-list. ..."
    )
```

**Retry loop shape** — the `for attempt in range(_MAX_RETRIES)` + `BadRequestError`/`RateLimitError`/`_RETRYABLE` pattern (lines 185–219) is untouched. The `extra_body` threading is purely additive — it does NOT alter the retry logic.

---

### `src/config.py` (MODIFY — three additions)

**Primary analog:** existing `moderator_model` / `detector_model` properties (lines 66–77) and `DETECTOR_MODELS` dict + `resolve_detector_model` (lines 93–107).

**Role property pattern** (lines 66–77 of `src/config.py`):
```python
@property
def moderator_model(self) -> str:
    if self.is_databricks:
        return "databricks-meta-llama-3-3-70b-instruct"
    return self.resolved_llm_model

@property
def detector_model(self) -> str:
    """Detection sub-agents run on the strong model ..."""
    if self.is_databricks:
        return "databricks-meta-llama-3-3-70b-instruct"
    return self.resolved_llm_model
```
Add `verifier_model` as a fourth property with the same shape: `if self.is_databricks: return "nemotron-super-49b-v1_5"  # self-managed vLLM endpoint`. Falls back to `self.detector_model` in local dev.

**Config knob pattern** (lines 51–53 of `src/config.py`):
```python
# CURRENT structured output knobs (lines 51–53):
structured_output_strict: bool = True
structured_output_max_repair_calls: int = 1
max_tokens_ceiling: int = 8000
```
Add `verifier_max_repair_calls: int = 1` alongside these, using the identical pydantic-settings field pattern.

**DETECTOR_MODELS dict pattern** (lines 93–99):
```python
DETECTOR_MODELS: dict[str, str] = {
    "databricks-meta-llama-3-3-70b-instruct": "Llama 3.3 70B",
    "databricks-qwen35-122b-a10b": "Qwen3.5 122B · A10B (MoE)",
    "databricks-qwen3-next-80b-a3b-instruct": "Qwen3-Next 80B · A3B (MoE)",
}
```
Add Nemotron entry AND add lineage tags for D-17. Lineage tags live in a companion dict (NOT changing the display-label value, which is consumed by the frontend):
```python
# Add to DETECTOR_MODELS:
"nemotron-super-49b-v1_5": "Nemotron Super 49B v1.5 (verifier)",

# New companion dict for D-17 lineage:
MODEL_LINEAGE: dict[str, str] = {
    "databricks-meta-llama-3-3-70b-instruct": "llama",
    "databricks-meta-llama-3-1-8b-instruct": "llama",
    "databricks-qwen35-122b-a10b": "qwen",
    "databricks-qwen3-next-80b-a3b-instruct": "qwen",
    "nemotron-super-49b-v1_5": "nemotron-on-llama",
    "defpredict-suggestor": "llama",
    "defpredict-evaluator": "llama",
}
```

---

### `src/databricks/serving.py` (MODIFY — add Nemotron key)

**Primary analog:** existing `_DB_MODELS` dict and `resolve_model` (lines 11–33, entire file).

**Current `_DB_MODELS`** (lines 11–16):
```python
_DB_MODELS = {
    "llama-8b": "databricks-meta-llama-3-1-8b-instruct",
    "llama-70b": "databricks-meta-llama-3-3-70b-instruct",
    "suggestor": "defpredict-suggestor",
    "evaluator": "defpredict-evaluator",
}
```
Add one entry: `"nemotron": "nemotron-super-49b-v1_5"`. The served-model-name string `"nemotron-super-49b-v1_5"` must exactly match the `--served-model-name` vLLM launch flag so `supports_guided_json` caches on the right key.

**`resolve_model` pattern** (lines 32–33):
```python
def resolve_model(model: str) -> str:
    return _DB_MODELS.get(model, model)
```
This function is unchanged — the shorthand key `"nemotron"` resolves through the existing `.get(model, model)` passthrough. No modification to the function body needed.

---

### `src/agents/review/registry.py` (MODIFY — `dispatch` field-level hint)

**Primary analog:** the existing `dispatch` method (lines 214–255) and its `ToolRejected` construction with `hint=` at line 233.

**Current `hint` pattern** (registry.py lines 227–235):
```python
parsed, error = parse_structured(raw_text, spec.model)
if parsed is None:
    rejected = ToolRejected(
        tool=name,
        reason_code="post_repair_malformed",
        reason=error or "tool arguments could not be parsed or validated",
        hint="send a JSON object matching this tool's schema exactly",  # ← generic
    )
    return self._rejected(name, {}, rejected, "post")
```
The upgrade is minimal: call `reliability.format_field_level_reprompt(error, spec.model)` instead of the generic string when the error is a pydantic `ValidationError`-sourced JSON string. The `error` variable is already `exc.json(indent=None)` from `parse_structured` (structured.py line 178). The `hint=` field type stays `str` — no schema change to `ToolRejected`.

**`_direct_validate` pattern** (lines 168–173) — unchanged:
```python
def _direct_validate(raw_args: str, model_cls: type[_ArgsModel]) -> bool:
    try:
        model_cls.model_validate_json(raw_args)
    except Exception:
        return False
    return True
```

**`render_rejection` pattern** (lines 138–147) — unchanged, already emits `hint` to the model:
```python
def render_rejection(r: ToolRejected) -> str:
    parts = [f'REJECTED[{r.reason_code}] {r.reason}']
    if r.hint:
        parts.append(f'HINT: {r.hint}')
    ...
    return "\n".join(parts)
```
The field-level error message from `reliability.format_field_level_reprompt` flows to the model via this existing render path — no change to `render_rejection` itself.

---

### `notebooks/deploy_nemotron.py` (NEW — deployment utility, batch)

**Primary analog:** `notebooks/deploy_adapters.py` — specifically `deploy_endpoint` (lines 84–125) and `register_adapter` (lines 40–81).

**MLflow registration pattern** (deploy_adapters.py lines 49–77):
```python
# deploy_adapters.py lines 49–77: transformers.log_model for LoRA adapters
mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run(run_name=f"register-{role}-adapter"):
    model_info = mlflow.transformers.log_model(
        transformers_model={"model": merged, "tokenizer": tokenizer},
        artifact_path=role,
        registered_model_name=model_name,
        task="llm/v1/chat",
    )
```
Nemotron uses `mlflow.pyfunc.log_model` instead (because self-managed vLLM, not transformers). Same `task="llm/v1/chat"` convention. Same `mlflow.set_registry_uri("databricks-uc")` + `mlflow.start_run()` wrapper.

**Endpoint creation pattern** (deploy_adapters.py lines 84–125):
```python
# deploy_adapters.py lines 87–112: the httpx endpoint-create pattern
host = os.environ.get("DATABRICKS_HOST", "")
token = os.environ.get("DATABRICKS_TOKEN", "")
payload = {
    "name": endpoint_name,
    "config": {
        "served_entities": [{
            "entity_name": entity_name,
            "entity_version": "1",
            "min_provisioned_throughput": 0,
            "max_provisioned_throughput": 200,
            "scale_to_zero_enabled": True,   # ← change to False for D-04 always-warm
        }],
    },
}
headers = {"Authorization": f"Bearer {token}"}
r = httpx.post(f"{host}/api/2.0/serving-endpoints", headers=headers, json=payload, timeout=30.0)
```
Nemotron changes: `"workload_type": "GPU_XLARGE_8"`, `"scale_to_zero_enabled": False` (D-04), and the payload body uses `"workload_type"/"workload_size"` keys (Databricks GPU serving schema). The create/update branching (`"already exists" in r.text.lower()`) is copied verbatim.

**CLI argument pattern** (deploy_adapters.py lines 128–145):
```python
parser = argparse.ArgumentParser()
parser.add_argument("--role", choices=["suggestor", "evaluator", "all"], required=True)
parser.add_argument("--register-only", action="store_true", ...)
```
`deploy_nemotron.py` uses the same `argparse` shape: `--register-only` and `--wait` flags following the same pattern.

**Volume path convention** (deploy_adapters.py lines 23–37):
```python
LOCAL_ADAPTER_DIR = Path("data/adapters")
VOLUME_ADAPTER_DIR = "/Volumes/defpredict/main/artifacts/adapters"
```
Nemotron: `NEMOTRON_VOLUME_DIR = "/Volumes/defpredict/main/artifacts/nemotron-49b"`. Same Volume path convention.

---

### `tests/unit/test_reliability.py` (NEW — unit test)

**Primary analog:** `tests/unit/test_llm_client.py` + `tests/unit/test_tool_schema_derivation.py`

**Unit test structure pattern** (test_llm_client.py lines 1–30):
```python
from __future__ import annotations
from types import SimpleNamespace
from llm.client import _request_safe_message

def test_request_safe_message_drops_response_only_fields_but_keeps_tool_calls():
    message = SimpleNamespace(
        model_dump=lambda **kw: {
            "role": "assistant",
            ...
        }
    )
    payload = _request_safe_message(message)
    assert "annotations" not in payload
```
Copy the `from __future__ import annotations` + `from types import SimpleNamespace` mock pattern. Tests are plain pytest functions (not class-based) for simple assertions; class-based grouping (`class TestStrictCoerce:`) for multi-case suites matching `test_gate.py` style.

**Schema derivation test pattern** (test_tool_schema_derivation.py lines 1–32):
```python
from llm.structured import build_tool_schema, tool_schema_for_databricks
PROHIBITED_KEYS = ("$ref", "$defs", "anyOf", ...)

def assert_databricks_legal(schema: dict) -> None:
    for node in _walk(schema):
        for key in node:
            assert key not in PROHIBITED_KEYS
```
Use `assert_databricks_legal` (already defined in the test file) to validate that `tool_schema_for_databricks(VERDICT)` produces a legal guided schema. Import it or copy the helper.

**Key test cases for `test_reliability.py`:**
- `test_guided_probe_caches` — call `supports_guided_json` twice with a mocked client; assert `client.chat.completions.create` called once
- `test_strict_coerce_numeric_string` — `strict_coerce({"confidence": "0.85"}, VERDICT)` → `{"confidence": 0.85}`
- `test_strict_coerce_bool_string` — `strict_coerce({"flag": "true"}, SomeModel)` → `{"flag": True}`
- `test_strict_coerce_wrapper_unwrap` — `strict_coerce({"VERDICT": {...}}, VERDICT)` → `{...}`
- `test_enum_near_miss_not_coerced` — `strict_coerce({"verdict": "keep"}, VERDICT)` leaves it as `"keep"` (pydantic will raise)
- `test_no_fabricated_verdict` — on deliberate bad input, assert `return[0] is None AND return[1] is not None AND isinstance(return[1], ParseFailed)`
- `test_field_level_error_format` — `format_field_level_reprompt(error, VERDICT)` contains the field name and expected type, NOT just a generic string

---

### `tests/unit/test_on_prem_guard.py` (NEW — unit test)

**Primary analog:** `tests/unit/test_llm_client.py` + `src/config.py` `resolve_detector_model`

**Guard test structure:** import the modified `get_client` (or the `_ON_PREM_ALLOW_LIST` set). Use `pytest.raises(ValueError)` to assert the guard fires. Pattern mirrors the `resolve_detector_model` semantics but tests the hard-raise path:
```python
# Mirrors the resolve_detector_model precedent (config.py lines 102–107)
# but asserts ValueError, not fallback:
import pytest
from unittest.mock import patch
from llm.client import get_client  # or wherever the guard lives

def test_forbidden_model_raises_value_error():
    with pytest.raises(ValueError, match="on-prem allow-list"):
        get_client(model="databricks-claude-3-5-sonnet")

def test_allowed_model_does_not_raise():
    # Must not raise; actual client construction can be mocked
    ...
```

---

### `tests/evals/test_verifier_probe.py` (NEW — eval / integration test)

**Primary analog:** `tests/evals/test_gate.py` + `tests/evals/test_frozen_score_snapshot.py`

**Eval test structure** (test_gate.py lines 1–60):
```python
from pathlib import Path
from evals.gate import GateResult, check_gate
from evals.schema import load_eval_set

DOC_ID = "mvr1381"
BASELINE = {"C-01", "C-02"}

class TestCheckGatePassesOnGoldenRun:
    def test_golden_run_passes_for_the_pinned_baseline(self):
        g = check_gate(golden_report(), load_eval_set(), DOC_ID, BASELINE)
        assert g.ok is True
```
The verifier probe follows the same `class TestVerifierConformance:` + `class TestVerifierDiscrimination:` split. Load the `beta-measurement-summary.json` via `Path(...)` (same pattern as `BASELINE_PATH` in test_gate.py line 13). Use `@pytest.mark.parametrize("thinking_mode", ["on", "off"])` for the D-06 per-mode assertion.

**DeepEval integration pattern:** the existing `tests/evals/test_gate.py` uses plain pytest class structure. The D-06 DeepEval harness uses `deepeval.assert_test` + `BaseMetric` subclasses for `conformance_rate` and `discrimination_accuracy`. Mark integration tests with `@pytest.mark.integration` to allow `pytest tests/unit/ -x` fast path.

---

## Shared Patterns

### 1. `instance XOR sentinel` typed-return contract

**Source files:**
- `src/llm/structured.py` lines 313–347 (`structured_call`)
- `src/tools/errors.py` lines 13–38 (`ToolRejected`)
- `src/schemas/llm.py` lines 1–16 (`ParseFailed`)

**Apply to:** `reliability.py` `coerce_and_validate` return type; every function in `reliability.py` that can fail

```python
# The contract, from structured.py line 323:
"""The frontend contract is: instance XOR parse_failure — never a raw text leak."""
# tuple[T | None, ParseFailed | None]  — exactly one is non-None
```

### 2. `structlog` telemetry counter pattern

**Source:** `src/llm/structured.py` lines 138–139, 277–278, 302–304; `src/llm/client.py` lines 139–141, 153–157

**Apply to:** `reliability.py` (near-miss counters, per-mode latency/token logging), `registry.py` modifications

```python
# Pattern (structured.py lines 277–278):
log = structlog.get_logger()
log.warning("moderator_rescue_called", model=model_cls.__name__)
log.info("moderator_rescue_success", model=model_cls.__name__)
log.error("moderator_rescue_failed", model=model_cls.__name__, error=(err or "")[:200])

# Apply same bind-and-count pattern for:
log.warning("coercion_enum_near_miss_rejected", field=..., value=..., valid_values=...)
log.info("guided_json_probe_cached", model=model, supported=True)
log.info("reliability_repair_attempt", model=model_cls.__name__, attempt=n)
```

### 3. `pydantic_settings.BaseSettings` config-field pattern

**Source:** `src/config.py` lines 7–86

**Apply to:** all new env-var-backed settings fields in `config.py`

```python
# Pattern (config.py lines 50–53):
structured_output_strict: bool = True
structured_output_max_repair_calls: int = 1
max_tokens_ceiling: int = 8000

# New fields follow identical pattern:
verifier_max_repair_calls: int = 1
verifier_model_id: str = ""   # empty = resolved via verifier_model property
```

### 4. `BadRequestError`→degrade conditional pattern

**Source:** `src/llm/client.py` lines 135–144

**Apply to:** `reliability.py` `supports_guided_json` capability probe — this is the exact mechanism to translate into the D-09 cache

```python
# src/llm/client.py lines 135–144 (the exact degrade logic to mirror):
except BadRequestError as exc:
    if response_format is not None and "response_format" in kwargs:
        log.warning("response_format_rejected_falling_back", error=str(exc)[:200])
        kwargs.pop("response_format", None)
        response_format = None
        continue
    log.error("llm_bad_request", error=str(exc))
    raise
```

### 5. Allow-list guard with `resolve` helper pattern

**Source:** `src/config.py` lines 93–107

**Apply to:** `get_client` D-16 guard (client.py) and the `_ON_PREM_ALLOW_LIST` set definition

```python
# src/config.py lines 93–107: the allow-list precedent
DETECTOR_MODELS: dict[str, str] = {
    "databricks-meta-llama-3-3-70b-instruct": "Llama 3.3 70B",
    ...
}
def resolve_detector_model(model: str | None) -> str:
    if model and model in DETECTOR_MODELS:
        return model
    return get_settings().detector_model
```
D-16 uses the same set-membership test but raises instead of falling back: `if model not in _ON_PREM_ALLOW_LIST: raise ValueError(...)`.

### 6. MLflow + httpx endpoint creation pattern

**Source:** `notebooks/deploy_adapters.py` lines 40–125

**Apply to:** `notebooks/deploy_nemotron.py` (Nemotron deployment)

```python
# deploy_adapters.py lines 87–112: the httpx + bearer-token pattern
host = os.environ.get("DATABRICKS_HOST", "")
token = os.environ.get("DATABRICKS_TOKEN", "")
headers = {"Authorization": f"Bearer {token}"}
r = httpx.post(f"{host}/api/2.0/serving-endpoints", headers=headers, json=payload, timeout=30.0)
if "already exists" in r.text.lower():
    r2 = httpx.put(f"{host}/api/2.0/serving-endpoints/{endpoint_name}/config", ...)
```

---

## No Analog Found

None. All Phase 6 files have close analogs in the existing codebase. The primary design choice (using `BadRequestError`→cache instead of `BadRequestError`→retry) is well-covered by the existing `chat_completion_full` degrade pattern.

---

## Critical Extraction Notes for Planner

1. **`tool_schema_for_databricks` is the mandatory schema route.** It is already defined in `structured.py` lines 102–106 and used by `build_tool_schema`. The `reliability.py` guided schema builder MUST route through it — never `VERDICT.model_json_schema()` raw. The test `test_raw_schema_is_illegal_negative_control` in `test_tool_schema_derivation.py` documents why.

2. **`ChatTurn.raw_message` must be echoed verbatim** on the corrective retry (client.py Pitfall 10 documented in the `ChatTurn` docstring, lines 49–68). The field-level re-prompt message is appended to the messages list; the previous `ChatTurn.raw_message` (the assistant turn with the malformed tool_call) must be included unchanged.

3. **`_DB_MODELS` shorthand key vs. served-model-name.** The `_guided_cache` in `reliability.py` must be keyed on the **served-model-name** string (e.g. `"nemotron-super-49b-v1_5"`) not the shorthand key (`"nemotron"`). After `serving.resolve_model("nemotron")` → `"nemotron-super-49b-v1_5"`, use the resolved name as the cache key.

4. **`structured_output_max_repair_calls` is already 1.** The new `verifier_max_repair_calls` follows the same default. If the planner sets the default to something other than 1, it will diverge from the established discipline (D-13 ties this explicitly to the existing field's value).

5. **`get_client()` is currently a singleton** (global `_client`, lines 13 and 70–86). The D-16 guard adds a `model: str | None = None` parameter for validation. The singleton behavior is preserved — the guard only inspects the `model` argument, it does NOT invalidate the cached client.

---

## Metadata

**Analog search scope:** `src/llm/`, `src/schemas/`, `src/config.py`, `src/databricks/`, `src/agents/review/`, `src/tools/`, `notebooks/`, `tests/unit/`, `tests/evals/`
**Files scanned:** 12 source files read in full
**Pattern extraction date:** 2026-08-08
