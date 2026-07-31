---
phase: 02-retrieval-navigation-tools-rulebook
plan: 08
subsystem: retrieval
tags: [databricks, delta-tables, cosine-similarity, sql-statement-api, dispatch-pattern, rulebook]

# Dependency graph
requires:
  - phase: 02-retrieval-navigation-tools-rulebook (plan 02)
    provides: "rulebook.store's RuleChunk/all_chunks/read_chunk_nt + the is_databricks dispatch seam (_rulebook_search_databricks's lazy forward-reference import this plan fulfills)"
  - phase: 02-retrieval-navigation-tools-rulebook (plan 03)
    provides: "the actual built local rulebook chunk store this plan pushes to Databricks: 605 chunks (215 eCFR + 4 ICH + 1 FDA + 385 precedent), from the git-tracked rulebook/ vendored snapshot"
provides:
  - "src/databricks/rulebook.py: push_chunks_to_delta() (build-time, LIVE, idempotent delete+insert) + search_rulebook_databricks() (runtime query, client-side cosine) -- completes Plan 02-02's two-backend dispatch seam (D-RB2/D-RB6)"
  - "Databricks Delta tables rulebook_chunks/rulebook_embeddings, live-populated with all 605 local rulebook chunks, verified via SQL COUNT(*) = 605 on both tables"
