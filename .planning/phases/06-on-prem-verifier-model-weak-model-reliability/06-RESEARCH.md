# Phase 6: On-Prem Verifier Model + Weak-Model Reliability (β) — Research

**Researched:** 2026-08-08
**Domain:** Self-managed vLLM on Databricks GPU serving + OpenAI-compatible reliability hardening
**Confidence:** HIGH (live CLI verification for GPU/endpoint facts; HIGH for vLLM flags from official docs; MEDIUM for some Nemotron-specific quantization details pending GPU hardware confirmation)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01** Nemotron is NOT currently deployed — deploy from scratch this phase.
**D-02** Deploy Nemotron THIS phase against a live endpoint — no deferral.
**D-03** Serve via self-managed vLLM (NOT Databricks managed Provisioned Throughput).
**D-04** Always-on GPU endpoint (kept warm; GPU_XLARGE_8 cost accepted).
**D-05** Probe corpus = the 115 real β-measurement candidates (mvr1381=112, minispec=3).
**D-06** Two-dimensional falsifiable pass bar: (a) conformance ≥98% post-repair, thinking ON and OFF each separately, plus one tool-call round-trip probe; (b) discrimination ≥80% correct on the known-good/known-bad split.
**D-07** Define a minimal VERDICT arg-model (verdict: KEEP|DOWNGRADE, confidence, rationale, grounding_span) in schemas/llm.py. Phase 7 extends, never redefines.
**D-08** Guided decoding (guided_json) wired into the tool-call turn for ALL 7 review tools + VERDICT on every endpoint that supports it.
**D-09** Detect-once, cache per-endpoint guided_json capability. Fail-safe on probe error: assume unsupported, fall through.
**D-10** Defense-in-depth stack: guided_json → native tool-parser → strict lossless coercion → field-level error + bounded retry → typed ParseFailed sentinel.
**D-11** Coercion = strict lossless allow-list + logged near-misses. Enum values NEVER guessed. Coerce only: numeric-string→number, 'true'/'false'→bool, single-key wrapper unwrap. Every rejected near-miss logged (structlog counter).
**D-12** On exhausted retries → typed field-level failure (ParseFailed); the CALLER decides. Never fabricate a verdict.
**D-13** Retry cap = 1 corrective retry, budget-counted, configurable (default 1 mirroring structured_output_max_repair_calls).
**D-14** Reliability baseline PINNED before any hardening lands. Metric = pre-repair malformed-arg rate + post-repair residual from Phase-3 D-TEL4 counters. Baseline numbers written as numbers in the plan.
**D-15** One shared reliability module: src/llm/reliability.py. Both registry.dispatch AND structured.py consume it.
**D-16** Minimal allow-list guard at the client boundary (get_client / model resolution): reject any model-id not in on-prem allow-list.
**D-17** Role + lineage metadata now; enforcement in Phase 7. Add verifier_model role + lineage tags (llama / qwen / nemotron-on-llama).
**D-18** Lock the SPLIT, not the policy. Phase 6 proves thinking ON and OFF each clear the D-06 bar and records latency + token cost per mode. Escalation trigger is Phase 7.
**D-19** Do NOT pick a quant blind. Day-one research task: enumerate GPU class, then pick quant. THEN amend ADR.
**D-20** Plan MUST carry an explicit decision gate — no serving build starts until quant/GPU pair confirmed vLLM-compatible.

### Claude's Discretion
- D-12 failure boundary: return ParseFailed, never a fabricated verdict (decided).
- D-13 retry-cap value: 1, configurable (decided).
- D-09 fallback strategy: detect-once/per-endpoint (decided).

### Deferred Ideas (OUT OF SCOPE)
- Verifier sub-agents, orchestrator fan-out, never-drop→KEEP mapping, decorrelation enforcement, interpretive-tail pass — Phase 7.
- Thinking-mode escalation trigger — Phase 7.
- Prompt-cache stable prefix, compaction, cheap-triage cost governance — Phase 8.
- Loosening coercion / bumping retry cap to 2 — only if telemetry proves it (evidence-driven).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODEL-01 | NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 served self-hosted on Databricks alongside Llama 3.3 70B + Qwen MoE; no external LLM API ever called | GPU hardware confirmed (GPU_XLARGE_8 = 8xH100 on this workspace per live CLI probe); vLLM launch flags documented; on-prem allow-list guard pattern in client.py is the integration point |
| MODEL-02 | Nemotron pre-wiring probes pass — vLLM tool-call + detailed thinking on/off validated on real verification traces; tool-parser flags and quant confirmed for target GPU | vLLM tool-parser flags documented; quant decision procedure with H100/GPU_XLARGE_8 produces FP8 recommendation; thinking toggle probe strings identified (/no_think + probe which fires) |
| RELIABILITY-01 | Tool-call arguments constrained by server-side guided decoding (vLLM guided_json / Ollama format) wherever endpoint supports it | extra_body={"structured_outputs": {"json": schema}} API documented; capability probe pattern identified (mirrors existing BadRequestError degrade in client.py) |
| RELIABILITY-02 | Malformed tool-args receive field-level, actionable error feedback (which field, expected type), bounded by a retry cap | Field-level error format identified; retry cap = 1 config knob mirrors structured_output_max_repair_calls; registry.dispatch hint field is the insertion point |
| RELIABILITY-03 | Targeted semantic arg coercion handles weak-model failure modes (quoted numbers/booleans, single-key-wrapper unwrap) without loosening advertised schemas | Exact coercion allow-list defined; near-miss logging via structlog; Phase-3 failure modes catalogued (Qwen: 4/5 post_repair_malformed; Llama: 0/0 in scored runs) |
</phase_requirements>

---

## Summary

Phase 6 has two parallel tracks that must gate on each other. **Track A (D-20 gate → serving build):** enumerate the GPU_XLARGE_8 hardware class (confirmed 8-GPU serving tier; strong evidence of H100 based on existing deployments), select the correct Nemotron-Super-49B quantization (FP8 is the Hopper-safe default; NVFP4 requires Blackwell and must NOT be assumed), register the model in Unity Catalog via MLflow, and deploy via the self-managed vLLM entrypoint pattern already proven by `defpredict-suggestor`/`-evaluator`. **Track B (reliability hardening):** write `src/llm/reliability.py` implementing the D-08–D-15 defense stack, wire it into `client.py` (`chat_completion_tools` gains `extra_body` passthrough + D-16 guard in `get_client`) and `registry.dispatch` (field-level errors replacing the generic `hint`), and write the `VERDICT` model in `schemas/llm.py`. Both tracks must converge in the D-06 probe suite: 115 real β candidates run through reliability.py with Nemotron live, asserting conformance ≥98% per thinking mode AND discrimination ≥80% on the matched-GT vs FP split.

