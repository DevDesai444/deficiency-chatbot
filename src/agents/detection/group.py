from __future__ import annotations

import asyncio
import json

from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient

from agents.detection.agent import make_flaw_agent, make_flaw_moderator
from agents.detection.flaw_types import get_relevant_flaw_types
from agents.event_bus import emit_sync
from config import get_settings
from retrieval.knowledge_base import get_deficiencies_by_type
from schemas.documents import CTDSection, IntermediateReport
from schemas.flaws import FlawReport


def _make_model_client() -> OpenAIChatCompletionClient:
    s = get_settings()
    if s.is_databricks:
        return OpenAIChatCompletionClient(
            model=s.resolved_llm_model,
            base_url=f"{s.databricks_host}/serving-endpoints",
            api_key=s.databricks_token,
        )
    return OpenAIChatCompletionClient(
        model=s.resolved_llm_model,
        base_url=s.llm_base_url,
        api_key="not-needed",
    )


def _build_context_for_flaw_type(flaw_type: str) -> str:
    historical = get_deficiencies_by_type(flaw_type, limit=5)
    if not historical:
        return ""

    lines = [f"\n--- Historical {flaw_type} deficiencies (for reference) ---"]
    for h in historical:
        text = h.get("deficiency_text", "")[:300]
        product = h.get("product_name", "unknown")
        lines.append(f"- [{product}] {text}")
    return "\n".join(lines)


async def _run_flaw_detection_async(
    intermediate_report: IntermediateReport,
    document_section: CTDSection,
    job_id: str,
) -> FlawReport:
    model_client = _make_model_client()
    s = get_settings()

    flaw_types = get_relevant_flaw_types(document_section)
    emit_sync(
        job_id, "detection", "agent_spawned", "",
        f"Routing {len(flaw_types)} flaw agents for {document_section.value}",
    )

    agents = []
    for flaw_type in flaw_types:
        agent = make_flaw_agent(flaw_type, model_client)
        agents.append((agent, flaw_type))
        emit_sync(job_id, "detection", "agent_spawned", agent.name, f"Checking for {flaw_type} issues")

    moderator = make_flaw_moderator(model_client)
    emit_sync(job_id, "detection", "agent_spawned", moderator.name, "Moderating consensus")

    all_agents = [a for a, _ in agents] + [moderator]

    report_text = json.dumps(intermediate_report.model_dump(), indent=2, default=str)

    context_blocks = []
    for _, flaw_type in agents:
        ctx = _build_context_for_flaw_type(flaw_type)
        if ctx:
            context_blocks.append(ctx)

    prompt = (
        f"## Intermediate Extraction Report\n\n{report_text}\n\n"
        + "\n".join(context_blocks)
        + "\n\nEach flaw detection agent: review this report for deficiencies in your domain. "
        "If you find issues, state them clearly with evidence. If not, say so explicitly.\n"
        "Then the moderator will run a consensus discussion."
    )

    termination = MaxMessageTermination(max_messages=len(agents) * 2 + 3)
    team = RoundRobinGroupChat(
        participants=all_agents,
        termination_condition=termination,
    )

    emit_sync(job_id, "detection", "consensus_start", "", "Starting flaw detection deliberation")

    result = await team.run(task=prompt)

    message_count = 0
    consensus_summary = ""
    for msg in result.messages:
        sender = getattr(msg, "source", "")
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content:
            emit_sync(job_id, "detection", "agent_message", sender, content[:200])
            message_count += 1
            if sender == moderator.name:
                consensus_summary = content

    flaws_found = _moderator_found_flaws(consensus_summary)
    consensus_rounds = min(message_count, s.max_consensus_rounds)

    emit_sync(
        job_id, "detection", "consensus_reached", "",
        f"{'Flaws detected' if flaws_found else 'No flaws found'} after {consensus_rounds} rounds",
    )
    emit_sync(job_id, "detection", "layer_complete", "", consensus_summary[:200])

    return FlawReport(
        flaws_found=flaws_found,
        findings=[],
        consensus_summary=consensus_summary,
        agents_participated=[a.name for a, _ in agents],
        consensus_rounds=consensus_rounds,
    )


def _moderator_found_flaws(summary: str) -> bool:
    lower = summary.lower()
    no_flaw_signals = ["no deficien", "no issues", "no flaws", "appears clean", "no significant"]
    return not any(signal in lower for signal in no_flaw_signals)


def run_flaw_detection(
    intermediate_report: IntermediateReport,
    document_section: CTDSection,
    job_id: str,
) -> FlawReport:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(
                asyncio.run,
                _run_flaw_detection_async(intermediate_report, document_section, job_id),
            )
            return future.result()

    return asyncio.run(
        _run_flaw_detection_async(intermediate_report, document_section, job_id)
    )
