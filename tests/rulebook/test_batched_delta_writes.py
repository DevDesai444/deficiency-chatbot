"""Batched Databricks write primitives + the filtered/incremental rulebook push.

push_chunks_to_delta used to issue FOUR serial statements per chunk (DELETE+INSERT chunks,
DELETE+INSERT embeddings). At 5,031 chunks that is ~20,000 serial Statement Execution API round
trips -- many hours. These tests pin the batched replacement.

ZERO live Databricks calls: _run_sql is monkeypatched everywhere and every statement is captured
for inspection. No credentials required.
"""
from __future__ import annotations

import numpy as np
import pytest

from databricks import delta as delta_mod
from databricks import rulebook as dbx_rulebook
from tests.rulebook.conftest import fixture_chunk


@pytest.fixture
def captured(monkeypatch):
    statements: list[str] = []
    monkeypatch.setattr(delta_mod, "_run_sql", lambda stmt: statements.append(stmt) or {})
    return statements


# --- _batched_insert / _delete_by_keys ------------------------------------------------------


def test_batched_insert_splits_on_byte_budget_and_preserves_every_tuple(captured):
    tuples = [(f"doc-{i}", f"text-{i}") for i in range(100)]
    written = delta_mod._batched_insert("t", ["doc_id", "body"], tuples, max_stmt_chars=400)

    assert written == 100
    assert len(captured) > 1, "a tiny byte budget must produce more than one statement"
    joined = "\n".join(captured)
    for doc_id, body in tuples:
        assert joined.count(f"'{doc_id}'") == 1
        assert joined.count(f"'{body}'") == 1
    assert all(s.startswith("INSERT INTO t (doc_id, body) VALUES ") for s in captured)


def test_batched_insert_emits_a_single_statement_when_everything_fits(captured):
    tuples = [(f"doc-{i}",) for i in range(50)]
    written = delta_mod._batched_insert("t", ["doc_id"], tuples)
    assert written == 50
    assert len(captured) == 1


def test_batched_insert_never_silently_drops_an_oversized_row(captured):
    """An eCFR canonical text can run ~46k chars. One row that alone blows the budget must
    still be written -- at least one row per statement, always."""
    huge = "x" * 5000
    written = delta_mod._batched_insert("t", ["body"], [(huge,), ("small",)], max_stmt_chars=100)
    assert written == 2
    assert len(captured) == 2
    assert huge in captured[0]
    assert "'small'" in captured[1]


def test_batched_insert_escapes_quotes_and_backslashes(captured):
    """T-JBZ-01: multi-row batching raises the blast radius of one bad escape from 1 row to
    ~200, so the escape path is pinned. 5,096 rows of vendor-authored spreadsheet text are
    interpolated into these statements."""
    nasty = "O'Brien said \\ 'drop table'"
    delta_mod._batched_insert("t", ["body"], [(nasty,)])
    assert captured[0].endswith(f"VALUES ({delta_mod._escape(nasty)})")
    assert "O''Brien" in captured[0]
    assert "\\\\" in captured[0]


def test_batched_insert_reports_statement_count_through_stats(captured):
    stats: dict = {}
    delta_mod._batched_insert("t", ["body"], [(f"v{i}",) for i in range(100)],
                              max_stmt_chars=200, stats=stats)
    assert stats["statements"] == len(captured)


def test_sql_literal_only_accepts_integers():
    """The one value that is NOT quoted is the bigint id. Its wrapper coerces via int(), so
    there is no path for arbitrary text to render unquoted."""
    assert str(delta_mod._SqlLiteral(501)) == "501"
    with pytest.raises((ValueError, TypeError)):
        delta_mod._SqlLiteral("501; DROP TABLE x")


def test_delete_by_keys_batches_and_covers_every_key(captured):
    keys = [f"doc-{i}" for i in range(100)]
    deleted = delta_mod._delete_by_keys("t", "doc_id", keys, max_stmt_chars=300)
    assert deleted == 100
    assert len(captured) > 1
    joined = "\n".join(captured)
    for k in keys:
        assert joined.count(f"'{k}'") == 1
    assert all(s.startswith("DELETE FROM t WHERE doc_id IN (") for s in captured)


def test_delete_by_keys_noop_on_empty(captured):
    assert delta_mod._delete_by_keys("t", "doc_id", []) == 0
    assert captured == []


# --- push_chunks_to_delta ------------------------------------------------------------------


