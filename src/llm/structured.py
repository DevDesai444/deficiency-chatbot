"""Defense-in-depth structured output for Databricks-hosted LLMs.

Layers:
  L1  response_format json_schema strict=True   (server-side constrained decoding)
  L2  truncation detector — retry once with 2x max_tokens
  L3  json-repair — deterministic in-process salvage
  L4  Pydantic ValidationError → caller-side re-prompt (existing correction loop)
  L5  Moderator (70B) rescue call — one-shot repair
  L6  Typed ParseFailed sentinel — never leak raw text to frontend
  L7  structlog counters per layer
"""
from __future__ import annotations

import copy
import json
from typing import TypeVar

import structlog
from json_repair import repair_json
from pydantic import BaseModel, ValidationError

from config import get_settings
from llm.client import chat_completion_full
from schemas.llm import ParseFailed

log = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)


def schema_for_databricks(model_cls: type[BaseModel]) -> dict:
    """Convert a Pydantic model's JSON schema to a Databricks-strict-compatible shape.

    Databricks strict mode (like OpenAI strict) requires:
      - additionalProperties: false on every object
      - No `pattern` on strings (some servers reject it)
      - anyOf[X, null] flattened to X (nullability handled via required)
      - $defs preserved
    """
    schema = model_cls.model_json_schema()
    return _sanitize(schema)


def _sanitize(node):
    if isinstance(node, dict):
        node = dict(node)  # shallow copy

        # Flatten anyOf[X, {"type": "null"}] to X
        if "anyOf" in node:
            variants = node["anyOf"]
            non_null = [v for v in variants if not (isinstance(v, dict) and v.get("type") == "null")]
            if len(non_null) == 1:
                # Merge the non-null variant into the parent, drop anyOf
                inherited = _sanitize(non_null[0])
                for k, v in inherited.items():
                    if k not in node:
                        node[k] = v
                node.pop("anyOf", None)
            else:
                node["anyOf"] = [_sanitize(v) for v in variants]

        # Strip 'pattern' — some Databricks endpoints reject it
        node.pop("pattern", None)

        # Force additionalProperties: false on objects
        if node.get("type") == "object":
            node["additionalProperties"] = False

        for k, v in list(node.items()):
            node[k] = _sanitize(v)
        return node
    if isinstance(node, list):
        return [_sanitize(v) for v in node]
    return node


def build_response_format(model_cls: type[BaseModel], name: str | None = None) -> dict:
    """Build the OpenAI-compatible response_format param for Databricks."""
    s = get_settings()
    schema = schema_for_databricks(model_cls)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name or model_cls.__name__,
            "schema": schema,
            "strict": s.structured_output_strict,
        },
    }


def _extract_json_blob(text: str) -> str:
    """Strip common wrappers: markdown fences, leading prose."""
    if not text:
        return text
    stripped = text.strip()

    # Fenced code block
    if "```" in stripped:
        # Find the first fence, take content up to the next fence
        first = stripped.find("```")
        # Skip the language tag line if present
        after_fence = stripped[first + 3:]
        newline = after_fence.find("\n")
        if newline > 0 and newline < 20:
            after_fence = after_fence[newline + 1:]
        end = after_fence.rfind("```")
        if end > 0:
            return after_fence[:end].strip()

    # Try to find outermost JSON object/array
    for open_c, close_c in [("{", "}"), ("[", "]")]:
        start = stripped.find(open_c)
        end = stripped.rfind(close_c)
        if start >= 0 and end > start:
            return stripped[start:end + 1]

    return stripped


def parse_structured(
    raw: str,
    model_cls: type[T],
) -> tuple[T | None, str | None]:
    """L3 + L4: extract, repair, validate.

    Returns (instance, None) on success or (None, error_message) on failure.
    """
    extracted = _extract_json_blob(raw)
    if not extracted:
        return None, "empty response after extraction"

    # First try clean parse
    try:
        obj = json.loads(extracted)
    except json.JSONDecodeError:
        # L3: deterministic repair (trailing commas, unclosed braces, unquoted keys)
        try:
            repaired = repair_json(extracted)
            obj = json.loads(repaired) if isinstance(repaired, str) else repaired
            log.info("json_repair_salvage", model=model_cls.__name__)
        except Exception as exc:
            return None, f"json_repair failed: {exc}"

    # L4: Pydantic validation — surface errors verbatim for caller re-prompt
    try:
        return model_cls.model_validate(obj), None
    except ValidationError as exc:
        return None, exc.json(indent=None)


