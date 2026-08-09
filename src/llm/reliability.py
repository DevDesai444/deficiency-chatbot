"""Shared reliability module — D-15.

Capability-probe cache + guided_json schema builder + strict annotation-aware
lossless coercion + field-level error formatter + bounded retry + typed XOR
return contract.

Both `registry.dispatch` AND `structured.py` consume this module; Phase 7's
verifier inherits the hardening for free. The defense stack is tested in ONE place.

D-13 honesty (FIX 5): coerce_and_validate does NOT make any live LLM call.
The "corrective retry" is the corrective re-prompt MESSAGE, embedded in
ParseFailed.reason. The Phase 7 orchestrator reads ParseFailed.reason, sends
it as a corrective message to the model, then calls coerce_and_validate again
with the model's corrected output. retries_remaining tracks whether the Phase 7
caller has budget to retry (layer="reliability-L3" means "caller should retry";
layer="reliability-L4" means "exhausted, don't retry").
"""
from __future__ import annotations

import json as _json
from enum import Enum
from typing import TypeVar, get_args, get_origin

import structlog
from openai import BadRequestError, OpenAI
from pydantic import BaseModel, ValidationError

from llm.structured import parse_structured, tool_schema_for_databricks
from schemas.llm import ParseFailed

log = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

# D-09: Module-level capability cache — detect-once per served-model-name.
# Key = served-model-name (e.g. "nemotron-super-49b-v1_5"), NOT the endpoint URL.
# After serving.resolve_model("nemotron") → "nemotron-super-49b-v1_5", use the
# resolved name as the cache key.
_guided_cache: dict[str, bool] = {}


def supports_guided_json(client: OpenAI, model: str) -> bool:
    """D-09: Detect-once, cache per served-model-name.

    Mirrors the response_format BadRequestError→degrade pattern in client.py
    lines 135-144. Fail-safe: any non-BadRequest error → assume unsupported.
    Never re-probe on the hot path — call once at startup or first use.
    """
    if model in _guided_cache:
        return _guided_cache[model]
    try:
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            extra_body={
                "structured_outputs": {
                    "json": {"type": "object", "properties": {}, "additionalProperties": False}
                }
            },
        )
        _guided_cache[model] = True
        log.info("guided_json_probe_cached", model=model, supported=True)
    except BadRequestError:
        _guided_cache[model] = False  # endpoint rejected it → fall through to native parser
        log.info("guided_json_probe_cached", model=model, supported=False)
    except Exception:
        _guided_cache[model] = False  # fail-safe: never block the real call on probe error
        log.warning("guided_json_probe_exception_fallback", model=model)
    return _guided_cache[model]


def build_guided_extra_body(model_cls: type[BaseModel]) -> dict:
    """D-08: Build the extra_body dict for guided decoding on tool-call turns.

    Always routes through tool_schema_for_databricks — never raw model_json_schema().
    Pitfall 7: raw schemas include $ref/anyOf/pattern that some vLLM backends reject.
    """
    schema = tool_schema_for_databricks(model_cls)  # mandatory route — never bypass
    return {"structured_outputs": {"json": schema}}


def _is_numeric_annotation(annotation: type | None) -> bool:
    """Return True if the annotation is int or float (or Optional[int/float]).

    FIX 6: strict_coerce is annotation-aware — only coerce numeric-string → number
    when the target field is annotated as int or float, not str. This prevents
    silently coercing legitimate str fields like batch numbers ("12345"), CFR tokens,
    version strings, or any str-typed field that looks numeric.
    """
    if annotation is None:
        return False
    # Handle Optional[X] / Union[X, None]
    origin = get_origin(annotation)
    if origin is not None:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return any(_is_numeric_annotation(a) for a in args)
    return annotation in (int, float)


def _is_bool_annotation(annotation: type | None) -> bool:
    """Return True if the annotation is bool (or Optional[bool]).

    FIX 6: only coerce bool-strings when the field is annotated bool.
    """
    if annotation is None:
        return False
    origin = get_origin(annotation)
    if origin is not None:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return any(_is_bool_annotation(a) for a in args)
    return annotation is bool


