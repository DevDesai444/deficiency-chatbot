"""Agent-facing navigation tools (Phase 2) -- the "hands" the drive-loop (Phase 3) calls.

Lazy PEP-562 barrel (mirrors `ingest`'s lazy barrel). `tools.errors` / `tools.ledger` are cheap,
cycle-free leaves and stay eager. `run_oracles_tool`, however, lives under
`agents.review.oracles_tool`, whose package `__init__` pulls in
`agents.review.loop -> registry -> tools.read_guideline -> rulebook.requirement_index`. When
`rulebook.requirement_index` is imported FIRST (its own `from tools.errors import ToolRejected`
triggers this barrel while `requirement_index` is only partially initialized), an EAGER
`run_oracles_tool` import re-enters `rulebook.requirement_index` before `enumerate_requirements`
is defined and raises a circular ImportError -- which broke the `tools`/`requirement_index` import
order, every Phase-4 verify command that imports `rulebook.requirement_index` first, and
`tests/rulebook/test_requirement_index_integration.py` collection (Rule 3 blocking fix).
Resolving `run_oracles_tool` lazily on first attribute access defers that chain until a caller
actually needs it, by which point `rulebook.requirement_index` is fully loaded.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger

if TYPE_CHECKING:  # type-checkers/IDEs only -- never executed at runtime
    from agents.review.oracles_tool import run_oracles_tool

__all__ = ["RetrievalLedger", "ToolRejected", "run_oracles_tool"]


def __getattr__(name: str):
    """PEP 562 lazy attribute resolution -- defers the `agents.review` import chain (which cycles
    back through `rulebook.requirement_index`) until `run_oracles_tool` is first accessed."""
    if name == "run_oracles_tool":
        from agents.review.oracles_tool import run_oracles_tool

        return run_oracles_tool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
