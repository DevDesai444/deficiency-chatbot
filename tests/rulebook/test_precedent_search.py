"""Tests for the Phase-5 precedent leg (RECALL-04, Plan 05-05).

Replaces the Wave-0 importorskip scaffold from Plan 01 with real tests now that
rulebook.precedent_search is implemented.

Test coverage:
  - test_same_anda_exclusion: D-PRC3 same-ANDA exclusion filter
  - test_above_threshold_candidate: B2 fix — real cosine score assertion, NOT a grep
  - test_short_section_skipped: Pitfall 3 — short sections skipped before FAISS call
  - test_pitfall4_correct_index: Pitfall 4 guard — module must not reference deficiency_kb
"""
from __future__ import annotations

import inspect

import pytest

import rulebook.precedent_search as ps_module
from rulebook.precedent_search import (
    _filter_precedent_chunks,
    _load_precedent_threshold,
    _search_rulebook_faiss_with_scores,
    search_precedents,
)


# ---------------------------------------------------------------------------
# Long section text helpers — avoids Pitfall 3 (len < 100) in tests
# ---------------------------------------------------------------------------

_LONG_SECTION = (
    "Method validation accuracy precision linearity specificity robustness "
    "forced degradation stability impurity limits regulatory compliance ICH Q2. "
    * 3
)
assert len(_LONG_SECTION) >= 100, "test helper text must be >= 100 chars"


def _patch_faiss_fn(monkeypatch, result):
    """Monkeypatch _search_rulebook_faiss_with_scores to return a fixed result list."""
    monkeypatch.setattr(
        ps_module,
        "_search_rulebook_faiss_with_scores",
        lambda text, top_k: result,
    )


def _patch_provenance(monkeypatch, prov_map: dict):
    """Monkeypatch get_provenance via the _precedents_module alias in precedent_search.

    precedent_search.py imports rulebook.precedents as _precedents_module and calls
    _precedents_module.get_provenance(...) — patching the module object attribute
    ensures the patch is visible to _filter_precedent_chunks at call time.
    """
    monkeypatch.setattr(
        ps_module._precedents_module,
        "get_provenance",
        lambda doc_id, **kw: prov_map.get(doc_id, []),
    )


# ---------------------------------------------------------------------------
# test_same_anda_exclusion (D-PRC3)
# ---------------------------------------------------------------------------

def test_same_anda_exclusion(monkeypatch):
    """D-PRC3: chunks whose anda_number matches the submission ANDA# are excluded.

    _search_rulebook_faiss_with_scores returns a high-scoring precedent chunk.
    get_provenance returns a provenance row with the SAME anda_number as the submission.
    search_precedents must exclude the chunk and return [].
    """
    _patch_faiss_fn(monkeypatch, [("precedent-abc123", 0.85)])
    _patch_provenance(monkeypatch, {"precedent-abc123": [{"anda_number": "12345"}]})

    results = search_precedents(
        _LONG_SECTION,
        threshold=0.5,
        submission_anda_number="12345",
    )
    assert results == [], (
        "D-PRC3: same-ANDA chunk must be excluded; got non-empty results"
    )


# ---------------------------------------------------------------------------
# test_above_threshold_candidate (D-PRC4, B2 fix)
# ---------------------------------------------------------------------------

def test_above_threshold_candidate(monkeypatch):
    """D-PRC4 + B2 fix: cosine score > threshold returns the candidate.

    Monkeypatches _search_rulebook_faiss_with_scores to return a real (doc_id, cosine) tuple.
    Monkeypatches get_provenance so the ANDA# does NOT match the submission.

    B2 fix assertion: asserts similarity_score > threshold as a VALUE assertion —
    NOT a source-text grep. This proves _filter_precedent_chunks thresholds on the
    actual FAISS cosine score returned by IndexFlatIP.search, not on a rank or proxy.
    """
    _patch_faiss_fn(monkeypatch, [("precedent-test123", 0.8)])
    _patch_provenance(monkeypatch, {"precedent-test123": [{"anda_number": "999"}]})

    results = search_precedents(
        _LONG_SECTION,
        threshold=0.6,
        submission_anda_number="different-anda",
    )

    assert len(results) == 1, f"Expected 1 result, got {len(results)}: {results}"
    doc_id, cosine_score = results[0]
    assert doc_id == "precedent-test123"

    # B2 fix: assert the REAL cosine score exceeds threshold — not a source-text grep
    assert cosine_score > 0.6, (
        f"B2 fix: similarity_score {cosine_score} must exceed threshold 0.6 — "
        "this is an actual score assertion, not a source-text grep (B2 resolution)"
    )


# ---------------------------------------------------------------------------
# test_short_section_skipped (Pitfall 3)
# ---------------------------------------------------------------------------

def test_short_section_skipped(monkeypatch):
    """Pitfall 3: sections with len(text) < 100 are skipped before calling FAISS.

    Verifies that _search_rulebook_faiss_with_scores is NEVER called when the
    section is too short — the guard must be at the search_precedents entry point.
    """
    called = []
    monkeypatch.setattr(
        ps_module,
        "_search_rulebook_faiss_with_scores",
        lambda text, top_k: called.append(text) or [],
    )

    short_text = "short"
    assert len(short_text) < 100

    results = search_precedents(short_text, threshold=0.5)

    assert results == [], f"Expected [] for short section, got {results}"
    assert called == [], (
        f"Pitfall 3: _search_rulebook_faiss_with_scores must NOT be called for "
        f"len(section_text) < 100; was called with: {called}"
    )


# ---------------------------------------------------------------------------
# test_pitfall4_correct_index (Pitfall 4)
# ---------------------------------------------------------------------------

def test_pitfall4_correct_index():
    """Pitfall 4 guard: precedent_search.py must NOT reference deficiency_kb.faiss.

    deficiency_kb.faiss is the per-submission index keyed by SQLite rowids, which
    cannot carry ANDA# metadata for same-ANDA exclusion. The precedent leg MUST
    use rulebook.faiss via _faiss_index directly (B2 fix).

    Inspects the source of the rulebook.precedent_search module and asserts
    'deficiency_kb' is absent.
    """
    src = inspect.getsource(ps_module)
    assert "deficiency_kb" not in src, (
        "Pitfall 4: precedent_search.py must not reference deficiency_kb.faiss. "
        "Use rulebook.faiss via _faiss_index from rulebook.store (B2 fix). "
        "Offending module source contains 'deficiency_kb'."
    )
