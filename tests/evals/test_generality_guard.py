"""D-GEN3 CI generality guard for the deterministic absence pass (RECALL-01, Plan 04-03).

This test FILE encodes the four D-GEN2 anti-overfitting invariants, witnessed on the HELD-OUT
spec32s41 corpus (D-GEN1: the generality witness, never the corpus the threshold was tuned on):

  1. NO-CONSTANT       -- absence.py embeds no dataset/doc/submission-ID literal, no CTD-family
                          string literal (3.2.S.* / 3.2.P.*), and no hardcoded numeric threshold
                          literal (the threshold is imported from the JSON baseline / passed in).
  2. RENAME-INVARIANCE -- reorganizing/renaming the held-out corpus dir yields the IDENTICAL
                          applicable-requirement set (content-derived, not folder-derived).
  3. SAME-LOGIC TRANSFER -- the held-out corpus's absences come from the SAME index entries firing
                          (same requirement_ids), not corpus-specific rules.
  4. THRESHOLD TRANSFER -- with the threshold FROZEN at its mvr1381-tuned value from
                          absence_threshold.json, the held-out corpus's absence candidates are
                          recovered unchanged (the threshold is a general recall bar, D-GEN2(4)).

WHAT STOCK CI ACTUALLY ENFORCES EVERY BUILD (be honest -- the committed config does not deliver
more than this): only invariant (1), the STRUCTURAL NO-CONSTANT scan of absence.py, runs
unconditionally in `.github/workflows/test.yml`'s fast lane; coverage-gate and the absence-gate
tripwire run alongside it as CI-enforced eval-gate checks. Invariant (2) RENAME-INVARIANCE and
invariants (3)+(4) SAME-LOGIC / THRESHOLD-TRANSFER need the gitignored held-out corpus
`data/32s41-Specification.pdf`; without it they `pytest.skip` (RENAME) or are slow-deselected
(SAME-LOGIC/THRESHOLD). They run FOR REAL only where the held-out corpus is present (a self-hosted
or scheduled runner that checks out data/, via the pytest-slow job / `-m slow`).

Offline (D-RB6): the real rulebook store is built from the committed snapshot; corpora ingest into
tmp_path; nothing touches Databricks or the shared data/ store beyond reading the local corpus PDF.
"""
from __future__ import annotations

import json
import re
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
_ABSENCE_SOURCE = Path("src/rulebook/absence.py")

# BACKSTOP denylist (documented): the known dataset/doc/submission ids. Kept for defense-in-depth
# and matched CASE-INSENSITIVELY, but it is a backstop only -- the primary NO-CONSTANT guard below
# is STRUCTURAL (rejects the CTD-family and threshold-literal shapes an unseen dataset id would not
# be caught by), so this list need not be exhaustive to keep absence.py corpus-general.
_DATASET_LITERALS = ("mvr1381", "spec32s41", "heldout32s41", "minispec")

# CTD-family string literals (3.2.S.* quality/drug-substance, 3.2.P.* drug-product): a hardcoded
# family/section path is a corpus/CTD-shape constant, never allowed in absence.py -- families must
# flow off the edge relation (families_by_requirement), not literals (CR-01 / anti-overfitting law).
_CTD_FAMILY_LITERAL = re.compile(r"3\.2\.[SP]\.")

# Float literals that look like a hardcoded numeric threshold. The threshold MUST be imported from
# the JSON baseline / passed in (D-THR) -- never a literal in absence.py. Boundary sentinels 0.0 and
# 1.0 (the no-hits fallback score / a full-recall bound) are NOT thresholds and are whitelisted.
_FLOAT_LITERAL = re.compile(r"(?<![\w.])\d+\.\d+")
_ALLOWED_FLOAT_SENTINELS = frozenset({"0.0", "1.0"})


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
    """D-GEN2(1) STRUCTURAL NO-CONSTANT: scan src/rulebook/absence.py source and FAIL THE BUILD if it
    embeds any corpus/CTD/threshold constant. Three structural rejections + one documented backstop:

      (a) CTD-family string literal (`3.2.S.*` / `3.2.P.*`): families must flow off the edge relation,
          never a hardcoded section path.
      (b) hardcoded numeric threshold float literal: the threshold is imported from the JSON baseline
          / passed in (D-THR), never a literal here. 0.0 / 1.0 boundary sentinels are whitelisted.
      (c) BACKSTOP: the known dataset/doc/submission-id denylist, matched CASE-INSENSITIVELY.

    This is a REAL structural guarantee, not a substring convenience: if it fails against the current
    absence.py, the offending literal is surfaced and the reviewer decides -- the test is NOT to be
    weakened to pass. (Expectation from CR-01: absence.py drives families off the edge relation and
    imports the threshold, so it should contain NONE of these literals.)"""
    source = _ABSENCE_SOURCE.read_text()
    offenders: list[str] = []

    # (a) CTD-family literals (3.2.S.* / 3.2.P.*).
    ctd = _CTD_FAMILY_LITERAL.findall(source)
    if ctd:
        offenders.append(f"CTD-family literal(s) {sorted(set(ctd))} (families must come from the edge relation)")

    # (b) hardcoded numeric threshold float literals (whitelist 0.0 / 1.0 boundary sentinels).
    floats = {m for m in _FLOAT_LITERAL.findall(source) if m not in _ALLOWED_FLOAT_SENTINELS}
    if floats:
        offenders.append(
            f"hardcoded numeric threshold literal(s) {sorted(floats)} "
            "(the threshold must be imported from the JSON baseline / passed in, D-THR)"
        )

    # (c) BACKSTOP denylist, case-insensitive.
    source_lower = source.lower()
    dataset = [lit for lit in _DATASET_LITERALS if lit.lower() in source_lower]
    if dataset:
        offenders.append(f"dataset id literal(s) {dataset} (backstop denylist)")

    assert not offenders, (
        f"src/rulebook/absence.py embeds a corpus/threshold constant -- {offenders}. "
        "The absence module must be corpus-general (D-GEN2 STRUCTURAL no-constant); do NOT weaken "
        "this test to pass -- fix absence.py or route the literal to the reviewer."
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
    absence pass runs in minutes. Only the STRUCTURAL NO-CONSTANT scan above runs unconditionally in
    stock CI; RENAME-INVARIANCE skips without the gitignored held-out PDF, and this SAME-LOGIC /
    THRESHOLD-TRANSFER invariant is slow-deselected -- both run for real only where the held-out
    corpus is provisioned (pytest-slow job / `-m slow`). The `absence-gate` CLI proves the same
    recovery mechanism on the non-held-out aggregate wherever a corpus is present (SC2), and runs as
    an always-on offline tripwire in CI (SKIPPED cleanly when data/ is absent)."""
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
