"""Tests for src/rulebook/store.py -- RuleChunk model, atomic local persistence, citation
lookup (Task 1), and the local FAISS+BM25 hybrid search + is_databricks dispatch seam
(Task 2) -- Plan 02-02, RULES-04.

Offline, no-network, no-Databricks (D-RB6): every test drives the LOCAL backend only, using
tmp_path-scoped cache_dir/db_path so runs never touch (or depend on) the shared data/ dir.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import config as config_module
import rulebook.store as store
from config import Settings
from ingest.anchors import HashMismatch, open_span
from rulebook.store import (
    RuleChunk,
    all_chunks,
    lookup_citation,
    read_chunk_nt,
    rulebook_nt_for,
    write_chunk,
)
from tests.rulebook.conftest import fixture_chunk

# --- RuleChunk model ---------------------------------------------------------


def test_rulechunk_validates_and_round_trips(tmp_path):
    chunk, _nt, _cache_dir, _db_path = fixture_chunk(tmp_path)
    dumped = chunk.model_dump()
    restored = RuleChunk.model_validate(dumped)
    assert restored == chunk
    assert dumped["citation"] == chunk.citation
    assert dumped["source"] == chunk.source


# --- write_chunk / read_chunk_nt --------------------------------------------


def test_write_then_read_chunk_nt_round_trips(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)

    got = read_chunk_nt(chunk.doc_id, cache_dir=cache_dir)

    assert got is not None
    assert got.canonical == nt.canonical
    assert got.raw_serialized == nt.raw_serialized
    assert got.normalizer_version == nt.normalizer_version
    assert got.serializer_version == nt.serializer_version
    assert [r.model_dump() for r in got.offset_map] == [r.model_dump() for r in nt.offset_map]


def test_rulebook_nt_for_is_an_alias_of_read_chunk_nt(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)

    assert rulebook_nt_for(chunk.doc_id, cache_dir=cache_dir) == read_chunk_nt(
        chunk.doc_id, cache_dir=cache_dir
    )


def test_read_chunk_nt_missing_doc_id_returns_none(tmp_path):
    cache_dir = str(tmp_path / "empty_cache")
    assert read_chunk_nt("does-not-exist", cache_dir=cache_dir) is None


# --- lookup_citation / all_chunks -------------------------------------------


def test_lookup_citation_exact_match(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(
        tmp_path, doc_id="21-cfr-211.166", citation="21 CFR 211.166"
    )
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)

    found = lookup_citation("21 CFR 211.166", db_path=db_path)

    assert found is not None
    assert found.doc_id == chunk.doc_id
    assert found.citation == "21 CFR 211.166"


def test_lookup_citation_unknown_returns_none(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)

    assert lookup_citation("21 CFR 999.999", db_path=db_path) is None


def test_all_chunks_returns_every_persisted_chunk(tmp_path):
    cache_dir = str(tmp_path / "cache")
    db_path = str(tmp_path / "test.db")
    chunk1, nt1, _, _ = fixture_chunk(
        tmp_path,
        doc_id="21-cfr-211.166",
        citation="21 CFR 211.166",
        text="Stability testing procedures.",
    )
    chunk2, nt2, _, _ = fixture_chunk(
        tmp_path,
        doc_id="21-cfr-211.100",
        citation="21 CFR 211.100",
        text="Written production and control procedures.",
    )
    write_chunk(chunk1, nt1, cache_dir=cache_dir, db_path=db_path)
    write_chunk(chunk2, nt2, cache_dir=cache_dir, db_path=db_path)

    chunks = all_chunks(db_path=db_path)

    assert {c.doc_id for c in chunks} == {chunk1.doc_id, chunk2.doc_id}


def test_write_chunk_same_doc_id_overwrites_not_duplicates(tmp_path):
    cache_dir = str(tmp_path / "cache")
    db_path = str(tmp_path / "test.db")
    chunk_v1, nt_v1, _, _ = fixture_chunk(
        tmp_path,
        doc_id="21-cfr-211.166",
        citation="21 CFR 211.166",
        text="First version text.",
    )
    write_chunk(chunk_v1, nt_v1, cache_dir=cache_dir, db_path=db_path)

    chunk_v2, nt_v2, _, _ = fixture_chunk(
        tmp_path,
        doc_id="21-cfr-211.166",
        citation="21 CFR 211.166 (rev)",
        text="Second, revised version text.",
    )
    write_chunk(chunk_v2, nt_v2, cache_dir=cache_dir, db_path=db_path)

    chunks = all_chunks(db_path=db_path)
    matching = [c for c in chunks if c.doc_id == "21-cfr-211.166"]
    assert len(matching) == 1
    assert matching[0].citation == "21 CFR 211.166 (rev)"
    # the cache file was also overwritten, not left stale
    got = read_chunk_nt("21-cfr-211.166", cache_dir=cache_dir)
    assert got.canonical == nt_v2.canonical


# --- span re-open: same grounding primitive as submission spans ------------


def test_written_chunk_span_reopens_byte_exact_via_open_span(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)
    got_nt = read_chunk_nt(chunk.doc_id, cache_dir=cache_dir)

    raw, canonical = open_span(chunk.span, got_nt, chunk.doc_id)

    assert canonical == nt.canonical[chunk.span.start : chunk.span.end]
    assert canonical == nt.canonical  # fixture mints a whole-chunk span (0, len)
    assert raw  # the raw citation-source substring is non-empty


def test_reopening_chunk_span_under_wrong_doc_id_raises_hash_mismatch(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)
    got_nt = read_chunk_nt(chunk.doc_id, cache_dir=cache_dir)

    with pytest.raises(HashMismatch):
        open_span(chunk.span, got_nt, "a-different-doc-id")


# --- atomic write -------------------------------------------------------------


def test_write_chunk_is_atomic_no_tmp_file_left_on_success(tmp_path):
    chunk, nt, cache_dir, db_path = fixture_chunk(tmp_path)
    write_chunk(chunk, nt, cache_dir=cache_dir, db_path=db_path)

    assert list(Path(cache_dir).glob("*.tmp")) == []


def test_crash_mid_write_leaves_no_half_written_cache_file(tmp_path):
    """Simulates a crash BEFORE os.replace: only a .tmp exists on disk -> read returns None,
    mirroring tests/ingest/test_store.py's crash-simulation pattern exactly."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    doc_id = "half-written-doc"
    safe = doc_id.replace("/", "_")
    (cache_dir / f"{safe}.tmp").write_text("{partial", encoding="utf-8")

    assert read_chunk_nt(doc_id, cache_dir=str(cache_dir)) is None


