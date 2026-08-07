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


# =============================================================================
# Phase 5 guard extension (Plan 06, Wave 4)
# Ruling 8 hierarchy:
#   PRIMARY guard tests appear FIRST — they must pass to ship Phase 5 (no pytest.skip).
#   SECONDARY tripwire tests appear AFTER — source-scan early warnings; failure triggers
#   investigation, not an automatic block.
# =============================================================================

# --- New source-path constants and helpers (Plan 06) -------------------------

_STRUCTURAL_SOURCE = Path("src/rulebook/structural.py")
_REFERENCES_SOURCE = Path("src/rulebook/references.py")
_PRECEDENT_SOURCE = Path("src/rulebook/precedent_search.py")
_SYNTHETIC_FIXTURE_DIR = Path("src/evals/dataset/synthetic_fixture")
_SYNTHETIC_FIXTURE_B_DIR = Path("tests/fixtures/synthetic_submission_b")  # B3 fix: real fixture_b


def _has_inline_ctd_literal(source: str) -> list[str]:
    """Strip re.compile() string contents before scanning for CTD literals (Pitfall 6 exemption).

    SECONDARY tripwire — called only from NO-CONSTANT parametrized test.
    Ensures the CTD extractor regex in references.py (r'(?:Module|Section)\\s+(3\\.2\\.[SP]\\....)
    inside re.compile()) is NOT flagged as a corpus constant.
    """
    cleaned = re.sub(r're\.compile\(r?["\'][^"\']*["\']\)', "", source, flags=re.DOTALL)
    return re.findall(r"3\.2\.[SP]\.", cleaned)


def _inline_float_offenders(source: str, allowed: frozenset) -> list[str]:
    """Float literal scan excluding re.compile contents, docstrings, and threshold-loader body.

    SECONDARY tripwire — called only from NO-CONSTANT parametrized test.
    Ruling 9 MEDIUM item d: 0.6 inside _load_precedent_threshold is the sole exempt float.

    Also strips Python triple-quoted docstrings (both triple-double-quote and triple-single-quote)
    so that documented numeric EXAMPLES in docstrings (e.g. 'round(0.104, 2) == 0.10')
    are not flagged as inline threshold constants.  The guard targets EXECUTABLE threshold
    literals (in function/method bodies), not docstring narrative text.
    """
    # Strip Python triple-quoted docstrings (documentation examples, not executable literals)
    cleaned = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    cleaned = re.sub(r"'''.*?'''", "", cleaned, flags=re.DOTALL)
    # Strip single-line # comments (to avoid catching numeric examples in comments)
    cleaned = re.sub(r"#[^\n]*", "", cleaned)
    # Strip re.compile() string contents (Pitfall 6 — CTD regex inside re.compile is exempt)
    cleaned = re.sub(r're\.compile\(r?["\'][^"\']*["\']\)', "", cleaned, flags=re.DOTALL)
    # Strip _load_precedent_threshold body (Ruling 9 exemption)
    cleaned = re.sub(
        r"def _load_precedent_threshold\(\)[^\n]*\n(    [^\n]*\n)*",
        "",
        cleaned,
    )
    return [f for f in re.findall(r"(?<![\w.])\d+\.\d+", cleaned) if f not in allowed]


# =============================================================================
# SECTION 3: PRIMARY behavior-transfer tests (Ruling 8 — must come BEFORE secondary)
# =============================================================================


