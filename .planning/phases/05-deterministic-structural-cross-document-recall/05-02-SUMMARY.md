---
phase: "05"
plan: "02"
subsystem: "retrieval-surface"
tags:
  - D-R5A
  - D-R5B
  - RECALL-05
  - Ruling-9-npy-fix
  - Ruling-9-key-exposure
  - Ruling-9-dense-coverage
  - index-persistence
dependency_graph:
  requires:
    - "05-01: CorpusIndex (corpus.py), RetrievalLedger, BM25Index, embed_texts/embed_query"
    - "05-01: ingest.store.cache_key / write_doc_cache / DEFAULT_CACHE_DIR"
    - "04: retrieval.hybrid.reciprocal_rank_fusion (k=60)"
    - "04: tools.textsplit.split_windows (window_chars=800)"
    - "04: ingest.anchors.mint_span"
  provides:
    - "D-R5A: search_corpus result 'score' field is dense cosine 0-1 (not RRF); 'rrf_score' preserved"
    - "D-R5B: build_doc_index builds .chunks.json/.embeddings.npy/.bm25.json at ingest"
    - "D-R5B: _has_persisted_index / _search_with_persisted_index / _search_legacy dispatch"
    - "D-CON2: sidecars keyed by content_hash+versions; content change invalidates sidecar"
    - "Ruling 9(a): .npy atomic write via open() file handle (not path-based np.save)"
    - "Ruling 9(b): CorpusIndex.cache_key_for(doc_id) exposes per-doc key for sidecar lookup"
    - "Ruling 9(c): dense_scores covers ALL chunk_ids (range(len(chunk_ids))), not just dense_order"
    - "Security: np.load(allow_pickle=False); sidecar-load-error fallback to _search_legacy"
  affects:
    - "absence.py line 142: top_score >= 0.04 threshold is now a live branch (was dead with RRF)"
    - "05-03 through 05-07: all plans can assume non-dead absence threshold signal"
    - "all query-time performance: O(corpus × queries) → O(query) once sidecars present"
tech_stack:
  added:
    - "numpy np.save via open() file handle: Ruling 9 atomic-write pattern"
    - "json.loads/json.dumps for .chunks.json and .bm25.json sidecar persistence"
    - "np.load(allow_pickle=False): security gate on numpy binary deserialization (T-05W1-01)"
  patterns:
    - "D-R5B dispatch: _has_persisted_index gates _search_with_persisted_index vs _search_legacy"
    - "Ruling 9 npy: open(tmp, 'wb') + np.save(f, arr) + os.replace(tmp, final)"
    - "D-CON2: sidecar key = content_hash__nv__sv__pv (same as JSON doc cache)"
    - "D-16 never-abort: build_doc_index errors caught/logged, ingest never crashes"
    - "T-05W1-04: sidecar load errors fall back to _search_legacy with warning"
key_files:
  created:
    - "tests/retrieval/__init__.py: new test package"
    - "tests/retrieval/test_hybrid.py: D-R5A motivation (RRF ceiling 0.0328 < 0.04) + Ruling 9 dense coverage"
    - "tests/ingest/test_corpus_index_persistence.py: 5 tests for D-R5B + all three Ruling 9 fixes"
  modified:
    - "src/tools/search_corpus.py: D-R5A all_scores/dense_scores, D-R5B build_doc_index/_has_persisted_index/_search_with_persisted_index/_search_legacy/_index_sidecar_paths"
    - "src/ingest/corpus.py: CorpusIndex.cache_key_for() method + ingest_corpus build_doc_index call"
    - "tests/tools/test_search_corpus.py: updated key-set assertion for new rrf_score field (Rule 1 auto-fix)"
decisions:
  - "D-R5A: score field is dense cosine (0-1); rrf_score field added for rank ordering — no function signature change"
  - "Ruling 9 npy: chose open() file handle approach (Option B from plan) over .tmp.npy suffix approach (Option A) — file handle is suffix-independent and explicit"
  - "Ruling 9 key exposure: chose CorpusIndex.cache_key_for() method (Option A from plan) — minimal change, reuses existing content_hash from DocEntry; no new manifest file needed"
  - "D-R5B _has_persisted_index: requires ALL three sidecars for ALL parseable docs — partial sidecar set would silently drop recall"
  - "Security T-05W1-01: np.load(allow_pickle=False) on every sidecar load; poisoned file falls back to _search_legacy"
  - "Security T-05W1-04: any sidecar load error (shape mismatch, missing key, numpy error) falls back to _search_legacy with warning log"
metrics:
  duration: "~1.5 hours"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
  commits: 2
  completed_date: "2026-08-07"
