"""
Vector search abstraction — local FAISS fallback or Databricks SQL text search.

When a Databricks Vector Search endpoint is configured, uses that.
Otherwise falls back to SQL LIKE matching against deficiency_kb columns.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from config import get_settings
from databricks.delta import _escape, _rows_from_result, _run_sql, _table

_DB_PATH = "data/defpredict.db"
_FAISS_INDEX_PATH = "data/deficiency_kb.faiss"
_FAISS_MAP_PATH = "data/deficiency_kb_map.json"

_faiss_index = None
_faiss_id_map: list[int] = []


def _ensure_faiss():
    global _faiss_index, _faiss_id_map
    if _faiss_index is not None:
        return

    import faiss

    idx_path = Path(_FAISS_INDEX_PATH)
    map_path = Path(_FAISS_MAP_PATH)

    if idx_path.exists() and map_path.exists():
        _faiss_index = faiss.read_index(str(idx_path))
        _faiss_id_map = json.loads(map_path.read_text())
    else:
        _faiss_index = None
        _faiss_id_map = []


def build_local_index(embeddings: np.ndarray, row_ids: list[int]) -> None:
    """Build FAISS index from embeddings and save to disk."""
    import faiss

    global _faiss_index, _faiss_id_map

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)

    Path(_FAISS_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, _FAISS_INDEX_PATH)
    Path(_FAISS_MAP_PATH).write_text(json.dumps(row_ids))

    _faiss_index = index
    _faiss_id_map = row_ids


def search_similar(
    query_embedding: np.ndarray | None = None,
    query_text: str = "",
    top_k: int = 10,
) -> list[dict]:
    s = get_settings()
    if s.is_databricks:
        return _search_databricks(query_text, top_k)
    return _search_faiss(query_embedding, top_k)


def _search_faiss(query_embedding: np.ndarray | None, top_k: int) -> list[dict]:
    if query_embedding is None:
        return []

    _ensure_faiss()
    if _faiss_index is None or _faiss_index.ntotal == 0:
        return []

    import faiss

    query = query_embedding.reshape(1, -1).astype(np.float32)
    faiss.normalize_L2(query)
    scores, indices = _faiss_index.search(query, top_k)

    results = []
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row

    for score, idx in zip(scores[0], indices[0], strict=True):
        if idx < 0 or idx >= len(_faiss_id_map):
            continue
        row_id = _faiss_id_map[idx]
        row = conn.execute(
            "SELECT * FROM deficiency_kb WHERE rowid = ?", (row_id,)
        ).fetchone()
        if row:
            result = dict(row)
            result["similarity_score"] = float(score)
            results.append(result)

    conn.close()
    return results


def _search_databricks(query_text: str, top_k: int) -> list[dict]:
    """SQL-based text search against Databricks Delta table.

    Searches deficiency_text and deficiency_response columns for keyword overlap.
    When a Vector Search endpoint is configured, this would use the VS API instead.
    """
    s = get_settings()
    if s.vector_search_endpoint:
        return _search_vector_endpoint(query_text, top_k)

    table = _table("deficiency_kb")
    keywords = [w.strip() for w in query_text.split() if len(w.strip()) > 3]

    if not keywords:
        stmt = f"SELECT * FROM {table} LIMIT {top_k}"
    else:
        conditions = []
        for kw in keywords[:5]:
            escaped = _escape(f"%{kw}%")
            conditions.append(
                f"(LOWER(deficiency_text) LIKE LOWER({escaped}) "
                f"OR LOWER(category) LIKE LOWER({escaped}) "
                f"OR LOWER(cmc_section) LIKE LOWER({escaped}))"
            )
        where = " OR ".join(conditions)
        stmt = f"SELECT * FROM {table} WHERE {where} LIMIT {top_k}"

    data = _run_sql(stmt)
    rows = _rows_from_result(data)
    for r in rows:
        r["similarity_score"] = 1.0
    return rows


def _search_vector_endpoint(query_text: str, top_k: int) -> list[dict]:
    """Query a Databricks Vector Search endpoint."""
    import httpx

    s = get_settings()
    index_name = f"{s.databricks_catalog}.{s.databricks_schema}.{s.vector_search_index}"

    with httpx.Client(
        base_url=s.databricks_host,
        headers={"Authorization": f"Bearer {s.databricks_token}"},
        timeout=30.0,
    ) as client:
        resp = client.post(
            f"/api/2.0/vector-search/indexes/{index_name}/query",
            json={
                "query_text": query_text,
                "columns": [
                    "anda_number", "product_name", "dosage_form",
                    "cmc_section", "deficiency_type", "category",
                    "deficiency_text", "deficiency_response",
                ],
                "num_results": top_k,
            },
        )

    data = resp.json()
    if "result" not in data:
        return []

    columns = data["manifest"]["columns"]
    col_names = [c["name"] for c in columns]
    results = []
    for row in data["result"].get("data_array", []):
        rec = dict(zip(col_names, row, strict=False))
        rec["similarity_score"] = rec.pop("score", 1.0)
        results.append(rec)
    return results
