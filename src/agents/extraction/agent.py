from __future__ import annotations

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from llm.prompts import EXTRACTION_AGENT, EXTRACTION_MODERATOR
from schemas.documents import ChunkGroup


def make_extraction_agent(
    group: ChunkGroup,
    model_client: OpenAIChatCompletionClient,
) -> AssistantAgent:
    section_summary = "\n".join(
        f"- {s.heading}: {len(s.text)} chars, {len(s.tables)} tables"
        for s in group.sections
    )

    return AssistantAgent(
        name=f"Extractor_{group.group_id}",
        model_client=model_client,
        system_message=EXTRACTION_AGENT,
        description=f"Extraction agent for sections: {section_summary}",
    )


def make_extraction_moderator(
    model_client: OpenAIChatCompletionClient,
) -> AssistantAgent:
    return AssistantAgent(
        name="Extraction_Moderator",
        model_client=model_client,
        system_message=EXTRACTION_MODERATOR,
        description="Moderator that consolidates extraction findings",
    )


def build_extraction_prompt(group: ChunkGroup) -> str:
    parts = []
    for section in group.sections:
        parts.append(f"## {section.heading}")
        parts.append(section.text[:4000])
        if section.tables:
            for table in section.tables:
                parts.append(f"\nTable: {table.title}")
                if table.headers:
                    parts.append(" | ".join(table.headers))
                for row in table.rows[:10]:
                    parts.append(" | ".join(row))
        parts.append("")
    return "\n".join(parts)
