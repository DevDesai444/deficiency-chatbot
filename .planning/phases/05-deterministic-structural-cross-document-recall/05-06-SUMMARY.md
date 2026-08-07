---
phase: "05"
plan: "06"
subsystem: "anti-overfitting-guard + phase5-gate-cli"
tags:
  - RECALL-05
  - D-GRD2
  - D-GRD3
  - Ruling4
  - Ruling8
  - SC2-PATH-B
  - B3-fix
  - Pitfall6
  - Ruling9-threshold-loader
dependency_graph:
  requires:
    - "05-01: synthetic fixture_a (src/evals/dataset/synthetic_fixture/) committed"
    - "05-01: fixture_b (tests/fixtures/synthetic_submission_b/) committed"
    - "05-03: src/rulebook/structural.py (detect_structural_inconsistencies)"
    - "05-04: src/rulebook/references.py (extract_references, detect_reference_anomalies)"
    - "05-05: src/rulebook/precedent_search.py (detect_precedent_candidates)"
    - "05-01: src/rulebook/guard_vocab.py (AGGREGATE_LEXICON, REFERENCE_CUE_WORDS)"
    - "05-01: src/tools/follow_reference.py (_CROSS_DOC_PENDING stub)"
    - "src/evals/run.py: cmd_absence_gate (existing Phase 4 gate, referenced by phase5-gate)"
  provides:
    - "tests/evals/test_generality_guard.py: PRIMARY guard (SAME-LOGIC x2, THRESHOLD-TRANSFER B3, RENAME-INVARIANCE)"
    - "tests/evals/test_generality_guard.py: SECONDARY tripwires (NO-CONSTANT parametrized x3, guard_vocab)"
    - "tests/evals/test_generality_guard.py: SC2/X1 state-aware assertion (deferred + hard-path structure)"
    - "src/evals/run.py: structural-gate, reference-gate, precedent-gate, phase5-gate, deterministic-recall-gate"
  affects:
    - "05-07 (Wave 5): follow_reference wiring activates hard-path SC2 assertion in phase5-gate and test"
    - "Phase 7: UNRESOLVED_REF volume (~22) is a precision signal for Phase-7 verifier handoff"
tech_stack:
  added: []
  patterns:
    - "PRIMARY guard before SECONDARY (Ruling 8 hierarchy): test order in file enforces the guard contract"
    - "_has_inline_ctd_literal: strips re.compile() contexts before CTD scan (Pitfall 6 exemption)"
    - "_inline_float_offenders: strips docstrings + comments + re.compile + _load_precedent_threshold body (Ruling 9)"
    - "SC2 PATH B state-aware: phase5-gate probes follow_reference status; LOUD WARN when stubbed; hard-assert post-Wave-5"
    - "precedent-gate Ruling 8: structured-skip (exit 0) when FAISS absent; hard-fail when FAISS present + 0 findings"
    - "run.py ADDITIVE-ONLY: 5 new cmd_* functions + subparser registrations appended; 7 existing cmd_* untouched"
key_files:
  created: []
  modified:
    - "tests/evals/test_generality_guard.py: PRIMARY guard x4 + SECONDARY tripwires x5 + SC2/X1 assertion x2 appended (additive only)"
    - "src/evals/run.py: cmd_structural_gate, cmd_reference_gate, cmd_precedent_gate, cmd_phase5_gate, cmd_deterministic_recall_gate appended; build_parser extended with 5 new subcommands (additive only)"
decisions:
  - "SC2 PATH B mandatory (binding_reviewer_addition_SC2): reference-gate hard-fails on 0 findings (currently ~22 UNRESOLVED_REF passes); phase5-gate auto-escalates to hard VALUE_CONTRADICTION assert once follow_reference is wired"
  - "LOUD WARN instead of silent pass: phase5-gate and test_phase5_gate_sc2_x1_deferred_branch both print explicit WARN line when SC2 X1 catch is deferred — non-silent by design"
  - "_inline_float_offenders strips docstrings and single-line comments before float scan to avoid false positives on example values in docstrings (e.g., structural.py line 33 'round(0.104, 2) == 0.10' is documentation, not a threshold)"
  - "Both SC2 test functions present: deferred-branch (passes today) + hard-path logic (structure validated, fires post-Wave-5) — no pytest.skip in either"
metrics:
  duration: "~60 minutes"
  tasks_completed: 2
  commits:
    - "bdda1ad: feat(05-06): add Phase 5 anti-overfitting guard extension + all gate CLI wiring"
  files_modified: 2
  lines_added: 797
---

