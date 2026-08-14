"""MODEL-02 pre-wiring probes for the live Nemotron-Super-49B-v1.5 endpoint.

D-06a: Tool-call round-trip returns structured tool_calls (not prose in content).
D-18: Thinking ON vs OFF produces different completion_token counts AND different
      discrimination quality (FIX 6).
Pitfall 1: Wrong --tool-call-parser -> tool_calls empty, content has prose.
Pitfall 2: Reasoning toggle string not probed -> D-18 split invalid.

All tests are @pytest.mark.integration and skip (not error) when the live endpoint
env/URL is absent — safe to collect and deselect by default.

FIX 6 changes (cross-AI review, Plan 05):
- Removed the blanket `@pytest.mark.skipif(True, ...)` module-level skip that made
  all tests permanently skip without a real gate. Replaced with per-fixture pytest.skip()
  that fires when is_databricks=False (endpoint genuinely absent).
- Removed `assert ... or True` tautology from test_thinking_on_inflates_completion_tokens
  — a degenerate assertion that always passes. That function is data-collection only;
  the hard split assertion is in test_thinking_mode_token_split_is_detected.
- Added test_thinking_mode_discrimination_comparison — runs a labeled micro-subset in
  BOTH thinking modes and asserts discrimination(ON) >= discrimination(OFF) - epsilon.
  Measures D-18 quality (not just token count) for Phase 7 escalation-trigger design.
"""
from __future__ import annotations

import json
import time
from typing import Any

import pytest
import structlog

log = structlog.get_logger()

pytestmark = pytest.mark.integration

# D-18: Reasoning toggle strings (from NVIDIA model card v1.5).
# PROBE NOTE: probe BOTH strings in the pre-wiring probe (D-18 task) and confirm
# which actually flips the token count — the toggle string is version-dependent.
# The v1.5 card uses /no_think for OFF; v1 used "detailed thinking off".
#
# β-PIVOT (2026-08-13): these now delegate to the canonical verifier elicitation prompt
# (src/llm/verifier_prompt.py), which supplies general skeptical-reviewer discipline. The
# prior minimal strings ("Analyze carefully…") caused weak models to rubber-stamp every
# candidate KEEP (D-06b blanket-KEEP tripwire). The thinking directive is preserved as the
# leading line of each mode. The prompt is corpus-agnostic (anti-overfitting law).
from llm.verifier_prompt import verifier_system_prompt  # noqa: E402

THINKING_ON_SYSTEM = verifier_system_prompt("on")
THINKING_OFF_SYSTEM = verifier_system_prompt("off")

# Minimal VERDICT tool schema for the round-trip probe.
# Must match SERVED_MODEL_NAME in deploy_nemotron.py and config.verifier_model.
VERDICT_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_verdict",
        "description": "Emit VERDICT on a candidate deficiency",
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

PROBE_MESSAGES = [
    {
        "role": "user",
        "content": (
            "Candidate: The stability study protocol omits the proposed shelf-life "
            "justification required by ICH Q1A(R2) §3.4.\n"
            "Source span: 'Stability studies were conducted at 25°C/60% RH.'\n"
            "Rule: ICH Q1A(R2) §3.4 — shelf-life justification required.\n"
            "Emit VERDICT."
        ),
    }
]