def _fake_remote_result(doc_ids: list[str]) -> dict:
    return {
        "manifest": {"schema": {"columns": [{"name": "doc_id"}]}},
        "result": {"data_array": [[d] for d in doc_ids]},
    }


def test_push_is_source_filtered_incremental_and_batched(tmp_path, monkeypatch):
    """Task 3 calls this with sources=("precedent",) and it is LOAD-BEARING: local holds ich=5
    while Databricks holds ich=4 (pre-existing, deliberately out-of-scope drift). Without the
    source filter, only_missing would helpfully push that stray ich chunk and land
    rulebook_embeddings at 5,032 instead of 5,031."""
    local_chunks = (
        [fixture_chunk(tmp_path, doc_id=f"precedent-{i}", source="precedent")[0] for i in range(30)]
        + [fixture_chunk(tmp_path, doc_id="ich-Q1A-R2", source="ich")[0]]
        + [fixture_chunk(tmp_path, doc_id="ecfr-211.166", source="ecfr")[0]]
    )
    already_remote = [f"precedent-{i}" for i in range(10)] + ["ecfr-211.166"]

    statements: list[str] = []

    def fake_run_sql(stmt: str):
        statements.append(stmt)
        if stmt.lstrip().upper().startswith("SELECT DOC_ID"):
            return _fake_remote_result(already_remote)
        return {}

    monkeypatch.setattr(delta_mod, "_run_sql", fake_run_sql)
    monkeypatch.setattr(dbx_rulebook, "_run_sql", fake_run_sql)
    monkeypatch.setattr(dbx_rulebook, "_table", lambda name: f"cat.sch.{name}")
    monkeypatch.setattr(delta_mod, "_table", lambda name: f"cat.sch.{name}")
    monkeypatch.setattr(dbx_rulebook, "all_chunks", lambda: local_chunks)
    monkeypatch.setattr(
        dbx_rulebook, "read_chunk_nt",
        lambda doc_id: type("NT", (), {"canonical": f"canonical text for {doc_id}"})(),
    )

    embed_calls: list[list[str]] = []

    def fake_embed(texts, **kwargs):
        embed_calls.append(list(texts))
        return np.zeros((len(texts), 4), dtype=np.float32)

    monkeypatch.setattr("retrieval.vector_search.embed_texts", fake_embed)

    report = dbx_rulebook.push_chunks_to_delta(sources=("precedent",), only_missing=True)

    assert report["candidates"] == 30
    assert report["skipped_existing"] == 10
    assert report["pushed"] == 20
    # the whole point: O(batches), not 4 statements per chunk
    assert report["statements"] < report["candidates"]
    assert report["statements"] < 4 * report["pushed"]

    joined = "\n".join(statements)
    # ich/ecfr must be untouched -- no DDL-free statement may name them
    assert "ich-Q1A-R2" not in joined
    assert "ecfr-211.166" not in joined
    # only the 20 missing precedent ids are embedded and written
    assert len(embed_calls) == 1
    assert len(embed_calls[0]) == 20
    for i in range(10, 30):
        assert f"'precedent-{i}'" in joined
    for i in range(10):
        assert f"'precedent-{i}'" not in joined


def test_push_without_source_filter_considers_every_chunk(tmp_path, monkeypatch):
    local_chunks = [
        fixture_chunk(tmp_path, doc_id="precedent-1", source="precedent")[0],
        fixture_chunk(tmp_path, doc_id="ich-Q1A-R2", source="ich")[0],
    ]
    monkeypatch.setattr(delta_mod, "_run_sql", lambda stmt: {})
    monkeypatch.setattr(dbx_rulebook, "_run_sql", lambda stmt: {})
    monkeypatch.setattr(dbx_rulebook, "_table", lambda name: f"cat.sch.{name}")
    monkeypatch.setattr(delta_mod, "_table", lambda name: f"cat.sch.{name}")
    monkeypatch.setattr(dbx_rulebook, "all_chunks", lambda: local_chunks)
    monkeypatch.setattr(
        dbx_rulebook, "read_chunk_nt",
        lambda doc_id: type("NT", (), {"canonical": "text"})(),
    )
    monkeypatch.setattr(
        "retrieval.vector_search.embed_texts",
        lambda texts, **kw: np.zeros((len(texts), 4), dtype=np.float32),
    )

    report = dbx_rulebook.push_chunks_to_delta()
    assert report["candidates"] == 2
    assert report["pushed"] == 2