def strict_coerce(raw_args: dict, model_cls: type[BaseModel]) -> dict:
    """D-11: Apply the allow-list of strict lossless coercions before pydantic validate.

    Allowed (information-preserving only, ANNOTATION-AWARE):
      - numeric-string → number ONLY when the field's annotation is int or float
        (not str — "12345" in a batch_number: str field must NOT be coerced to 12345)
      - 'true' / 'false' → bool ONLY when the field's annotation is bool
      - single-key wrapper unwrap (key matches model class name exactly)

    Forbidden:
      - enum snapping / nearest-match (e.g. 'keep' → 'KEEP') — D-11 hardest rule
      - partial numeric coercion ('12abc' → 12)
      - any coercion that changes information content
      - coercing a str-annotated field that happens to hold a numeric-looking string
        (FIX 6 — prevents "12345" batch number → 12345 int when field is str-typed)

    Every rejected enum near-miss is logged (structlog counter).
    """
    # Unwrap single-key wrapper if key exactly matches model class name
    if len(raw_args) == 1:
        (k, v) = next(iter(raw_args.items()))
        if k == model_cls.__name__ and isinstance(v, dict):
            log.info("coercion_wrapper_unwrap", model=model_cls.__name__, key=k)
            raw_args = v

    coerced: dict = {}
    for field_name, value in raw_args.items():
        if isinstance(value, str):
            field_meta = model_cls.model_fields.get(field_name)
            annotation = field_meta.annotation if field_meta is not None else None

            # FIX 6: annotation-aware numeric coercion — ONLY when field is int/float
            if _is_numeric_annotation(annotation):
                try:
                    if "." in value:
                        coerced[field_name] = float(value)
                        log.info("coercion_numeric_string", field=field_name, value=value, to="float")
                        continue
                    else:
                        coerced[field_name] = int(value)
                        log.info("coercion_numeric_string", field=field_name, value=value, to="int")
                        continue
                except ValueError:
                    pass  # not a valid number string — fall through

            # FIX 6: annotation-aware bool coercion — ONLY when field is bool
            if _is_bool_annotation(annotation):
                if value.lower() == "true":
                    coerced[field_name] = True
                    log.info("coercion_bool_string", field=field_name, value=value, to=True)
                    continue
                if value.lower() == "false":
                    coerced[field_name] = False
                    log.info("coercion_bool_string", field=field_name, value=value, to=False)
                    continue

            # Enum fields: PASS-THROUGH ONLY — log near-misses, do NOT coerce (D-11)
            is_enum = (
                annotation is not None
                and isinstance(annotation, type)
                and issubclass(annotation, Enum)
            )
            if is_enum:
                valid = {e.value for e in annotation}
                if value not in valid:
                    log.warning(
                        "coercion_enum_near_miss_rejected",
                        field=field_name,
                        value=value,
                        valid_values=sorted(valid),
                    )
                    # Pass through unchanged — pydantic will raise ValidationError

        coerced[field_name] = value
    return coerced


def format_field_level_reprompt(error: ValidationError, model_cls: type[BaseModel]) -> str:
    """RELIABILITY-02: Field-level corrective re-prompt message.

    Replaces the generic registry.dispatch hint ('send a JSON object matching
    this tool's schema exactly') with per-field guidance naming the failing field
    and its expected type. Extends the ValidationError.errors() path already
    used implicitly in parse_structured (structured.py line 178).
    """
    lines = [
        f"The {model_cls.__name__} args failed validation. Fix the following fields:"
    ]
    for e in error.errors():
        loc = ".".join(str(x) for x in e["loc"])
        msg = e["msg"]
        err_type = e.get("type", "")
        field_meta = model_cls.model_fields.get(loc)
        expected_type = ""
        if field_meta is not None and field_meta.annotation is not None:
            ann = field_meta.annotation
            expected_type = f" (expected: {getattr(ann, '__name__', str(ann))})"
        lines.append(f"  - Field '{loc}': {msg}{expected_type} [error_type={err_type}]")
    lines.append(f"Return ONLY valid JSON matching the {model_cls.__name__} schema.")
    return "\n".join(lines)