# --- rulebook_search: local hybrid (FAISS + lexical) search (Task 2) -------


@pytest.fixture(autouse=True)
def _reset_faiss_module_cache(monkeypatch):
    """The FAISS index is an intentional process-lifetime module-level cache (mirrors
    databricks/vector.py's _ensure_faiss). Reset it before/after every test in this module so
    one test's monkeypatched index can never leak into another (test-order independence).

    raising=False: at Task-2 RED time _faiss_index/_faiss_doc_ids do not exist on the module
    yet -- this fixture must not itself break Task 1's already-passing tests while Task 2's
    tests are still red.
    """
    monkeypatch.setattr(store, "_faiss_index", None, raising=False)
    monkeypatch.setattr(store, "_faiss_doc_ids", [], raising=False)
    yield


def test_rulebook_search_local_ranks_exact_substring_match_first(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(environment="local"))
    monkeypatch.setattr(store, "_ensure_faiss", lambda: None)  # no FAISS index -- pure lexical leg

    chunk_a, nt_a, _, _ = fixture_chunk(
        tmp_path,
        doc_id="doc-a",
        citation="21 CFR 211.166",
        text="Stability testing procedures for drug products.",
    )
    chunk_b, nt_b, _, _ = fixture_chunk(
        tmp_path,
        doc_id="doc-b",
        citation="21 CFR 211.100",
        text="Container closure system requirements for packaging.",
    )
    nt_by_doc = {chunk_a.doc_id: nt_a, chunk_b.doc_id: nt_b}
    monkeypatch.setattr(store, "all_chunks", lambda db_path=store._DB_PATH: [chunk_a, chunk_b])
    monkeypatch.setattr(
        store,
        "read_chunk_nt",
        lambda doc_id, cache_dir=store.DEFAULT_RULEBOOK_CACHE_DIR: nt_by_doc.get(doc_id),
    )

    results = store.rulebook_search("stability testing", top_k=5)

    assert results, "expected at least one ranked result"
    assert results[0].doc_id == chunk_a.doc_id


