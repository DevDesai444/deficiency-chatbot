from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import BaseModel, Field

from llm.structured import build_tool_schema, tool_schema_for_databricks

PROHIBITED_KEYS = ("$ref", "$defs", "anyOf", "oneOf", "allOf", "prefixItems", "pattern")


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def assert_databricks_legal(schema: dict) -> None:
    """Every documented Databricks tool-schema restriction, asserted structurally."""
    schema_keys = set()
    for node in _walk(schema):
        for key in node:
            assert key not in PROHIBITED_KEYS
            schema_keys.add(key)
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
    assert len(schema_keys) <= 16


class FlatArgs(BaseModel):
    query: str
    top_k: int = Field(ge=1)


class InnerArgs(BaseModel):
    doc_id: str
    heading: str | None = None


class NestedArgs(BaseModel):
    target: InnerArgs
    include_tables: bool = False


class Verdict(StrEnum):
    VIOLATION = "violation"
    GAP = "gap"


class EnumArgs(BaseModel):
    verdict: Verdict


def test_flat_scalar_model_derives_legal_schema():
    schema = tool_schema_for_databricks(FlatArgs)
    assert_databricks_legal(schema)
    assert set(schema["properties"]) == {"query", "top_k"}


def test_nested_model_inlines_refs():
    schema = tool_schema_for_databricks(NestedArgs)
    assert_databricks_legal(schema)
    assert set(schema["properties"]) == {"target", "include_tables"}
    assert set(schema["properties"]["target"]["properties"]) == {"doc_id", "heading"}


def test_optional_string_flattens_nullable_anyof():
    schema = tool_schema_for_databricks(InnerArgs)
    assert_databricks_legal(schema)
    assert schema["properties"]["heading"]["type"] == "string"


def test_enum_field_derives_without_refs():
    schema = tool_schema_for_databricks(EnumArgs)
    assert_databricks_legal(schema)
    assert schema["properties"]["verdict"] == {
        "enum": ["violation", "gap"],
        "title": "Verdict",
        "type": "string",
    }


def test_build_tool_schema_wraps_function_parameters():
    tool = build_tool_schema(FlatArgs, name="search_corpus", description="Search the corpus")
    assert set(tool) == {"type", "function"}
    assert tool["type"] == "function"
    assert set(tool["function"]) == {"name", "description", "parameters"}
    assert tool["function"]["name"] == "search_corpus"
    assert_databricks_legal(tool["function"]["parameters"])


def test_raw_schema_is_illegal_negative_control():
    with pytest.raises(AssertionError):
        assert_databricks_legal(NestedArgs.model_json_schema())
