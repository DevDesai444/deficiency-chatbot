---
phase: "05"
plan: "07"
subsystem: "follow-reference-wiring + failure-family-extension"
tags:
  - RECALL-02
  - RECALL-03
  - RECALL-04
  - RECALL-05
  - Ruling-7
  - B4-fix
  - FailureFamily-extension
  - SC2-HARD-PATH
  - Wave-5
dependency_graph:
  requires:
    - "05-04: src/rulebook/edges.py (add_edge / get_edges with D-RB3 provenance)"
    - "05-04: src/rulebook/references.py (extract_references + detect_reference_anomalies)"
    - "05-06: src/evals/run.py phase5-gate SC2 probe (Plan 06 owns; imported _CROSS_DOC_PENDING)"
    - "05-01: tests/tools/conftest.py (build_corpus_index for offline B4 test fixture)"
  provides:
    - "src/tools/follow_reference.py: real cross-doc edge lookup (B4 fix, Ruling 7)"
    - "src/evals/schema.py: FailureFamily.structural + reference_graph + precedent_similarity"
    - "tests/tools/test_follow_reference.py: 5 tests (B4 integration + sentinel absence + db_path param)"
  affects:
    - "src/evals/run.py:813 phase5-gate SC2 probe: _CROSS_DOC_PENDING no longer returned → HARD path always taken"
    - "tests/evals/test_generality_guard.py: test_phase5_gate_sc2_x1_deferred_branch will fail (designed-to-fail after Wave 5)"
    - "Phase 7: UNRESOLVED_REF volume (~22) unchanged — precision signal for verifier handoff"
tech_stack:
  added: []
  patterns:
    - "follow_reference defaulted db_path: all existing call sites valid without modification"
    - "B4 integration test: build_corpus_index (offline) + add_edge (planted edge) + follow_reference"
    - "FailureFamily additive extension: iterate-all pattern in _end_to_end_by_family auto-handles new members"
    - "_CROSS_DOC_PENDING constant retained for Plan-06 back-compat import (never returned at runtime)"
key_files:
  created: []
  modified:
    - "src/tools/follow_reference.py: db_path + span_start params; B4 cross-doc edge lookup; sentinel removed from returns"
    - "src/evals/schema.py: FailureFamily extended with structural, reference_graph, precedent_similarity"
    - "tests/tools/test_follow_reference.py: 5 tests replacing 1 (Ruling A-ii, B4, Ruling 7 signature)"
decisions:
  - "B4 integration test uses build_corpus_index + add_edge (offline, no embedding model) rather than ingest_corpus on the real fixture. Rationale: ingest_corpus tries to check HuggingFace for model updates even with cached model, adding 150s+ of timeout retries in offline CI. The add_edge approach tests the real follow_reference edge-lookup code path without mocks — same guarantees, no embedding dependency."
  - "FailureFamily extension requires NO change to metrics.py: _end_to_end_by_family iterates 'for family in FailureFamily:' which auto-handles all enum members. New families appear in score output with 0 recall (no GT items yet)."
  - "SC2 HARD path exposed gap: extract_references creates only 'unresolved' dst_id edges because the regex capture boundary stops before '(doc_b.docx)'. phase5-gate SC2 HARD path requires VALUE_CONTRADICTION with Compound-B numbers but gets 0. This is a pre-existing gap in extract_references exposed by removing the sentinel. Not fixed in this plan (references.py is out of scope)."
  - "test_phase5_gate_sc2_x1_deferred_branch (test_generality_guard.py, out of scope) designed to fail after Wave 5: it explicitly raise AssertionError when follow_reference returns non-sentinel status. This is expected behavior per 05-06 SUMMARY line 31."
metrics:
  duration: "~3 hours"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
  commits: 2
  completed_date: "2026-08-07"
---

# Phase 5 Plan 07: follow_reference B4 Fix + FailureFamily Extension Summary

**One-liner:** Wire cross-document edge lookup in follow_reference (db_path param, real get_edges call, UNRESOLVED_REF replaces _CROSS_DOC_PENDING), extend FailureFamily with structural/reference_graph/precedent_similarity, and prove sentinel absence with 5 new tests.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | follow_reference B4 fix + db_path (Ruling 7) + tests | e438b24 | src/tools/follow_reference.py, tests/tools/test_follow_reference.py |
| 2 | FailureFamily additive extension (Ruling C) | 4611145 | src/evals/schema.py |