# ---------------------------------------------------------------------------
# FIX 6: Discrimination comparison micro-subset (D-18 quality measure)
# ---------------------------------------------------------------------------
# A SYNTHETIC labeled micro-subset crafted for this integration test only.
# NOT the full Plan 06 labeled subset — that uses real Phase 5 FP candidates.
# NOT using fn_gt_ids or UNRESOLVED_REF candidates (unmatched != false per ADR).
#
# Format: (candidate_name, expected_verdict, user_message)
# known-good (KEEP-expected): clearly real deficiencies
# known-planted-bad (DOWNGRADE-expected): clearly false / non-issues
DISCRIMINATION_MICRO_SUBSET: list[tuple[str, str, str]] = [
    # Known-good (KEEP-expected): textbook stability deficiency
    (
        "stability_missing_shelf_life_justification",
        "KEEP",
        (
            "Candidate: The stability study protocol omits the proposed shelf-life "
            "justification required by ICH Q1A(R2) §3.4.\n"
            "Source span: 'Stability studies were conducted at 25°C/60% RH.'\n"
            "Rule: ICH Q1A(R2) §3.4 — shelf-life justification required.\n"
            "Emit VERDICT."
        ),
    ),
    # Known-good (KEEP-expected): missing specifications table
    (
        "missing_acceptance_criteria",
        "KEEP",
        (
            "Candidate: Section 3.2.P.5 does not include acceptance criteria for "
            "assay or degradation products, violating 21 CFR 314.50(d)(1).\n"
            "Source span: 'The drug product specification includes physical "
            "appearance and pH only.'\n"
            "Rule: 21 CFR 314.50(d)(1) — complete specifications required.\n"
            "Emit VERDICT."
        ),
    ),
    # Known-planted-bad (DOWNGRADE-expected): false — rule is clearly satisfied
    (
        "false_positive_rule_satisfied",
        "DOWNGRADE",
        (
            "Candidate: The submission lacks stability data.\n"
            "Source span: 'Table 5: 24-month accelerated stability data at 40°C/75% RH "
            "shows all parameters within specification for 24 months.'\n"
            "Rule: ICH Q1A(R2) §3.4 — stability data required.\n"
            "Note: The source span clearly PROVIDES the required 24-month data. "
            "The candidate deficiency is factually incorrect.\n"
            "Emit VERDICT."
        ),
    ),
    # Known-planted-bad (DOWNGRADE-expected): false — speculative hallucination
    (
        "false_positive_speculative",
        "DOWNGRADE",
        (
            "Candidate: The batch record may not comply with regulations.\n"
            "Source span: 'Batch manufacturing records are maintained per SOP-042.'\n"
            "Rule: 21 CFR 211.188 — batch production records required.\n"
            "Note: The source span confirms records ARE maintained per SOP; no "
            "deficiency exists — the candidate is a speculative hallucination.\n"
            "Emit VERDICT."
        ),
    ),
]

_KEEP_COUNT = sum(1 for _, ev, _ in DISCRIMINATION_MICRO_SUBSET if ev == "KEEP")
_DOWNGRADE_COUNT = sum(1 for _, ev, _ in DISCRIMINATION_MICRO_SUBSET if ev == "DOWNGRADE")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def nemotron_client():
    """Return an OpenAI client pointed at the live Nemotron endpoint.

    Skips (not errors) when the environment is not Databricks or when
    the endpoint URL env vars are absent — safe to collect and deselect by default.
    """
    from config import get_settings
    from llm.client import get_client

    s = get_settings()
    if not s.is_databricks:
        pytest.skip(
            "Integration probe requires Databricks (ENVIRONMENT=databricks). "
            "is_databricks=False in this environment — skipping without error."
        )
    if not s.databricks_host or not s.databricks_token:
        pytest.skip(
            "DATABRICKS_HOST and DATABRICKS_TOKEN not set — cannot reach live endpoint."
        )
    return get_client(model=s.verifier_model)


@pytest.fixture(scope="module")
def nemotron_model():
    """Return the served model name — nemotron-super-49b-v1_5."""
    from config import get_settings

    s = get_settings()
    if not s.is_databricks:
        pytest.skip("Integration probe requires Databricks.")
    return s.verifier_model  # "nemotron-super-49b-v1_5"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_verdict(system_prompt: str, user_message: str, model: str) -> str | None:
    """Run a single tool-call turn and return the parsed verdict string or None on parse error.

    Uses chat_completion_tools with guided_model_cls=VERDICT (D-08 auto-inject)
    and coerce_and_validate (D-10 defense stack). Returns None on any failure.
    """
    from llm.client import chat_completion_tools
    from llm.reliability import coerce_and_validate
    from schemas.llm import VERDICT

    turn = chat_completion_tools(
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        tools=[VERDICT_TOOL],
        model=model,
        temperature=0.0,
        max_tokens=256,
        guided_model_cls=VERDICT,  # D-08: auto-inject guided decode if supported
    )
    if not turn.tool_calls:
        return None
    try:
        raw_args = json.loads(turn.tool_calls[0].function.arguments)
    except (json.JSONDecodeError, IndexError):
        return None
    instance, failure = coerce_and_validate(raw_args, VERDICT)
    if instance is None:
        return None
    return instance.verdict.value  # "KEEP" or "DOWNGRADE"


