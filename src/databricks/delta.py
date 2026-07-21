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


def _run_sql(statement: str) -> dict:
    s = get_settings()
    with _sql_client() as client:
        resp = client.post(
            "/api/2.0/sql/statements",
            json={
                "warehouse_id": s.databricks_warehouse_id,
                "statement": statement,
                "wait_timeout": "50s",
            },
        )
    data = resp.json()
    state = data.get("status", {}).get("state", "")
    if state != "SUCCEEDED":
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


def _fetch_chunk(link: str) -> dict:
    """Fetch one result chunk by its internal link (Databricks SQL Statement API)."""
    with _sql_client() as client:
        resp = client.get(link)
        resp.raise_for_status()
        return resp.json()


def _rows_from_result(data: dict) -> list[dict]:
    """Flatten a Databricks SQL result into row dicts, following chunk pagination.

    A large result is split across chunks: the initial response carries only the first
    chunk's ``data_array`` plus a ``next_chunk_internal_link``. Reading ``data_array``
    alone silently truncates the result (e.g. 261 of 500 rows on the embeddings table),
    so we walk the chunk links to completion.
    """
    manifest = data.get("manifest", {})
    columns = [c["name"] for c in manifest.get("schema", {}).get("columns", [])]
    result = data.get("result", {}) or {}
    rows = list(result.get("data_array", []) or [])
    next_link = result.get("next_chunk_internal_link")
    while next_link:
        chunk = _fetch_chunk(next_link)
        rows.extend(chunk.get("data_array", []) or [])
        next_link = chunk.get("next_chunk_internal_link")
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
