"""
Register fine-tuned LoRA adapters with MLflow and deploy
to Databricks Model Serving endpoints.

Prerequisites:
    - Adapters saved to data/adapters/{suggestor,evaluator}/ (local)
      or /Volumes/defpredict/main/artifacts/adapters/{role}/ (Databricks)
    - Databricks workspace with Model Serving enabled
    - DATABRICKS_HOST and DATABRICKS_TOKEN set

Usage:
    python notebooks/deploy_adapters.py --role suggestor
    python notebooks/deploy_adapters.py --role evaluator
    python notebooks/deploy_adapters.py --role all
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

LOCAL_ADAPTER_DIR = Path("data/adapters")
VOLUME_ADAPTER_DIR = "/Volumes/defpredict/main/artifacts/adapters"
BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"


def _adapter_path(role: str) -> str:
    volume = Path(f"{VOLUME_ADAPTER_DIR}/{role}")
    local = LOCAL_ADAPTER_DIR / role
    if volume.exists():
        return str(volume)
    if local.exists():
        return str(local)
    print(f"Adapter not found at {volume} or {local}")
    print(f"Run: python notebooks/fine_tune.py --role {role}")
    sys.exit(1)


def register_adapter(role: str) -> str:
    import mlflow
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    adapter_path = _adapter_path(role)
    on_databricks = "DATABRICKS_RUNTIME_VERSION" in os.environ

    if on_databricks:
        mlflow.set_registry_uri("databricks-uc")
        model_name = f"defpredict.main.defpredict_{role}"
    else:
        model_name = f"defpredict-{role}"

    print(f"Loading base model: {BASE_MODEL}")
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.bfloat16,
        device_map={"": 0} if torch.cuda.is_available() else "cpu",
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print(f"Applying LoRA adapter from: {adapter_path}")
    model = PeftModel.from_pretrained(base, adapter_path)

    print("Merging adapter into base model")
    merged = model.merge_and_unload()

    with mlflow.start_run(run_name=f"register-{role}-adapter"):
        model_info = mlflow.transformers.log_model(
            transformers_model={"model": merged, "tokenizer": tokenizer},
            artifact_path=role,
            registered_model_name=model_name,
            task="llm/v1/chat",
        )

    print(f"Registered {model_name} — URI: {model_info.model_uri}")
    del merged, model, base
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return model_info.model_uri


def deploy_endpoint(role: str, model_uri: str) -> None:
    import httpx

    host = os.environ.get("DATABRICKS_HOST", "")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not host or not token:
        print("DATABRICKS_HOST and DATABRICKS_TOKEN required for deployment")
        sys.exit(1)

    on_databricks = "DATABRICKS_RUNTIME_VERSION" in os.environ
    endpoint_name = f"defpredict-{role}"
    entity_name = f"defpredict.main.defpredict_{role}" if on_databricks else f"defpredict-{role}"

    payload = {
        "name": endpoint_name,
        "config": {
            "served_entities": [{
                "entity_name": entity_name,
                "entity_version": "1",
                "workload_size": "Small",
                "scale_to_zero_enabled": True,
            }],
        },
    }

    headers = {"Authorization": f"Bearer {token}"}

    r = httpx.post(f"{host}/api/2.0/serving-endpoints", headers=headers, json=payload, timeout=30.0)
    if r.status_code == 200:
        print(f"Created endpoint: {endpoint_name}")
    elif "already exists" in r.text.lower():
        r2 = httpx.put(
            f"{host}/api/2.0/serving-endpoints/{endpoint_name}/config",
            headers=headers,
            json=payload["config"],
            timeout=30.0,
        )
        print(f"Updated endpoint: {endpoint_name} (HTTP {r2.status_code})")
    else:
        print(f"Failed: HTTP {r.status_code}: {r.text[:500]}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["suggestor", "evaluator", "all"], required=True)
    parser.add_argument("--register-only", action="store_true", help="Register without deploying")
    args = parser.parse_args()

    roles = ["suggestor", "evaluator"] if args.role == "all" else [args.role]

    for role in roles:
        print(f"\n--- {role} ---")
        model_uri = register_adapter(role)
        if not args.register_only:
            deploy_endpoint(role, model_uri)

    print("\nDone. Update .env with the new endpoint names if needed.")


if __name__ == "__main__":
    main()
