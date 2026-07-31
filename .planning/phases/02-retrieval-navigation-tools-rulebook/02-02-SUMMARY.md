---
phase: 02-retrieval-navigation-tools-rulebook
plan: 02
subsystem: database

tags: [sqlite, faiss, pydantic, hybrid-search, rulebook, span-anchor, dependency-management]

# Dependency graph
requires:
  - phase: 01-ingestion-foundation
    provides: "span-anchor substrate (SpanID/NormalizedText/OffsetRun schemas, mint_span/open_span/HashMismatch re-open primitive, ingest/store.py's atomic-write + SQLite conventions)"
provides:
  - "RuleChunk pydantic model carrying RULES-04's required metadata ({source, citation, version, license, url} + span)"
  - "Atomic local persistence (write_chunk/read_chunk_nt/rulebook_nt_for) mirroring ingest/store.py exactly, upsert-by-doc_id"
  - "Exact-citation lookup (lookup_citation) + full enumeration (all_chunks) over a new rulebook_chunks SQLite table in the shared data/defpredict.db"
  - "Local FAISS+BM25/lexical hybrid search (rulebook_search) with zero network calls, D-RB6-compliant"
  - "The is_databricks two-backend dispatch seam (rulebook_search -> _rulebook_search_local | _rulebook_search_databricks), failing loudly (ModuleNotFoundError) rather than silently degrading until Plan 02-08 lands the Databricks side"
  - "Generic (src_id, dst_id, edge_type, provenance_span_id) edge table (add_edge/get_edges), D-RB3, enforcing 'no unexplained edges' in code"
  - "faiss-cpu promoted from [dependency-groups].dev to [project].dependencies (RESEARCH.md Pitfall 7 closed)"
affects: [02-03-rulebook-vendoring, 02-04-search-corpus-hybrid-fusion, 02-08-databricks-rulebook-backend, phase-3-agent-loop-tools, phase-5-adversarial-verifier]

# Tech tracking
tech-stack:
  added: ["faiss-cpu>=1.8 (now a runtime/base dependency, not dev-only)"]
  patterns:
    - "Two-backend dispatch behind one interface (is_databricks) -- extends the SAME established pattern in retrieval/vector_search.py::embed_texts and databricks/vector.py::search_similar to the rulebook store"
    - "Generic 4-column edge table (src_id, dst_id, edge_type, provenance_span_id) instead of bespoke per-relation tables -- zero-migration extensibility"
    - "Rulebook chunks pass through the SAME open_span/HashMismatch grounding primitive Phase-1 submission spans use -- no parallel, weaker verification path"
    - "Process-lifetime module-global FAISS cache (mirrors databricks/vector.py's _ensure_faiss) -- correct here because the rulebook is one shared build-once/query-many corpus, not per-run state"

key-files:
  created:
    - src/rulebook/__init__.py
    - src/rulebook/store.py
    - src/rulebook/edges.py
    - tests/rulebook/__init__.py
    - tests/rulebook/conftest.py
    - tests/rulebook/test_store.py
    - tests/rulebook/test_edges.py
  modified:
    - pyproject.toml

key-decisions:
  - "faiss-cpu moved from [dependency-groups].dev to [project].dependencies, verified via a full uv sync (fresh venv resolves cleanly, faiss imports OK) in addition to the tomllib acceptance checks"
  - "_rulebook_search_local's dense (FAISS) leg is fully wired and exercised, but final fusion falls back to pure-lexical ranking via a documented ImportError branch until retrieval.hybrid (RRF) lands in Plan 02-04 -- tests assert the dense leg runs without error and correct chunks still surface, not a dense-driven ranking that doesn't exist yet"
  - "fixture_chunk(tmp_path) test helper returns (chunk, nt, cache_dir, db_path) so every test is fully tmp_path-isolated, never touching the shared data/ directory or data/defpredict.db"

patterns-established:
  - "Rulebook persistence mirrors ingest/store.py's atomic temp->os.replace + sqlite3.Row conventions exactly, adding new tables (rulebook_chunks, edges) to the SAME data/defpredict.db file rather than a separate database"
  - "Parameterized SQL only, everywhere (? placeholders); WHERE-clause structure may be built dynamically from fixed literal column names, but values are never string-interpolated"

requirements-completed: [RULES-04]

duration: ~25min
completed: 2026-07-31
---

# Phase 02 Plan 02: Rulebook Local Store (RuleChunk + Edges + Hybrid Search) Summary

**Local SQLite+FAISS+BM25 rulebook backend (RuleChunk model, atomic persistence, citation lookup, hybrid search, generic edge table) built TDD, with faiss-cpu promoted to a runtime dependency and the is_databricks dispatch seam failing loudly until Plan 02-08 lands.**

