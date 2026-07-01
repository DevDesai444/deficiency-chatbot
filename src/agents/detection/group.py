from __future__ import annotations

import json

from autogen import GroupChat, GroupChatManager

from agents.detection.agent import make_flaw_agent, make_flaw_moderator
from agents.detection.flaw_types import get_relevant_flaw_types
from agents.event_bus import emit_sync
from config import get_settings
from retrieval.knowledge_base import get_deficiencies_by_type
from schemas.documents import CTDSection, IntermediateReport
from schemas.flaws import FlawFinding, FlawReport


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


def _build_context_for_flaw_type(flaw_type: str) -> str:
    """Pull historical deficiencies as context for this flaw type."""
    historical = get_deficiencies_by_type(flaw_type, limit=5)
    if not historical:
        return ""

    lines = [f"\n--- Historical {flaw_type} deficiencies (for reference) ---"]
    for h in historical:
        text = h.get("deficiency_text", "")[:300]
        product = h.get("product_name", "unknown")
        lines.append(f"- [{product}] {text}")
    return "\n".join(lines)


def run_flaw_detection(
    intermediate_report: IntermediateReport,
    document_section: CTDSection,
    job_id: str,
) -> FlawReport:
    config = _llm_config()
    s = get_settings()

    flaw_types = get_relevant_flaw_types(document_section)
    emit_sync(
        job_id, "detection", "agent_spawned", "",
        f"Routing {len(flaw_types)} flaw agents for {document_section.value}",
    )

    agents = []
    for flaw_type in flaw_types:
        agent = make_flaw_agent(flaw_type, config)
        agents.append((agent, flaw_type))
        emit_sync(job_id, "detection", "agent_spawned", agent.name, f"Checking for {flaw_type} issues")

    moderator = make_flaw_moderator(config)
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

    groupchat = GroupChat(
        agents=all_agents,
        messages=[],
        max_round=len(agents) * 2 + 3,
        speaker_selection_method="round_robin",
    )
    manager = GroupChatManager(groupchat=groupchat, llm_config=config)

    emit_sync(job_id, "detection", "consensus_start", "", "Starting flaw detection deliberation")

    agents[0][0].initiate_chat(
        manager,
        message=prompt,
        silent=True,
    )

    for msg in groupchat.messages:
        sender = msg.get("name", "")
        content = msg.get("content", "")
        if content:
            emit_sync(job_id, "detection", "agent_message", sender, content[:200])

    findings: list[FlawFinding] = []
    consensus_summary = ""
    moderator_messages = [
        msg.get("content", "") for msg in groupchat.messages
        if msg.get("name") == moderator.name and msg.get("content")
    ]
    if moderator_messages:
        consensus_summary = moderator_messages[-1]

    flaws_found = bool(findings) or _moderator_found_flaws(consensus_summary)

    consensus_rounds = min(len(groupchat.messages), s.max_consensus_rounds)
    emit_sync(
        job_id, "detection", "consensus_reached", "",
        f"{'Flaws detected' if flaws_found else 'No flaws found'} after {consensus_rounds} rounds",
    )
    emit_sync(job_id, "detection", "layer_complete", "", consensus_summary[:200])

    return FlawReport(
        flaws_found=flaws_found,
        findings=findings,
        consensus_summary=consensus_summary,
        agents_participated=[a.name for a, _ in agents],
        consensus_rounds=consensus_rounds,
    )


def _moderator_found_flaws(summary: str) -> bool:
    """Heuristic: check if the moderator's summary indicates flaws were found."""
    lower = summary.lower()
    no_flaw_signals = ["no deficien", "no issues", "no flaws", "appears clean", "no significant"]
    return not any(signal in lower for signal in no_flaw_signals)
