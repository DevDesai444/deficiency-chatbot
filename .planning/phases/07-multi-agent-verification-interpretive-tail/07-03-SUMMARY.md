---
phase: 07-multi-agent-verification-interpretive-tail
plan: 03
subsystem: verify
tags: [verifier, orchestrator, coverage-report, gap-1-proxy-gate, recall-invariant, decorrelation]
requires:
  - "src/verify/{panel,verifier,consensus,grounding}.py (Plan 07-02 atoms)"
  - "src/tools/{get_section,read_guideline}.py (full re-open)"
  - "src/evals/{match,metrics}.py (FROZEN F1 path — untouched)"
provides:
  - "src/verify/coverage.py — CoverageReport (reviewed_keep/reviewed_downgrade/could_not_locate) + consolidate"
  - "src/verify/orchestrator.py — verify_candidates(...) -> (list[Fault], CoverageReport); family_of"
  - "src/verify/assemble.py — assemble_scored_report + downgraded_dedup_keys (Gap-1 filter)"
affects:
  - "Plan 07-04 (interpretive tail): tags a candidate's Fault.source so family_of returns its family; reads downgraded_dedup_keys for zero-TP-loss"
tech-stack:
  added: []
  patterns:
    - "single consolidation source of truth (verify.coverage.consolidate) re-exported by orchestrator"
    - "two re-open modes: production corpus/manifest/ledger vs. test reopen_* callable injection"
    - "surface-not-existence: a downgrade moves a fault from the ACTIVE scored surface to the coverage audit surface, never deletes it"
key-files:
  created:
    - src/verify/coverage.py
    - src/verify/assemble.py
    - tests/verify/test_scored_report_filter.py
  modified:
    - src/verify/orchestrator.py
    - tests/verify/test_invariant_no_drop.py
decisions:
  - "verify_candidates return type changed from list to (list[Fault], CoverageReport) — only test_invariant_no_drop read the return; updated to the tuple contract per plan."
  - "consolidation lives once in verify.coverage; orchestrator re-exports it (no duplicate grouping logic)."
  - "DOWNGRADE confidence discount is a general documented constant (0.5), never a corpus-derived value."
  - "could_not_locate is NOT a DOWNGRADE: tier stays 'full' so the candidate remains ACTIVE in the scored report."
metrics:
  duration: "~35 min"
  tasks: 3
  files_created: 3
  files_modified: 2
  completed: 2026-08-14
---

# Phase 7 Plan 03: Orchestrator + Coverage + Assemble Summary

Completed the Phase-7 verifier orchestration layer: full per-candidate re-open of source+rule,
decorrelated panel fan-out, the code-gated downgrade-never-drop consensus invariant, an honest
CoverageReport (no positive-pass field), and the Gap-1 report-assembly filter that makes the frozen
F1 path actually see the verifier's precision effect (a DOWNGRADEd FP stops counting as an FP) while
retaining every DOWNGRADEd fault in coverage for zero-TP-loss recall accounting.

## What Was Built

- **src/verify/coverage.py** — `CoverageReport` (reviewed_keep / reviewed_downgrade /
  could_not_locate; deliberately NO positive-pass field) + `consolidate(faults)` grouping by
  `Fault.dedup_key`, merge-never-drop, with an absence-anchor fallback key. Asserts summed group
  member count == input length (T-07-08).
- **src/verify/orchestrator.py** (extended from the Wave-1 seam) — `verify_candidates` now:
  consolidates by dedup_key; re-opens FULL source via `get_section` and FULL rule via
  `read_guideline` (paginated through the oversized handle, never truncated); on ToolRejected/None
  either half → `could_not_locate` and the candidate is KEPT active (tier unchanged); fans out an
  isolated decorrelated panel; applies `consensus`; on DOWNGRADE lowers confidence + sets
  `confidence_tier="low"` IN PLACE and records `{dedup_key, agreeing_verifiers}` in
  `reviewed_downgrade`; returns `(verified_faults, CoverageReport)`. `family_of` accessor defined
  (the Plan-04 wiring point). Output length == unique dedup_key groups — never dropped.
