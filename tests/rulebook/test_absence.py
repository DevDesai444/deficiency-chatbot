"""Composition + behavior tests for the deterministic absence pass (RECALL-01, Plan 04-03).

Every test drives the REAL Phase-1/Plan-02 primitives offline (D-RB6): a self-contained rulebook
store built from the committed `rulebook/**` snapshot (never Databricks, never the shared `data/`
store) plus tmp_path-scoped corpora. The whole-section (D-SEC1) cases are the class the main eval
structurally cannot measure -- omit a REQUIRED family -> absence fires; omit a NON-REQUIRED family
-> nothing fires -- so they are carried here as constructed composition tests.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import rulebook.requirement_index as ri
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest, DocEntry, OutlineEntry
from rulebook.absence import enumerate_absences
from schemas.documents import DocClassification
from schemas.faults import ComplianceVerdict, Fault
from tools.ledger import RetrievalLedger

# A threshold safely ABOVE the reciprocal_rank_fusion ceiling (2/(60+1) = 0.0328): the
# recall-biased bar (D-ABS2) at which every applicable requirement over-emits. Tests assert
# BEHAVIOR at a fixed bar; the committed absence_threshold.json is the tuned/recorded value.
_OVER_EMIT_THRESHOLD = 0.04


@pytest.fixture(scope="module")
def _self_contained_rulebook_store():
    """Build the real local rulebook store + requirement edges from the committed snapshot.

    Mirrors tests/rulebook/test_requirement_index_integration.py: offline (build_* with
    update_manifest=False), never touches Databricks or rewrites rulebook/manifest.yaml.
    """
    from rulebook.build import build_ecfr, build_fda, build_ich

    for rows in (
        build_ecfr(update_manifest=False),
        build_ich(update_manifest=False),
        build_fda(update_manifest=False),
    ):
        errors = [r for r in rows if "error" in r]
        assert not errors, f"rulebook build fixture hit vendoring errors: {errors}"
    ri.load_requirement_index.cache_clear()
    ri.build_requirement_edges()
    # NOTE: no rebuild_local_index() here. The absence pass never queries the rulebook FAISS index
    # (rulebook_search); its retrieval is search_corpus over the EPHEMERAL SUBMISSION index, which
    # builds its own embeddings from the corpus. Embedding all 221 rulebook chunks under torch/CPU
    # is both unnecessary and the source of a backend segfault in this test environment.
    yield
    ri.load_requirement_index.cache_clear()


def _corpus_with_families(tmp_path, families: list[str]) -> CorpusIndex:
    """Construct a CorpusIndex whose manifest classifies one synthetic document into each of
    `families`, with NO cached text (so search_corpus finds nothing -> every applicable
    requirement is sub-threshold). Used for the whole-section composition tests, where the point
    is the manifest's PROFILE + which families have documents, not retrieval content."""
    documents = [
        DocEntry(
            doc_id=f"doc-{i}",
            filename=f"doc-{i}.pdf",
            content_hash=f"hash-{i}",
            status="parsed",
            classification=DocClassification(family_guess=fam, label=fam, confidence=1.0),
            outline=[],
        )
        for i, fam in enumerate(families)
    ]
    manifest = CoverageManifest(documents=documents)
    # cache_dir points at an empty tmp dir: cached_entry returns None, search_corpus returns [].
    return CorpusIndex(root=str(tmp_path), cache_dir=str(tmp_path / "empty-cache"), manifest=manifest)


def _ingest_docx(tmp_path, name: str) -> CorpusIndex:
    """Ingest the committed mini_spec.docx into a tmp corpus (real substrate, offline)."""
    import shutil

    from ingest.corpus import ingest_corpus

    src = Path("src/evals/dataset/docs/mini_spec.docx")
    if not src.exists():
        pytest.skip(f"missing committed docx fixture: {src}")
    root = tmp_path / "corpus"
    root.mkdir()
    shutil.copy2(src, root / name)
    return ingest_corpus(root, cache_dir=str(tmp_path / "ingest-cache"))


def test_never_addressed_requirement_emits_grounded_gap(
    tmp_path, _self_contained_rulebook_store
):
    """A submission that never addresses an applicable requirement -> >=1 absence Fault with
    verdict==GAP and a re-derivable CoverageAbsenceAnchor (the requirement-level D-ABS1 path)."""
    corpus = _ingest_docx(tmp_path, "mini_spec.docx")
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, corpus.manifest, ledger, threshold=_OVER_EMIT_THRESHOLD,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    assert faults, "expected at least one over-emitted absence candidate"
    for f in faults:
        assert isinstance(f, Fault)
        assert f.verdict == ComplianceVerdict.GAP
        assert f.submission_span_id is None
        # re-derivable anchor: enumerate inputs present (D-GATE2)
        assert f.absence_anchor is not None
        assert f.absence_anchor.requirement_id
        assert f.absence_anchor.family
        assert f.rule_span_id is not None  # rule half grounded byte-exact


def test_strong_hit_requirement_is_not_emitted(tmp_path, _self_contained_rulebook_store):
    """A requirement whose trigger retrieves a strong (above-threshold) hit is NOT emitted (the
    search-and-found path). With threshold 0.0, no requirement can be sub-threshold on retrieval,
    so the ONLY candidates are whole-section zero-document families -- proving the retrieval-level
    over-emit is gated on the score, not fired unconditionally."""
    corpus = _ingest_docx(tmp_path, "mini_spec.docx")
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, corpus.manifest, ledger, threshold=0.0,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    # threshold 0.0: every real retrieval hit (score > 0) is above-threshold, so no requirement
    # with a document in its family over-emits. Any candidate must be a zero-document family.
    families_present = {
        d.classification.family_guess for d in corpus.manifest.documents if d.classification
    }
    for f in faults:
        assert f.absence_anchor.family not in families_present, (
            "at threshold 0.0 only zero-document families may fire, not a family with a doc"
        )


