# Phase 6 Plan 05: Nemotron Deploy — Mechanism Research

**Researched:** 2026-08-09
**Domain:** Databricks Custom Model Serving + vLLM entrypoint + UC Volumes + GPU_XLARGE_8
**Confidence:** HIGH for serving mechanism and client addressing; MEDIUM for the 93 GB artifact path (confirmed by multiple sources but not a direct Databricks statement about Volume-backed UC registry storage)

---

## Executive Summary

The current `notebooks/deploy_nemotron.py` is architecturally closer to correct than its docstring suggests. Databricks Custom Model Serving DOES run the `entrypoint` command directly and NEVER calls `predict()` — this is confirmed verbatim by official docs. The `NotImplementedError` in `predict()` is therefore harmless and intentional. **The real deployment risk is different**: the `artifacts={"model_dir": NEMOTRON_VOLUME_DIR}` pattern and the `--model {NEMOTRON_VOLUME_DIR}` flag in the entrypoint both point to a `/Volumes/...` path. Databricks serving containers do NOT have FUSE access to `/Volumes/` at runtime — that path will be invisible inside the container unless the files are also uploaded into the MLflow artifact store.

The good news: there is a clean, documented solution. The MLflow `artifacts={}` parameter accepts `/Volumes/...` source paths, and Databricks SDK (`>=0.102.0`) uploads those files into the UC-backed artifact store during registration. The serving container then receives those files at a relative path matching the artifact key, and the entrypoint command uses that relative key name as `--model <key>`. For 93 GB of weights this is a one-time upload during `register_model()` (not on every deploy), after which the registered model version is re-usable without re-upload.

**The second real bug**: the client probe calls `model=SERVED_MODEL_NAME` (`"nemotron-super-49b-v1_5"`), but Databricks serving requires `model=ENDPOINT_NAME` (`"defpredict-nemotron"`). The two values serve different layers: `--served-model-name` is an internal vLLM identifier; the Databricks routing layer uses the endpoint name.

**Primary recommendation:** Keep the MLflow pyfunc + entrypoint approach (it is the correct Databricks vehicle for self-managed vLLM). Fix the two concrete bugs: (1) change the entrypoint `--model` path from the Volume path to the artifact key name, and (2) change the probe's `model=` to the endpoint name. Expect the initial `register_model()` to take 30–90 minutes uploading 93 GB through the Databricks SDK.

---

## Recommended Serving Vehicle

**Vehicle: MLflow pyfunc + `entrypoint` metadata (Custom Model Serving, `workload_type="GPU_XLARGE_8"`)**

This is the correct and only viable option for the stated requirements. Evaluation of all four candidates:

### (a) Custom-Container Model Serving

Not the mechanism used here. Databricks Custom Model Serving uses MLflow pyfunc + `entrypoint` metadata internally — it IS the "custom container" approach from the user's perspective, but Databricks manages the container build from the registered model. There is no separate "bring your own Docker image" path for GPU_XLARGE serving exposed to end users through the standard serving API. The `entrypoint` field in the pyfunc metadata IS the custom entrypoint mechanism.

**Verdict**: This IS what `deploy_nemotron.py` implements. Correct vehicle.

### (b) `mlflow.transformers.log_model` native GPU serving

This path uses Databricks's managed transformers runtime, which calls the MLflow `transformers` flavor's built-in inference server. It does NOT run a vLLM process. Therefore it LOSES:
- `--tool-parser-plugin` (Nemotron-specific tool-call parser)
- `--tool-call-parser llama_nemotron_json`
- `--enable-auto-tool-choice`
- vLLM server-side guided decoding (`extra_body structured_outputs`)
- `--tensor-parallel-size 8` control
- `--dtype fp8 --quantization fp8`

All of these are D-03/SC2/SC3 requirements. **This path FAILS SC2/SC3 and must not be used.** The `deploy_adapters.py` template uses `mlflow.transformers.log_model` because the adapter models (Llama-3.1-8B) use Databricks managed inference — a different requirement. Do not port that specific call to the Nemotron deploy.

**Verdict**: REJECTED. Loses all vLLM-specific controls.

### (c) vLLM on a Databricks GPU cluster or Databricks App

Running `python3 -m vllm.entrypoints.openai.api_server` on a long-lived Databricks cluster or Databricks App is technically possible and works for local/Databricks notebook access, but it has serious problems for this use case:

