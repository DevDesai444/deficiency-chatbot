from __future__ import annotations

import json

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from llm.prompts import EXTRACTION_AGENT, EXTRACTION_MODERATOR

# Groups and sections flow as plain JSON dicts (see parse.section_splitter):
#   group   = {"group_id": str, "sections": [section, ...]}
#   section = {"heading", "text", "blocks", "tables", "figures", "page_start", "page_end"}


def make_extraction_agent(
    group: dict,
    model_client: OpenAIChatCompletionClient,
) -> AssistantAgent:
    section_summary = "\n".join(
        f"- {s['heading']}: {len(s.get('text', ''))} chars, {len(s.get('tables', []))} tables"
        for s in group["sections"]
    )

    return AssistantAgent(
        name=f"Extractor_{group['group_id']}",
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


def _table_to_json(table: dict) -> dict:
    out: dict = {"title": table.get("title", ""), "kind": table.get("kind", "grid"), "page": table.get("page", 0)}
    if table.get("kind") == "key_value":
        out["pairs"] = {p["label"]: p["value"] for p in table.get("pairs", [])}
    else:
        out["headers"] = table.get("headers", [])
        out["rows"] = table.get("rows", [])
    return out


def _section_to_json(section: dict, label: str) -> dict:
    """A section as the structured JSON the LLM reads -- no flattening, no truncation."""
    return {
        "heading": label,
        "pages": [section.get("page_start", 0), section.get("page_end", 0)],
        "content": [
            {"role": b.get("role", "paragraph"), "text": b["text"]}
            for b in section.get("blocks", [])
            if b.get("role") not in ("page_header", "page_footer") and b.get("text")
        ],
        "tables": [_table_to_json(t) for t in section.get("tables", [])],
        "figures": [f["caption"] for f in section.get("figures", []) if f.get("caption")],
    }


def _render_section(section: dict, label: str) -> list[str]:
    return [json.dumps(_section_to_json(section, label), ensure_ascii=False)]


def build_extraction_prompt(group: dict) -> str:
    parts = []
    for section in group["sections"]:
        parts.extend(_render_section(section, section["heading"]))
    return "\n".join(parts)


# The discussion converges at the end, so the transcript is trimmed from the front.
_TRANSCRIPT_CHAR_BUDGET = 8000


def build_structured_extraction_prompt(group: dict, transcript: str) -> str:
    """Sections labelled by position, so a section is addressed by index in the output."""
    parts = []
    for index, section in enumerate(group["sections"]):
        parts.extend(_render_section(section, f"[section_index: {index}] {section['heading']}"))
    sources = "\n".join(parts)

    return (
        f"## Source sections\n\n{sources}\n\n"
        f"## Extraction discussion\n\n{transcript[-_TRANSCRIPT_CHAR_BUDGET:]}\n\n"
        "Emit one entry per section above, echoing its section_index exactly as given."
    )
