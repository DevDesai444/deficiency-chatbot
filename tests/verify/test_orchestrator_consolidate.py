# VERIFY-02 — fan-out keyed on dedup_key; consolidation merges, never drops.
"""RED stub (Wave 0). Turns GREEN when src/verify/orchestrator.py implements consolidation.

Two Faults with the SAME dedup_key are grouped (merged, count preserved end-to-end); distinct
keys stay separate. Consolidation must never reduce the surfaced candidate count.
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import deterministic_candidate, absence_candidate


def test_same_dedup_key_grouped_distinct_keys_separate():
    orch = pytest.importorskip(
        "verify.orchestrator",
        reason="src/verify/orchestrator.py lands in Wave 1/2; consolidation test flips on then.",
    )
    a = deterministic_candidate()  # dedup_key docA:sec1:null
    b = deterministic_candidate()  # same dedup_key -> should group with a
    c = absence_candidate()        # dedup_key docA:sec2:req-x -> distinct

    groups = orch.consolidate([a, b, c])

    # two distinct dedup_keys -> exactly two groups
    assert len(groups) == 2
    keys = {g.dedup_key for g in groups}
    assert keys == {"docA:sec1:null", "docA:sec2:req-x"}
    # the shared-key group merged both members (count preserved, nothing dropped)
    merged = next(g for g in groups if g.dedup_key == "docA:sec1:null")
    assert len(merged.members) == 2
