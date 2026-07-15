from __future__ import annotations

import pytest

from agents.detection import classifier
from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS
from schemas.documents import CTDSection, IntermediateReport


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


class TestDescribeDocument:
    """The scope guard in FLAW_DETECTION_AGENT cannot fire on a bare CTD code."""

    def test_names_the_subject_for_substance_sections(self):
        described = classifier.describe_document(CTDSection.S_4_1_SPECIFICATION)
        assert "3.2.S.4.1" in described
        assert "Raw Material Specification" in described
        assert "drug substance" in described

    def test_names_the_subject_for_product_sections(self):
        assert "drug product" in classifier.describe_document(CTDSection.P_7_STABILITY)

    def test_unknown_section_is_stated_not_guessed(self):
        described = classifier.describe_document(CTDSection.UNKNOWN)
        assert "unidentified" in described
        assert "drug substance" not in described
        assert "drug product" not in described

    def test_falls_back_to_the_code_when_unlabelled(self):
        # Every enum member must describe without raising, labelled or not.
        for section in CTDSection:
            assert classifier.describe_document(section)

    def test_states_identity_without_prescribing_content(self):
        """A glossary, not a rulebook — it says what the document is, never what belongs in it."""
        for section in CTDSection:
            described = classifier.describe_document(section).lower()
            for rule_word in ("must", "shall", "should", "require"):
                assert rule_word not in described