affects: [02-09, phase-3 (agent loop -- if the Databricks-side rulebook query is ever wired into an agent-facing tool)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-backend contract completion (D-RB6): config.Settings.is_databricks selects Databricks Delta + client-side-cosine vs local SQLite+FAISS+BM25 -- the tool contract (list[RuleChunk]) never changes"
    - "Client-side cosine over a Delta embeddings table, reproducing databricks/vector.py::_search_embeddings_table's exact structure against rulebook_embeddings/rulebook_chunks -- the literal Vector Search Admin API is 403 scope-blocked on the configured token (Pitfall 6)"

key-files:
  created:
    - src/databricks/rulebook.py
    - tests/rulebook/test_databricks_dispatch.py
  modified:
    - tests/rulebook/test_store.py

key-decisions:
  - "Rebuilt the local rulebook chunk store from scratch in this worktree, offline, from the git-tracked rulebook/ snapshot (build_ecfr/build_ich/build_fda with update_manifest=False + ingest_precedents against the vendored xlsm) -- the data/defpredict.db discovered in the shared main checkout was stale/contaminated (385 precedent-only rows, missing all 220 eCFR/ICH/FDA rule chunks), not a valid source to push from"
  - "Split Task 1 and Task 2 into two separate feat commits despite both being authored before the live run completed, by staging src/databricks/rulebook.py at its Task-1-only intermediate content first -- preserves one-commit-per-task even though Task 2's RED/GREEN work happened during Task 1's ~58min live-run wait"
  - "Fixed a pre-existing Plan 02-02 test (test_store.py) that started making a REAL Databricks SQL call once databricks.rulebook.search_rulebook_databricks existed -- see Deviations"

requirements-completed: [RULES-04]

# Metrics
duration: ~80min (of which ~58min is the one-time LIVE Databricks population of 605 chunks -- 2424 sequential SQL Statement Execution API round trips, ~1.4s/call, no bulk-insert path available over that HTTP API)
completed: 2026-07-31
---

# Phase 2 Plan 08: Databricks Rulebook Serving Summary

**Databricks Delta tables (`rulebook_chunks`/`rulebook_embeddings`) live-populated with all 605 local rulebook chunks via an idempotent `push_chunks_to_delta`, plus a client-side-cosine `search_rulebook_databricks` query path completing Plan 02-02's two-backend dispatch seam -- verified end-to-end without a single test touching real Databricks.**

## Performance

- **Duration:** ~80 min (dominated by a ~58 min one-time LIVE Databricks population run -- 2,424 sequential SQL Statement Execution API calls at ~1.4s/round-trip; the SQL Statement API has no bind-param/bulk-insert support, so this per-chunk delete+insert pattern, matching the codebase's existing Databricks write style, is inherently sequential)
- **Completed:** 2026-07-31T10:32:08Z
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- `push_chunks_to_delta()` run LIVE against the real configured Databricks workspace: read all 605 chunks from the local rulebook store (215 eCFR + 4 ICH + 1 FDA + 385 precedent), embedded every chunk's canonical text via the Databricks embeddings endpoint, and upserted them into `rulebook_chunks`/`rulebook_embeddings` -- verified via `_run_sql(SELECT COUNT(*)...)` returning exactly 605 on both tables
- `search_rulebook_databricks` implemented as the exact structural mirror of the already-proven `databricks/vector.py::_search_embeddings_table` client-side-cosine pattern, since the literal Vector Search Admin API is 403 scope-blocked on the configured token (RESEARCH.md Pitfall 6) -- reuses `_rows_from_result`'s chunk-pagination discipline, never the truncating `data_array`-only shortcut
- The two-backend dispatch seam Plan 02-02 wired (`rulebook.store.rulebook_search` -> `is_databricks` ? Databricks : local) is now fulfilled end-to-end; `tests/rulebook/test_databricks_dispatch.py` proves this via monkeypatch with zero real network calls
- Caught and fixed a real D-RB6 violation: a pre-existing Plan 02-02 test began making an actual live Databricks SQL call the moment `search_rulebook_databricks` started existing (see Deviations) -- the whole-cluster regression suite now runs in ~13s instead of ~85s with `DATABRICKS_HOST`/`DATABRICKS_TOKEN` unset, confirming the eliminated network call

## Task Commits

Each task was committed atomically:

1. **Task 1: push_chunks_to_delta -- LIVE population of Databricks rulebook_chunks/rulebook_embeddings** - `23e42f7` (feat)
2. **Task 2: search_rulebook_databricks -- client-side cosine query + mocked dispatch test** - RED `031af9e` (test) -> GREEN `48c6cb8` (feat)

_Note: no separate plan-metadata commit -- this SUMMARY.md is committed alongside per the worktree/parallel-executor protocol (orchestrator owns STATE.md/ROADMAP.md)._

## Files Created/Modified

- `src/databricks/rulebook.py` - `_ensure_rulebook_tables`/`push_chunks_to_delta` (Task 1) + `search_rulebook_databricks` (Task 2): the Databricks half of the rulebook's two-backend contract, reusing `databricks/delta.py`'s `_run_sql`/`_table`/`_escape`/`_rows_from_result` conventions verbatim
- `tests/rulebook/test_databricks_dispatch.py` - dedicated dispatch-seam test: `is_databricks=True` correctly reaches `search_rulebook_databricks`, monkeypatched, zero real Databricks calls
- `tests/rulebook/test_store.py` - one test renamed/rewritten (see Deviations) to stay accurate now that `databricks/rulebook.py` exists

## Decisions Made

- **Rebuilt the local rulebook store offline in this worktree** rather than trusting the `data/defpredict.db` found in the shared main checkout, which turned out to be stale/contaminated (385 precedent-only rows, zero eCFR/ICH/FDA rule chunks -- see Issues Encountered). Used `build_ecfr`/`build_ich`/`build_fda` (all offline-first: read the committed `rulebook/` snapshot when present, no network) with `update_manifest=False` to avoid touching the tracked `rulebook/manifest.yaml`, plus `ingest_precedents()` against the already-vendored `rulebook/precedents/*.xlsm`. Result: 605 chunks (215+4+1+385), matching Plan 02-03's own verified count exactly.
- **Task 1 / Task 2 commit split.** Both tasks' code were authored close together (Task 2's RED/GREEN work filled the ~58min wait for Task 1's live run), but `src/databricks/rulebook.py` was deliberately staged at its Task-1-only intermediate content first so `push_chunks_to_delta` and `search_rulebook_databricks` still land in separate, per-task commits.
- **`update_manifest=False`** on the offline rebuild calls specifically to avoid any risk of `rulebook/manifest.yaml` (a Plan 02-03-owned, git-tracked file) drifting from its committed content as a side effect of Task 1's data-provisioning work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Local rulebook store in this worktree was incomplete/stale, blocking Task 1's live-population step**
- **Found during:** Task 1 (before running `push_chunks_to_delta()` live)
- **Issue:** `data/` and `.env` are gitignored and do not propagate to a fresh `git worktree` checkout. The `data/defpredict.db` copied in from the shared main checkout (to unblock the live run) turned out to hold only 385 precedent-source rows and zero eCFR/ICH/FDA rule chunks -- inconsistent with Plan 02-03's committed SUMMARY, which verified 605 chunks (215+4+1+385) built and self-checked.
- **Fix:** Removed the copied `data/defpredict.db`/`data/rulebook_cache/` and rebuilt the local store from scratch, fully offline, from this worktree's own git-tracked `rulebook/` snapshot via `build_ecfr()`/`build_ich()`/`build_fda()` (`update_manifest=False`) + `ingest_precedents()` against the vendored xlsm. Result verified: `all_chunks()` = 605, matching Plan 02-03 exactly; spot-checked `lookup_citation("21 CFR 211.166")` resolves correctly.
- **Files modified:** none (data-only; `data/` is gitignored, `rulebook/manifest.yaml` deliberately untouched via `update_manifest=False`)
- **Verification:** `all_chunks()` returns 605, source breakdown `{ecfr: 215, ich: 4, fda: 1, precedent: 385}`; `git status --short` clean (manifest.yaml unmodified)
- **Committed in:** not applicable (no tracked-file change; this was worktree data provisioning)

**2. [Rule 1 - Bug] Pre-existing test started making a real live Databricks call once `databricks.rulebook.search_rulebook_databricks` existed**
- **Found during:** Task 2 (after implementing `search_rulebook_databricks`, running the whole-cluster regression)
- **Issue:** `tests/rulebook/test_store.py::test_rulebook_search_databricks_dispatch_fails_loudly_not_silently` (Plan 02-02) asserted `pytest.raises((ImportError, ModuleNotFoundError))`, documented as valid only until "`src/databricks/rulebook.py` lands in Plan 02-08." Once `search_rulebook_databricks` existed, the import succeeded and execution fell through to `retrieval.vector_search.embed_query` and `databricks.delta._run_sql` -- both hold their OWN module-level `get_settings` binding (via `from config import get_settings` at import time), never touched by this test's `config_module.get_settings` monkeypatch. Confirmed: the test made an actual live Databricks SQL call during a supposedly-offline run (`DID NOT RAISE`, and the run took the full real network round-trip time) -- a direct D-RB6 violation this plan's own success criteria forbids ("Zero test in this plan or anywhere in the phase reaches real Databricks").
- **Fix:** Renamed to `test_rulebook_search_databricks_dispatch_routes_to_databricks_module` and rewrote to monkeypatch `databricks.rulebook.search_rulebook_databricks` directly (mirroring `test_databricks_dispatch.py`'s new dedicated seam test), preserving the original test's intent -- prove `is_databricks=True` reaches the Databricks branch, never a silent local fallback -- while eliminating the real network call.
- **Files modified:** `tests/rulebook/test_store.py`
- **Verification:** `tests/rulebook/ -q` (33 tests) passes with `DATABRICKS_HOST=`/`DATABRICKS_TOKEN=` unset, completing in ~13s (down from ~85s pre-fix, confirming the eliminated live call)
- **Committed in:** `48c6cb8` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 blocking/data-provisioning, 1 bug -- both required for Task 1/Task 2 to be genuinely correct against real conditions, not scope creep)
**Impact on plan:** Deviation 2 is a direct, load-bearing validation of this plan's own T-02-27 threat-model mitigation ("a test accidentally reaching real Databricks because a monkeypatch target is misspelled/incomplete") -- the threat scenario the plan predicted actually materialized in a pre-existing test the moment this plan's module landed, and was caught by exactly the acceptance-criteria check (`DATABRICKS_HOST=`/`DATABRICKS_TOKEN=` unset test run) the plan specified.

## Issues Encountered

- **Worktree base was stale** (HEAD at an old pre-Wave-1 commit rather than `CLI_for_folders` tip `0292b07`) -- recovered via the sanctioned `git reset --hard` from `worktree-path-safety.md`, per this plan's explicit `<worktree_base_recovery>` instructions, after confirming HEAD was on the `worktree-agent-*` branch namespace.
- **Absolute-path/cwd hazard caught mid-session:** several early commands used `cd /Users/DEVDESAI1/dev/deficiency-chatbot && ...` or bare absolute paths without the `.claude/worktrees/agent-aa7f542305a6654c7` prefix, which resolve to the shared main checkout, not this isolated worktree (matches the documented #3097/#3099 hazards). Caught before any Write/Edit or destructive git operation occurred (the only actions taken against the main checkout were read-only: `git branch`/`log`/`fetch`/`worktree list`, `ls`, `grep`, a `.env` masked-value check, and one Databricks SQL smoke-test). Corrected course immediately: confirmed the true default worktree cwd, and every subsequent Write/Edit/commit used explicit worktree-rooted paths or the correct default cwd.
- **`.env` and `data/` are gitignored and did not propagate to this fresh worktree** -- copied `.env` from the main checkout (a plain filesystem copy of gitignored credentials, no git operation, never staged/committed) so the live Databricks run had credentials to use; the local rulebook store itself was rebuilt from scratch rather than copied (see Deviation 1).

## User Setup Required

None - no external service configuration required. Databricks credentials were already present in the repository root's `.env` (provisioned prior to this session); this plan only needed a worktree-local copy to run the live population step.

## Next Phase Readiness

- The Databricks half of D-RB2's two-backend rulebook contract is now real, not aspirational: `config.Settings.is_databricks=True` routes `rulebook.store.rulebook_search` to `search_rulebook_databricks`, which queries live-populated Delta tables holding the exact same 605 chunks the local SQLite/FAISS/BM25 backend serves (D-RB6).
- Per this plan's own documented deferral (mirroring D-RB3's identical precedent-search deferral and Plan 02-02's identical local-leg note): `search_rulebook_databricks`/`rulebook_search` still have ZERO agent-facing tool consumers in Phase 2 by design. Wiring either backend into an agent-facing tool (e.g. `read_guideline`'s citation-discovery fallback, Plan 02-09) is deferred to Phase-3 evidence.
- `push_chunks_to_delta()` is documented as idempotent (upsert-by-doc_id) and safe to re-run if the local rulebook store is later extended (e.g., additional ICH/FDA guidances) -- no design changes needed for a re-population.
- Minor follow-up opportunity (not a blocker): the 2,424-call, ~58min live-population runtime is inherent to the SQL Statement Execution API's lack of bulk-insert/bind-param support; if the local rulebook store grows substantially beyond 605 chunks, a future plan may want to batch multiple rows per `INSERT` statement (still `_escape`'d) rather than one row per round trip -- deliberately NOT done here to stay faithful to this plan's specified delete+insert-per-chunk pattern matching the codebase's existing Databricks write style.

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*

## Self-Check: PASSED

- All 3 created/modified files verified present on disk (`src/databricks/rulebook.py`, `tests/rulebook/test_databricks_dispatch.py`, `tests/rulebook/test_store.py`).
- All 3 task commit hashes (`031af9e`, `23e42f7`, `48c6cb8`) verified present in `git log`.
- Live Databricks row counts (605/605 on `rulebook_chunks`/`rulebook_embeddings`) verified via `_run_sql(SELECT COUNT(*)...)` at live-run completion (see `push_chunks_to_delta() returned: 605` in the run log).
