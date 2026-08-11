# Databricks request — enable GPU_XLARGE_8 (8×H100) for Custom Model Serving

**Workspace:** aip-amn-dev — https://aip-amn-dev.cloud.databricks.com (AWS)
**Requested by:** dev.desai@amneal.com
**Feature:** GPU workload types for **Custom Model Serving** (self-managed vLLM pyfunc), specifically **`GPU_XLARGE_8` (8×H100)** and ideally **`GPU_XLARGE` (1×H100)**.

## What we need
Enable the H100 custom-model-serving workload tiers (`GPU_XLARGE`, `GPU_XLARGE_8`) on this workspace so we can create a serving endpoint for a self-managed vLLM model at tensor-parallel-8, FP8, always-warm (`scale_to_zero_enabled=false`).

## Use case
Serving `nvidia/Llama-3_3-Nemotron-Super-49B-v1.5` (FP8 quant, TP-8) as an internal regulatory-compliance verifier. Model registered in Unity Catalog: `defpredict.main.defpredict_nemotron`.

## Current behavior (reproduces the gap)
`POST /api/2.0/serving-endpoints` with:
```json
{"config":{"served_entities":[{"workload_type":"GPU_XLARGE_8","workload_size":"Small", ...}]}}
```
returns:
```
HTTP 400 INVALID_PARAMETER_VALUE:
"Workload type 'GPU_XLARGE_8' with size 'Small' is not supported. Please choose a node type from "   ← empty list
```
(example request_id: `8e464f66-8dfa-4e9d-bee7-fce106e44499`)

`GPU_XLARGE` (1×H100) returns the same empty-list rejection.

## Tiers currently offered on this workspace (for reference)
Available (non-Hopper): `GPU_SMALL` (T4), `GPU_MEDIUM` (A10G), `MULTIGPU_MEDIUM` (4×A10G), `GPU_MEDIUM_8` (8×A10G), `GPU_LARGE` (L40, Beta).
Not offered: `GPU_XLARGE`, `GPU_XLARGE_8` (H100) — these are the tiers we are requesting.

## Note
Existing endpoints `defpredict-evaluator` / `defpredict-suggestor` show `GPU_XLARGE_8` in their served config, but those are **Provisioned-Throughput** endpoints (Databricks-managed), which does not grant the tier for **custom** pyfunc serving. We specifically need the H100 tier enabled for the custom-model-serving create path.
