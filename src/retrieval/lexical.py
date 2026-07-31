"""Ephemeral per-submission BM25 lexical index (D-RB5's lexical leg of search_corpus).

Deliberately a SEPARATE, small wrapper from the rulebook's own local BM25 (src/rulebook/store.py)
-- the two corpora have opposite lifecycles (per-run/discarded vs. build-once/persistent) and
this ~15-line duplication keeps that boundary architecturally clean rather than coupling
retrieval to rulebook (Claude's Discretion).
"""
from __future__ import annotations

from rank_bm25 import BM25Okapi


class BM25Index:
    def __init__(self, chunk_texts: list[str], chunk_ids: list[str]) -> None:
        self._ids = list(chunk_ids)
        self._corpus_tokens = [t.lower().split() for t in chunk_texts]
        self._bm25 = BM25Okapi(self._corpus_tokens) if self._corpus_tokens else None

    def query(self, query_text: str, top_k: int = 10) -> list[str]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(query_text.lower().split())
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        return [self._ids[i] for i in ranked[:top_k]]
