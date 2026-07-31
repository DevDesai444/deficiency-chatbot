"""Local rulebook chunk store (D-RB6 offline backend) -- atomic persistence + citation lookup
+ hybrid local search, mirroring ingest/store.py's SQLite/atomic-write conventions exactly.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from schemas.documents import NormalizedText, OffsetRun, SpanID

DEFAULT_RULEBOOK_CACHE_DIR = "data/rulebook_cache"
_DB_PATH = "data/defpredict.db"  # SAME db file as ingest/store.py + databricks/vector.py -- new tables


class RuleChunk(BaseModel):
    doc_id: str
    citation: str
    source: str  # "ecfr" | "ich" | "fda"
    version: str  # edition/guideline date
    license: str
    url: str
    span: SpanID  # the WHOLE-chunk span over its own canonical text
    normalizer_version: str
    serializer_version: str


def _cache_path(cache_dir: str, doc_id: str) -> Path:
    safe = doc_id.replace("/", "_")
    return Path(cache_dir) / f"{safe}.json"


def write_chunk(
    chunk: RuleChunk,
    nt: NormalizedText,
    cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
    db_path: str = _DB_PATH,
) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    final = _cache_path(cache_dir, chunk.doc_id)
    tmp = final.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {
                "chunk": chunk.model_dump(),
                "canonical": nt.canonical,
                "raw_serialized": nt.raw_serialized,
                "offset_map": [r.model_dump() for r in nt.offset_map],
                "normalizer_version": nt.normalizer_version,
                "serializer_version": nt.serializer_version,
            }
        ),
        encoding="utf-8",
    )
    os.replace(tmp, final)  # atomic rename: a crash before this leaves only .tmp, never a half .json
    _upsert_chunk_row(chunk, db_path)


def read_chunk_nt(doc_id: str, cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR) -> NormalizedText | None:
    final = _cache_path(cache_dir, doc_id)
    if not final.exists():
        return None
    entry = json.loads(final.read_text(encoding="utf-8"))
    return NormalizedText(
        canonical=entry["canonical"],
        raw_serialized=entry["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in entry["offset_map"]],
        normalizer_version=entry["normalizer_version"],
        serializer_version=entry["serializer_version"],
    )


def rulebook_nt_for(doc_id: str, cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR) -> NormalizedText | None:
    """Alias RESEARCH.md's requirement-index loader-gate Code Example calls by this name."""
    return read_chunk_nt(doc_id, cache_dir)


def _get_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_chunks_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS rulebook_chunks "
        "(doc_id TEXT PRIMARY KEY, citation TEXT, source TEXT, version TEXT, "
        "license TEXT, url TEXT, span_json TEXT, normalizer_version TEXT, serializer_version TEXT)"
    )


def _upsert_chunk_row(chunk: RuleChunk, db_path: str) -> None:
    conn = _get_conn(db_path)
    _ensure_chunks_table(conn)
    conn.execute(
        "INSERT INTO rulebook_chunks (doc_id, citation, source, version, license, url, span_json, "
        "normalizer_version, serializer_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(doc_id) DO UPDATE SET citation=excluded.citation, source=excluded.source, "
        "version=excluded.version, license=excluded.license, url=excluded.url, span_json=excluded.span_json, "
        "normalizer_version=excluded.normalizer_version, serializer_version=excluded.serializer_version",
        (
            chunk.doc_id,
            chunk.citation,
            chunk.source,
            chunk.version,
            chunk.license,
            chunk.url,
            chunk.span.model_dump_json(),
            chunk.normalizer_version,
            chunk.serializer_version,
        ),
    )
    conn.commit()
    conn.close()


def _row_to_chunk(row: sqlite3.Row) -> RuleChunk:
    return RuleChunk(
        doc_id=row["doc_id"],
        citation=row["citation"],
        source=row["source"],
        version=row["version"],
        license=row["license"],
        url=row["url"],
        span=SpanID.model_validate_json(row["span_json"]),
        normalizer_version=row["normalizer_version"],
        serializer_version=row["serializer_version"],
    )


def lookup_citation(citation: str, db_path: str = _DB_PATH) -> RuleChunk | None:
    conn = _get_conn(db_path)
    _ensure_chunks_table(conn)
    row = conn.execute("SELECT * FROM rulebook_chunks WHERE citation = ?", (citation,)).fetchone()
    conn.close()
    return _row_to_chunk(row) if row else None


def all_chunks(db_path: str = _DB_PATH) -> list[RuleChunk]:
    conn = _get_conn(db_path)
    _ensure_chunks_table(conn)
    rows = conn.execute("SELECT * FROM rulebook_chunks").fetchall()
    conn.close()
    return [_row_to_chunk(r) for r in rows]


# --- local FAISS+BM25 hybrid search + the is_databricks dispatch seam (Task 2) ---------------

_RULEBOOK_FAISS_PATH = "data/rulebook.faiss"
_RULEBOOK_FAISS_MAP_PATH = "data/rulebook_map.json"
_faiss_index = None
_faiss_doc_ids: list[str] = []


def _ensure_faiss():
    global _faiss_index, _faiss_doc_ids
    if _faiss_index is not None:
        return
    import faiss

    idx_path, map_path = Path(_RULEBOOK_FAISS_PATH), Path(_RULEBOOK_FAISS_MAP_PATH)
    if idx_path.exists() and map_path.exists():
        _faiss_index = faiss.read_index(str(idx_path))
        _faiss_doc_ids = json.loads(map_path.read_text())
    else:
        _faiss_index, _faiss_doc_ids = None, []


