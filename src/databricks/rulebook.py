"""Databricks-side rulebook serving (D-RB2) -- the runtime backend behind rulebook.store's
is_databricks dispatch seam. Populated deterministically from the SAME local build every test
uses (D-RB6); this module is imported ONLY behind that dispatch, never at test time.
"""

from __future__ import annotations

import json

from databricks.delta import _escape, _run_sql, _table
from rulebook.store import all_chunks, read_chunk_nt


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
