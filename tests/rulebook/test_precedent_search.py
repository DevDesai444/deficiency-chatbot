"""Wave-0 test scaffold for Phase-5 precedent leg (RECALL-04, Plan 05-05).

These are FAILING tests (or skipped tests) that define the expected behavior of
rulebook.precedent_search (not yet implemented). Wave-2 Plan 05-05 implements the module
and makes these tests pass.

Scaffold pattern: pytest.importorskip on the target module so pytest --collect-only
passes cleanly without ImportError.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Guard: skip all tests if rulebook.precedent_search is not yet implemented
# ---------------------------------------------------------------------------
precedent_search = pytest.importorskip(
    "rulebook.precedent_search",
    reason="rulebook.precedent_search not yet implemented — Wave-2 Plan 05-05",
)


def test_same_anda_exclusion():
    """D-PRC3: precedent candidates from the SAME ANDA as the submission are excluded.

    When the submission's ANDA# matches a precedent chunk's anda_number metadata,
    that chunk must be filtered out of the results.
    """
    pytest.skip("Wave-2 precedent_search.py implementation not yet present")


def test_above_threshold_candidate():
    """D-PRC4: a submission section with cosine >= threshold produces a PrecedentAnchor.

    When bge-m3 cosine similarity between submission section embedding and a precedent
    chunk exceeds the absolute threshold from precedent_threshold.json, a candidate
    must be emitted with leg_tag='PRECEDENT' and tier=Tier.ADVISORY.
    """
    pytest.skip("Wave-2 precedent_search.py implementation not yet present")


def test_below_threshold_no_candidate():
    """D-PRC4: a section with cosine < threshold does NOT produce a candidate.

    The absolute threshold is enforced: below-threshold sections are silently skipped,
    not over-emitted (unlike D-ABS2 absence over-emit — precedent is qualitatively
    different from absence, so no over-emit here).
    """
    pytest.skip("Wave-2 precedent_search.py implementation not yet present")


def test_held_out_fixture_skips_without_faiss():
    """D-GRD2: guard test runs against synthetic fixture; skips cleanly without FAISS asset."""
    faiss_path = "data/deficiency_kb.faiss"
    import pathlib
    if not pathlib.Path(faiss_path).exists():
        pytest.skip(f"deficiency_kb.faiss not present at {faiss_path}; skipping cosine test")
    pytest.skip("Wave-2 precedent_search.py implementation not yet present")
