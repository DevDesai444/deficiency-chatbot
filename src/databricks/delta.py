"""
Data store abstraction — SQLite locally, Databricks Delta in production.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from config import get_settings

log = structlog.get_logger()

_DB_PATH = "data/defpredict.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Databricks SQL Statement Execution API helpers
# ---------------------------------------------------------------------------

def _sql_client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(
        base_url=s.databricks_host,
        headers={"Authorization": f"Bearer {s.databricks_token}"},
        timeout=50.0,
    )


_INLINE_LIMIT_MARKER = "Inline byte limit exceeded"


def _post_statement(statement: str, disposition: str) -> dict:
    s = get_settings()
    with _sql_client() as client:
        resp = client.post(
            "/api/2.0/sql/statements",
            json={
                "warehouse_id": s.databricks_warehouse_id,
                "statement": statement,
                "wait_timeout": "50s",
                "disposition": disposition,
                "format": "JSON_ARRAY",
            },
        )
    return resp.json()


def _run_sql(statement: str) -> dict:
    """Execute a statement, transparently escalating to EXTERNAL_LINKS when the result is
    too large to inline.

    The API caps disposition=INLINE results at 25 MiB. A full embeddings scan blows past that
    once the corpus grows: ~5.6k rows x ~20 KB of JSON per 1024-dim vector is ~110 MB. The
    tables were ~10 MB when this code was written, so the ceiling was invisible until the KB
    grew. Rather than make every caller choose a disposition, try INLINE (cheap, one round
    trip, correct for the many small statements this codebase issues) and fall back to
    EXTERNAL_LINKS only on the specific inline-limit error.
    """
    data = _post_statement(statement, "INLINE")
    state = data.get("status", {}).get("state", "")
    if state != "SUCCEEDED":
        err = data.get("status", {}).get("error", {}).get("message", "unknown error")
        if _INLINE_LIMIT_MARKER in err:
            log.info("databricks_sql_external_links_retry", statement=statement[:120])
            data = _post_statement(statement, "EXTERNAL_LINKS")
            state = data.get("status", {}).get("state", "")
            if state == "SUCCEEDED":
                return data
            err = data.get("status", {}).get("error", {}).get("message", "unknown error")
        log.error("databricks_sql_failed", statement=statement[:200], error=err)
        raise RuntimeError(f"Databricks SQL error: {err}")
    return data


def _table(name: str) -> str:
    s = get_settings()
    return f"{s.databricks_catalog}.{s.databricks_schema}.{name}"


def _escape(val: Any) -> str:
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''").replace("\\", "\\\\")
    return f"'{s}'"


class _SqlLiteral:
    """A value rendered WITHOUT quoting -- the one legitimate exception to _escape.

    Needed because deficiency_kb.id / deficiency_embeddings.record_id are BIGINT: under Spark's
    default ANSI store-assignment policy a quoted '501' is not implicitly cast to 501. The
    constructor coerces through int(), so the ONLY thing that can ever reach a statement
    unquoted is a genuine integer -- there is no path here for arbitrary text (T-JBZ-01).
    """

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = int(value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"_SqlLiteral({self.value})"


def _render(val: Any) -> str:
    """Every value goes through _escape -- except a pre-validated integer _SqlLiteral."""
    return str(val) if isinstance(val, _SqlLiteral) else _escape(val)


# ---------------------------------------------------------------------------
# Byte-budgeted batched write primitives (shared by both Delta writers)
# ---------------------------------------------------------------------------

_MAX_STMT_CHARS = 500_000   # Statement Execution API payload headroom; batches flush on BYTE
                            # budget, not row count, because canonical texts range from ~500
                            # chars (a precedent deficiency) to ~46k (an eCFR section) and
                            # embeddings are ~20KB of JSON each.


def _flush_batches(
    rendered: list[str], prefix_len: int, sep_len: int, max_stmt_chars: int,
) -> list[list[str]]:
    """Split already-rendered value fragments into the FEWEST batches that each stay under the
    budget. A single fragment that alone exceeds the budget still gets its own batch -- an
    oversized eCFR canonical text must remain writable, never silently dropped."""
    batches: list[list[str]] = []
    current: list[str] = []
    current_len = prefix_len
    for frag in rendered:
        addition = len(frag) + (sep_len if current else 0)
        if current and current_len + addition > max_stmt_chars:
            batches.append(current)
            current, current_len = [], prefix_len
            addition = len(frag)
        current.append(frag)
        current_len += addition
    if current:
        batches.append(current)
    return batches


def _batched_insert(
    table: str,
    columns: list[str],
    value_tuples: list[tuple],
    max_stmt_chars: int = _MAX_STMT_CHARS,
    stats: dict | None = None,
) -> int:
    """Multi-row INSERT, flushed whenever the rendered statement would exceed the budget.

    Every value goes through _escape -- no exceptions, no f-string shortcuts -- except an
    explicitly int-coerced _SqlLiteral (see above). Returns rows written; when `stats` is
    supplied, accumulates the number of statements issued under key "statements"."""
    if not value_tuples:
        return 0
    prefix = f"INSERT INTO {table} ({', '.join(columns)}) VALUES "
    rendered = ["(" + ", ".join(_render(v) for v in row) + ")" for row in value_tuples]
    batches = _flush_batches(rendered, len(prefix), len(", "), max_stmt_chars)
    for batch in batches:
        _run_sql(prefix + ", ".join(batch))
    if stats is not None:
        stats["statements"] = stats.get("statements", 0) + len(batches)
    return len(value_tuples)


def _delete_by_keys(
    table: str,
    key_col: str,
    keys: list[str],
    max_stmt_chars: int = _MAX_STMT_CHARS,
    stats: dict | None = None,
) -> int:
    """DELETE ... WHERE key_col IN (...), same byte-budgeted batching. Paired with
    _batched_insert this gives upsert-by-key idempotency without a MERGE statement (which this
    codebase does not use anywhere in databricks/*.py -- stay consistent)."""
    if not keys:
        return 0
    prefix = f"DELETE FROM {table} WHERE {key_col} IN ("
    rendered = [_render(k) for k in keys]
    batches = _flush_batches(rendered, len(prefix) + 1, len(", "), max_stmt_chars)
    for batch in batches:
        _run_sql(prefix + ", ".join(batch) + ")")
    if stats is not None:
        stats["statements"] = stats.get("statements", 0) + len(batches)
    return len(keys)


def _fetch_chunk(link: str) -> dict:
    """Fetch one result chunk by its internal link (Databricks SQL Statement API)."""
    with _sql_client() as client:
        resp = client.get(link)
        resp.raise_for_status()
        return resp.json()


def _fetch_external_link(url: str) -> list:
    """Download one EXTERNAL_LINKS result chunk.

    Deliberately a BARE client, not _sql_client(): these URLs are pre-signed, and sending an
    Authorization header alongside the signature makes the storage backend reject the request.
    """
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json() or []


def _rows_from_result(data: dict) -> list[dict]:
    """Flatten a Databricks SQL result into row dicts, following chunk pagination.

    A large result is split across chunks: the initial response carries only the first
    chunk's ``data_array`` plus a ``next_chunk_internal_link``. Reading ``data_array``
    alone silently truncates the result (e.g. 261 of 500 rows on the embeddings table),
    so we walk the chunk links to completion.

    A result too large to inline at all comes back as ``external_links`` instead (see
    ``_run_sql``'s EXTERNAL_LINKS escalation). Those are PRE-SIGNED URLs: they must be
    fetched WITHOUT the Authorization header, because the storage backend rejects a request
    carrying both a presigned signature and a bearer token. Each link yields the same
    JSON_ARRAY shape as an inline chunk, and links are followed to completion the same way.
    """
    manifest = data.get("manifest", {})
    columns = [c["name"] for c in manifest.get("schema", {}).get("columns", [])]
    result = data.get("result", {}) or {}

    expected = manifest.get("total_row_count")

    rows: list = []
    if result.get("external_links"):
        payload: dict | None = result
        while payload:
            links = payload.get("external_links") or []
            if not links:
                break
            next_link = None
            for link in links:
                rows.extend(_fetch_external_link(link["external_link"]))
                # The continuation pointer rides on the link object, not the envelope.
                next_link = link.get("next_chunk_internal_link") or next_link
            if not next_link:
                break
            chunk = _fetch_chunk(next_link)
            # A continuation may return external_links at the TOP level or nested under
            # "result" depending on the endpoint. Accept both -- assuming one shape is what
            # truncated this to 1031/5596 rows on the first attempt.
            payload = chunk.get("result") or chunk
    else:
        rows = list(result.get("data_array", []) or [])
        next_link = result.get("next_chunk_internal_link")
        while next_link:
            chunk = _fetch_chunk(next_link)
            rows.extend(chunk.get("data_array", []) or [])
            next_link = chunk.get("next_chunk_internal_link")

    # Fail loud on a short read. Truncation here is silent and downstream-invisible: a
    # similarity search over 1/5 of the corpus returns confident, wrong neighbours rather
    # than an error. This codebase has already been bitten twice by exactly that (261/500
    # inline, then 1031/5596 external), so the invariant is asserted, not trusted.
    if expected is not None and len(rows) != int(expected):
        raise RuntimeError(
            f"truncated result: read {len(rows)} rows but manifest declares {expected}. "
            f"Refusing to return a partial result set."
        )
    return [dict(zip(columns, row, strict=True)) for row in rows]


# ---------------------------------------------------------------------------
# Public API — auto-dispatches to SQLite or Databricks
# ---------------------------------------------------------------------------

def create_job(job_id: str, document_name: str) -> None:
    s = get_settings()
    if s.is_databricks:
        _create_job_databricks(job_id, document_name)
        return

    conn = _get_conn()
    conn.execute(
        "INSERT INTO analysis_jobs (job_id, document_name, status, created_at) VALUES (?, ?, ?, ?)",
        (job_id, document_name, "accepted", datetime.now(UTC).isoformat()),
    )
    conn.commit()
    conn.close()


def update_job_status(job_id: str, status: str, **extra: Any) -> None:
    s = get_settings()
    if s.is_databricks:
        _update_job_databricks(job_id, status, **extra)
        return

    conn = _get_conn()
    sets = ["status = ?"]
    vals: list[Any] = [status]

    if status in ("complete", "error"):
        sets.append("completed_at = ?")
        vals.append(datetime.now(UTC).isoformat())

    for key in ("intermediate_report", "flaw_report", "recommendations"):
        if key in extra:
            sets.append(f"{key} = ?")
            vals.append(json.dumps(extra[key]) if extra[key] is not None else None)

    vals.append(job_id)
    conn.execute(f"UPDATE analysis_jobs SET {', '.join(sets)} WHERE job_id = ?", vals)
    conn.commit()
    conn.close()


def get_job(job_id: str) -> dict | None:
    s = get_settings()
    if s.is_databricks:
        return _get_job_databricks(job_id)

    conn = _get_conn()
    row = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    result = dict(row)
    for json_col in ("intermediate_report", "flaw_report", "recommendations"):
        if result.get(json_col):
            result[json_col] = json.loads(result[json_col])
    return result


def log_agent_event(
    job_id: str,
    layer: str,
    event_type: str,
    agent_name: str = "",
    message: str = "",
) -> None:
    s = get_settings()
    if s.is_databricks:
        _log_event_databricks(job_id, layer, event_type, agent_name, message)
        return

    conn = _get_conn()
    conn.execute(
        "INSERT INTO agent_events (job_id, timestamp, layer, event_type, agent_name, message) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (job_id, datetime.now(UTC).isoformat(), layer, event_type, agent_name, message),
    )
    conn.commit()
    conn.close()


def query_deficiencies(filters: dict[str, str] | None = None, limit: int = 50) -> list[dict]:
    s = get_settings()
    if s.is_databricks:
        return _query_deficiencies_databricks(filters, limit)

    conn = _get_conn()
    query = "SELECT * FROM deficiency_kb"
    params: list[str] = []
    if filters:
        clauses = []
        for key, val in filters.items():
            clauses.append(f"{key} LIKE ?")
            params.append(f"%{val}%")
        query += " WHERE " + " AND ".join(clauses)
    query += f" LIMIT {limit}"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Databricks implementations via SQL Statement Execution API
# ---------------------------------------------------------------------------

def _create_job_databricks(job_id: str, document_name: str) -> None:
    now = datetime.now(UTC).isoformat()
    table = _table("analysis_jobs")
    stmt = (
        f"INSERT INTO {table} (job_id, document_name, status, created_at) "
        f"VALUES ({_escape(job_id)}, {_escape(document_name)}, 'accepted', {_escape(now)})"
    )
    _run_sql(stmt)


def _update_job_databricks(job_id: str, status: str, **extra: Any) -> None:
    sets = [f"status = {_escape(status)}"]

    if status in ("complete", "error"):
        sets.append(f"completed_at = {_escape(datetime.now(UTC).isoformat())}")

    for key in ("intermediate_report", "flaw_report", "recommendations"):
        if key in extra:
            val = json.dumps(extra[key]) if extra[key] is not None else None
            sets.append(f"{key} = {_escape(val)}")

    table = _table("analysis_jobs")
    stmt = f"UPDATE {table} SET {', '.join(sets)} WHERE job_id = {_escape(job_id)}"
    _run_sql(stmt)


def _get_job_databricks(job_id: str) -> dict | None:
    table = _table("analysis_jobs")
    stmt = f"SELECT * FROM {table} WHERE job_id = {_escape(job_id)}"
    data = _run_sql(stmt)
    rows = _rows_from_result(data)
    if not rows:
        return None
    result = rows[0]
    for json_col in ("intermediate_report", "flaw_report", "recommendations"):
        if result.get(json_col):
            result[json_col] = json.loads(result[json_col])
    return result


def _log_event_databricks(
    job_id: str, layer: str, event_type: str, agent_name: str, message: str,
) -> None:
    now = datetime.now(UTC).isoformat()
    table = _table("agent_events")
    stmt = (
        f"INSERT INTO {table} (job_id, event_timestamp, layer, event_type, agent_name, message) "
        f"VALUES ({_escape(job_id)}, {_escape(now)}, {_escape(layer)}, "
        f"{_escape(event_type)}, {_escape(agent_name)}, {_escape(message)})"
    )
    _run_sql(stmt)


def _query_deficiencies_databricks(
    filters: dict[str, str] | None, limit: int,
) -> list[dict]:
    table = _table("deficiency_kb")
    stmt = f"SELECT * FROM {table}"
    if filters:
        clauses = []
        for key, val in filters.items():
            clauses.append(f"{key} LIKE {_escape(f'%{val}%')}")
        stmt += " WHERE " + " AND ".join(clauses)
    stmt += f" LIMIT {limit}"
    data = _run_sql(stmt)
    return _rows_from_result(data)
