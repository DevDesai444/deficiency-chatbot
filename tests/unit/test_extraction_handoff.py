"""Unit tests for the Layer 1 -> Layer 2 handoff payload."""
from __future__ import annotations

import json

import pytest

from agents.extraction.agent import build_extraction_prompt, build_structured_extraction_prompt
from agents.extraction.group import _build_transcript, _run_extraction_async
from schemas.documents import (
    CTDSection,
    ExtractionFindingOut,
    GroupExtract,
    KeyValue,
    SectionExtract,
)


class _Msg:
    def __init__(self, source, content):
        self.source = source
        self.content = content


class _Agent:
    def __init__(self, name):
        self.name = name


class _Team:
    def __init__(self, *args, **kwargs):
        pass

    async def run(self, task):
        class _Result:
            messages = [_Msg("Extraction_Moderator", "consolidated. EXTRACTION_COMPLETE")]
        return _Result()


@pytest.fixture
def group():
    return {
        "group_id": "group_0",
        "sections": [
            {
                "heading": "AET Derivation",
                "text": "The AET was calculated as 22.727 ug/g.",
                "blocks": [{"role": "paragraph", "text": "The AET was calculated as 22.727 ug/g."}],
                "tables": [{
                    "kind": "grid", "title": "Table 16",
                    "headers": ["Compound", "Result"], "rows": [["2-Butanone", "8.72 ug/g"]],
                    "pairs": [], "page": 16,
                }],
                "figures": [],
                "page_start": 14, "page_end": 17,
            },
            {
                "heading": "Leachables Summary",
                "text": "No PDE was established for the identified leachable.",
                "blocks": [{"role": "paragraph", "text": "No PDE was established for the identified leachable."}],
                "tables": [], "figures": [],
                "page_start": 18, "page_end": 19,
            },
        ],
    }


@pytest.fixture
def patched(monkeypatch, group):
    """Stub the AutoGen team and model client; structured_call is set per-test."""
    import agents.extraction.group as mod

    monkeypatch.setattr(mod, "_make_model_client", lambda *a, **k: object())
    monkeypatch.setattr(mod, "make_extraction_agent", lambda g, c: _Agent(f"Extractor_{g['group_id']}"))
    monkeypatch.setattr(mod, "make_extraction_moderator", lambda c: _Agent("Extraction_Moderator"))
    monkeypatch.setattr(mod, "RoundRobinGroupChat", _Team)
    monkeypatch.setattr(mod, "emit_sync", lambda *a, **k: None)
    return mod


def _set_extract(monkeypatch, mod, extract):
    def fake_structured_call(**kwargs):
        return extract, None
    monkeypatch.setattr(mod, "structured_call", fake_structured_call)


class TestPromptFidelity:
    def test_structured_prompt_carries_text_and_table_cells(self, group):
        prompt = build_structured_extraction_prompt(group, "transcript")
        for probe in ["22.727", "8.72", "Table 16", "2-Butanone", "PDE"]:
            assert probe in prompt

    def test_structured_prompt_labels_sections_by_index(self, group):
        prompt = build_structured_extraction_prompt(group, "")
        assert "[section_index: 0]" in prompt
        assert "[section_index: 1]" in prompt

    def test_plain_extraction_prompt_is_structured_json(self, group):
        """The agent-facing prompt is the section's structured JSON -- not flattened text."""
        prompt = build_extraction_prompt(group)
        objs = [json.loads(line) for line in prompt.splitlines() if line.strip()]
        assert len(objs) == 2
        assert objs[0]["heading"] == "AET Derivation"
        assert any("22.727" in c["text"] for c in objs[0]["content"])
        assert objs[0]["tables"][0]["rows"] == [["2-Butanone", "8.72 ug/g"]]
        assert any("PDE" in c["text"] for c in objs[1]["content"])


class TestTranscript:
    def test_task_echo_excluded(self):
        msgs = [_Msg("user", "## Section\nsource text"), _Msg("Extractor_group_0", "I found X")]
        transcript = _build_transcript(msgs)
        assert "source text" not in transcript
        assert transcript == "[Extractor_group_0] I found X"

    def test_non_string_content_skipped(self):
        assert _build_transcript([_Msg("Extractor_group_0", None), _Msg("A", "")]) == ""

    def test_consensus_survives_truncation(self, group):
        """The task echo is far longer than the budget; the consensus arrives last."""
        msgs = [
            _Msg("user", "## Section\n" + "body text " * 2000),
            _Msg("Extractor_group_0", "The AET is 22.727"),
            _Msg("Extraction_Moderator", "CONSENSUS_MARKER. EXTRACTION_COMPLETE"),
        ]
        prompt = build_structured_extraction_prompt(group, _build_transcript(msgs))
        discussion = prompt.split("## Extraction discussion")[1]
        assert "CONSENSUS_MARKER" in discussion

    def test_long_transcript_trimmed_from_front(self, group):
        msgs = [_Msg("Extractor_group_0", "x" * 20000), _Msg("Extraction_Moderator", "TAIL_MARKER")]
        prompt = build_structured_extraction_prompt(group, _build_transcript(msgs))
        discussion = prompt.split("## Extraction discussion")[1]
        assert "TAIL_MARKER" in discussion
        assert len(discussion) < 9000