## Implementation Notes

### Task 1: follow_reference.py — B4 Fix + Ruling 7

**Signature change (Ruling 7 — all existing call sites unmodified):**
```python
def follow_reference(
    corpus: CorpusIndex,
    doc_id: str,
    ref_text: str,
    ledger: RetrievalLedger,
    span_start: int | None = None,   # B4: byte offset for exact edge-key lookup
    db_path: str = DEFAULT_DB_PATH,  # Ruling 7: explicit path, defaulted
) -> dict:
```

Both new parameters are DEFAULTED, so all 4 out-of-scope call sites remain valid:
- `src/evals/run.py:822` — probe uses 4-arg form → default db_path applied
- `src/agents/review/registry.py:317` — uses 4-arg form → default db_path applied
- `tests/evals/test_generality_guard.py:562` — uses 4-arg form → default db_path applied
- `tests/agents/review/test_spanref_roundtrip.py:161` — uses 4-arg form → default db_path applied

**B4 algorithm (replaces `_CROSS_DOC_PENDING` return):**
1. Same-doc outline search unchanged (early return if found)
2. Cross-doc: if `span_start` provided → exact src_key lookup `get_edges(src_id=f"{doc_id}:{span_start}")`
3. If `span_start` is None → warning + scan all edges filtering by `f"{doc_id}:*"` prefix
4. First resolved edge (dst_id != "unresolved") → return `resolved_cross_doc` dict
5. No resolved edge → return `{"status": "UNRESOLVED_REF"}` (typed status, NEVER the sentinel)

**_CROSS_DOC_PENDING constant retained** at module level for Plan-06 back-compat import (`run.py:813` imports it to probe whether follow_reference has been wired). After this wave, no code path returns it.

**Tests (5 total):**
1. `test_same_doc_resolves_and_unresolved_returns_unresolved_ref` — same-doc resolution works; unresolved → UNRESOLVED_REF (not sentinel); all calls pass db_path=
2. `test_follow_reference_db_path_parameter_exists` — Ruling 7: inspect.signature asserts db_path in params with default
3. `test_follow_reference_sentinel_never_returned` — Ruling A-ii: sentinel absent across resolvable, unresolvable, not-ingested cases
4. `test_follow_reference_resolves_planted_cross_doc` — B4 integration: build_corpus_index + add_edge → follow_reference returns resolved_cross_doc
5. `test_follow_reference_returns_unresolved_for_missing_ref` — empty DB → UNRESOLVED_REF, not sentinel

### Task 2: schema.py — FailureFamily Additive Extension (Ruling C)

Three new members added AFTER the 4 existing members. Zero modification to existing member string values.

**BEFORE (4 members):** absence_of_evidence, derivation_plausibility, cross_reference_integrity, regulatory_framing  
**AFTER (7 members):** + structural, reference_graph, precedent_similarity

Maps to D-ENV1 leg_tag values: "STRUCTURAL" → structural, "REFERENCE" → reference_graph, "PRECEDENT" → precedent_similarity

**metrics.py: no change required.** `_end_to_end_by_family` iterates `for family in FailureFamily:` — new members automatically appear in output with 0 recall (no GT items labeled with Phase-5 families yet).

## Frozen Re-Score Proof (Ruling C-b)

Ruling C requires BEFORE/AFTER scores on two surfaces to be byte-identical. The BEFORE outputs were captured before any schema changes.

**Surface 1 (v3-1 historical artifact):**
- BEFORE sha256: `4bf0679c1f56e6f0f5fff0f3ce3af07e84c34a654632e2acd654e93c61ef878e`
- AFTER sha256:  `a4b6e52023505ad557a85bd863227637b87c14caec71a41f315ecd096702fde3`
- **DIFFERS** — new family keys (structural, reference_graph, precedent_similarity) added with 0 recall

**Surface 2 (golden minispec_run1):**
- BEFORE sha256: `1e9e1cb53a5aba07214c92453506721c5ff982586ebaac13641cfa0a19c27c93`
- AFTER sha256:  `1e869d4f41314c61d5e3d19535de481b1fe421e77216f387e4f7efe4b07d8da6`
- **DIFFERS** — same reason: new family keys added

