"""Offline test doubles + shared fixtures for the Phase-7 multi-agent verifier (Wave 0).

This conftest stands up the MODEL boundary only — it never imports src/verify/ (which does not
exist until Waves 1-3). The consensus / decorrelation / invariant tests inject `ScriptedFleetClient`
(a deterministic stand-in for `llm.client.chat_completion_tools`, keyed by MODEL id) so the whole
verifier suite runs offline and byte-deterministic, with no live fleet call and the on-prem guard
untouched (T-07-02).

Mirrors the Phase-3 `tests/agents/review/conftest.ScriptedChatClient` pattern: deep-copies every
`messages` list it is shown so a decorrelation test can assert exactly what each verifier saw even
after the loop mutates its list. The per-model `seen_messages_by_model` is the decorrelation seam.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from itertools import count
from types import SimpleNamespace
from typing import Any

import pytest

from ingest.anchors import mint_span
from ingest.normalize import normalize
from llm.client import ChatTurn
from schemas.documents import NormalizedText, SpanID
from schemas.faults import CoverageAbsenceAnchor, Fault

_CALL_COUNTER = count(1)


# --------------------------------------------------------------------------------------------------
# The fleet double — deterministic stand-in for chat_completion_tools, keyed by MODEL.
# --------------------------------------------------------------------------------------------------
@dataclass
class ScriptedFleetClient:
    """Deterministic stand-in for `llm.client.chat_completion_tools`, keyed by MODEL endpoint id.

    `script` maps a model endpoint id -> the ordered sequence of `ChatTurn`s that model returns.
    `__call__(messages, tools, *, model, **kw)` records `copy.deepcopy(messages)` under
    `seen_messages_by_model[model]` (so message assertions survive later mutation — the same
    deepcopy discipline as ScriptedChatClient) and returns the next scripted turn for that model,
    clamped to the last entry once the script is exhausted.

    `seen_tools_by_model` mirrors the same for the tool list, so a write-disabled test can assert
    the exact tools each verifier was offered.
    """

    script: dict[str, list[ChatTurn]] = field(default_factory=dict)
    seen_messages_by_model: dict[str, list[list[dict]]] = field(default_factory=dict)
    seen_tools_by_model: dict[str, list[list[dict]]] = field(default_factory=dict)

    def __call__(self, messages: list[dict], tools: list[dict], *, model: str, **kw: Any) -> ChatTurn:
        self.seen_messages_by_model.setdefault(model, []).append(copy.deepcopy(messages))
        self.seen_tools_by_model.setdefault(model, []).append(copy.deepcopy(tools))
        turns = self.script.get(model, [])
        if not turns:
            raise KeyError(f"ScriptedFleetClient has no script for model {model!r}")
        idx = len(self.seen_messages_by_model[model]) - 1
        return turns[min(idx, len(turns) - 1)]


# --------------------------------------------------------------------------------------------------
# ChatTurn builders — mirror the tool-call shape the real verifier parses.
# --------------------------------------------------------------------------------------------------
def make_tool_call(name: str, args: dict) -> object:
    """Return the subset of OpenAI's tool-call object shape a verifier consumes.

    Reused verbatim from tests/agents/review/conftest.make_tool_call so both suites agree on the
    `.function.name` / `.function.arguments` (JSON string) contract.
    """
    return SimpleNamespace(
        id=f"call_{next(_CALL_COUNTER):03d}",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args, sort_keys=True)),
    )


def make_verdict_turn(
    verdict: str,
    grounding_span: str,
    *,
    confidence: float = 0.5,
    rationale: str = "scripted verdict",
) -> ChatTurn:
    """A ChatTurn carrying one `submit_verdict` tool call with a VERDICT-shaped payload.

    VERDICT (src/schemas/llm.py) requires verdict + confidence + rationale + grounding_span, so the
    scripted payload carries all four; `verdict` is passed through verbatim (KEEP/DOWNGRADE — or an
    off-value a ParseFailed test can drive). finish_reason="stop".
    """
    tool_call = make_tool_call(
        "submit_verdict",
        {
            "verdict": verdict,
            "confidence": confidence,
            "rationale": rationale,
            "grounding_span": grounding_span,
        },
    )
    return ChatTurn(
        content="",
        finish_reason="stop",
        tool_calls=[tool_call],
        raw_message={
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            ],
        },
        usage_present=True,
    )


def make_parse_fail_turn() -> ChatTurn:
    """A ChatTurn that represents an unparseable tool call (finish_reason='tool_parse_error').

    VERIFY-01 invariant: a parse-failed verdict must resolve to KEEP, never a silent drop.
    """
    return ChatTurn(
        content="",
        finish_reason="tool_parse_error",
        tool_calls=[],
        raw_message={"role": "assistant", "content": ""},
        usage_present=True,
    )


# --------------------------------------------------------------------------------------------------
# Byte-exact grounding substrate — a real NormalizedText + minted SpanID pair.
# Built via the production `normalize()` so open_span round-trips against a genuine offset_map
# (no hand-rolled fake), keeping grounding-re-resolution tests honest.
# --------------------------------------------------------------------------------------------------
def make_normalized_text(text: str, *, serializer_version: str = "test-sv") -> NormalizedText:
    """A real NormalizedText over `text` via the production normalizer (byte-exact substrate)."""
    return normalize(text, serializer_version=serializer_version)


def mint_span_over(nt: NormalizedText, substring: str, doc_id: str = "docA") -> SpanID:
    """Mint a content-addressed SpanID over the first occurrence of `substring` in `nt.canonical`.

    Raises if the substring is absent, so a test never mints a span that cannot re-open.
    """
    start = nt.canonical.find(substring)
    if start < 0:
        raise ValueError(f"substring {substring!r} not found in canonical text")
    end = start + len(substring)
    return mint_span(nt.canonical, start, end, doc_id, nt.normalizer_version)


@pytest.fixture
def grounding_substrate() -> tuple[NormalizedText, SpanID, str]:
    """(NormalizedText, SpanID, grounding_span) triple for grounding-re-resolution tests.

    The grounding_span is a verbatim substring of the span's canonical text, so a correct
    re-resolution is grounded True and a tampered stream / absent substring is grounded False.
    """
    nt = make_normalized_text(
        "The stability study reports a total impurity of 0.14 percent at 6 months."
    )
    span = mint_span_over(nt, "total impurity of 0.14 percent")
    return nt, span, "0.14 percent"


# --------------------------------------------------------------------------------------------------
# Candidate builders — Faults the verifier verifies + consolidates.
# Described by STRUCTURE (leg/anchor shape), never by any corpus value (T-07-01 / RECALL-05 guard).
# --------------------------------------------------------------------------------------------------
def deterministic_candidate() -> Fault:
    """A STRUCTURAL deterministic-leg candidate: has a submission_span_id, full tier."""
    nt = make_normalized_text("Total is 0.14 percent though the largest single value is 0.15.")
    span = mint_span_over(nt, "Total is 0.14 percent")
    return Fault(
        title="Aggregate total disagrees with tabulated rows",
        leg_tag="STRUCTURAL",
        submission_span_id=span,
        dedup_key="docA:sec1:null",
        confidence=0.6,
        confidence_tier="full",
        source="oracle:aggregate_recompute",
    )


def absence_candidate() -> Fault:
    """An ABSENCE-family candidate: no submission_span_id, an absence_anchor with a claim span."""
    nt = make_normalized_text("The submission asserts full method validation was performed.")
    claim_span = mint_span_over(nt, "full method validation was performed")
    return Fault(
        title="Required stability data appears absent",
        leg_tag="ABSENCE",
        submission_span_id=None,
        absence_anchor=CoverageAbsenceAnchor(
            requirement_id="req-structural-family-x",
            threshold=0.4,
            claim_span_id=claim_span,
        ),
        dedup_key="docA:sec2:req-x",
        confidence=0.5,
        confidence_tier="full",
        source="checklist:absence_enumeration",
    )


def tail_candidate() -> Fault:
    """An interpretive-tail candidate produced by a reviewer of the qwen family.

    `source` carries the producer-family marker "qwen" that a later panel-composition test reads to
    exclude the qwen panel (VERIFY-03 decorrelation).
    """
    nt = make_normalized_text("The linearity r-squared of 0.991 is characterized as acceptable.")
    span = mint_span_over(nt, "linearity r-squared of 0.991")
    return Fault(
        title="Linearity acceptance criterion may be interpretive",
        leg_tag=None,
        submission_span_id=span,
        dedup_key="docA:sec3:null",
        confidence=0.35,
        confidence_tier="full",
        source="reviewer:qwen:3.2.P.4.3",
    )


def labeled_fp_candidate() -> Fault:
    """A KNOWN-FALSE-POSITIVE candidate for the Gap-1 report-assembly filter test.

    STRUCTURE: a structural "aggregate mismatch" whose recompute actually AGREES — a genuine
    non-fault the verifier should DOWNGRADE. Its evidence anchor is minted to NOT collide with any
    ground-truth anchor, so a DOWNGRADEd FP must NOT be scored as an FP (Plan 03/04).
    """
    nt = make_normalized_text("Total is 0.30 percent and the two rows are 0.15 and 0.15.")
    span = mint_span_over(nt, "Total is 0.30 percent")
    return Fault(
        title="Claimed aggregate mismatch that in fact reconciles",
        leg_tag="STRUCTURAL",
        submission_span_id=span,
        dedup_key="docA:secFP:null",
        confidence=0.55,
        confidence_tier="full",
        source="oracle:aggregate_recompute",
    )


def labeled_tp_candidate() -> Fault:
    """A KNOWN-TRUE-POSITIVE candidate for the Gap-1 zero-TP-loss test.

    STRUCTURE: a real aggregate mismatch whose evidence anchor is minted TO collide with a
    ground-truth anchor. A DOWNGRADE of it must STILL be counted as a matched TP (no TP loss).
    """
    nt = make_normalized_text("Total is 0.14 percent although the largest single value is 0.15.")
    span = mint_span_over(nt, "Total is 0.14 percent")
    return Fault(
        title="Aggregate total below the largest tabulated single value",
        leg_tag="STRUCTURAL",
        submission_span_id=span,
        dedup_key="docA:secTP:null",
        confidence=0.6,
        confidence_tier="full",
        source="oracle:aggregate_recompute",
    )


@pytest.fixture
def scripted_fleet() -> ScriptedFleetClient:
    """An empty ScriptedFleetClient a test populates with a per-model script."""
    return ScriptedFleetClient()
