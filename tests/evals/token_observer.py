"""Session-only token/telemetry observer for the Phase-6 verifier gate.

Reviewer ruling (2026-08-10): the reviewer-audited ``run_probe_batch`` in
``test_verifier_probe.py`` intentionally discards per-call token usage. To recover
the Phase-7 escalation data (per-mode token cost) WITHOUT editing the audited gate
artifact, this module wraps ``llm.client.chat_completion_tools`` with a pure
*observer* that tees ``ChatTurn`` token counts into an append-only JSONL side file.

HARD CONDITION 1 — FAIL-OPEN BY CONSTRUCTION:
  The wrapper calls the real ``chat_completion_tools`` FIRST and returns its exact
  result. The tee body is wrapped end-to-end in ``try/except: pass`` — an observer
  failure may drop a telemetry row but can NEVER raise into, alter, delay, or retry
  the probe path. Writes are append-only, one row per call, no buffering that could
  block. If installation itself fails, it silently no-ops (the gate runs unobserved
  rather than breaking).

The gate logic stays byte-identical: this module only reads ``turn.prompt_tokens`` /
``turn.completion_tokens`` off the value the real function already returned.
"""
from __future__ import annotations

import functools
import json
import os
import time

_INSTALLED = False


def install(jsonl_path: str | None = None, mode: str | None = None) -> bool:
    """Idempotently wrap ``llm.client.chat_completion_tools`` with the token tee.

    Returns True if the wrapper is in place, False if it no-op'd (fail-open).
    ``mode`` is read from ``PROBE_MODE`` at CALL time (not install time) so a single
    installed wrapper attributes rows to whichever thinking-mode invocation is active.
    """
    global _INSTALLED
    path = jsonl_path or os.environ.get("TOKEN_OBSERVER_JSONL")
    if not path:
        return False
    try:
        import llm.client as _c  # noqa: PLC0415 — deferred so src/ is on sys.path first
    except Exception:
        return False

    orig = getattr(_c, "chat_completion_tools", None)
    if orig is None:
        return False
    if getattr(orig, "_token_observed", False):
        _INSTALLED = True
        return True

    @functools.wraps(orig)
    def _observed(*args, **kwargs):
        # Probe path FIRST — untouched, its return value is what the caller gets.
        turn = orig(*args, **kwargs)
        # Everything below is best-effort telemetry. It must never affect `turn`.
        try:
            row = {
                "ts": time.time(),
                "mode": mode or os.environ.get("PROBE_MODE", "unknown"),
                "model": kwargs.get("model"),
                "prompt_tokens": int(getattr(turn, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(turn, "completion_tokens", 0) or 0),
            }
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        except Exception:
            pass
        return turn

    _observed._token_observed = True  # type: ignore[attr-defined]
    try:
        _c.chat_completion_tools = _observed
    except Exception:
        return False
    _INSTALLED = True
    return True
