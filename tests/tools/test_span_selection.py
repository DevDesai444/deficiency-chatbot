"""Tests for RetrievalLedger, ToolRejected, textsplit, and oversized (Phase 2 Plan 01 Task 1)."""
from __future__ import annotations

from pathlib import Path

from schemas.documents import SpanID
from tools import RetrievalLedger, ToolRejected, oversized
from tools.textsplit import split_sentences, split_windows


def _span(doc_id="d1", start=0, end=5, h="abc") -> SpanID:
    return SpanID(doc_id=doc_id, start=start, end=end, hash=h)


# --- RetrievalLedger ----------------------------------------------------------

def test_ledger_starts_empty():
    ledger = RetrievalLedger()
    assert ledger.dedup_hit_rate() == 0.0
    assert ledger.was_issued(_span()) is False


def test_record_span_and_was_issued():
    ledger = RetrievalLedger()
    span = _span(start=0, end=5)
    ledger.record_span(span)
    assert ledger.was_issued(span) is True
    different_end = _span(start=0, end=6)
    assert ledger.was_issued(different_end) is False


def test_check_and_mark_served():
    ledger = RetrievalLedger()
    assert ledger.check_and_mark_served("d1", 0, 10) is False   # first time: renders, marks served
    assert ledger.check_and_mark_served("d1", 0, 10) is True    # identical repeat: dedup hit
    assert ledger.check_and_mark_served("d1", 0, 11) is False   # different range: not a hit


def test_dedup_hit_rate():
    ledger = RetrievalLedger()
    assert ledger.dedup_hit_rate() == 0.0
    ledger.check_and_mark_served("d1", 0, 10)   # check 1: miss
    ledger.check_and_mark_served("d1", 0, 10)   # check 2: hit
    ledger.check_and_mark_served("d1", 0, 10)   # check 3: hit
    assert ledger.dedup_hit_rate() == 2 / 3


def test_two_ledgers_never_share_state():
    """Pitfall 9 -- issued spans and served ranges never leak across separate ledger instances."""
    a, b = RetrievalLedger(), RetrievalLedger()
    span = _span()
    a.record_span(span)
    a.check_and_mark_served("d1", 0, 5)
    assert b.was_issued(span) is False
    assert b.check_and_mark_served("d1", 0, 5) is False   # b has never served this range either


# --- ToolRejected ---------------------------------------------------------------

def test_tool_rejected_round_trip_and_defaults():
    rejected = ToolRejected(tool="get_section", reason_code="range_too_large", reason="too big")
    assert rejected.hint == ""
    assert rejected.preview == ""
    assert rejected.handle == ""
    restored = ToolRejected.model_validate(rejected.model_dump())
    assert restored == rejected


def test_tool_rejected_preview_and_handle_populate():
    rejected = ToolRejected(
        tool="get_section", reason_code="range_too_large", reason="too big",
        preview="[d1:0:5] hi", handle="get_section:d1:0:100",
    )
    assert rejected.preview == "[d1:0:5] hi"
    assert rejected.handle == "get_section:d1:0:100"
    assert ToolRejected.model_validate(rejected.model_dump()) == rejected


# --- textsplit ------------------------------------------------------------------

def test_split_sentences_basic():
    text = "A. B. C"
    spans = split_sentences(text)
    assert len(spans) == 3
    pieces = [text[s:e] for s, e in spans]
    assert pieces == ["A.", "B.", "C"]
    assert all(piece.strip() for piece in pieces)   # non-empty


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_split_sentences_no_terminal_punctuation():
    text = "hello world with no terminal punctuation"
    assert split_sentences(text) == [(0, len(text))]


def test_split_windows_never_splits_mid_sentence():
    text = "One sentence here. Another sentence follows. And a third one too."
    sentences = split_sentences(text)
    windows = split_windows(text, window_chars=10)
    boundaries = {offset for pair in sentences for offset in pair}
    for w_start, w_end in windows:
        assert w_start in boundaries
        assert w_end in boundaries
    # every sentence is fully contained within exactly one window (never split across two)
    for s_start, s_end in sentences:
        assert any(w_start <= s_start and s_end <= w_end for w_start, w_end in windows)


def test_split_windows_empty_text():
    assert split_windows("") == []


# --- oversized ------------------------------------------------------------------

def test_persist_and_load_range(tmp_path):
    scratch = str(tmp_path)
    handle = oversized.persist_range("get_section", "d1", 0, 500, "nv1", cursor=100, scratch_dir=scratch)
    descriptor = oversized.load_range(handle, scratch_dir=scratch)
    assert descriptor is not None
    assert descriptor["doc_id"] == "d1"
    assert descriptor["start"] == 0
    assert descriptor["end"] == 500
    assert descriptor["normalizer_version"] == "nv1"
    assert descriptor["cursor"] == 100


def test_persist_range_is_idempotent_by_key(tmp_path):
    scratch = str(tmp_path)
    h1 = oversized.persist_range("get_section", "d1", 0, 500, "nv1", cursor=100, scratch_dir=scratch)
    h2 = oversized.persist_range("get_section", "d1", 0, 500, "nv1", cursor=200, scratch_dir=scratch)
    assert h1 == h2
    scratch_files = list(Path(scratch).glob("*.json"))
    assert len(scratch_files) == 1   # overwritten, never duplicated
    assert oversized.load_range(h2, scratch_dir=scratch)["cursor"] == 200   # latest write wins


def test_load_range_unknown_handle_returns_none(tmp_path):
    assert oversized.load_range("get_section:d1:0:1", scratch_dir=str(tmp_path)) is None


def test_advance_cursor(tmp_path):
    scratch = str(tmp_path)
    handle = oversized.persist_range("get_section", "d1", 0, 500, "nv1", cursor=100, scratch_dir=scratch)
    oversized.advance_cursor(handle, 300, scratch_dir=scratch)
    assert oversized.load_range(handle, scratch_dir=scratch)["cursor"] == 300


def test_advance_cursor_unknown_handle_is_noop(tmp_path):
    oversized.advance_cursor("get_section:d1:0:1", 50, scratch_dir=str(tmp_path))   # must not raise
    assert oversized.load_range("get_section:d1:0:1", scratch_dir=str(tmp_path)) is None