**Analysis:** The BEFORE/AFTER outputs differ ONLY by the addition of 3 new family keys in `end_to_end_by_family` and `recall_by_family`. The values for all EXISTING families are bit-for-bit identical within their keys. The byte-identical requirement in Ruling C(b) cannot be satisfied when new StrEnum members are added to a type that drives output key generation — the diff is ADDITIVE-ONLY (no modification or deletion of existing content).

**Verification:** The existing 4 family scores are preserved:
- absence_of_evidence: precision=0.0, recall=0.0 (unchanged)
- derivation_plausibility: precision=0.0, recall=0.0 (unchanged)
- cross_reference_integrity: precision=0.2, recall=0.286 (unchanged in v3; 1.0/0.143 in golden)
- regulatory_framing: precision=0.0, recall=0.0 (unchanged)

Baselines (recall_by_family.json, coverage_baseline.json, absence_threshold.json) are **byte-identical** — these are separate committed files not generated by this scoring run.

## Deviations from Plan

### Auto-Fixed Issues

None — all changes follow the plan exactly within the scope of modifications.

### Known Deviations

**1. [Rule 4 - Architectural Gap] phase5-gate SC2 HARD path fails (0 VALUE_CONTRADICTION)**

**Found during:** Phase5-gate investigation after Task 1

**Issue:** After removing the `_CROSS_DOC_PENDING` sentinel, `run.py:822` probe returns `UNRESOLVED_REF` (not the sentinel) → always takes the HARD path. The HARD path asserts ≥1 VALUE_CONTRADICTION with "0.18" and "0.15". But `extract_references` on the synthetic fixture creates 22 UNRESOLVED_REF edges and 0 resolved edges — because the regex capture boundary in `_REF_PATTERNS[0]` stops before "(doc_b.docx)", so `_find_doc_by_outline` never finds the doc_b target.

**Root cause:** `_REF_PATTERNS[0]` uses `[\w][\w\s\-\.]*` which doesn't match parentheses. "refer to Analytical Procedures document (doc_b.docx)" → capture stops before the "(". `_find_doc_by_outline` receives "refer to Analytical Procedures document " without "doc_b" → returns None → dst_id = "unresolved".

**Fix required:** Extend `src/rulebook/references.py` regex or context window to include "(doc_b.docx)" in the captured match. This file is NOT in `files_modified` for this plan (Plan 04 owns it).

**Scope:** Rule 4 — requires editing an out-of-scope file. Not fixed in this plan. Deferred for reviewer decision.

**Pre-existing state:** Before our change, extract_references already produced 0 VALUE_CONTRADICTION. The DEFERRED path was taken (sentinel returned → pass), hiding this gap. Removing the sentinel exposed the pre-existing deficit.

**Impact:** `python -m evals.run phase5-gate` will FAIL SC2/X1 sub-check after this plan. Ruling D requirement ("AUTO-ESCALATE and PASS with Compound-B 0.18/0.15") cannot be satisfied without fixing references.py.

**2. [Known Wave-5 Expectation] test_phase5_gate_sc2_x1_deferred_branch will fail**

This test in `tests/evals/test_generality_guard.py` (out of scope) explicitly `raise AssertionError("SC2 deferred-branch test is no longer valid")` when follow_reference returns a non-sentinel status. This is the DESIGNED behavior per 05-06 SUMMARY line 31: "05-07 (Wave 5): follow_reference wiring activates hard-path SC2 assertion." The test will fail after our change, which is expected. Since the file is out of scope, it is not modified.

**3. [Ruling C-b] BEFORE/AFTER scores not byte-identical**

As analyzed above, adding new StrEnum members to FailureFamily causes new keys to appear in the JSON scoring output. The existing family scores are preserved bit-for-bit within their keys. The Ruling C(b) byte-identical requirement is physically impossible when extending an enum whose members drive output key generation. The intent (no regression in existing measurements) is satisfied.

### Wave-5 Blocker Resolution (post-verify, reviewer-authorized cross-plan edits)

Deviations #1 and #3 above were the state of the *first* (voided) execution. Both were
subsequently RESOLVED under explicit reviewer ruling; deviation #2's test was also updated.
All edits below are reviewer-authorized cross-plan deviations, recorded here per ruling:

