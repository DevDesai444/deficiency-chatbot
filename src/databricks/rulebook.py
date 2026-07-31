"""Databricks-side rulebook serving (D-RB2) -- the runtime backend behind rulebook.store's
is_databricks dispatch seam. Populated deterministically from the SAME local build every test
uses (D-RB6); this module is imported ONLY behind that dispatch, never at test time.
"""

from __future__ import annotations

import json

import numpy as np

from databricks.delta import _escape, _rows_from_result, _run_sql, _table
from rulebook.store import RuleChunk, all_chunks, read_chunk_nt


def _ensure_rulebook_tables() -> None:
    chunks_table = _table("rulebook_chunks")
    emb_table = _table("rulebook_embeddings")
    _run_sql(
        f"CREATE TABLE IF NOT EXISTS {chunks_table} "
        "(doc_id STRING, citation STRING, source STRING, version STRING, license STRING, "
        "url STRING, span_json STRING, normalizer_version STRING, serializer_version STRING, canonical_text STRING)"
    )
    _run_sql(f"CREATE TABLE IF NOT EXISTS {emb_table} (doc_id STRING, embedding STRING)")


def push_chunks_to_delta() -> int:
    """Idempotent (upsert-by-doc_id via delete+insert, matching this codebase's existing
    Databricks write style -- no MERGE INTO used elsewhere in databricks/*.py, stay consistent)."""
    from retrieval.vector_search import embed_texts

    _ensure_rulebook_tables()
    chunks_table, emb_table = _table("rulebook_chunks"), _table("rulebook_embeddings")
    chunks = all_chunks()
    if not chunks:
        return 0

    texts = [(read_chunk_nt(c.doc_id).canonical if read_chunk_nt(c.doc_id) else "") for c in chunks]
    embeddings = embed_texts(texts)

    for chunk, text, emb in zip(chunks, texts, embeddings, strict=True):
        _run_sql(f"DELETE FROM {chunks_table} WHERE doc_id = {_escape(chunk.doc_id)}")
        _run_sql(
            f"INSERT INTO {chunks_table} (doc_id, citation, source, version, license, url, span_json, normalizer_version, serializer_version, canonical_text) "
            f"VALUES ({_escape(chunk.doc_id)}, {_escape(chunk.citation)}, {_escape(chunk.source)}, {_escape(chunk.version)}, "
            f"{_escape(chunk.license)}, {_escape(chunk.url)}, {_escape(chunk.span.model_dump_json())}, "
            f"{_escape(chunk.normalizer_version)}, {_escape(chunk.serializer_version)}, {_escape(text)})"
        )
        _run_sql(f"DELETE FROM {emb_table} WHERE doc_id = {_escape(chunk.doc_id)}")
        _run_sql(
            f"INSERT INTO {emb_table} (doc_id, embedding) VALUES ({_escape(chunk.doc_id)}, {_escape(json.dumps(emb.tolist()))})"
        )
    return len(chunks)


# NOTE (plan-checker Warning 1 / D-RB6 traceability): search_rulebook_databricks has ZERO
# agent-facing tool consumers in Phase 2 -- mirrors the identical, already-documented deferral
# on rulebook.store.rulebook_search (Plan 02-02, local leg of this SAME dispatch seam). It is
# still REQUIRED here: D-RB2 locks the Databricks-side query capability as its own serving-layer
# deliverable, independent of a consumer. Wiring either leg into an agent-facing tool is
# DEFERRED to Phase-3 evidence, mirroring D-RB3's identical precedent-search deferral. Do not
# delete this function for having no caller yet; it is locked-decision infrastructure.
def search_rulebook_databricks(query_text: str, top_k: int) -> list[RuleChunk]:
    from retrieval.vector_search import embed_query as _embed

    query_emb = _embed(query_text)

    emb_table, chunks_table = _table("rulebook_embeddings"), _table("rulebook_chunks")
    emb_data = _run_sql(f"SELECT doc_id, embedding FROM {emb_table}")
    emb_rows = _rows_from_result(emb_data)  # NEVER read data_array alone -- walks chunk pagination
    if not emb_rows:
        return []

    doc_ids = [r["doc_id"] for r in emb_rows]
    embeddings = np.array([json.loads(r["embedding"]) for r in emb_rows], dtype=np.float32)
    q = query_emb.reshape(1, -1).astype(np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-9)
    e_norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    scores = (e_norm @ q_norm.T).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]
    top_ids = [doc_ids[i] for i in top_indices]

    id_list = ", ".join(_escape(i) for i in top_ids)
    chunk_data = _run_sql(f"SELECT * FROM {chunks_table} WHERE doc_id IN ({id_list})")
    chunk_rows = {r["doc_id"]: r for r in _rows_from_result(chunk_data)}

    from schemas.documents import SpanID

    results = []
    for doc_id in top_ids:
        r = chunk_rows.get(doc_id)
        if r is None:
            continue
        results.append(
            RuleChunk(
                doc_id=r["doc_id"],
                citation=r["citation"],
                source=r["source"],
                version=r["version"],
                license=r["license"],
                url=r["url"],
                span=SpanID.model_validate_json(r["span_json"]),
                normalizer_version=r["normalizer_version"],
                serializer_version=r["serializer_version"],
            )
        )
    return results