def rebuild_local_index() -> None:
    """Re-embed every persisted chunk's canonical text and rebuild the FAISS index (called by
    the build script after vendoring, Plan 02-03; safe to re-run -- fully deterministic from
    the persisted chunk store)."""
    import faiss
    import numpy as np

    from retrieval.vector_search import embed_texts

    global _faiss_index, _faiss_doc_ids
    chunks = all_chunks()
    if not chunks:
        _faiss_index, _faiss_doc_ids = None, []
        return
    texts = [(read_chunk_nt(c.doc_id).canonical if read_chunk_nt(c.doc_id) else "") for c in chunks]
    # One encode() call PER chunk, not one bulk call over the whole list: rulebook chunks vary
    # wildly in length (a whole-section span can run tens of thousands of chars, e.g. some eCFR
    # sections). A single bulk `embed_texts(texts, batch_size=1)` call still segfaults in the CPU
    # sentence-transformers backend -- encode() pre-processes/sorts the FULL input list before
    # its internal batch loop runs, so the crash is tied to list SIZE, not batch padding.
    # Embedding one chunk at a time (a fresh, single-item encode() call per chunk) is proven
    # stable up to the largest observed chunk (~46k chars) and is the safe path here. This is a
    # one-time build script (D-RB2) -- the throughput cost of no bulk-call optimization is an
    # acceptable trade for reliability.
    embeddings = np.stack([embed_texts([text], batch_size=1)[0] for text in texts])
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    Path(_RULEBOOK_FAISS_PATH).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, _RULEBOOK_FAISS_PATH)
    Path(_RULEBOOK_FAISS_MAP_PATH).write_text(json.dumps([c.doc_id for c in chunks]))
    _faiss_index, _faiss_doc_ids = index, [c.doc_id for c in chunks]


def _rulebook_search_local(query: str, top_k: int) -> list[RuleChunk]:
    chunks = {c.doc_id: c for c in all_chunks()}
    if not chunks:
        return []
    # lexical leg: substring hit count over each chunk's citation + canonical text
    q_lower = query.lower()
    lexical_ranked = sorted(
        chunks.values(),
        key=lambda c: -(
            (read_chunk_nt(c.doc_id).canonical.lower().count(q_lower) if read_chunk_nt(c.doc_id) else 0)
            + (2 if q_lower in c.citation.lower() else 0)
        ),
    )
    lexical_ids = [c.doc_id for c in lexical_ranked if c.doc_id in chunks][: top_k * 2]
    # dense leg
    dense_ids: list[str] = []
    _ensure_faiss()
    if _faiss_index is not None and _faiss_index.ntotal > 0:
        import faiss

        from retrieval.vector_search import embed_query

        q = embed_query(query).reshape(1, -1).astype("float32")
        faiss.normalize_L2(q)
        _, indices = _faiss_index.search(q, min(top_k * 2, _faiss_index.ntotal))
        dense_ids = [_faiss_doc_ids[i] for i in indices[0] if 0 <= i < len(_faiss_doc_ids)]
    try:
        from retrieval.hybrid import reciprocal_rank_fusion

        fused = reciprocal_rank_fusion([lexical_ids, dense_ids]) if dense_ids else [(i, 0.0) for i in lexical_ids]
    except ImportError:
        # retrieval.hybrid lands in Plan 02-04 (Wave 2, after this plan) -- fall back to
        # pure-lexical ranking so THIS plan's own tests (which run before Plan 02-04 exists)
        # stay green; once Plan 02-04 lands, the dense leg is folded in automatically.
        fused = [(i, 0.0) for i in lexical_ids]
    return [chunks[doc_id] for doc_id, _score in fused[:top_k] if doc_id in chunks]


def _rulebook_search_databricks(query: str, top_k: int) -> list[RuleChunk]:
    """Databricks-side rulebook query -- implemented in Plan 02-08 (src/databricks/rulebook.py).
    Deliberately a lazy import so this module loads fine before Plan 02-08 lands; calling this
    branch before then is a clear ModuleNotFoundError, never a silent fallback to local (which
    would defeat is_databricks's purpose and mask an incomplete backend)."""
    from databricks.rulebook import search_rulebook_databricks

    return search_rulebook_databricks(query, top_k)


# NOTE (plan-checker Warning 1 / D-RB6 traceability): rulebook_search has ZERO agent-facing
# tool consumers in Phase 2 -- read_guideline's enumerate mode (D-RI2) is index-only (curated,
# eval-scoped triggers per D-RB4/D-RI1) and its fetch mode requires an EXACT citation string, so
# this hybrid search is not yet reachable from the agent loop. It is still REQUIRED here: D-RB6
# locks "the deterministic build from the vendored snapshot is also queryable locally" as its
# OWN deliverable, independent of a consumer. Wiring it into an agent-facing tool (e.g. a
# citation-discovery fallback on read_guideline, or a dedicated rule-search tool) is DEFERRED to
# Phase-3 evidence -- the SAME deferral discipline D-RB3 already applies to precedent-search
# ("exposing precedent-search as a 6th tool... Deferred, not dropped"). Do not delete this
# function for having no caller yet; it is locked-decision infrastructure, not dead code.
def rulebook_search(query: str, top_k: int = 10) -> list[RuleChunk]:
    from config import get_settings

    s = get_settings()
    if s.is_databricks:
        return _rulebook_search_databricks(query, top_k)
    return _rulebook_search_local(query, top_k)