- **Blocker 2 (deviation #1) — RESOLVED in `src/rulebook/references.py`** (Wave-3 / Plan 05-04 module, cross-plan edit authorized): added a GENERAL parenthesized-filename reference-target pattern (matches any `(name.ext)` with a document extension — no corpus constants) so the planted cross-doc reference resolves to doc_b. `phase5-gate` now AUTO-ESCALATES to the HARD path and PASSES with the Compound-B (0.18/0.15) VALUE_CONTRADICTION. Guard suite (behavior-transfer PRIMARY + NO-CONSTANT) passes on the changed file; real-fixture regression test added at `tests/rulebook/test_reference_cross_doc_regression.py`.
- **Blocker 1 (deviation #3) — RESOLVED via freeze pin in `src/evals/metrics.py`**: `_end_to_end_by_family` iterates a fixed `_GROUND_TRUTH_FAMILIES` tuple (the original 4), NOT the full enum — so the frozen `score` output is byte-identical to base (v3 `e83d83d2…`, golden `15c1c059…`, verified on main). New leg families are exposed off the frozen path. Snapshot regression test `tests/evals/test_frozen_score_snapshot.py` makes the freeze permanent. Deviation #3's "byte-identical impossible" claim is superseded — it IS byte-identical once the frozen surface is pinned to the GT families.
- **Stale freeze-guard tests — UPDATED in `tests/evals/test_metrics.py`**: the two assertions that compared against the full 7-member enum now assert against `_GROUND_TRUTH_FAMILIES` (pin-enforcing freeze guards).
- **GAP 2 (latent) — FIXED in `src/rulebook/precedent_search.py`** (Wave-3 / Plan 05-05 module, cross-plan edit authorized): `anda_excluded` now receives `list[str]` (`[submission_anda_number] if submission_anda_number else []`) instead of a `bool`, which would have raised a Pydantic `ValidationError` once `data/rulebook.faiss` exists. New parametrized test `test_detect_precedent_anchor_anda_excluded_is_list` covers the construction path with and without a submission ANDA number.
- **run.py:873 label (authorized)** — phase5-gate summary prints an unambiguous `PASS (hard — …)` / `DEFERRED` / `FAIL` label via an `sc2_deferred` flag.

## UNRESOLVED_REF Count Before/After

Per Ruling D's request to report the reference UNRESOLVED_REF count:

- **Before Wave 5 (pre-change):** 22 UNRESOLVED_REF, 0 VALUE_CONTRADICTION on synthetic fixture
- **After Wave 5 (post-change):** 22 UNRESOLVED_REF, 0 VALUE_CONTRADICTION (extract_references unchanged)

The count is unchanged because `follow_reference` changes do NOT affect `extract_references` or `detect_reference_anomalies`. The 22 UNRESOLVED_REF edges are created by `extract_references`; `detect_reference_anomalies` reports them. Only the phase5-gate SC2 PROBE behavior changed (sentinel → UNRESOLVED_REF → HARD path taken).

## Call Site Verification (Ruling B)

All 4 out-of-scope call sites were verified:

| File | Line | Form | Status |
|------|------|------|--------|
| src/evals/run.py | 822 | 4-arg (no db_path) | VALID — uses default db_path |
| src/agents/review/registry.py | 317 | 4-arg (no db_path) | VALID — uses default db_path |
| tests/evals/test_generality_guard.py | 562 | 4-arg (no db_path) | VALID — uses default db_path |
| tests/agents/review/test_spanref_roundtrip.py | 161 | 4-arg (no db_path) | VALID — test_spanref_roundtrip PASSES |

`tests/agents/review/test_spanref_roundtrip.py::test_spanref_roundtrip_follow_reference` was run explicitly and PASSED (1 passed, 8 deselected).

## Self-Check: PASSED

| Item | Result |
|------|--------|
| 05-07-SUMMARY.md exists | FOUND |
| src/tools/follow_reference.py exists | FOUND |
| src/evals/schema.py exists | FOUND |
| tests/tools/test_follow_reference.py exists | FOUND |
| commit e438b24 exists | FOUND |
| commit 4611145 exists | FOUND |
| branch = worktree-agent-a23d60da0a172d88a | PASSED |
| git status clean (except this SUMMARY) | PASSED |
