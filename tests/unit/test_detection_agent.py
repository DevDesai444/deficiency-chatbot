"""Unit tests for flaw specialist agent construction and prompt rendering."""
from __future__ import annotations

import pytest
from autogen_ext.models.openai import OpenAIChatCompletionClient

from agents.detection.agent import make_flaw_agent
from llm.prompts import FLAW_DETECTION_AGENT

_ABSENCE_TYPES = ("Commitments/Undertakings", "Coverage Gaps")


@pytest.fixture(scope="module")
def model_client():
    return OpenAIChatCompletionClient(
        model="stub",
        base_url="http://localhost/v1",
        api_key="not-used",
        model_info={
            "vision": False,
            "function_calling": False,
            "json_output": False,
            "family": "unknown",
            "structured_output": False,
        },
    )


class TestMakeFlawAgent:
    def test_make_flaw_agent_builds_absence_category(self, model_client):
        agent = make_flaw_agent("Commitments/Undertakings", model_client)
        assert agent.name == "Flaw_Commitments_Undertakings"

    def test_absence_agent_description_uses_catalog(self, model_client):
        agent = make_flaw_agent("Commitments/Undertakings", model_client)
        assert "post-approval reporting" in agent.description


class TestFlawDetectionPrompt:
    @pytest.mark.parametrize("flaw_type", _ABSENCE_TYPES)
    def test_prompt_carries_no_force_instruction(self, flaw_type):
        prompt = FLAW_DETECTION_AGENT.format(flaw_type=flaw_type)
        assert f"No {flaw_type} deficiencies identified" in prompt
        assert "do NOT force findings" in prompt

    @pytest.mark.parametrize("flaw_type", _ABSENCE_TYPES)
    def test_prompt_states_absence_cannot_manufacture(self, flaw_type):
        prompt = FLAW_DETECTION_AGENT.format(flaw_type=flaw_type)
        assert "is not evidence that one exists" in prompt

    def test_prompt_unchanged_for_defect_categories(self):
        prompt = FLAW_DETECTION_AGENT.format(flaw_type="Specification/CoA")
        assert "do NOT force findings" in prompt