- **src/verify/assemble.py** — `assemble_scored_report(verified_faults, coverage)` surfaces ONLY
  `confidence_tier != "low"` faults in `FaultReport.faults` (KEEP-tier + could-not-locate);
  DOWNGRADEd faults are excluded from `.faults` but retained in `coverage.reviewed_downgrade`.
  `downgraded_dedup_keys(coverage)` is the zero-TP-loss accessor Plan 04 reads. Never deletes a
  fault (β no-drop law: surface, not existence).

## Tests

- **tests/verify/test_coverage_report.py** — FLIPPED GREEN (CoverageReport shape, no compliant field).
- **tests/verify/test_orchestrator_consolidate.py** — GREEN (consolidation merge-never-drop).
- **tests/verify/test_invariant_no_drop.py** — updated to the `(faults, coverage)` contract; asserts
  all-DOWNGRADE keeps every candidate (same object, tier low, lowered confidence) AND records it in
  the coverage audit trail; static drop-verb guard GREEN.
- **tests/verify/test_scored_report_filter.py** — NEW (Gap-1). Proves BOTH halves: a DOWNGRADEd FP
  is NOT counted as an FP by the frozen `_end_to_end` (fp strictly lower than the pre-filter report;
  fp == 0), AND a DOWNGRADEd TP is still retained (its dedup_key in `downgraded_dedup_keys`, credited
  by the report.faults ∪ coverage zero-TP-loss accounting). Second test: a could_not_locate candidate
  stays active in the scored report.

### Test Results

- `tests/verify/` (isolated): **13 passed, 1 skipped** — the only skip is `test_tail_gate`
  (verify.tail lands Plan 04, guarded-skip as designed). Newly GREEN this wave:
  `test_coverage_report`, both `test_scored_report_filter` cases. No previously-green verify test
  regressed.
- Full no-endpoint suite (`-m "not integration and not slow"`): **704 passed, 12 skipped, 0 failed**
  (exit 0). The frozen `src/evals/match.py` + `metrics._end_to_end` path was not touched.

## Hard Laws Upheld

- **RECALL INVARIANT** — no path in orchestrator.py or assemble.py pops/removes/dels a fault
  (grep-verified + static source-scan test); output length == unique dedup_key count; DOWNGRADE only
  lowers confidence/tier.
- **FULL RE-OPEN** — `get_section` (source) + `read_guideline` (rule), paginated via handle, never a
  truncated excerpt.
- **COVERAGE REPORT** — no positive-pass field; reviewed-KEEP, reviewed-DOWNGRADE (with agreeing
  verifiers, kept VISIBLE), could-not-locate (naming the un-located half).
- **ASSEMBLE (Gap-1)** — only KEEP-tier faults reach `FaultReport.faults`; DOWNGRADEd retained in
  coverage; frozen F1 path untouched; filter test asserts BOTH FP-not-counted and TP-retained.
- **REUSE / on-prem / no hardcoded constants** — reuses the Plan-02 atoms + Phase-6 tools verbatim;
  no corpus/rule literal; the only constant is a general 0.5 confidence discount.

## Deviations from Plan

**None affecting invariants.** Two documentation-driven adjustments (both to satisfy the plan's own
static acceptance greps without weakening intent):
- **[Rule 3 - Blocking] coverage.py docstring reworded** to avoid the literal lowercase token
  `compliant` so the `grep -v '^#' | grep -c compliant == 0` acceptance gate passes; meaning
  ("no positive-pass field", ComplianceVerdict discipline) preserved.
- **[Rule 3 - Blocking] orchestrator.py docstring reworded** to avoid the literal substrings
  `.pop(` / `.remove(` / `del faults` so the static drop-verb source-scan test does not false-trip on
  the docstring that describes the guarantee.

## Requirements

- VERIFY-01 (downgrade-never-drop) — realized as the orchestrator code path + `test_invariant_no_drop`.
- VERIFY-02 (fan-out on dedup_key, consolidate/dedup, honest coverage report) — realized.
- VERIFY-03 (decorrelated panel; `family_of` accessor) — realized (panel exclusion via `family_of` +
  `panel_for`; Plan-04 tags the tail candidate's source).

## Self-Check: PASSED

All created/modified files present on disk; all three task commits (e41a3b5, 1b48027, 6645096) present in git history.
