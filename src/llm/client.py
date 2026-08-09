from __future__ import annotations

import time
from dataclasses import dataclass

import structlog
from pydantic import BaseModel
from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI, RateLimitError

from config import ON_PREM_ALLOW_LIST, get_settings  # D-16: single source of truth (FIX 4)
# D-08: supports_guided_json + build_guided_extra_body are imported FUNCTION-LOCALLY in
# chat_completion_tools to prevent the circular import:
#   client.py → reliability.py → structured.py → client.py (chat_completion_full)
# Module-level import of reliability here would close that circle. Function-local import
# defers the resolution until after all modules are initialized.

log = structlog.get_logger()

# D-16: Deny-first substring check (FIX 4).
# Catches known external model families by name pattern even if they don't appear
# in ON_PREM_ALLOW_LIST as an exact ID. New on-prem models are NOT blocked by this
# check — only known external families (claude, gpt, gemini).
_EXTERNAL_FAMILY_SUBSTRINGS = ("claude", "gpt", "gemini")

_client: OpenAI | None = None

_RETRYABLE = (APIConnectionError, APITimeoutError)
_MAX_RETRIES = 5
_BASE_DELAY = 1.0
_RATE_LIMIT_BASE_DELAY = 8.0    # per-minute token limits need real waits, not 1-4s
_RATE_LIMIT_MAX_DELAY = 60.0


def _request_safe_message(message) -> dict:
    """Return the assistant message shape that can be sent back on the next request."""
    payload = message.model_dump(exclude_none=True, exclude_unset=True)
    for response_only in ("annotations", "audio", "refusal"):
        payload.pop(response_only, None)
    return payload


