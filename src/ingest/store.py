"""Content-hash-keyed persistence: resumable, version-invalidated cache + SQLite manifest index.

Storage-format decision (D-15, resolved discretion): the corpus manifest lives in **SQLite**
following the existing job store (`databricks/delta.py`: `sqlite3.Row` + JSON columns). The
per-document parse cache (which retains the FULL canonical text, D-32) is one JSON file per
`cache_key` under a controlled cache dir, written atomically (temp -> os.replace). Rationale:
SQLite matches the established job store; a JSON-per-doc cache keyed by content-hash is trivially
resumable and never writes under an attacker-controlled filename (T-01-03).

The cache key folds in `normalizer_version` + `serializer_version` + `parser_version`
(D-14/D-24): a version bump is a clean cache MISS, so parser/normalizer/serializer changes
never serve stale canonical text or stale span offsets (Pitfall 6).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

from ingest.manifest import CoverageManifest

DEFAULT_CACHE_DIR = "data/ingest_cache"
DEFAULT_DB_PATH = "data/defpredict.db"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


def content_hash(file_bytes: bytes) -> str:
    """Cache-invalidation key over the raw file bytes (D-14)."""
    return hashlib.blake2b(file_bytes, digest_size=16).hexdigest()


def cache_key(
    content_hash: str, normalizer_version: str, serializer_version: str, parser_version: str
) -> str:
    """A filesystem-safe key folding in all three versions; a version bump invalidates (D-24, Pitfall 6).

    `parser_version` was added in Phase 3 (P2 / D-PRE1). Before it, `content_hash` was a hash of
    the FILE BYTES (ingest/corpus.py:119), so a parser change altered canonical text and every
    span offset while the key stayed identical -- a stale entry was served indefinitely.
    Deliberately has NO default: a missed call site must fail loudly, not emit a wrong key.
    """
    nv = _UNSAFE.sub("_", normalizer_version)
    sv = _UNSAFE.sub("_", serializer_version)
    pv = _UNSAFE.sub("_", parser_version)
    return f"{content_hash}__{nv}__{sv}__{pv}"


def _cache_path(cache_dir, key: str) -> Path:
    return Path(cache_dir) / f"{key}.json"


def write_doc_cache(cache_dir, key: str, entry: dict) -> None:
    """Atomically persist a per-document cache entry (temp -> os.replace); no half entry on crash.

    `entry` retains the FULL canonical text (D-32) plus raw_serialized, offset_map, versions, the
    DocEntry, and the table index — so Phase 2 get_section / Phase 4 reference extraction never
    re-parse the corpus.
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    final = _cache_path(cache_dir, key)
    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry), encoding="utf-8")
    os.replace(tmp, final)   # atomic rename: a crash before this leaves only .tmp, never a half .json


def read_doc_cache(cache_dir, key: str) -> dict | None:
    """Return the cached entry for `key`, or None on a miss (skip-unchanged / reparse-on-miss)."""
    final = _cache_path(cache_dir, key)
    if not final.exists():
        return None
    return json.loads(final.read_text(encoding="utf-8"))


def _get_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS corpus_manifest "
        "(corpus_id TEXT PRIMARY KEY, manifest_json TEXT, created_at TEXT)"
    )


def save_manifest(manifest: CoverageManifest, corpus_id: str = "default", db_path: str = DEFAULT_DB_PATH) -> None:
    """Persist a CoverageManifest as a JSON column keyed by corpus_id (delta.py conventions, D-15)."""
    conn = _get_conn(db_path)
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO corpus_manifest (corpus_id, manifest_json, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(corpus_id) DO UPDATE SET manifest_json=excluded.manifest_json, created_at=excluded.created_at",
        (corpus_id, json.dumps(manifest.model_dump()), manifest.created_at),
    )
    conn.commit()
    conn.close()


def load_manifest(corpus_id: str = "default", db_path: str = DEFAULT_DB_PATH) -> CoverageManifest | None:
    """Load a CoverageManifest by corpus_id, or None if absent."""
    conn = _get_conn(db_path)
    _ensure_table(conn)
    row = conn.execute(
        "SELECT manifest_json FROM corpus_manifest WHERE corpus_id = ?", (corpus_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return CoverageManifest.model_validate(json.loads(row["manifest_json"]))