- The serving URL is the cluster driver's IP/port, not a stable workspace endpoint — no stable `base_url` for the OpenAI client to address from other processes
- No Databricks-managed auth routing — the cluster would need to be reachable via a static IP or reverse proxy, which is not available in the standard Databricks compute model
- No endpoint lifecycle management (no READY state, no idempotent create/update, no serving-endpoint API monitoring)
- Cost is cluster uptime (DBU/hr) charged continuously, with no teardown API equivalent — the "teardown policy" would be cluster termination, losing the always-warm guarantee for the next session

**Verdict**: REJECTED for production use. Viable only for local one-off testing within a Databricks notebook session.

### (d) Native Databricks vLLM feature (2026)

The Databricks Foundation Model APIs (Provisioned Throughput) can serve specific models via their own managed vLLM internally, but:
- This is Databricks-managed, NOT self-managed
- The Nemotron-Super-49B-v1.5 is not in the FMAPI catalog as of 2026-08-09
- Even if it were, the Nemotron-specific tool-parser plugin (`llama_nemotron_toolcall_parser_no_streaming.py`) cannot be injected into a managed runtime
- D-03 explicitly prohibits Databricks Provisioned Throughput

**Verdict**: REJECTED. D-03 excludes this option.

### Why Custom Model Serving with `entrypoint` metadata is correct

[VERIFIED: docs.databricks.com/aws/en/machine-learning/model-serving/serve-custom-llms, 2026-08-09]

The official Databricks documentation states verbatim: **"Serving runs your entrypoint rather than the model's `predict` method, so `predict` is never called and can return an empty result."** This is the document's own description of the mechanism. The `NemotronServingModel.predict()` raising `NotImplementedError` is therefore NOT the bug — it is by design.

The entrypoint:
1. Runs inside the serving container with the MLflow artifacts folder as the working directory
2. Starts a vLLM process on port 8080 (Databricks serving expects port 8080)
3. Databricks's reverse proxy routes `/serving-endpoints/<endpoint-name>/invocations` traffic to port 8080 in the container
4. The OpenAI client reaches the vLLM server through this proxy

This vehicle supports all required vLLM flags (full flag set analysis in the section below).

---

## Concrete Deploy Steps

### What the new `deploy_nemotron.py` must do (implementation-ready)

#### Step 0 — Understand the artifact upload path

When you call:
```python
mlflow.pyfunc.log_model(
    artifacts={"model_dir": "/Volumes/defpredict/main/artifacts/nemotron-49b"},
    ...
)
```

