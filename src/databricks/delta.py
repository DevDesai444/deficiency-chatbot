"""
Data store abstraction — SQLite locally, Databricks Delta in production.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from config import get_settings

_DB_PATH = "data/defpredict.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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


# --- Databricks stubs (require DATABRICKS_HOST + DATABRICKS_TOKEN) ---

def _create_job_databricks(job_id: str, document_name: str) -> None:
    raise NotImplementedError("Databricks Delta write not yet configured — set ENVIRONMENT=local")

def _update_job_databricks(job_id: str, status: str, **extra: Any) -> None:
    raise NotImplementedError("Databricks Delta write not yet configured")

def _get_job_databricks(job_id: str) -> dict | None:
    raise NotImplementedError("Databricks Delta read not yet configured")

def _log_event_databricks(job_id: str, layer: str, event_type: str, agent_name: str, message: str) -> None:
    raise NotImplementedError("Databricks Delta write not yet configured")

def _query_deficiencies_databricks(filters: dict[str, str] | None, limit: int) -> list[dict]:
    raise NotImplementedError("Databricks Delta read not yet configured")