# Phase 5 Plan 06: Anti-Overfitting Guard Extension + Phase 5 Gate CLI Summary

**One-liner:** PRIMARY behavior-transfer guard (SAME-LOGIC x2 + real THRESHOLD-TRANSFER on fixture_b dissolution domain + RENAME-INVARIANCE) plus all five Phase 5 CLI gates in run.py — structural-gate, reference-gate, precedent-gate (Ruling 8 hard-fail/skip), phase5-gate (SC2 state-aware), deterministic-recall-gate.

## What Was Built

### Task 1: test_generality_guard.py Extension (Additive Only)

**New constants and helpers (after existing code):**
- `_STRUCTURAL_SOURCE`, `_REFERENCES_SOURCE`, `_PRECEDENT_SOURCE` — source paths for SECONDARY scan
- `_SYNTHETIC_FIXTURE_DIR`, `_SYNTHETIC_FIXTURE_B_DIR` — fixture path constants (B3 fix)
- `_has_inline_ctd_literal(source)` — strips `re.compile()` contexts before CTD scan (Pitfall 6 exemption)
- `_inline_float_offenders(source, allowed)` — strips docstrings + comments + re.compile + threshold-loader body before float scan (Ruling 9 + docstring-example exemption)

**PRIMARY guard tests (Ruling 8 — appear before SECONDARY, no pytest.skip):**
1. `test_same_logic_structural_on_synthetic` — detect_structural_inconsistencies on fixture_a, assert >= 1 structural_anchor fault
2. `test_same_logic_reference_on_synthetic` — extract_references + detect_reference_anomalies on fixture_a, assert >= 1 reference_anchor fault
3. `test_threshold_transfer_structural_fixture_b` (B3 fix) — structural detection on BOTH fixture_a AND fixture_b (dissolution domain: different compound names, different values, different vocabulary); asserts >= 1 fault on each; proves structural logic is not fitted to impurity/CMC vocabulary
4. `test_rename_invariance_structural` — shutil.copytree fixture_a to renamed dir; assert same fault count; content-derived, not folder-derived

**SECONDARY tripwire tests (Ruling 8 — appear after PRIMARY):**
5. `test_new_modules_embed_no_corpus_constant[structural]` — source scan of structural.py
6. `test_new_modules_embed_no_corpus_constant[references]` — source scan of references.py (Pitfall 6: CTD inside re.compile exempt)
7. `test_new_modules_embed_no_corpus_constant[precedent_search]` — source scan of precedent_search.py (Ruling 9: threshold-loader body exempt)
8. `test_guard_vocab_contains_no_corpus_token` — AGGREGATE_LEXICON + REFERENCE_CUE_WORDS contain no corpus-specific tokens

**SC2/X1 state-aware assertion tests (binding_reviewer_addition_SC2):**
9. `test_phase5_gate_sc2_x1_deferred_branch` — validates deferred path: follow_reference stubbed → LOUD WARN + exit 0
10. `test_phase5_gate_sc2_x1_hard_path_logic` — validates hard-path assertion structure: if VALUE_CONTRADICTION faults exist, enforces 0.18 and 0.15 in details

### Task 2: run.py Gate CLI (Additive Only — Ruling 4)

All five Phase 5 gate subcommands appended to run.py; existing 7 subcommands (`score`, `gate`, `run`, `agent-run`, `retrieval-gate`, `coverage-gate`, `absence-gate`) untouched byte-for-byte:

**`structural-gate`** (`cmd_structural_gate`): Ingests synthetic fixture_a, runs detect_structural_inconsistencies, hard-fails (return 1) on 0 structural findings.

**`reference-gate`** (`cmd_reference_gate`): Degraded per SC2 PATH B — ingests fixture_a, runs extract_references + detect_reference_anomalies, hard-fails on 0 reference findings. Currently yields ~22 UNRESOLVED_REF (passes degraded).

**`precedent-gate`** (`cmd_precedent_gate`): Ruling 8 hard-fail/skip sentinel:
- `data/rulebook.faiss` absent → structured skip (exit 0 + SKIP message), NOT an error
- `data/rulebook.faiss` present → hard-fails on 0 precedent candidates

**`phase5-gate`** (`cmd_phase5_gate`): Sequential dispatch to absence-gate + structural-gate + reference-gate + precedent-gate, plus SC2/X1 state-aware probe:
- Calls `follow_reference` on the 3-doc fixture cross-doc reference (doc_a → doc_b)
- If stubbed (`_CROSS_DOC_PENDING`): LOUD WARN + pass degraded (exit 0 from SC2 sub-check)
- If resolved cross-doc (post-Wave-5): HARD-ASSERT >= 1 VALUE_CONTRADICTION with Compound-B numbers (0.18 and 0.15); return 1 if absent