The Databricks MLflow SDK reads the Volume path and uploads all 97 files (92.9 GiB) into the MLflow artifact store (which is backed by the UC Volume that Databricks allocates for the registered model's artifact storage — a different Volume from your weights Volume, managed by Databricks). This upload happens at `log_model()` time, not at endpoint creation time.

**This upload is 93 GB through the Python SDK. Expect 30–90 minutes. It must be done from a machine with access to the Databricks API (your local dev machine or a Databricks notebook — either works).**

After the upload, the registered model version references the uploaded artifacts. The serving container sees them at the relative path `model_dir/` (the artifact key name) when the entrypoint launches.

**Requirement:** `databricks-sdk >= 0.102.0` to avoid the 5-minute artifact upload timeout. Verify with:
```bash
pip show databricks-sdk | grep Version
```

#### Step 1 — Fix the entrypoint `--model` path

**The current bug**: the VLLM_CMD uses `--model {NEMOTRON_VOLUME_DIR}` (an absolute `/Volumes/...` path). The serving container does not have FUSE access to `/Volumes/`, so vLLM cannot find the model at that path.

**The fix**: the entrypoint runs from the MLflow artifacts folder. The artifact key `"model_dir"` becomes a relative subdirectory. Use the artifact key name as the `--model` argument:

```python
# WRONG (current):
VLLM_CMD = (
    "python3 -m vllm.entrypoints.openai.api_server "
    f"--model {NEMOTRON_VOLUME_DIR} "   # ← /Volumes/... path, not visible in container
    ...
)

# CORRECT:
VLLM_CMD = (
    "python3 -m vllm.entrypoints.openai.api_server "
    "--model model_dir "                 # ← relative to the MLflow artifacts folder
    f"--served-model-name {SERVED_MODEL_NAME} "
    "--trust-remote-code "
    f"--tensor-parallel-size {TENSOR_PARALLEL_SIZE} "
    "--max-model-len 65536 "
    "--gpu-memory-utilization 0.95 "
    "--enable-auto-tool-choice "
    "--tool-parser-plugin model_dir/llama_nemotron_toolcall_parser_no_streaming.py "
    "--tool-call-parser llama_nemotron_json "
    "--host 0.0.0.0 "
    "--port 8080 "
    f"--dtype {DTYPE_FLAG} "
    f"--quantization {DTYPE_FLAG} "
)
```

Note also: the `--tool-parser-plugin` path must also change from an absolute Volume path to the relative artifact key path. In the artifacts folder the plugin file is at `model_dir/llama_nemotron_toolcall_parser_no_streaming.py` (since it ships with the model weights, it will be in the uploaded artifact directory).

#### Step 2 — Fix the `register_model()` function

```python
def register_model() -> str:
    """Register Nemotron as an MLflow pyfunc in Unity Catalog.
    
    IMPORTANT: This uploads 92.9 GiB from the Volume into the MLflow artifact store.
    Expect 30-90 minutes. Requires databricks-sdk >= 0.102.0 (no 5-min timeout).
    Run once; the registered version is reused on subsequent deploys.
    """
    mlflow.set_registry_uri("databricks-uc")
    with mlflow.start_run(run_name="register-nemotron"):
        mlflow.pyfunc.log_model(
            name="defpredict_nemotron",
            python_model=NemotronServingModel(),
            artifacts={
                # The artifact key "model_dir" becomes the relative path
                # the entrypoint sees at runtime. The SDK uploads the full
                # 97-file / 92.9 GiB directory from the Volume.
                "model_dir": NEMOTRON_VOLUME_DIR,
            },
            metadata={
                "task": "llm/v1/chat",
                "entrypoint": VLLM_CMD,      # uses "--model model_dir" (relative)
                "served_model_name": SERVED_MODEL_NAME,
                "quant": DTYPE_FLAG,
                "tensor_parallel_size": TENSOR_PARALLEL_SIZE,
                "adr_gate": "D-19/D-20 PASSED 2026-08-09",
            },
            registered_model_name=UC_MODEL_NAME,
            extra_pip_requirements=["vllm>=0.11"],
        )
    print(f"Registered: {UC_MODEL_NAME}")
    return "1"
```

#### Step 3 — The endpoint creation payload (unchanged, already correct)

```python
payload = {
    "name": ENDPOINT_NAME,
    "config": {
        "served_entities": [
            {
                "entity_name": UC_MODEL_NAME,        # "defpredict.main.defpredict_nemotron"
                "entity_version": entity_version,    # "1"
                "workload_type": "GPU_XLARGE_8",     # proven tier (not in public docs, but live)
                "workload_size": "Small",
                "scale_to_zero_enabled": False,       # H100 tier: no scale-to-zero
            }
        ]
    },
}
```

`GPU_XLARGE_8` is an account-negotiated tier confirmed live on this workspace (existing endpoints `defpredict-suggestor` and `defpredict-evaluator` use it). It is NOT documented on the public `serve-custom-llms` page (which only documents `GPU_XLARGE` = 1×H100). The API accepts `GPU_XLARGE_8` because the workspace is enrolled. Do NOT change this to `GPU_XLARGE` — that is the single-GPU tier.

#### Step 4 — The teardown (unchanged, correct)

```python
httpx.delete(f"{host}/api/2.0/serving-endpoints/{ENDPOINT_NAME}", headers=headers)
```

Idempotent: 404 = already gone = success. This is the ADR dev-teardown policy mechanism.

#### Step 5 — The alternative approach if the 93 GB upload is impractical

If the 93 GB upload from a local machine is too slow (bad network, time pressure), there is a second valid approach using a `load_context` method:

```python
class NemotronServingModel(mlflow.pyfunc.PythonModel):
    """pyfunc that downloads weights from the Volume via Files API at cold start.
    
    This avoids the 93 GB upload at log_model time. The serving container
    must have DATABRICKS_HOST + DATABRICKS_TOKEN env vars injected by the endpoint config.
    
    Tradeoff: cold start is 10-30 minutes longer (download time inside container).
    Only viable for always-warm endpoints with infrequent restarts (D-04 profile).
    """
    
    def load_context(self, context):
        import subprocess, os, tempfile
        # Download weights from Volume via Files API or use the Databricks SDK
        # The serving container CAN access Volumes via the Files API (HTTP), 
        # even though it cannot mount them via FUSE.
        #
        # For vLLM, write weights to local disk first, then launch the server
        # as a subprocess (NOTE: this changes the architecture — vLLM is now
        # managed as a subprocess of the pyfunc, not as the entrypoint).
        # This approach is MORE COMPLEX and should be used only if upload is impractical.
        raise NotImplementedError("See entrypoint approach — preferred")
    
    def predict(self, context, model_input):
        raise NotImplementedError("Served via vLLM entrypoint, not pyfunc predict")
```

The `load_context` / Files API approach is significantly more complex (the pyfunc becomes a wrapper that manages the vLLM subprocess lifecycle, which is fragile). Prefer the entrypoint approach with the artifact upload.

---

## Endpoint Addressing

**This section corrects a real bug in the current `probe()` function.**

### The bug

```python
# In deploy_nemotron.py probe():
turn = chat_completion_tools(
    ...
    model=SERVED_MODEL_NAME,   # "nemotron-super-49b-v1_5" ← WRONG for Databricks serving
    ...
)
```

### Why it's wrong

[VERIFIED: docs.databricks.com/aws/en/machine-learning/model-serving/serve-custom-llms, 2026-08-09]

When using the OpenAI SDK against a Databricks serving endpoint, the `model=` parameter must be the **endpoint name**, not the vLLM `--served-model-name`. The official docs state:

> "When using the OpenAI SDK, the `model` parameter is the `<endpoint-name>`."

The routing works as follows:
1. The OpenAI client sends `POST {base_url}/v1/chat/completions` with `"model": "defpredict-nemotron"`
2. Databricks's serving gateway receives this at `{host}/serving-endpoints/` (the base_url)
3. The gateway routes to the endpoint named `defpredict-nemotron`
4. Inside the container, the request reaches port 8080 where vLLM is running
5. vLLM sees `"model": "defpredict-nemotron"` but it has a `--served-model-name nemotron-super-49b-v1_5`

vLLM will accept `model=<endpoint-name>` in this routing context — it matches on the value passed through, and Databricks handles the name translation. The `--served-model-name` is for direct vLLM API access (not through Databricks serving proxy) and for the vLLM `v1/models` response.

### Correct client configuration

```python
# Correct: base_url uses /serving-endpoints (no trailing slash), model= is ENDPOINT NAME
client = OpenAI(
    base_url=f"{DATABRICKS_HOST}/serving-endpoints",
    api_key=DATABRICKS_TOKEN,
    timeout=120.0,
)

response = client.chat.completions.create(
    model="defpredict-nemotron",          # ← ENDPOINT NAME (not served-model-name)
    messages=[...],
    tools=[...],
    ...
)
```

### What `serving.py` and `client.py` use

[VERIFIED: src/databricks/serving.py:16, src/llm/client.py:148-149]

```python
# serving.py — "nemotron" key maps to the served-model-name, not endpoint name
_DB_MODELS = {
    "nemotron": "nemotron-super-49b-v1_5",  # ← this is the SERVED-MODEL-NAME
}
```

```python
# client.py — correct base_url construction
_client = OpenAI(
    base_url=f"{s.databricks_host}/serving-endpoints",  # ← correct
    api_key=s.databricks_token,
)
```

**The `_DB_MODELS["nemotron"]` value `"nemotron-super-49b-v1_5"` is the served-model-name, which is WRONG for the `model=` parameter when calling through Databricks serving.** It needs to be `"defpredict-nemotron"` (the endpoint name). The `serving.py` and `config.verifier_model` need to be corrected to use the endpoint name, or `chat_completion_tools` needs to accept `model=ENDPOINT_NAME`.

**However**: there is nuance here. The current `probe()` directly passes `SERVED_MODEL_NAME`. The on-prem allow-list in `client.py` checks the model string against `ON_PREM_ALLOW_LIST`. The allow-list includes both `"nemotron-super-49b-v1_5"` AND `"defpredict-nemotron"`. The correct fix is:

1. `serving.py _DB_MODELS["nemotron"]` → change to `"defpredict-nemotron"` (the endpoint name)
2. `probe()` → use `model=ENDPOINT_NAME` (`"defpredict-nemotron"`)
3. `config.verifier_model` → return `"defpredict-nemotron"` (the endpoint name)
4. The `_guided_cache` key in `reliability.py` uses the model string passed to `chat_completion_tools` — this should then be keyed on `"defpredict-nemotron"` consistently

---

## vLLM Entrypoint Flag Fidelity

All required flags survive the MLflow pyfunc + entrypoint mechanism. Analysis:

| Flag | Survives? | Notes |
|------|-----------|-------|
| `--tensor-parallel-size 8` | YES | Passed directly in entrypoint string |
| `--dtype fp8` | YES | Passed directly |
| `--quantization fp8` | YES | Passed directly |
| `--enable-auto-tool-choice` | YES | Passed directly |
| `--tool-parser-plugin model_dir/llama_nemotron_toolcall_parser_no_streaming.py` | YES (with fix) | Must use relative artifact key path, not `/Volumes/...` — see Step 1 |
| `--tool-call-parser llama_nemotron_json` | YES | Passed directly |
| `--max-model-len 65536` | YES | Passed directly |
| `--gpu-memory-utilization 0.95` | YES | Passed directly |
| `--host 0.0.0.0 --port 8080` | YES | Required by Databricks serving (port 8080 is mandatory) |
| structured-outputs / `guided_json` | YES | vLLM's xgrammar/auto backend active by default; extra_body mechanism not affected by Databricks proxy |
| `--served-model-name nemotron-super-49b-v1_5` | YES (internal) | vLLM uses this internally; Databricks routes by endpoint name |

**Flags that do NOT survive Databricks managed serving (the rejected path b):**
All of the above flags are ABSENT from Databricks managed transformers serving. That is the reason path (b) was rejected.

---

## Open Risks / Version Caveats

### Risk 1: 93 GB artifact upload time and reliability [HIGH]

**What can go wrong**: the `log_model()` call uploads 97 files / 92.9 GiB through the Databricks SDK. On a slow network this takes 30–90 minutes. With `databricks-sdk < 0.102.0`, it times out after 5 minutes.

**Mitigation**:
1. Verify `databricks-sdk >= 0.102.0` before running `register_model()`
2. Run from a Databricks notebook (not a local machine) — the SDK uses internal Databricks network, which is much faster (10–30 Gbps vs residential ~100 Mbps)
3. Run `--register-only` mode first; monitor progress. If it times out, upgrade the SDK and retry
4. The upload is idempotent in the sense that a new model version is created on each `register_model()` call — but it re-uploads the full 93 GB. Consider re-using an existing version number if registration was successful but endpoint creation failed

### Risk 2: `/Volumes/...` path in entrypoint is invisible to serving container [HIGH — already materialized]

**Current state**: the VLLM_CMD uses `--model {NEMOTRON_VOLUME_DIR}` and `--tool-parser-plugin {NEMOTRON_VOLUME_DIR}/llama_nemotron_toolcall_parser_no_streaming.py`. These paths are both absolute `/Volumes/...` paths that the serving container cannot see. This will cause vLLM to fail at startup with a "model path not found" error, and the endpoint will reach FAILED state, not READY.

**Fix**: change both paths to relative artifact key paths (`model_dir` and `model_dir/llama_nemotron_toolcall_parser_no_streaming.py`) as documented in Step 1 above. [VERIFIED: docs.databricks.com — "model paths are relative to that folder [the MLflow artifacts folder]"]

### Risk 3: `model=SERVED_MODEL_NAME` in probe() hits Databricks routing layer [HIGH — already materialized]

**Current state**: `probe()` calls `chat_completion_tools(model="nemotron-super-49b-v1_5")`. The Databricks serving gateway routes by endpoint name, not by the vLLM served-model-name. This call will fail with a 404 or "model not found" error from Databricks.

**Fix**: change all `model=` arguments in probe() from `SERVED_MODEL_NAME` to `ENDPOINT_NAME`, and correspondingly fix `serving.py _DB_MODELS["nemotron"]` and `config.verifier_model`. [VERIFIED: docs.databricks.com — "the model parameter is the endpoint-name"]

### Risk 4: GPU_XLARGE_8 not in public docs — enrollment required [MEDIUM]

**What can go wrong**: a future workspace, region, or account may not have `GPU_XLARGE_8` enrolled. The endpoint creation will return a 400 or 422 with "workload_type not supported" or similar. The Fallback Rider in `deploy()` handles capacity denial but NOT workload_type rejection — it specifically checks for capacity and hardware mismatch signals, not for unknown tier names.

**Mitigation**: the Fallback Rider should be extended to detect `workload_type not supported` errors and fall through. However, since this workspace has the tier enrolled (confirmed via live endpoints), this is a low-probability risk for the current workspace. The `_is_capacity_denial()` function's keyword list should include `"not supported"` or the error detection should be broadened to include tier availability failures.

### Risk 5: `--tool-parser-plugin` path at container startup [MEDIUM]

**What can go wrong**: the plugin file `llama_nemotron_toolcall_parser_no_streaming.py` must be at `model_dir/llama_nemotron_toolcall_parser_no_streaming.py` in the serving container. If the upload stripped the file (because it has no `.safetensors` extension), vLLM will fail to load the tool-call parser and produce an error. The tool-call probe (Pitfall 1) will fail — `tool_calls=[]`, prose in `content`.

**Verification**: confirm the plugin file is included in the artifact upload by checking it was present in the Volume:
```bash
# Already confirmed in the objective: "97 files, 92.9 GiB, incl. llama_nemotron_toolcall_parser_no_streaming.py"
ls /Volumes/defpredict/main/artifacts/nemotron-49b/llama_nemotron_toolcall_parser_no_streaming.py
```
The file is confirmed present in the Volume. Since `artifacts={"model_dir": NEMOTRON_VOLUME_DIR}` uploads the entire directory, the plugin file will be included.

### Risk 6: Cold-start timing and `wait_for_ready` timeout [LOW]

**What can go wrong**: on first deployment of the endpoint, Databricks must allocate the H100 cluster AND download the serving container image AND load the 93 GB artifact. This can take 20–45 minutes. The current `wait_for_ready(timeout_minutes=30)` may be insufficient.

**Mitigation**: increase `--timeout-minutes 60` for the first deployment. Subsequent READY transitions (after teardown + redeploy from the same model version) are faster — the container image may be cached.

### Risk 7: vLLM version in serving container vs. `llama_nemotron_json` parser [LOW-MEDIUM]

**What can go wrong**: `extra_pip_requirements=["vllm>=0.11"]` installs vLLM on the serving container, but the minimum `>=0.11` bound may install a version that doesn't have the `llama_nemotron_json` parser registered. The Nemotron tool-parser may require a specific vLLM version range.

**Mitigation**: pin a concrete version in `extra_pip_requirements`. Based on the objective (weights include `llama_nemotron_toolcall_parser_no_streaming.py`), the parser is shipped with the model weights and loaded via `--tool-parser-plugin`, which means it works independently of what vLLM natively ships — the plugin file is the parser. No vLLM version constraint beyond `>=0.6` (when `--tool-parser-plugin` was added) is required for this. The existing `>=0.11` bound is safe.

---

## Sources

### Primary (HIGH confidence)

- [Serve custom LLMs with Custom Model Serving — Databricks AWS docs](https://docs.databricks.com/aws/en/machine-learning/model-serving/serve-custom-llms) — fetched 2026-08-09. Confirms: entrypoint mechanism, `predict()` not called, GPU_XLARGE = 1×H100, `model=` must be endpoint name, relative artifact paths, `scale_to_zero_enabled=False` for H100
- [Custom models overview — Databricks AWS docs](https://docs.databricks.com/aws/en/machine-learning/model-serving/custom-models) — fetched 2026-08-09. Confirms: GPU workload types (GPU_SMALL/MEDIUM/XLARGE), model serving architecture
- [Package custom artifacts for Model Serving — Databricks AWS docs](https://docs.databricks.com/aws/en/machine-learning/model-serving/model-serving-custom-artifacts) — fetched 2026-08-09. Confirms: `/Volumes/...` paths accepted in `artifacts={}`, files are uploaded/packaged into the model artifact
- `src/llm/client.py` (live codebase, read 2026-08-09) — confirms `base_url=f"{s.databricks_host}/serving-endpoints"` and `model=` guard structure
- `src/databricks/serving.py` (live codebase, read 2026-08-09) — confirms `_DB_MODELS["nemotron"] = "nemotron-super-49b-v1_5"` (served-model-name, not endpoint name)
- `.planning/ADR-nemotron-verifier-model.md` D-19/D-20 Amendment (live, read 2026-08-09) — confirms GPU_XLARGE_8 = 8×H100, FP8, TP-8, scale_to_zero=False, teardown policy
- `notebooks/deploy_nemotron.py` (live codebase, read 2026-08-09) — confirms the two bugs: `/Volumes/...` path in VLLM_CMD and model=SERVED_MODEL_NAME in probe()

### Secondary (MEDIUM confidence)

- [Accessing Databricks Volumes from a Serving Endpoint — Databricks Community](https://community.databricks.com/t5/machine-learning/accessing-databricks-volumes-from-a-serving-endpoint-using-a/td-p/93196) — Databricks employees confirm: FUSE mounts not available in serverless serving containers; Files API workaround; artifact packaging is the recommended approach
- Databricks SDK release notes confirming `>=0.102.0` fixes the 5-minute artifact upload timeout [CITED from docs.databricks.com/aws/en/machine-learning/model-serving/serve-custom-llms mention of SDK version requirement]
- Serverless GPU environment version 5 release notes — confirms vLLM 0.13.0 added to Databricks AI environment (context for vLLM availability in serving containers)

### Tertiary (LOW confidence — for context only)

- WebSearch results on `GPU_XLARGE_8` — no public documentation found; the tier is confirmed live via the existing endpoint probes only (HIGH confidence from that source, LOW from docs)

---

## Summary of Required Changes to `deploy_nemotron.py`

| Change | Location | Current (wrong) | Correct |
|--------|----------|-----------------|---------|
| entrypoint `--model` path | `VLLM_CMD` constant | `--model {NEMOTRON_VOLUME_DIR}` (`/Volumes/...`) | `--model model_dir` (relative artifact key) |
| entrypoint `--tool-parser-plugin` path | `VLLM_CMD` constant | `--tool-parser-plugin {NEMOTRON_VOLUME_DIR}/llama_nemotron_toolcall_parser_no_streaming.py` | `--tool-parser-plugin model_dir/llama_nemotron_toolcall_parser_no_streaming.py` |
| Same two fixes in `VLLM_CMD_BF16` | `VLLM_CMD_BF16` constant | Same Volume paths | Same relative paths |
| `probe()` model= argument | `probe()` function | `model=SERVED_MODEL_NAME` (`"nemotron-super-49b-v1_5"`) | `model=ENDPOINT_NAME` (`"defpredict-nemotron"`) |
| `_DB_MODELS["nemotron"]` in serving.py | `src/databricks/serving.py:16` | `"nemotron-super-49b-v1_5"` | `"defpredict-nemotron"` |
| `config.verifier_model` | `src/config.py` | Returns `"nemotron-super-49b-v1_5"` | Should return `"defpredict-nemotron"` |
| ON_PREM_ALLOW_LIST | `src/config.py` | May have both strings | Ensure `"defpredict-nemotron"` is present |
| `wait_for_ready` default timeout | `wait_for_ready()` | 30 minutes | 60 minutes for first cold deployment |

**Note on `_guided_cache` keying**: if `config.verifier_model` changes from `"nemotron-super-49b-v1_5"` to `"defpredict-nemotron"`, the guided-decode probe cache key changes accordingly. This is correct — the cache is keyed on the model string used in API calls, which should be the endpoint name. No code change in `reliability.py` is needed beyond ensuring the string is consistent.

---

## What is NOT Broken in the Current `deploy_nemotron.py`

For completeness — these parts are architecturally correct and should not be changed:

- `mlflow.pyfunc.log_model` is the correct call (not `mlflow.transformers.log_model`)
- `NemotronServingModel.predict()` raising `NotImplementedError` is correct by design
- `metadata={"task": "llm/v1/chat", "entrypoint": VLLM_CMD}` is the correct metadata structure
- `workload_type="GPU_XLARGE_8"` is the correct tier for this workspace
- `scale_to_zero_enabled=False` is correct (H100 tier does not support scale-to-zero)
- `extra_pip_requirements=["vllm>=0.11"]` is correct (installs vLLM on the serving container)
- `registered_model_name=UC_MODEL_NAME` (`"defpredict.main.defpredict_nemotron"`) is correct
- The Fallback Rider (Row 2/Row 3 mechanics) is architecturally correct
- `teardown()` via DELETE `/api/2.0/serving-endpoints/{ENDPOINT_NAME}` is correct
- The try/finally teardown policy in `main()` is correct
- `--tensor-parallel-size 8`, `--dtype fp8 --quantization fp8`, all vLLM flags are correct
- `--host 0.0.0.0 --port 8080` is required and correct

---

## RESEARCH COMPLETE
