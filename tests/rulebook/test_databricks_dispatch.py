"""Tests for src/databricks/rulebook.py's dispatch seam (Plan 02-08 Task 2, D-RB6 HARD offline
contract) -- proves rulebook.store.rulebook_search correctly routes to the Databricks branch
(databricks.rulebook.search_rulebook_databricks) when is_databricks=True, WITHOUT ever reaching
real Databricks: search_rulebook_databricks itself is monkeypatched to a fake in-test function.

Mirrors tests/rulebook/conftest.py's fixture_chunk builder and test_store.py's dispatch-test
conventions (config_module.get_settings monkeypatch) for consistency. Makes ZERO real HTTP/
network calls -- no httpx/requests import is exercised un-mocked here, and no real .env
Databricks credentials are required for this test to pass (D-RB6 HARD constraint).
"""

from __future__ import annotations

import config as config_module
from config import Settings
from rulebook import store
from tests.rulebook.conftest import fixture_chunk


def test_rulebook_search_dispatches_to_databricks_branch_without_touching_real_databricks(
    tmp_path, monkeypatch
):
    """is_databricks=True correctly reaches databricks.rulebook.search_rulebook_databricks --
    proving the two-backend seam Plan 02-02 wired is now fulfilled end-to-end (D-RB6/D-RB2).
    search_rulebook_databricks is monkeypatched to a fake, in-test function: this test makes
    ZERO real HTTP/network calls and requires no Databricks credentials to pass."""
    fake_chunk, _nt, _cache_dir, _db_path = fixture_chunk(tmp_path)
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(environment="databricks"))
    monkeypatch.setattr("databricks.rulebook.search_rulebook_databricks", lambda q, k: [fake_chunk])

    result = store.rulebook_search("anything", top_k=3)

    assert result == [fake_chunk]