**`deterministic-recall-gate`** (`cmd_deterministic_recall_gate`): Three-leg recall report (RECALL-02/03/04 only, no absence-gate); hard-fails on structural or reference 0 findings; reports precedent without hard-fail (FAISS dependency).

## Gate Verification Results

| Gate | Result | Note |
|------|--------|------|
| structural-gate | PASS | 2 structural faults (SUM on Total Impurities, MAX on Maximum Measured Value) |
| reference-gate | PASS | 22 reference faults (UNRESOLVED_REF — degraded per SC2 PATH B) |
| precedent-gate | SKIP (exit 0) | data/rulebook.faiss absent — structured skip, not error |
| phase5-gate | PASS | All gates pass; SC2 emits LOUD WARN (deferred to Wave 5) |
| deterministic-recall-gate | PASS | structural: 2, reference: 22, precedent: SKIP |

## Test Verification Results

| Test Group | Tests | Result |
|------------|-------|--------|
| SECONDARY tripwires (no ingest) | 5 (3 parametrized + guard_vocab) | 5 passed in 0.86s |
| PRIMARY guard (fixture ingest required) | 4 | validated via direct Python invocation |
| SC2/X1 state-aware | 2 | deferred-branch validated; hard-path structure present |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Docstring example exemption in _inline_float_offenders**
- **Found during:** Task 1 SECONDARY scan validation
- **Issue:** `_inline_float_offenders` as specified in the plan only stripped `re.compile()` contexts and the `_load_precedent_threshold` body. When run against `structural.py`, it flagged documented examples in docstrings (e.g., `round(0.104, 2) == 0.10` on line 33) as "inline float threshold literals" — false positives.
- **Fix:** Extended `_inline_float_offenders` to also strip Python triple-quoted docstrings and single-line comments before scanning. Floats in documentation (narrative text explaining algorithm behavior) are not executable threshold constants. The guard targets code-body literals only.
- **Files modified:** `tests/evals/test_generality_guard.py` (helper function)
- **Commit:** bdda1ad
- **Assessment:** This is a correctness fix (false positives would make the SECONDARY tripwire non-trustworthy). The stripping of docstrings is analogous to the existing re.compile() stripping — both remove non-executable string content before scanning for literals.

### SC2 PATH B Implementation (binding_reviewer_addition_SC2)

The reviewer mandated PATH B (state-aware SC2 assertion) rather than the original plan's simpler reference-gate design. This was implemented as specified:
- `reference-gate` hard-fails on 0 findings (currently passes with ~22 UNRESOLVED_REF)
- `phase5-gate` includes SC2/X1 probe that auto-escalates once `follow_reference` is wired
- Two new test functions cover both branches (deferred + hard-path)

## Phase-7 Handoff Precision Note

`detect_reference_anomalies` on the 3-doc committed fixture_a yields **~22 UNRESOLVED_REF / 0 VALUE_CONTRADICTION** pre-Plan-07 (Wave 4 baseline). This is a precision signal for the Phase-7 verifier handoff:
- The high UNRESOLVED_REF volume is expected — most textual references in the synthetic fixture cannot be resolved to known doc IDs, so they correctly register as UNRESOLVED_REF
- VALUE_CONTRADICTION count = 0 because `follow_reference` is still stubbed (`_CROSS_DOC_PENDING`); the X1 planted violation (Compound B 0.18% vs NMT 0.15%) cannot be caught until cross-doc resolution is wired in Wave 5 (Plan 07)
- Many UNRESOLVED_REF entries will resolve or be pruned once `follow_reference` lands: cross-doc edges that currently resolve to "unresolved" will either become resolved (if the target doc is found) or become ABSENT_TARGET / VALUE_CONTRADICTION

The ~22 UNRESOLVED_REF is **not a precision problem** at this stage — it reflects the honest state of the reference graph before Plan 07's cross-doc resolution. Phase-7 verifier should expect this number to decrease significantly after Wave 5.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| tests/evals/test_generality_guard.py exists | FOUND |
| src/evals/run.py exists | FOUND |
| 05-06-SUMMARY.md exists | FOUND |
| commit bdda1ad exists | FOUND |
| 12 total subcommands (7 existing + 5 new) | FOUND |
| All 5 new cmd_* functions importable | FOUND |
| Existing 7 cmd_* functions untouched | FOUND |
| SECONDARY tripwire tests: 5 passed, 0.86s | PASSED |
| precedent-gate: SKIP (no FAISS) | PASSED |
