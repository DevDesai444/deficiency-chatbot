# VERIFY-01 — downgrade-never-drop: no verifier path deletes a candidate.
"""RED stub (Wave 0). Turns GREEN when src/verify/orchestrator.py lands (Wave 1/2).

The non-negotiable invariant: given a panel that ALL DOWNGRADE, the orchestrator's output list
length == input length; the DOWNGRADEd Fault is the SAME object mutated (confidence lowered,
confidence_tier="low"), never removed. Plus a static source assertion that no fault list is ever
popped/deleted/removed in src/verify/.
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import (
    ScriptedFleetClient,
    deterministic_candidate,
    make_verdict_turn,
)


def test_all_downgrade_keeps_every_candidate_object_mutated_not_dropped():
    orch = pytest.importorskip(
        "verify.orchestrator",
        reason="src/verify/orchestrator.py lands in Wave 1/2; invariant test flips on then.",
    )
    from config import VERIFIER_FLEET

    candidate = deterministic_candidate()
    before_id = id(candidate)
    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("DOWNGRADE", "Total is 0.14 percent")] for m in VERIFIER_FLEET}
    )

    before_conf = candidate.confidence
    verified, coverage = orch.verify_candidates([candidate], fleet_client=fleet)

    # length preserved == unique dedup_key count (never dropped)
    assert len(verified) == 1
    # SAME object, mutated in place: confidence lowered + tier flipped to low
    assert id(verified[0]) == before_id
    assert verified[0].confidence_tier == "low"
    assert verified[0].confidence < before_conf
    # the DOWNGRADEd fault is recorded in the coverage audit trail (visible, not buried), with the
    # agreeing verifiers — never silently dropped.
    assert coverage.reviewed_downgrade
    assert coverage.reviewed_downgrade[0]["dedup_key"] == candidate.dedup_key
    assert coverage.reviewed_downgrade[0]["agreeing_verifiers"]


def test_no_drop_mutation_verbs_in_verify_source():
    """Static guard: src/verify/ never pops/deletes/removes from a fault list (VERIFY-01)."""
    import pathlib

    verify_dir = pathlib.Path("src/verify")
    if not verify_dir.exists():
        pytest.skip("src/verify/ not built until Wave 1/2; static drop-verb guard flips on then.")
    offending = []
    for path in verify_dir.rglob("*.py"):
        src = path.read_text()
        for verb in (".pop(", "del faults", ".remove("):
            if verb in src:
                offending.append((str(path), verb))
    assert not offending, f"drop verbs found in src/verify/: {offending}"