# ---------------------------------------------------------------------------
# Test 1: Tool-call round-trip — Pitfall 1 guard
# ---------------------------------------------------------------------------


def test_nemotron_tool_call_returns_structured_tool_calls(nemotron_client, nemotron_model):
    """Pitfall 1 guard: tool_calls populated, content empty/None (MODEL-02 / D-06a).

    If wrong --tool-call-parser: tool_calls=[], content=response text (prose leak).
    If correct parser (llama_nemotron_json): tool_calls=[...], content=None or "".

    Failure here means the --tool-call-parser vLLM flag is wrong or the
    llama_nemotron_toolcall_parser_no_streaming.py plugin was not loaded.
    """
    from llm.client import chat_completion_tools
    from schemas.llm import VERDICT

    turn = chat_completion_tools(
        messages=[{"role": "system", "content": THINKING_OFF_SYSTEM}] + PROBE_MESSAGES,
        tools=[VERDICT_TOOL],
        model=nemotron_model,
        temperature=0.0,
        max_tokens=256,
        guided_model_cls=VERDICT,  # D-08: auto-inject guided decode if supported
    )
    content_preview = repr((turn.content or "")[:200])
    assert turn.tool_calls, (
        f"tool_calls is empty — wrong --tool-call-parser or model responded with prose. "
        f"finish_reason={turn.finish_reason!r}, content={content_preview}"
    )
    # Prose leak check: content should be None or empty on a proper tool-call turn.
    assert not (turn.content or "").strip(), (
        f"content is non-empty — prose leaked from tool-call turn (Pitfall 1). "
        f"content={content_preview}"
    )


