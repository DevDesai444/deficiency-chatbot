---
phase: "05"
plan: "05"
subsystem: "rulebook-precedent-leg"
tags:
  - RECALL-04
  - D-PRC1
  - D-PRC2
  - D-PRC3
  - D-PRC4
  - D-PIX1
  - D-PIX3
  - B2-fix
  - Pitfall3
  - Pitfall4
  - Ruling9-threshold-loader
dependency_graph:
  requires:
    - "05-01: issue_cached_span, emit_precedent_finding, PrecedentAnchor (Wave 0)"
    - "05-01: precedent_threshold.json stub created"
    - "rulebook.store: _ensure_faiss, _faiss_index, _faiss_doc_ids (IndexFlatIP)"
    - "rulebook.precedents: get_provenance (ANDA# metadata)"
    - "retrieval.vector_search: embed_query (L2-normalized embeddings)"
  provides:
    - "rulebook.precedent_search: search_precedents, detect_precedent_candidates, _search_rulebook_faiss_with_scores, _filter_precedent_chunks (RECALL-04)"
    - "src/evals/baseline/precedent_threshold.json: threshold 0.6 (D-PRC4 initial value)"
  affects:
    - "05-06 (Wave 4): gate wiring for precedent-gate in run.py"
    - "05-07: anti-overfitting guard — precedent threshold transfer test"
tech_stack:
  added: []
  patterns:
    - "B2 fix: _search_rulebook_faiss_with_scores uses direct FAISS IndexFlatIP.search — real cosine = inner product for L2-normalized vectors"
    - "module-alias import (import rulebook.precedents as _precedents_module) for testable get_provenance patch"
    - "Ruling 9 threshold-loader exemption: fallback float only inside _load_precedent_threshold; no inline float elsewhere"
    - "Pitfall 3: len(section_text) < 100 early-exit before embedding call"
    - "Pitfall 4 source-inspection test: inspect.getsource(ps_module) asserts no ephemeral-index reference"
key_files:
  created:
    - "src/rulebook/precedent_search.py: search_precedents + detect_precedent_candidates + _search_rulebook_faiss_with_scores + _filter_precedent_chunks (B2 fix)"
  modified:
    - "tests/rulebook/test_precedent_search.py: replaced Wave-0 importorskip scaffold with 4 real passing tests"
    - "src/evals/baseline/precedent_threshold.json: threshold 0.0 -> 0.6 with note that it is NOT hardcoded in module code"
decisions:
  - "Import rulebook.precedents as _precedents_module (module alias) so get_provenance is patchable via monkeypatch in tests"
  - "D-GEN2 / Ruling 9: module docstring avoids inline float literal — docstring uses prose reference only; function body holds sole exemption"
  - "Pitfall 4 test strips module source via inspect.getsource and asserts no ephemeral-index name present"
metrics:
  duration: "~45 minutes"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 2
  commits: 1
  completed_date: "2026-08-07"
---

# Phase 5 Plan 05: RECALL-04 Precedent-Similarity Recall Leg Summary

RECALL-04 precedent leg implemented: search_precedents queries rulebook.faiss via direct FAISS IndexFlatIP.search for real cosine scores (B2 fix), applies same-ANDA exclusion, absolute cosine threshold from JSON, and emits PrecedentAnchor findings through the Wave-1 issue_cached_span gate.

## Completed Tasks

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | precedent_search.py + tests + threshold JSON | d4ef7d4 | precedent_search.py, test_precedent_search.py, precedent_threshold.json |

## Implementation Notes

### Task 1: Create precedent_search.py + tests + update threshold JSON

Created `src/rulebook/precedent_search.py` with four functions:

**`_load_precedent_threshold() -> float`** (Ruling 9 MEDIUM item d — sole exempt function):
- Reads `src/evals/baseline/precedent_threshold.json["threshold"]`
- Fallback return is the ONLY inline float allowed anywhere in the module
- Docstring notes "D-GEN2 exemption: sole function allowed to contain the fallback float"
- The verify regex strips this function body before scanning

**`_search_rulebook_faiss_with_scores(query_text, top_k) -> list[tuple[str, float]]`** (B2 fix):
- Imports `_faiss_index, _faiss_doc_ids` directly from `rulebook.store`
- Calls `_ensure_faiss()` then `_faiss_index.search(qv, top_k)` for real inner-product distances
- IndexFlatIP with L2-normalized vectors: IP distance == cosine similarity (range 0-1)
- Returns `[(doc_id, cosine_score)]` — NOT RuleChunk objects, NOT rank proxies

**`_filter_precedent_chunks(raw_results, submission_anda_number, threshold) -> list[tuple[str, float]]`**:
- Filter 1: `doc_id.startswith("precedent-")` (SC3)
- Filter 2: same-ANDA exclusion via `_precedents_module.get_provenance(doc_id)` (D-PRC3)
- Filter 3: `cosine_score >= threshold` on the REAL cosine value (B2 fix)

**`search_precedents(section_text, top_k=5, threshold=None, submission_anda_number=None)`**:
- Pitfall 3: `if len(section_text) < 100: return []` before any FAISS call
- `effective_threshold = threshold if threshold is not None else _load_precedent_threshold()`
- Retrieves 3x top_k candidates, filters, sorts descending, caps at top_k

