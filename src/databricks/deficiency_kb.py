"""Guarded APPEND writers for the flat deficiency_kb (Destination A), local + Databricks.

There was no in-repo writer for the Databricks `deficiency_kb` / `deficiency_embeddings` tables
at all -- those rows were populated by hand. And the local writer, `notebooks/seed_data.py`,
uses `df.to_sql(..., if_exists="replace")`, which would WIPE every existing row. This module is
the append-only replacement for both sides:

  * never REPLACE, always APPEND;
  * refuse to run at all when the observed before-count disagrees with the caller's
    `expect_before` (the idempotency guard for a monotonic append -- a second run aborts
    instead of duplicating);
  * assign Databricks ids monotonically from MAX(id) + 1, in the caller's list order.

THE ID CONTRACT. SQLite rowid N and Databricks `deficiency_kb.id` N must describe the SAME
record: `notebooks/build_index.py` keys the local FAISS map on rowid, and
`src/databricks/vector.py` joins the remote embeddings on `id`. Both sides are therefore
written in WORKBOOK ORDER from the same `load_kb_rows` list.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from databricks.delta import (
    _MAX_STMT_CHARS,
    _batched_insert,
    _rows_from_result,
    _run_sql,
    _SqlLiteral,
    _table,
)

_DB_PATH = "data/defpredict.db"

# The 9 canonical fields, in the order notebooks/seed_data.py's normalization produced them.
KB_COLUMNS = (
    "anda_number", "product_name", "dosage_form", "cmc_section", "deficiency_type",
    "cohort_year", "category", "deficiency_text", "deficiency_response",
)
# The Databricks table additionally carries id + response_date.
_DBX_COLUMNS = ("id", *KB_COLUMNS, "response_date")

# ~1024-dim float JSON is ~20KB per row, so a 500k budget lands ~25 rows per statement.
_EMB_MAX_STMT_CHARS = _MAX_STMT_CHARS


def load_kb_rows(xlsm_path: str | Path) -> list[dict]:
    """Flat-KB rows in WORKBOOK ORDER.

    REUSES rulebook.precedents._read_rows so the two destinations share ONE header mapping --
    the normalized-header fix protects this path too (the old literal header map would have
    silently NULLed cohort_year and category for an entire workbook on this side as well).

    Three deliberate differences from the precedent (Destination B) path:
      * NO forward-fill. seed_data.py did not forward-fill, so the existing rows carry raw
        blanks; this destination stays raw-as-read. The D-PREC forward-fill is Destination B's.
      * Values normalized exactly as seed_data did: `str(v).strip() if v is not None else ""`
        (openpyxl hands back anda_number as an int).
      * _read_rows' bookkeeping `row_ordinal` key is dropped -- exactly the 9 canonical fields.

    _read_rows skips rows with an empty deficiency cell, which is precisely seed_data's
    effective selection rule.
    """
    from rulebook.precedents import _read_rows

    rows = _read_rows(xlsm_path)
    return [
        {col: (str(row[col]).strip() if row.get(col) is not None else "") for col in KB_COLUMNS}
        for row in rows
    ]


def append_local(rows: list[dict], expect_before: int, db_path: str = _DB_PATH) -> dict:
    """APPEND rows to the local deficiency_kb, preserving list order so rowids stay positionally
    aligned with the Databricks ids (see THE ID CONTRACT above). Never `to_sql(replace)`."""
    conn = sqlite3.connect(db_path)
    try:
        # Insert BY COLUMN NAME, never by position: the table was created by pandas to_sql, so
        # its column order is the spreadsheet's, not this module's.
        table_cols = [r[1] for r in conn.execute("PRAGMA table_info(deficiency_kb)")]
        if not table_cols:
            raise RuntimeError(f"{db_path}: deficiency_kb does not exist")

        before = conn.execute("SELECT COUNT(*) FROM deficiency_kb").fetchone()[0]
        if before != expect_before:
            raise RuntimeError(
                f"refusing to append: deficiency_kb holds {before} rows but --expect-before "
                f"said {expect_before}. Either this append already ran, or someone else "
                f"changed the table."
            )
        max_rowid_before = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM deficiency_kb").fetchone()[0]

        col_list = ", ".join(f'"{c}"' for c in table_cols)
        placeholders = ", ".join("?" * len(table_cols))
        with conn:
            conn.executemany(
                f"INSERT INTO deficiency_kb ({col_list}) VALUES ({placeholders})",
                [tuple(row.get(c, "") for c in table_cols) for row in rows],
            )

        after = conn.execute("SELECT COUNT(*) FROM deficiency_kb").fetchone()[0]
        max_rowid = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM deficiency_kb").fetchone()[0]
    finally:
        conn.close()

    return {
        "before": before,
        "appended": len(rows),
        "after": after,
        "first_new_rowid": max_rowid_before + 1,
        "max_rowid": max_rowid,
    }


def _kb_counts() -> tuple[int, int]:
    kb = _table("deficiency_kb")
    res = _rows_from_result(_run_sql(f"SELECT COUNT(*) AS n, MAX(id) AS max_id FROM {kb}"))
    row = res[0] if res else {"n": 0, "max_id": 0}
    return int(row.get("n") or 0), int(row.get("max_id") or 0)


def _emb_count() -> int:
    emb = _table("deficiency_embeddings")
    res = _rows_from_result(_run_sql(f"SELECT COUNT(*) AS n FROM {emb}"))
    return int(res[0].get("n") or 0) if res else 0


def remote_counts() -> dict:
    """Read-only pre-flight helper -- no writes."""
    count, max_id = _kb_counts()
    return {"deficiency_kb": count, "max_id": max_id, "deficiency_embeddings": _emb_count()}


def append_databricks(rows: list[dict], expect_before: int) -> dict:
    """APPEND rows to defpredict.<schema>.deficiency_kb with ids assigned from MAX(id) + 1 in
    LIST ORDER, so id N lines up with local rowid N."""
    kb = _table("deficiency_kb")
    before, max_id = _kb_counts()
    if before != expect_before:
        raise RuntimeError(
            f"refusing to append: {kb} holds {before} rows but --expect-before said "
            f"{expect_before}. Someone else may have changed shared state."
        )

    # response_date has no local counterpart. MIRROR whatever the existing rows use (NULL vs '')
    # rather than inventing a third convention.
    probe = _rows_from_result(_run_sql(f"SELECT response_date FROM {kb} WHERE id = 1"))
    response_date = probe[0].get("response_date") if probe else None

    ids = [max_id + 1 + i for i in range(len(rows))]
    stats: dict = {}
    _batched_insert(
        kb,
        list(_DBX_COLUMNS),
        [
            (_SqlLiteral(row_id), *(row.get(c, "") for c in KB_COLUMNS), response_date)
            for row_id, row in zip(ids, rows, strict=True)
        ],
        stats=stats,
    )

    after, _ = _kb_counts()
    return {
        "before": before,
        "appended": len(rows),
        "after": after,
        "ids": ids,
        "first_id": ids[0] if ids else None,
        "last_id": ids[-1] if ids else None,
        "statements": stats.get("statements", 0),
        "response_date_convention": response_date,
    }


def append_embeddings_databricks(rows: list[dict], ids: list[int], expect_before: int) -> dict:
    """Embed each row with notebooks/build_index.py's EXACT text join and write one
    deficiency_embeddings row per kb row, record_id == the matching kb id."""
    from retrieval.vector_search import embed_texts

    emb = _table("deficiency_embeddings")
    before = _emb_count()
    if before != expect_before:
        raise RuntimeError(
            f"refusing to append: {emb} holds {before} rows but --expect-before said "
            f"{expect_before}. Someone else may have changed shared state."
        )

    # build_index.py's exact join -- if this drifts, the local and remote indices describe
    # different vectors for the same record.
    texts = [
        " | ".join(
            p for p in [
                row.get("product_name", ""), row.get("deficiency_type", ""),
                row.get("cmc_section", ""), row.get("deficiency_text", ""),
            ] if p
        )
        for row in rows
    ]
    embeddings = embed_texts(texts)

    stats: dict = {}
    _batched_insert(
        emb,
        ["record_id", "embedding"],
        [
            (_SqlLiteral(record_id), json.dumps(list(map(float, vec))))
            for record_id, vec in zip(ids, embeddings, strict=True)
        ],
        max_stmt_chars=_EMB_MAX_STMT_CHARS,
        stats=stats,
    )

    after = _emb_count()
    return {
        "before": before,
        "appended": len(rows),
        "after": after,
        "statements": stats.get("statements", 0),
    }
