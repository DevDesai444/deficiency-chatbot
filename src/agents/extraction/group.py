from __future__ import annotations

from autogen import GroupChat, GroupChatManager

from agents.event_bus import emit_sync
from agents.extraction.agent import (
    build_extraction_prompt,
    make_extraction_agent,
    make_extraction_moderator,
)
from config import get_settings
from schemas.documents import (
    ChunkGroup,
    ExtractionFinding,
    IntermediateReport,
    SectionSummary,
)


def _llm_config() -> dict:
    s = get_settings()
    return {
        "config_list": [
            {
                "model": s.llm_model,
                "base_url": s.llm_base_url if not s.is_databricks else f"{s.databricks_host}/serving-endpoints",
                "api_key": s.databricks_token if s.is_databricks else "not-needed",
            }
        ],
        "temperature": s.llm_temperature,
        "cache_seed": None,
    }


def run_extraction(
    groups: list[ChunkGroup],
    document_name: str,
    document_type: str,
    job_id: str,
) -> IntermediateReport:
    config = _llm_config()

    agents = []
    for group in groups:
        agent = make_extraction_agent(group, config)
        agents.append((agent, group))
        emit_sync(job_id, "extraction", "agent_spawned", agent.name, f"Analyzing {len(group.sections)} sections")

    moderator = make_extraction_moderator(config)
    emit_sync(job_id, "extraction", "agent_spawned", moderator.name, "Moderating extraction")

    all_agents = [a for a, _ in agents] + [moderator]

    groupchat = GroupChat(
        agents=all_agents,
        messages=[],
        max_round=len(agents) + 3,
        speaker_selection_method="round_robin",
    )
    manager = GroupChatManager(groupchat=groupchat, llm_config=config)

    initial_prompts = []
    for agent, group in agents:
        prompt = build_extraction_prompt(group)
        initial_prompts.append(f"[{agent.name}] Please analyze these sections:\n\n{prompt}")

    combined_prompt = (
        f"Document: {document_name} (Type: {document_type})\n\n"
        "Each extraction agent should analyze their assigned sections and report findings.\n"
        "Then the moderator should consolidate into a single intermediate report.\n\n"
        + "\n\n---\n\n".join(initial_prompts)
    )

    agents[0][0].initiate_chat(
        manager,
        message=combined_prompt,
        silent=True,
    )

    findings: list[ExtractionFinding] = []
    summaries: list[SectionSummary] = []
    consensus_notes = ""

    for msg in groupchat.messages:
        sender = msg.get("name", "")
        content = msg.get("content", "")

        if content:
            emit_sync(job_id, "extraction", "agent_message", sender, content[:200])

        if sender == moderator.name and content:
            consensus_notes = content

    for group in groups:
        for section in group.sections:
            summaries.append(
                SectionSummary(
                    section_id=section.section_id,
                    summary=section.heading,
                )
            )

    emit_sync(job_id, "extraction", "layer_complete", "", f"Extracted {len(summaries)} sections")

    return IntermediateReport(
        document_name=document_name,
        document_type=document_type,
        sections=summaries,
        findings=findings,
        consensus_notes=consensus_notes,
    )