**Primary recommendation:** Pin the D-14 baseline numbers as literals on Wave 0 before writing a single line of hardening code. Then gate Wave 1 on the D-20 GPU/quant confirmation (a CLI/API query, not a build). Serve Nemotron with the `GPU_XLARGE_8` template and `--tensor-parallel-size 8` (matching the proven 8-GPU tier); use FP8 unless Blackwell is explicitly confirmed. Wire guided decode via `extra_body={"structured_outputs": {"json": schema}}` (the current vLLM API; the `guided_json` alias still works but is pre-v0.12 legacy). The capability probe is a single cheap call per endpoint at startup — detect-once, cache, never re-probe on the hot path.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Nemotron deployment (vLLM entrypoint, MLflow registration) | Databricks GPU serving (infrastructure) | notebooks/deploy_nemotron.py (deployment script) | vLLM runs on the GPU serving container; the deploy script registers the model artifact in Unity Catalog and creates the endpoint |
| On-prem allow-list guard | API/Backend (client.py get_client) | config.py allow-list definitions | The guard sits at the LLM client factory — before any HTTP request leaves the process |
| Guided decode capability probe + cache | API/Backend (reliability.py) | client.py (chat_completion_tools extra_body passthrough) | One-time probe per endpoint at startup; the cache lives in process memory in reliability.py |
| Guided JSON schema injection | API/Backend (client.py chat_completion_tools) | reliability.py (schema builder helper) | The extra_body arg is threaded into the OpenAI client call in chat_completion_tools |
| Strict lossless coercion | API/Backend (reliability.py) | registry.dispatch, structured.py parse_structured | Coercion runs before pydantic validate; both dispatch paths call reliability.py |
| Field-level error formatting + bounded retry | API/Backend (reliability.py) | registry.dispatch (hint field upgrade) | Retry logic sits in reliability.py; registry.dispatch populates the reprompt message |
| VERDICT model definition | API/Backend (schemas/llm.py) | reliability.py (guided schema derivation) | VERDICT lives next to ParseFailed; tool_schema_for_databricks(VERDICT) produces the guided schema |
| Role/lineage tagging (D-17) | API/Backend (config.py) | serving.py (_DB_MODELS map) | verifier_model property + lineage tags live in config; serving.py maps the key to the endpoint id |
| D-06 probe suite (conformance + discrimination) | Test/Eval (tests/evals/test_verifier_probe.py) | reliability.py, schemas/llm.py | DeepEval test replays 115 candidates through reliability.py; asserts both dimensions of the pass bar |

---

## Standard Stack

### Core (already pinned in pyproject.toml — no new installs for client-side)

| Library | Version (pinned) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openai` | `>=2.40` (pyproject.toml) | OpenAI-compatible client for all Databricks endpoints | Already wired; `extra_body` passthrough is the guided-decode channel |
| `pydantic` | `>=2.7` | VERDICT model, coercion validation, schema derivation | Already in use; `tool_schema_for_databricks()` produces legal vLLM schemas |
| `json-repair` | `>=0.30` | L3 deterministic JSON salvage in structured.py | Already wired; not extended in Phase 6 |
| `structlog` | `>=24.1` | Near-miss counter + per-mode latency telemetry | Already wired; extend with new counters |
| `deepeval` | `>=4.1` | DeepEval pytest harness for D-06 probe suite | Already declared in CLAUDE.md stack |

### Server-Side (Nemotron vLLM container — NOT in app pyproject.toml)

| Component | Version Floor | Purpose | Notes |
|-----------|---------|---------|-------|
| `vllm` | `>=0.11` | Serves Nemotron with tool-parser + guided decode | Pin a concrete release when building the container; ≥0.12 uses `structured_outputs` API; ≥0.11 supports `guided_json` alias |
| `nvidia/Llama-3_3-Nemotron-Super-49B-v1_5` (HuggingFace) | v1.5 | The verifier model weights | Download to Databricks Volume or DBFS before serving |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `extra_body={"structured_outputs": {"json": schema}}` | `extra_body={"guided_json": schema}` | The legacy alias still accepted in vLLM <0.12; prefer the current API but handle both in the probe for forward compatibility |
| FP8 quantization (Hopper) | NVFP4 (Blackwell) | NVFP4 halves VRAM again but requires B200/GB200; only viable if Blackwell hardware is confirmed. BF16 is safe but requires all 8 H100s with high utilization. FP8 is the Hopper default. |
| FP8 quantization | AWQ/GPTQ INT4 | INT4 further reduces VRAM at some accuracy cost; viable fallback if FP8 doesn't fit on the confirmed GPU tier |

**Installation (server-side only — client-side already installed):**
```bash
# On the Databricks GPU cluster / serving container — not the app image
pip install "vllm>=0.11"
# Download model weights to a Databricks Volume before serving
# huggingface-cli download nvidia/Llama-3_3-Nemotron-Super-49B-v1_5 \
#   --local-dir /Volumes/defpredict/main/artifacts/nemotron-49b
```

**Version verification (client-side):**
```bash
pip show openai pydantic json-repair structlog deepeval
```

---

## Architecture Patterns

### System Architecture Diagram

```
[config.py verifier_model role]
        │
        ▼
[client.py get_client()]
  ← D-16 on-prem allow-list guard ─────────────────► BLOCK (loud fail) if not in allow-list
        │ allowed
        ▼
[reliability.py supports_guided_json(client, model)]
  ← detect-once, cached per served-model-name ──────► True/False cached in _guided_cache
        │
        ▼
[client.py chat_completion_tools(..., extra_body=?)]
  ← if supported: extra_body={"structured_outputs": {"json": schema}}
  ← if unsupported: no extra_body (fall through to native tool-parser)
        │
        ▼
[Nemotron vLLM endpoint on Databricks GPU_XLARGE_8]
  ← --tool-call-parser llama_nemotron_json
  ← --tool-parser-plugin <weights_dir>/llama_nemotron_toolcall_parser_no_streaming.py
  ← --enable-auto-tool-choice
  ← server-side structured_outputs backend (xgrammar/auto)
        │
        ▼ tool_calls returned (or prose in content if parser mismatch → caught by coercion)
        │
[reliability.py coerce_and_validate(turn, VERDICT)]
  1. json.loads(args)
  2. strict lossless coercion:
       numeric-string → number
       'true'/'false' → bool
       single-key wrapper unwrap (key == model name)
       enum tokens: PASS-THROUGH ONLY — not coerced
  3. VERDICT.model_validate(coerced)
        │ ok?
        ├── YES → return (verdict_instance, None)
        └── NO → field-level error message (which field, expected type)
                  │
                  └─ retries_left (cap=1, budget-counted)?
                       │ YES → corrective re-prompt → retry → coerce_and_validate
                       │        │ ok? YES → return (verdict_instance, None)
                       │        │ NO  → return (None, ParseFailed)
                       └─ NO → return (None, ParseFailed)  [never fabricate]
        │
        ▼
[VERDICT xor ParseFailed returned to caller]
[Phase 7 orchestrator maps ParseFailed → KEEP (never-drop policy)]
```

**Nemotron deployment flow (D-20 gate applies between steps 1 and 2):**
```
[Day-0 research task]
  → databricks serving-endpoints list / cluster instance type query
  → confirm GPU_XLARGE_8 hardware class (H100 vs Blackwell)
  ↓ [D-20 GATE: quant/GPU pair confirmed]
  → pick quant: FP8 (Hopper/H100) or NVFP4 (Blackwell only)
  → amend ADR-nemotron-verifier-model.md with confirmed pair

[Serving build]
  → download weights to /Volumes/defpredict/main/artifacts/nemotron-49b/
  → author notebooks/deploy_nemotron.py (mlflow.pyfunc.log_model + metadata entrypoint)
  → register in UC: defpredict.main.defpredict_nemotron
  → create endpoint: defpredict-nemotron (workload_type=GPU_XLARGE_8, scale_to_zero=False per D-04)
  → wait READY
  → run pre-wiring probes (MODEL-02)
```

### Recommended Project Structure

```
src/
├── llm/
│   ├── client.py          # + extra_body passthrough in chat_completion_tools (D-08)
│   │                      # + on-prem allow-list guard in get_client (D-16)
│   ├── structured.py      # UNCHANGED contract; imports reliability.py for coercion
│   └── reliability.py     # NEW (D-15): capability-probe cache, guided_json builder,
│                          #   strict lossless coercion, field-level error formatter,
│                          #   bounded retry (1 corrective reprompt)
├── schemas/
│   └── llm.py             # ParseFailed (exists) + NEW VERDICT model (D-07)
├── config.py              # + verifier_model property, Nemotron id + lineage tags (D-17),
│                          #   verifier_max_repair_calls knob (D-13)
└── databricks/
    └── serving.py         # + "nemotron" key in _DB_MODELS pointing to endpoint id