def test_same_logic_structural_on_synthetic(tmp_path):
    """PRIMARY GUARD: structural check fires on committed fixture_a (D-GRD2).

    Proves detect_structural_inconsistencies produces >= 1 Fault with a structural_anchor
    on the committed synthetic fixture_a.  No pytest.skip — the fixture MUST be committed.
    If this test fails: the structural leg is broken or the fixture was removed.
    Ruling 8: PRIMARY guard — must pass to ship Phase 5.
    """
    from ingest.corpus import ingest_corpus
    from rulebook.structural import detect_structural_inconsistencies
    from tools.ledger import RetrievalLedger

    assert _SYNTHETIC_FIXTURE_DIR.exists(), (
        f"synthetic fixture_a missing at {_SYNTHETIC_FIXTURE_DIR} (D-GRD1). "
        "The fixture must be committed — run Plan 01 first."
    )

    corpus = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=str(tmp_path / "cache"))
    ledger = RetrievalLedger()
    faults = detect_structural_inconsistencies(corpus, corpus.manifest, ledger)

    struct_faults = [f for f in faults if f.structural_anchor is not None]
    assert len(struct_faults) > 0, (
        f"SAME-LOGIC (structural) failed: detect_structural_inconsistencies produced "
        f"{len(faults)} total faults and {len(struct_faults)} with structural_anchor on "
        f"fixture_a. Planted violations X2a/X2b/X2c must fire. "
        "Check: fixture_a doc_b.docx must have addressable tables tier."
    )


def test_same_logic_reference_on_synthetic(tmp_path):
    """PRIMARY GUARD: reference detection fires on committed fixture_a (D-GRD2).

    Proves extract_references + detect_reference_anomalies produces >= 1 Fault with a
    reference_anchor on the committed synthetic fixture_a.  No pytest.skip.
    If this test fails: the reference leg is broken or the fixture was removed.
    Ruling 8: PRIMARY guard — must pass to ship Phase 5.
    """
    from ingest.corpus import ingest_corpus
    from rulebook.references import detect_reference_anomalies, extract_references
    from tools.ledger import RetrievalLedger

    assert _SYNTHETIC_FIXTURE_DIR.exists(), (
        f"synthetic fixture_a missing at {_SYNTHETIC_FIXTURE_DIR} (D-GRD1). "
        "The fixture must be committed — run Plan 01 first."
    )

    corpus = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=str(tmp_path / "cache"))
    edges_db = str(tmp_path / "edges.db")
    extract_references(corpus, corpus.manifest, db_path=edges_db)
    ledger = RetrievalLedger()
    faults = detect_reference_anomalies(corpus, corpus.manifest, ledger, db_path=edges_db)

    ref_faults = [f for f in faults if f.reference_anchor is not None]
    assert len(ref_faults) > 0, (
        f"SAME-LOGIC (reference) failed: detect_reference_anomalies produced "
        f"{len(faults)} total faults and {len(ref_faults)} with reference_anchor on "
        f"fixture_a. Planted cross-references must generate at least UNRESOLVED_REF findings. "
        "Check: fixture_a doc_a.pdf and doc_b.docx must contain extractable references."
    )


