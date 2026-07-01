"""
Vector search abstraction — local FAISS fallback or Databricks Vector Search.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from config import get_settings

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
    query_embedding: np.ndarray,
    top_k: int = 10,
) -> list[dict]:
    s = get_settings()
    if s.is_databricks:
        return _search_databricks(query_embedding, top_k)

    return _search_faiss(query_embedding, top_k)


def _search_faiss(query_embedding: np.ndarray, top_k: int) -> list[dict]:
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


def _search_databricks(query_embedding: np.ndarray, top_k: int) -> list[dict]:
    raise NotImplementedError("Databricks Vector Search not yet configured — set ENVIRONMENT=local")