notebooks/
└── deploy_nemotron.py     # NEW: mlflow.pyfunc.log_model + serving endpoint creation
tests/
├── unit/
│   ├── test_reliability.py          # NEW: coercion allow-list, probe cache, field-level errors
│   ├── test_on_prem_guard.py        # NEW: allow-list guard blocks forbidden ids
│   └── test_verdict_schema.py       # NEW: VERDICT model validates / rejects enum tokens
└── evals/
    └── test_verifier_probe.py       # NEW: D-06 conformance + discrimination probe suite (DeepEval)
```

### Pattern 1: vLLM Launch Command (Nemotron, GPU_XLARGE_8 / H100, FP8)

**What:** Start the Nemotron server with FP8 weights, tensor-parallel-8 (one per GPU in GPU_XLARGE_8), and the Nemotron-specific tool parser and reasoning parser.

**When to use:** When GPU_XLARGE_8 hardware is confirmed as Hopper (H100). If Blackwell is confirmed instead, replace `--dtype fp8 --quantization fp8` with NVFP4 flags.

```bash
# Source: NVIDIA model card (HuggingFace nvidia/Llama-3_3-Nemotron-Super-49B-v1_5)
# + vLLM tool_calling docs (https://docs.vllm.ai/en/stable/features/tool_calling.html)
python3 -m vllm.entrypoints.openai.api_server \
  --model /Volumes/defpredict/main/artifacts/nemotron-49b \
  --served-model-name nemotron-super-49b-v1_5 \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.95 \
  --enable-auto-tool-choice \
  --tool-parser-plugin "/Volumes/defpredict/main/artifacts/nemotron-49b/llama_nemotron_toolcall_parser_no_streaming.py" \
  --tool-call-parser llama_nemotron_json \
  --host 0.0.0.0 \
  --port 8080
  # structured outputs ON by default (xgrammar/auto backend) — no extra flag needed
  # Optional: --structured-outputs-config.backend xgrammar   # pin if auto misbehaves
```

**BF16 alternative (if FP8 unavailable):**
Same command, remove `--dtype fp8 --quantization fp8`, add `--dtype bfloat16`. Needs all 8 H100s (8×80GB = 640GB) with `--gpu-memory-utilization 0.95` which is tight — FP8 halves it and is the safer default on H100.

**NVFP4 alternative (Blackwell ONLY — do NOT use on H100):**
`--tensor-parallel-size 1` (fits single B200 at ~80GB), different quantization flags. This path requires explicit Blackwell hardware confirmation (D-19/D-20 gate).

### Pattern 2: MLflow pyfunc Deployment (D-03 self-managed vLLM)

**What:** Register Nemotron as an MLflow pyfunc model with the vLLM entrypoint baked into the metadata. This is the deployment shape proven by defpredict-suggestor/-evaluator (GPU_XLARGE_8 workload_type).

**When to use:** Creating the Databricks model serving endpoint for Nemotron.

```python
# Source: Databricks custom model serving docs
# + deploy_adapters.py pattern (notebooks/deploy_adapters.py — the proven template)
import mlflow
import mlflow.pyfunc

class NemotronServingModel(mlflow.pyfunc.PythonModel):
    """Placeholder pyfunc — actual serving is done by the vLLM entrypoint."""
    def predict(self, context, model_input):
        raise NotImplementedError("Served via vLLM entrypoint, not pyfunc predict")

weights_dir = "/Volumes/defpredict/main/artifacts/nemotron-49b"
vllm_cmd = (
    "python3 -m vllm.entrypoints.openai.api_server "
    f"--model {weights_dir} "
    "--served-model-name nemotron-super-49b-v1_5 "
    "--trust-remote-code "
    "--tensor-parallel-size 8 "
    "--max-model-len 65536 "
    "--gpu-memory-utilization 0.95 "
    "--enable-auto-tool-choice "
    f"--tool-parser-plugin {weights_dir}/llama_nemotron_toolcall_parser_no_streaming.py "
    "--tool-call-parser llama_nemotron_json "
    "--host 0.0.0.0 --port 8080"
)

mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run(run_name="register-nemotron"):
    mlflow.pyfunc.log_model(
        name="defpredict_nemotron",
        python_model=NemotronServingModel(),
        artifacts={"model_dir": weights_dir},
        metadata={
            "task": "llm/v1/chat",
            "entrypoint": vllm_cmd,
        },
        registered_model_name="defpredict.main.defpredict_nemotron",
    )
```

Then create the endpoint:
```python
import httpx, os
payload = {
    "name": "defpredict-nemotron",
    "config": {
        "served_entities": [{
            "entity_name": "defpredict.main.defpredict_nemotron",
            "entity_version": "1",
            "workload_type": "GPU_XLARGE_8",  # proven tier on this workspace
            "workload_size": "Small",
            "scale_to_zero_enabled": False,    # D-04: always-warm
        }]
    }
}
```

### Pattern 3: Guided Decode via extra_body (D-08/D-09)

**What:** Pass the tool-argument schema as a server-side decoding constraint on the tool-call turn.

**When to use:** After `supports_guided_json()` returns True for the endpoint. Applied to ALL 7 review tools + VERDICT.

```python
# Source: vLLM structured outputs docs (https://docs.vllm.ai/en/stable/features/structured_outputs.html)
# Note: "guided_json" is the pre-v0.12 alias; "structured_outputs" is the current API.
# Both accepted in production vLLM; use structured_outputs API, handle guided_json as fallback.

def build_guided_extra_body(model_cls: type[BaseModel]) -> dict:
    """Build the extra_body dict for guided decoding on tool-call turns."""
    schema = tool_schema_for_databricks(model_cls)  # reuse existing sanitizer — never raw
    return {"structured_outputs": {"json": schema}}

# In chat_completion_tools, when supported:
extra = build_guided_extra_body(VERDICT) if supports_guided_json(client, model) else {}
resp = client.chat.completions.create(
    model=model,
    messages=messages,
    tools=tools,
    tool_choice="auto",
    temperature=0.0,
    max_tokens=256,
    extra_body=extra or None,
)
```

### Pattern 4: Capability Probe — Detect Once, Cache Per Endpoint (D-09)

**What:** A cheap single probe call to detect guided_json support. Mirrors the existing `response_format` BadRequestError→degrade pattern in `client.py`.

```python
# Source: mirrors client.py chat_completion_full BadRequestError degrade pattern
_guided_cache: dict[str, bool] = {}

def supports_guided_json(client: OpenAI, model: str) -> bool:
    if model in _guided_cache:
        return _guided_cache[model]
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            extra_body={"structured_outputs": {"json": {"type": "object", "properties": {}, "additionalProperties": False}}},
        )
        _guided_cache[model] = True
    except BadRequestError:
        _guided_cache[model] = False    # endpoint rejected it → fall through to native parser
    except Exception:
        _guided_cache[model] = False    # fail-safe: never block the real call on probe error
    return _guided_cache[model]
```

### Pattern 5: Thinking-Mode Toggle (D-18)

**What:** Set reasoning ON or OFF via the system prompt. The served endpoint is the same regardless of mode — no restart needed.

```python
# Source: NVIDIA model card (HuggingFace nvidia/Llama-3_3-Nemotron-Super-49B-v1_5)
# The v1.5 card documents /no_think for OFF; v1 used "detailed thinking off".
# The AI-SPEC confirms both and says to probe which token actually flips behavior.

