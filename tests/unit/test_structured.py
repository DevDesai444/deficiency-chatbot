from __future__ import annotations

from pydantic import BaseModel, Field

from llm.structured import _extract_json_blob, parse_structured, schema_for_databricks
from schemas.corrections import Correction, CorrectionList, EvaluationOutput


class Simple(BaseModel):
    name: str
    count: int
    tags: list[str] = Field(default_factory=list)


def test_schema_strips_pattern_and_forces_additional_properties_false():
    schema = schema_for_databricks(Simple)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    for prop in schema["properties"].values():
        if isinstance(prop, dict):
            assert "pattern" not in prop


def test_schema_flattens_any_of_null():
    class Optional_(BaseModel):
        x: int | None = None

    schema = schema_for_databricks(Optional_)
    prop = schema["properties"]["x"]
    # anyOf[int, null] should have been flattened
    assert "anyOf" not in prop


def test_extract_json_blob_strips_markdown_fence():
    text = 'Sure! Here is the JSON:\n```json\n{"name": "foo", "count": 3}\n```\nEnd.'
    assert _extract_json_blob(text) == '{"name": "foo", "count": 3}'


def test_extract_json_blob_handles_no_fence():
    text = 'Some prose {"name": "foo", "count": 3} trailing text'
    extracted = _extract_json_blob(text)
    assert '"name"' in extracted
    assert extracted.endswith("}")


def test_parse_structured_repairs_trailing_comma():
    text = '{"name": "foo", "count": 3, "tags": ["a", "b",],}'
    result, err = parse_structured(text, Simple)
    assert err is None
    assert result is not None
    assert result.name == "foo"
    assert result.tags == ["a", "b"]


def test_parse_structured_repairs_unclosed_brace():
    text = '{"name": "foo", "count": 3'
    result, err = parse_structured(text, Simple)
    assert result is not None
    assert result.count == 3


def test_parse_structured_surfaces_validation_error_on_missing_required():
    text = '{"name": "foo"}'  # missing count
    result, err = parse_structured(text, Simple)
    assert result is None
    assert err is not None
    assert "count" in err


def test_parse_correction_list_from_markdown_wrapped_response():
    text = (
        "## Flaw Report\n\n"
        "```json\n"
        '{\n'
        '  "corrections": [\n'
        '    {\n'
        '      "flaw_category": "reference_standard",\n'
        '      "suggestion": "Provide reference standard certificates",\n'
        '      "explanation": "Missing supporting docs",\n'
        '      "priority": "high",\n'
        '      "references": ["21 CFR 211.194"]\n'
        '    }\n'
        '  ]\n'
        '}\n'
        "```\n"
    )
    result, err = parse_structured(text, CorrectionList)
    assert err is None
    assert result is not None
    assert len(result.corrections) == 1
    c = result.corrections[0]
    assert isinstance(c, Correction)
    assert c.suggestion.startswith("Provide reference")


def test_parse_evaluation_output_from_verbose_response():
    text = (
        'The verdict is minor_revision because certain fields lack detail.\n'
        '```json\n{"verdict": "minor_revision", "feedback": "Add references."}\n```'
    )
    result, err = parse_structured(text, EvaluationOutput)
    assert err is None
    assert result is not None
    assert result.verdict.value == "minor_revision"
    assert result.feedback == "Add references."