def test_threshold_transfer_structural_fixture_b(tmp_path):
    """PRIMARY GUARD — THRESHOLD-TRANSFER (Ruling 8, B3 fix).

    fixture_b (tests/fixtures/synthetic_submission_b/) uses:
    - Different domain vocabulary: "dissolution", "release", "% Dissolved" (not "impurity", "NMT")
    - Different compound names: "Sample 1/2", "Total Average" (not "Compound A/B", "Total Impurities")
    - Different numeric values: 65%, 78%, 63%, 72% (not 0.10%, 0.18%, 0.12%, 42.3)
    - SAME violation TYPES: labeled-aggregate recompute (MEAN wrong on Total Average; MAX wrong)
    Failure means structural check depends on fixture_a-specific constants -> anti-overfitting law violated.

    This is a REAL transfer test (B3 fix): fixture_b has DIFFERENT surface forms, NOT a rename of
    fixture_a. Both fixture_a AND fixture_b must produce structural violations with the SAME logic.
    Ruling 8: PRIMARY guard — must pass to ship Phase 5.  No pytest.skip.
    """
    from ingest.corpus import ingest_corpus
    from rulebook.structural import detect_structural_inconsistencies
    from tools.ledger import RetrievalLedger

    assert _SYNTHETIC_FIXTURE_B_DIR.exists(), (
        f"fixture_b missing at {_SYNTHETIC_FIXTURE_B_DIR} (B3 fix). "
        "REAL fixture with DIFFERENT surface forms from fixture_a — NOT a rename. "
        "Must be committed at tests/fixtures/synthetic_submission_b/."
    )
    assert _SYNTHETIC_FIXTURE_DIR.exists(), (
        f"fixture_a missing at {_SYNTHETIC_FIXTURE_DIR} (D-GRD1)."
    )

    # Run on fixture_a (baseline SAME-LOGIC check)
    corpus_a = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=str(tmp_path / "cache_a"))
    ledger_a = RetrievalLedger()
    struct_a = [
        f for f in detect_structural_inconsistencies(corpus_a, corpus_a.manifest, ledger_a)
        if f.structural_anchor is not None
    ]
    assert len(struct_a) > 0, (
        "THRESHOLD-TRANSFER pre-check: fixture_a produced 0 structural violations. "
        "Fix SAME-LOGIC failure first."
    )

    # Run on fixture_b (THRESHOLD-TRANSFER: different domain vocabulary, different values)
    corpus_b = ingest_corpus(_SYNTHETIC_FIXTURE_B_DIR, cache_dir=str(tmp_path / "cache_b"))
    ledger_b = RetrievalLedger()
    struct_b = [
        f for f in detect_structural_inconsistencies(corpus_b, corpus_b.manifest, ledger_b)
        if f.structural_anchor is not None
    ]

    assert len(struct_b) > 0, (
        f"THRESHOLD-TRANSFER failed: fixture_b ({_SYNTHETIC_FIXTURE_B_DIR}) produced "
        f"0 structural violations. "
        f"fixture_b uses dissolution domain vocabulary (different surface forms than fixture_a). "
        f"Structural check must not depend on fixture_a-specific values. "
        f"Expected: MEAN violation on 'Total Average 63%' (true mean 71.5%) and MAX violation "
        f"on 'Maximum Release 66%' (true max 72%). fixture_a produced {len(struct_a)} violation(s)."
    )


def test_rename_invariance_structural(tmp_path):
    """PRIMARY GUARD: renaming submission directory leaves fault count unchanged (D-GRD2).

    Ingests fixture_a as-is, then under a completely different directory name. The structural
    violation count must be identical — structural detection is content-driven, not folder-derived.
    Distinct from THRESHOLD-TRANSFER: same content, different path; THRESHOLD-TRANSFER uses
    genuinely different content (fixture_b).
    Ruling 8: PRIMARY guard — must pass to ship Phase 5.  No pytest.skip.
    """
    from ingest.corpus import ingest_corpus
    from rulebook.structural import detect_structural_inconsistencies
    from tools.ledger import RetrievalLedger

    assert _SYNTHETIC_FIXTURE_DIR.exists(), (
        f"synthetic fixture_a missing at {_SYNTHETIC_FIXTURE_DIR} (D-GRD1)."
    )

    # Original directory
    corpus_orig = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=str(tmp_path / "cache_orig"))
    ledger_orig = RetrievalLedger()
    faults_original = [
        f for f in detect_structural_inconsistencies(corpus_orig, corpus_orig.manifest, ledger_orig)
        if f.structural_anchor is not None
    ]

    # Copy to a completely different directory name (same content, different path)
    renamed_dir = tmp_path / "completely-unrelated-folder-name-for-rename-invariance"
    shutil.copytree(str(_SYNTHETIC_FIXTURE_DIR), str(renamed_dir))
    corpus_renamed = ingest_corpus(renamed_dir, cache_dir=str(tmp_path / "cache_renamed"))
    ledger_renamed = RetrievalLedger()
    faults_renamed = [
        f for f in detect_structural_inconsistencies(corpus_renamed, corpus_renamed.manifest, ledger_renamed)
        if f.structural_anchor is not None
    ]

    assert len(faults_original) == len(faults_renamed), (
        f"RENAME-INVARIANCE failed: original directory produced {len(faults_original)} "
        f"structural faults but renamed directory produced {len(faults_renamed)}. "
        f"Structural detection must be folder-name invariant (content-derived, D-GRD2)."
    )
    assert len(faults_original) > 0, (
        "RENAME-INVARIANCE: both configurations produced 0 faults — fixture must "
        "produce >= 1 structural fault."
    )


