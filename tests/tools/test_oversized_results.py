"""Oversized-range tests for get_section (Phase 2 Plan 01 Task 2, TOOLS-04 plan-checker Blocker 2).

`oversized.DEFAULT_SCRATCH_DIR` ("data/tool_scratch") is a RELATIVE path baked into
persist_range/load_range/advance_cursor's own default parameter at import time -- monkeypatching
the module attribute after import does not retroactively change an already-bound default.
`monkeypatch.chdir(tmp_path)` sidesteps that entirely: the relative default then resolves
inside pytest's own temp directory, so no scratch file ever leaks into the real repo tree.
"""
from __future__ import annotations

import pytest

from tests.tools.conftest import build_corpus_index
from tools.errors import ToolRejected
from tools.get_section import get_section


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


@pytest.fixture(autouse=True)
def _scratch_in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_oversized_fails_not_truncates(tmp_path, fresh_ledger):
    body = "Word. " * 3000
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])
    canonical = corpus.cached_entry("d1")["canonical"]

    result = get_section(corpus, "d1", fresh_ledger, start=0, end=len(canonical), max_chars=100)
    assert isinstance(result, ToolRejected)
    assert result.reason_code == "range_too_large"
    assert result.preview != ""    # TOOLS-04 preview populated, never blank
    assert result.handle != ""     # TOOLS-04 handle populated, never blank
    assert len(result.preview) < len(canonical)   # a bounded preview, not the whole range


def test_oversized_persist_preview_handle_pages_forward(tmp_path, fresh_ledger):
    body = "Word. " * 3000
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])
    canonical = corpus.cached_entry("d1")["canonical"]

    rejected = get_section(corpus, "d1", fresh_ledger, start=0, end=len(canonical), max_chars=100)
    assert isinstance(rejected, ToolRejected)
    assert rejected.handle

    continued = get_section(corpus, "d1", fresh_ledger, handle=rejected.handle, max_chars=100)
    assert isinstance(continued, str)          # a NEW bounded, annotated chunk -- not a rejection
    assert continued != rejected.preview       # genuinely new text, not the same preview again
    assert continued.startswith("[d1:")        # still span-ID-annotated (D-GRAN)

    # the agent NEVER recomputes (start,end) itself -- an unrelated/unknown handle is rejected
    unknown = get_section(corpus, "d1", fresh_ledger, handle="get_section:d1:9999:99999")
    assert isinstance(unknown, ToolRejected)
    assert unknown.reason_code == "not_found"


def test_oversized_handle_rejects_wrong_doc_id(tmp_path, fresh_ledger):
    body = "Word. " * 3000
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])
    canonical = corpus.cached_entry("d1")["canonical"]
    rejected = get_section(corpus, "d1", fresh_ledger, start=0, end=len(canonical), max_chars=100)
    assert isinstance(rejected, ToolRejected)

    other_corpus = build_corpus_index(tmp_path, "d2", [_block("Unrelated document body text.")])
    mismatched = get_section(other_corpus, "d2", fresh_ledger, handle=rejected.handle)
    assert isinstance(mismatched, ToolRejected)
    assert mismatched.reason_code == "not_found"
