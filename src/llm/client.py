from __future__ import annotations

import time
from dataclasses import dataclass

import structlog
from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI, RateLimitError

from config import get_settings

log = structlog.get_logger()

_client: OpenAI | None = None

_RETRYABLE = (APIConnectionError, APITimeoutError, RateLimitError)
_MAX_RETRIES = 3
_BASE_DELAY = 1.0


@dataclass
class ChatResult:
    content: str
    finish_reason: str


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
    response_format: dict | None = None,
) -> str:
    """Backwards-compatible entry point — returns raw text."""
    result = chat_completion_full(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    return result.content


def chat_completion_full(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> ChatResult:
    """Full-response variant — returns text + finish_reason so callers can detect truncation."""
    s = get_settings()
    client = get_client()

    kwargs: dict = {
        "model": model or s.resolved_llm_model,
        "messages": messages,
        "temperature": temperature if temperature is not None else s.llm_temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            return ChatResult(
                content=choice.message.content or "",
                finish_reason=choice.finish_reason or "stop",
            )
        except BadRequestError as exc:
            # Server may reject response_format on some endpoint types.
            # Retry once without it so the pipeline degrades gracefully to prompt-only mode.
            if response_format is not None and "response_format" in kwargs:
                log.warning("response_format_rejected_falling_back", error=str(exc)[:200])
                kwargs.pop("response_format", None)
                response_format = None
                continue
            log.error("llm_bad_request", error=str(exc))
            raise
        except _RETRYABLE as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_call_failed", error=str(exc), attempts=_MAX_RETRIES)
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            log.warning("llm_call_retry", error=str(exc), attempt=attempt + 1, delay=delay)
            time.sleep(delay)

    return ChatResult(content="", finish_reason="error")
