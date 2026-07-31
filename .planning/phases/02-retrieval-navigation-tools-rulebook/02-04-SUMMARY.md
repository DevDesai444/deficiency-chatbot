---
phase: 02-retrieval-navigation-tools-rulebook
plan: 04
subsystem: retrieval
tags: [bm25, rank-bm25, reciprocal-rank-fusion, faiss, hybrid-search, span-grounding, retrieval-ledger]

# Dependency graph
requires:
  - phase: 02-retrieval-navigation-tools-rulebook (Plan 01)
    provides: "RetrievalLedger, ToolRejected, split_windows -- the tool-boundary primitives search_corpus imports directly; CorpusIndex.cached_entry, mint_span, open_span from the Phase-1 substrate"
provides:
  - "BM25Index (src/retrieval/lexical.py) -- ephemeral per-submission BM25 lexical index wrapper over rank-bm25, the D-RB5 lexical leg"
  - "reciprocal_rank_fusion (src/retrieval/hybrid.py) -- the public RRF formula (score = sum(1/(k+rank_i)), k=60) combining any number of ranked ID lists, no library"
  - "search_corpus (src/tools/search_corpus.py) -- the first of the 5 navigation tools: local hybrid (FAISS dense + BM25 lexical) retrieval over a per-submission corpus, chunked via split_windows, fused via RRF, returning span-grounded ({doc_id, span_id, score, snippet}), ledger-recorded results -- zero Databricks coupling"
affects: ["02-07 (SC4 retrieval-recall eval-harness gate calls search_corpus directly)", "02-05 (emit_finding -- search_corpus is how the agent discovers evidence spans to eventually cite)", "Phase 3 (agent drive loop registers search_corpus as its first callable tool)"]

# Tech tracking
tech-stack:
  added: ["rank-bm25>=0.2.2"]
  patterns:
    - "Per-call-local dense+lexical index construction (BM25Index + embeddings built fresh as local variables inside search_corpus(), never a module global) -- extends Plan 02-01's per-run RetrievalLedger discipline to the retrieval index itself (T-02-14)"
    - "Patch-the-importing-module's-namespace when mocking a from-import in tests (embed_texts/embed_query monkeypatched on tools.search_corpus, not on retrieval.vector_search where they're defined) -- matches the precedent tests/rulebook/test_store.py already established for the rulebook's own hybrid search"

key-files:
  created:
    - src/retrieval/lexical.py
    - src/retrieval/hybrid.py
    - src/tools/search_corpus.py
    - tests/tools/test_lexical.py
    - tests/tools/test_hybrid.py
    - tests/tools/test_search_corpus.py
  modified:
    - pyproject.toml

key-decisions:
  - "Test files for retrieval.{lexical,hybrid} live under tests/tools/ (not tests/retrieval/, which does not exist), matching this phase's VALIDATION.md quick-run scope and the plan's own declared file list verbatim"
  - "Every test mocks the dense leg (embed_texts/embed_query) rather than loading the real bge-m3 model, for speed/determinism/offline-safety (D-RB6) -- the SC4 exact-identifier test specifically constructs mocked dense scores that rank a semantically-similar-but-wrong-number distractor ABOVE the target, so the test proves the BM25 leg -- not a lucky dense embedding -- is what rescues the correct document"
  - "This worktree requires `uv run pytest` (not bare `pytest`/`python3 -m pytest`) to reach the project's managed venv -- bare `pytest` on PATH resolves to an unrelated global Python 3.12 install lacking rank-bm25 and every other project dependency (fastapi, pydantic, etc.); the plan's own literal `PYTHONPATH=src pytest ...` verify commands were run as `PYTHONPATH=src uv run pytest ...` throughout"

patterns-established:
  - "SC4 hard-subset test pattern: mock the dense leg to DELIBERATELY favor the wrong document (proving dense-alone would fail), then assert the FUSED result still surfaces the right one via BM25 -- reusable by Plan 02-07's eval-harness gate as the same proof shape at corpus scale"
  - "Multi-document CorpusIndex test fixtures are assembled by calling the existing single-doc tests/tools/conftest.py::build_corpus_index() once per document (same tmp_path/cache_dir, distinct doc_ids) and merging the resulting DocEntry rows into one CoverageManifest -- avoids modifying the shared conftest.py while still reusing its real serialize/normalize/build_table_index pipeline"

requirements-completed: [TOOLS-01]

# Metrics
duration: ~49min
completed: 2026-07-31
---

# Phase 2 Plan 04: Hybrid Retrieval Tool (search_corpus) Summary

**Local FAISS+BM25 hybrid `search_corpus` tool fusing dense and lexical rankings via Reciprocal Rank Fusion (k=60), with a real test proving the SC4 exact-identifier hard subset is carried by the BM25 leg even when the dense leg is deliberately wrong.**

## Performance

