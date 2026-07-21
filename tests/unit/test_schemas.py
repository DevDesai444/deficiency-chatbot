"""Unit tests for Pydantic schema validation."""
from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from schemas.documents import ChunkGroup, CTDSection, ParsedSection
from schemas.events import AgentEvent, EventType
from schemas.faults import EvidenceClass, Fault, FaultReport, Tier
from schemas.flaws import FlawCategory, Severity, SimilarDeficiency


class TestCTDSection:
    def test_all_values_are_strings(self):
        for section in CTDSection:
            assert isinstance(section.value, str)

    def test_known_section_exists(self):
        assert CTDSection.S_4_1_SPECIFICATION == "3.2.S.4.1"


class TestFaultSchemas:
    def test_fault_defaults(self):
        f = Fault(title="Missing residual solvent spec")
        assert f.severity == Severity.MEDIUM
        assert f.tier == Tier.ADVISORY
        assert f.evidence_class == EvidenceClass.MODEL_JUDGMENT
        assert f.category == FlawCategory.GENERAL_CMC
        assert f.precedents == []
        assert f.novel is False

    def test_fault_report_empty(self):
        r = FaultReport(job_id="j", faults=[], faults_found=False)
        assert r.faults == []
        assert r.faults_found is False

    def test_confidence_is_bounded(self):
        with pytest.raises(ValidationError):
            Fault(title="x", confidence=1.5)

    def test_fault_roundtrips(self):
        f = Fault(
            title="Result out of specification",
            category=FlawCategory.SPEC_MISMATCH,
            tier=Tier.VERIFIED,
            evidence_class=EvidenceClass.CODE_VERIFIED,
            precedents=[SimilarDeficiency(product_name="X", deficiency_text="y")],
        )
        dumped = f.model_dump()
        assert Fault(**dumped).tier == Tier.VERIFIED
        assert Fault(**dumped).precedents[0].product_name == "X"


class TestAgentEvent:
    def test_minimal_event(self):
        e = AgentEvent(job_id="j1", layer="detection", event_type="agent_spawned")
        assert e.agent_name == ""
        assert e.metadata == {}

    def test_model_dump_roundtrip(self):
        e = AgentEvent(
            job_id="j1",
            layer="detection",
            event_type="layer_complete",
            agent_name="specialist:impurities",
            message="3 faults",
        )
        d = e.model_dump()
        assert d["layer"] == "detection"
        assert AgentEvent(**d) == e

    def test_agent_event_rejects_unknown_event_type(self):
        with pytest.raises(ValidationError):
            AgentEvent(job_id="x", layer="detection", event_type="totally_bogus")

    @pytest.mark.parametrize("event_type", list(get_args(EventType)))
    def test_all_documented_event_types_construct(self, event_type):
        event = AgentEvent(job_id="x", layer="detection", event_type=event_type)
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