def _retry_after_seconds(exc) -> float | None:
    """Read a Retry-After header off a rate-limit error, if the server sent one."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@dataclass
class ChatResult:
    content: str
    finish_reason: str


@dataclass
class ChatTurn:
    """One tool-calling turn's result (AGENT-01). Sibling of ChatResult, not a replacement.

    `raw_message` is the request-safe assistant message and MUST be echoed back into the message
    list verbatim (Pitfall 10): reconstructing the assistant message by hand -- dropping
    tool_calls or mismatching tool_call_id -- produces 400s or silent context loss.

    `usage_present=False` means the provider returned no usage object and the caller's token
    figures are a DECLARED ESTIMATE, not a measurement (D-BUD5 / Pitfall 8). The run summary
    surfaces this so no reader mistakes an estimate for a measured budget.
    """

    content: str
    finish_reason: str
    tool_calls: list
    raw_message: dict
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    usage_present: bool = False


def get_client(model: str | None = None) -> OpenAI:
    """Return the OpenAI-compatible client singleton.

    D-16: If a model ID is provided, enforce the on-prem allow-list guard
    BEFORE returning or constructing the singleton. Two layers:

    Layer 1 — Deny-first substring check (FIX 4):
      Rejects any model-id containing known external family names ('claude', 'gpt',
      'gemini') case-insensitively. Catches variants like 'claude-3-opus-custom' or
      'databricks-claude-opus-4-8' that may not be in the exact allow-list. The real
      endpoint 'databricks-claude-opus-4-8' is confirmed live in this workspace today
      and is an exact example of the one-string-away misconfiguration surface this
      guard defends against.

    Layer 2 — Exact allow-list check:
      Rejects any model-id not in ON_PREM_ALLOW_LIST (config.py is the single source
      of truth; no duplicate set literal in client.py — FIX 4).

    Regulated pharma submission data must never reach an external LLM API
    (21 CFR Part 11 confidentiality). This guard fails loud before any HTTP call.
    """
    # D-16: Layer 1 — deny-first substring check for known external families (FIX 4).
    # Applied BEFORE the allow-list check so that external model names with unusual
    # prefixes (e.g. "databricks-claude-opus-4-8") fail loudly regardless of
    # whether they appear in ON_PREM_ALLOW_LIST.
    if model is not None:
        model_lower = model.lower()
        matched = [s for s in _EXTERNAL_FAMILY_SUBSTRINGS if s in model_lower]
        if matched:
            raise ValueError(
                f"Model {model!r} contains a known external family name {matched}. "
                f"Regulated pharma submission data must never leave on-prem infrastructure "
                f"(21 CFR Part 11 confidentiality). "
                f"If this is a legitimate on-prem model, add it to config.DETECTOR_MODELS first "
                f"and ensure it does not match external family substrings."
            )
    # D-16: Layer 2 — exact allow-list check.
    # Catches any model-id not in the confirmed on-prem set (config drift defense).
    # ON_PREM_ALLOW_LIST is imported from config.py — single source of truth (FIX 4).
    if model is not None and model not in ON_PREM_ALLOW_LIST:
        raise ValueError(
            f"Model {model!r} is not in the on-prem allow-list. "
            f"Forbidden external models include databricks-claude-*, databricks-gpt-*, "
            f"databricks-gemini-* — regulated pharma submission data must never leave "
            f"on-prem infrastructure (21 CFR Part 11 confidentiality). "
            f"Allowed: {sorted(ON_PREM_ALLOW_LIST)}"
        )
    global _client
    if _client is None:
        s = get_settings()
        if s.is_databricks:
            _client = OpenAI(
                base_url=f"{s.databricks_host}/serving-endpoints",
                api_key=s.databricks_token,
                timeout=120.0,
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
        except RateLimitError as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_rate_limited_giving_up", attempts=_MAX_RETRIES)
                raise
            retry_after = _retry_after_seconds(exc)
            delay = retry_after if retry_after else min(_RATE_LIMIT_BASE_DELAY * (2 ** attempt), _RATE_LIMIT_MAX_DELAY)
            log.warning("llm_rate_limited_backoff", attempt=attempt + 1, delay=round(delay, 1))
            time.sleep(delay)
        except _RETRYABLE as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_call_failed", error=str(exc), attempts=_MAX_RETRIES)
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            log.warning("llm_call_retry", error=str(exc), attempt=attempt + 1, delay=delay)
            time.sleep(delay)

    return ChatResult(content="", finish_reason="error")


def chat_completion_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    tool_choice: str = "auto",
    extra_body: dict | None = None,                          # D-08: explicit override (caller wins)
    guided_model_cls: type[BaseModel] | None = None,         # D-08/Pitfall-7: source model for sanitized schema
) -> ChatTurn:
    """AGENT-01: a tool-calling turn using the same resilience layer as chat_completion_full.

    D-08: Guided decode auto-inject. When guided_model_cls is provided and
    supports_guided_json() confirms the model supports it, extra_body is auto-injected
    from build_guided_extra_body(guided_model_cls). This single wiring point covers
    ALL tool-call turns (all 7 review tools + VERDICT) without requiring every caller
    to pass extra_body explicitly.

    PITFALL 7: the guided schema MUST route through tool_schema_for_databricks()
    (via build_guided_extra_body) — NEVER the raw tool parameters dict. Raw schemas
    can contain $ref/anyOf/pattern that vLLM backends reject. build_guided_extra_body
    calls tool_schema_for_databricks internally and is the single mandatory sanitized
    builder. Any raw-schema helper bypassing this is explicitly forbidden (Pitfall 7).

    If explicit extra_body is provided by the caller, it takes precedence over auto-inject.
    """
    s = get_settings()
    client = get_client()
    resolved_model = model or s.resolved_llm_model

    # D-08: Auto-detect guided decode support and inject if supported.
    # Function-local imports to prevent circular import:
    #   client.py → reliability.py → structured.py → client.py
    # Explicit extra_body from the caller always takes precedence over auto-inject.
    # guided_model_cls must route through build_guided_extra_body (Pitfall 7 guard).
    if extra_body is None and guided_model_cls is not None:
        from llm.reliability import build_guided_extra_body, supports_guided_json  # noqa: PLC0415
        if supports_guided_json(client, resolved_model):
            extra_body = build_guided_extra_body(guided_model_cls)

    kwargs: dict = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "tools": tools,
        "tool_choice": tool_choice,
    }
    if extra_body is not None:
        kwargs["extra_body"] = extra_body  # D-08: server-side guided JSON decoding

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            usage = getattr(response, "usage", None)
            details = getattr(usage, "prompt_tokens_details", None) if usage else None
            return ChatTurn(
                content=choice.message.content or "",
                finish_reason=choice.finish_reason or "stop",
                tool_calls=list(choice.message.tool_calls or []),
                raw_message=_request_safe_message(choice.message),
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                cached_tokens=getattr(details, "cached_tokens", 0) or 0,
                usage_present=usage is not None,
            )
        except BadRequestError as exc:
            log.error("llm_bad_request", error=str(exc))
            raise
        except RateLimitError as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_rate_limited_giving_up", attempts=_MAX_RETRIES)
                raise
            retry_after = _retry_after_seconds(exc)
            delay = retry_after if retry_after else min(_RATE_LIMIT_BASE_DELAY * (2 ** attempt), _RATE_LIMIT_MAX_DELAY)
            log.warning("llm_rate_limited_backoff", attempt=attempt + 1, delay=round(delay, 1))
            time.sleep(delay)
        except _RETRYABLE as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_call_failed", error=str(exc), attempts=_MAX_RETRIES)
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            log.warning("llm_call_retry", error=str(exc), attempt=attempt + 1, delay=delay)
            time.sleep(delay)

    return ChatTurn(content="", finish_reason="error", tool_calls=[], raw_message={}, usage_present=False)
