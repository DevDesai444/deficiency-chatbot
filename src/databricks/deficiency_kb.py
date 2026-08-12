"""Guarded APPEND writers for the flat deficiency_kb (Destination A), local + Databricks.

There was no in-repo writer for the Databricks `deficiency_kb` / `deficiency_embeddings` tables
at all -- those rows were populated by hand. And the local writer, `notebooks/seed_data.py`,
uses `df.to_sql(..., if_exists="replace")`, which would WIPE every existing row. This module is
the append-only replacement for both sides:

  * never REPLACE, always APPEND;
  * refuse to run at all when the observed before-count disagrees with the caller's
    `expect_before` (the idempotency guard for a monotonic append -- a second run aborts
    instead of duplicating);
  * pick the Databricks id strategy from what the table actually DECLARES.

THE ID CONTRACT. `defpredict.main.deficiency_kb.id` is `BIGINT GENERATED ALWAYS AS IDENTITY`,
so a writer cannot choose id values -- Delta rejects any explicit value outright
(DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED) and guarantees only that generated
values are unique and increasing, NOT contiguous and NOT in VALUES order.

We therefore do NOT try to correlate input-list position to assigned id. Instead
`append_databricks` inserts WITHOUT the id column, and `read_back_new_rows` re-reads the rows
the warehouse just created. Embeddings are then built from the columns that came BACK, so
`deficiency_embeddings.record_id` matches its own row's real `id` by construction -- correct
regardless of which ids Delta picked or what order it returns them in, and immune to the
ambiguity that 670 duplicate deficiency texts would otherwise create.

Remote ids are consequently NOT positionally aligned with local SQLite rowid. That alignment is
load-bearing nowhere: `src/databricks/vector.py` joins `deficiency_embeddings.record_id` to
`deficiency_kb.id` entirely within the remote store, and `notebooks/build_index.py` keys the
local FAISS map on local rowid within the local store. The two id spaces never cross.
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
# ...and the id-less form used when `id` is GENERATED ALWAYS AS IDENTITY (the live schema).
_DBX_COLUMNS_NO_ID = (*KB_COLUMNS, "response_date")
# The columns build_index.py's embedding text is composed from, re-read after insert.
_EMBED_SOURCE_COLUMNS = ("product_name", "deficiency_type", "cmc_section", "deficiency_text")

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


def _identity_columns(table: str) -> set[str]:
    """Columns declared GENERATED ALWAYS AS IDENTITY. Delta rejects ANY explicit value for such
    a column (DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED), so a writer cannot choose
    their values -- the warehouse does, and Delta guarantees only that the generated values are
    unique and increasing, NOT that they are contiguous or that they follow VALUES order."""
    rows = _rows_from_result(_run_sql(f"SHOW CREATE TABLE {table}"))
    ddl = "\n".join(str(next(iter(r.values()), "")) for r in rows)
    cols: set[str] = set()
    for line in ddl.splitlines():
        stripped = line.strip().rstrip(",")
        if "GENERATED ALWAYS AS IDENTITY" in stripped.upper():
            cols.add(stripped.split()[0].strip("`"))
    return cols


def append_databricks(rows: list[dict], expect_before: int) -> dict:
    """APPEND rows to defpredict.<schema>.deficiency_kb.

    The write MODE is chosen from what the table declares, not assumed:

      * `id` is GENERATED ALWAYS AS IDENTITY (the live schema) -> insert WITHOUT `id` and let
        the warehouse assign. Callers pair this with `read_back_new_rows`.
      * `id` is a plain column -> assign ids explicitly from MAX(id) + 1 in list order.

    Any OTHER identity column is refused outright: this writer supplies a value for every
    non-id column, and Delta rejects explicit values for identity columns, so the append would
    fail partway with some batches already landed.
    """
    kb = _table("deficiency_kb")
    before, max_id = _kb_counts()
    if before != expect_before:
        raise RuntimeError(
            f"refusing to append: {kb} holds {before} rows but --expect-before said "
            f"{expect_before}. Someone else may have changed shared state."
        )

    # PRE-FLIGHT, before a single row is written -- an identity mismatch discovered mid-append
    # leaves earlier batches already committed, and identity values are never reused.
    identity = _identity_columns(kb)
    non_id_identity = identity - {"id"}
    if non_id_identity:
        raise RuntimeError(
            f"refusing to append: {kb} declares {sorted(non_id_identity)} as GENERATED ALWAYS "
            f"AS IDENTITY, but this writer supplies an explicit value for every non-id column. "
            f"Delta rejects explicit values for identity columns, so the append would fail "
            f"partway with earlier batches already committed."
        )
    identity_id = "id" in identity

    # response_date has no local counterpart. MIRROR whatever the existing rows use (NULL vs '')
    # rather than inventing a third convention.
    probe = _rows_from_result(_run_sql(f"SELECT response_date FROM {kb} ORDER BY id LIMIT 1"))
    response_date = probe[0].get("response_date") if probe else None

    stats: dict = {}
    if identity_id:
        columns = list(_DBX_COLUMNS_NO_ID)
        tuples = [(*(row.get(c, "") for c in KB_COLUMNS), response_date) for row in rows]
        ids: list[int] = []   # assigned by the warehouse; recovered via read_back_new_rows
    else:
        columns = list(_DBX_COLUMNS)
        ids = [max_id + 1 + i for i in range(len(rows))]
        tuples = [
            (_SqlLiteral(row_id), *(row.get(c, "") for c in KB_COLUMNS), response_date)
            for row_id, row in zip(ids, rows, strict=True)
        ]
    _batched_insert(kb, columns, tuples, stats=stats)

    after, after_max_id = _kb_counts()
    if after != before + len(rows):
        raise RuntimeError(
            f"post-append count mismatch on {kb}: expected {before + len(rows)}, found {after}. "
            f"The append is NOT complete -- inspect before re-running (a blind retry would "
            f"duplicate whatever did land)."
        )
    return {
        "write_mode": "identity" if identity_id else "explicit-id",
        "before": before,
        "appended": len(rows),
        "after": after,
        "max_id_before": max_id,
        "max_id_after": after_max_id,
        "ids": ids,
        "statements": stats.get("statements", 0),
        "response_date_convention": response_date,
    }


def read_back_new_rows(max_id_before: int, expect_count: int) -> list[dict]:
    """Re-read the rows the warehouse just created, so embeddings can be built from what
    actually landed rather than from input-list position.

    This is what makes the identity path safe: `record_id` is taken from the same returned row
    as its text, so it matches by construction no matter which ids Delta chose or in what order
    it returns them. Correlating on deficiency_text instead would be ambiguous -- the corpus
    holds many duplicate texts.
    """
    kb = _table("deficiency_kb")
    cols = ", ".join(("id", *_EMBED_SOURCE_COLUMNS))
    # _rows_from_result walks chunk pagination; reading data_array alone silently truncates a
    # result this size (the exact bug documented in databricks/delta.py).
    rows = _rows_from_result(_run_sql(f"SELECT {cols} FROM {kb} WHERE id > {int(max_id_before)}"))
    if len(rows) != expect_count:
        raise RuntimeError(
            f"read-back returned {len(rows)} rows above id {max_id_before}, expected "
            f"{expect_count}. Refusing to embed a partial set -- that would leave "
            f"deficiency_kb rows with no matching deficiency_embeddings record_id."
        )
    return rows


def append_embeddings_databricks(kb_rows: list[dict], expect_before: int) -> dict:
    """Embed each row with notebooks/build_index.py's EXACT text join and write one
    deficiency_embeddings row per kb row, record_id == that row's own kb id.

    `kb_rows` are the READ-BACK rows from `read_back_new_rows` -- each carries its own `id`
    alongside the text columns, so there is no zip-against-input-order to get wrong.
    """
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
        " | ".join(p for p in (row.get(c) or "" for c in _EMBED_SOURCE_COLUMNS) if p)
        for row in kb_rows
    ]
    record_ids = [int(row["id"]) for row in kb_rows]
    embeddings = embed_texts(texts)

    stats: dict = {}
    _batched_insert(
        emb,
        ["record_id", "embedding"],
        [
            (_SqlLiteral(record_id), json.dumps(list(map(float, vec))))
            for record_id, vec in zip(record_ids, embeddings, strict=True)
        ],
        max_stmt_chars=_EMB_MAX_STMT_CHARS,
        stats=stats,
    )

    after = _emb_count()
    # POST-WRITE guard. A batched insert that is interrupted partway (process killed, timeout)
    # leaves a SHORT table, not a failed one -- the earlier statements have already committed.
    # Without this the caller returns 0 and the orphan rows are only found later by the
    # kb-LEFT-JOIN-embeddings check. Observed for real: a run died during its final batches and
    # left ids 5493..5596 unembedded while reporting success.
    if after != before + len(kb_rows):
        raise RuntimeError(
            f"short write on {emb}: expected {before + len(kb_rows)} rows, found {after} "
            f"({before + len(kb_rows) - after} missing). The insert was interrupted partway. "
            f"Re-run backfill_missing_embeddings() -- it is idempotent and writes only the gap."
        )
    return {
        "before": before,
        "appended": len(kb_rows),
        "after": after,
        "assigned_id_min": min(record_ids) if record_ids else None,
        "assigned_id_max": max(record_ids) if record_ids else None,
        "assigned_id_count": len(set(record_ids)),
        "statements": stats.get("statements", 0),
    }


def missing_embedding_ids() -> list[int]:
    """deficiency_kb ids with no matching deficiency_embeddings.record_id."""
    kb, emb = _table("deficiency_kb"), _table("deficiency_embeddings")
    rows = _rows_from_result(_run_sql(
        f"SELECT k.id AS id FROM {kb} k LEFT JOIN {emb} e ON k.id = e.record_id "
        f"WHERE e.record_id IS NULL ORDER BY k.id"
    ))
    return [int(r["id"]) for r in rows]


def backfill_missing_embeddings(batch: int = 500) -> dict:
    """Embed and insert ONLY the kb rows that currently lack an embedding.

    Idempotent and self-correcting: it derives its work from the live orphan set rather than
    from a caller-supplied list, so re-running after a partial write finishes the job and
    re-running after a complete one is a no-op. This is the recovery path for an append that
    was interrupted mid-batch -- the committed rows stay, only the gap is filled.
    """
    from retrieval.vector_search import embed_texts

    kb, emb = _table("deficiency_kb"), _table("deficiency_embeddings")
    before = _emb_count()
    missing = missing_embedding_ids()
    if not missing:
        return {"before": before, "missing": 0, "appended": 0, "after": before}

    cols = ", ".join(("id", *_EMBED_SOURCE_COLUMNS))
    appended = 0
    for start in range(0, len(missing), batch):
        chunk = missing[start : start + batch]
        id_list = ", ".join(str(i) for i in chunk)
        rows = _rows_from_result(_run_sql(f"SELECT {cols} FROM {kb} WHERE id IN ({id_list})"))
        if len(rows) != len(chunk):
            raise RuntimeError(
                f"read-back returned {len(rows)} of {len(chunk)} requested kb rows; refusing "
                f"to embed a partial set."
            )
        texts = [
            " | ".join(p for p in (r.get(c) or "" for c in _EMBED_SOURCE_COLUMNS) if p)
            for r in rows
        ]
        vectors = embed_texts(texts)
        _batched_insert(
            emb,
            ["record_id", "embedding"],
            [
                (_SqlLiteral(int(r["id"])), json.dumps(list(map(float, vec))))
                for r, vec in zip(rows, vectors, strict=True)
            ],
            max_stmt_chars=_EMB_MAX_STMT_CHARS,
        )
        appended += len(rows)

    after = _emb_count()
    return {"before": before, "missing": len(missing), "appended": appended, "after": after}
