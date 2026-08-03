"""Review loop mechanics for AGENT-01.

The full turn loop lands in this plan after the static prefix proof. The
prefix renderer is kept here because it serializes the exact provider-facing
system message and tool schema bytes.
"""
from __future__ import annotations

import json
from typing import Any

from agents.review.prompts import SYSTEM_PROMPT


def render_prefix(registry: Any) -> str:
    """Serialize the static provider prefix: system message plus tool schemas."""
    prefix = {
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        "tools": registry.schemas(),
    }
    return json.dumps(prefix, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = ["render_prefix"]