def test_whole_section_required_family_omitted_fires(tmp_path, _self_contained_rulebook_store):
    """D-SEC1: a corpus that exhibits the drug_substance profile (a 3.2.S.* document) but OMITS a
    required spec family (3.2.S.4.1 has zero documents) fires whole-section absence for that
    family. The drug_substance profile requires 3.2.S.4.1 via a profile_requires_family edge."""
    # Present family: 3.2.S.2 (drug_substance profile) -- but NOT 3.2.S.4.1 (a required spec family)
    corpus = _corpus_with_families(tmp_path, ["3.2.S.2"])
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, corpus.manifest, ledger, threshold=_OVER_EMIT_THRESHOLD,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    fired_families = {f.absence_anchor.family for f in faults}
    assert "3.2.S.4.1" in fired_families, (
        f"required-but-absent family 3.2.S.4.1 should fire whole-section absence; got {fired_families}"
    )
    # every candidate is grounded (GAP, rule span, re-derivable anchor)
    for f in faults:
        assert f.verdict == ComplianceVerdict.GAP
        assert f.rule_span_id is not None
        assert f.absence_anchor.requirement_id and f.absence_anchor.family


def test_whole_section_fires_supplementally_linked_requirements(
    tmp_path, _self_contained_rulebook_store
):
    """CR-01 regression: when a drug_substance submission OMITS the required spec family 3.2.S.4.1
    entirely, the whole-section pass must fire EVERY requirement edge-linked to that family -- not
    only entries whose native `.family` is 3.2.S.4.1. `CFR-211160B-SOUND-BASIS` and
    `CFR-211194-CALCULATIONS` are edge-linked to 3.2.S.4.1 via `_SUPPLEMENTAL_FAMILY_REQUIREMENT_LINKS`
    while their native `.family` is 3.2.S.5, so the old `.family`-only selection silently dropped them
    (a recall miss on the exact omitted-section path D-SEC1 exists to catch). The fixed pass mirrors
    enumerate_requirements' edge-driven applicability, so they surface as whole-section candidates.

    Threshold 0.0 ISOLATES the whole-section branch: the empty-cache corpus makes search_corpus
    return [] (top_score 0.0), so `0.0 >= 0.0` short-circuits the requirement-level over-emit for
    every requirement -- the ONLY candidates that can fire are whole-section zero-document families.
    An assertion that these CFR entries fire UNDER family 3.2.S.4.1 therefore witnesses the
    whole-section selection specifically: it fails on the old `.family`-only generator (their native
    `.family` 3.2.S.5 excludes them from the 3.2.S.4.1 candidate set) and passes on the edge-driven
    fix."""
    # drug_substance profile present (a 3.2.S.* document) but 3.2.S.4.1 has ZERO documents.
    corpus = _corpus_with_families(tmp_path, ["3.2.S.2"])
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, corpus.manifest, ledger, threshold=0.0,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    # requirement ids that fired for the omitted 3.2.S.4.1 whole-section family
    fired_for_s41 = {
        f.absence_anchor.requirement_id
        for f in faults
        if f.absence_anchor.family == "3.2.S.4.1"
    }
    # sanity: enumerate_requirements DOES link these two entries to 3.2.S.4.1 (edge-driven truth)
    applicable_for_s41 = ri.enumerate_requirements(corpus.manifest, family="3.2.S.4.1")
    linked_ids = {e.id for e in applicable_for_s41}
    assert {"CFR-211160B-SOUND-BASIS", "CFR-211194-CALCULATIONS"} <= linked_ids, (
        "fixture precondition: both CFR entries must be edge-linked to 3.2.S.4.1"
    )
    assert {"CFR-211160B-SOUND-BASIS", "CFR-211194-CALCULATIONS"} <= fired_for_s41, (
        "supplementally-linked CFR entries must fire whole-section absence for the omitted 3.2.S.4.1 "
        f"family (old .family-only selection dropped them); got fired_for_s41={fired_for_s41}"
    )
    for f in faults:
        assert f.verdict == ComplianceVerdict.GAP
        assert f.rule_span_id is not None


def test_whole_section_non_required_family_omitted_is_silent(
    tmp_path, _self_contained_rulebook_store
):
    """D-SEC2 false-absence guard: a corpus whose profile does NOT require family 3.2.P.5 (no
    drug_product document present) never fires whole-section absence for 3.2.P.5 -- the profile
    gate. Only a drug_substance profile is exhibited, which requires 3.2.S.* families, not P.*."""
    corpus = _corpus_with_families(tmp_path, ["3.2.S.2"])  # drug_substance only, no drug_product
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, corpus.manifest, ledger, threshold=_OVER_EMIT_THRESHOLD,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    fired_families = {f.absence_anchor.family for f in faults}
    assert "3.2.P.5" not in fired_families, (
        f"non-required family 3.2.P.5 must NOT fire (profile-gate, D-SEC2); got {fired_families}"
    )


def test_rejected_applicability_returns_empty(tmp_path, _self_contained_rulebook_store):
    """A manifest with no classified documents yields no profile and no applicable requirements ->
    the pass returns [] (never raises), the ToolRejected/empty-applicability propagation path."""
    manifest = CoverageManifest(documents=[])
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=str(tmp_path / "empty"), manifest=manifest)
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, manifest, ledger, threshold=_OVER_EMIT_THRESHOLD,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    assert faults == []
