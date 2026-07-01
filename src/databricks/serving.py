"""
Model Serving wrapper — unified interface for Ollama (local) and Databricks endpoints.
Both expose OpenAI-compatible APIs.
"""
from __future__ import annotations

from openai import OpenAI

from config import get_settings


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
