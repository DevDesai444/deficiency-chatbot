from __future__ import annotations

import asyncio
import json

from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from json_repair import repair_json

from agents.detection.agent import make_flaw_agent, make_flaw_moderator
from agents.detection.classifier import select_flaw_types
from agents.event_bus import emit_sync
from config import get_settings
from llm.client import chat_completion
from llm.prompts import FINDING_EXTRACTOR, SELECTOR_PROMPT
from llm.structured import _extract_json_blob
from retrieval.knowledge_base import get_deficiencies_by_type
from schemas.documents import CTDSection, IntermediateReport
from schemas.flaws import FlawCategory, FlawFinding, FlawReport, Severity

_MODEL_INFO = {
    "vision": False,
    "function_calling": False,
    "json_output": True,
    "family": "unknown",
}

_MAX_TURNS_BACKSTOP = 30


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


def _find_balanced_array(text: str) -> str:
    """Return the first bracket-balanced ``[...]`` span in ``text``.

    Walks the string tracking nesting depth so we do not fall for prose that
    contains a second bracket pair (``[{...}]. See also: [refs]``). Respects
    string literals so brackets inside a JSON string do not throw off the
    counter. Returns ``""`` when no balanced span is found.
    """
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:i + 1]
    return ""


def _extract_json_array(response: str) -> str:
    """Prefer the first bracket-balanced JSON array in ``response``.

    Falls back to :func:`_extract_json_blob` when no balanced array is present.
    ``_extract_json_blob`` tries ``{}`` before ``[]`` and uses greedy
    ``find``/``rfind``, so prose like ``Findings: [{...}]. See also: [refs]``
    would either yield the inner object or swallow the trailing bracket pair.
    """
    if not response:
        return ""

    stripped = response.strip()

    # If wrapped in a markdown fence, defer to the shared blob extractor first —
    # it handles language tags and closing fences.
    if "```" in stripped:
        blob = _extract_json_blob(stripped)
        balanced = _find_balanced_array(blob)
        if balanced:
            return balanced
        if blob.startswith("["):
            return blob
        return blob

    balanced = _find_balanced_array(stripped)
    if balanced:
        return balanced

    return _extract_json_blob(stripped)


def _extract_structured_findings(
    consensus_summary: str,
    document_section: CTDSection,
) -> list[FlawFinding]:
    """Post-chat step: extract structured FlawFinding objects from consensus."""
    s = get_settings()
    categories_str = ", ".join(c.value for c in FlawCategory)

    response = chat_completion(
        messages=[
            {
                "role": "system",
                "content": FINDING_EXTRACTOR.format(categories=categories_str),
            },
            {"role": "user", "content": consensus_summary},
        ],
        model=s.moderator_model,
        max_tokens=2000,
    )

    extracted = _extract_json_array(response)
    if not extracted:
        return []
    try:
        raw_findings = json.loads(extracted)
    except json.JSONDecodeError:
        try:
            repaired = repair_json(extracted)
            raw_findings = json.loads(repaired) if isinstance(repaired, str) else repaired
        except Exception:
            return []
    if not isinstance(raw_findings, list):
        return []

    findings = []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue

        category_str = raw.get("category", "general_cmc")
        try:
            category = FlawCategory(category_str)
        except ValueError:
            category = FlawCategory.GENERAL_CMC

        section_str = raw.get("section_id", "unknown")
        try:
            section = CTDSection(section_str)
        except ValueError:
            section = document_section

        severity_str = raw.get("severity", "medium")
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.MEDIUM

        findings.append(FlawFinding(
            category=category,
            section_id=section,
            description=raw.get("description", ""),
            evidence=raw.get("evidence", ""),
            severity=severity,
        ))

    return findings


async def _run_flaw_detection_async(
    intermediate_report: IntermediateReport,
    document_section: CTDSection,
    job_id: str,
) -> FlawReport:
    s = get_settings()
    agent_client = _make_model_client()
    selector_client = _make_model_client(s.moderator_model)

    flaw_types = select_flaw_types(intermediate_report)
    emit_sync(
        job_id, "detection", "agent_spawned", "",
        f"LLM selected {len(flaw_types)} flaw categories: {', '.join(flaw_types)}",
    )

    agents = []
    for flaw_type in flaw_types:
        agent = make_flaw_agent(flaw_type, agent_client)
        agents.append((agent, flaw_type))
        emit_sync(job_id, "detection", "agent_spawned", agent.name, f"Checking for {flaw_type} issues")

    moderator = make_flaw_moderator(selector_client)
    emit_sync(job_id, "detection", "agent_spawned", moderator.name, "Moderating consensus (70B)")

    all_agents = [a for a, _ in agents] + [moderator]
    flaw_agent_names = {a.name for a, _ in agents}

    def candidate_func(messages):
        spoken = set()
        for msg in messages:
            source = getattr(msg, "source", "")
            if source in flaw_agent_names:
                spoken.add(source)

        not_yet_reported = [n for n in flaw_agent_names if n not in spoken]
        if not_yet_reported:
            return not_yet_reported

        last_speaker = getattr(messages[-1], "source", "") if messages else ""
        if last_speaker != moderator.name:
            return [moderator.name]

        return list(flaw_agent_names)

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
        "The moderator will drive the consensus discussion."
    )

    termination = TextMentionTermination("CONSENSUS_REACHED")
    team = SelectorGroupChat(
        participants=all_agents,
        model_client=selector_client,
        termination_condition=termination,
        max_turns=_MAX_TURNS_BACKSTOP,
        selector_prompt=SELECTOR_PROMPT,
        candidate_func=candidate_func,
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

    findings = _extract_structured_findings(consensus_summary, document_section)

    emit_sync(
        job_id, "detection", "consensus_reached", "",
        f"{len(findings)} findings confirmed after {message_count} messages",
    )
    emit_sync(job_id, "detection", "layer_complete", "", consensus_summary[:200])

    return FlawReport(
        flaws_found=len(findings) > 0,
        findings=findings,
        consensus_summary=consensus_summary,
        agents_participated=[a.name for a, _ in agents],
        consensus_rounds=message_count,
    )


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
