"""Eval-set integrity test (HARD CONDITION B — reviewer-mandated addition, Plan 05-01).

Asserts that load_eval_set() returns BYTE-IDENTICAL document IDs and the IDENTICAL
ground-truth deficiency count before vs after the synthetic_fixture lands. This makes
accidental inclusion of the synthetic fixture in the scored eval set STRUCTURALLY
IMPOSSIBLE to introduce silently.

The test captures the frozen known-good values from the eval set at the time of Plan 05-01
authoring and hard-asserts against them. If the synthetic_fixture were accidentally placed
at the dataset/ TOP LEVEL as a *.deficiencies.json file (HARD CONDITION A violation),
load_eval_set() would glob it and this test would FAIL with a count mismatch — surfacing
the violation immediately in CI.

HARD CONDITION A reminder: the synthetic fixture lives at:
  src/evals/dataset/synthetic_fixture/     (subdirectory — NOT globbed by load_eval_set)
  tests/fixtures/synthetic_submission_b/   (test fixtures dir — NOT in dataset/)

The scorer glob (schema.py:106) is:
  resolved_dir.glob("*.deficiencies.json")

This is NON-RECURSIVE (no **), so files inside subdirectories are invisible to the scorer.

Frozen values captured from the eval set as of Plan 05-01:
  - Document IDs: ['minispec', 'mvr1381', 'spec32s41']
  - Deficiency count: 35
"""
from __future__ import annotations

from evals.schema import load_eval_set

# ---------------------------------------------------------------------------
# Frozen known-good values (captured 2026-08-07, Plan 05-01)
# Do NOT change these values. If load_eval_set() returns different values,
# either a frozen file was modified (MUST NOT) or a new file was accidentally
# included (check HARD CONDITION A — no *.deficiencies.json at dataset/ top level).
# ---------------------------------------------------------------------------
_FROZEN_DOC_IDS = ["minispec", "mvr1381", "spec32s41"]
_FROZEN_DEFICIENCY_COUNT = 35


def test_eval_set_doc_ids_unchanged():
    """load_eval_set() document IDs must match frozen list exactly (byte-identical).

    Fails if a new document was added to documents.json (which would need reviewer approval)
    or if a document was accidentally removed.
    """
    es = load_eval_set()
    actual_ids = sorted(d.doc_id for d in es.documents)
    assert actual_ids == _FROZEN_DOC_IDS, (
        f"Eval set document IDs changed. "
        f"Expected: {_FROZEN_DOC_IDS}. "
        f"Got: {actual_ids}. "
        f"If this is intentional, update _FROZEN_DOC_IDS and _FROZEN_DEFICIENCY_COUNT "
        f"after reviewer approval. If this is accidental, check for stray *.deficiencies.json "
        f"files at src/evals/dataset/ top level (HARD CONDITION A)."
    )


def test_eval_set_deficiency_count_unchanged():
    """load_eval_set() deficiency count must match frozen count exactly.

    Fails if any *.deficiencies.json at src/evals/dataset/ top level was added, removed,
    or modified. The synthetic_fixture lives in a subdirectory and is invisible to the
    scorer glob (non-recursive), so it must NOT change this count.
    """
    es = load_eval_set()
    actual_count = len(es.deficiencies)
    assert actual_count == _FROZEN_DEFICIENCY_COUNT, (
        f"Eval set deficiency count changed. "
        f"Expected: {_FROZEN_DEFICIENCY_COUNT}. "
        f"Got: {actual_count}. "
        f"If a new *.deficiencies.json was accidentally placed at src/evals/dataset/ top level, "
        f"REMOVE IT immediately (HARD CONDITION A — synthetic fixture must be in subdirectory). "
        f"If this is an intentional eval set change, update _FROZEN_DEFICIENCY_COUNT "
        f"after reviewer approval."
    )


def test_synthetic_fixture_is_invisible_to_scorer():
    """The synthetic_fixture subdirectory must not contain any *.deficiencies.json at top level.

    This test directly asserts HARD CONDITION A by checking that no *.deficiencies.json
    file exists at the src/evals/dataset/ top level that wasn't there before Plan 05-01.
    """
    import pathlib
    dataset_dir = pathlib.Path(__file__).parent.parent.parent / "src" / "evals" / "dataset"
    assert dataset_dir.exists(), f"dataset dir must exist: {dataset_dir}"

    # Collect all *.deficiencies.json at the top level (non-recursive, same as scorer glob)
    top_level_deficiency_files = sorted(dataset_dir.glob("*.deficiencies.json"))
    top_level_names = [f.name for f in top_level_deficiency_files]

    # These are the KNOWN frozen files from before Plan 05-01
    frozen_deficiency_files = sorted(["heldout32s41.deficiencies.json", "minispec.deficiencies.json", "mvr1381.deficiencies.json"])
    assert top_level_names == frozen_deficiency_files, (
        f"Unexpected *.deficiencies.json files at dataset/ top level (HARD CONDITION A violation). "
        f"Expected: {frozen_deficiency_files}. "
        f"Got: {top_level_names}. "
        f"Remove any fixture-related *.deficiencies.json and place them in a SUBDIRECTORY "
        f"(e.g., dataset/synthetic_fixture/fixture_manifest.json, NOT *.deficiencies.json)."
    )
