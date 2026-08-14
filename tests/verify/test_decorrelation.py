# VERIFY-03 — the verifier message never contains the producer's chain-of-thought.
"""RED stub (Wave 0). Turns GREEN when src/verify/orchestrator.py assembles the verifier prompt.

Each verifier sees ONLY claim + re-opened source + rule — never the producer's reasoning/CoT.
Assert a known producer-CoT sentinel string is absent from every seen message body.
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import (
    ScriptedFleetClient,
    tail_candidate,
    make_verdict_turn,
)

_PRODUCER_COT_SENTINEL = "PRODUCER_CHAIN_OF_THOUGHT_LEAK_SENTINEL"


def test_verifier_never_sees_producer_chain_of_thought():
    orch = pytest.importorskip(
        "verify.orchestrator",
        reason="src/verify/orchestrator.py lands in Wave 1/2/3; decorrelation test flips on then.",
    )
    from config import VERIFIER_FLEET

    candidate = tail_candidate()
    # Plant the producer's reasoning where a naive implementation might forward it.
    candidate.detail = f"{_PRODUCER_COT_SENTINEL} the model reasoned step by step here."

    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("KEEP", "linearity r-squared of 0.991")] for m in VERIFIER_FLEET}
    )
    orch.verify_candidates([candidate], fleet_client=fleet)

    saw_message = False
    for message_lists in fleet.seen_messages_by_model.values():
        for messages in message_lists:
            saw_message = True
            blob = "\n".join(str(m.get("content", "")) for m in messages)
            assert _PRODUCER_COT_SENTINEL not in blob, "producer chain-of-thought leaked to a verifier"
    assert saw_message, "no verifier message recorded — orchestrator did not fan out"