## Performance

- **Duration:** ~25 min (includes worktree base recovery -- see Issues Encountered)
- **Completed:** 2026-07-31
- **Tasks:** 3 completed (each as a RED -> GREEN TDD pair, 6 commits total)
- **Files modified:** 8 (7 created, 1 modified)

## Accomplishments

- `RuleChunk` pydantic model + atomic local persistence (`write_chunk`/`read_chunk_nt`/`rulebook_nt_for`) that upserts by `doc_id` and passes the exact same `ingest.anchors.open_span`/`HashMismatch` grounding primitive Phase-1 submission spans use -- proven byte-exact re-open in tests, not asserted
- `lookup_citation` (exact-match) + `all_chunks` (full enumeration) over a new `rulebook_chunks` SQLite table in the shared `data/defpredict.db`, parameterized queries only
- Local FAISS+lexical hybrid search (`rulebook_search`) with a working `is_databricks` two-backend dispatch: the local branch runs with zero network calls; the Databricks branch raises `ModuleNotFoundError` (never a silent fallback) until Plan 02-08 implements `src/databricks/rulebook.py`
- Generic `(src_id, dst_id, edge_type, provenance_span_id)` edge table (`add_edge`/`get_edges`) enforcing "no unexplained edges" in code (`ValueError` on empty provenance)
- `faiss-cpu` promoted to `[project].dependencies`, verified clean via a full `uv sync` (fresh venv, `import faiss` succeeds) -- RESEARCH.md Pitfall 7 closed

## Task Commits

Each task followed the mandatory RED -> GREEN TDD cycle, committed atomically:

1. **Task 1: store.py -- RuleChunk model + atomic local persistence + citation lookup**
   - `12dfba1` (test) -- failing tests for RuleChunk/write_chunk/read_chunk_nt/lookup_citation/all_chunks/span re-open/atomic write
   - `eb02498` (feat) -- implementation; 12/12 tests green
2. **Task 2: store.py -- local FAISS+BM25 hybrid search + is_databricks dispatch + faiss-cpu promotion**
   - `a28fb65` (test) -- failing tests for rulebook_search's local hybrid ranking, empty-corpus, dense-leg-no-crash, and databricks-dispatch-fails-loudly
   - `8e3fd60` (feat) -- implementation + pyproject.toml dependency move; 17/17 tests green (Task 1 + 2)
3. **Task 3: edges.py -- the generic edge table**
   - `31b135c` (test) -- failing tests for add_edge/get_edges filter combinations, upsert, empty-provenance rejection
   - `5912669` (feat) -- implementation; 22/22 tests green (full plan suite)

**Plan metadata:** (this commit, following SUMMARY.md)

