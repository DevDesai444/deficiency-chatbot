"""Wave-0 test scaffold for Phase-5 structural leg (RECALL-02, Plan 05-03).

These are FAILING tests (or skipped tests) that define the expected behavior of
rulebook.structural (not yet implemented). Wave-2 Plan 05-03 implements the module
and makes these tests pass.

Scaffold pattern: pytest.importorskip on the target module so pytest --collect-only
passes cleanly without ImportError.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Guard: skip all tests if rulebook.structural is not yet implemented
# ---------------------------------------------------------------------------
structural = pytest.importorskip(
    "rulebook.structural",
    reason="rulebook.structural not yet implemented — Wave-2 Plan 05-03",
)


def test_aggregate_violation_detected():
    """Labeled-aggregate MAX violation detected: Total < max single component.

    Fixture: doc_b.docx Table 1 (X2a planted violation):
      Total Impurities 0.12% < Compound B 0.18%
    The structural detector must flag this as a LABELED_AGGREGATE_MAX violation.
    """
    pytest.skip("Wave-2 structural.py implementation not yet present")


def test_aggregate_sum_violation_detected():
    """Labeled-aggregate SUM violation detected: Total != sum of components.

    Fixture: doc_b.docx Table 1 (X2b planted violation):
      Total 0.12% != Compound A 0.10% + Compound B 0.18% = 0.28%
    """
    pytest.skip("Wave-2 structural.py implementation not yet present")


def test_aggregate_max_batch_violation_detected():
    """Labeled-aggregate MAX violation detected: Maximum < true max across batch rows.

    Fixture: doc_b.docx Table 2 (X2c planted violation):
      Maximum Measured Value 42.3 < true max(38.2, 57.8, 44.1) = 57.8
    """
    pytest.skip("Wave-2 structural.py implementation not yet present")


def test_compliant_row_not_flagged():
    """Compound A at 0.10% is BELOW NMT 0.15% — must NOT be flagged as a violation.

    This is the negative test: Compound A complies (0.10 < 0.15).
    Only Compound B (0.18% > 0.15%) is the real violation.
    """
    pytest.skip("Wave-2 structural.py implementation not yet present")


def test_fixture_cosine_regime():
    """D-GRD1 constraint 3: fixture text must be realistic enough for bge-m3 cosine regime.

    This test verifies the fixture has sufficient domain vocabulary to exercise the
    dense-cosine thresholds. It does NOT require the FAISS index to be present.
    """
    import pathlib
    from pathlib import Path

    fixture_dir = Path("src/evals/dataset/synthetic_fixture")
    assert fixture_dir.exists(), f"fixture dir must exist: {fixture_dir}"
    # Verify doc_b.docx has sufficient regulatory domain text (>= 100 chars of vocabulary)
    try:
        import docx as docx_lib
        doc = docx_lib.Document(str(fixture_dir / "doc_b.docx"))
        full_text = " ".join(para.text for para in doc.paragraphs)
        domain_terms = [
            "impurity", "specification", "NMT", "accuracy", "method validation",
            "dissolution", "stability", "validation", "analytical procedure",
        ]
        present = [t for t in domain_terms if t.lower() in full_text.lower()]
        assert len(present) >= 3, (
            f"D-GRD1: fixture doc_b.docx must contain at least 3 domain vocabulary terms "
            f"for non-degenerate bge-m3 cosine regime. Present: {present}"
        )
        assert len(full_text) >= 100, (
            f"D-GRD1: fixture text must be at least 100 chars, got {len(full_text)}"
        )
    except ImportError:
        pytest.skip("python-docx not available for cosine-regime check")