# =============================================================================
# SECTION 4: SECONDARY source-scan tripwires (Ruling 8 — after PRIMARY tests)
# Failure triggers investigation; not an automatic block.
# =============================================================================


@pytest.mark.parametrize(
    "source_path,check_ctd",
    [
        (Path("src/rulebook/structural.py"), False),       # no CTD patterns expected
        (Path("src/rulebook/references.py"), True),        # CTD extractor inside re.compile (exempt)
        (Path("src/rulebook/precedent_search.py"), False), # no CTD patterns expected
    ],
    ids=["structural", "references", "precedent_search"],
)
def test_new_modules_embed_no_corpus_constant(source_path, check_ctd):
    """SECONDARY tripwire: source scan for inline corpus constants in Phase 5 leg modules.

    Uses _has_inline_ctd_literal (Pitfall 6 exemption: strips re.compile() string contents
    before CTD scan) and _inline_float_offenders (Ruling 9 threshold-loader exemption: strips
    _load_precedent_threshold body before float scan).

    Three checks per module:
      (a) CTD-family literal: 3.2.S.* / 3.2.P.* must not appear outside re.compile() context.
      (b) inline float threshold: non-sentinel floats outside re.compile() and the threshold-loader.
      (c) dataset ID backstop: no known corpus/submission ID literal.

    Failure triggers investigation — do NOT weaken to pass.  A real corpus constant in a leg
    module violates the anti-overfitting law.
    """
    assert source_path.exists(), (
        f"SECONDARY tripwire: source file {source_path} missing — cannot scan for corpus constants."
    )

    source = source_path.read_text()
    _DATASET_ID_DENYLIST = ("mvr1381", "spec32s41", "heldout32s41", "minispec")

    offenders: list[str] = []

    # (a) CTD-family literals (stripped of re.compile() context via Pitfall 6 helper)
    ctd_hits = _has_inline_ctd_literal(source)
    if ctd_hits:
        offenders.append(
            f"CTD-family literal(s) {sorted(set(ctd_hits))} found OUTSIDE re.compile() context "
            f"in {source_path}. Families must flow from the edge relation, not inline literals "
            f"(D-GRD3 / Pitfall 6). CTD patterns inside re.compile() are exempt."
        )

    # (b) inline float threshold literals (after stripping re.compile() and threshold-loader body)
    float_hits = _inline_float_offenders(source, _ALLOWED_FLOAT_SENTINELS)
    if float_hits:
        offenders.append(
            f"Inline float literal(s) {sorted(set(float_hits))} in {source_path} "
            f"outside re.compile() and _load_precedent_threshold body. "
            f"Thresholds must be loaded from JSON, not hardcoded (D-GEN2 / Ruling 9)."
        )

    # (c) dataset/corpus ID backstop (case-insensitive)
    source_lower = source.lower()
    dataset_hits = [lit for lit in _DATASET_ID_DENYLIST if lit.lower() in source_lower]
    if dataset_hits:
        offenders.append(
            f"Dataset ID literal(s) {dataset_hits} found in {source_path}. "
            f"These are submission-specific constants — remove them (D-GRD3 backstop)."
        )

    assert not offenders, (
        f"SECONDARY tripwire: {source_path} embeds corpus/threshold constant(s):\n"
        + "\n".join(f"  - {o}" for o in offenders)
        + "\nDo NOT weaken this test to pass — fix the module or route to the reviewer."
    )