_TDD tasks: every task has exactly a test -> feat pair; no refactor commit was needed (implementation matched the plan's own worked-out code closely, no cleanup pass required)._

## Files Created/Modified

- `src/rulebook/__init__.py` - plain eager barrel re-exporting `RuleChunk`
- `src/rulebook/store.py` - `RuleChunk` model, atomic persistence, citation lookup, local FAISS+lexical hybrid search, `is_databricks` dispatch seam
- `src/rulebook/edges.py` - generic `(src_id, dst_id, edge_type, provenance_span_id)` edge table
- `tests/rulebook/__init__.py` - empty package marker (enables `from tests.rulebook.conftest import ...`, matching `tests/ingest/`'s convention)
- `tests/rulebook/conftest.py` - `fixture_chunk(tmp_path)` builder: real `NormalizedText` + matching `RuleChunk`, tmp_path-scoped `(cache_dir, db_path)`
- `tests/rulebook/test_store.py` - 17 tests covering Tasks 1 and 2
- `tests/rulebook/test_edges.py` - 5 tests covering Task 3
- `pyproject.toml` - moved `faiss-cpu>=1.8` from `[dependency-groups].dev` to `[project].dependencies`

## Decisions Made

- **Dense-leg test strategy:** rather than asserting a specific dense-driven fusion order (which the plan's own code cannot yet produce -- `retrieval.hybrid`'s RRF lands in Plan 02-04, and the current `ImportError` fallback always uses pure-lexical ranking), the dense-leg test builds a real tiny in-memory `faiss.IndexFlatIP` and asserts the FAISS query path runs cleanly end-to-end and correct results still surface. This avoids a test that would pass even if the dense leg were deleted, while still exercising and validating the actual FAISS wiring (`_ensure_faiss`, `index.search`, `embed_query` integration).
- **`uv sync` verification:** ran a full `uv sync` (no `uv.lock` existed in this worktree) to confirm the `faiss-cpu` dependency-group move resolves cleanly in a fresh install -- confirmed both via the plan's `tomllib`-based acceptance checks and by actually importing `faiss` from the freshly-synced venv's interpreter. `.venv/` and `uv.lock` are gitignored (not committed) per existing project convention.
- **Test isolation:** every test uses `tmp_path`-scoped `cache_dir`/`db_path` (never the shared `data/` directory or `data/defpredict.db`), and the FAISS module-level cache (`store._faiss_index`/`store._faiss_doc_ids`) is reset via an `autouse` fixture (`raising=False`, since those attributes don't exist until Task 2's GREEN phase) so no test's monkeypatched state leaks into another.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' code matches the plan's own worked-out implementation; no Rule 1/2/3 auto-fixes were needed in the plan's own scope.

## Issues Encountered

**Worktree base was stale by 87 commits (pre-execution, resolved before Task 1).** This worktree's branch (`worktree-agent-afe2ff57cc436d058`) was checked out at `bdad5c5` ("Replace 3-layer pipeline with deterministic-first fault detection"), which predates the entire `.planning/` directory, `CLAUDE.md`, and all of Phase 0/1/2's work -- the plan file this agent was asked to execute did not exist in the worktree. Diagnosed via `git worktree list` + `git merge-base`, confirmed the working tree was clean (no uncommitted work to lose), and applied the sanctioned worktree-branch-check recovery from `worktree-path-safety.md` (`git reset --hard` to `CLI_for_folders`'s tip `efed2d4`, the only permitted exception to the destructive-git-operations prohibition). Verified afterward that HEAD remained on the correct `worktree-agent-afe2ff57cc436d058` branch (not detached, not a protected ref) and that the plan file and full `.planning/` tree were then present. This was infrastructure recovery, not a plan deviation -- no plan files were affected.

**Pre-existing, out-of-scope test failures found (not fixed, not caused by this plan).** A full-repo regression run (`pytest tests/`) surfaced 19 failures, all in `tests/evals/test_cli.py` and `tests/evals/test_metrics.py`, all with the same root cause: `src/evals/metrics.py::_retrieval_recall_at_k` reads `fault.cited_section_indices`, a field `src/schemas/faults.py::Fault` does not define. Verified via `git show efed2d4:...` that this drift already existed at this plan's base commit, before any of this plan's changes -- entirely unrelated to `src/rulebook/`. `src/schemas/faults.py` is an explicit import-only file this plan must never modify, and `src/evals/metrics.py` is not in this plan's `files_modified`, so per the deviation rules' scope boundary this was left untouched and is recorded here for the orchestrator/next session rather than in a shared `deferred-items.md` (which is outside this plan's declared file scope). This plan's own suite (`tests/rulebook/`, 22/22) is unaffected and fully green both under the system Python and a freshly `uv sync`'d venv.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The local rulebook backend (persistence, citation lookup, hybrid search, edge table) is complete and D-RB6-offline-compliant; Plan 02-03 can now vendor real eCFR/ICH/FDA content through `write_chunk` and populate the edge table through `add_edge`.
- `rulebook_search`'s dense leg will automatically start contributing to fused ranking as soon as Plan 02-04 lands `retrieval.hybrid::reciprocal_rank_fusion` -- no further changes to `store.py` are needed for that integration (the `try/except ImportError` seam is already in place).
- The `is_databricks` dispatch is ready for Plan 02-08 to fill in `src/databricks/rulebook.py::search_rulebook_databricks` -- the contract (`query: str, top_k: int -> list[RuleChunk]`) is locked by this plan's dispatch call site.
- **Blocker for the orchestrator/next session (not this plan):** the pre-existing `Fault.cited_section_indices` gap in `src/schemas/faults.py`/`src/evals/metrics.py` (see Issues Encountered) blocks 19 eval-harness tests and is outside every currently-executing Phase-2 plan's `files_modified` scope -- it will need its own fix task.

## Self-Check: PASSED

All 7 claimed files verified present on disk (`src/rulebook/__init__.py`, `src/rulebook/store.py`, `src/rulebook/edges.py`, `tests/rulebook/__init__.py`, `tests/rulebook/conftest.py`, `tests/rulebook/test_store.py`, `tests/rulebook/test_edges.py`) plus `pyproject.toml` (modified) and this `SUMMARY.md`. All 6 task commits (`12dfba1`, `eb02498`, `a28fb65`, `8e3fd60`, `31b135c`, `5912669`) plus the SUMMARY commit (`f55e152`) verified present via `git cat-file -t`. No missing items.

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*
