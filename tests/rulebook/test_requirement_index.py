"""Tests for src/rulebook/requirement_index.py -- RequirementEntry model, the D-RI1(1) loader
gate (byte-exact provenance re-open + D-05 family-registry membership), submission_profile, and
enumerate_requirements (D-RB4 UNION resolution) -- Plan 02-06, RULES-05.

Task 1 tests (this file, everything except `test_every_absence_family_deficiency_has_firing_entry`)
are fully offline (D-RB6) and independent of Task 2: every loader-gate case builds its own
NormalizedText via `ingest.normalize.normalize` + a real `mint_span`, monkeypatching
`rulebook_nt_for`/`edges.get_edges` in place of touching the shared `data/` store or Task 2's
real committed `requirement_index.yaml` -- these tests pass whether or not Task 2 has run yet.

Task 2 adds `test_every_absence_family_deficiency_has_firing_entry`, which DOES load the real
committed `src/rulebook/requirement_index.yaml` (via a bare `load_requirement_index()` call) and
the real edges populated against the vendored rulebook store from Plan 02-03.
"""
from __future__ import annotations

import pytest
import yaml

import rulebook.requirement_index as ri
from ingest.anchors import HashMismatch, mint_span
from ingest.manifest import CoverageManifest, DocEntry
from ingest.normalize import normalize
from schemas.documents import DocClassification, SpanID
from tools.errors import ToolRejected

# --- fixtures / helpers ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_load_requirement_index_cache():
    """load_requirement_index is @lru_cache(maxsize=1) -- clear before/after every test so one
    test's cached result (or a stale path-keyed entry) never leaks into the next."""
    ri.load_requirement_index.cache_clear()
    yield
    ri.load_requirement_index.cache_clear()


