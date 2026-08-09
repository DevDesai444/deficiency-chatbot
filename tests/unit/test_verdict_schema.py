"""Unit test shells for D-07 — VERDICT model + Databricks-legal schema derivation
+ schema byte-stability invariant.

VERDICT is a future pydantic model in schemas/llm.py (does not exist until Plan 02).
Tests call pytest.skip() at runtime if VERDICT is not yet available so that:
  - pytest --collect-only always exits 0 (collection succeeds)
  - all test items appear in the collection output
  - tests skip cleanly at run time, not at import time

Schema tests reuse the assert_databricks_legal helper inline (same logic as
test_tool_schema_derivation.py).
"""
from __future__ import annotations

import importlib

import pytest


# ---------------------------------------------------------------------------
# Runtime helper — skip individual tests if VERDICT not yet in schemas
# ---------------------------------------------------------------------------

def _require_verdict():
    """Import VERDICT from schemas.llm or skip the calling test."""
    try:
        mod = importlib.import_module("schemas.llm")
        if not hasattr(mod, "VERDICT"):
            pytest.skip("VERDICT model not yet in schemas/llm.py — Plan 02")
        return mod.VERDICT
    except ImportError:
        pytest.skip("schemas.llm not importable")


# ---------------------------------------------------------------------------
# Inline assert_databricks_legal (same logic as test_tool_schema_derivation.py)
# ---------------------------------------------------------------------------

_PROHIBITED_KEYS = ("$ref", "$defs", "anyOf", "oneOf", "allOf", "prefixItems", "pattern")


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _assert_databricks_legal(schema: dict) -> None:
    """Every documented Databricks tool-schema restriction, asserted structurally."""
    schema_keys: set[str] = set()
    for node in _walk(schema):
        for key in node:
            assert key not in _PROHIBITED_KEYS, (
                f"Prohibited key {key!r} found in schema — not Databricks-legal"
            )
            schema_keys.add(key)
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, (
                "Object nodes must have additionalProperties=false"
            )
    assert len(schema_keys) <= 16, (
        f"Schema uses {len(schema_keys)} distinct keys — Databricks limit is 16"
    )


# ---------------------------------------------------------------------------
# D-07: VERDICT model validation
# ---------------------------------------------------------------------------

def test_verdict_model_validates_keep():
    """A valid KEEP verdict must be accepted by the VERDICT model."""
    VERDICT = _require_verdict()
    v = VERDICT(
        verdict="KEEP",
        confidence=0.9,
        rationale="Evidence strongly supports the claim.",
        grounding_span="Section 4.3, paragraph 2",
    )
    assert v.verdict == "KEEP"
    assert v.confidence == pytest.approx(0.9)


def test_verdict_model_validates_downgrade():
    """A valid DOWNGRADE verdict must be accepted by the VERDICT model."""
    VERDICT = _require_verdict()
    v = VERDICT(
        verdict="DOWNGRADE",
        confidence=0.1,
        rationale="Insufficient evidence for the deficiency claim.",
        grounding_span="N/A",
    )
    assert v.verdict == "DOWNGRADE"


def test_verdict_rejects_invalid_enum():
    """An invalid verdict enum value must raise ValidationError (case-sensitive)."""
    VERDICT = _require_verdict()
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VERDICT(
            verdict="keep",  # lowercase — not a valid enum value
            confidence=0.9,
            rationale="...",
            grounding_span="...",
        )


def test_verdict_rejects_confidence_out_of_range():
    """Confidence values outside [0.0, 1.0] must raise ValidationError."""
    VERDICT = _require_verdict()
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        VERDICT(
            verdict="KEEP",
            confidence=1.5,  # out of range
            rationale="...",
            grounding_span="...",
        )


# ---------------------------------------------------------------------------
# D-07: Databricks-legal schema derivation
# ---------------------------------------------------------------------------

def test_guided_schema_is_databricks_legal():
    """tool_schema_for_databricks(VERDICT) must produce a schema with no prohibited keys.

    Prohibited keys: $ref, $defs, anyOf, oneOf, allOf, prefixItems, pattern.
    All object nodes must have additionalProperties=false.
    """
    VERDICT = _require_verdict()
    from llm.structured import tool_schema_for_databricks
    schema = tool_schema_for_databricks(VERDICT)
    _assert_databricks_legal(schema)


def test_guided_schema_is_stable():
    """Schema byte-stability invariant: calling tool_schema_for_databricks(VERDICT) twice
    must return identical output (deterministic guided_json cache key).

    If the schema dict is non-deterministic (e.g., dict insertion-order varies), the
    guided_json argument to the LLM call would differ between calls, defeating caching
    and potentially causing the model to re-learn the schema on every call.
    """
    VERDICT = _require_verdict()
    from llm.structured import tool_schema_for_databricks
    schema_a = tool_schema_for_databricks(VERDICT)
    schema_b = tool_schema_for_databricks(VERDICT)
    assert schema_a == schema_b, (
        "tool_schema_for_databricks(VERDICT) is non-deterministic — "
        "the guided_json cache key would be unstable."
    )
