# Databricks request — enable Custom Model Serving (custom entrypoint / self-managed vLLM) + GPU tiers

**Workspace:** aip-amn-dev — https://aip-amn-dev.cloud.databricks.com (AWS)
**Requested by:** dev.desai@amneal.com

## Primary blocker (please enable this)
**Custom Model Serving with a custom `entrypoint` (self-managed vLLM via MLflow pyfunc `metadata.entrypoint`) is not enabled on this workspace.** Creating a serving endpoint for our registered custom model returns:

```
HTTP 400 BAD_REQUEST:
"Served entity 'defpredict_nemotron-2' with entrypoint is not supported for your workspace."
```
(request_ids: `6cfe84a6-1bc5-4361-953c-9f3ef4cac5e1`, `499d0043-13b1-49da-bce9-cb01785dffb7`)

This happens on **every** GPU tier (including the available `GPU_MEDIUM_8` = 8×A10G) and every quant — the block is the custom-entrypoint feature itself, not the tier. Please enable Custom Model Serving / custom-entrypoint (self-managed vLLM) for this workspace.

## Secondary (also needed for the intended config)
Enable the **H100 GPU workload tiers** for custom serving — `GPU_XLARGE_8` (8×H100) and ideally `GPU_XLARGE` (1×H100). Creating with `workload_type=GPU_XLARGE_8` currently returns `INVALID_PARAMETER_VALUE ... "not supported. Please choose a node type from "` with an **empty** list. Tiers currently offered here are non-Hopper only: `GPU_SMALL` (T4), `GPU_MEDIUM` (A10G), `MULTIGPU_MEDIUM` (4×A10G), `GPU_MEDIUM_8` (8×A10G), `GPU_LARGE` (L40, Beta).

## Use case
Serve `nvidia/Llama-3_3-Nemotron-Super-49B-v1.5` (custom DeciLM architecture) via self-managed vLLM (TP-8) as an internal regulatory-compliance verifier. Registered in Unity Catalog: `defpredict.main.defpredict_nemotron` (v1 = FP8 entrypoint, v2 = BF16 entrypoint). This model's custom architecture is NOT servable via Provisioned Throughput, so custom-entrypoint serving is required.

## Note
Existing `defpredict-evaluator` / `defpredict-suggestor` endpoints are **Provisioned-Throughput** (Databricks-managed, no custom entrypoint) — they do NOT indicate custom-entrypoint serving is enabled.
