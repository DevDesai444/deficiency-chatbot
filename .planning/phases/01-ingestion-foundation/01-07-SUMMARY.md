---
phase: 01-ingestion-foundation
plan: 07
subsystem: database
tags: [manifest, sqlite, cache, content-hash, atomic-write, availability-tiers]

requires:
  - phase: 01-ingestion-foundation
    provides: "SpanID + DocClassification (Plan 02); NormalizedText versions (Plan 03); databricks/delta.py SQLite conventions"
provides:
  - "ingest.manifest: CoverageManifest / DocEntry / OutlineEntry — status vocab + availability tiers + section outline (span-ID + label)"
  - "ingest.store: content_hash, cache_key (version-folded), write/read_doc_cache (atomic, full canonical text), save/load_manifest (SQLite)"
affects: [01-09]

tech-stack:
  added: []
  patterns:
    - "Declared availability contract: per-doc status + structure/tables tiers stated up front, read from the manifest not at runtime (D-30/SC6)"
    - "Atomic per-doc cache (temp -> os.replace) keyed by content-hash + normalizer/serializer versions (resumable + version-invalidated)"

key-files:
  created:
    - src/ingest/manifest.py
    - src/ingest/store.py
    - tests/ingest/test_store.py
  modified: []

key-decisions:
  - "D-15 storage format (resolved discretion): SQLite corpus_manifest table (JSON column, delta.py conventions) for the manifest index; one JSON file per cache_key under a controlled cache dir for the per-doc parse cache (retains full canonical text, D-32)."
  - "cache_key folds normalizer_version + serializer_version and sanitizes '/' etc. to a filesystem-safe key, so a version bump is a clean MISS (D-24) and the key is never derived from an attacker filename (T-01-03)."
  - "write_doc_cache writes key.tmp then os.replace(tmp, key.json): a crash before the rename leaves only a .tmp, never a half .json — read_doc_cache returns None and the doc reparses."

patterns-established:
  - "OutlineEntry stores the section span-ID as identity + the heading text as a label only (D-18)."

requirements-completed: []  # INGEST-03 manifest/store substrate landed; the corpus walker that populates it is Plan 09.

duration: ~30min
completed: 2026-07-30
---

# Phase 1 · Plan 07: Coverage Manifest + Resumable Content-Hash Store — Summary

**Defined the declared per-document availability contract (status + structure/tables tiers + section outline) and the content-hash-keyed persistence store — an atomic, version-invalidated per-doc cache that retains the full canonical text (D-32), plus a SQLite manifest index following the existing job-store conventions.**

## Performance
- **Duration:** ~30 min · **Tasks:** 2 · **Files:** 3 created

## Task Commits
1. **Task 1: manifest schema** — `8a36b05` (feat)
2. **Task 2: store (cache + SQLite)** — `bd2c11c` (feat)

## Verification (every acceptance command run via `.venv/bin/python`)
- Manifest round-trip (`parsed_partial` DocEntry → `model_validate(model_dump())`) → **manifest OK**; greps `parsed_partial` / `addressable|unavailable` / `OutlineEntry` pass.
- `test_cache_resume_and_invalidate` → passes: skip-unchanged hit; normalizer-version bump → MISS; no `.tmp` after success; a `.tmp`-only crash state → `read_doc_cache` returns None.
- `test_manifest_availability_tiers` → passes: flat doc persists `structure:flat`/`tables:unavailable` + degradation reason + outline label, round-trips through SQLite; escalation_rate preserved.
- `os.replace` + `normalizer_version` greps in store pass; `canonical` present in the cached entry (D-32).
- Full `pytest tests/ingest/` → **38 passed** (no regression).

## D-15 storage format (resolved discretion, recorded)
- **SQLite** `corpus_manifest(corpus_id PK, manifest_json, created_at)` for the index (delta.py `sqlite3.Row` + JSON-column conventions); **JSON-per-`cache_key`** files (atomic temp→rename) for the per-doc cache retaining the full canonical text. Rationale: matches the established job store, trivially resumable, never writes under an attacker-controlled filename.

## Files
- `src/ingest/manifest.py`, `src/ingest/store.py`, `tests/ingest/test_store.py`.
