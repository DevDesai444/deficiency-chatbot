"""Unit tests for Pydantic schema validation."""
from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from schemas.corrections import Correction, Evaluation, RecommendationSet, Verdict
from schemas.documents import ChunkGroup, CTDSection, ParsedSection, SectionSummary
from schemas.events import AgentEvent, EventType
from schemas.flaws import FlawCategory, FlawFinding, FlawReport, Severity


class TestCTDSection:
    def test_all_values_are_strings(self):
        for section in CTDSection:
            assert isinstance(section.value, str)

    def test_known_section_exists(self):
        assert CTDSection.S_4_1_SPECIFICATION == "3.2.S.4.1"


class TestFlawSchemas:
    def test_flaw_finding_defaults(self):
        f = FlawFinding(
            category=FlawCategory.SPEC_MISMATCH,
            section_id="3.2.S.4.1",
            description="Test description",
            evidence="Test evidence",
        )
        assert f.severity == Severity.MEDIUM
        assert f.corroborations == []

    def test_flaw_report_empty(self):
        r = FlawReport(flaws_found=False, findings=[], consensus_summary="Clean")
        assert len(r.findings) == 0

    def test_flaw_finding_new_fields_default_empty(self):
        f = FlawFinding(
            category=FlawCategory.SPEC_MISMATCH,
            section_id="3.2.S.4.1",
            description="Test description",
        )
        assert f.numeric_claims == []
        assert f.guidance_refs == []
        assert f.table_ref == ""

    @pytest.mark.parametrize("value", ["commitment_missing", "coverage_gap"])
    def test_flaw_category_roundtrips_absence_values(self, value):
        assert FlawCategory(value).value == value
        f = FlawFinding(category=value, section_id="3.2.P.6", description="d")
        dumped = f.model_dump()
        assert dumped["category"] == value
        assert FlawFinding(**dumped).category == FlawCategory(value)


class TestCorrectionSchemas:
    def test_correction_defaults(self):
        c = Correction(
            flaw_category=FlawCategory.SPEC_MISMATCH,
            suggestion="Fix it",
            explanation="Because",
        )
        assert c.priority == Severity.MEDIUM
        assert c.references == []

    def test_evaluation_verdicts(self):
        for v in Verdict:
            e = Evaluation(verdict=v, corrections_reviewed=1)
            assert e.verdict == v

    def test_recommendation_set_defaults(self):
        r = RecommendationSet(job_id="test")
        assert r.flaws_found is True
        assert r.recommendations == []
        assert r.analysis_seconds == 0.0


class TestAgentEvent:
    def test_minimal_event(self):
        e = AgentEvent(
            job_id="j1",
            layer="extraction",
            event_type="agent_spawned",
        )
        assert e.agent_name == ""
        assert e.metadata == {}

    def test_model_dump_roundtrip(self):
        e = AgentEvent(
            job_id="j1",
            layer="detection",
            event_type="consensus_reached",
            agent_name="FlawAgent_1",
            message="Found 3 issues",
        )
        d = e.model_dump()
        assert d["layer"] == "detection"
        e2 = AgentEvent(**d)
        assert e2 == e

    def test_agent_event_accepts_parse_repair_event_type(self):
        event = AgentEvent(
            job_id="x",
            layer="correction",
            event_type="parse_repair",
        )
        assert event.event_type == "parse_repair"

    def test_evidence_dropped_is_valid_event_type(self):
        assert "evidence_dropped" in get_args(EventType)

    def test_agent_event_rejects_unknown_event_type(self):
        with pytest.raises(ValidationError):
            AgentEvent(
                job_id="x",
                layer="correction",
                event_type="totally_bogus",
            )

    @pytest.mark.parametrize("event_type", list(get_args(EventType)))
    def test_all_documented_event_types_construct(self, event_type):
        event = AgentEvent(
            job_id="x",
            layer="correction",
            event_type=event_type,
        )
        assert event.event_type == event_type


class TestParsedSection:
    def test_section_creation(self):
        s = ParsedSection(
            section_id="3.2.S.4.1",
            heading="Specifications",
            text="Test content",
            page_range=(1, 5),
        )
        assert s.tables == []

    def test_section_summary_pages_default_zero(self):
        s = SectionSummary(section_id=CTDSection.S_4_1_SPECIFICATION, summary="Spec")
        assert (s.page_start, s.page_end) == (0, 0)
        assert s.key_values == {}

    def test_chunk_group(self):
        sections = [
            ParsedSection(
                section_id=CTDSection.S_1_GENERAL,
                heading="Sec 1",
                text="a" * 100,
                page_range=(1, 2),
            ),
        ]
        g = ChunkGroup(group_id="g1", sections=sections)
        assert len(g.sections) == 1


class TestCorrectionFieldGuidance:
    """Field descriptions are the only place the shape of a Correction reaches the model.

    They are carried into the strict json_schema sent to the endpoint. No prompt states
    what `explanation` should contain, so dropping a description silently returns the
    field to the empty-string default the endpoint emits to satisfy strict decoding.
    """

    def test_descriptions_reach_the_strict_schema(self):
        from llm.structured import schema_for_databricks
        from schemas.corrections import CorrectionList

        props = schema_for_databricks(CorrectionList)["$defs"]["Correction"]["properties"]
        for field in ("suggestion", "explanation", "references"):
            assert props[field].get("description")

    def test_references_permit_empty_rather_than_demand_a_citation(self):
        from schemas.corrections import CorrectionList

        desc = CorrectionList.model_json_schema()["$defs"]["Correction"]["properties"]
        assert "empty" in desc["references"]["description"].lower()

    def test_explanation_is_not_told_to_cite_from_memory(self):
        from schemas.corrections import CorrectionList

        desc = CorrectionList.model_json_schema()["$defs"]["Correction"]["properties"]
        assert "memory" in desc["explanation"]["description"].lower()
