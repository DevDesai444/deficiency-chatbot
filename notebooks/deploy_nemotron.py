#!/usr/bin/env python3
"""Deploy Nemotron-Super-49B-v1.5 via self-managed vLLM to Databricks GPU_XLARGE_8.

D-03: self-managed vLLM (NOT Databricks managed Provisioned Throughput).
D-04: always-warm, scale_to_zero_enabled=False (H100 tier has no scale-to-zero).
D-20: FP8 quant on GPU_XLARGE_8 (8xH100 Hopper) — confirmed in
      ADR-nemotron-verifier-model.md D-19/D-20 Amendment, gate passed 2026-08-09.
Pattern: mirrors notebooks/deploy_adapters.py (proven mlflow + GPU_XLARGE_8 pattern).

Three SEPARABLE operations callable independently:
  deploy()   — MLflow pyfunc registration + serving endpoint create/update
  probe()    — run pre-wiring probes against the live endpoint; returns structured result
  teardown() — stop/delete the endpoint (idempotent: no-op if already gone)

CLI:
  python notebooks/deploy_nemotron.py                   # deploy -> probe (try/finally teardown)
  python notebooks/deploy_nemotron.py --register-only   # MLflow registration only (no endpoint)
  python notebooks/deploy_nemotron.py --deploy-only     # deploy + wait READY (no probe)
  python notebooks/deploy_nemotron.py --teardown        # teardown only

DEV TEARDOWN POLICY (ADR D-19/D-20 Amendment §3):
  The endpoint is stopped/deleted between active development sessions.
  The live CLI path (deploy -> probe) MUST run teardown in a try/finally so the
  endpoint comes down whether probes PASS or FAIL — no idle H100 hours.
  This is un-bypassable in the default CLI flow.

FALLBACK RIDER (ADR D-19/D-20 Amendment §4):
  If endpoint creation returns a capacity denial OR runtime reveals non-Hopper
  hardware, fall through the pre-ranked rows mechanically — Row 2 (BF16) then
  Row 3 (AWQ-INT4). Do not silently work around; surface the row selection.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import mlflow
import mlflow.pyfunc

# ===== Configuration =====

NEMOTRON_VOLUME_DIR = "/Volumes/defpredict/main/artifacts/nemotron-49b"
UC_MODEL_NAME = "defpredict.main.defpredict_nemotron"
ENDPOINT_NAME = "defpredict-nemotron"

# MUST match --served-model-name in vLLM and config.verifier_model + _guided_cache key.
# Value: "nemotron-super-49b-v1_5" — cross-referenced against serving.py _DB_MODELS["nemotron"]
SERVED_MODEL_NAME = "nemotron-super-49b-v1_5"

# ===== D-19/D-20 confirmed values (ADR-nemotron-verifier-model.md D-19/D-20 Amendment) =====
# Gate PASSED 2026-08-09: GPU_XLARGE_8 = 8xH100 (Hopper), FP8 confirmed.
TENSOR_PARALLEL_SIZE = 8   # 8xH100 (GPU_XLARGE_8 Hopper)
DTYPE_FLAG = "fp8"         # FP8 — Hopper-native quant; locks D-19/D-20 gate

# ===== Fallback Rider rows (ADR §4 — no new gate, mechanical row-selection only) =====
# Row 1 (default): FP8 on GPU_XLARGE_8 / H100 / TP-8  <- this file uses Row 1
# Row 2 (capacity denial / non-Hopper): BF16, same TP-8
# Row 3 (Row 2 unavailable): AWQ-INT4, smallest fitting tier
_FALLBACK_ROW2_DTYPE = "bfloat16"
_FALLBACK_ROW3_DTYPE = "awq"  # INT4 via AWQ — requires --quantization awq

VLLM_CMD = (
    "python3 -m vllm.entrypoints.openai.api_server "
    "--model model_dir "
    f"--served-model-name {SERVED_MODEL_NAME} "
    "--trust-remote-code "
    f"--tensor-parallel-size {TENSOR_PARALLEL_SIZE} "
    "--max-model-len 65536 "
    "--gpu-memory-utilization 0.95 "
    "--enable-auto-tool-choice "
    # llama_nemotron_toolcall_parser_no_streaming.py ships with the model weights;
    # path is relative to the MLflow artifacts folder (the artifact key "model_dir").
    "--tool-parser-plugin model_dir/llama_nemotron_toolcall_parser_no_streaming.py "
    "--tool-call-parser llama_nemotron_json "
    "--host 0.0.0.0 "
    "--port 8080 "
    f"--dtype {DTYPE_FLAG} "
    f"--quantization {DTYPE_FLAG} "
    # structured_outputs ON by default (xgrammar/auto backend) — no extra flag needed;
    # optional: --structured-outputs-config.backend xgrammar to pin if auto misbehaves
)

VLLM_CMD_BF16 = (
    "python3 -m vllm.entrypoints.openai.api_server "
    "--model model_dir "
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
    f"--dtype {_FALLBACK_ROW2_DTYPE} "
)


# ===== MLflow pyfunc placeholder =====

class NemotronServingModel(mlflow.pyfunc.PythonModel):
    """Placeholder pyfunc — actual serving done by the vLLM entrypoint baked into metadata.

    The MLflow pyfunc artifact is the deployment vehicle for the entrypoint command
    and the model weights path. The vLLM server process is what receives inference
    traffic; this class is never called at inference time.
    """

    def predict(self, context: Any, model_input: Any) -> Any:
        raise NotImplementedError(
            "NemotronServingModel.predict is never called — the model is served "
            "via the vLLM entrypoint registered in the MLflow artifact metadata."
        )


# ===== Three separable operations =====

def register_model() -> str:
    """Register Nemotron as an MLflow pyfunc in Unity Catalog.

    IMPORTANT: This uploads 92.9 GiB from the Volume into the MLflow artifact store.
    Expect 30-90 minutes. Requires databricks-sdk >= 0.102.0 (avoids 5-min upload timeout).
    Run from a Databricks notebook (internal network) for fastest upload speed.
    Run once; the registered version is reused on subsequent deploys without re-upload.

    Returns the registered model version string (typically "1").
    Idempotent: re-running creates a new model version in Unity Catalog,
    which is safe and intentional — the endpoint config is updated separately.

    extra_pip_requirements: vllm>=0.11 ensures the serving container has the correct
    vLLM with the llama_nemotron_json tool-call parser available.
    """
    mlflow.set_registry_uri("databricks-uc")
    # A spark_python_task has NO default MLflow experiment (unlike a notebook),
    # so start_run() raises RESOURCE_DOES_NOT_EXIST unless one is set explicitly.
    mlflow.set_experiment(
        os.environ.get("MLFLOW_EXPERIMENT_PATH", "/Users/dev.desai@amneal.com/defpredict-nemotron")
    )
    # Unity Catalog requires a model signature (input/output schema) or version
    # registration fails, even though the pyfunc predict is never called (the vLLM
    # entrypoint serves). A minimal chat signature satisfies the requirement.
    from mlflow.models.signature import ModelSignature
    from mlflow.types.schema import ColSpec, Schema

    _sig = ModelSignature(
        inputs=Schema([ColSpec("string", "prompt")]),
        outputs=Schema([ColSpec("string", "response")]),
    )
    with mlflow.start_run(run_name="register-nemotron"):
        mlflow.pyfunc.log_model(
            artifact_path="defpredict_nemotron",
            python_model=NemotronServingModel(),
            artifacts={"model_dir": NEMOTRON_VOLUME_DIR},
            signature=_sig,
            metadata={
                "task": "llm/v1/chat",
                "entrypoint": VLLM_CMD,
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


def deploy(entity_version: str = "1", _row: int = 1) -> None:
    """Create or update the Databricks GPU_XLARGE_8 serving endpoint.

    Idempotent: if the endpoint already exists, updates its config (PUT).
    If creation returns a capacity denial OR reveals non-Hopper hardware,
    falls through the Fallback Rider rows mechanically (Row 2 -> BF16, Row 3 -> AWQ-INT4).

    Args:
        entity_version: The registered model version to serve (default "1").
        _row: Internal Fallback Rider row selector (1=FP8, 2=BF16, 3=AWQ-INT4).
    """
    host = os.environ.get("DATABRICKS_HOST", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not host or not token:
        raise RuntimeError(
            "DATABRICKS_HOST and DATABRICKS_TOKEN must be set. "
            "Source your .env file before running this script."
        )

    _row_names = {1: "Row 1 (FP8/H100)", 2: "Row 2 (BF16 fallback)", 3: "Row 3 (AWQ-INT4 fallback)"}
    print(f"Deploying endpoint {ENDPOINT_NAME!r} — {_row_names.get(_row, f'Row {_row}')}")

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": ENDPOINT_NAME,
        "config": {
            "served_entities": [
                {
                    "entity_name": UC_MODEL_NAME,
                    "entity_version": entity_version,
                    "workload_type": "GPU_XLARGE_8",  # proven tier on aip-amn-dev (D-04)
                    "workload_size": "Small",
                    "scale_to_zero_enabled": False,    # D-04: always-warm (H100 tier has no scale-to-zero)
                }
            ]
        },
    }

    r = httpx.post(
        f"{host}/api/2.0/serving-endpoints",
        headers=headers,
        json=payload,
        timeout=30.0,
    )

    # === Fallback Rider: capacity denial -> row-selection ===
    if r.status_code == 429 or (r.status_code >= 400 and _is_capacity_denial(r.text)):
        _apply_fallback_rider(r.text, entity_version, _row, headers, host, payload)
        return

    if "already exists" in r.text.lower():
        print(f"Endpoint {ENDPOINT_NAME!r} already exists — updating config")
        r2 = httpx.put(
            f"{host}/api/2.0/serving-endpoints/{ENDPOINT_NAME}/config",
            headers=headers,
            json=payload["config"],
            timeout=30.0,
        )
        if r2.status_code >= 400:
            _maybe_fallback(r2.text, entity_version, _row, headers, host, payload)
            return
        print(f"Endpoint config updated (HTTP {r2.status_code})")
    else:
        if r.status_code >= 400:
            _maybe_fallback(r.text, entity_version, _row, headers, host, payload)
            return
        print(f"Endpoint create accepted (HTTP {r.status_code})")

    print(f"Endpoint {ENDPOINT_NAME!r} create/update accepted")


def _is_capacity_denial(response_text: str) -> bool:
    """Detect a capacity denial or workload_type tier-rejection in the API response body.

    Risk 4 (06-05-DEPLOY-RESEARCH.md): GPU_XLARGE_8 is an account-negotiated tier.
    A workspace without enrollment returns 'workload_type not supported' or 'not supported'
    — these are treated as capacity/tier denials and fall through the Fallback Rider rows.
    """
    lowered = response_text.lower()
    return any(token in lowered for token in (
        "capacity", "no capacity", "quota", "insufficient",
        "not supported", "workload_type",
    ))


def _is_hardware_mismatch(response_text: str) -> bool:
    """Detect a non-Hopper hardware signal in the API response body."""
    lowered = response_text.lower()
    return any(token in lowered for token in ("not supported", "cuda capability", "fp8 not"))


def _apply_fallback_rider(
    response_text: str,
    entity_version: str,
    current_row: int,
    headers: dict,
    host: str,
    payload: dict,
) -> None:
    """Mechanical Fallback Rider row selection — never silently absorbs failures."""
    if current_row >= 3:
        raise RuntimeError(
            f"[FALLBACK RIDER] All rows exhausted. Last API response: {response_text[:400]}\n"
            "Escalate to Databricks support for GPU capacity allocation."
        )
    next_row = current_row + 1
    row_labels = {2: "Row 2 — BF16 (A100-safe)", 3: "Row 3 — AWQ-INT4"}
    print(
        f"\n[FALLBACK RIDER] Capacity denial or hardware mismatch detected.\n"
        f"  Response: {response_text[:200]}\n"
        f"  Falling through to {row_labels.get(next_row, f'Row {next_row}')}"
    )
    deploy(entity_version=entity_version, _row=next_row)


def _maybe_fallback(
    response_text: str,
    entity_version: str,
    current_row: int,
    headers: dict,
    host: str,
    payload: dict,
) -> None:
    """Check if the error is a Fallback Rider trigger; if so, apply it; else raise."""
    if _is_capacity_denial(response_text) or _is_hardware_mismatch(response_text):
        _apply_fallback_rider(response_text, entity_version, current_row, headers, host, payload)
    else:
        raise RuntimeError(
            f"Endpoint deploy failed (non-capacity error): {response_text[:500]}"
        )


def wait_for_ready(timeout_minutes: int = 60) -> None:
    """Poll until the endpoint reaches READY state.

    Idempotent: safe to call if already READY (returns immediately).

    Args:
        timeout_minutes: Maximum wait time before raising TimeoutError.
    """
    host = os.environ.get("DATABRICKS_HOST", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout_minutes * 60
    last_state = "UNKNOWN"
    while time.time() < deadline:
        try:
            r = httpx.get(
                f"{host}/api/2.0/serving-endpoints/{ENDPOINT_NAME}",
                headers=headers,
                timeout=15.0,
            )
            data = r.json()
            last_state = data.get("state", {}).get("ready", "NOT_READY")
            print(f"  Endpoint state: {last_state}", end="\r")
            if last_state == "READY":
                print(f"\nEndpoint {ENDPOINT_NAME!r} is READY")
                return
        except Exception as exc:
            print(f"  Poll error: {exc}", end="\r")
        time.sleep(30)
    raise TimeoutError(
        f"Endpoint {ENDPOINT_NAME!r} did not reach READY after {timeout_minutes} minutes. "
        f"Last state: {last_state}. Check Databricks workspace for error details."
    )


@dataclass
class ProbeResult:
    """Structured result from the pre-wiring probe suite."""

    endpoint_name: str = ENDPOINT_NAME
    tool_call_ok: bool = False
    thinking_on_tokens: int = 0
    thinking_off_tokens: int = 0
    token_split_ok: bool = False
    verdict_parse_ok: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.tool_call_ok and self.token_split_ok and self.verdict_parse_ok


def probe() -> ProbeResult:
    """Run the MODEL-02 pre-wiring probes against the live Nemotron endpoint.

    Probes (non-metered — only called when the endpoint is already READY):
      1. Tool-call round-trip: confirm tool_calls populated, content empty (Pitfall 1)
      2. Thinking ON/OFF token split: confirm toggle fires (D-18 / Pitfall 2)
      3. VERDICT parse: confirm guided decode + coerce_and_validate produces a valid instance

    Returns a ProbeResult dataclass. Does NOT raise on probe failure — the caller
    (the try/finally main path) decides whether to raise after teardown runs.
    """
    import json

    result = ProbeResult()

    # Import inside function to keep module importable without src/ on path
    try:
        import sys as _sys
        _src = os.path.join(os.path.dirname(__file__), "..", "src")
        if _src not in _sys.path:
            _sys.path.insert(0, _src)
        from llm.client import chat_completion_tools
        from llm.reliability import coerce_and_validate, supports_guided_json
        from config import get_settings
        from schemas.llm import VERDICT
    except ImportError as exc:
        result.errors.append(f"Import error (src not on path?): {exc}")
        return result

    _VERDICT_TOOL = {
        "type": "function",
        "function": {
            "name": "emit_verdict",
            "description": "Emit VERDICT on a candidate deficiency",
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": ["KEEP", "DOWNGRADE"]},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                    "grounding_span": {"type": "string"},
                },
                "required": ["verdict", "confidence", "rationale", "grounding_span"],
                "additionalProperties": False,
            },
        },
    }

    _PROBE_MSG = [
        {
            "role": "user",
            "content": (
                "Candidate: The stability study protocol omits the proposed shelf-life "
                "justification required by ICH Q1A(R2) §3.4.\n"
                "Source span: 'Stability studies were conducted at 25°C/60% RH.'\n"
                "Rule: ICH Q1A(R2) §3.4 — shelf-life justification required.\n"
                "Emit VERDICT."
            ),
        }
    ]

    _THINKING_OFF_SYS = "/no_think\nYou are a regulatory compliance verifier. Emit the VERDICT directly."
    _THINKING_ON_SYS = (
        "You are a regulatory compliance verifier. detailed thinking on\n"
        "Analyze the candidate deficiency carefully before emitting the VERDICT."
    )

    # Probe 1: Tool-call round-trip (Pitfall 1)
    try:
        turn = chat_completion_tools(
            messages=[{"role": "system", "content": _THINKING_OFF_SYS}] + _PROBE_MSG,
            tools=[_VERDICT_TOOL],
            model=ENDPOINT_NAME,
            temperature=0.0,
            max_tokens=256,
            guided_model_cls=VERDICT,
        )
        result.tool_call_ok = bool(turn.tool_calls) and not (turn.content or "").strip()
        if not result.tool_call_ok:
            content_preview = repr((turn.content or "")[:100])
            result.errors.append(
                f"Probe 1 FAILED: tool_calls={bool(turn.tool_calls)}, content={content_preview}. "
                "Check --tool-call-parser (Pitfall 1)."
            )
    except Exception as exc:
        result.errors.append(f"Probe 1 exception: {exc}")

    # Probe 2: Thinking ON/OFF token split (D-18 / Pitfall 2)
    try:
        turn_on = chat_completion_tools(
            messages=[{"role": "system", "content": _THINKING_ON_SYS}] + _PROBE_MSG,
            tools=[_VERDICT_TOOL],
            model=ENDPOINT_NAME,
            temperature=0.6,
            max_tokens=2048,
        )
        turn_off = chat_completion_tools(
            messages=[{"role": "system", "content": _THINKING_OFF_SYS}] + _PROBE_MSG,
            tools=[_VERDICT_TOOL],
            model=ENDPOINT_NAME,
            temperature=0.0,
            max_tokens=256,
        )
        result.thinking_on_tokens = turn_on.completion_tokens
        result.thinking_off_tokens = turn_off.completion_tokens
        result.token_split_ok = result.thinking_on_tokens > result.thinking_off_tokens
        if not result.token_split_ok:
            result.errors.append(
                f"Probe 2 FAILED: ON tokens={result.thinking_on_tokens}, "
                f"OFF tokens={result.thinking_off_tokens}. "
                "Toggle string may be wrong — check /no_think vs 'detailed thinking off' (Pitfall 2)."
            )
    except Exception as exc:
        result.errors.append(f"Probe 2 exception: {exc}")

    # Probe 3: VERDICT parse round-trip (D-06a)
    try:
        turn = chat_completion_tools(
            messages=[{"role": "system", "content": _THINKING_OFF_SYS}] + _PROBE_MSG,
            tools=[_VERDICT_TOOL],
            model=ENDPOINT_NAME,
            temperature=0.0,
            max_tokens=256,
            guided_model_cls=VERDICT,
        )
        if turn.tool_calls:
            raw_args = json.loads(turn.tool_calls[0].function.arguments)
            instance, failure = coerce_and_validate(raw_args, VERDICT)
            result.verdict_parse_ok = instance is not None and failure is None
            if not result.verdict_parse_ok:
                result.errors.append(
                    f"Probe 3 FAILED: coerce_and_validate returned failure={failure}. "
                    "Check guided decode wiring (D-08)."
                )
        else:
            result.verdict_parse_ok = False
            result.errors.append("Probe 3 FAILED: no tool_calls on VERDICT turn")
    except Exception as exc:
        result.errors.append(f"Probe 3 exception: {exc}")

    return result


def teardown() -> None:
    """Stop/delete the defpredict-nemotron serving endpoint.

    Idempotent: safe to call if the endpoint is already gone (no-op).
    DEV TEARDOWN POLICY (ADR D-19/D-20 §3): called in try/finally so idle H100 hours
    cannot accumulate even if probes fail.

    Does not raise if the endpoint is already gone (404 is treated as success).
    Raises on unexpected API errors (non-404 failures).
    """
    host = os.environ.get("DATABRICKS_HOST", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not host or not token:
        print("WARNING: DATABRICKS_HOST/TOKEN not set — skipping teardown (credentials absent)")
        return

    headers = {"Authorization": f"Bearer {token}"}
    print(f"Teardown: deleting endpoint {ENDPOINT_NAME!r}")
    r = httpx.delete(
        f"{host}/api/2.0/serving-endpoints/{ENDPOINT_NAME}",
        headers=headers,
        timeout=30.0,
    )
    if r.status_code == 404 or "does not exist" in r.text.lower() or "not found" in r.text.lower():
        print(f"Endpoint {ENDPOINT_NAME!r} already gone — teardown is a no-op")
        return
    if r.status_code >= 400:
        raise RuntimeError(f"Teardown failed (HTTP {r.status_code}): {r.text[:300]}")
    print(f"Endpoint {ENDPOINT_NAME!r} deleted (HTTP {r.status_code})")


# ===== CLI entrypoint =====

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy Nemotron-Super-49B-v1.5 to Databricks GPU_XLARGE_8.\n\n"
            "Default flow (no flags): register -> deploy -> wait READY -> probe -> teardown.\n"
            "The try/finally teardown is un-bypassable in the default flow (ADR dev-teardown policy).\n"
            "Use --deploy-only to leave the endpoint running for extended evaluation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--register-only",
        action="store_true",
        help=(
            "Register model in Unity Catalog only — do NOT create a serving endpoint. "
            "Non-metered acceptance check: python notebooks/deploy_nemotron.py --register-only"
        ),
    )
    parser.add_argument(
        "--deploy-only",
        action="store_true",
        help="Deploy (register + create endpoint + wait READY) without running probes or teardown.",
    )
    parser.add_argument(
        "--teardown",
        action="store_true",
        help="Delete the defpredict-nemotron endpoint (idempotent).",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Skip waiting for endpoint READY after creation.",
    )
    parser.add_argument(
        "--timeout-minutes",
        type=int,
        default=30,
        help="Timeout in minutes for wait_for_ready (default: 30).",
    )
    args = parser.parse_args()

    # === Teardown-only mode ===
    if args.teardown:
        teardown()
        return

    # === Register-only mode (non-metered acceptance check) ===
    if args.register_only:
        version = register_model()
        print(f"Register-only complete. Model version: {version}")
        print(f"UC model: {UC_MODEL_NAME}")
        print("Next step: python notebooks/deploy_nemotron.py --deploy-only")
        return

    # === Deploy-only mode (no probe, no teardown) ===
    if args.deploy_only:
        version = register_model()
        deploy(entity_version=version)
        if not args.no_wait:
            wait_for_ready(timeout_minutes=args.timeout_minutes)
        print("Deploy complete. Endpoint left running for extended evaluation.")
        print("Remember to teardown when done: python notebooks/deploy_nemotron.py --teardown")
        return

    # === Default: deploy -> probe -> teardown (try/finally — un-bypassable) ===
    # DEV TEARDOWN POLICY: the finally block ensures teardown runs whether probes
    # PASS or FAIL. This is the mandatory path for development sessions.
    version = register_model()
    deploy(entity_version=version)
    if not args.no_wait:
        wait_for_ready(timeout_minutes=args.timeout_minutes)

    probe_result: ProbeResult | None = None
    try:
        print("\n--- Running MODEL-02 pre-wiring probes ---")
        probe_result = probe()
    finally:
        # DEV TEARDOWN POLICY (ADR D-19/D-20 §3): always-on teardown.
        # This finally block is intentionally un-bypassable — the endpoint
        # comes down in the same session regardless of probe outcome.
        print("\n--- Teardown (dev-teardown policy, try/finally) ---")
        try:
            teardown()
        except Exception as td_exc:
            print(f"WARNING: teardown raised {td_exc} — manual cleanup may be needed.")

    # === Report probe results after teardown ===
    if probe_result is not None:
        print("\n=== MODEL-02 Probe Results ===")
        print(f"  tool_call_ok:       {probe_result.tool_call_ok}")
        print(f"  token_split_ok:     {probe_result.token_split_ok}")
        print(f"    thinking_on_tokens:  {probe_result.thinking_on_tokens}")
        print(f"    thinking_off_tokens: {probe_result.thinking_off_tokens}")
        print(f"  verdict_parse_ok:   {probe_result.verdict_parse_ok}")
        if probe_result.errors:
            print("\nErrors:")
            for err in probe_result.errors:
                print(f"  - {err}")
        if probe_result.all_passed:
            print("\nAll probes PASSED — Nemotron endpoint is wired correctly.")
        else:
            print("\nSome probes FAILED — review errors above before proceeding to Plan 06.")
            sys.exit(1)


if __name__ == "__main__":
    main()
