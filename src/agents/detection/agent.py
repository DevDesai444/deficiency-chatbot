from __future__ import annotations

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS
from llm.prompts import FLAW_DETECTION_AGENT, FLAW_MODERATOR


def make_flaw_agent(
    flaw_type: str,
    model_client: OpenAIChatCompletionClient,
) -> AssistantAgent:
    description = FLAW_TYPE_DEFINITIONS.get(flaw_type, flaw_type)
    system_prompt = FLAW_DETECTION_AGENT.format(flaw_type=flaw_type)

    safe_name = flaw_type.replace("/", "_").replace(" ", "_")
    return AssistantAgent(
        name=f"Flaw_{safe_name}",
        model_client=model_client,
        system_message=system_prompt,
        description=f"Detects {flaw_type} deficiencies: {description}",
    )


def make_flaw_moderator(
    model_client: OpenAIChatCompletionClient,
) -> AssistantAgent:
    return AssistantAgent(
        name="Flaw_Moderator",
        model_client=model_client,
        system_message=FLAW_MODERATOR,
        description="Moderates flaw detection consensus discussion",
    )
