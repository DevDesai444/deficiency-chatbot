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
