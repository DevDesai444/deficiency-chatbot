"""The isolated, write-disabled single verifier call (VERIFY-01).

One panel member judges one candidate against re-opened FULL context (source + rule), returning
``VERDICT`` (KEEP | DOWNGRADE) or the literal string ``"KEEP"``. Composes the Phase-6 reliability
stack verbatim: ``verifier_system_prompt`` (family-aware, invariant-aligned) + ``chat_completion_tools``
(on-prem guard + guided decode + <function=> 400 recovery) + ``coerce_and_validate`` (XOR contract;
never fabricates a verdict).

RECALL INVARIANT (β law, enforced in CODE not prompt):
  - finish_reason in {"tool_parse_error","error"} or no tool_calls  -> "KEEP" (unreadable => KEEP)
  - coerce_and_validate returns ParseFailed after one bounded corrective retry -> "KEEP"
  - unsure is the model's job (the prompt defaults to KEEP); an off-value verdict token is NEVER
    coerced (reliability.strict_coerce) -> ParseFailed -> "KEEP"
A verdict is NEVER fabricated here; "KEEP" the string is returned so a caller can distinguish
"verifier could not be read" from a parsed VERDICT(verdict=KEEP).

DECORRELATION / write-disabled (VERIFY-03 / VERIFY-01):
  - the user message contains ONLY the claim + re-opened source_text + rule_text — never the
    producer's chain-of-thought. ``render_candidate`` deliberately reads only the claim summary.
  - the tool list handed to the model is READ-ONLY (get_section + read_guideline). An in-code
    assertion (not a prompt instruction) rejects any write/emit tool leaking into the list.

ON-PREM: every real call path routes through ``chat_completion_tools`` -> ``get_client`` (the
on-prem allow-list guard). ``completion`` defaults to ``chat_completion_tools`` so tests can inject
a scripted fleet double without touching that guard.
"""
from __future__ import annotations

import json
from typing import Callable, Literal

import structlog

from config import get_settings
from llm.client import chat_completion_tools
from llm.reliability import coerce_and_validate, format_field_level_reprompt_from_json
from llm.structured import build_tool_schema
from llm.verifier_prompt import verifier_system_prompt
from schemas.llm import VERDICT

# Import the read-only tool arg models + descriptions the review layer already validates against,
# so the verifier's tool schemas are derived from the SAME pydantic models — never hand-rolled.
from agents.review.registry import (
    GET_SECTION_DESCRIPTION,
    READ_GUIDELINE_DESCRIPTION,
    GetSectionArgs,
    ReadGuidelineArgs,
)

log = structlog.get_logger()

# Tool-name markers that must NEVER appear in a verifier's tool list. The verifier is write-disabled:
# it may only re-open evidence (get_section / read_guideline), never emit / write / mutate a finding.
_WRITE_TOOL_MARKERS = ("emit", "write", "mutate", "submit_finding")


def read_only_verifier_tools() -> list[dict]:
    """The ONLY tools a verifier is offered: get_section + read_guideline (read-only re-open).

    Derived via ``build_tool_schema`` from the same arg models the review registry validates, so the
    verifier and the review loop agree on the schema. An in-code guard (not a prompt) asserts no
    write/emit tool is present — the write-disabled invariant is a code gate.
    """
    tools = [
        build_tool_schema(GetSectionArgs, "get_section", GET_SECTION_DESCRIPTION),
        build_tool_schema(ReadGuidelineArgs, "read_guideline", READ_GUIDELINE_DESCRIPTION),
    ]
    _assert_no_write_tool(tools)
    return tools


def _assert_no_write_tool(tools: list[dict]) -> None:
    """Fail loud if any offered tool name looks like a write/emit tool (code gate, not prompt)."""
    for t in tools:
        name = ((t.get("function") or {}).get("name") or "")
        if any(mark in name for mark in _WRITE_TOOL_MARKERS):
            raise AssertionError(f"verifier tool list must be read-only; found write/emit tool: {name!r}")


# The verifier's VERDICT OUTPUT channel. The write-disabled invariant forbids mutating the corpus /
# findings (emit_finding), NOT recording a judgment — so a "submit_verdict" tool is allowed (and the
# name matches the offline ScriptedFleetClient fixture + passes the write-tool guard, which blocks
# emit_/write/mutate/submit_finding). This is REQUIRED, not optional: weak open-weights models
# (Llama/Qwen) do NOT reliably emit a VERDICT via guided-JSON where the endpoint lacks guided
# support — Llama answers in free text ("VERDICT: DOWNGRADE") with no structured grounding_span, so
# the consensus gate (which needs a grounded downgrade) never fires. Offering the tool makes both
# families emit a structured VERDICT incl. grounding_span (proven by the Phase-6 D-06 probe). Without
# it every real downgrade was discarded as "unreadable => KEEP" (the live-checkpoint no-op bug).
SUBMIT_VERDICT_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "submit_verdict",
        "description": "Record the VERDICT (KEEP or DOWNGRADE) on the candidate deficiency, with a "
        "verbatim grounding_span copied from the provided source.",
        "parameters": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["KEEP", "DOWNGRADE"]},
                "confidence": {"type": "number"},
                "rationale": {"type": "string"},
                "grounding_span": {"type": "string"},
            },
            "required": ["verdict", "confidence", "rationale", "grounding_span"],
            "additionalProperties": False,
        },
    },
}


