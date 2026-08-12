"""
Model Serving wrapper — unified interface for Ollama (local) and Databricks endpoints.
Both expose OpenAI-compatible APIs.
"""
from __future__ import annotations

from openai import OpenAI

from llm.client import get_client  # D-16 ADDENDUM: route through the guarded singleton

_DB_MODELS = {
    "llama-8b": "databricks-meta-llama-3-1-8b-instruct",
    "llama-70b": "databricks-meta-llama-3-3-70b-instruct",
    "qwen-80b": "databricks-qwen3-next-80b-a3b-instruct",
    "qwen-122b": "databricks-qwen35-122b-a10b",
    "nemotron": "defpredict-nemotron",  # D-03/D-17: routable endpoint name (Databricks model= must be endpoint name, not vLLM served-model-name)
}


def get_llm_client() -> OpenAI:
    """Return the on-prem guarded OpenAI-compatible client singleton.

    D-16 ADDENDUM: Routes through llm.client.get_client() so the deny-first
    substring check and ON_PREM_ALLOW_LIST guard always run before any HTTP call.
    Raw client construction previously here has been removed — client.py is the
    single site for all OpenAI client instantiation in src/.
    """
    return get_client()


def resolve_model(model: str) -> str:
    return _DB_MODELS.get(model, model)
