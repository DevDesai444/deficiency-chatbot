"""Unit tests for D-17 / β-PIVOT — verifier_model role + MODEL_LINEAGE tags.

Tests in this file cover:
  - Settings.verifier_model resolves to the served Llama 3.3 70B endpoint by default on Databricks
  - VERIFIER_MODEL_NAME overrides the verifier endpoint (e.g. back to "defpredict-nemotron")
  - MODEL_LINEAGE maps both the routable endpoint name and vLLM served-model-name to lineage
  - verifier_max_repair_calls defaults to 1 (mirrors structured_output_max_repair_calls)
  - "defpredict-nemotron" (deferred verifier endpoint) is still in DETECTOR_MODELS + allow-list
  - ON_PREM_ALLOW_LIST is importable from config and is a frozenset (FIX 4)

β-PIVOT (2026-08-13): Nemotron-Super-49B is unservable on aip-amn-dev (custom-entrypoint
serving disabled; H100 tiers unenrolled — see 06-06-GATE-BLOCKED-STATUS.md). The verifier
role runs on the already-served Llama 3.3 70B endpoint. Recall-safe: recall is deterministic
(Phase 5) and the verifier is downgrade-never-drop (Phase 7), so verifier model strength is
precision-only. Nemotron stays fully wired and reachable via VERIFIER_MODEL_NAME.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Core verifier_model / lineage tests
# ---------------------------------------------------------------------------

def test_verifier_model_role_resolves_served_llama_by_default():
    """Settings.verifier_model must default to the served Llama 3.3 70B endpoint on Databricks.

    β-PIVOT: Nemotron is unservable, so the default verifier endpoint is the already-served
    Llama 3.3 70B. The OpenAI model= must be the Databricks ENDPOINT NAME.
    """
    from config import Settings
    settings = Settings(environment="databricks", databricks_host="x", databricks_token="x")
    assert settings.verifier_model == "databricks-meta-llama-3-3-70b-instruct"


def test_verifier_model_name_override_restores_nemotron():
    """VERIFIER_MODEL_NAME override routes the verifier back to Nemotron (deferred path).

    The Nemotron endpoint stays wired; when Databricks custom serving is enabled, setting
    verifier_model_name='defpredict-nemotron' restores it with no other code change.
    """
    from config import Settings
    settings = Settings(
        environment="databricks",
        databricks_host="x",
        databricks_token="x",
        verifier_model_name="defpredict-nemotron",
    )
    assert settings.verifier_model == "defpredict-nemotron"


def test_verifier_model_resolved_value_is_allow_listed():
    """Whatever verifier_model resolves to MUST be in the D-16 on-prem allow-list."""
    from config import Settings, ON_PREM_ALLOW_LIST
    settings = Settings(environment="databricks", databricks_host="x", databricks_token="x")
    assert settings.verifier_model in ON_PREM_ALLOW_LIST


def test_verifier_fleet_members_allow_listed_and_lineage_tagged():
    """β-PIVOT: every VERIFIER_FLEET endpoint must be on-prem allow-listed AND lineage-tagged.

    The Phase-6 gate runs across the whole fleet and Phase 7 fans out across it for
    decorrelated consensus — so each id must pass the D-16 guard and resolve a family.
    """
    from config import VERIFIER_FLEET, ON_PREM_ALLOW_LIST, MODEL_LINEAGE
    assert len(VERIFIER_FLEET) >= 2, "fleet must have >=2 endpoints for cross-family decorrelation"
    for model_id in VERIFIER_FLEET:
        assert model_id in ON_PREM_ALLOW_LIST, f"{model_id} not in ON_PREM_ALLOW_LIST (D-16 guard)"
        assert model_id in MODEL_LINEAGE, f"{model_id} has no MODEL_LINEAGE family tag"


def test_verifier_fleet_is_cross_family():
    """The fleet must span >=2 distinct model families (Llama + Qwen) so consensus is decorrelated."""
    from config import VERIFIER_FLEET, MODEL_LINEAGE
    families = {MODEL_LINEAGE[m] for m in VERIFIER_FLEET}
    assert len(families) >= 2, f"fleet must span >=2 families for decorrelation, got: {families}"


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