THINKING_ON_SYSTEM = (
    "You are a regulatory compliance verifier. detailed thinking on\n"
    "Analyze the candidate deficiency carefully before emitting the VERDICT."
)
THINKING_OFF_SYSTEM = (
    "/no_think\n"
    "You are a regulatory compliance verifier. Emit the VERDICT directly."
)
# PROBE NOTE: run both strings in the pre-wiring probe (D-18 task) and confirm which
# actually changes the token count / presence of <think> tags in the response.
# The reasoning toggle string is version-dependent and must be empirically verified.
```

**Temperature per mode:**
- Reasoning OFF: `temperature=0.0` (greedy), `max_tokens=256`
- Reasoning ON: `temperature=0.6`, `top_p=0.95`, `max_tokens=2048`

### Pattern 6: On-Prem Allow-List Guard (D-16)

**What:** Reject any model-id not in the on-prem allow-list at the client boundary.

```python
# Source: config.py resolve_detector_model pattern (the existing precedent)
_ON_PREM_ALLOW_LIST = {
    # Databricks-hosted open-weights
    "databricks-meta-llama-3-3-70b-instruct",
    "databricks-meta-llama-3-1-8b-instruct",
    "databricks-qwen35-122b-a10b",
    "databricks-qwen3-next-80b-a3b-instruct",
    # Self-managed Nemotron (Phase 6)
    "nemotron-super-49b-v1_5",
    "defpredict-nemotron",
    # Fine-tuned defpredict variants
    "defpredict-suggestor",
    "defpredict-evaluator",
}

def get_client(model: str | None = None) -> OpenAI:
    if model is not None and model not in _ON_PREM_ALLOW_LIST:
        raise ValueError(
            f"Model {model!r} is not in the on-prem allow-list. "
            f"Forbidden models include databricks-claude-*, databricks-gpt-5-*, "
            f"databricks-gemini-* — regulated pharma data must never leave on-prem infrastructure."
        )
    # ... existing client construction ...
