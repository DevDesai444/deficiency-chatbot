"""Databricks-side rulebook serving (D-RB2) -- the runtime backend behind rulebook.store's
is_databricks dispatch seam. Populated deterministically from the SAME local build every test
uses (D-RB6); this module is imported ONLY behind that dispatch, never at test time.
"""

from __future__ import annotations

import json

import numpy as np

from databricks.delta import (
    _batched_insert,
    _delete_by_keys,
    _escape,
    _rows_from_result,
    _run_sql,
    _table,
)
from rulebook.store import RuleChunk, all_chunks, read_chunk_nt

# Embeddings are ~1024-dim JSON (~20KB each), so their batches flush far sooner than the
# canonical-text batches do; a shared 500k-char budget lands them around 25 rows/statement.
_EMB_MAX_STMT_CHARS = 500_000


def _ensure_rulebook_tables() -> None:
    chunks_table = _table("rulebook_chunks")
    emb_table = _table("rulebook_embeddings")
    _run_sql(
        f"CREATE TABLE IF NOT EXISTS {chunks_table} "
        "(doc_id STRING, citation STRING, source STRING, version STRING, license STRING, "
        "url STRING, span_json STRING, normalizer_version STRING, serializer_version STRING, canonical_text STRING)"
    )
    _run_sql(f"CREATE TABLE IF NOT EXISTS {emb_table} (doc_id STRING, embedding STRING)")


def push_chunks_to_delta(
    sources: tuple[str, ...] | None = None,
    only_missing: bool = False,
) -> dict:
    """Push local rulebook chunks + their embeddings to Delta.

    Idempotent (upsert-by-doc_id via batched delete+insert, matching this codebase's existing
    Databricks write style -- databricks/*.py never uses a MERGE statement, stay consistent).

    This used to issue FOUR SERIAL statements per chunk. At 5,031 chunks that is ~20,000 serial
    Statement Execution API round trips -- many hours. It is now O(batches).

    `sources` filters by chunk.source. This is LOAD-BEARING, not a convenience: the local store
    holds ich=5 while Databricks holds ich=4 (pre-existing drift, explicitly out of scope).
    Without the filter, `only_missing` would helpfully push that stray ich chunk and land
    rulebook_embeddings at 5,032 instead of the intended 5,031.

    `only_missing` skips doc_ids already present remotely -- which also skips RE-EMBEDDING them.

    Returns {"candidates", "skipped_existing", "pushed", "statements"}.
    """
    from retrieval.vector_search import embed_texts

    _ensure_rulebook_tables()
    chunks_table, emb_table = _table("rulebook_chunks"), _table("rulebook_embeddings")

    chunks = all_chunks()
    if sources is not None:
        chunks = [c for c in chunks if c.source in sources]
    report = {"candidates": len(chunks), "skipped_existing": 0, "pushed": 0, "statements": 0}
    if not chunks:
        return report

    if only_missing:
        existing = {
            r["doc_id"] for r in _rows_from_result(_run_sql(f"SELECT doc_id FROM {chunks_table}"))
        }
        report["statements"] += 1
        kept = [c for c in chunks if c.doc_id not in existing]
        report["skipped_existing"] = len(chunks) - len(kept)
        chunks = kept
        if not chunks:
            return report

    texts = [(read_chunk_nt(c.doc_id).canonical if read_chunk_nt(c.doc_id) else "") for c in chunks]
    embeddings = embed_texts(texts)   # ONE bulk call; the Databricks backend batches 16 internally
    doc_ids = [c.doc_id for c in chunks]

    stats: dict = {}
    _delete_by_keys(chunks_table, "doc_id", doc_ids, stats=stats)
    _batched_insert(
        chunks_table,
        ["doc_id", "citation", "source", "version", "license", "url", "span_json",
         "normalizer_version", "serializer_version", "canonical_text"],
        [
            (c.doc_id, c.citation, c.source, c.version, c.license, c.url,
             c.span.model_dump_json(), c.normalizer_version, c.serializer_version, text)
            for c, text in zip(chunks, texts, strict=True)
        ],
        stats=stats,
    )
    _delete_by_keys(emb_table, "doc_id", doc_ids, stats=stats)
    _batched_insert(
        emb_table,
        ["doc_id", "embedding"],
        [(c.doc_id, json.dumps(emb.tolist())) for c, emb in zip(chunks, embeddings, strict=True)],
        max_stmt_chars=_EMB_MAX_STMT_CHARS,
        stats=stats,
    )

    report["pushed"] = len(chunks)
    report["statements"] += stats.get("statements", 0)
    return report


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