- **Duration:** ~49 min
- **Started:** 2026-07-31T07:38:41Z
- **Completed:** 2026-07-31T08:27:33Z
- **Tasks:** 2 / 2
- **Files modified:** 7 (6 created + pyproject.toml)

## Accomplishments

- `BM25Index` (`src/retrieval/lexical.py`): thin `rank-bm25` wrapper -- the ephemeral, per-submission lexical leg, deliberately separate from the rulebook's own (persistent, build-once) local BM25 in `src/rulebook/store.py`.
- `reciprocal_rank_fusion` (`src/retrieval/hybrid.py`): the public RRF formula `score = sum(1/(k+rank_i))`, k=60, hand-verified against a worked example, no library.
- `search_corpus` (`src/tools/search_corpus.py`): chunks every `parsed`/`parsed_partial` document's canonical text via `split_windows`, runs a local FAISS-equivalent dense leg (`embed_texts`/`embed_query`, pinned to local bge-m3 per D-RB6, reused verbatim) and the new BM25 lexical leg, fuses both rankings via RRF, mints a span-ID per fused chunk, `ledger.record_span`s it, and returns `{doc_id, span_id, score, snippet}` -- never a whole document. Zero Databricks coupling: no `is_databricks` branch, no `databricks.*` import anywhere in the file (grep-verified, and asserted directly in a test via `inspect.getsource`).
- The per-run index (BM25 index + embeddings) is built entirely from local variables inside each `search_corpus()` call -- no module-global cache -- proven by a test that queries two different `CorpusIndex` instances back-to-back and asserts zero cross-run leakage (T-02-14).
- SC4's exact-identifier hard subset is proven functionally: a query for a bare numeric identifier (`"11477"`) ranks its home document first even when the dense leg is mocked to rank a semantically-identical-but-wrong-number distractor (`"20038"`) as the closer embedding match -- the hybrid RRF fusion, not a lucky embedding, is what gets it right.
- 14 new tests (8 for lexical/hybrid, 6 for search_corpus), all offline (dense leg mocked, no model load, no network); whole-plan and whole-`tests/tools/` suites green (43/43); confirmed zero regressions in `tests/rulebook/` (22/22, whose own local hybrid search now exercises the real `retrieval.hybrid` fusion path for the first time since it landed in this plan) and in the full repo suite (235 passed, 19 pre-existing/out-of-scope failures unchanged from Plan 02-01's baseline, 0 new failures).

## Task Commits

Each task was committed atomically:

1. **Task 1: lexical.py (BM25) + hybrid.py (RRF) fusion primitives** - `4ac88d2` (feat)
2. **Task 2: search_corpus.py -- chunk, embed, fuse, annotate, record** - `4f7d47e` (feat)

_Both were `type="auto" tdd="true"` tasks; tests were written together with the implementation in each task's single commit, matching Plan 02-01's established precedent in this same phase (plan action blocks specified test-writing and implementation together per task, not as separate RED/GREEN steps)._

## Files Created/Modified

- `src/retrieval/lexical.py` - `BM25Index` (`__init__`, `.query`)
- `src/retrieval/hybrid.py` - `reciprocal_rank_fusion`
- `src/tools/search_corpus.py` - `_nt_from_cache_entry`, `_build_chunks`, `search_corpus`
- `tests/tools/test_lexical.py` - 4 tests (exact-token ranking, numeric-identifier ranking, empty corpus, top_k)
- `tests/tools/test_hybrid.py` - 4 tests (hand-computed formula + ordering, empty rankings, single-list id not dropped, default k=60)
- `tests/tools/test_search_corpus.py` - 6 tests (bounded/span-grounded/ledger-recorded shape + byte-exact reopen, SC4 exact-identifier hard subset, empty corpus, no-Databricks source check, no cross-corpus index leakage, top_k honored)
- `pyproject.toml` - added `rank-bm25>=0.2.2` (via `uv add rank-bm25`)

## Decisions Made

- Followed Plan 02-01's precedent of one commit per task (implementation + tests together) rather than splitting into separate `test(...)`/`feat(...)` RED/GREEN commits, since both this plan's task `<action>` blocks and the sibling plan already established this convention for `tdd="true"` tasks whose behavior and implementation are both fully specified together.
- Multi-document `CorpusIndex` test fixtures are built by calling `tests/tools/conftest.py::build_corpus_index()` once per document against the same `tmp_path` (shared `cache_dir`) and merging the resulting single-`DocEntry` manifests into one `CoverageManifest`, rather than modifying the shared `conftest.py` (which is out of this plan's declared `files_modified` scope) or hand-rolling a fake cache.
- The exact-identifier test's mocked dense-leg scores are deliberately constructed (via a hand-computed RRF trace, verified empirically by the passing test on first run) so the distractor document tops the dense-only ranking while the target only ranks second -- this makes the test a real proof that BM25 rescues the correct answer, not a coincidence of a scoring tie.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected a stale worktree base before any work could begin**
- **Found during:** pre-Task-1 setup (mandatory worktree branch/base check, per this plan's explicit `<worktree_base_recovery>` instruction)
- **Issue:** This worktree's branch (`worktree-agent-a4659c00cab773a74`) was created from `bdad5c5`, a commit predating all of Phase 1's `src/ingest/` module and Phase 2 Wave 1 (`src/tools/*`, `src/rulebook/store.py`). None of this plan's required imports (`ingest.anchors`, `ingest.corpus`, `tools.ledger`, `tools.textsplit`, `retrieval.vector_search`) were present.
- **Fix:** Verified HEAD was attached to the correct `worktree-agent-*` namespace (not a protected ref) and the working tree was clean, then ran the sanctioned `git reset --hard 3f9d3b4` (the current `CLI_for_folders` tip) per `worktree-path-safety.md`'s spawn-time branch check.
- **Files modified:** none (a branch-pointer correction, not a content change).
- **Verification:** `git rev-parse HEAD` == `3f9d3b4`; `src/tools/ledger.py` and `src/retrieval/vector_search.py` confirmed present afterward.
- **Committed in:** n/a (branch correction, no commit of its own; both task commits build on top of `3f9d3b4`).

**2. [Rule 3 - Blocking] Used `uv run pytest` instead of the plan's literal bare `pytest` invocation**
- **Found during:** pre-Task-1 verification (confirming `rank-bm25` was importable after `uv add`)
- **Issue:** This worktree has its own project-managed `.venv`, but bare `pytest`/`python3` on `PATH` resolve to an unrelated global installation (`pytest 9.0.2`, no project dependencies at all -- not `rank_bm25`, not `fastapi`, not `pydantic`). Running the plan's literal `PYTHONPATH=src pytest ...` verify commands as written would fail on basic imports, not just the new dependency.
- **Fix:** Ran every verify/acceptance-criteria command as `PYTHONPATH=src uv run pytest ...` instead, which correctly resolves the worktree's own `.venv` (confirmed via `uv run python3 -c "import rank_bm25, fastapi, pydantic"`).
- **Files modified:** none (an invocation-mechanism correction).
- **Verification:** all of Task 1's and Task 2's acceptance-criteria commands pass under `uv run`.
- **Committed in:** n/a (no content change; documented here so a future plan in this same worktree doesn't lose time rediscovering it).

---

**Total deviations:** 2 auto-fixed (both Rule 3 -- blocking environment/setup corrections, no design or scope changes).
**Impact on plan:** Both were necessary to execute the plan at all; neither changed what was built.

## Issues Encountered

None beyond the two blocking setup corrections above (see Deviations). The pre-existing, out-of-scope `tests/evals/` failures already logged in `.planning/phases/02-retrieval-navigation-tools-rulebook/deferred-items.md` by Plan 02-01 (19 tests, `AttributeError: 'Fault' object has no attribute 'cited_section_indices'`, root-caused to the off-limits `src/schemas/faults.py`) were re-confirmed unchanged in this plan's own full-repo regression run -- not re-logged, since the existing entry already covers them exactly.

## User Setup Required

None - no external service configuration required. All tests run entirely offline (dense embeddings mocked, no network, no Databricks credentials, no PDF/DOCX file I/O).

## Next Phase Readiness

- `search_corpus` is ready to be registered as the first of the 5 navigation tools in Phase 3's agent drive loop, and is ready for Plan 02-05's `emit_finding` to consume its returned span-IDs as discovered evidence.
- Plan 02-07's SC4 retrieval-recall eval-harness gate can call `search_corpus` directly; this plan's own exact-identifier test is the same proof shape (mock-the-dense-leg-wrong, assert-BM25-rescues-it) that gate should apply at real eval-corpus scale.
- `src/retrieval/hybrid.py`'s `reciprocal_rank_fusion` landing also activated the previously-dormant real-fusion code path inside `src/rulebook/store.py::_rulebook_search_local` (its `ImportError` fallback to pure-lexical ranking no longer triggers) -- confirmed zero regression via the full `tests/rulebook/` suite (22/22 still green).
- No blockers for this plan's own scope.

## Self-Check: PASSED

- All 7 created/modified files verified present on disk (`src/retrieval/` x2, `src/tools/search_corpus.py`, `tests/tools/` x3, `pyproject.toml`).
- Both commit hashes verified present in `git log --oneline`: `4ac88d2` (Task 1), `4f7d47e` (Task 2).
- Zero off-limits/import-only files touched (`git diff --name-only 3f9d3b4 HEAD -- src/agents/detection/ src/llm/client.py src/llm/structured.py src/schemas/faults.py tests/agents/detection/test_planner_redesign.py tests/unit/test_detection.py` is empty).

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*
