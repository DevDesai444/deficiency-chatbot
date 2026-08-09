"""Unit test shells for D-17 — verifier_model role + MODEL_LINEAGE tags.

Tests in this file cover:
  - Settings.verifier_model resolves to the Nemotron model on Databricks
  - MODEL_LINEAGE dict maps model IDs to lineage tag strings
  - verifier_max_repair_calls defaults to 1 (mirrors structured_output_max_repair_calls)
  - nemotron-super-49b-v1_5 is in DETECTOR_MODELS
  - ON_PREM_ALLOW_LIST is importable from config and is a frozenset (FIX 4)

The verifier_model property and MODEL_LINEAGE dict do not exist in config.py yet
(Plan 02). The importorskip guard on config-plus skips this file gracefully.
However, DETECTOR_MODELS and ON_PREM_ALLOW_LIST tests import from config directly
(which does exist) — those tests can run against the current config.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Tests that depend on future additions to config.py (Plan 02)
# These use xfail so they appear in the report but don't block collection.
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="verifier_model + MODEL_LINEAGE not yet in config.py — Plan 02")
def test_verifier_model_role_resolves_nemotron():
    """Settings.verifier_model must return 'nemotron-super-49b-v1_5' on Databricks."""
    from config import Settings
    settings = Settings(environment="databricks", databricks_host="x", databricks_token="x")
    assert settings.verifier_model == "nemotron-super-49b-v1_5"


@pytest.mark.xfail(strict=False, reason="MODEL_LINEAGE not yet in config.py — Plan 02")
def test_lineage_nemotron_is_nemotron_on_llama():
    """MODEL_LINEAGE['nemotron-super-49b-v1_5'] must be 'nemotron-on-llama'."""
    from config import MODEL_LINEAGE
    assert MODEL_LINEAGE["nemotron-super-49b-v1_5"] == "nemotron-on-llama"


@pytest.mark.xfail(strict=False, reason="MODEL_LINEAGE not yet in config.py — Plan 02")
def test_lineage_llama_is_llama():
    """MODEL_LINEAGE['databricks-meta-llama-3-3-70b-instruct'] must be 'llama'."""
    from config import MODEL_LINEAGE
    assert MODEL_LINEAGE["databricks-meta-llama-3-3-70b-instruct"] == "llama"


@pytest.mark.xfail(strict=False, reason="verifier_max_repair_calls not yet in config.py — Plan 02")
def test_verifier_max_repair_calls_default_is_1():
    """Settings.verifier_max_repair_calls must default to 1
    (mirrors structured_output_max_repair_calls; single re-prompt budget)."""
    from config import Settings
    assert Settings().verifier_max_repair_calls == 1


# ---------------------------------------------------------------------------
# Tests that CAN run now (against current config.py)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=False, reason="nemotron-super-49b-v1_5 not yet in DETECTOR_MODELS — Plan 02")
def test_nemotron_in_detector_models():
    """nemotron-super-49b-v1_5 must appear in DETECTOR_MODELS once the verifier is wired."""
    from config import DETECTOR_MODELS
    assert "nemotron-super-49b-v1_5" in DETECTOR_MODELS


def test_on_prem_allow_list_imported_from_config():
    """ON_PREM_ALLOW_LIST must be importable from config and be a frozenset (FIX 4).

    This is the single-source-of-truth invariant: the allow-list that guards get_client
    must be defined in config.py, not scattered across the codebase.
    """
    # If ON_PREM_ALLOW_LIST doesn't exist yet, mark as expected failure
    try:
        from config import ON_PREM_ALLOW_LIST
    except ImportError:
        pytest.xfail("ON_PREM_ALLOW_LIST not yet in config.py — Plan 02")
    assert isinstance(ON_PREM_ALLOW_LIST, frozenset), (
        f"ON_PREM_ALLOW_LIST must be a frozenset, got: {type(ON_PREM_ALLOW_LIST)}"
    )
