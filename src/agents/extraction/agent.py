from __future__ import annotations

from autogen import ConversableAgent

from llm.prompts import EXTRACTION_AGENT, EXTRACTION_MODERATOR
from schemas.documents import ChunkGroup


def make_extraction_agent(
    group: ChunkGroup,
    llm_config: dict,
) -> ConversableAgent:
    section_summary = "\n".join(
        f"- {s.heading}: {len(s.text)} chars, {len(s.tables)} tables"
        for s in group.sections
    )

    return ConversableAgent(
        name=f"Extractor_{group.group_id}",
        system_message=EXTRACTION_AGENT,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description=f"Extraction agent for sections: {section_summary}",
        default_auto_reply="",
        max_consecutive_auto_reply=2,
        code_execution_config=False,
    )


def make_extraction_moderator(llm_config: dict) -> ConversableAgent:
    return ConversableAgent(
        name="Extraction_Moderator",
        system_message=EXTRACTION_MODERATOR,
        llm_config=llm_config,
        human_input_mode="NEVER",
        description="Moderator that consolidates extraction findings",
        default_auto_reply="",
        max_consecutive_auto_reply=2,
        code_execution_config=False,
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
