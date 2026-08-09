"""Unit tests for MODEL-01 / D-16 — on-prem allow-list guard (FIX 4).

All tests exercise the `get_client(model=...)` function which must:
  - raise ValueError for any model ID that is NOT in ON_PREM_ALLOW_LIST
  - deny-first substring check: any string containing "claude", "gpt", or "gemini"
    must be rejected even if the exact ID is not in the allow-list
  - allow any model ID in ON_PREM_ALLOW_LIST without raising
  - treat model=None as a passthrough (singleton returned)

FIX 4: ON_PREM_ALLOW_LIST is the single source of truth; it must be a superset of
        DETECTOR_MODELS. All model IDs in DETECTOR_MODELS must be present in ON_PREM_ALLOW_LIST.

Plan 06-04: the capability-keyed skip guard has been removed — the D-16 guard is
implemented, all 9 tests RUN and must PASS (0 skipped).
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from llm.client import get_client


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
    """model=None is a passthrough — singleton returned, no allow-list check needed."""
    with patch("llm.client.OpenAI", return_value=MagicMock()):
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
