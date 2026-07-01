"""
Build FAISS vector index from the seeded SQLite deficiency_kb table.

Usage:
    PYTHONPATH=src uv run python notebooks/build_index.py
"""
from __future__ import annotations

import sqlite3

import numpy as np

from databricks.vector import build_local_index
from retrieval.vector_search import embed_texts

DB_PATH = "data/defpredict.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT rowid, * FROM deficiency_kb").fetchall()
    conn.close()

    if not rows:
        print("No records in deficiency_kb — run seed_data.py first.")
        return

    texts = []
    row_ids = []
    for r in rows:
        d = dict(r)
        parts = [
            d.get("product_name", ""),
            d.get("deficiency_type", ""),
            d.get("cmc_section", ""),
            d.get("deficiency_text", ""),
        ]
        text = " | ".join(p for p in parts if p)
        texts.append(text)
        row_ids.append(d["rowid"])

    print(f"Embedding {len(texts)} records...")
    embeddings = embed_texts(texts)
    embeddings = np.array(embeddings, dtype=np.float32)

    print(f"Building FAISS index (dim={embeddings.shape[1]})...")
    build_local_index(embeddings, row_ids)
    print("Done. Index saved to data/deficiency_kb.faiss")


if __name__ == "__main__":
    main()
