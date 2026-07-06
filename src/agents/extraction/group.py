from __future__ import annotations

import asyncio

from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

from agents.event_bus import emit_sync
from agents.extraction.agent import (
    build_extraction_prompt,
    make_extraction_agent,
    make_extraction_moderator,
)
from config import get_settings
from schemas.documents import (
    ChunkGroup,
    IntermediateReport,
    SectionSummary,
)

_MODEL_INFO = {
    "vision": False,
    "function_calling": False,
    "json_output": True,
    "family": "unknown",
}

_MAX_TURNS_BACKSTOP = 30

# Llama 3.1 context = 131,072 tokens. Reserve ~30k for system prompts, output, and
# accumulated conversation. Budget = 100k tokens ≈ 400k chars input.
_EXTRACTION_PROMPT_CHAR_BUDGET = 400_000


def _make_model_client(model: str | None = None) -> OpenAIChatCompletionClient:
    s = get_settings()
    resolved = model or s.resolved_llm_model
    if s.is_databricks:
        return OpenAIChatCompletionClient(
            model=resolved,
            base_url=f"{s.databricks_host}/serving-endpoints",
            api_key=s.databricks_token,
            model_info=_MODEL_INFO,
        )
    return OpenAIChatCompletionClient(
        model=resolved,
        base_url=s.llm_base_url,
        api_key="not-needed",
        model_info=_MODEL_INFO,
    )


async def _run_extraction_async(
    groups: list[ChunkGroup],
    document_name: str,
    document_type: str,
    job_id: str,
) -> IntermediateReport:
    model_client = _make_model_client()

    agents = []
    for group in groups:
        agent = make_extraction_agent(group, model_client)
        agents.append((agent, group))
        emit_sync(job_id, "extraction", "agent_spawned", agent.name, f"Analyzing {len(group.sections)} sections")

    moderator = make_extraction_moderator(model_client)
    emit_sync(job_id, "extraction", "agent_spawned", moderator.name, "Moderating extraction")

    all_agents = [a for a, _ in agents] + [moderator]

    termination = TextMentionTermination("EXTRACTION_COMPLETE")
    team = RoundRobinGroupChat(
        participants=all_agents,
        termination_condition=termination,
        max_turns=_MAX_TURNS_BACKSTOP,
    )

    initial_prompts = []
    for agent, group in agents:
        prompt = build_extraction_prompt(group)
        initial_prompts.append(f"[{agent.name}] Please analyze these sections:\n\n{prompt}")

    combined_prompt = (
        f"Document: {document_name} (Type: {document_type})\n\n"
        "Each extraction agent should analyze their assigned sections and report findings.\n"
        "Review other agents' findings for cross-section dependencies.\n"
        "The moderator will consolidate when all agents have converged.\n\n"
        + "\n\n---\n\n".join(initial_prompts)
    )

    result = await team.run(task=combined_prompt)

    consensus_notes = ""
    msg_count = 0
    for msg in result.messages:
        sender = getattr(msg, "source", "")
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content:
            emit_sync(job_id, "extraction", "agent_message", sender, content[:200])
            msg_count += 1
            if sender == moderator.name:
                consensus_notes = content

    summaries: list[SectionSummary] = []
    for group in groups:
        for section in group.sections:
            summaries.append(
                SectionSummary(
                    section_id=section.section_id,
                    summary=section.heading,
                )
            )

    emit_sync(
        job_id, "extraction", "layer_complete", "",
        f"Extracted {len(summaries)} sections in {msg_count} messages",
    )

    return IntermediateReport(
        document_name=document_name,
        document_type=document_type,
        sections=summaries,
        findings=[],
        consensus_notes=consensus_notes,
    )


def run_extraction(
    groups: list[ChunkGroup],
    document_name: str,
    document_type: str,
    job_id: str,
) -> IntermediateReport:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                _run_extraction_async(groups, document_name, document_type, job_id),
            )
            return future.result()

    return asyncio.run(
        _run_extraction_async(groups, document_name, document_type, job_id)
    )
