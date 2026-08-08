---
status: testing
phase: 05-deterministic-structural-cross-document-recall
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, 05-06-SUMMARY.md, 05-07-SUMMARY.md]
started: 2026-08-08T18:40:33Z
updated: 2026-08-08T18:40:33Z
---

## Current Test

number: 1
name: Structural leg detects intra-document inconsistencies (RECALL-02 / SC1)
expected: |
  Run: uv run python -m evals.run structural-gate
  Should PASS (exit 0) and report 2 findings with a structural_anchor on the
  synthetic fixture — one SUM-aggregate violation (stated 0.12% vs recomputed
  0.28) and one MAX violation (stated 42.3 vs recomputed 57.8) — each dual-cited
  to two re-openable table cells.
awaiting: user response

## Tests

### 1. Structural leg detects intra-document inconsistencies (RECALL-02 / SC1)
expected: |
  Run: uv run python -m evals.run structural-gate
  PASS (exit 0), 2 findings with structural_anchor on the synthetic fixture
  (SUM violation 0.12% vs 0.28; MAX violation 42.3 vs 57.8), each dual-cited to
  two verbatim re-openable cells.
result: [pending]

### 2. Cross-document reference graph catches X1 end-to-end (RECALL-03 / SC2)
expected: |
  Run: uv run python -m evals.run reference-gate  (and/or phase5-gate)
  reference-gate PASS with reference_anchor findings including VALUE_CONTRADICTION.
  phase5-gate's SC2/X1 hard assertion detects Compound-B 0.18% > NMT 0.15% across
  documents. (Recall-biased: ~17 UNRESOLVED_REF + 13 VALUE_CONTRADICTION on the
  fixture is the sanctioned over-emit handed to Phase 7.)
result: [pending]

### 3. Precedent leg wired; structured-skip when FAISS asset absent (RECALL-04 / SC3)
expected: |
  Run: uv run python -m evals.run precedent-gate
  Structured SKIP (exit 0) because data/rulebook.faiss is not built yet. Code is
  substantive (search_precedents + detect_precedent_candidates + PrecedentAnchor).
  When the FAISS asset lands, the gate flips to hard-fail on 0 findings with no
  code change.
result: [pending]

### 4. Anti-overfitting guard: no submission-specific constant, transfers to held-out corpus (SC4)
expected: |
  Run: uv run pytest tests/evals/test_generality_guard.py -q
  All PRIMARY guards pass unconditionally (SAME-LOGIC on fixture_a x2,
  THRESHOLD-TRANSFER on fixture_b, RENAME-INVARIANCE) plus SECONDARY NO-CONSTANT
  tripwires for structural.py / references.py / precedent_search.py. Proves no
  batch number / doc name / spec value / section path is embedded in check logic.
result: [pending]

### 5. Real-corpus recall holds at 0.1875 with C-01 matched; zero TPs lost (5R / SC5)
expected: |
  Run: uv run python -m evals.run beta-recall-gate
  PASS. Prints matched set and aggregate = 0.1875 (6/32): mvr1381 0.179
  (A-09, A-11, B-01, C-01, C-06) + minispec 0.250 (MS-01). Above the 0.107 golden
  and 0.071 agent baselines; C-01 matched (first time in project history, was
  0.000); no baseline matched id lost. NOTE: structured-SKIP (exit 0) is expected
  if the gitignored local eval corpus is not present in this checkout.
result: [pending]

### 6. Combined Phase 5 gate passes; full test suite green (SC5)
expected: |
  Run: uv run python -m evals.run phase5-gate   then   uv run pytest -q
  phase5-gate PASS (absence + structural + reference + precedent + SC2 probe all
  clear). Full suite: 589 passed, 11 skipped, 0 failed (frozen measurement
  preserved byte-identical; zero true positives lost).
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps

[none yet]