```

### Anti-Patterns to Avoid

- **Reusing the Llama/Qwen tool-call parser for Nemotron.** Nemotron uses `--tool-call-parser llama_nemotron_json` with its own plugin file. Using `llama3_json` silently returns tool calls as prose in `content` rather than structured `tool_calls`.
- **Re-probing guided_json capability on every call.** The D-09 probe must be detect-once-and-cache. Re-probing doubles request volume and pollutes the D-18 latency numbers.
- **Sending raw `model.model_json_schema()` as the guided schema.** Always route through `tool_schema_for_databricks()` which strips `pattern`, flattens `anyOf[X, null]`, and sets `additionalProperties: false`. Raw schemas will be rejected by some vLLM backends.
- **Coercing enum values.** The `verdict` field is `KEEP|DOWNGRADE`. A token that isn't exactly one of these FAILS to ParseFailed — it is never snapped to nearest. This is D-11's hardest rule.
- **Assuming NVFP4 without confirming Blackwell.** NVFP4 is Blackwell-only. On H100 (Hopper), it either fails or silently falls back to a slower path. Use FP8 unless the hardware is explicitly confirmed as Blackwell.
- **Setting `scale_to_zero_enabled=True` for the Nemotron endpoint.** D-04 mandates always-warm. The existing `defpredict-suggestor/-evaluator` also have `scale_to_zero=False` de facto (GPU_XLARGE_8 likely disallows it; H100 endpoints historically don't support scale-to-zero on this workspace).
- **Stuffing whole documents into the verify context.** Input stays narrow (one cited span + one rule + the claim). Reasoning-ON traces are the only real context risk; the L2 truncation-retry in structured.py bounds that.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema sanitization for vLLM | Custom schema stripper | `tool_schema_for_databricks()` in structured.py | Already handles `$ref` inlining, `pattern` removal, `anyOf[X, null]` flattening, `additionalProperties: false` — exactly the constraints vLLM and Databricks strict mode require |
| JSON repair | Custom JSON fixer | `json-repair` via `parse_structured()` in structured.py | Already wired as L3 with `json_repair()` + exception handling; do not duplicate |
| Retry/backoff for LLM calls | Custom retry loop | Existing `_RETRYABLE` + exponential backoff in `chat_completion_tools` | Already handles `APIConnectionError`, `APITimeoutError`, `RateLimitError` with correct delays |
| Structured output contract | Custom result type | `ParseFailed` in schemas/llm.py + the `instance XOR ParseFailed` pattern | Already established in structured.py; VERDICT uses the same contract |
| Tool schema derivation | Handwritten JSON schemas | `build_tool_schema(model_cls, name, description)` | Derives from pydantic — single source of truth ensures the shown schema and the validating model cannot drift |
| DeepEval custom metrics | Hand-rolled rate assertions | `@pytest.mark` + `deepeval` custom metric class | DeepEval already provides `conformance_rate` metric pattern; handles threshold assertions and CI integration |
| Telemetry counters | Print statements | `structlog.get_logger()` + bound counter increments | Already established as the telemetry substrate (D-TEL4 repair_layer counters already use it) |

**Key insight:** The entire defense stack already exists in outline — guided decode is the one new layer. Adding it via `extra_body` in `chat_completion_tools` is a one-line change to the existing call; the rest of the reliability.py work is organizing the existing patterns (coercion from the Qwen near-miss history, field-level errors extending the existing `hint` field, the ParseFailed sentinel already in schemas/llm.py) into one shared module.

---

## Quant/GPU Decision Procedure (D-19/D-20)

This is the HARD BLOCKER that gates the serving build. The decision procedure is:

**Step 1 — Enumerate the actual GPU hardware on GPU_XLARGE_8:**
```bash
# The two proven endpoints use GPU_XLARGE_8 (confirmed via live CLI probe 2026-08-08).
# GPU_XLARGE (single GPU) on AWS Databricks is documented as H100-80GB.
# GPU_XLARGE_8 is the 8-GPU tier — strong evidence of 8×H100-80GB = 640GB total VRAM.
# Confirm by querying the workspace cluster types:
databricks clusters list-node-types --profile amneal-dev 2>/dev/null | python3 -m json.tool | grep -A5 -B5 "H100\|A100\|Blackwell\|B200"
# OR check the cluster type used by the existing endpoints:
databricks api get "/api/2.0/serving-endpoints/defpredict-suggestor" --profile amneal-dev
# The workload_type GPU_XLARGE_8 is confirmed; the hardware class needs one verification step.
```

**Step 2 — GPU hardware → quantization mapping:**

| Confirmed GPU | VRAM total | Recommended Quant | tensor-parallel | Notes |
|--------------|------------|-----------------|----------------|-------|
| 8×H100-80GB (Hopper) | 640GB | **FP8** | 8 | 49B FP8 ≈ 49GB weights; fits easily. BF16 ≈ 98GB also fits but wastes headroom. |
| 8×A100-80GB (Ampere) | 640GB | **BF16 or FP8** | 8 | FP8 supported on Ampere in vLLM via `llm_compressor`; BF16 also fits |
| 1×B200-80GB (Blackwell) | 80GB | **NVFP4** | 1 | NVFP4 ≈ 25GB; only option that fits a single Blackwell GPU |
| 2×H100-80GB | 160GB | **FP8** | 2 | Per NVIDIA cookbook for -49B |

**Step 3 — Amend ADR:** Once the hardware is confirmed, update `.planning/ADR-nemotron-verifier-model.md` with: `Confirmed GPU: GPU_XLARGE_8 = [X×GPUNAME]; Quant: [FP8/NVFP4/BF16]; tensor-parallel: [N]`.

**Working assumption for planning:** GPU_XLARGE_8 = 8×H100-80GB (Hopper). **FP8 is the default recommendation.** NVFP4 is explicitly excluded until Blackwell is confirmed. This assumption must be validated on Day 0 of Wave 1 — it is the D-20 gate.

[VERIFIED: live databricks CLI probe — GPU_XLARGE_8 workload_type on defpredict-suggestor and defpredict-evaluator, 2026-08-08]
[ASSUMED: GPU_XLARGE_8 hardware = 8×H100. Strong inference from Databricks documentation (GPU_XLARGE = 1×H100-80GB; _8 suffix = 8 units). Must be confirmed via cluster node type query.]

---

## Phase 3 Baseline Telemetry — Pinned Numbers (D-14)

These numbers MUST be written as literals in the plan before any hardening code is written.

**Llama 3.3 70B (v1 scored runs — 3 runs, 03-18-SUMMARY.md):**
- pre_repair_malformed: 0 / 0 / 0 (all runs)
- post_repair_malformed: 0 / 0 / 0 (all runs)
- total_tool_calls: 7 / 17 / 7

**Llama 3.3 70B (v3 scored runs — 3 runs, 03-19-V3-RUN-NOTES.md):**
- pre_repair_malformed: not explicitly broken out in v3 notes (D-TEL4 not referenced in the v3 report)
- post_repair_malformed: not explicitly broken out in v3 notes
- Known tool rejections: `not_found` (tool-name calls for non-existent tools); `range_too_large`
- These are TOOL-NAME rejections, not arg-format malformed-arg failures — a distinct class

**Qwen fidelity probe (1 run, 03-QWEN-FIDELITY-PROBE.md):**
- pre_repair_malformed: 0
- post_repair_malformed: 4 (out of 5 total tool-call attempts)
- post-repair conformance rate: 1/5 = 20% (fails the ≥95% bar)
- Failure class: wholesale unrepairable `read_guideline` args — NOT optional-param near-misses
- Additional observation: Qwen content shape differed (reasoning-list vs flat string) — pydantic serialization warning recorded

**Baseline for D-14 comparison (write these as literals in PLAN.md Wave 1):**
- Llama malformed-arg rate (v1 scored): pre=0%, post=0% (3-run average)
- Qwen malformed-arg rate (probe): pre=0%, post=4/5=80% (1 probe run)
- "Measurably reduced" for Phase 6 = post-repair malformed-arg rate arithmetically lower than these pins after hardening lands, replayed on the same probe suite via reliability.py

[VERIFIED: 03-18-SUMMARY.md D-TEL4 section; 03-QWEN-FIDELITY-PROBE.md clause (a) reading — 2026-08-08]

---

## Common Pitfalls

### Pitfall 1: Wrong Tool-Call Parser Family

**What goes wrong:** The `--tool-call-parser` value is shared across models, or the plugin file path is wrong. Tool calls come back as prose in `content` rather than structured `tool_calls` — the reliability layer never gets invoked because there are no structured tool_calls to parse.

**Why it happens:** Copy-paste from the Llama-3.3-70B deployment which uses `llama3_json` (a built-in parser, no plugin needed). Nemotron requires `llama_nemotron_json` registered via `--tool-parser-plugin` pointing to the plugin file shipped IN the model weights directory.

**How to avoid:** The plugin file `llama_nemotron_toolcall_parser_no_streaming.py` must be downloaded alongside the model weights. The `--tool-parser-plugin` path is ABSOLUTE and points to wherever the weights were downloaded on the serving container. Verify in the pre-wiring probe: confirm `tool_calls` is populated (not empty) and `content` is empty (or None) on a tool-call turn.

**Warning signs:** `turn.tool_calls` is `[]`, `turn.content` contains the response text. `finish_reason` is `stop` instead of `tool_calls`.

### Pitfall 2: Reasoning Toggle String Not Probed

**What goes wrong:** The system prompt uses `"detailed thinking off"` (v1 string) but the served v1.5 model expects `/no_think` — or vice versa. The model silently stays in the wrong mode. The D-18 latency/token split is invalid because both "modes" ran the same path.

**Why it happens:** The NVIDIA model card and the HuggingFace model card use different strings across versions. The AI-SPEC explicitly flags this.

**How to avoid:** Probe both strings in the pre-wiring (MODEL-02). Compare `completion_tokens` counts — reasoning-ON generates a `<think>...</think>` block that dramatically inflates completion tokens. The string that produces the token-count split IS the correct toggle. Record the confirmed string in ADR and in the config.

**Warning signs:** Both "modes" produce identical `completion_tokens` counts.

### Pitfall 3: NVFP4 on Hopper Hardware

**What goes wrong:** NVFP4 is selected thinking it will work on H100. Either vLLM errors on launch, or silently falls back to a slower emulation path that makes the benchmark invalid.

**Why it happens:** NVFP4 (NVIDIA's 4-bit floating-point format) uses Blackwell-specific tensor cores (B200/GB200). It is not a generic INT4 format.

**How to avoid:** The D-20 gate explicitly blocks serving build until GPU hardware is confirmed. FP8 is safe on both Hopper and Blackwell (Hopper has native FP8 tensor cores since H100). When in doubt, use FP8.

**Warning signs:** vLLM launch fails with a CUDA capability error, or the quantization flag is silently ignored.

### Pitfall 4: Guided Decode Probe on Hot Path

**What goes wrong:** `supports_guided_json()` is called on every tool-call turn (not cached). This doubles request volume, pollutes the D-18 latency measurements, and may hit rate limits.

**Why it happens:** The probe function is easy to call; caching requires a module-level dict and slightly more structure.

**How to avoid:** The `_guided_cache` dict is a module-level singleton in `reliability.py`. The probe is called once per served-model-name (or at startup). The cache key is the `served-model-name` (e.g., `"nemotron-super-49b-v1_5"`) not the endpoint URL.

**Warning signs:** D-18 latency numbers for the "probe" endpoint are approximately double what they should be; JSONL logs show alternating probe and real calls.

### Pitfall 5: Fabricated Verdict on ParseFailed

**What goes wrong:** The reliability layer, instead of returning `ParseFailed`, returns `VERDICT(verdict="KEEP", confidence=0.5, rationale="parsing failed", grounding_span="")` as a synthetic fallback. Phase 7 treats this as a real KEEP from the verifier.

**Why it happens:** It feels "safe" to default to KEEP (never-drop). But this conflates "verifier said KEEP" with "we couldn't read the verifier" — exactly the Phase-3 hidden-fallback lesson.

**How to avoid:** D-12 is the hard constraint. `reliability.py` returns `tuple[VERDICT | None, ParseFailed | None]` — exactly one is non-None, never fabricate. Unit test the invariant: on a deliberately bad model output, assert return[0] is None AND return[1] is not None.

**Warning signs:** `ParseFailed` counter in structlog is consistently zero even when Qwen/Llama is known to produce malformed args.

### Pitfall 6: Coercing an Enum Value

**What goes wrong:** A model returns `verdict="Keep"` (wrong case) or `verdict="KEEP."` (trailing period). The coercion layer "helpfully" maps it to `Verdict.KEEP`. The advertised schema appears strict but is actually loose — SC4 violated.

**Why it happens:** The `verdict` field looks like a string that's "close" to a valid value. It's tempting to add case normalization.

**How to avoid:** D-11 forbids enum coercion. The coercion allow-list is: numeric-string→number, `'true'/'false'`→bool, single-key wrapper unwrap only. The `verdict` field is PASS-THROUGH — if it's not exactly `KEEP` or `DOWNGRADE`, it fails to `ParseFailed` and the near-miss token is logged. This ensures the discrimination bar (D-06b) is measuring what the model actually produces, not what we coerced.

**Warning signs:** The near-miss log shows variants like `"keep"`, `"KEEP."`, `"Keep."` being coerced — these should appear as ParseFailed + logged near-miss, not as successful validates.

### Pitfall 7: tool_schema_for_databricks Bypassed for Guided Schema

**What goes wrong:** The guided schema is built with `VERDICT.model_json_schema()` directly instead of `tool_schema_for_databricks(VERDICT)`. The raw schema includes `$ref` (from enums), `anyOf` (from optional fields), and may include `pattern` — all of which some vLLM backends reject.

**Why it happens:** `model_json_schema()` is one less function call. It looks right.

**How to avoid:** Always use `tool_schema_for_databricks()` which inlines `$ref`, strips `pattern`, flattens `anyOf[X, null]`, and forces `additionalProperties: false`. The existing test `test_raw_schema_is_illegal_negative_control` in `test_tool_schema_derivation.py` documents why the raw schema is illegal.

---

## Code Examples

### VERDICT Model (D-07)

```python
# Source: 06-AI-SPEC.md Section 4b + 06-CONTEXT.md D-07
# File: src/schemas/llm.py (alongside ParseFailed)
from enum import Enum
from pydantic import BaseModel, Field

