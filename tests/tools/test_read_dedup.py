"""Read-dedup test for get_section (Phase 2 Plan 01 Task 2, COST-04)."""
from __future__ import annotations

from tests.tools.conftest import build_corpus_index
from tools.get_section import get_section


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def test_repeat_read_returns_stub_and_reports_hit_rate(tmp_path, fresh_ledger):
    body = "First sentence here. Second sentence follows. Third one too."
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])

    first = get_section(corpus, "d1", fresh_ledger, start=0, end=20)
    assert isinstance(first, str)
    assert not first.startswith("[STILL_CURRENT]")

    second = get_section(corpus, "d1", fresh_ledger, start=0, end=20)
    assert isinstance(second, str)
    assert second.startswith("[STILL_CURRENT]")

    assert fresh_ledger.dedup_hit_rate() > 0


def test_different_range_same_doc_is_not_a_dedup_hit(tmp_path, fresh_ledger):
    body = "First sentence here. Second sentence follows. Third one too."
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])

    get_section(corpus, "d1", fresh_ledger, start=0, end=20)
    different = get_section(corpus, "d1", fresh_ledger, start=20, end=40)
    assert isinstance(different, str)
    assert not different.startswith("[STILL_CURRENT]")
    assert fresh_ledger.dedup_hit_rate() == 0.0
