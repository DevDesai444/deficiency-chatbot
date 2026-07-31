"""retrieval.lexical.BM25Index -- the ephemeral per-submission lexical leg (D-RB5)."""
from __future__ import annotations

from retrieval.lexical import BM25Index


def test_bm25_ranks_exact_token_match_above_non_match():
    idx = BM25Index(
        chunk_texts=[
            "the quick brown fox jumps over the lazy dog",
            "a completely unrelated sentence about something else",
        ],
        chunk_ids=["c1", "c2"],
    )
    result = idx.query("quick brown fox", top_k=5)
    assert result[0] == "c1"


def test_bm25_exact_numeric_identifier_outranks_semantically_similar_chunk():
    idx = BM25Index(
        chunk_texts=[
            "Batch 11477 showed 0.3% degradation after six months of stability testing.",
            "Batch 20038 showed 0.3% degradation after six months of stability testing.",
        ],
        chunk_ids=["batch-11477-doc", "batch-20038-doc"],
    )
    result = idx.query("11477", top_k=5)
    assert result[0] == "batch-11477-doc"


def test_bm25_empty_corpus_returns_empty_list_never_raises():
    idx = BM25Index(chunk_texts=[], chunk_ids=[])
    assert idx.query("anything", top_k=5) == []


def test_bm25_respects_top_k():
    idx = BM25Index(
        chunk_texts=["alpha beta", "alpha gamma", "alpha delta"],
        chunk_ids=["c1", "c2", "c3"],
    )
    result = idx.query("alpha", top_k=2)
    assert len(result) == 2
