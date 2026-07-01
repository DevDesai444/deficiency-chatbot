"""Unit tests for Pydantic schema validation."""
from __future__ import annotations

from schemas.corrections import Correction, Evaluation, RecommendationSet, Verdict
from schemas.documents import ChunkGroup, CTDSection, ParsedSection
from schemas.events import AgentEvent
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


class TestParsedSection:
    def test_section_creation(self):
        s = ParsedSection(
            section_id="3.2.S.4.1",
            heading="Specifications",
            text="Test content",
            page_range=(1, 5),
        )
        assert s.tables == []

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
