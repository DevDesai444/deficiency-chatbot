from __future__ import annotations

from autogen import ConversableAgent

from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS
from llm.prompts import FLAW_DETECTION_AGENT, FLAW_MODERATOR


def make_flaw_agent(
    flaw_type: str,
    llm_config: dict,
) -> ConversableAgent:
    description = FLAW_TYPE_DEFINITIONS.get(flaw_type, flaw_type)
    system_prompt = FLAW_DETECTION_AGENT.format(flaw_type=flaw_type)

    safe_name = flaw_type.replace("/", "_").replace(" ", "_")
    return ConversableAgent(
        name=f"Flaw_{safe_name}",
        system_message=system_prompt,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description=f"Detects {flaw_type} deficiencies: {description}",
        default_auto_reply="",
        max_consecutive_auto_reply=3,
        code_execution_config=False,
    )


def make_flaw_moderator(llm_config: dict) -> ConversableAgent:
    return ConversableAgent(
        name="Flaw_Moderator",
        system_message=FLAW_MODERATOR,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="Moderates flaw detection consensus discussion",
        default_auto_reply="",
        max_consecutive_auto_reply=3,
        code_execution_config=False,
    )
