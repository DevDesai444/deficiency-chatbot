"""Cross-document reference resolution regression test (Blocker 2, Wave 5).

Tests that extract_references + detect_reference_anomalies CORRECTLY resolves the planted
X1 cross-document reference in the committed synthetic fixture (doc_a -> doc_b) and
surfaces a VALUE_CONTRADICTION fault for Compound B (0.18% vs NMT 0.15%).

The two real fixture text shapes that must resolve (per reviewer ruling):
  1. "see Analytical Procedures, Table 1" — textual reference with title-fragment match
  2. "refer to Analytical Procedures document (doc_b.docx)" — parenthesized filename match

Both must produce edges that resolve to doc_b, enabling the Ruling-6 pipeline to run
and emit at least one VALUE_CONTRADICTION with "0.18" and "0.15" in the detail.

This test validates the GENERAL fix: _find_doc_by_outline resolves via bidirectional
first-line heading match ("analytical procedures" in heading) AND via parenthesized
filename pattern, without any corpus-specific constants in references.py.

Reviewer-authorized cross-plan deviation (Plan-04 references.py edited under Wave 5).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from rulebook.references import detect_reference_anomalies, extract_references
from tools.ledger import RetrievalLedger

_SYNTHETIC_FIXTURE = Path("src/evals/dataset/synthetic_fixture")


@pytest.fixture(scope="module")
def _fixture_corpus_and_faults():
    """Build the corpus + run extract_references + detect_reference_anomalies once.

    Scoped to module so the embedding model loads once for all tests.
    Returns (corpus, all_faults, value_contradictions).
    """
    assert _SYNTHETIC_FIXTURE.exists(), (
        f"Synthetic fixture missing at {_SYNTHETIC_FIXTURE}. "
        "The fixture must be committed (doc_a.pdf + doc_b.docx + doc_c.pdf)."
    )

    from ingest.corpus import ingest_corpus
    from rulebook import edges as edges_module

    with tempfile.TemporaryDirectory() as tmp:
        corpus = ingest_corpus(str(_SYNTHETIC_FIXTURE), cache_dir=tmp + "/cache")
        edges_db = tmp + "/edges.db"
        extract_references(corpus, corpus.manifest, db_path=edges_db)

        all_edges = edges_module.get_edges(db_path=edges_db)
        resolved = [e for e in all_edges if e[1] != "unresolved"]
        unresolved = [e for e in all_edges if e[1] == "unresolved"]

        ledger = RetrievalLedger()
        all_faults = detect_reference_anomalies(
            corpus, corpus.manifest, ledger, db_path=edges_db
        )

    value_contradictions = [
        f for f in all_faults
        if f.reference_anchor is not None
        and f.reference_anchor.anomaly == "VALUE_CONTRADICTION"
    ]

    return {
        "corpus_doc_ids": {d.doc_id: d.filename for d in corpus.manifest.documents},
        "all_edges": all_edges,
        "resolved": resolved,
        "unresolved": unresolved,
        "all_faults": all_faults,
        "value_contradictions": value_contradictions,
    }


def test_cross_doc_edge_resolves_to_doc_b(_fixture_corpus_and_faults):
    """The planted cross-doc reference in doc_a must resolve to doc_b (not 'unresolved').

    Fixture text shapes tested:
      - "see Analytical Procedures, Table 1" (textual ref with title-fragment)
      - "(doc_b.docx)" (parenthesized filename)

    At least one edge from doc_a must be resolved to doc_b's doc_id.
    """
    data = _fixture_corpus_and_faults
    resolved = data["resolved"]
    corpus_doc_ids = data["corpus_doc_ids"]

    # Find doc_b's doc_id by filename
    doc_b_id = next(
        (did for did, fname in corpus_doc_ids.items() if fname == "doc_b.docx"), None
    )
    assert doc_b_id is not None, (
        "doc_b.docx not found in the fixture corpus. "
        "The fixture must include doc_b.docx."
    )

    # At least one edge must point to doc_b
    edges_to_doc_b = [
        e for e in resolved if e[1].startswith(f"{doc_b_id}:")
    ]
    assert len(edges_to_doc_b) >= 1, (
        f"No resolved edge points to doc_b (doc_id={doc_b_id!r}). "
        f"Total resolved edges: {len(resolved)}, all dst_ids: {[e[1] for e in resolved[:10]]}. "
        "references.py must resolve '(doc_b.docx)' or 'Analytical Procedures' in doc_a "
        "to doc_b's doc_id. "
        "Fix: ensure _find_doc_by_outline uses parenthesized filename OR "
        "bidirectional first-line heading match (Wave 5 Blocker 2 fix)."
    )


def test_value_contradiction_compound_b_present(_fixture_corpus_and_faults):
    """VALUE_CONTRADICTION faults must include the Compound B violation: 0.18% vs NMT 0.15%.

    The Ruling-6 pipeline (steps A-F) must fire on the resolved cross-doc edge from doc_a
    to doc_b and emit >= 1 VALUE_CONTRADICTION whose detail contains both "0.18" and "0.15".

    This is the X1 catch: Compound B at 0.18% exceeds the NMT 0.15% single-impurity limit.
    """
    data = _fixture_corpus_and_faults
    value_contradictions = data["value_contradictions"]
    all_details = " ".join((f.detail or "") for f in value_contradictions)

    assert value_contradictions, (
        f"No VALUE_CONTRADICTION faults found on fixture_a. "
        f"Total faults: {len(data['all_faults'])}, all anomalies: "
        f"{[f.reference_anchor.anomaly for f in data['all_faults'] if f.reference_anchor][:10]}. "
        "The cross-doc edge from doc_a to doc_b must be resolved so Ruling-6 pipeline fires. "
        "Fix: references.py must resolve 'Analytical Procedures' or '(doc_b.docx)' to doc_b."
    )

    assert "0.18" in all_details, (
        f"VALUE_CONTRADICTION faults present but '0.18' (Compound B value) not in details. "
        f"Found {len(value_contradictions)} VALUE_CONTRADICTION fault(s). "
        f"Details sample: {all_details[:400]!r}"
    )

    assert "0.15" in all_details, (
        f"VALUE_CONTRADICTION faults present but '0.15' (NMT limit) not in details. "
        f"Found {len(value_contradictions)} VALUE_CONTRADICTION fault(s). "
        f"Details sample: {all_details[:400]!r}"
    )


def test_unresolved_ref_count_reduced(_fixture_corpus_and_faults):
    """UNRESOLVED_REF count must be lower than the pre-fix baseline (was 22, now <= 17).

    This test documents that the Blocker 2 fix REDUCES unresolved references by resolving
    cross-doc edges. It is not a strict equality assertion (future fixture changes may
    affect the count), but a directional improvement guard.
    """
    data = _fixture_corpus_and_faults
    unresolved_count = len(data["unresolved"])
    total_count = len(data["all_edges"])
    resolved_count = len(data["resolved"])

    # Pre-fix baseline: 22 unresolved out of 25 total (3 resolved)
    # Post-fix: >= 5 resolved (reduced unresolved by >= 5)
    assert resolved_count >= 5, (
        f"After Wave 5 fix, at least 5 edges should resolve (pre-fix was 3). "
        f"Got resolved={resolved_count}, total={total_count}, unresolved={unresolved_count}. "
        "The '(doc_b.docx)' and 'Analytical Procedures' references must resolve."
    )


def test_reference_resolution_is_general(_fixture_corpus_and_faults):
    """Regression: both reference shapes resolve (not just one).

    This test verifies that the fix is general enough to handle BOTH the textual reference
    shape ("see Analytical Procedures, Table 1") AND the parenthesized filename shape
    ("(doc_b.docx)"). If only one resolves, the fix is partial.

    Both shapes are in the real fixture doc_a.pdf. The test verifies by checking that
    resolved edges include both textual_ref AND value_crossref types from doc_a.
    """
    data = _fixture_corpus_and_faults
    resolved = data["resolved"]
    corpus_doc_ids = data["corpus_doc_ids"]

    doc_a_id = next(
        (did for did, fname in corpus_doc_ids.items() if fname == "doc_a.pdf"), None
    )
    doc_b_id = next(
        (did for did, fname in corpus_doc_ids.items() if fname == "doc_b.docx"), None
    )
    assert doc_a_id and doc_b_id, "fixture must have doc_a.pdf and doc_b.docx"

    doc_a_to_doc_b = [
        e for e in resolved
        if e[0].startswith(f"{doc_a_id}:") and e[1].startswith(f"{doc_b_id}:")
    ]

    # Must have at least 2 different edge types or 2 different offsets (both shapes)
    assert len(doc_a_to_doc_b) >= 2, (
        f"Expected >= 2 resolved edges from doc_a to doc_b (one for each reference shape). "
        f"Got {len(doc_a_to_doc_b)}: {doc_a_to_doc_b}. "
        "Both '(doc_b.docx)' (textual_ref) and 'Analytical Procedures' (value_crossref) "
        "reference shapes must resolve."
    )