def call_structured(
    messages: list[dict[str, str]],
    model_cls: type[T],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
) -> tuple[T | None, ParseFailed | None, str]:
    """L1 + L2: server-side strict decoding, with truncation retry.

    Returns (validated_instance, parse_failure_or_None, raw_text).
    Callers use raw_text to feed L5 (moderator rescue) or L6 (sentinel).
    """
    s = get_settings()
    response_format = build_response_format(model_cls)

    try:
        result = chat_completion_full(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=min(max_tokens, s.max_tokens_ceiling),
            response_format=response_format,
        )
    except Exception as exc:
        log.error("l1_call_exception", model=model_cls.__name__, error=str(exc)[:200])
        return None, ParseFailed(
            layer="L1",
            reason="LLM call raised exception before parsing",
            raw_output="",
            validation_error=str(exc)[:1000],
        ), ""

    # L2: truncation detection — retry once with doubled max_tokens (capped)
    if result.finish_reason == "length" and max_tokens < s.max_tokens_ceiling:
        new_max = min(max_tokens * 2, s.max_tokens_ceiling)
        log.warning("truncation_retry", model=model_cls.__name__, old=max_tokens, new=new_max)
        try:
            result = chat_completion_full(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=new_max,
                response_format=response_format,
            )
        except Exception as exc:
            log.warning("l2_retry_failed_using_truncated", error=str(exc)[:200])
            # Keep the truncated first result — L3/L4 may still salvage it.

    instance, err = parse_structured(result.content, model_cls)
    if instance is not None:
        return instance, None, result.content

    return None, ParseFailed(
        layer="L1+L2+L3+L4",
        reason="strict decoding output did not validate",
        raw_output=result.content[:2000],
        validation_error=(err or "")[:1000],
    ), result.content


def repair_with_moderator(
    raw: str,
    validation_error: str,
    model_cls: type[T],
    context: str = "",
) -> tuple[T | None, ParseFailed | None]:
    """L5: escalate to the 70B moderator for a one-shot repair.

    The moderator gets: the failing text, the Pydantic error, the target schema,
    and strict response_format. Called only in the ~0.5% failure tail.
    """
    s = get_settings()
    if s.structured_output_max_repair_calls <= 0:
        return None, ParseFailed(
            layer="L5",
            reason="moderator repair disabled by config",
            raw_output=raw[:2000],
            validation_error=validation_error[:1000],
        )

    schema_str = json.dumps(schema_for_databricks(model_cls), indent=2)
    system = (
        "You are a schema-repair assistant. Return ONLY valid JSON matching the target schema. "
        "No prose, no markdown fences."
    )
    user = (
        (f"## Context\n{context}\n\n" if context else "")
        + f"## Target JSON Schema\n```json\n{schema_str}\n```\n\n"
        + f"## Malformed Output\n{raw[:4000]}\n\n"
        + f"## Validation Error\n{validation_error[:1500]}\n\n"
        + "Emit ONLY the corrected JSON object."
    )

    log.warning("moderator_rescue_called", model=model_cls.__name__)

    try:
        result = chat_completion_full(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=s.moderator_model,
            temperature=0.0,
            max_tokens=s.max_tokens_ceiling,
            response_format=build_response_format(model_cls),
        )
    except Exception as exc:
        log.error("moderator_rescue_exception", error=str(exc)[:200])
        return None, ParseFailed(
            layer="L5",
            reason="moderator rescue call raised exception",
            raw_output=raw[:2000],
            validation_error=str(exc)[:1000],
        )

    instance, err = parse_structured(result.content, model_cls)
    if instance is not None:
        log.info("moderator_rescue_success", model=model_cls.__name__)
        return instance, None

    log.error("moderator_rescue_failed", model=model_cls.__name__, error=(err or "")[:200])
    return None, ParseFailed(
        layer="L5",
        reason="moderator repair also failed to produce valid output",
        raw_output=result.content[:2000],
        validation_error=(err or "")[:1000],
    )


def structured_call(
    messages: list[dict[str, str]],
    model_cls: type[T],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
    repair_context: str = "",
) -> tuple[T | None, ParseFailed | None]:
    """Top-level entry point: runs L1 → L5. Returns validated instance OR ParseFailed sentinel.

    The frontend contract is:  instance XOR parse_failure  — never a raw text leak.
    """
    instance, failure, raw = call_structured(
        messages=messages,
        model_cls=model_cls,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if instance is not None:
        return instance, None

    # L5: moderator rescue
    repaired, repair_failure = repair_with_moderator(
        raw=raw,
        validation_error=(failure.validation_error if failure else ""),
        model_cls=model_cls,
        context=repair_context,
    )
    if repaired is not None:
        return repaired, None

    # L6: sentinel — bubble up structured failure, never raw text
    return None, repair_failure or failure
