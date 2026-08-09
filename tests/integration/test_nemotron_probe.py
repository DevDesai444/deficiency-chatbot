"""Integration test shells for MODEL-02 — Nemotron Super 49B pre-wiring probes.

ALL tests require:
  1. The Nemotron endpoint to be deployed and reachable (D-20 gate)
  2. Live Databricks credentials

All tests are marked:
  - @pytest.mark.integration — excluded from `pytest tests/unit/ -x` fast path
  - @pytest.mark.skipif(True, ...) — skipped at runtime until D-20 gate passes

The skipif condition (True) will be replaced with an endpoint-readiness check in
Wave 2 (plan 05: Nemotron live endpoint). Do NOT remove the skipif unconditionally
before D-20 passes.

Tests validate:
  - Pitfall 1: tool_calls in `content` vs structured `tool_calls` field
  - D-18: thinking-mode token split (ON > OFF completion tokens)
  - D-06a: VERDICT tool schema round-trip via guided_json
"""
from __future__ import annotations

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        True,  # replaced with endpoint-readiness check in Wave 2
        reason="Nemotron endpoint not yet deployed — D-20 gate must pass first",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nemotron_client():
    """Return a configured OpenAI-compatible client pointing at the Nemotron endpoint."""
    from llm.client import get_client
    from config import get_settings
    settings = get_settings()
    return get_client(model="nemotron-super-49b-v1_5")


@pytest.fixture
def verdict_tool_schema():
    """Return the Databricks-legal VERDICT tool schema."""
    from llm.structured import build_tool_schema
    from schemas.llm import VERDICT
    return build_tool_schema(VERDICT, name="render_verdict", description="Emit a structured VERDICT")


# ---------------------------------------------------------------------------
# MODEL-02: Nemotron structured tool-call validation
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_nemotron_tool_call_returns_structured_tool_calls(nemotron_client, verdict_tool_schema):
    """Nemotron must return structured `tool_calls`, NOT prose in `content`.

    Validates Pitfall 1 (RESEARCH.md §Nemotron Pitfalls): some deployments incorrectly
    serialise tool calls as a JSON string inside `message.content` rather than the
    OpenAI-spec `message.tool_calls` list. This test confirms the correct shape.
    """
    response = nemotron_client.chat.completions.create(
        model="nemotron-super-49b-v1_5",
        messages=[
            {
                "role": "user",
                "content": (
                    "Call render_verdict with verdict=KEEP, confidence=0.95, "
                    "rationale='Evidence found', grounding_span='Section 3.2'"
                ),
            }
        ],
        tools=[verdict_tool_schema],
        tool_choice={"type": "function", "function": {"name": "render_verdict"}},
    )
    turn = response.choices[0].message

    # Pitfall 1 check: tool_calls must be a non-empty list, content must be None/empty
    assert turn.tool_calls, (
        "Nemotron returned no tool_calls — check tool-parser configuration (Pitfall 1). "
        "Response content: " + repr(turn.content)
    )
    assert not turn.content, (
        "Nemotron serialised tool call as prose in content instead of tool_calls (Pitfall 1). "
        "content: " + repr(turn.content)
    )


# ---------------------------------------------------------------------------
# D-18: Thinking-mode token split
# ---------------------------------------------------------------------------

_THINKING_ON_SYSTEM = (
    "You are a careful regulatory reviewer. Think step by step before answering."
)
_THINKING_OFF_SYSTEM = (
    "You are a regulatory reviewer. Respond concisely without internal reasoning."
)

_PROBE_USER_MSG = (
    "Does the phrase 'stability data available on request' constitute a deficiency "
    "under 21 CFR 211.166? Answer with one of: KEEP or DOWNGRADE."
)


@pytest.mark.integration
@pytest.mark.parametrize("thinking_mode,system_prompt", [
    ("on", _THINKING_ON_SYSTEM),
    ("off", _THINKING_OFF_SYSTEM),
])
def test_thinking_on_inflates_completion_tokens(
    nemotron_client, thinking_mode, system_prompt
):
    """Data-collection test: record completion_tokens for each thinking mode.

    NOTE: This test is data-collection only — it does NOT assert ON > OFF.
    The definitive D-18 assertion is in test_thinking_mode_token_split_is_detected.
    Do NOT add 'assert ... or True' here — that is a tautology.

    What this test DOES assert: the response is well-formed (choices non-empty,
    usage present). If the endpoint is up, this is always true.
    """
    response = nemotron_client.chat.completions.create(
        model="nemotron-super-49b-v1_5",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _PROBE_USER_MSG},
        ],
        max_tokens=512,
    )
    assert response.choices, "Nemotron returned no choices (endpoint error)"
    assert response.usage is not None, "Nemotron returned no usage stats"
    # Log token count for the D-18 harness (informational, not a pass/fail assertion)
    print(
        f"\n[D-18 data] thinking_mode={thinking_mode!r} "
        f"completion_tokens={response.usage.completion_tokens}"
    )


@pytest.mark.integration
def test_thinking_mode_token_split_is_detected(nemotron_client):
    """D-18 definitive assertion: thinking-ON produces more completion tokens than OFF.

    Runs both modes in sequence and compares the completion_tokens counts.
    This is the real D-18 check; test_thinking_on_inflates_completion_tokens is
    data-collection only.
    """
    def _tokens(system_prompt: str) -> int:
        response = nemotron_client.chat.completions.create(
            model="nemotron-super-49b-v1_5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _PROBE_USER_MSG},
            ],
            max_tokens=512,
        )
        return response.usage.completion_tokens

    tokens_on = _tokens(_THINKING_ON_SYSTEM)
    tokens_off = _tokens(_THINKING_OFF_SYSTEM)

    assert tokens_on > tokens_off, (
        f"D-18 FAILED: thinking-ON tokens ({tokens_on}) not greater than "
        f"thinking-OFF tokens ({tokens_off}). "
        "Check the system prompt strings and Nemotron reasoning-toggle configuration."
    )


# ---------------------------------------------------------------------------
# D-06a: VERDICT tool schema round-trip
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_tool_call_round_trip_verdict(nemotron_client, verdict_tool_schema):
    """Send a minimal VERDICT tool schema via guided_json; assert response parses
    to a valid VERDICT instance. Validates D-06a conformance for Nemotron.
    """
    from schemas.llm import VERDICT

    response = nemotron_client.chat.completions.create(
        model="nemotron-super-49b-v1_5",
        messages=[
            {
                "role": "user",
                "content": (
                    "Evaluate: does 'no expiry date listed' violate 21 CFR 211.137? "
                    "Call render_verdict with your assessment."
                ),
            }
        ],
        tools=[verdict_tool_schema],
        tool_choice={"type": "function", "function": {"name": "render_verdict"}},
    )
    turn = response.choices[0].message
    assert turn.tool_calls, "No tool_calls returned — D-06a conformance check failed"

    import json
    args_raw = turn.tool_calls[0].function.arguments
    args_dict = json.loads(args_raw)

    # Must parse to a valid VERDICT instance without error
    verdict_instance = VERDICT(**args_dict)
    assert verdict_instance.verdict in ("KEEP", "DOWNGRADE"), (
        f"Unexpected verdict value: {verdict_instance.verdict!r}"
    )
    assert 0.0 <= verdict_instance.confidence <= 1.0, (
        f"Confidence out of range: {verdict_instance.confidence}"
    )
