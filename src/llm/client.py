from __future__ import annotations

import time

import structlog
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from config import get_settings

log = structlog.get_logger()

_client: OpenAI | None = None

_RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError)
_MAX_RETRIES = 3
_BASE_DELAY = 1.0


def get_client() -> OpenAI:
    global _client
    if _client is None:
        s = get_settings()
        if s.is_databricks:
            _client = OpenAI(
                base_url=f"{s.databricks_host}/serving-endpoints",
                api_key=s.databricks_token,
                timeout=60.0,
            )
        else:
            _client = OpenAI(
                base_url=s.llm_base_url,
                api_key="not-needed",
                timeout=120.0,
            )
    return _client


def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
) -> str:
    s = get_settings()
    client = get_client()

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model or s.resolved_llm_model,
                messages=messages,
                temperature=temperature if temperature is not None else s.llm_temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except _RETRYABLE as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_call_failed", error=str(exc), attempts=_MAX_RETRIES)
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            log.warning("llm_call_retry", error=str(exc), attempt=attempt + 1, delay=delay)
            time.sleep(delay)

    return ""