def test_rulebook_search_local_returns_ranked_list_with_no_network_call(tmp_path, monkeypatch):
    """Confirms the return type/shape (a ranked list[RuleChunk]) and that no faiss index on
    disk / no embeddings call is required for the local backend to answer a query."""
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(environment="local"))
    monkeypatch.setattr(store, "_ensure_faiss", lambda: None)

    chunk, nt, _, _ = fixture_chunk(tmp_path)
    monkeypatch.setattr(store, "all_chunks", lambda db_path=store._DB_PATH: [chunk])
    monkeypatch.setattr(
        store,
        "read_chunk_nt",
        lambda doc_id, cache_dir=store.DEFAULT_RULEBOOK_CACHE_DIR: nt if doc_id == chunk.doc_id else None,
    )

    results = store.rulebook_search("stability", top_k=5)

    assert isinstance(results, list)
    assert all(isinstance(r, RuleChunk) for r in results)
    assert results[0].doc_id == chunk.doc_id


def test_rulebook_search_local_with_empty_corpus_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(environment="local"))
    monkeypatch.setattr(store, "_ensure_faiss", lambda: None)
    monkeypatch.setattr(store, "all_chunks", lambda db_path=store._DB_PATH: [])

    assert store.rulebook_search("anything", top_k=5) == []


def test_rulebook_search_dense_leg_is_consulted_when_faiss_index_present(tmp_path, monkeypatch):
    """The dense (FAISS) leg is exercised (not skipped) when a populated index exists -- this
    proves the FAISS query wiring (index.search + embed_query integration) is correct and
    raises no exception. Final fusion currently falls back to pure-lexical ranking until
    retrieval.hybrid lands in Plan 02-04 (see the documented ImportError branch in
    _rulebook_search_local), so this asserts the dense leg runs cleanly end-to-end and the
    expected chunks still surface -- not a specific dense-driven fused order."""
    import faiss

    import retrieval.vector_search as vs_module

    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(environment="local"))

    chunk_a, nt_a, _, _ = fixture_chunk(
        tmp_path,
        doc_id="doc-a",
        citation="21 CFR 211.166",
        text="Stability testing procedures for drug products.",
    )
    chunk_b, nt_b, _, _ = fixture_chunk(
        tmp_path,
        doc_id="doc-b",
        citation="21 CFR 211.100",
        text="Container closure system requirements for packaging.",
    )
    nt_by_doc = {chunk_a.doc_id: nt_a, chunk_b.doc_id: nt_b}
    monkeypatch.setattr(store, "all_chunks", lambda db_path=store._DB_PATH: [chunk_a, chunk_b])
    monkeypatch.setattr(
        store,
        "read_chunk_nt",
        lambda doc_id, cache_dir=store.DEFAULT_RULEBOOK_CACHE_DIR: nt_by_doc.get(doc_id),
    )

    # a tiny, real, in-memory FAISS index -- no disk, no network.
    dim = 2
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    monkeypatch.setattr(store, "_faiss_index", index)
    monkeypatch.setattr(store, "_faiss_doc_ids", [chunk_a.doc_id, chunk_b.doc_id])
    monkeypatch.setattr(store, "_ensure_faiss", lambda: None)  # index already "warm"
    monkeypatch.setattr(vs_module, "embed_query", lambda text: np.array([1.0, 0.0], dtype="float32"))

    results = store.rulebook_search("stability testing", top_k=5)

    assert {c.doc_id for c in results} == {chunk_a.doc_id, chunk_b.doc_id}
    assert results[0].doc_id == chunk_a.doc_id  # lexical leg still ranks the substring match first


def test_rulebook_search_databricks_dispatch_fails_loudly_not_silently(tmp_path, monkeypatch):
    """is_databricks=True but src/databricks/rulebook.py does not exist yet (lands in Plan
    02-08) -- must raise, never silently fall back to the local branch (D-RB6 / T-02-08)."""
    monkeypatch.setattr(config_module, "get_settings", lambda: Settings(environment="databricks"))

    with pytest.raises((ImportError, ModuleNotFoundError)):
        store.rulebook_search("stability testing", top_k=3)