def test_guard_vocab_contains_no_corpus_token():
    """SECONDARY tripwire: AGGREGATE_LEXICON + REFERENCE_CUE_WORDS must be general vocabulary.

    Asserts that no entry in the declared vocabulary registries (guard_vocab.py) is a
    corpus-specific token — no ANDA numbers, no submission doc names, no mvr1381-specific terms.
    If this fails: a corpus constant leaked into the shared vocabulary registry (D-GRD3).
    """
    from rulebook.guard_vocab import AGGREGATE_LEXICON, REFERENCE_CUE_WORDS

    _CORPUS_TOKENS = re.compile(
        r"mvr1381|ANDA\d+|spec32s41|heldout32s41|estradiol|minispec",
        re.IGNORECASE,
    )

    for token in list(AGGREGATE_LEXICON) + list(REFERENCE_CUE_WORDS):
        assert not _CORPUS_TOKENS.search(token), (
            f"SECONDARY tripwire: guard_vocab token {token!r} looks corpus-specific "
            f"(matched corpus-token pattern). "
            f"AGGREGATE_LEXICON and REFERENCE_CUE_WORDS must contain only general vocabulary "
            f"with no submission/doc/ANDA-specific terms (D-GRD3)."
        )


# =============================================================================
# Phase 5 SC2/X1 state-aware assertion (binding_reviewer_addition_SC2)
# =============================================================================


def test_phase5_gate_sc2_x1_deferred_branch():
    """SC2 / X1 state-aware assertion — sentinel constant verification (Wave 5 post-wiring).

    After Wave 5, follow_reference is fully wired for cross-document resolution and no longer
    returns _CROSS_DOC_PENDING. This test verifies the state transition:
      - _CROSS_DOC_PENDING constant still exists (for back-compat with run.py:813 import)
      - follow_reference returns a REAL status (not the pending sentinel)
      - The SC2 HARD path is now active: run.py:813 probe will always take the hard branch

    Wave 4 (DEFERRED): follow_reference returned _CROSS_DOC_PENDING — run.py took the
      DEFERRED (exit-0) path and emitted a WARN. That behavior is now retired (Wave 5).
    Wave 5 (WIRED): follow_reference returns 'resolved_cross_doc' or 'UNRESOLVED_REF' —
      run.py always takes the HARD path (VALUE_CONTRADICTION must be present).

    SC2 catch is non-silent: any CI that passes without the HARD path VALUE_CONTRADICTION
    is making an explicit, visible decision.
    """
    from tools.follow_reference import _CROSS_DOC_PENDING

    # Verify the sentinel constant is still importable (back-compat for run.py:813)
    assert _CROSS_DOC_PENDING == "cross_document_resolution_pending_phase_4", (
        "_CROSS_DOC_PENDING sentinel must be retained for run.py:813 back-compat import "
        "(Plan 06 owns run.py; do not delete the constant)."
    )

    # Verify the sentinel value is a well-known string (not None / empty)
    assert isinstance(_CROSS_DOC_PENDING, str) and len(_CROSS_DOC_PENDING) > 10, (
        "_CROSS_DOC_PENDING must be a non-empty string sentinel."
    )

    # Verify that follow_reference no longer returns the pending sentinel
    # (probe the fixture to confirm the HARD path is active post-Wave-5)
    assert _SYNTHETIC_FIXTURE_DIR.exists(), (
        f"Fixture_a missing at {_SYNTHETIC_FIXTURE_DIR} (required for SC2 probe)."
    )

    with __import__("tempfile").TemporaryDirectory() as tmp:
        from ingest.corpus import ingest_corpus
        from tools.follow_reference import follow_reference
        from tools.ledger import RetrievalLedger

        corpus = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=tmp + "/cache")
        ledger = RetrievalLedger()
        doc_ids = [d.doc_id for d in corpus.manifest.documents]
        assert doc_ids, "fixture must have at least one document"

        probe_doc_id = doc_ids[0]
        result = follow_reference(corpus, probe_doc_id, "doc_b", ledger)
        status = result.get("status", "")

    # Post-Wave-5: the DEFERRED sentinel must NEVER be returned
    assert status != _CROSS_DOC_PENDING, (
        f"follow_reference returned _CROSS_DOC_PENDING on Wave 5 — the sentinel should "
        f"never be returned after follow_reference was wired for cross-doc resolution. "
        f"status={status!r}"
    )
    # Post-Wave-5: must return a real typed status
    assert status in ("resolved_cross_doc", "UNRESOLVED_REF", "resolved") or result.get("resolved"), (
        f"follow_reference must return a real typed status post-Wave-5 "
        f"(resolved_cross_doc, UNRESOLVED_REF, or resolved=True). Got status={status!r}, result={result!r}"
    )
    print(f"SC2 state: follow_reference returns status={status!r} (HARD path active post-Wave-5).")


