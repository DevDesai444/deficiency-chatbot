"""
Model Serving wrapper — unified interface for Ollama (local) and Databricks endpoints.
Both expose OpenAI-compatible APIs.
"""
from __future__ import annotations

from openai import OpenAI

from config import get_settings

_DB_MODELS = {
    "llama-8b": "databricks-meta-llama-3-1-8b-instruct",
    "llama-70b": "databricks-meta-llama-3-3-70b-instruct",
}


def get_llm_client() -> OpenAI:
    s = get_settings()
    if s.is_databricks:
        return OpenAI(
            base_url=f"{s.databricks_host}/serving-endpoints",
            api_key=s.databricks_token,
        )
    return OpenAI(
        base_url=s.llm_base_url,
        api_key="not-needed",
    )


def resolve_model(model: str) -> str:
    return _DB_MODELS.get(model, model)
