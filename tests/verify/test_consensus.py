# VERIFY-01 / VERIFY-03 — DOWNGRADE requires affirmative grounded majority; else KEEP.
"""RED stub (Wave 0). Turns GREEN when src/verify/consensus.py lands.

Invariant table:
  - lone DOWNGRADE (rest KEEP)                     -> KEEP
  - split vote                                     -> KEEP
  - affirmative GROUNDED majority DOWNGRADE        -> DOWNGRADE
  - an UNGROUNDED DOWNGRADE does not count toward the majority

A verdict counts toward a DOWNGRADE only if it is DOWNGRADE AND grounded. Everything else -> KEEP.
"""
from __future__ import annotations

import pytest


def _v(verdict: str, grounded: bool, model: str):
    """A minimal panel verdict record the consensus fn consumes."""
    return {"verdict": verdict, "grounded": grounded, "model": model}


def test_consensus_downgrade_only_on_affirmative_grounded_majority():
    consensus_mod = pytest.importorskip(
        "verify.consensus",
        reason="src/verify/consensus.py lands in Wave 1; consensus test flips on then.",
    )
    consensus = consensus_mod.consensus
    panel_size = 3

    # lone grounded DOWNGRADE, two KEEP -> KEEP
    lone = consensus(None, [_v("DOWNGRADE", True, "a"), _v("KEEP", True, "b"), _v("KEEP", True, "c")], panel_size)
    assert lone[0] == "KEEP"

    # split 1 grounded DOWNGRADE / 1 KEEP / 1 KEEP-ish -> KEEP (no majority)
    split = consensus(None, [_v("DOWNGRADE", True, "a"), _v("KEEP", True, "b")], panel_size)
    assert split[0] == "KEEP"

    # affirmative grounded majority (2 of 3) -> DOWNGRADE
    maj = consensus(None, [_v("DOWNGRADE", True, "a"), _v("DOWNGRADE", True, "b"), _v("KEEP", True, "c")], panel_size)
    assert maj[0] == "DOWNGRADE"

    # 2 DOWNGRADEs but one is UNGROUNDED -> the ungrounded one does not count -> KEEP
    ungrounded = consensus(None, [_v("DOWNGRADE", True, "a"), _v("DOWNGRADE", False, "b"), _v("KEEP", True, "c")], panel_size)
    assert ungrounded[0] == "KEEP"
