"""Shared Wave-0 test scaffolding for the Phase-2 tools suite (mirrors tests/ingest/conftest.py's
discipline: every tests/tools/* test imports fixtures/builders from here, entirely offline).

Provides:
  * `fresh_ledger`   -- a brand-new, per-test `RetrievalLedger()`.
  * `make_doc_dict`  -- re-exported directly from tests.ingest.conftest (import it, never
                         duplicate it) for building fixture corpus documents in later tasks.
"""
from __future__ import annotations

import pytest

from tests.ingest.conftest import (
    make_doc_dict,  # noqa: F401 -- re-exported for tests/tools/* fixture builders
)
from tools.ledger import RetrievalLedger


@pytest.fixture
def fresh_ledger() -> RetrievalLedger:
    return RetrievalLedger()
