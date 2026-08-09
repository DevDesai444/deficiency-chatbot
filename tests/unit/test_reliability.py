"""Unit test shells for RELIABILITY-01/02/03 + D-09 + D-11 + D-12.

All tests call pytest.skip() at runtime if the target modules are not yet implemented
(Plan 03 for llm.reliability, Plan 02 for VERDICT schema). Collection always succeeds.

FIX 6: strict_coerce must be annotation-aware — only coerce numeric/bool fields whose
        pydantic annotation declares a numeric or bool type. test_str_numeric_field_not_coerced
        enforces this invariant.
"""
from __future__ import annotations

import importlib

import pytest
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Runtime import helpers — used inside each test so collection never fails
# ---------------------------------------------------------------------------

def _require_reliability():
    """Import llm.reliability or skip the test if not yet implemented."""
    try:
        return importlib.import_module("llm.reliability")
    except ImportError:
        pytest.skip("src/llm/reliability.py not yet implemented — Plan 03")


def _require_verdict():
    """Import VERDICT from schemas.llm or skip the test if not yet added."""
    try:
        mod = importlib.import_module("schemas.llm")
        if not hasattr(mod, "VERDICT"):
            pytest.skip("VERDICT model not yet in schemas/llm.py — Plan 02")
        return mod.VERDICT
    except ImportError:
        pytest.skip("schemas.llm not importable")


def _require_parse_failed():
    """Import ParseFailed from schemas.llm."""
    try:
        mod = importlib.import_module("schemas.llm")
        return mod.ParseFailed
    except ImportError:
        pytest.skip("schemas.llm not importable")


# ---------------------------------------------------------------------------
# Stub pydantic models used only in these tests
# ---------------------------------------------------------------------------

class SomeModel(BaseModel):
    top_k: int
    flag: bool


class BatchModel(BaseModel):
    batch_number: str  # annotation is str — must NOT be coerced to int


# ---------------------------------------------------------------------------
# RELIABILITY-01: guided_json probe — detect-once, fail-safe
# ---------------------------------------------------------------------------

def test_guided_probe_caches():
    """Probe must call the endpoint exactly ONCE across two calls (detect-once, D-09)."""
    reliability = _require_reliability()
    supports_guided_json = reliability.supports_guided_json

    from types import SimpleNamespace
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))],
    )

    supports_guided_json(mock_client, model="test-model")
    supports_guided_json(mock_client, model="test-model")

    assert mock_client.chat.completions.create.call_count == 1


def test_guided_probe_bad_request_returns_false():
    """BadRequestError from the endpoint must return False without raising (fail-safe)."""
    reliability = _require_reliability()
    supports_guided_json = reliability.supports_guided_json

    from unittest.mock import MagicMock

    try:
        from openai import BadRequestError
    except ImportError:
        pytest.skip("openai not installed")

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = BadRequestError(
        message="guided_json not supported",
        response=MagicMock(status_code=400),
        body={"error": {"message": "not supported"}},
    )

    result = supports_guided_json(mock_client, model="test-model-bad")
    assert result is False


def test_guided_probe_generic_exception_returns_false():
    """Any unexpected exception from the probe must return False (fail-safe, D-09)."""
    reliability = _require_reliability()
    supports_guided_json = reliability.supports_guided_json

    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("network down")

    result = supports_guided_json(mock_client, model="test-model-err")
    assert result is False


# ---------------------------------------------------------------------------
# RELIABILITY-03: strict_coerce — annotation-aware type coercion (FIX 6)
# ---------------------------------------------------------------------------

