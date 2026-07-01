"""
Register fine-tuned LoRA adapters with MLflow and deploy
to Databricks Model Serving endpoints.

Prerequisites:
    - Adapters saved to data/adapters/{suggestor,evaluator}/
    - Databricks workspace with Model Serving enabled
    - DATABRICKS_HOST and DATABRICKS_TOKEN set

Usage:
    python notebooks/deploy_adapters.py --role suggestor
    python notebooks/deploy_adapters.py --role evaluator
    python notebooks/deploy_adapters.py --role all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ADAPTER_DIR = Path("data/adapters")
BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"


def register_adapter(role: str) -> str:
    import mlflow
    from mlflow.pyfunc import PythonModel

    adapter_path = ADAPTER_DIR / role
    if not adapter_path.exists():
        print(f"Adapter not found at {adapter_path}")
        print(f"Run: python notebooks/fine_tune.py --role {role}")
        sys.exit(1)

    model_name = f"defpredict-{role}"

    class LoRAAdapter(PythonModel):
        def load_context(self, context):
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer

            base = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype=torch.float16,
                device_map="auto",
            )
            self.model = PeftModel.from_pretrained(base, context.artifacts["adapter_dir"])
            self.tokenizer = AutoTokenizer.from_pretrained(context.artifacts["adapter_dir"])
            self.model.eval()

        def predict(self, context, model_input):
            import torch

            messages = model_input.to_dict("records")
            prompts = []
            for row in messages:
                prompt = row.get("prompt", "")
                prompts.append(prompt)

            results = []
            for prompt in prompts:
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=1024,
                        temperature=0.3,
                        do_sample=True,
                    )
                text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                results.append(text[len(prompt):])
            return results

    with mlflow.start_run(run_name=f"register-{role}-adapter"):
        model_info = mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=LoRAAdapter(),
            artifacts={"adapter_dir": str(adapter_path)},
            registered_model_name=model_name,
            pip_requirements=[
                "torch>=2.3",
                "transformers>=4.42",
                "peft>=0.11",
                "accelerate>=0.30",
            ],
        )

    print(f"Registered {model_name} — URI: {model_info.model_uri}")
    return model_info.model_uri


def deploy_endpoint(role: str, model_uri: str) -> None:
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import (
        EndpointCoreConfigInput,
        ServedEntityInput,
    )

    w = WorkspaceClient()
    endpoint_name = f"defpredict-{role}"
    model_name = f"defpredict-{role}"

    entity = ServedEntityInput(
        entity_name=model_name,
        entity_version="1",
        workload_size="Small",
        scale_to_zero_enabled=True,
    )

    try:
        w.serving_endpoints.create(
            name=endpoint_name,
            config=EndpointCoreConfigInput(served_entities=[entity]),
        )
        print(f"Created endpoint: {endpoint_name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            w.serving_endpoints.update_config(
                name=endpoint_name,
                served_entities=[entity],
            )
            print(f"Updated endpoint: {endpoint_name}")
        else:
            raise


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