---

# Phase 5 Plan 02: D-R5A + D-R5B RECALL-05 Retrieval Surface Summary

Dense cosine score replacing dead-branch RRF score (D-R5A), per-submission index persistence at ingest with query-time sidecar loading (D-R5B), and all three Ruling 9 MEDIUM fixes — (a) .npy atomic-write via open() file handle, (b) CorpusIndex.cache_key_for() for query-time key exposure, (c) dense_scores over ALL chunk_ids — committed and green.

## Completed Tasks

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | D-R5A: dense cosine score for ALL fused chunks + RRF ceiling regression test | 8f07755 | search_corpus.py, tests/retrieval/test_hybrid.py, test_search_corpus.py |
| 2 | D-R5B: per-submission index persistence at ingest + load at query (all Ruling 9 fixes) | 44da350 | search_corpus.py, corpus.py, test_corpus_index_persistence.py |

## Implementation Notes

### Task 1: D-R5A — Dense Cosine Score

The pre-existing code computed `scores = (e_norm @ q_norm.T).flatten()` but then only used a slice (`dense_order`) for `dense_ranked`. Critically, the `score` field in the result used the RRF score from `reciprocal_rank_fusion`, which has a mathematical ceiling of `N/(k+1) = 2/61 ≈ 0.0328`. The absence.py threshold is `top_score >= 0.04` — this was a permanent dead branch.

Fix (3 changes to `search_corpus.py`):
1. Renamed `scores` to `all_scores` (communicates full-corpus intent)
2. Built `dense_scores = {chunk_ids[i]: float(all_scores[i]) for i in range(len(chunk_ids))}` — covers ALL chunks, not just `dense_order` subset (Ruling 9 dense coverage)
3. Loop variable `score` renamed to `rrf_score`; result dict gains `"score": dense_scores.get(cid, 0.0)` and `"rrf_score": rrf_score`

The `dense_scores.get(cid, 0.0)` always hits because `dense_scores` covers all chunk_ids — there are no lexical-only hits that would fall through to the 0.0 default.

### Task 2: D-R5B — Per-Submission Index Persistence

**corpus.py changes:**

Added `CorpusIndex.cache_key_for(doc_id) -> str | None` — derives the cache key from `d.content_hash` already in the manifest, matching `cached_entry()`'s own key derivation. This exposes the key without re-hashing file bytes (Ruling 9 key exposure).

`ingest_corpus` now calls `build_doc_index(cache_dir, key, nt, doc_id)` after `write_doc_cache`. Errors are caught with `except Exception` and logged as warnings — the D-16 never-abort contract is preserved.

**search_corpus.py additions:**

- `_index_sidecar_paths(cache_dir, key)` — returns `{"chunks": ..., "embeddings": ..., "bm25": ...}` Path dict for the three sidecars
- `build_doc_index(cache_dir, key, nt, doc_id)` — builds all three sidecars atomically:
  - `.chunks.json` and `.bm25.json`: standard temp-file atomic write (`.tmp` suffix safe for text)
  - `.embeddings.npy`: uses `with open(tmp, "wb") as f: np.save(f, arr)` then `os.replace(tmp, final)` — the open() file handle bypasses np.save's .npy-appending behavior entirely (Ruling 9)
- `_has_persisted_index(corpus)` — checks all three sidecars exist for ALL parseable docs; uses `corpus.cache_key_for(doc_id)` (Ruling 9 key exposure); False if any sidecar missing
- `_search_with_persisted_index(corpus, query, ledger, top_k)` — fast path: loads sidecars, embeds only query; `np.load(allow_pickle=False)` (T-05W1-01); falls back to `_search_legacy` on any load error (T-05W1-04); Ruling 9 dense coverage applied (dense_scores over ALL chunk_ids)
- `_search_legacy(corpus, query, ledger, top_k)` — original embed-all path, preserved for backward compat
- `search_corpus` — dispatches on `_has_persisted_index`; result schema identical except `score` is cosine and `rrf_score` is new

**The .npy atomic-write bug (Ruling 9):**

`np.save(path, arr)` appends `.npy` to the path when `path` does NOT end in `.npy`. If a caller uses `path.with_suffix(".tmp")` → `"key.embeddings.tmp"`, np.save creates `"key.embeddings.tmp.npy"`. Then `os.replace("key.embeddings.tmp", "key.embeddings.npy")` fails with FileNotFoundError because `"key.embeddings.tmp"` was never created.