def _submit_verdict_args(turn) -> str | None:
    """Return the JSON-args string of the verifier's ``submit_verdict`` tool call, or None.

    None (=> KEEP, unreadable) when the turn errored, carried no tool calls, or the model called a
    read tool but never submitted a verdict. When exactly one tool call is present we accept it even
    if the name differs (guided/legacy paths), so a scripted single-call fixture still parses.
    """
    if turn.finish_reason in ("tool_parse_error", "error"):
        return None
    calls = turn.tool_calls or []
    for tc in calls:
        if getattr(getattr(tc, "function", None), "name", None) == "submit_verdict":
            return tc.function.arguments
    if len(calls) == 1:  # single-call fixture / guided path with a differently-named call
        return calls[0].function.arguments
    return None


def render_candidate(candidate, source_text: str, rule_text: str) -> str:
    """Render ONLY claim + re-opened source + rule for the verifier's user message.

    Deliberately reads the claim summary (title/evidence/anchor) and NEVER ``candidate.detail`` or
    any producer chain-of-thought field — decorrelation-in-code (VERIFY-03). The caller passes
    already-re-opened FULL ``source_text`` + ``rule_text`` (the orchestrator does the
    get_section/read_guideline; the verifier does not re-open here).
    """
    claim = getattr(candidate, "title", "") or ""
    evidence = getattr(candidate, "evidence", "") or ""
    claim_block = claim if not evidence else f"{claim}\nCited evidence: {evidence}"
    return (
        "Judge this candidate deficiency against the re-opened source and rule below.\n\n"
        f"CANDIDATE CLAIM:\n{claim_block}\n\n"
        f"RE-OPENED SOURCE:\n{source_text}\n\n"
        f"CITED RULE:\n{rule_text}\n\n"
        "Return your verdict (KEEP or DOWNGRADE) with a verbatim grounding_span from the source."
    )


def verify_once(
    candidate,
    source_text: str,
    rule_text: str,
    model: str,
    completion: Callable = chat_completion_tools,
) -> VERDICT | Literal["KEEP"]:
    """One isolated verifier call. Returns a parsed ``VERDICT`` (with ``.model`` set) or ``"KEEP"``.

    See module docstring for the recall invariant. ``completion`` defaults to
    ``chat_completion_tools`` so a test can inject a scripted fleet double; the real path always
    routes through the on-prem guard.
    """
    system = verifier_system_prompt(thinking_mode="off", model=model)
    # ONLY the submit_verdict OUTPUT channel is offered. The evidence is already re-opened in FULL by
    # the orchestrator (_reopen_full_source/_reopen_full_rule) and rendered below, so the verifier
    # judges pre-rendered context and emits a verdict in one shot — this IS the write-disabled,
    # source-re-opened contract (the re-open happens in the orchestrator, VERIFY-01). Offering the
    # read tools (get_section/read_guideline) here is actively harmful: with no tool loop to service
    # them, a reasoning model (Qwen3-next) calls get_section instead of submitting a verdict and its
    # vote is lost as "unreadable => KEEP" — the 3rd consensus vote that never landed. The Phase-6
    # D-06 probe (verdict-tool only) got 100% conformance from every fleet model.
    tools = [SUBMIT_VERDICT_TOOL]
    _ = read_only_verifier_tools  # retained (write-disabled guard + import); not offered single-shot
    messages = [
        {"role": "system", "content": system},
        # ONLY claim + re-opened source + rule. NEVER the producer's chain-of-thought.
        {"role": "user", "content": render_candidate(candidate, source_text, rule_text)},
    ]

    turn = completion(
        messages,
        tools,
        model=model,
        temperature=0.0,
        guided_model_cls=VERDICT,
    )

    # Invariant: an unreadable turn (no submit_verdict) => KEEP (never fabricate a verdict).
    args_str = _submit_verdict_args(turn)
    if args_str is None:
        log.info("verifier_unreadable_keep", model=model, finish_reason=turn.finish_reason)
        return "KEEP"

    try:
        raw_args = json.loads(args_str)
    except Exception as exc:  # malformed JSON in the tool args => KEEP
        log.info("verifier_bad_tool_args_keep", model=model, error=str(exc)[:200])
        return "KEEP"

    verdict, failed = coerce_and_validate(
        raw_args, VERDICT, retries_remaining=get_settings().verifier_max_repair_calls
    )

    if failed is not None:
        # ONE bounded corrective re-prompt using the field-level reprompt message, then re-coerce.
        reprompt = format_field_level_reprompt_from_json(failed.validation_error or None, VERDICT)
        messages.append({"role": "user", "content": reprompt})
        turn2 = completion(
            messages,
            tools,
            model=model,
            temperature=0.0,
            guided_model_cls=VERDICT,
        )
        args_str2 = _submit_verdict_args(turn2)
        if args_str2 is None:
            return "KEEP"
        try:
            raw_args2 = json.loads(args_str2)
        except Exception:
            return "KEEP"
        verdict, failed2 = coerce_and_validate(raw_args2, VERDICT, retries_remaining=0)
        if failed2 is not None or verdict is None:
            log.info("verifier_parse_fail_keep", model=model)
            return "KEEP"

    if verdict is None:  # defensive: XOR contract guarantees this cannot happen, but never fabricate
        return "KEEP"

    verdict.model = model
    return verdict
