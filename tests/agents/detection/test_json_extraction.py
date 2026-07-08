"""Regression tests for LLM JSON extraction in the detection agents.

Guards against the greedy ``response.index('[') → response.rindex(']')`` slice
that used to swallow prose bracket pairs. Both call sites now use a
bracket-balanced extractor plus ``repair_json`` fallback.
"""
from __future__ import annotations

import pytest

from agents.detection import classifier as classifier_mod
from agents.detection import group as group_mod
from agents.detection.classifier import select_flaw_types
from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS
from agents.detection.group import _extract_structured_findings
from schemas.documents import CTDSection, IntermediateReport


_ONE_FINDING_JSON = (
    '{"category":"general_cmc","description":"x","evidence":"y",'
    '"severity":"medium","section_id":"unknown"}'
)


def _patch_group_response(monkeypatch: pytest.MonkeyPatch, response: str) -> None:
    monkeypatch.setattr(
        group_mod,
        "chat_completion",
        lambda *args, **kwargs: response,
    )


def _patch_classifier_response(monkeypatch: pytest.MonkeyPatch, response: str) -> None:
    monkeypatch.setattr(
        classifier_mod,
        "chat_completion",
        lambda *args, **kwargs: response,
    )


def _minimal_report() -> IntermediateReport:
    return IntermediateReport(
        document_name="test.pdf",
        document_type="Unknown",
        sections=[],
        findings=[],
        consensus_notes="",
    )


# ---------------------------------------------------------------------------
# _extract_structured_findings (group.py)
# ---------------------------------------------------------------------------


def test_extract_findings_prose_with_multiple_bracket_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = f"Findings: [{_ONE_FINDING_JSON}]. See also: [refs]"
    _patch_group_response(monkeypatch, response)
    findings = _extract_structured_findings("consensus", CTDSection.UNKNOWN)
    assert len(findings) == 1
    assert findings[0].description == "x"


def test_extract_findings_markdown_fenced_json_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = f"```json\n[{_ONE_FINDING_JSON}]\n```"
    _patch_group_response(monkeypatch, response)
    findings = _extract_structured_findings("consensus", CTDSection.UNKNOWN)
    assert len(findings) == 1


def test_extract_findings_trailing_comma_repaired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = (
        '[{"category":"general_cmc","description":"x","evidence":"y",'
        '"severity":"medium","section_id":"unknown",},]'
    )
    _patch_group_response(monkeypatch, response)
    findings = _extract_structured_findings("consensus", CTDSection.UNKNOWN)
    assert len(findings) == 1


def test_extract_findings_all_prose_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_group_response(monkeypatch, "No findings identified in this document.")
    findings = _extract_structured_findings("consensus", CTDSection.UNKNOWN)
    assert findings == []


def test_extract_findings_empty_response_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_group_response(monkeypatch, "")
    findings = _extract_structured_findings("consensus", CTDSection.UNKNOWN)
    assert findings == []


# ---------------------------------------------------------------------------
# select_flaw_types (classifier.py)
# ---------------------------------------------------------------------------


def test_select_flaw_types_prose_with_multiple_bracket_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = 'Categories: ["specification","stability"]. Skipped: [none]'
    _patch_classifier_response(monkeypatch, response)
    assert select_flaw_types(_minimal_report()) == ["specification", "stability"]


def test_select_flaw_types_markdown_fenced_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = '```json\n["specification","stability"]\n```'
    _patch_classifier_response(monkeypatch, response)
    assert select_flaw_types(_minimal_report()) == ["specification", "stability"]


def test_select_flaw_types_trailing_comma_repaired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_classifier_response(monkeypatch, '["specification",]')
    assert select_flaw_types(_minimal_report()) == ["specification"]


def test_select_flaw_types_all_prose_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_classifier_response(monkeypatch, "No categories selected.")
    fallback = list(FLAW_TYPE_DEFINITIONS.keys())[:4]
    assert select_flaw_types(_minimal_report()) == fallback


def test_select_flaw_types_non_string_elements_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_classifier_response(monkeypatch, "[1,2,3]")
    fallback = list(FLAW_TYPE_DEFINITIONS.keys())[:4]
    assert select_flaw_types(_minimal_report()) == fallback
