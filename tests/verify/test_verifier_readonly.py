# VERIFY-01 — the verifier is write-disabled: no emit/write tool is reachable.
"""RED stub (Wave 0). Turns GREEN when src/verify/orchestrator.py builds the verifier tool list.

Assert on the tools the orchestrator hands to each ScriptedFleetClient call: only read tools
(get_section / read_guideline) may be present; no emit_finding / write / mutate tool.
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import (
    ScriptedFleetClient,
    deterministic_candidate,
    make_verdict_turn,
)

_WRITE_TOOL_MARKERS = ("emit_finding", "emit_", "write", "mutate", "submit_finding")


def test_verifier_tool_list_contains_no_write_tool():
    orch = pytest.importorskip(
        "verify.orchestrator",
        reason="src/verify/orchestrator.py lands in Wave 1/2; write-disabled test flips on then.",
    )
    from config import VERIFIER_FLEET

    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("KEEP", "Total is 0.14 percent")] for m in VERIFIER_FLEET}
    )
    orch.verify_candidates([deterministic_candidate()], fleet_client=fleet)

    seen_any = False
    for tool_lists in fleet.seen_tools_by_model.values():
        for tools in tool_lists:
            seen_any = True
            names = {(t.get("function", {}) or {}).get("name", "") for t in tools}
            for name in names:
                assert not any(mark in name for mark in _WRITE_TOOL_MARKERS), (
                    f"verifier was offered a write tool: {name}"
                )
    assert seen_any, "no verifier tool list was recorded — orchestrator did not call the fleet"