class VerdictChoice(str, Enum):
    KEEP = "KEEP"
    DOWNGRADE = "DOWNGRADE"

class VERDICT(BaseModel):
    """Minimal verifier verdict model — D-07. Phase 7 extends, never redefines."""
    verdict: VerdictChoice          # NEVER coerced (D-11); off-value → ParseFailed
    confidence: float = Field(ge=0.0, le=1.0)   # coercible: numeric-string→float (lossless)
    rationale: str                  # why keep/downgrade (for E6 human review)
    grounding_span: str             # verbatim cited span the verdict rests on
```

### Strict Lossless Coercion (D-11)

```python
# Source: 06-CONTEXT.md D-11; 03-QWEN-FIDELITY-PROBE.md failure class analysis
# File: src/llm/reliability.py

def strict_coerce(raw_args: dict, model_cls: type[BaseModel]) -> dict:
    """Apply the D-11 allow-list of lossless coercions before pydantic validate.
    
    Allowed:
      - numeric-string → number (whole string is a valid number; no truncation)
      - 'true' / 'false' → bool (case-insensitive; exact match only)
      - single-key wrapper unwrap (key matches model class name; e.g. {"VERDICT": {...}} → {...})
    
    Forbidden:
      - enum snapping / nearest-match (e.g. 'keep' → 'KEEP')
      - partial numeric coercion ('12abc' → 12)
      - any coercion that changes the information content
    
    Every rejected near-miss is logged via structlog.
    """
    import structlog
    log = structlog.get_logger()
    
    # Unwrap single-key wrapper if key matches model name
    if len(raw_args) == 1:
        (k, v) = next(iter(raw_args.items()))
        if k == model_cls.__name__ and isinstance(v, dict):
            log.info("coercion_wrapper_unwrap", model=model_cls.__name__, key=k)
            raw_args = v
    
    coerced = {}
    for field_name, value in raw_args.items():
        if isinstance(value, str):
            # numeric-string → number
            try:
                if '.' in value:
                    coerced[field_name] = float(value)
                    log.info("coercion_numeric_string", field=field_name, value=value)
                else:
                    coerced[field_name] = int(value)
                    log.info("coercion_numeric_string", field=field_name, value=value)
                continue
            except ValueError:
                pass
            # 'true'/'false' → bool
            if value.lower() == 'true':
                coerced[field_name] = True
                log.info("coercion_bool_string", field=field_name, value=value)
                continue
            if value.lower() == 'false':
                coerced[field_name] = False
                log.info("coercion_bool_string", field=field_name, value=value)
                continue
            # Enum fields: pass-through only — log near-misses
            field_info = model_cls.model_fields.get(field_name)
            if field_info is not None:
                annotation = field_info.annotation
                if hasattr(annotation, '__mro__') and Enum in annotation.__mro__:
                    valid = {e.value for e in annotation}
                    if value not in valid:
                        log.warning(
                            "coercion_enum_near_miss_rejected",
                            field=field_name,
                            value=value,
                            valid_values=list(valid),
                        )
                        # Do not coerce — let pydantic raise ValidationError
        coerced[field_name] = value
    return coerced
```

### Field-Level Error Formatter (RELIABILITY-02)

```python
# Source: 06-CONTEXT.md D-12; registry.py hint field (the existing pattern to extend)
# File: src/llm/reliability.py

from pydantic import ValidationError

def format_field_level_reprompt(error: ValidationError, model_cls: type[BaseModel]) -> str:
    """Format a corrective re-prompt naming the failing field and expected type.
    
    Replaces the generic 'send a JSON object matching this tool's schema exactly' hint
    with field-specific guidance (RELIABILITY-02).
    """
    lines = [f"The VERDICT args failed validation. Please fix the following fields:"]
    for e in error.errors():
        loc = ".".join(str(x) for x in e["loc"])
        msg = e["msg"]
        typ = e.get("type", "")
        field_info = model_cls.model_fields.get(loc)
        expected = ""
        if field_info is not None:
            expected = f" (expected type: {field_info.annotation.__name__ if hasattr(field_info.annotation, '__name__') else field_info.annotation})"
        lines.append(f"  - Field '{loc}': {msg}{expected} [error_type={typ}]")
    lines.append("Return ONLY valid JSON matching the VERDICT schema.")
    return "\n".join(lines)
```

### DeepEval Probe Suite Skeleton (D-06)

```python
# Source: 06-AI-SPEC.md Section 5; 06-CONTEXT.md D-05/D-06
# File: tests/evals/test_verifier_probe.py

import json
from pathlib import Path
import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

BETA_SUMMARY = Path(".planning/phases/05-deterministic-structural-cross-document-recall/beta-measurement/beta-measurement-summary.json")
MATCHED_GT_IDS = {"A-09", "A-11", "B-01", "C-01", "C-06", "MS-01"}  # from beta-measurement-summary.json

class ConformanceRateMetric(BaseMetric):
    """D-06a: ≥98% machine-parsable VERDICT post-repair, per thinking mode."""
    threshold = 0.98
    name = "conformance_rate"
    
    def measure(self, test_case: LLMTestCase) -> float:
        # replay probe suite through reliability.py
        # count parse successes / total
        ...
    
    def is_successful(self) -> bool:
        return self.score >= self.threshold

class DiscriminationAccuracyMetric(BaseMetric):
    """D-06b: ≥80% correct on matched-GT (KEEP) vs FP-over-emit (DOWNGRADE) split."""
    threshold = 0.80
    name = "discrimination_accuracy"
    
    def measure(self, test_case: LLMTestCase) -> float:
        # for each probe: check verdict matches expected (GT→KEEP, FP→DOWNGRADE)
        # also assert: majority verdict NOT ≥95% (constant-verdict tripwire)
        ...
    
    def is_successful(self) -> bool:
        return self.score >= self.threshold

@pytest.mark.parametrize("thinking_mode", ["on", "off"])
def test_verifier_conformance_and_discrimination(thinking_mode):
    """Gate: conformance ≥98% AND discrimination ≥80%, both modes."""
    # Load 115 β candidates from report JSONs
    # Run reliability.py with Nemotron endpoint
    # Assert both metrics pass
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `guided_json` extra_body param | `structured_outputs.json` extra_body param | vLLM v0.12 | Legacy alias still accepted; plan for current API but handle both |
| Llama-3.3-70B as the strongest on-prem model | Nemotron-Super-49B as verifier/reasoning model | Phase 6 | Adds thinking-mode toggle, DPO tool-calling, decorrelated lineage from Qwen |
| Generic `hint` in ToolRejected | Field-level error messages (field name + expected type) | Phase 6 | Enables targeted corrective re-prompt for specific failing fields |
| No guided-decode on tool-call path | `extra_body={"structured_outputs": {"json": schema}}` on every tool-call turn | Phase 6 | Server-side schema enforcement as L0 before the existing repair stack |
| NVFP4 (planned in ADR, pending hardware confirmation) | FP8 (Hopper default) or NVFP4 (Blackwell confirmed) | Phase 6 D-19/D-20 gate | Prevents a wrong-GPU quantization from breaking the serving build |
| No verifier_model role in config | verifier_model property in Settings resolving to Nemotron | Phase 6 | Phase 7 can route verification calls without knowing the endpoint id |

