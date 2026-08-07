"""D-RB5: the per-submission hybrid retrieval tool. LOCAL AND EPHEMERAL ONLY -- no Databricks
branch exists in this file by design (routing submission content to Databricks would add
network cost/latency to every run and make SC4's recall measurement non-deterministic)."""
from __future__ import annotations

import time

import numpy as np

from ingest.anchors import mint_span
from ingest.corpus import CorpusIndex
from retrieval.hybrid import reciprocal_rank_fusion
from retrieval.lexical import BM25Index
from retrieval.vector_search import embed_query, embed_texts
from tools.ledger import RetrievalLedger
from tools.textsplit import split_windows


def _nt_from_cache_entry(entry: dict):
    from schemas.documents import NormalizedText, OffsetRun
    return NormalizedText(canonical=entry["canonical"], raw_serialized=entry["raw_serialized"],
                          offset_map=[OffsetRun.model_validate(r) for r in entry["offset_map"]],
                          normalizer_version=entry["normalizer_version"], serializer_version=entry["serializer_version"])


def _build_chunks(corpus: CorpusIndex) -> list[tuple[str, int, int, str, str]]:
    """[(doc_id, start, end, chunk_text, normalizer_version), ...] over every parsed/parsed_partial doc."""
    chunks = []
    for entry in corpus.manifest.documents:
        if entry.status not in ("parsed", "parsed_partial"):
            continue
        cache = corpus.cached_entry(entry.doc_id)
        if cache is None:
            continue
        nt = _nt_from_cache_entry(cache)
        for start, end in split_windows(nt.canonical, window_chars=800):
            chunks.append((entry.doc_id, start, end, nt.canonical[start:end], nt.normalizer_version))
    return chunks


def search_corpus(corpus: CorpusIndex, query: str, ledger: RetrievalLedger, top_k: int = 10) -> list[dict]:
    chunks = _build_chunks(corpus)
    if not chunks:
        return []
    chunk_ids = [f"{doc_id}:{start}:{end}" for doc_id, start, end, _text, _nv in chunks]
    by_chunk_id = {cid: c for cid, c in zip(chunk_ids, chunks, strict=True)}

    bm25 = BM25Index([c[3] for c in chunks], chunk_ids)
    lexical_ranked = bm25.query(query, top_k=top_k * 2)

    embedding_started = time.monotonic()
    try:
        embeddings = embed_texts([c[3] for c in chunks])
        q_emb = embed_query(query).reshape(1, -1).astype(np.float32)
    finally:
        ledger.record_embedding_time(time.monotonic() - embedding_started)
    q_norm = q_emb / (np.linalg.norm(q_emb) + 1e-9)
    e_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    # D-R5A + Ruling 9 (dense score coverage): compute cosine for ALL chunks, not just top-K.
    # The old code named this `scores` then sliced it for dense_order — which meant lexical-only
    # hits (ranked low or absent in dense_order) were returned with the RRF score instead of
    # their real cosine.  Building dense_scores over range(len(chunk_ids)) ensures every chunk
    # that appears in the fused result, however it got there, has its true cosine value.
    all_scores = (e_norm @ q_norm.T).flatten()  # shape: (n_chunks,) — cosine 0–1 (L2-normalised)
    dense_scores = {chunk_ids[i]: float(all_scores[i]) for i in range(len(chunk_ids))}
    dense_order = np.argsort(all_scores)[::-1][: top_k * 2]
    dense_ranked = [chunk_ids[i] for i in dense_order]

    fused = reciprocal_rank_fusion([lexical_ranked, dense_ranked])[:top_k]

    out = []
    for cid, rrf_score in fused:
        doc_id, start, end, text, nv = by_chunk_id[cid]
        # Mint the span over the DOCUMENT's own canonical text (absolute offsets), not the
        # chunk substring -- re-reading the doc's cached entry here is cheap (already cached,
        # not re-parsed) and is what makes the returned span-ID re-openable via open_span
        # against the doc's real NormalizedText.
        cache = corpus.cached_entry(doc_id)
        nt = _nt_from_cache_entry(cache)
        span = mint_span(nt.canonical, start, end, doc_id, nv)
        ledger.record_span(span)
        out.append({
            "doc_id": doc_id, "span_id": span.model_dump(),
            # D-R5A: expose the true dense cosine (0–1) as "score" so absence.py's
            # top_score >= 0.04 threshold is a meaningful signal, not a dead branch.
            # dense_scores covers all chunk_ids (Ruling 9), so .get() always hits.
            "score": dense_scores.get(cid, 0.0),
            # Preserve RRF score for rank ordering / debugging.
            "rrf_score": rrf_score,
            "snippet": f"[{doc_id}:{start}:{end}] {text}",
        })
    return out