# ---------------------------------------------------------------------------
# Test 2: Data-collection parametrized per mode — NO assertion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode,system_prompt,temperature,max_tokens",
    [
        ("on", THINKING_ON_SYSTEM, 0.6, 2048),
        ("off", THINKING_OFF_SYSTEM, 0.0, 256),
    ],
)
def test_thinking_on_inflates_completion_tokens(
    nemotron_client, nemotron_model, mode, system_prompt, temperature, max_tokens
):
    """Data-collection probe: record completion_tokens per thinking mode (D-18).

    FIX 6: This function does NOT assert ON > OFF — that was a tautology in the
    Plan 01 stub (`assert completion_tokens is not None or True` always passed).
    The hard token-split assertion runs in test_thinking_mode_token_split_is_detected.
    The discrimination quality assertion runs in test_thinking_mode_discrimination_comparison.
    This function is a DATA-CAPTURE probe only — it records per-mode usage to structlog.

    Records:
      - wall_ms: latency per mode
      - prompt_tokens: input token count
      - completion_tokens: output token count (higher ON = <think> block fired)
      - usage_present: True if the endpoint returned usage stats
    """
    from llm.client import chat_completion_tools

    t0 = time.perf_counter()
    turn = chat_completion_tools(
        messages=[{"role": "system", "content": system_prompt}] + PROBE_MESSAGES,
        tools=[VERDICT_TOOL],
        model=nemotron_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    wall_ms = (time.perf_counter() - t0) * 1000

    log.info(
        "d18_thinking_mode_probe",
        mode=mode,
        wall_ms=round(wall_ms, 1),
        prompt_tokens=turn.prompt_tokens,
        completion_tokens=turn.completion_tokens,
        usage_present=turn.usage_present,
    )
    # No assertion on token count — the hard split assertion is in the next test.
    # The discrimination quality assertion is in test_thinking_mode_discrimination_comparison.
    # This function is a data-capture probe only.


# ---------------------------------------------------------------------------
# Test 3: Definitive D-18 token-split assertion
# ---------------------------------------------------------------------------


def test_thinking_mode_token_split_is_detected(nemotron_client, nemotron_model):
    """D-18: Run both modes; assert ON completion_tokens > OFF completion_tokens.

    This is the definitive check that the reasoning toggle string is correct.
    If both produce equal token counts, the toggle is ineffective — check the
    system prompt strings and update THINKING_OFF_SYSTEM (Pitfall 2).

    Thinking ON generates a <think>...</think> block that dramatically inflates
    completion_tokens. Thinking OFF produces only the direct answer.
    """
    from llm.client import chat_completion_tools

    results: dict[str, int] = {}
    for mode, system_prompt, temperature, max_tokens in [
        ("on", THINKING_ON_SYSTEM, 0.6, 2048),
        ("off", THINKING_OFF_SYSTEM, 0.0, 256),
    ]:
        turn = chat_completion_tools(
            messages=[{"role": "system", "content": system_prompt}] + PROBE_MESSAGES,
            tools=[VERDICT_TOOL],
            model=nemotron_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        results[mode] = turn.completion_tokens
        log.info(
            "d18_token_split_probe",
            mode=mode,
            completion_tokens=turn.completion_tokens,
            usage_present=turn.usage_present,
        )

    assert results["on"] > results["off"], (
        f"D-18 token split not detected: ON tokens={results['on']}, OFF tokens={results['off']}. "
        f"Thinking toggle may be ineffective — probe both toggle strings ('/no_think' vs "
        f"'detailed thinking off') per Pitfall 2 in RESEARCH.md. "
        f"Confirm the correct string by checking which system prompt produces a larger token count."
    )


# ---------------------------------------------------------------------------
# Test 4: FIX 6 — Discrimination comparison (D-18 quality measure)
# ---------------------------------------------------------------------------


def test_thinking_mode_discrimination_comparison(nemotron_client, nemotron_model):
    """FIX 6 / D-18: Thinking ON does not significantly hurt discrimination quality.

    Runs DISCRIMINATION_MICRO_SUBSET (2 known-good + 2 known-planted-bad) through
    BOTH thinking modes and counts correct verdicts per mode.

    Assertion: discrimination(ON) >= discrimination(OFF) - epsilon
    where epsilon=1 allows at most one item to slip (lenient — the micro-subset is
    synthetic and small, so variance is high). Directional, not strict.

    Why this test matters for Phase 7:
    - Token count alone (test_thinking_mode_token_split_is_detected) proves the toggle
      FIRES, not that it HELPS. This test measures whether thinking mode actually
      improves the model's ability to distinguish real deficiencies from false positives.
    - If ON mode significantly hurts discrimination, escalating to thinking mode in
      Phase 7 may reduce accuracy — a critical Phase 7 escalation-trigger risk.
    - The result is logged to structlog as d18_discrimination_summary for Phase 7
      calibration of the escalation trigger (D-18 design data).

    Note: A failure here (ON worse than OFF by >1 item) is a directional signal,
    not the D-06b hard accuracy gate (>=80% on the full labeled subset, Plan 06).
    """
    results: dict[str, dict[str, Any]] = {}

    for thinking_mode, system_prompt in [("on", THINKING_ON_SYSTEM), ("off", THINKING_OFF_SYSTEM)]:
        correct = 0
        total = 0
        keep_correct = 0
        downgrade_correct = 0

        for name, expected_verdict, user_msg in DISCRIMINATION_MICRO_SUBSET:
            actual_verdict = _run_verdict(
                system_prompt=system_prompt,
                user_message=user_msg,
                model=nemotron_model,
            )
            total += 1
            is_correct = actual_verdict == expected_verdict
            if is_correct:
                correct += 1
                if expected_verdict == "KEEP":
                    keep_correct += 1
                else:
                    downgrade_correct += 1
            log.info(
                "d18_discrimination_probe",
                mode=thinking_mode,
                candidate=name,
                expected=expected_verdict,
                actual=actual_verdict,
                correct=is_correct,
            )

        discrimination_score = correct / total if total > 0 else 0.0
        results[thinking_mode] = {
            "correct": correct,
            "total": total,
            "keep_correct": keep_correct,
            "downgrade_correct": downgrade_correct,
            "discrimination_score": discrimination_score,
        }
        log.info(
            "d18_discrimination_summary",
            mode=thinking_mode,
            discrimination_score=discrimination_score,
            keep_recall=keep_correct / _KEEP_COUNT if _KEEP_COUNT > 0 else None,
            downgrade_rate=downgrade_correct / _DOWNGRADE_COUNT if _DOWNGRADE_COUNT > 0 else None,
        )

    # Directional assertion: ON must not be significantly WORSE than OFF.
    # epsilon=1 allows at most 1 fewer correct item in ON vs OFF (4-item micro-subset).
    # A failure here signals that forcing thinking mode HURTS discrimination — a risk
    # for Phase 7's escalation trigger.
    epsilon = 1
    on_correct = results["on"]["correct"]
    off_correct = results["off"]["correct"]

    assert on_correct >= off_correct - epsilon, (
        f"Thinking ON mode significantly hurts discrimination: "
        f"ON correct={on_correct}/{results['on']['total']}, "
        f"OFF correct={off_correct}/{results['off']['total']}. "
        f"ON discrimination_score={results['on']['discrimination_score']:.2f}, "
        f"OFF discrimination_score={results['off']['discrimination_score']:.2f}. "
        f"The thinking toggle may be actively harming verdict quality — "
        f"Phase 7 escalation to ON mode may reduce accuracy. "
        f"Per-mode data logged under d18_discrimination_probe events."
    )


# ---------------------------------------------------------------------------
# Test 5: VERDICT round-trip — D-06a conformance seed
# ---------------------------------------------------------------------------


def test_tool_call_round_trip_verdict_parses(nemotron_client, nemotron_model):
    """D-06a conformance seed: single round-trip produces a parsable VERDICT.

    Uses coerce_and_validate (D-10 defense stack) + supports_guided_json probe
    (D-09 detect-once/cache). Validates that:
      1. The endpoint returns a non-empty tool_calls list (Pitfall 1 guard).
      2. The tool_calls[0].function.arguments is valid JSON.
      3. coerce_and_validate produces a VERDICT instance (not ParseFailed).
      4. The verdict field is KEEP or DOWNGRADE (no coercion — D-11 passthrough).

    Failure here typically indicates:
      - Wrong --tool-call-parser (Pitfall 1) -> tool_calls empty
      - Guided decode not wired (D-08) -> args malformed
      - Enum coercion violation (D-11) -> verdict field value off-schema
    """
    from llm.client import chat_completion_tools
    from llm.reliability import build_guided_extra_body, coerce_and_validate, supports_guided_json
    from schemas.llm import VERDICT

    turn = chat_completion_tools(
        messages=[{"role": "system", "content": THINKING_OFF_SYSTEM}] + PROBE_MESSAGES,
        tools=[VERDICT_TOOL],
        model=nemotron_model,
        temperature=0.0,
        max_tokens=256,
        guided_model_cls=VERDICT,  # D-08: auto-inject via client.py (Plan 04 Change 2)
    )
    content_preview = repr((turn.content or "")[:200])
    assert turn.tool_calls, (
        f"No tool_calls — cannot validate VERDICT args. "
        f"content={content_preview}, finish_reason={turn.finish_reason!r}"
    )

    raw_args = json.loads(turn.tool_calls[0].function.arguments)
    verdict_instance, failure = coerce_and_validate(raw_args, VERDICT)

    assert verdict_instance is not None, (
        f"VERDICT did not parse: failure={failure}. "
        f"raw_args={raw_args}. "
        f"This may indicate wrong --tool-call-parser or malformed args from the model. "
        f"Check guided decode wiring (D-08) and Pitfall 1 in RESEARCH.md."
    )
    assert failure is None, f"Unexpected non-None failure alongside valid instance: {failure}"
    assert verdict_instance.verdict.value in ("KEEP", "DOWNGRADE"), (
        f"Unexpected verdict value: {verdict_instance.verdict.value!r}. "
        f"Enum coercion is forbidden (D-11) — only KEEP or DOWNGRADE are valid."
    )