**Deprecated/outdated:**
- `guided_json` as the primary extra_body key: still works in vLLM but superseded by `structured_outputs` API (treat as fallback).
- Thinking-mode toggle string `"detailed thinking on/off"`: used in v1 docs; v1.5 card documents `/no_think`. Probe both.
- GGUF quantization for vLLM: GGUF is llama.cpp native, not a first-class vLLM path. Do not plan around it.

---

## Runtime State Inventory

This is a greenfield deployment (Nemotron is not currently deployed per D-01). However there is relevant state to check:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | No Nemotron endpoint currently in `aip-amn-dev` (verified 2026-08-08: 58 endpoints searched, 0 match nemotron/nvidia/49b) | None — deploy from scratch |
| Live service config | `defpredict-suggestor` and `defpredict-evaluator` use `GPU_XLARGE_8` — this workload type exists and is provisioned on the workspace | Reuse `GPU_XLARGE_8` for Nemotron endpoint |
| OS-registered state | None — all serving is Databricks-managed | None |
| Secrets/env vars | `DATABRICKS_HOST`, `DATABRICKS_TOKEN` already in `.env`; `verifier_model` env var is new (add to Settings) | Add `verifier_model: str = ""` to Settings; default resolves via `verifier_model` property |
| Build artifacts | Model weights must be downloaded to `/Volumes/defpredict/main/artifacts/nemotron-49b/` before deploy | Download task required (Wave 1 Day 0 or pre-work) |

**Nothing found in categories: OS-registered state — verified by CLI endpoint enumeration.**

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | GPU_XLARGE_8 hardware = 8×H100-80GB (Hopper) | Quant/GPU Decision Procedure | If Blackwell, FP8 is still safe but NVFP4 becomes an option. If A100, FP8 still works. Risk is low — wrong assumption doesn't break anything, just misses an optimization. |
| A2 | The plugin file `llama_nemotron_toolcall_parser_no_streaming.py` ships inside the HuggingFace model weights directory | vLLM Launch Command | If the file isn't in the weights dir, the tool-parser-plugin path is wrong and vLLM won't start. Pre-wiring probe (MODEL-02) will catch this. |
| A3 | `/no_think` (v1.5 string) is the correct reasoning-OFF toggle for the served model | Thinking-Mode Toggle pattern | If the served build is v1 (uses `"detailed thinking off"`), the OFF probe silently won't work. D-18 probe task explicitly verifies which string flips behavior. |
| A4 | `GPU_XLARGE_8` endpoints support `scale_to_zero_enabled=False` (always-warm) | MLflow deployment pattern | The existing `defpredict-suggestor/-evaluator` have this config and are READY — confirming the endpoint type supports always-warm. Low risk. |
| A5 | The vLLM `structured_outputs` API (not just `guided_json` alias) is available in the vLLM version on the workspace GPU serving container | Guided Decode pattern | If vLLM version is pre-0.12, only `guided_json` alias works. The probe (D-09) catches this at runtime — fail-safe to native parser. |

---

## Open Questions

1. **What is the exact GPU hardware on GPU_XLARGE_8?**
   - What we know: `GPU_XLARGE_8` is the confirmed workload_type on both `defpredict-suggestor` and `defpredict-evaluator` (live CLI probe 2026-08-08). Databricks documents `GPU_XLARGE` as 1×H100-80GB; the `_8` suffix strongly implies 8 units.
   - What's unclear: The exact GPU model (H100 SXM5 vs PCIe? NVLink vs PCIe fabric?). Whether Blackwell (B200) has been provisioned for this workspace.
   - Recommendation: **Day 0 task — run `databricks clusters list-node-types --profile amneal-dev | python3 -m json.tool` and grep for GPU identifiers.** This resolves D-19 and unblocks D-20.

2. **vLLM version on the GPU serving container?**
   - What we know: The workspace used `GPU_XLARGE_8` for transformers-based models (fine-tuned Llama 8B). The vLLM version available on the serving container is determined by the Databricks ML runtime version.
   - What's unclear: Whether the available runtime supports vLLM ≥0.11 with the `llama_nemotron_json` parser natively, or whether a custom requirements.txt is needed in the MLflow artifact.
   - Recommendation: Include `extra_pip_requirements=["vllm>=0.11"]` in the `mlflow.pyfunc.log_model` call to ensure the correct version is available.

3. **Model weights download mechanism?**
   - What we know: HuggingFace hub (`nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`) is the source. The workspace has `/Volumes/defpredict/main/artifacts/` for artifact storage.
   - What's unclear: Whether HuggingFace is reachable from the Databricks workspace network, or whether a VPN/proxy is needed. Also: whether the NVIDIA Open Model License + Llama 3.3 Community License have been reviewed/accepted for the organization.
   - Recommendation: Pre-check network reachability and license acceptance before Wave 1 build starts. This is a potential blocker that is not a code task.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `databricks` CLI | D-19 GPU enumeration; D-20 gate | ✓ | v1.6.0 | — |
| Databricks workspace `aip-amn-dev` | All serving tasks | ✓ | Authenticated (dev.desai@amneal.com) | — |
| `GPU_XLARGE_8` workload type | Nemotron endpoint (D-04) | ✓ | Confirmed on 2 live endpoints | — |
| HuggingFace model hub | Nemotron weights download | Unknown | — | Internal mirror / pre-downloaded DBFS copy |
| vLLM `>=0.11` on serving container | D-03 self-managed vLLM | Unknown | — | Include in `extra_pip_requirements` |
| `deepeval>=4.1` | D-06 probe suite | Unknown (dev env) | — | `pip install deepeval>=4.1` (already in CLAUDE.md stack) |
| Nemotron weights in DBFS/Volume | Serving build | ✗ | — | Must download before Wave 1 deploy step |

**Missing dependencies with no fallback:**
- Nemotron weights — must be downloaded to `/Volumes/defpredict/main/artifacts/nemotron-49b/` before the serving build starts. This is a prerequisite step, not a code task.