class TestStrictCoerce:
    def test_numeric_string_float(self):
        """'0.85' in a float field must coerce to 0.85."""
        reliability = _require_reliability()
        VERDICT = _require_verdict()
        result = reliability.strict_coerce({"confidence": "0.85"}, VERDICT)
        assert result["confidence"] == pytest.approx(0.85)

    def test_numeric_string_int(self):
        """'10' in an int field must coerce to 10."""
        reliability = _require_reliability()
        result = reliability.strict_coerce({"top_k": "10"}, SomeModel)
        assert result["top_k"] == 10

    def test_bool_string_true(self):
        """'true' in a bool field must coerce to True."""
        reliability = _require_reliability()
        result = reliability.strict_coerce({"flag": "true"}, SomeModel)
        assert result["flag"] is True

    def test_bool_string_false(self):
        """'false' in a bool field must coerce to False."""
        reliability = _require_reliability()
        result = reliability.strict_coerce({"flag": "false"}, SomeModel)
        assert result["flag"] is False

    def test_wrapper_unwrap(self):
        """{'VERDICT': {...}} single-key wrapper must be unwrapped to the inner dict."""
        reliability = _require_reliability()
        VERDICT = _require_verdict()
        inner = {
            "verdict": "KEEP",
            "confidence": 0.9,
            "rationale": "ok",
            "grounding_span": "span",
        }
        result = reliability.strict_coerce({"VERDICT": inner}, VERDICT)
        assert result["verdict"] == "KEEP"

    def test_enum_near_miss_not_coerced(self):
        """'keep' (lowercase near-miss) must NOT be coerced to 'KEEP' — coercion is
        annotation-aware for numeric/bool only; enum values are left as-is so pydantic
        raises a validation error on the exact wrong value (FIX 6)."""
        reliability = _require_reliability()
        VERDICT = _require_verdict()
        result = reliability.strict_coerce({"verdict": "keep"}, VERDICT)
        assert result["verdict"] == "keep"

    def test_enum_exact_value_unchanged(self):
        """'KEEP' must be left as 'KEEP' (no transformation)."""
        reliability = _require_reliability()
        VERDICT = _require_verdict()
        result = reliability.strict_coerce({"verdict": "KEEP"}, VERDICT)
        assert result["verdict"] == "KEEP"

    def test_str_numeric_field_not_coerced(self):
        """FIX 6: when the annotation is str, a numeric-looking string must NOT be
        coerced to int. '12345' in a str field must remain '12345' as a string."""
        reliability = _require_reliability()
        result = reliability.strict_coerce({"batch_number": "12345"}, BatchModel)
        assert isinstance(result["batch_number"], str)
        assert result["batch_number"] == "12345"


# ---------------------------------------------------------------------------
# RELIABILITY-02: format_field_level_reprompt — field-specific error messages
# ---------------------------------------------------------------------------

def test_field_level_error_format():
    """format_field_level_reprompt must name the failing field + expected type,
    not just emit a generic message (RELIABILITY-02)."""
    reliability = _require_reliability()
    VERDICT = _require_verdict()
    from pydantic import ValidationError

    try:
        VERDICT(verdict="BAD_VALUE", confidence=99.0, rationale="r", grounding_span="s")
    except ValidationError as exc:
        msg = reliability.format_field_level_reprompt(exc, VERDICT)
        assert any(field in msg for field in ("verdict", "confidence")), (
            f"reprompt message does not name any failing field: {msg!r}"
        )
        assert len(msg) > 20, f"reprompt message suspiciously short: {msg!r}"


# ---------------------------------------------------------------------------
# D-12: coerce_and_validate — typed ParseFailed on exhausted retry (no fabrication)
# ---------------------------------------------------------------------------

def test_no_fabricated_verdict():
    """When given a deliberately malformed input, coerce_and_validate must return
    (None, ParseFailed) — never a fabricated VERDICT (D-12)."""
    reliability = _require_reliability()
    ParseFailed = _require_parse_failed()
    VERDICT = _require_verdict()

    bad_raw = '{"verdict": "TOTALLY_WRONG_ENUM_VALUE", "confidence": "not_a_number"}'
    result_verdict, result_error = reliability.coerce_and_validate(bad_raw, VERDICT)
    assert result_verdict is None, (
        f"Expected None verdict for malformed input, got: {result_verdict}"
    )
    assert result_error is not None, "Expected a ParseFailed error, got None"
    assert isinstance(result_error, ParseFailed), (
        f"Expected ParseFailed, got: {type(result_error)}"
    )
