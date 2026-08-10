#!/usr/bin/env python3
"""Pre-metering proof of the token observer (reviewer HARD CONDITION 2, 2026-08-10).

Validates the observer end-to-end against a cheap, allow-listed, pay-per-token
endpoint (``databricks-meta-llama-3-1-8b-instruct``) BEFORE the H100 Nemotron clock
starts. One ~5-token ping goes through the SAME ``chat_completion_tools`` path the
gate uses; success requires that exactly one JSONL telemetry row appears afterward
with sane (non-negative, prompt>0) token numbers.

Exit 0 = observer proven live -> caller may proceed to deploy().
Exit 1 = observer not proven -> caller MUST NOT deploy (no idle H100).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))            # for `tests.evals.token_observer`
sys.path.insert(0, str(ROOT / "src"))    # for `llm.client`

# Cheap, allow-listed, pay-per-token, tool-capable (Llama 3.3 70B FMAPI). Passes the
# D-16 deny-first guard (no claude/gpt/gemini substring) and is in DETECTOR_MODELS.
CHEAP_MODEL = "databricks-meta-llama-3-3-70b-instruct"


def main() -> int:
    jsonl = os.environ.get("TOKEN_OBSERVER_JSONL")
    if not jsonl:
        print("PROOF FAIL: TOKEN_OBSERVER_JSONL not set")
        return 1
    os.environ["PROBE_MODE"] = "proof"

    from tests.evals.token_observer import install

    if not install():
        print("PROOF FAIL: observer install() returned False (fail-open no-op)")
        return 1

    before = 0
    p = Path(jsonl)
    if p.exists():
        before = sum(1 for _ in p.open())

    from llm.client import chat_completion_tools

    tool = {
        "type": "function",
        "function": {
            "name": "noop",
            "description": "no-op",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    }
    turn = chat_completion_tools(
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        tools=[tool],
        model=CHEAP_MODEL,
        temperature=0.0,
        max_tokens=5,
        tool_choice="auto",
    )
    print(f"ping ok: prompt_tokens={turn.prompt_tokens} completion_tokens={turn.completion_tokens}")

    if not p.exists():
        print("PROOF FAIL: no JSONL written")
        return 1
    rows = [json.loads(x) for x in p.open() if x.strip()]
    if len(rows) <= before:
        print(f"PROOF FAIL: no new row appended (before={before}, now={len(rows)})")
        return 1
    last = rows[-1]
    pt, ct = last.get("prompt_tokens", 0), last.get("completion_tokens", 0)
    if not isinstance(pt, int) or not isinstance(ct, int) or pt <= 0 or ct < 0:
        print(f"PROOF FAIL: insane token numbers in row: {last}")
        return 1
    print(f"PROOF PASS: observer row appended -> {last}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
