"""Unit tests for D-17 — verifier_model role + MODEL_LINEAGE tags.

Tests in this file cover:
  - Settings.verifier_model resolves to the endpoint name "defpredict-nemotron" on Databricks
  - MODEL_LINEAGE maps both the routable endpoint name and vLLM served-model-name to lineage
  - verifier_max_repair_calls defaults to 1 (mirrors structured_output_max_repair_calls)
  - "defpredict-nemotron" (routable endpoint id) is in DETECTOR_MODELS
  - ON_PREM_ALLOW_LIST is importable from config and is a frozenset (FIX 4)

06-05-DEPLOY-FIX: verifier_model now returns the Databricks ENDPOINT NAME
"defpredict-nemotron" (not the vLLM served-model-name "nemotron-super-49b-v1_5").
The OpenAI model= parameter must be the endpoint name when routing through Databricks.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Core verifier_model / lineage tests
# ---------------------------------------------------------------------------

def test_verifier_model_role_resolves_endpoint_name():
    """Settings.verifier_model must return 'defpredict-nemotron' (endpoint name) on Databricks.

    06-05-DEPLOY-FIX: the OpenAI model= must be the Databricks ENDPOINT NAME, not the
    vLLM --served-model-name. The endpoint name is "defpredict-nemotron".
    """
    from config import Settings
    settings = Settings(environment="databricks", databricks_host="x", databricks_token="x")
    assert settings.verifier_model == "defpredict-nemotron"


def test_lineage_endpoint_name_is_nemotron_on_llama():
    """MODEL_LINEAGE['defpredict-nemotron'] must be 'nemotron-on-llama'.

    The verifier is addressed by its endpoint name in API calls; the lineage entry
    must be keyed on the same routable id so Phase 7 decorrelation logic resolves it.
    """
    from config import MODEL_LINEAGE
    assert MODEL_LINEAGE["defpredict-nemotron"] == "nemotron-on-llama"


def test_lineage_served_model_name_is_nemotron_on_llama():
    """MODEL_LINEAGE['nemotron-super-49b-v1_5'] must be 'nemotron-on-llama'.

    The vLLM served-model-name entry is kept for direct vLLM access / legacy references.
    """
    from config import MODEL_LINEAGE
    assert MODEL_LINEAGE["nemotron-super-49b-v1_5"] == "nemotron-on-llama"


def test_lineage_llama_is_llama():
    """MODEL_LINEAGE['databricks-meta-llama-3-3-70b-instruct'] must be 'llama'."""
    from config import MODEL_LINEAGE
    assert MODEL_LINEAGE["databricks-meta-llama-3-3-70b-instruct"] == "llama"


def test_verifier_max_repair_calls_default_is_1():
    """Settings.verifier_max_repair_calls must default to 1
    (mirrors structured_output_max_repair_calls; single re-prompt budget)."""
    from config import Settings
    assert Settings().verifier_max_repair_calls == 1


# ---------------------------------------------------------------------------
# DETECTOR_MODELS membership — routable endpoint id must be present
# ---------------------------------------------------------------------------

def test_endpoint_name_in_detector_models():
    """'defpredict-nemotron' (routable endpoint id) must appear in DETECTOR_MODELS.

    06-05-DEPLOY-FIX: the routable id is in DETECTOR_MODELS so ON_PREM_ALLOW_LIST
    (derived from DETECTOR_MODELS keys) covers it and the D-16 guard does not
    reject the verifier's own endpoint.
    """
    from config import DETECTOR_MODELS
    assert "defpredict-nemotron" in DETECTOR_MODELS


def test_on_prem_allow_list_imported_from_config():
    """ON_PREM_ALLOW_LIST must be importable from config and be a frozenset (FIX 4).

    This is the single-source-of-truth invariant: the allow-list that guards get_client
    must be defined in config.py, not scattered across the codebase.
    """
    try:
        from config import ON_PREM_ALLOW_LIST
    except ImportError:
        pytest.xfail("ON_PREM_ALLOW_LIST not yet in config.py — Plan 02")
    assert isinstance(ON_PREM_ALLOW_LIST, frozenset), (
        f"ON_PREM_ALLOW_LIST must be a frozenset, got: {type(ON_PREM_ALLOW_LIST)}"
    )


def test_endpoint_name_in_allow_list():
    """'defpredict-nemotron' must be in ON_PREM_ALLOW_LIST.

    06-05-DEPLOY-FIX: the D-16 guard checks the model= string against ON_PREM_ALLOW_LIST.
    The verifier uses model='defpredict-nemotron' in probe calls — it must be allowed.
    """
    from config import ON_PREM_ALLOW_LIST
    assert "defpredict-nemotron" in ON_PREM_ALLOW_LIST, (
        "'defpredict-nemotron' must be in ON_PREM_ALLOW_LIST so the D-16 guard "
        "does not reject the verifier's own endpoint."
    )
