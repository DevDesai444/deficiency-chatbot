from __future__ import annotations

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from llm.prompts import EXTRACTION_AGENT, EXTRACTION_MODERATOR
from schemas.documents import ChunkGroup, ParsedSection


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


def _render_section(section: ParsedSection, label: str) -> list[str]:
    parts = [f"## {label}"]
    parts.append(section.text[:4000])
    if section.tables:
        for table in section.tables:
            parts.append(f"\nTable: {table.title}")
            if table.kind == "key_value" or table.pairs:
                for pair in table.pairs:
                    parts.append(f"{pair.label}: {pair.value}")
            else:
                if table.headers:
                    parts.append(" | ".join(table.headers))
                for row in table.rows[:10]:
                    parts.append(" | ".join(row))
    parts.append("")
    return parts


def build_extraction_prompt(group: ChunkGroup) -> str:
    parts = []
    for section in group.sections:
        parts.extend(_render_section(section, section.heading))
    return "\n".join(parts)


# The discussion converges at the end, so the transcript is trimmed from the front.
_TRANSCRIPT_CHAR_BUDGET = 8000


def build_structured_extraction_prompt(group: ChunkGroup, transcript: str) -> str:
    """Sections labelled by position, since CTD ids repeat within a group."""
    parts = []
    for index, section in enumerate(group.sections):
        parts.extend(_render_section(section, f"[section_index: {index}] {section.heading}"))
    sources = "\n".join(parts)

    return (
        f"## Source sections\n\n{sources}\n\n"
        f"## Extraction discussion\n\n{transcript[-_TRANSCRIPT_CHAR_BUDGET:]}\n\n"
        "Emit one entry per section above, echoing its section_index exactly as given."
    )
