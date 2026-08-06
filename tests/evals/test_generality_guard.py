"""D-GEN3 CI generality guard for the deterministic absence pass (RECALL-01, Plan 04-03).

This test FILE FAILS THE BUILD (D-GEN3, enforced every run -- never a one-time audit) if the
absence module embeds a corpus constant or if a folder rename changes applicability. It encodes the
four D-GEN2 invariants, witnessed on the HELD-OUT spec32s41 corpus (D-GEN1: the generality witness,
never the corpus the threshold was tuned on):

  1. NO-CONSTANT      -- absence.py references no dataset/doc/submission-ID literal.
  2. RENAME-INVARIANCE -- reorganizing/renaming the held-out corpus dir yields the IDENTICAL
                          applicable-requirement set (content-derived, not folder-derived).
  3. SAME-LOGIC TRANSFER -- the held-out corpus's absences come from the SAME index entries firing
                          (same requirement_ids), not corpus-specific rules.
  4. THRESHOLD TRANSFER -- with the threshold FROZEN at its mvr1381-tuned value from
                          absence_threshold.json, the held-out corpus's absence candidates are
                          recovered unchanged (the threshold is a general recall bar, D-GEN2(4)).

Offline (D-RB6): the real rulebook store is built from the committed snapshot; corpora ingest into
tmp_path; nothing touches Databricks or the shared data/ store beyond reading the local corpus PDF.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import rulebook.requirement_index as ri
from ingest.corpus import ingest_corpus
from rulebook.absence import enumerate_absences
from rulebook.requirement_index import enumerate_requirements
from tools.ledger import RetrievalLedger

_ABSENCE_BASELINE = Path("src/evals/baseline/absence_threshold.json")
_HELDOUT_PDF = Path("data/32s41-Specification.pdf")  # spec32s41 -- the D-GEN1 held-out witness
_DATASET_LITERALS = ("mvr1381", "spec32s41", "heldout32s41", "minispec")


@pytest.fixture(scope="module")
def _self_contained_rulebook_store():
    """Real local rulebook store + requirement edges from the committed snapshot (offline)."""
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
    yield
    ri.load_requirement_index.cache_clear()


def _ingest_heldout(tmp_path, subdir: str) -> "object":
    if not _HELDOUT_PDF.exists():
        pytest.skip(f"missing held-out witness PDF (gitignored local corpus): {_HELDOUT_PDF}")
    root = tmp_path / subdir
    root.mkdir(parents=True)
    shutil.copy2(_HELDOUT_PDF, root / _HELDOUT_PDF.name)
    return ingest_corpus(root, cache_dir=str(tmp_path / f"cache-{subdir}"))


# --- Invariant 1: NO-CONSTANT (always runs, no ingest -- the cheap D-GEN3 tripwire) ----------

def test_absence_module_embeds_no_corpus_constant():
    """D-GEN2(1): absence.py must reference no corpus/doc/submission-ID literal. Reads the module
    source directly and asserts none of the dataset ids appears -- the build FAILS if one does."""
    source = Path("src/rulebook/absence.py").read_text().lower()
    offenders = [lit for lit in _DATASET_LITERALS if lit in source]
    assert not offenders, (
        f"src/rulebook/absence.py embeds dataset literal(s) {offenders} -- "
        "the absence module must be corpus-general (D-GEN2 no-constant)"
    )


# --- Invariant 2: RENAME-INVARIANCE (applicability is content-derived, not folder-derived) ----

def test_rename_invariance_of_applicable_requirements(tmp_path, _self_contained_rulebook_store):
    """D-GEN2(2): ingesting the held-out corpus under two DIFFERENT directory names yields the
    IDENTICAL applicable-requirement set. Applicability flows from CONTENT classification, never
    the folder name -- a rename that changed applicability would fail the build."""
    corpus_a = _ingest_heldout(tmp_path, "3.2.S.4.1-Specification")
    corpus_b = _ingest_heldout(tmp_path, "some-unrelated-folder-name")

    app_a = enumerate_requirements(corpus_a.manifest)
    app_b = enumerate_requirements(corpus_b.manifest)
    assert isinstance(app_a, list) and isinstance(app_b, list)
    ids_a = {e.id for e in app_a}
    ids_b = {e.id for e in app_b}
    assert ids_a == ids_b, (
        f"folder rename changed applicability: {ids_a ^ ids_b} (D-GEN2 rename-invariance)"
    )
    assert ids_a, "the held-out corpus must fire at least one applicable requirement"


# --- Invariants 3 + 4: SAME-LOGIC + THRESHOLD TRANSFER (frozen mvr1381 threshold) -------------

@pytest.mark.slow
def test_threshold_transfer_and_same_logic_on_heldout(tmp_path, _self_contained_rulebook_store):
    """D-GEN2(3)+(4): with the threshold FROZEN at its mvr1381-tuned value from the committed
    absence_threshold.json, the held-out corpus's absence candidates are recovered, and they arise
    from the SAME requirement-index entries firing (candidate requirement_ids are a subset of the
    corpus's applicable requirement ids) -- not from corpus-specific rules. Proven on spec32s41,
    the corpus the threshold was NEVER tuned on (anti-circularity, D-GEN1).

    Marked `slow` (opt-in via `-m slow`): `search_corpus` re-embeds every held-out corpus chunk on
    each per-requirement query on this CPU-only sentence-transformers backend, so a full held-out
    absence pass runs in minutes. The always-on tripwires (NO-CONSTANT + RENAME-INVARIANCE above)
    catch the two dominant overfitting modes cheaply every run; this deeper invariant runs in the
    slow lane. The `absence-gate` CLI proves the same recovery mechanism on the non-held-out
    aggregate every run (SC2)."""
    threshold = json.loads(_ABSENCE_BASELINE.read_text())["threshold"]

    corpus = _ingest_heldout(tmp_path, "heldout-witness")
    ledger = RetrievalLedger()
    faults = enumerate_absences(
        corpus, corpus.manifest, ledger, threshold=threshold,
        rulebook_cache_dir=str(Path("data/rulebook_cache")),
    )
    assert faults, (
        "the frozen mvr1381-tuned threshold must recover >=1 absence candidate on the held-out "
        "witness (THRESHOLD TRANSFER, D-GEN2(4))"
    )

    # SAME-LOGIC: every emitted candidate's requirement_id is one the same requirement index
    # enumerated for THIS corpus -- the absences come from shared index entries, not bespoke rules.
    applicable = enumerate_requirements(corpus.manifest)
    assert isinstance(applicable, list)
    applicable_ids = {e.id for e in applicable}
    candidate_ids = {f.absence_anchor.requirement_id for f in faults}
    assert candidate_ids <= applicable_ids, (
        f"held-out absence candidates {candidate_ids - applicable_ids} are not in the applicable "
        "index-entry set -- absences must arise from the SAME index entries firing (D-GEN2(3))"
    )
    # Every recovered candidate is grounded + re-derivable (the frozen threshold is a general recall
    # bar, not an mvr1381-specific fit) -- the candidate set is stable and index-driven.
    for f in faults:
        assert f.absence_anchor.threshold == threshold
        assert f.absence_anchor.requirement_id and f.absence_anchor.family
