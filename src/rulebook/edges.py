"""Generic edge table (D-RB3): (src_id, dst_id, edge_type, provenance_span_id).

Not bespoke per-relation tables -- multi-hop / new relation types add ON this same table with
zero migration. Every edge carries a provenance span-ID (the span that JUSTIFIES it) -- no
unexplained edges (enforced: add_edge rejects an empty provenance_span_id).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

_DB_PATH = "data/defpredict.db"  # SAME db file as store.py / ingest/store.py


def _get_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS edges "
        "(src_id TEXT, dst_id TEXT, edge_type TEXT, provenance_span_id TEXT, "
        "PRIMARY KEY (src_id, dst_id, edge_type))"
    )


def add_edge(
    src_id: str, dst_id: str, edge_type: str, provenance_span_id: str, db_path: str = _DB_PATH
) -> None:
    if not provenance_span_id:
        raise ValueError(
            f"edge {src_id!r}->{dst_id!r} ({edge_type!r}) has no provenance_span_id -- "
            "D-RB3 forbids unexplained edges"
        )
    conn = _get_conn(db_path)
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO edges (src_id, dst_id, edge_type, provenance_span_id) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(src_id, dst_id, edge_type) DO UPDATE SET provenance_span_id=excluded.provenance_span_id",
        (src_id, dst_id, edge_type, provenance_span_id),
    )
    conn.commit()
    conn.close()


def get_edges(
    src_id: str | None = None,
    dst_id: str | None = None,
    edge_type: str | None = None,
    db_path: str = _DB_PATH,
) -> list[tuple[str, str, str, str]]:
    conn = _get_conn(db_path)
    _ensure_table(conn)
    clauses, params = [], []
    if src_id is not None:
        clauses.append("src_id = ?")
        params.append(src_id)
    if dst_id is not None:
        clauses.append("dst_id = ?")
        params.append(dst_id)
    if edge_type is not None:
        clauses.append("edge_type = ?")
        params.append(edge_type)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT src_id, dst_id, edge_type, provenance_span_id FROM edges{where}", params).fetchall()
    conn.close()
    return [(r["src_id"], r["dst_id"], r["edge_type"], r["provenance_span_id"]) for r in rows]