We avoid this entirely by using `open(tmp, "wb") as f: np.save(f, arr)` — np.save writing to a file object never appends `.npy` regardless of filename.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_search_corpus.py key-set assertion for new rrf_score field**
- **Found during:** Task 1 implementation
- **Issue:** Adding `rrf_score` to the result dict caused `test_search_corpus_returns_bounded_span_grounded_ledger_recorded_results` to fail: `AssertionError: {'doc_id', 'span_id', 'score', 'rrf_score', 'snippet'} != {'doc_id', 'span_id', 'score', 'snippet'}`
- **Fix:** Updated assertion to `assert set(r) == {"doc_id", "span_id", "score", "rrf_score", "snippet"}` with inline comment explaining D-R5A
- **Files modified:** `tests/tools/test_search_corpus.py`
- **Commit:** 8f07755

### Plan Interpretation Notes (Not Deviations)

- **`_build_chunks` signature**: The plan described `build_doc_index(cache_dir, key, nt, doc_id)` operating on a `NormalizedText`, while the existing `_build_chunks` takes a full `CorpusIndex`. These are separate concerns: `build_doc_index` takes `nt` for a single-doc build (called at ingest time), while `_build_chunks` builds across the whole corpus (used in `_search_legacy`). Added `_build_doc_chunks(nt, doc_id)` as the single-doc chunking helper.
- **`test_search_corpus_score_is_dense_cosine_not_rrf`**: Added to `tests/retrieval/test_hybrid.py` (rather than a separate file) since it directly demonstrates the D-R5A fix with mocked embeddings. This extends the test count from the plan's 4 tests to 4+1=5 in that file (net benefit: end-to-end proof of D-R5A).

## Known Stubs

None. All D-R5A and D-R5B behaviors are fully wired. No placeholder values in result schema.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: numpy_binary_deserialization | `src/tools/search_corpus.py:_search_with_persisted_index` | np.load on .embeddings.npy sidecar — mitigated: allow_pickle=False + load-error fallback to _search_legacy (T-05W1-01 / T-05W1-04 from plan threat register, both mitigated) |

## Test Results

```
tests/retrieval/test_hybrid.py (4 tests):
  test_rrf_score_ceiling_below_absence_threshold       PASSED (RRF max 0.0328 < 0.04)
  test_rrf_ceiling_is_exactly_two_over_k_plus_one      PASSED (algebraic proof)
  test_dense_scores_cover_all_chunk_ids                PASSED (range(len(chunk_ids)) verified)
  test_search_corpus_score_is_dense_cosine_not_rrf     PASSED (score=1.0, rrf_score<=0.033)

tests/ingest/test_corpus_index_persistence.py (5 tests):
  test_persisted_index_built_at_ingest                 PASSED (all 3 sidecars present)
  test_npy_atomic_write_correct_path                   PASSED (no double-.npy extension)
  test_persisted_index_loads_at_query                  PASSED (embed_texts not called at query)
  test_persisted_index_invalidated_on_content_change   PASSED (D-CON2 verified)
  test_sidecar_key_lookup                              PASSED (Ruling 9 key exposure verified)

Previous tests still green:
  tests/tools/test_search_corpus.py     6 passed (including updated key-set assertion)
  tests/tools/test_hybrid.py            4 passed (no regression)

Plan verification commands:
  PYTHONPATH=src uv run pytest tests/retrieval/test_hybrid.py tests/ingest/test_corpus_index_persistence.py -x -q  => 9 passed
  PYTHONPATH=src uv run python -c "import inspect, tools.search_corpus as m; src = inspect.getsource(m); assert 'dense_scores' in src; assert '_has_persisted_index' in src; print('D-R5A+R5B verified')"  => D-R5A+R5B verified
```

## Self-Check: PASSED

Files created/modified confirmed present:
- `src/tools/search_corpus.py` — dense_scores over range(len(chunk_ids)), rrf_score field, build_doc_index, _has_persisted_index, _search_with_persisted_index, _search_legacy, _index_sidecar_paths: FOUND
- `src/ingest/corpus.py` — CorpusIndex.cache_key_for(), build_doc_index call in ingest_corpus: FOUND
- `tests/retrieval/__init__.py`: FOUND
- `tests/retrieval/test_hybrid.py` — 4 tests: FOUND
- `tests/ingest/test_corpus_index_persistence.py` — 5 tests: FOUND
- `tests/tools/test_search_corpus.py` — key-set assertion updated: FOUND

Commits confirmed:
- 8f07755: feat(05-02): D-R5A — dense cosine score for ALL fused chunks + RRF ceiling test
- 44da350: feat(05-02): D-R5B per-submission index persistence + Ruling 9 fixes (npy/key/coverage)

evals/ directory untouched (confirmed via git diff HEAD~2 HEAD --name-only | grep evals/).