def format_field_level_reprompt_from_json(err_json: str | None, model_cls: type[BaseModel]) -> str:
    """RELIABILITY-02 / B2: Build field-level reprompt from a pydantic ValidationError JSON string.

    Companion to format_field_level_reprompt for callers that hold a JSON error-string
    (e.g. registry.py which receives exc.json(indent=None) from parse_structured) rather
    than a live ValidationError object. Normalizes the JSON string and delegates to the
    same core formatter logic.

    Called by registry.dispatch to satisfy D-15 without duplicating the core formatting.
    """
    _GENERIC_HINT = "send a JSON object matching this tool's schema exactly"
    if err_json is None:
        return _GENERIC_HINT
    try:
        errors = _json.loads(err_json)
        if not isinstance(errors, list) or len(errors) == 0:
            return _GENERIC_HINT
        lines = [f"Fix the following fields in {model_cls.__name__}:"]
        for e in errors:
            loc = ".".join(str(x) for x in e.get("loc", ["(unknown)"]))
            msg = e.get("msg", "invalid value")
            err_type = e.get("type", "")
            field_meta = model_cls.model_fields.get(loc)
            expected_type = ""
            if field_meta is not None and field_meta.annotation is not None:
                ann = field_meta.annotation
                expected_type = f" (expected: {getattr(ann, '__name__', str(ann))})"
            lines.append(f"  - Field '{loc}': {msg}{expected_type} [error_type={err_type}]")
        lines.append(f"Return ONLY valid JSON matching the {model_cls.__name__} schema.")
        return "\n".join(lines)
    except Exception:
        return _GENERIC_HINT


def coerce_and_validate(
    raw_args: dict | str,
    model_cls: type[T],
    retries_remaining: int = 1,
) -> tuple[T | None, ParseFailed | None]:
    """D-10/D-12/D-13: Defense-in-depth validate with bounded corrective retry.

    Contract: returns (instance, None) XOR (None, ParseFailed) — exactly one
    is non-None. NEVER fabricates a verdict (D-12). The caller (Phase 7
    orchestrator) maps ParseFailed → KEEP; baking fallback-KEEP here would
    conflate 'verifier said keep' with 'we couldn't read the verifier'.

    D-13 honesty (FIX 5): this function does NOT make any LLM client call.
    The "corrective retry" is the corrective re-prompt MESSAGE, embedded in
    ParseFailed.reason. The Phase 7 orchestrator reads ParseFailed.reason,
    sends it as a corrective message to the model, then calls this function
    again with the model's corrected output. retries_remaining tracks whether
    the Phase 7 caller has budget to retry (layer="reliability-L3" means
    "caller should retry"; layer="reliability-L4" means "exhausted, don't retry").

    Accepts raw_args as either a dict (tool-call path) or a JSON string
    (structured-output path) — both are normalised to a dict before processing.
    """
    from config import get_settings  # function-local to avoid potential circular import
    s = get_settings()

    # Normalise: accept JSON strings in addition to dicts
    if isinstance(raw_args, str):
        try:
            raw_args = _json.loads(raw_args)
        except Exception as exc:
            return None, ParseFailed(
                layer="reliability-L2",
                reason=f"raw_args is not valid JSON: {exc}",
                raw_output=str(raw_args),
            )

    coerced = strict_coerce(raw_args, model_cls)
    try:
        instance = model_cls.model_validate(coerced)
        return instance, None
    except ValidationError as exc:
        reprompt_msg = format_field_level_reprompt(exc, model_cls)
        if retries_remaining <= 0:
            log.warning(
                "reliability_exhausted_retries",
                model=model_cls.__name__,
                retries=s.verifier_max_repair_calls,
            )
            return None, ParseFailed(
                layer="reliability-L4",
                reason=f"Exhausted {s.verifier_max_repair_calls} corrective retry(s) — field validation failed",
                raw_output=str(raw_args),
                validation_error=exc.json(indent=None),
            )
        log.info(
            "reliability_repair_attempt",
            model=model_cls.__name__,
            retries_remaining=retries_remaining,
        )
        # layer="reliability-L3": caller (Phase 7) should re-prompt using ParseFailed.reason
        # as the corrective message, then call coerce_and_validate again with retries_remaining-1.
        return None, ParseFailed(
            layer="reliability-L3",
            reason=reprompt_msg,
            raw_output=str(raw_args),
            validation_error=exc.json(indent=None),
        )
