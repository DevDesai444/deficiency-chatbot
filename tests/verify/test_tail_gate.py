# VERIFY-04 — the interpretive tail is grounded then passed through the SAME consensus verifier.
"""RED stub (Wave 0). Turns GREEN when src/verify/tail.py lands.

A tail candidate is emitted only through the byte-exact grounding gate and then passed through the
SAME consensus verifier as every deterministic candidate. A tail candidate the panel does not
affirmatively keep-support is NOT surfaced as grounded — its confidence is lowered, never dropped.
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import (
    ScriptedFleetClient,
    tail_candidate,
    make_verdict_turn,
)


def test_tail_candidate_without_keep_support_is_downgraded_not_dropped():
    tail = pytest.importorskip(
        "verify.tail",
        reason="src/verify/tail.py lands in Wave 3; tail-gate test flips on then.",
    )
    from config import VERIFIER_FLEET

    candidate = tail_candidate()
    before_id = id(candidate)

    # panel DOWNGRADEs with grounding -> tail candidate is not surfaced as grounded, only lowered
    fleet = ScriptedFleetClient(
        script={m: [make_verdict_turn("DOWNGRADE", "linearity r-squared of 0.991")] for m in VERIFIER_FLEET}
    )
    out = tail.run_tail([candidate], fleet_client=fleet)

    # same object, never dropped
    assert len(out) == 1
    assert id(out[0]) == before_id
    # not surfaced as grounded/active: tier lowered
    assert out[0].confidence_tier == "low"
    assert out[0].confidence <= candidate.confidence
