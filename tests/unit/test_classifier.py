from __future__ import annotations

import pytest

from agents.detection import classifier
from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS
from schemas.documents import IntermediateReport


@pytest.fixture
def report() -> IntermediateReport:
    return IntermediateReport(document_name="x")


@pytest.fixture
def stub_llm(monkeypatch):
    """Pin the selector's LLM response so only the parsing path is under test."""
    def _stub(response: str) -> None:
        monkeypatch.setattr(
            classifier, "chat_completion", lambda *args, **kwargs: response
        )
    return _stub


@pytest.fixture
def captured_events(monkeypatch) -> list[tuple]:
    events: list[tuple] = []
    monkeypatch.setattr(
        classifier,
        "emit_sync",
        lambda *args, **kwargs: events.append(args),
    )
    return events


def test_unparseable_response_returns_full_catalog(report, stub_llm):
    stub_llm("I cannot help")
    assert classifier.select_flaw_types(report) == list(FLAW_TYPE_DEFINITIONS)


def test_empty_array_returns_full_catalog(report, stub_llm):
    stub_llm("[]")
    selected = classifier.select_flaw_types(report)
    assert selected != []
    assert len(selected) == len(FLAW_TYPE_DEFINITIONS)


def test_valid_selection_returned_unchanged(report, stub_llm):
    stub_llm('["Impurities", "Stability"]')
    assert classifier.select_flaw_types(report) == ["Impurities", "Stability"]


def test_novel_category_preserved(report, stub_llm):
    stub_llm('["Impurities", "Extractables Profile"]')
    assert classifier.select_flaw_types(report) == ["Impurities", "Extractables Profile"]


def test_non_string_entries_dropped(report, stub_llm):
    stub_llm('["Impurities", 5, null]')
    assert classifier.select_flaw_types(report) == ["Impurities"]


def test_all_entries_invalid_returns_full_catalog(report, stub_llm):
    stub_llm("[1, 2, {}]")
    assert len(classifier.select_flaw_types(report)) == len(FLAW_TYPE_DEFINITIONS)


def test_blank_strings_dropped(report, stub_llm):
    stub_llm('["", "   "]')
    assert len(classifier.select_flaw_types(report)) == len(FLAW_TYPE_DEFINITIONS)


def test_duplicates_collapsed(report, stub_llm):
    stub_llm('["Impurities", "Impurities"]')
    assert classifier.select_flaw_types(report) == ["Impurities"]


def test_fallback_emits_warning_and_event(report, stub_llm, captured_events, monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(
        classifier.log,
        "warning",
        lambda event, **kwargs: warnings.append(event),
    )

    stub_llm("[]")
    classifier.select_flaw_types(report, job_id="j1")

    assert warnings == ["flaw_type_selection_fallback"]
    assert len(captured_events) == 1
    assert captured_events[0][:3] == ("j1", "detection", "parse_repair")


def test_valid_selection_emits_no_event(report, stub_llm, captured_events):
    stub_llm('["Impurities"]')
    classifier.select_flaw_types(report, job_id="j1")
    assert captured_events == []


def test_fallback_without_job_id_does_not_emit(report, stub_llm, captured_events):
    stub_llm("[]")
    assert len(classifier.select_flaw_types(report)) == len(FLAW_TYPE_DEFINITIONS)
    assert captured_events == []
