"""Wave-0 test scaffold for Phase-5 reference leg (RECALL-03, Plan 05-04).

These are FAILING tests (or skipped tests) that define the expected behavior of
rulebook.references (not yet implemented). Wave-2 Plan 05-04 implements the module
and makes these tests pass.

Scaffold pattern: pytest.importorskip on the target module so pytest --collect-only
passes cleanly without ImportError.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Guard: skip all tests if rulebook.references is not yet implemented
# ---------------------------------------------------------------------------
references = pytest.importorskip(
    "rulebook.references",
    reason="rulebook.references not yet implemented — Wave-2 Plan 05-04",
)


def test_docx_hyperlink_extraction():
    """D-REF1: extract_docx returns 'hyperlinks' key with links from DOCX rels file.

    Fixture: doc_b.docx in synthetic_fixture/ should have hyperlink relationships
    (any DOCX with hyperlinks has rels); doc_a.pdf has a fitz link annotation.
    """
    pytest.skip("Wave-2 references.py implementation not yet present")


def test_absent_target_manifest_check():
    """D-REF5: ABSENT_TARGET check consults the coverage manifest before emitting.

    A reference to a target that is NOT in the corpus manifest -> ABSENT_TARGET.
    A reference to a target that IS in the manifest but the referent section is missing
    -> emit as full candidate (not deferred).
    """
    pytest.skip("Wave-2 references.py implementation not yet present")


def test_value_contradiction_x1_detected():
    """X1 VALUE_CONTRADICTION: doc_a 'NMT 0.15%' vs doc_b 'Compound B 0.18%'.

    The cross-doc value contradiction via the hyperlink edge must be detected as:
    - leg_tag = 'REFERENCE'
    - anomaly = 'VALUE_CONTRADICTION'
    - confidence_tier = 'full' (edge-linked, not just label-matched)
    """
    pytest.skip("Wave-2 references.py implementation not yet present")


def test_label_match_contradiction_low_confidence():
    """D-REF3: label-match-only contradiction emits as 'low' confidence_tier.

    When no confirmed cross-reference edge connects the two values' locations,
    but the label/identifier match suggests a contradiction, emit as low-confidence.
    """
    pytest.skip("Wave-2 references.py implementation not yet present")