**Missing dependencies with fallback:**
- HuggingFace hub reachability: fallback is using a pre-staged DBFS copy if the hub is not reachable from the workspace.
- vLLM on container: fallback is including `extra_pip_requirements=["vllm>=0.11"]` in the MLflow artifact.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + deepeval 4.x |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) — existing config, asyncio_mode=auto |
| Quick run command | `pytest tests/unit/test_reliability.py tests/unit/test_on_prem_guard.py tests/unit/test_verdict_schema.py -x` |
| Full suite command | `deepeval test run tests/evals/test_verifier_probe.py --identifier "phase6-verifier-conformance-discrimination"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-01 (SC1) | No external endpoint ever configured/called | unit | `pytest tests/unit/test_on_prem_guard.py -x` | ❌ Wave 0 |
| MODEL-02 (SC2) | Nemotron pre-wiring probes pass (vLLM tool-call + thinking ON/OFF + tool-parser flags) | integration (live endpoint) | `pytest tests/integration/test_nemotron_probe.py -x` | ❌ Wave 0 |
| RELIABILITY-01 | guided_json capability probe returns True/False; extra_body wired on supported endpoints | unit | `pytest tests/unit/test_reliability.py::test_guided_probe_caches -x` | ❌ Wave 0 |
| RELIABILITY-02 | Field-level errors name the failing field + expected type (not generic hint) | unit | `pytest tests/unit/test_reliability.py::test_field_level_error_format -x` | ❌ Wave 0 |
| RELIABILITY-03 | Coercion handles numeric-string→number, bool-string, single-key unwrap; enums never coerced | unit | `pytest tests/unit/test_reliability.py::test_strict_coerce -x` | ❌ Wave 0 |
| D-06a (conformance) | ≥98% parsable VERDICT post-repair, thinking ON + OFF each | integration (live Nemotron) | `deepeval test run tests/evals/test_verifier_probe.py` | ❌ Wave 0 |
| D-06b (discrimination) | ≥80% correct on known-good/known-bad split | integration (live Nemotron) | `deepeval test run tests/evals/test_verifier_probe.py` | ❌ Wave 0 |
| D-12 (typed failure honesty) | ParseFailed on exhausted retry; no fabricated verdict | unit | `pytest tests/unit/test_reliability.py::test_no_fabricated_verdict -x` | ❌ Wave 0 |
| D-14 (baseline delta) | Post-hardening malformed-arg rate < pinned Phase-3 baseline | integration (probe replay) | `pytest tests/evals/test_reliability_baseline.py -x` | ❌ Wave 0 |
| D-16 (allow-list guard) | Forbidden model ids (databricks-claude-*, gpt-5-*, gemini-*) raise ValueError | unit | `pytest tests/unit/test_on_prem_guard.py -x` | ❌ Wave 0 |
| D-17 (lineage tags) | verifier_model resolves to Nemotron; lineage tag = nemotron-on-llama | unit | `pytest tests/unit/test_config.py::test_verifier_model_role -x` | ❌ Wave 0 |
| D-18 (thinking mode split) | Both modes clear D-06a; latency/token counts differ between modes | integration | included in test_verifier_probe.py | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_reliability.py tests/unit/test_on_prem_guard.py tests/unit/test_verdict_schema.py -x`
- **Per wave merge:** `pytest tests/unit/ tests/evals/test_reliability_baseline.py -x`
- **Phase gate:** `deepeval test run tests/evals/test_verifier_probe.py --identifier "phase6-verifier-conformance-discrimination"` — full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_reliability.py` — covers RELIABILITY-01/02/03, D-09, D-11, D-12
- [ ] `tests/unit/test_on_prem_guard.py` — covers MODEL-01 / D-16
- [ ] `tests/unit/test_verdict_schema.py` — covers D-07 VERDICT model + schema derivation
- [ ] `tests/integration/test_nemotron_probe.py` — covers MODEL-02 (live endpoint required; mark with `@pytest.mark.integration`)
- [ ] `tests/evals/test_verifier_probe.py` — covers D-06a/D-06b/D-14/D-18 (live Nemotron required; DeepEval harness)
- [ ] `tests/evals/test_reliability_baseline.py` — covers D-14 pinned-baseline diff harness
- [ ] `tests/unit/test_config.py` additions — covers D-17 verifier_model + lineage tags

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Not applicable — serving endpoints use workspace bearer tokens |
| V3 Session Management | No | Stateless per verdict; no session store |
| V4 Access Control | YES | D-16 on-prem allow-list guard at `get_client` + `resolve_detector_model` precedent |
| V5 Input Validation | YES | `tool_schema_for_databricks()` + pydantic model validation; coercion is strictly lossless |
| V6 Cryptography | No | TLS for Databricks endpoints; no custom crypto |
| V7 Error Handling | YES | `ParseFailed` sentinel prevents raw LLM output leaking to frontend |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Config-drift model-id reaches external endpoint | Information Disclosure | D-16 allow-list guard: `ValueError` on any non-allow-listed id; fail-loud, never silent downgrade |
| Regulated pharma data sent to Claude/GPT/Gemini | Information Disclosure | D-16 guard explicitly targets `databricks-claude-*`, `databricks-gpt-5-*`, `databricks-gemini-*` |
| Malformed verdict fabricated as KEEP (silent) | Tampering | D-12: `VERDICT XOR ParseFailed` contract; unit test asserts no fabricated verdict |
| Adversarial tool args bypassing schema via coercion | Tampering | D-11 strict allow-list; enum never coerced; every near-miss logged |
| Reasoning trace containing PII/IP leaked in `rationale` field | Information Disclosure | All serving is on-prem (Databricks `aip-amn-dev`); `rationale` is internal, not surfaced to FDA |

---

## Sources

### Primary (HIGH confidence)

- Live Databricks CLI probe (`databricks serving-endpoints get defpredict-suggestor/evaluator --profile amneal-dev`) — confirmed `workload_type: GPU_XLARGE_8` on both endpoints, 2026-08-08 [VERIFIED]
- `src/llm/client.py`, `src/llm/structured.py`, `src/agents/review/registry.py`, `src/config.py`, `src/databricks/serving.py`, `src/tools/errors.py`, `src/schemas/llm.py` — read 2026-08-08 [VERIFIED]
- `06-CONTEXT.md` D-01..D-20 + `06-AI-SPEC.md` Sections 1-7 — authoritative phase decisions [VERIFIED]
- `03-18-SUMMARY.md` (D-TEL4 telemetry: Llama v1 pre_repair_malformed=0/post_repair_malformed=0) [VERIFIED]
- `03-QWEN-FIDELITY-PROBE.md` (Qwen: post_repair_malformed=4/5) [VERIFIED]
- `beta-measurement-summary.json` (115 candidates: matched_gt_ids=[A-09,A-11,B-01,C-01,C-06,MS-01], fp_count=102) [VERIFIED]
- vLLM structured outputs docs: https://docs.vllm.ai/en/stable/features/structured_outputs.html — `extra_body={"structured_outputs": {"json": schema}}`; backends; legacy `guided_json` alias [CITED]
- vLLM tool calling docs: https://docs.vllm.ai/en/stable/features/tool_calling.html — `--enable-auto-tool-choice`, `--tool-call-parser`, `--tool-parser-plugin`; built-in parsers list [CITED]
- NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 model card (HuggingFace) — vLLM launch cmd with `--tool-parser-plugin` + `--tool-call-parser llama_nemotron_json`; reasoning toggle `/no_think`; temperature recommendations; GPU tested on 2×H100-80GB and 2×A100-80GB [CITED]
- `.planning/ADR-nemotron-verifier-model.md` — accepted decision; quant note (NVFP4/GGUF); decorrelation guardrail [VERIFIED]

### Secondary (MEDIUM confidence)

- Databricks custom model serving docs: https://docs.databricks.com/aws/en/machine-learning/model-serving/serve-custom-llms — GPU_SMALL/MEDIUM/XLARGE tier descriptions; MLflow pyfunc.log_model entrypoint pattern; port 8080 requirement [CITED: docs are for GPU_XLARGE; GPU_XLARGE_8 is the workspace-specific tier confirmed by CLI]
- NVIDIA Nemotron-3-Super vLLM cookbook (NVIDIA-NeMo/Nemotron repo): BF16/FP8/NVFP4 GPU memory requirements; quant decision table; tensor-parallel sizes per quant [CITED]
- `notebooks/deploy_adapters.py` — proven mlflow.transformers.log_model + serving endpoint creation pattern for `GPU_XLARGE_8` [VERIFIED]

### Tertiary (LOW confidence)

- WebSearch: Databricks GPU_XLARGE_8 = 8×H100 inference — consistent with Databricks docs (GPU_XLARGE = 1×H100; suffix _8 = 8 units) but not explicitly documented in a public page [ASSUMED: A1]

---

## Metadata

**Confidence breakdown:**
- Standard stack (client-side): HIGH — all packages already pinned in pyproject.toml; versions verified
- GPU/quant decision procedure: MEDIUM — GPU_XLARGE_8 hardware class confirmed as existing; exact GPU model (H100 vs other) assumed from strong circumstantial evidence
- vLLM flags (tool-parser, guided decode): HIGH — verified against official vLLM docs + NVIDIA model card
- Nemotron reasoning toggle: MEDIUM — v1.5 string (`/no_think`) from model card; D-18 probe task will confirm empirically
- Phase 3 baseline telemetry: HIGH — read directly from committed run artifacts
- Beta probe corpus composition: HIGH — read directly from committed beta-measurement-summary.json

**Research date:** 2026-08-08
**Valid until:** 2026-09-07 (30 days; vLLM and Databricks serving APIs are moderately stable; Nemotron model card is fixed)
