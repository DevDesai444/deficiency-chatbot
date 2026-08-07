"""D-RB5: the per-submission hybrid retrieval tool. LOCAL AND EPHEMERAL ONLY -- no Databricks
branch exists in this file by design (routing submission content to Databricks would add
network cost/latency to every run and make SC4's recall measurement non-deterministic).

D-R5A (Wave 2): `score` field is the true dense cosine similarity (0–1) for ALL fused chunks,
including lexical-only hits (Ruling 9 dense coverage).  `rrf_score` is preserved for ordering.
The old code returned the RRF score (max 0.0328) which was permanently below absence.py's 0.04
threshold — a dead branch on every call.

D-R5B (Wave 2): per-doc search index sidecars are built ONCE at ingest time
(build_doc_index / corpus.py) and loaded at query time (_search_with_persisted_index).
This avoids re-embedding the whole corpus on every search_corpus call — O(corpus) per
query drops to O(query) once sidecars are present.  Backward-compat: if sidecars are
absent (first run, legacy corpus, or build failure) the legacy embed-all path is used.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

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


def _build_doc_chunks(nt, doc_id: str) -> list[dict]:
    """Build chunk dicts for a single document's NormalizedText.

    Returns list of {"doc_id", "start", "end", "text", "normalizer_version"} dicts,
    matching the window sizes used by _build_chunks.
    """
    chunks = []
    for start, end in split_windows(nt.canonical, window_chars=800):
        chunks.append({
            "doc_id": doc_id,
            "start": start,
            "end": end,
            "text": nt.canonical[start:end],
            "normalizer_version": nt.normalizer_version,
        })
    return chunks


def _index_sidecar_paths(cache_dir: str, key: str) -> dict[str, Path]:
    """Return the canonical sidecar file paths for a given cache key.

    D-R5B: sidecars are keyed by the same content_hash + version cache_key as the
    JSON doc cache, so a file whose bytes change gets a new content_hash and rebuilds
    its sidecars (D-CON2 invalidation-by-hash).
    """
    base = Path(cache_dir)
    return {
        "chunks": base / f"{key}.chunks.json",
        "embeddings": base / f"{key}.embeddings.npy",
        "bm25": base / f"{key}.bm25.json",
    }


def build_doc_index(cache_dir: str, key: str, nt, doc_id: str) -> None:
    """Build and persist per-doc search index sidecars at ingest time.

    Called by ingest_corpus after write_doc_cache so that search_corpus can load
    sidecars at query time instead of re-embedding the whole submission (D-R5B).

    Sidecar files:
      {key}.chunks.json    — list of chunk metadata dicts (doc_id/start/end/text/nv)
      {key}.bm25.json      — list[list[str]] tokenized corpus for BM25Okapi rebuild
      {key}.embeddings.npy — float32 array shape (n_chunks, dim) with L2-normalised vectors

    All three are written atomically (tmp → os.replace) per Pitfall 7.

    Ruling 9 (.npy atomic-write fix): np.save(path, arr) appends ".npy" to the filename
    when path does NOT already end in ".npy".  Using ".tmp" as a suffix creates
    "{key}.embeddings.tmp.npy" — so os.replace("{key}.embeddings.tmp", ...) fails with
    FileNotFoundError.  We avoid this by using an open() file handle: np.save(f, arr)
    writes directly to the open binary stream and NEVER appends ".npy" regardless of the
    filename.  This is the only correct approach that is also suffix-independent.

    Errors are logged as warnings and never propagate — ingest's D-16 never-abort contract
    requires that a build_doc_index failure cannot crash or skip the document.
    """
    try:
        import structlog
        _log = structlog.get_logger()

        paths = _index_sidecar_paths(cache_dir, key)
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

        chunks = _build_doc_chunks(nt, doc_id)
        if not chunks:
            return  # nothing to index for this doc

        chunk_texts = [c["text"] for c in chunks]
        # Embed all chunks for this document — only happens at ingest, not at query time (D-R5B)
        embeddings = embed_texts(chunk_texts)  # shape: (n_chunks, dim)
        # L2-normalise so cosine = inner product at query time
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9
        embeddings_norm = (embeddings / norms).astype(np.float32)

        tokenized = [t.lower().split() for t in chunk_texts]

        # .chunks.json — atomic text write (plain JSON: no .npy edge case)
        chunks_tmp = paths["chunks"].with_name(paths["chunks"].name + ".tmp")
        chunks_tmp.write_text(json.dumps(chunks), encoding="utf-8")
        os.replace(chunks_tmp, paths["chunks"])

        # .bm25.json — atomic text write (tokenized corpus: list[list[str]])
        bm25_tmp = paths["bm25"].with_name(paths["bm25"].name + ".tmp")
        bm25_tmp.write_text(json.dumps(tokenized), encoding="utf-8")
        os.replace(bm25_tmp, paths["bm25"])

        # .embeddings.npy — CORRECT atomic write (Ruling 9: open file handle avoids .npy append)
        # WRONG pattern (creates "{key}.embeddings.tmp.npy", not "{key}.embeddings.tmp"):
        #   np.save(paths["embeddings"].with_suffix(".tmp"), embeddings_norm)
        # CORRECT: use open() binary stream — np.save(f, arr) never appends ".npy" to a stream
        emb_tmp = paths["embeddings"].with_name(paths["embeddings"].name + ".tmp")
        with open(emb_tmp, "wb") as f:
            np.save(f, embeddings_norm)
        os.replace(emb_tmp, paths["embeddings"])

    except Exception as exc:  # noqa: BLE001
        try:
            import structlog as _sl
            _sl.get_logger().warning("build_doc_index_failed", doc_id=doc_id, error=str(exc)[:200])
        except Exception:  # noqa: BLE001
            pass  # structlog itself unavailable — swallow silently per D-16


def _has_persisted_index(corpus: CorpusIndex) -> bool:
    """Return True iff ALL parseable docs in the corpus have their .chunks.json sidecar.

    D-R5B: the fast query path is only safe when EVERY parseable doc's sidecar is
    present — a partial set means at least one doc's chunks would be missing from
    the search, silently dropping recall.

    Ruling 9 (key exposure): uses corpus.cache_key_for(doc_id) to locate sidecars
    without re-hashing file bytes — the key is derived from the already-computed
    content_hash in the manifest.
    """
    for entry in corpus.manifest.documents:
        if entry.status not in ("parsed", "parsed_partial"):
            continue
        key = corpus.cache_key_for(entry.doc_id)
        if key is None:
            return False
        paths = _index_sidecar_paths(corpus.cache_dir, key)
        if not paths["chunks"].exists() or not paths["embeddings"].exists() or not paths["bm25"].exists():
            return False
    return True


def _search_with_persisted_index(
    corpus: CorpusIndex, query: str, ledger: RetrievalLedger, top_k: int
) -> list[dict]:
    """Fast query path: load sidecars, embed ONLY the query, compute cosine for all chunks.

    D-R5B: at query time, only the query vector is computed — the corpus embeddings are
    loaded from .embeddings.npy sidecars built at ingest.

    Ruling 9 (dense score coverage): dense_scores covers ALL chunk_ids loaded from sidecars,
    matching the Task-1 fix so lexical-only hits are never silently zeroed.

    Security (T-05W1-01): np.load uses allow_pickle=False — disables pickle deserialization.
    If allow_pickle=False raises on a poisoned file, fall back to _search_legacy.
    Security (T-05W1-02): json.loads is safe (no code execution).
    Security (T-05W1-04): any sidecar load error falls back to _search_legacy with a warning.
    """
    import structlog
    _log = structlog.get_logger()

    # Collect all chunks + embeddings across docs from sidecars
    all_chunks: list[tuple[str, int, int, str, str]] = []
    all_embeddings_list: list[np.ndarray] = []

    for entry in corpus.manifest.documents:
        if entry.status not in ("parsed", "parsed_partial"):
            continue
        key = corpus.cache_key_for(entry.doc_id)
        if key is None:
            _log.warning("sidecar_key_missing", doc_id=entry.doc_id)
            return _search_legacy(corpus, query, ledger, top_k)
        paths = _index_sidecar_paths(corpus.cache_dir, key)
        try:
            doc_chunks = json.loads(paths["chunks"].read_text(encoding="utf-8"))
            # Security T-05W1-01: allow_pickle=False prevents pickle deserialization
            doc_emb = np.load(str(paths["embeddings"]), allow_pickle=False)
            # Validate shape consistency
            if len(doc_chunks) != doc_emb.shape[0]:
                raise ValueError(
                    f"Sidecar shape mismatch for {entry.doc_id}: "
                    f"{len(doc_chunks)} chunks vs {doc_emb.shape[0]} embeddings"
                )
        except Exception as exc:  # noqa: BLE001 — T-05W1-04: any load error falls back
            _log.warning("sidecar_load_failed", doc_id=entry.doc_id, error=str(exc)[:200])
            return _search_legacy(corpus, query, ledger, top_k)

        for chunk, emb_row in zip(doc_chunks, doc_emb, strict=True):
            all_chunks.append((
                chunk["doc_id"], chunk["start"], chunk["end"],
                chunk["text"], chunk["normalizer_version"],
            ))
            all_embeddings_list.append(emb_row)

    if not all_chunks:
        return []

    # Stack all embeddings into one matrix — already L2-normalised at ingest
    e_norm = np.stack(all_embeddings_list, axis=0).astype(np.float32)  # (n_chunks, dim)

    chunk_ids = [f"{doc_id}:{start}:{end}" for doc_id, start, end, _text, _nv in all_chunks]
    by_chunk_id = {cid: c for cid, c in zip(chunk_ids, all_chunks, strict=True)}

    # Build BM25 from the combined tokenized corpus (reloaded from sidecars)
    # Note: BM25 must cover the full combined corpus for RRF to work correctly
    bm25 = BM25Index([c[3] for c in all_chunks], chunk_ids)
    lexical_ranked = bm25.query(query, top_k=top_k * 2)

    # Embed only the query (D-R5B: corpus already embedded at ingest)
    embedding_started = time.monotonic()
    try:
        q_emb = embed_query(query).reshape(1, -1).astype(np.float32)
    finally:
        ledger.record_embedding_time(time.monotonic() - embedding_started)
    q_norm = q_emb / (np.linalg.norm(q_emb) + 1e-9)

    # D-R5A + Ruling 9: compute cosine for ALL chunk_ids (not just top-K dense)
    all_scores = (e_norm @ q_norm.T).flatten()
    dense_scores = {chunk_ids[i]: float(all_scores[i]) for i in range(len(chunk_ids))}
    dense_order = np.argsort(all_scores)[::-1][: top_k * 2]
    dense_ranked = [chunk_ids[i] for i in dense_order]

    fused = reciprocal_rank_fusion([lexical_ranked, dense_ranked])[:top_k]

    out = []
    for cid, rrf_score in fused:
        doc_id, start, end, text, nv = by_chunk_id[cid]
        cache = corpus.cached_entry(doc_id)
        nt = _nt_from_cache_entry(cache)
        span = mint_span(nt.canonical, start, end, doc_id, nv)
        ledger.record_span(span)
        out.append({
            "doc_id": doc_id, "span_id": span.model_dump(),
            "score": dense_scores.get(cid, 0.0),
            "rrf_score": rrf_score,
            "snippet": f"[{doc_id}:{start}:{end}] {text}",
        })
    return out


def _search_legacy(
    corpus: CorpusIndex, query: str, ledger: RetrievalLedger, top_k: int
) -> list[dict]:
    """Legacy path: build chunks and embed the FULL corpus on every call.

    Used as fallback when persisted index sidecars are absent (first run, legacy corpus,
    or build failure).  Identical to the pre-D-R5B search_corpus logic.
    """
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
    # D-R5A + Ruling 9 (dense score coverage): compute cosine for ALL chunks
    all_scores = (e_norm @ q_norm.T).flatten()
    dense_scores = {chunk_ids[i]: float(all_scores[i]) for i in range(len(chunk_ids))}
    dense_order = np.argsort(all_scores)[::-1][: top_k * 2]
    dense_ranked = [chunk_ids[i] for i in dense_order]

    fused = reciprocal_rank_fusion([lexical_ranked, dense_ranked])[:top_k]

    out = []
    for cid, rrf_score in fused:
        doc_id, start, end, text, nv = by_chunk_id[cid]
        cache = corpus.cached_entry(doc_id)
        nt = _nt_from_cache_entry(cache)
        span = mint_span(nt.canonical, start, end, doc_id, nv)
        ledger.record_span(span)
        out.append({
            "doc_id": doc_id, "span_id": span.model_dump(),
            "score": dense_scores.get(cid, 0.0),
            "rrf_score": rrf_score,
            "snippet": f"[{doc_id}:{start}:{end}] {text}",
        })
    return out


def search_corpus(corpus: CorpusIndex, query: str, ledger: RetrievalLedger, top_k: int = 10) -> list[dict]:
    """Hybrid (BM25 + dense cosine) search over the per-submission corpus.

    D-R5B dispatch: if all parseable docs have persisted index sidecars (built at ingest),
    use the fast _search_with_persisted_index path (only embeds the query).  Otherwise
    fall back to the legacy _search_legacy path (embeds the full corpus per call).

    Result schema per item:
      doc_id    str   — document identifier
      span_id   dict  — SpanID (content-addressed, re-openable via open_span)
      score     float — dense cosine similarity 0–1 (D-R5A; was RRF score — dead branch)
      rrf_score float — RRF rank-fusion score (for ordering / debugging)
      snippet   str   — "[doc_id:start:end] chunk_text"
    """
    if _has_persisted_index(corpus):
        return _search_with_persisted_index(corpus, query, ledger, top_k)
    return _search_legacy(corpus, query, ledger, top_k)