class TestHandoffPayload:
    @pytest.mark.asyncio
    async def test_evidence_reaches_layer_two(self, monkeypatch, patched, group):
        """The substring probes that failed against the shipped pipeline."""
        _set_extract(monkeypatch, patched, GroupExtract(sections=[
            SectionExtract(
                section_index=0,
                summary="AET derivation for the drug product.",
                key_values=[
                    KeyValue(label="AET calculated", value="22.727 ug/g"),
                    KeyValue(label="2-Butanone result", value="8.72 ug/g"),
                    KeyValue(label="Source table", value="Table 16"),
                ],
            ),
            SectionExtract(
                section_index=1,
                summary="Leachables summary.",
                findings=[ExtractionFindingOut(
                    finding="No PDE established",
                    evidence="No PDE was established for the identified leachable.",
                )],
            ),
        ]))

        report = await _run_extraction_async([group], "EL_Report", "E&L", "job1")
        payload = json.dumps(report.model_dump(), default=str)

        for probe in ["22.727", "8.72", "Table 16", "2-Butanone", "PDE"]:
            assert probe in payload, f"{probe} absent from the Layer 2 payload"

    @pytest.mark.asyncio
    async def test_findings_are_constructed(self, monkeypatch, patched, group):
        _set_extract(monkeypatch, patched, GroupExtract(sections=[
            SectionExtract(
                section_index=1,
                summary="Leachables summary.",
                findings=[ExtractionFindingOut(
                    finding="No PDE established",
                    evidence="No PDE was established for the identified leachable.",
                )],
            ),
        ]))

        report = await _run_extraction_async([group], "EL_Report", "E&L", "job1")
        assert len(report.findings) == 1
        assert report.findings[0].agent_name == "Extractor_group_0"
        assert report.findings[0].section_id == CTDSection.UNKNOWN  # CTD no longer computed

    @pytest.mark.asyncio
    async def test_page_range_carried(self, monkeypatch, patched, group):
        _set_extract(monkeypatch, patched, GroupExtract(sections=[]))
        report = await _run_extraction_async([group], "EL_Report", "E&L", "job1")
        assert (report.sections[0].page_start, report.sections[0].page_end) == (14, 17)
        assert (report.sections[1].page_start, report.sections[1].page_end) == (18, 19)

    @pytest.mark.asyncio
    async def test_sections_addressed_by_index_not_ctd_id(self, monkeypatch, patched, group):
        """Both sections share a CTDSection; each must keep its own extract."""
        _set_extract(monkeypatch, patched, GroupExtract(sections=[
            SectionExtract(section_index=0, summary="First summary"),
            SectionExtract(section_index=1, summary="Second summary"),
        ]))
        report = await _run_extraction_async([group], "EL_Report", "E&L", "job1")
        assert [s.summary for s in report.sections] == ["First summary", "Second summary"]

    @pytest.mark.asyncio
    async def test_unanchored_values_dropped_from_payload(self, monkeypatch, patched, group):
        _set_extract(monkeypatch, patched, GroupExtract(sections=[
            SectionExtract(
                section_index=0,
                summary="AET derivation.",
                key_values=[
                    KeyValue(label="AET", value="22.727 ug/g"),
                    KeyValue(label="Invented", value="99.999 ug/g"),
                ],
            ),
        ]))
        report = await _run_extraction_async([group], "EL_Report", "E&L", "job1")
        assert report.sections[0].key_values == {"AET": "22.727 ug/g"}


class TestZeroFindingsRemainsPossible:
    @pytest.mark.asyncio
    async def test_empty_group_extract_yields_no_findings(self, monkeypatch, patched, group):
        _set_extract(monkeypatch, patched, GroupExtract(sections=[]))
        report = await _run_extraction_async([group], "Clean", "E&L", "job1")

        assert report.findings == []
        assert all(s.key_values == {} for s in report.sections)
        assert [s.summary for s in report.sections] == ["AET Derivation", "Leachables Summary"]

    @pytest.mark.asyncio
    async def test_clean_sections_yield_no_findings(self, monkeypatch, patched, group):
        _set_extract(monkeypatch, patched, GroupExtract(sections=[
            SectionExtract(section_index=0, summary="Nothing salient."),
            SectionExtract(section_index=1, summary="Nothing salient."),
        ]))
        report = await _run_extraction_async([group], "Clean", "E&L", "job1")
        assert report.findings == []
        assert all(s.key_values == {} for s in report.sections)

    @pytest.mark.asyncio
    async def test_parse_failure_degrades_to_headings(self, monkeypatch, patched, group):
        """A parse failure must never fabricate — it falls back to today's output."""
        from schemas.corrections import ParseFailed

        def failing_call(**kwargs):
            return None, ParseFailed(layer="L6", reason="unparseable", raw_output="")
        monkeypatch.setattr(patched, "structured_call", failing_call)

        report = await _run_extraction_async([group], "EL_Report", "E&L", "job1")
        assert report.findings == []
        assert [s.summary for s in report.sections] == ["AET Derivation", "Leachables Summary"]
