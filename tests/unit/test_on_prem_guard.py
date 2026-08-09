"""Unit tests for MODEL-01 / D-16 — on-prem allow-list guard (FIX 4 + ADDENDUM).

All tests exercise the `get_client(model=...)` function which must:
  - raise ValueError for any model ID that is NOT in ON_PREM_ALLOW_LIST
  - deny-first substring check: any string containing "claude", "gpt", or "gemini"
    must be rejected even if the exact ID is not in the allow-list
  - allow any model ID in ON_PREM_ALLOW_LIST without raising
  - no-arg get_client() resolves the default model and checks it (ADDENDUM)

FIX 4: ON_PREM_ALLOW_LIST is the single source of truth; it must be a superset of
        DETECTOR_MODELS. All model IDs in DETECTOR_MODELS must be present in ON_PREM_ALLOW_LIST.

D-16 ADDENDUM tests added (reviewer ruling B):
  (i)   serving path: forbidden id raises ValueError via serving.get_llm_client if the
        default resolves to a forbidden id
  (ii)  no-arg get_client() whose resolved default is a forbidden id raises ValueError
  (iii) positive controls: allowed LLM and embeddings ids pass (OpenAI patched)
  (iv)  structural scan: test_no_raw_openai_construction.py (separate file)
  (v)   embeddings path: forbidden embeddings id raises; databricks-bge-large-en passes

Plan 06-04: the capability-keyed skip guard has been removed — the D-16 guard is
implemented, all tests RUN and must PASS (0 skipped).
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from llm.client import get_client
import llm.client as _client_module  # for resetting the singleton between tests


# ---------------------------------------------------------------------------
# Deny-list tests — forbidden model IDs must raise ValueError
# ---------------------------------------------------------------------------

def test_forbidden_claude_model_raises_value_error():
    """Any Databricks-proxied Claude model must be rejected (on-prem constraint)."""
    with pytest.raises(ValueError):
        get_client(model="databricks-claude-3-5-sonnet")


def test_forbidden_gpt5_model_raises_value_error():
    """Any GPT model must be rejected (on-prem constraint)."""
    with pytest.raises(ValueError):
        get_client(model="databricks-gpt-5-omni")


def test_forbidden_gemini_model_raises_value_error():
    """Any Gemini model must be rejected (on-prem constraint)."""
    with pytest.raises(ValueError):
        get_client(model="databricks-gemini-2-flash")


def test_forbidden_live_claude_opus_endpoint_raises():
    """LIVE endpoint 'databricks-claude-opus-4-8' confirmed present in this workspace.

    This is the real one-string-away misconfiguration surface: a Databricks endpoint
    for Claude Opus 4.8 that exists TODAY in this workspace. The deny-first substring
    check ('claude' present) must catch it before any HTTP call leaves the process.
    Regulated pharma submission data must never reach an external LLM via config drift.
    """
    with pytest.raises(ValueError):
        get_client(model="databricks-claude-opus-4-8")


# ---------------------------------------------------------------------------
# Deny-first substring tests (FIX 4) — substring match, not just exact ID
# ---------------------------------------------------------------------------

def test_deny_substring_claude_variant():
    """Any model ID containing 'claude' (even a custom fork) must be rejected.
    The deny-first check uses substring matching, not just allow-list lookup."""
    with pytest.raises(ValueError):
        get_client(model="claude-3-opus-custom")


def test_deny_substring_gpt_variant():
    """Any model ID containing 'gpt' (even a local fork) must be rejected."""
    with pytest.raises(ValueError):
        get_client(model="gpt-4o-local-fork")


# ---------------------------------------------------------------------------
# Allow-list tests — allowed model IDs must NOT raise
# ---------------------------------------------------------------------------

def test_allowed_llama_model_does_not_raise():
    """The primary Llama 3.3 70B model must be in the allow-list."""
    with patch("llm.client.OpenAI", return_value=MagicMock()):
        # Should not raise
        get_client(model="databricks-meta-llama-3-3-70b-instruct")


def test_allowed_nemotron_does_not_raise():
    """Nemotron Super 49B must be in the allow-list (Phase 6 verifier model)."""
    with patch("llm.client.OpenAI", return_value=MagicMock()):
        get_client(model="nemotron-super-49b-v1_5")


def test_none_model_does_not_raise():
    """model=None resolves the configured default and checks it.

    D-16 ADDENDUM: Previously model=None skipped all guards. Now it resolves the
    concrete default (resolved_llm_model) and applies the deny-first substring check
    (Layer 1, always). In local dev (is_databricks=False) the allow-list check (Layer 2)
    is skipped — Ollama is localhost by construction, so any non-external model name passes.
    The default 'mistral:7b-instruct' contains no external family substrings and should
    not raise in local dev.
    """
    with patch("llm.client.OpenAI", return_value=MagicMock()):
        # In local dev (is_databricks=False), resolved default = 'mistral:7b-instruct'
        # which has no external family substrings — should not raise.
        get_client(model=None)


# ---------------------------------------------------------------------------
# FIX 4: Single-source-of-truth invariant
# ---------------------------------------------------------------------------

def test_allow_list_covers_detector_models():
    """ON_PREM_ALLOW_LIST must be a superset of DETECTOR_MODELS keys.

    Any model the user can select via the UI (DETECTOR_MODELS) must be in the
    allow-list that guards get_client. A model in DETECTOR_MODELS that is NOT in
    ON_PREM_ALLOW_LIST would create a route where the UI selects a model that the
    client then rejects — a broken invariant (FIX 4).
    """
    from config import DETECTOR_MODELS
    from llm.client import ON_PREM_ALLOW_LIST

    detector_set = set(DETECTOR_MODELS.keys())
    assert ON_PREM_ALLOW_LIST >= detector_set, (
        f"ON_PREM_ALLOW_LIST must cover all DETECTOR_MODELS. "
        f"Missing: {detector_set - ON_PREM_ALLOW_LIST}"
    )


# ---------------------------------------------------------------------------
# D-16 ADDENDUM tests (reviewer ruling B)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=False)
def reset_client_singleton():
    """Reset the get_client singleton before and after each test that modifies it."""
    orig = _client_module._client
    _client_module._client = None
    yield
    _client_module._client = orig


# (i) serving path — forbidden id reaching serving.get_llm_client raises ValueError
# when the configured default resolves to a forbidden name.
def test_serving_get_llm_client_with_forbidden_default_raises(reset_client_singleton):
    """(i) serving.get_llm_client() routes through get_client(); if resolved_llm_model
    is a forbidden external id the ValueError propagates before any HTTP call.

    Monkeypatch resolved_llm_model to a forbidden id (e.g. 'databricks-claude-opus-4-8')
    and assert serving.get_llm_client() raises ValueError.
    """
    from databricks import serving
    from config import Settings

    with patch.object(Settings, "resolved_llm_model", new_callable=lambda: property(lambda self: "databricks-claude-opus-4-8")):
        with pytest.raises(ValueError, match="claude"):
            serving.get_llm_client()


# (ii) no-arg get_client() with a forbidden default raises ValueError
def test_no_arg_get_client_forbidden_default_raises(reset_client_singleton):
    """(ii) get_client() with no args resolves the default model and checks it.

    Previously model=None skipped both the deny-first check and the allow-list check.
    After D-16 ADDENDUM, resolved_llm_model is resolved first, then the guard runs.
    Monkeypatch resolved_llm_model to a forbidden id and assert ValueError is raised.
    """
    from config import Settings

    with patch.object(Settings, "resolved_llm_model", new_callable=lambda: property(lambda self: "databricks-claude-opus-4-8")):
        with pytest.raises(ValueError, match="claude"):
            get_client()


# (iii) positive controls — allowed ids on both LLM and embeddings paths pass
def test_allowed_llm_id_via_get_client_passes(reset_client_singleton):
    """(iii-a) Allowed LLM model id passes get_client() guard without raising."""
    with patch("llm.client.OpenAI", return_value=MagicMock()):
        # Should not raise — Llama 70B is in ON_PREM_ALLOW_LIST
        client = get_client("databricks-meta-llama-3-3-70b-instruct")
        assert client is not None


def test_allowed_embeddings_id_via_get_client_passes(reset_client_singleton):
    """(iii-b) Allowed embeddings model id passes get_client() guard without raising.

    databricks-bge-large-en was added to ON_PREM_ALLOW_LIST in the D-16 ADDENDUM.
    The guard must allow it so that vector_search._embed_databricks() can call
    get_client('databricks-bge-large-en') without error.
    """
    with patch("llm.client.OpenAI", return_value=MagicMock()):
        client = get_client("databricks-bge-large-en")
        assert client is not None


# (v) embeddings path — forbidden embeddings id raises; on-prem one passes
def test_forbidden_embeddings_id_raises(reset_client_singleton):
    """(v-a) A forbidden embeddings model id (contains 'gpt') raises ValueError.

    If config drift causes the embeddings model to be set to an external endpoint,
    the guard on get_client('databricks-gpt-embeddings-large') must catch it.
    """
    with pytest.raises(ValueError, match="gpt"):
        get_client("databricks-gpt-embeddings-large")


def test_on_prem_embeddings_id_in_allow_list():
    """(v-b) databricks-bge-large-en must be in ON_PREM_ALLOW_LIST.

    This is the Databricks BGE embeddings endpoint used by vector_search._embed_databricks().
    Embeddings carry raw submission text so they are in scope for the 21 CFR Part 11
    on-prem boundary. Verified here at the allow-list level (separate from singleton test).
    """
    from config import ON_PREM_ALLOW_LIST

    assert "databricks-bge-large-en" in ON_PREM_ALLOW_LIST, (
        "databricks-bge-large-en must be in ON_PREM_ALLOW_LIST — "
        "embeddings carry raw submission text (21 CFR Part 11 scope)."
    )