**`detect_precedent_candidates(corpus, manifest, ledger, submission_anda_number=None)`**:
- Iterates `manifest.documents` -> `doc_entry.outline` for each section
- Calls `search_precedents` per section
- Builds `PrecedentAnchor(submission_span_id=span_id, precedent_doc_ids=..., similarity_scores=..., threshold=..., anda_excluded=...)`
- Emits via `emit_precedent_finding` (imported from `tools.emit_finding` — Plan 01, no write here, B5 fix)

### Import Pattern for Testability

The module uses `import rulebook.precedents as _precedents_module` and calls
`_precedents_module.get_provenance(doc_id)`. This lets tests patch the attribute via
`monkeypatch.setattr(ps_module._precedents_module, "get_provenance", ...)` which is the
standard Python module-attribute pattern. A direct `from ... import get_provenance` would bind
at import time and make monkeypatching ineffective.

### Test Coverage (4 tests, all GREEN)

- `test_same_anda_exclusion`: monkeypatches FAISS function and provenance; asserts empty result when ANDA matches (D-PRC3)
- `test_above_threshold_candidate`: monkeypatches FAISS and provenance (different ANDA); asserts `cosine_score > 0.6` as a VALUE assertion — not a source-text grep (B2 fix)
- `test_short_section_skipped`: asserts `_search_rulebook_faiss_with_scores` was never called for short text (Pitfall 3)
- `test_pitfall4_correct_index`: inspects `inspect.getsource(ps_module)` and asserts ephemeral-index name is absent (Pitfall 4)

### Ruling 9 Compliance

The plan's verify regex strips `_load_precedent_threshold` body before scanning. The module docstring was rewritten to avoid inline float literals — uses "threshold fallback float" (prose) while the function body holds the sole code literal. Same approach applied to D-PIX1 note to avoid the Pitfall 4 source-inspection test failure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-alias import needed for testable get_provenance patching**
- **Found during:** Task 1 (test_same_anda_exclusion failed)
- **Issue:** Plan scaffold used `from rulebook.precedents import get_provenance` which binds the name at import time. Monkeypatching `rulebook.precedents.get_provenance` had no effect on the already-bound local name in `_filter_precedent_chunks`.
- **Fix:** Changed to `import rulebook.precedents as _precedents_module` and calling `_precedents_module.get_provenance(doc_id)`. Updated test helper accordingly.
- **Files modified:** `src/rulebook/precedent_search.py`, `tests/rulebook/test_precedent_search.py`
- **Commit:** d4ef7d4

**2. [Rule 1 - Bug] Module docstring contained inline float and ephemeral-index name**
- **Found during:** Task 1 verify step (Ruling 9 inline-float scan + Pitfall 4 test)
- **Issue:** The module docstring's D-GEN2 note contained the literal `0.6` (triggering float guard) and D-PIX1 note named the ephemeral index explicitly (triggering Pitfall 4 source-inspection test). Both are prose-only issues, not functional code bugs.
- **Fix:** Rewrote both sentences to use descriptive prose without the triggering literals.
- **Files modified:** `src/rulebook/precedent_search.py`
- **Commit:** d4ef7d4

**3. [Rule 1 - Bug] Plan verify command used string type with inspect.getsource**
- **Found during:** Task 1 verify step
- **Issue:** Plan's verify command called `inspect.getsource(search_precedents.__module__)` — `__module__` is a string; getsource raises TypeError.
- **Fix:** Used `import rulebook.precedent_search as m; inspect.getsource(m)` in the verify invocation. No plan source files modified — execution-time adaptation only.

## Known Stubs

None. All functions are fully implemented. `threshold: 0.6` in `precedent_threshold.json` is the plan-specified initial value per D-PRC4, not a stub — the note in the JSON says it should be updated after empirical measurement on mvr1381.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes. Module reads `rulebook.faiss` (read-only, T-05W2C-01 mitigated) and `precedent_provenance` SQLite (read-only, T-05W2C-02 accepted). `emit_precedent_finding` validates via `ledger.was_issued + open_span` (T-05W2C-03 mitigated by Plan 01).

## Test Results

```
tests/rulebook/test_precedent_search.py::test_same_anda_exclusion PASSED
tests/rulebook/test_precedent_search.py::test_above_threshold_candidate PASSED
tests/rulebook/test_precedent_search.py::test_short_section_skipped PASSED
tests/rulebook/test_precedent_search.py::test_pitfall4_correct_index PASSED

4 passed in 0.22s

Plan verify command:
  precedent_search.py B2 fix + D-GEN2 + Ruling9 threshold-loader exemption + Pitfall 4 OK
```

## Self-Check: PASSED

Files confirmed present:
- `src/rulebook/precedent_search.py` — FOUND (created)
- `tests/rulebook/test_precedent_search.py` — FOUND (modified from scaffold)
- `src/evals/baseline/precedent_threshold.json` — FOUND (updated to 0.6)
- `.planning/phases/05-deterministic-structural-cross-document-recall/05-05-SUMMARY.md` — FOUND (this file)

Commits confirmed:
- d4ef7d4: feat(05-05): RECALL-04 precedent-similarity leg — FOUND in git log