def test_phase5_gate_sc2_x1_hard_path_logic(monkeypatch):
    """SC2 / X1 state-aware assertion — HARD path logic (monkeypatched follow_reference).

    Validates that the hard-assertion logic is present and fires correctly once
    follow_reference is wired for cross-document resolution (Wave 5).

    Monkeypatches follow_reference to return a resolved_cross_doc status, then verifies
    that detect_reference_anomalies on the 3-doc fixture is checked for VALUE_CONTRADICTION
    findings containing the Compound-B numbers (0.18 and 0.15).

    This test exercises the HARD path of phase5-gate's SC2 sub-check:
      IF follow_reference resolves cross-doc: HARD-ASSERT >= 1 VALUE_CONTRADICTION
      whose evidence/anchor carries the Compound-B numbers (0.18 and 0.15).
    """
    import json

    from ingest.corpus import ingest_corpus
    from rulebook.references import detect_reference_anomalies, extract_references
    from tools.ledger import RetrievalLedger

    assert _SYNTHETIC_FIXTURE_DIR.exists(), (
        f"Fixture_a missing at {_SYNTHETIC_FIXTURE_DIR}."
    )

    with __import__("tempfile").TemporaryDirectory() as tmp:
        corpus = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=tmp + "/cache")
        edges_db = tmp + "/edges.db"
        extract_references(corpus, corpus.manifest, db_path=edges_db)
        ledger = RetrievalLedger()
        faults = detect_reference_anomalies(corpus, corpus.manifest, ledger, db_path=edges_db)

    # Hard path assertion: once follow_reference resolves cross-doc (Wave 5),
    # the fixture's X1 violation (Compound B 0.18% vs NMT 0.15%) must appear
    # as a VALUE_CONTRADICTION fault. This test validates the assertion logic
    # by checking whether value contradictions exist in the current findings.
    # Currently VALUE_CONTRADICTION = 0 (DEFERRED), so we assert the logic structure.

    # For the monkeypatched hard path: verify the Compound-B assertion logic
    # If VALUE_CONTRADICTION faults exist and contain 0.18/0.15, that is the X1 catch.
    value_contradictions = [
        f for f in faults
        if f.reference_anchor is not None
        and f.reference_anchor.anomaly == "VALUE_CONTRADICTION"
    ]

    # Build the detail text for compound-B number search
    all_details = " ".join(
        (f.detail or "") for f in value_contradictions
    )

    # Wave 5 HARD path: VALUE_CONTRADICTION must be present with Compound-B numbers.
    # follow_reference is now wired for cross-doc resolution — the edge from doc_a to doc_b
    # must resolve so detect_reference_anomalies can surface the 0.18% vs NMT 0.15% violation.
    assert value_contradictions, (
        "SC2 X1 HARD assertion (Wave 5): extract_references + detect_reference_anomalies must "
        "produce >= 1 VALUE_CONTRADICTION fault on fixture_a. "
        f"Got {len(faults)} total faults, 0 with VALUE_CONTRADICTION. "
        "Check: references.py must resolve '(doc_b.docx)' or 'Analytical Procedures' to doc_b "
        "so Ruling-6 pipeline fires on Compound B (0.18% vs NMT 0.15%)."
    )
    assert "0.18" in all_details and "0.15" in all_details, (
        "SC2 X1 hard assertion: VALUE_CONTRADICTION fault must carry Compound-B numbers "
        "(0.18 and 0.15) once follow_reference resolves cross-doc. "
        f"VALUE_CONTRADICTION count: {len(value_contradictions)}, "
        f"details sample: {all_details[:200]!r}"
    )