def _write_index_yaml(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "requirement_index.yaml"
    path.write_text(yaml.safe_dump(rows, sort_keys=False))
    return str(path)


def _fixture_span(doc_id: str = "ich-Q2-R2", text: str = "Specificity should be demonstrated."):
    """A real NormalizedText + a real, byte-exact SpanID over its whole canonical text (mirrors
    tests/rulebook/conftest.py's fixture_chunk discipline, without touching the shared store)."""
    nt = normalize(text)
    span = mint_span(nt.canonical, 0, len(nt.canonical), doc_id, nt.normalizer_version)
    return nt, span


def _valid_row(entry_id: str = "Q2-SPECIFICITY", family: str = "3.2.S.4.3", span: SpanID | None = None) -> dict:
    if span is None:
        _, span = _fixture_span()
    return {
        "id": entry_id,
        "family": family,
        "citation": "ICH Q2(R2) -- Specificity",
        "trigger": "Analytical method validation must demonstrate specificity.",
        "provenance_span_id": span.model_dump(),
    }


def _doc_entry(family_guess: str, doc_id: str = "doc-1") -> DocEntry:
    return DocEntry(
        doc_id=doc_id,
        filename=f"{doc_id}.pdf",
        content_hash="deadbeef",
        classification=DocClassification(family_guess=family_guess),
    )


def _requirement_entry(entry_id: str, family: str) -> ri.RequirementEntry:
    _, span = _fixture_span()
    return ri.RequirementEntry(
        id=entry_id, family=family, citation="citation", trigger=f"trigger for {entry_id}",
        provenance_span_id=span,
    )


# --- RequirementEntry model -----------------------------------------------------------------


def test_requirement_entry_validates():
    _, span = _fixture_span()
    entry = ri.RequirementEntry(
        id="Q2-SPECIFICITY",
        family="3.2.S.4.3",
        citation="ICH Q2(R2) -- Specificity",
        trigger="Analytical method validation must demonstrate specificity.",
        provenance_span_id=span,
    )
    assert entry.id == "Q2-SPECIFICITY"
    assert entry.family == "3.2.S.4.3"
    assert entry.provenance_span_id == span


def test_requirement_entry_round_trips_through_dump_and_validate():
    _, span = _fixture_span()
    entry = ri.RequirementEntry(
        id="Q2-SPECIFICITY", family="3.2.S.4.3", citation="c", trigger="t", provenance_span_id=span
    )
    restored = ri.RequirementEntry.model_validate(entry.model_dump())
    assert restored == entry


# --- load_requirement_index: the D-RI1(1) loader gate ---------------------------------------


def test_load_requirement_index_rejects_unregistered_family(tmp_path, monkeypatch):
    nt, span = _fixture_span()
    monkeypatch.setattr(ri, "rulebook_nt_for", lambda doc_id: nt)
    path = _write_index_yaml(tmp_path, [_valid_row(family="NOT-A-REAL-FAMILY", span=span)])

    with pytest.raises(ValueError, match="NOT-A-REAL-FAMILY"):
        ri.load_requirement_index(path=path)


def test_load_requirement_index_family_error_names_the_offending_entry_id(tmp_path, monkeypatch):
    nt, span = _fixture_span()
    monkeypatch.setattr(ri, "rulebook_nt_for", lambda doc_id: nt)
    path = _write_index_yaml(tmp_path, [_valid_row(entry_id="BOGUS-ENTRY", family="nope-family", span=span)])

    with pytest.raises(ValueError, match="BOGUS-ENTRY"):
        ri.load_requirement_index(path=path)


def test_load_requirement_index_rejects_provenance_doc_not_in_rulebook_store(tmp_path, monkeypatch):
    _, span = _fixture_span(doc_id="does-not-exist-in-store")
    monkeypatch.setattr(ri, "rulebook_nt_for", lambda doc_id: None)
    path = _write_index_yaml(tmp_path, [_valid_row(span=span)])

    with pytest.raises(ValueError, match="not found in the rulebook store"):
        ri.load_requirement_index(path=path)


def test_load_requirement_index_rejects_non_byte_exact_provenance(tmp_path, monkeypatch):
    """Tampers the span's hash after minting -- the exact fabrication/drift scenario D-21/D-RI1
    exists to catch. open_span must raise (HashMismatch propagates -- the behavior spec allows
    either a raw HashMismatch or a wrapped ValueError; this module propagates HashMismatch)."""
    nt, span = _fixture_span()
    tampered = span.model_copy(update={"hash": "deadbeefdeadbeef"})
    monkeypatch.setattr(ri, "rulebook_nt_for", lambda doc_id: nt)
    path = _write_index_yaml(tmp_path, [_valid_row(span=tampered)])

    with pytest.raises(HashMismatch):
        ri.load_requirement_index(path=path)


def test_load_requirement_index_all_valid_returns_matching_entries(tmp_path, monkeypatch):
    nt, span = _fixture_span()
    monkeypatch.setattr(ri, "rulebook_nt_for", lambda doc_id: nt)
    path = _write_index_yaml(tmp_path, [_valid_row(span=span)])

    result = ri.load_requirement_index(path=path)

    assert len(result) == 1
    assert isinstance(result[0], ri.RequirementEntry)
    assert result[0].id == "Q2-SPECIFICITY"
    assert result[0].provenance_span_id == span


def test_load_requirement_index_multiple_valid_rows_all_returned(tmp_path, monkeypatch):
    nt1, span1 = _fixture_span(doc_id="doc-1", text="Specificity should be demonstrated.")
    nt2, span2 = _fixture_span(doc_id="doc-2", text="Linearity should be assessed across the reportable range.")
    nt_by_doc = {"doc-1": nt1, "doc-2": nt2}
    monkeypatch.setattr(ri, "rulebook_nt_for", lambda doc_id: nt_by_doc.get(doc_id))
    path = _write_index_yaml(
        tmp_path,
        [
            _valid_row(entry_id="Q2-SPECIFICITY", span=span1),
            _valid_row(entry_id="Q2-LINEARITY", span=span2),
        ],
    )

    result = ri.load_requirement_index(path=path)

    assert {e.id for e in result} == {"Q2-SPECIFICITY", "Q2-LINEARITY"}


def test_load_requirement_index_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")

    assert ri.load_requirement_index(path=str(path)) == []


# --- submission_profile: content-derived, never path/folder-driven (D-09) -------------------


def test_submission_profile_drug_substance_only():
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3")])
    assert ri.submission_profile(manifest) == {"drug_substance"}


def test_submission_profile_drug_product_only():
    manifest = CoverageManifest(documents=[_doc_entry("3.2.P.7")])
    assert ri.submission_profile(manifest) == {"drug_product"}


def test_submission_profile_union_of_both():
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3", "d1"), _doc_entry("3.2.P.7", "d2")])
    assert ri.submission_profile(manifest) == {"drug_substance", "drug_product"}


def test_submission_profile_empty_manifest_returns_empty_set():
    assert ri.submission_profile(CoverageManifest()) == set()


def test_submission_profile_unclassified_documents_return_empty_set():
    manifest = CoverageManifest(documents=[DocEntry(doc_id="d1", filename="d1.pdf", content_hash="x")])
    assert ri.submission_profile(manifest) == set()


# --- enumerate_requirements: D-RI2 applicability resolution ---------------------------------


def test_enumerate_requirements_rejects_unregistered_family():
    manifest = CoverageManifest()

    result = ri.enumerate_requirements(manifest, family="NOT-REGISTERED")

    assert isinstance(result, ToolRejected)
    assert result.tool == "read_guideline"
    assert result.reason_code == "family_not_in_registry"


def test_enumerate_requirements_never_silently_empty_on_bad_family():
    """An invalid family is a typed rejection, never a silent empty list (behavior spec)."""
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3")])

    result = ri.enumerate_requirements(manifest, family="also-not-registered")

    assert isinstance(result, ToolRejected)


def test_enumerate_requirements_direct_family_match(monkeypatch):
    entry = _requirement_entry("Q2-SPECIFICITY", "3.2.S.4.3")
    monkeypatch.setattr(ri, "load_requirement_index", lambda: [entry])

    def fake_get_edges(src_id=None, dst_id=None, edge_type=None, db_path=None):
        rows = [("3.2.S.4.3", "Q2-SPECIFICITY", "family_requires_requirement", "prov")]
        return [
            r for r in rows
            if (src_id is None or r[0] == src_id) and (edge_type is None or r[2] == edge_type)
        ]

    monkeypatch.setattr(ri.edges, "get_edges", fake_get_edges)
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3")])

    result = ri.enumerate_requirements(manifest)

    assert result == [entry]


def test_enumerate_requirements_fires_for_family_with_zero_classified_documents_via_profile_closure(monkeypatch):
    """The absence mechanism (D-RB4): a family with ZERO classified documents in the manifest
    still surfaces its requirement, via the profile_requires_family -> family_requires_requirement
    UNION -- proving this is structural, not merely a direct `.family` filter over present docs."""
    entry = _requirement_entry("CFR-211166-STABILITY-PROGRAM", "3.2.P.7")
    monkeypatch.setattr(ri, "load_requirement_index", lambda: [entry])

    def fake_get_edges(src_id=None, dst_id=None, edge_type=None, db_path=None):
        rows = [
            ("drug_product", "3.2.P.7", "profile_requires_family", "prov1"),
            ("3.2.P.7", "CFR-211166-STABILITY-PROGRAM", "family_requires_requirement", "prov2"),
        ]
        return [
            r for r in rows
            if (src_id is None or r[0] == src_id)
            and (dst_id is None or r[1] == dst_id)
            and (edge_type is None or r[2] == edge_type)
        ]

    monkeypatch.setattr(ri.edges, "get_edges", fake_get_edges)
    # manifest has a 3.2.P.1 document (-> drug_product profile) but ZERO 3.2.P.7 documents.
    manifest = CoverageManifest(documents=[_doc_entry("3.2.P.1")])
    assert all(d.classification.family_guess != "3.2.P.7" for d in manifest.documents)

    result = ri.enumerate_requirements(manifest)

    assert result == [entry]


def test_enumerate_requirements_family_filter_narrows_result(monkeypatch):
    e1 = _requirement_entry("Q2-SPECIFICITY", "3.2.S.4.3")
    e2 = _requirement_entry("CFR-211166-STABILITY-PROGRAM", "3.2.P.7")
    monkeypatch.setattr(ri, "load_requirement_index", lambda: [e1, e2])

    def fake_get_edges(src_id=None, dst_id=None, edge_type=None, db_path=None):
        rows = [
            ("3.2.S.4.3", "Q2-SPECIFICITY", "family_requires_requirement", "p1"),
            ("3.2.P.7", "CFR-211166-STABILITY-PROGRAM", "family_requires_requirement", "p2"),
        ]
        return [
            r for r in rows
            if (src_id is None or r[0] == src_id) and (edge_type is None or r[2] == edge_type)
        ]

    monkeypatch.setattr(ri.edges, "get_edges", fake_get_edges)
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3", "d1"), _doc_entry("3.2.P.7", "d2")])

    result = ri.enumerate_requirements(manifest, family="3.2.S.4.3")

    assert [e.id for e in result] == ["Q2-SPECIFICITY"]


def test_enumerate_requirements_empty_manifest_and_no_edges_returns_empty_list(monkeypatch):
    monkeypatch.setattr(ri, "load_requirement_index", lambda: [])
    monkeypatch.setattr(ri.edges, "get_edges", lambda **kwargs: [])

    result = ri.enumerate_requirements(CoverageManifest())

    assert result == []


def test_enumerate_requirements_results_sorted_by_id(monkeypatch):
    e_b = _requirement_entry("Q2-LINEARITY", "3.2.S.4.3")
    e_a = _requirement_entry("Q2-ACCURACY", "3.2.S.4.3")
    monkeypatch.setattr(ri, "load_requirement_index", lambda: [e_b, e_a])

    def fake_get_edges(src_id=None, dst_id=None, edge_type=None, db_path=None):
        rows = [
            ("3.2.S.4.3", "Q2-LINEARITY", "family_requires_requirement", "p1"),
            ("3.2.S.4.3", "Q2-ACCURACY", "family_requires_requirement", "p2"),
        ]
        return [
            r for r in rows
            if (src_id is None or r[0] == src_id) and (edge_type is None or r[2] == edge_type)
        ]

    monkeypatch.setattr(ri.edges, "get_edges", fake_get_edges)
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3")])

    result = ri.enumerate_requirements(manifest)

    assert [e.id for e in result] == ["Q2-ACCURACY", "Q2-LINEARITY"]
