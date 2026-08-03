from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agents.review.registry import (
    EmitFindingArgs,
    ToolRegistry,
)
from agents.review.spanref import SPAN_REF_RE
from tests.agents.review.conftest import build_multi_corpus_index
from tests.unit.test_tool_schema_derivation import _walk, assert_databricks_legal

PROHIBITED_KEYS = ("$ref", "$defs", "anyOf", "oneOf", "allOf", "prefixItems", "pattern")


def _registry_for(corpus):
    return ToolRegistry(
        corpus=corpus,
        manifest=corpus.manifest,
        ledger=pytest.importorskip("tools.ledger").RetrievalLedger(),
    )


def _blocks(text: str) -> list[dict]:
    return [{"text": text, "role": "body", "reading_order": 0}]


def _schemas(registry: ToolRegistry) -> list[dict]:
    return registry.schemas()


def _parameter_schema(tool: dict) -> dict:
    return tool["function"]["parameters"]


def _tool_by_name(registry: ToolRegistry, name: str) -> dict:
    return next(tool for tool in registry.schemas() if tool["function"]["name"] == name)


def test_all_seven_schemas_are_databricks_legal(tmp_path):
    registry = _registry_for(
        build_multi_corpus_index(
            tmp_path,
            [("doc-a", _blocks("Assay validation includes precision."), ["Validation"])],
        )
    )
    schemas = _schemas(registry)

    assert len(schemas) == 7
    names = [schema["function"]["name"] for schema in schemas]
    assert names == [
        "search_corpus",
        "open_doc",
        "get_section",
        "read_guideline",
        "follow_reference",
        "emit_finding",
        "run_oracles",
    ]
    assert len(set(names)) == len(names)
    for schema in schemas:
        assert_databricks_legal(_parameter_schema(schema))


def test_no_prohibited_construct_in_any_schema(tmp_path):
    registry = _registry_for(
        build_multi_corpus_index(tmp_path, [("doc-a", _blocks("Stability commitment."), ["Stability"])])
    )

    for tool in registry.schemas():
        seen = {
            key
            for node in _walk(_parameter_schema(tool))
            if isinstance(node, dict)
            for key in node
        }
        assert not (seen & set(PROHIBITED_KEYS)), (tool["function"]["name"], seen & set(PROHIBITED_KEYS))


def test_every_schema_is_within_the_key_cap(tmp_path):
    registry = _registry_for(
        build_multi_corpus_index(tmp_path, [("doc-a", _blocks("Reference standard lots."), ["Reference"])])
    )

    for tool in registry.schemas():
        keys = {
            key
            for node in _walk(_parameter_schema(tool))
            if isinstance(node, dict)
            for key in node
        }
        assert len(keys) <= 16, (tool["function"]["name"], sorted(keys))


def test_tool_count_is_within_the_databricks_cap(tmp_path):
    registry = _registry_for(
        build_multi_corpus_index(tmp_path, [("doc-a", _blocks("One document."), ["Heading"])])
    )

    assert len(registry.schemas()) <= 32


def test_verdict_enum():
    schema = EmitFindingArgs.model_json_schema()
    registry_schema = _parameter_schema(_tool_by_name(object.__new__(ToolRegistry), "emit_finding"))
    verdict = registry_schema["properties"]["verdict"]

    assert verdict["type"] == "string"
    assert verdict["enum"] == ["violation", "gap", "ambiguous"]
    assert "compliant" not in verdict["enum"]
    assert schema["properties"]["verdict"]
    with pytest.raises(ValidationError):
        EmitFindingArgs(
            submission_span_id="[mvr1381:1:2]",
            rule_span_id="[ecfr-211:1:2]",
            verdict="compliant",
            title="Compliant answer should not validate",
            detail="This is deliberately rejected.",
        )


def test_span_ids_are_strings_not_nested_models():
    schema = _parameter_schema(_tool_by_name(object.__new__(ToolRegistry), "emit_finding"))

    assert schema["properties"]["submission_span_id"]["type"] == "string"
    assert schema["properties"]["rule_span_id"]["type"] == "string"
    for node in _walk(schema):
        if isinstance(node, dict):
            assert "$ref" not in node


def test_span_id_description_shows_the_rendered_form():
    schema = _parameter_schema(_tool_by_name(object.__new__(ToolRegistry), "emit_finding"))

    for field_name in ("submission_span_id", "rule_span_id"):
        description = schema["properties"][field_name]["description"]
        assert SPAN_REF_RE.search(description)


def test_schema_list_is_deterministic(tmp_path):
    corpus_a = build_multi_corpus_index(
        tmp_path / "a",
        [("doc-a", _blocks("Assay validation content."), ["Assay"])],
    )
    corpus_b = build_multi_corpus_index(
        tmp_path / "b",
        [
            ("doc-b", _blocks("Different impurity content."), ["Impurities"]),
            ("doc-c", _blocks("Different stability content."), ["Stability"]),
        ],
    )

    left = json.dumps(_registry_for(corpus_a).schemas(), sort_keys=True)
    right = json.dumps(_registry_for(corpus_b).schemas(), sort_keys=True)

    assert left == right


def test_required_fields_are_required():
    registry = object.__new__(ToolRegistry)
    required_by_tool = {
        "search_corpus": {"query"},
        "open_doc": {"doc_id"},
        "get_section": {"doc_id"},
        "read_guideline": set(),
        "follow_reference": {"doc_id", "ref_text"},
        "emit_finding": {"submission_span_id", "rule_span_id", "verdict", "title", "detail"},
        "run_oracles": {"doc_id"},
    }

    for tool_name, required_fields in required_by_tool.items():
        schema = _parameter_schema(_tool_by_name(registry, tool_name))
        assert required_fields <= set(schema.get("required", []))


def test_d_ri2_optional_citation_surface_is_preserved():
    schema = _parameter_schema(_tool_by_name(object.__new__(ToolRegistry), "read_guideline"))

    assert "citation" in schema["properties"]
    assert "citation" not in schema.get("required", [])
