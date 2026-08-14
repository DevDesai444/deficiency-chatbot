---
phase: 07-multi-agent-verification-interpretive-tail
plan: 01
subsystem: verification-scaffold
tags: [test-scaffold, precision-fixture, baseline, red-stubs, wave-0]
requires:
  - src/llm/client.ChatTurn
  - src/schemas/faults.Fault
  - src/schemas/llm.VERDICT
  - src/ingest/anchors.open_span
  - src/config.VERIFIER_FLEET
  - src/config.MODEL_LINEAGE
provides:
  - tests/verify (offline verifier test package + ScriptedFleetClient double)
  - tests/verify/fixtures/labeled_fp_candidates.json (measurable precision signal)
  - src/evals/baseline/phase5_f1_baseline.json (falsifiable Phase-5 F1 floor)
  - 9 guarded RED stubs for VERIFY-01..04 + grounding + tail
affects:
  - Plan 07-02 (consensus/panel/orchestrator turn stubs green)
  - Plan 07-03 (coverage/grounding/tail turn stubs green)
  - Plan 07-04 (report-assembly filter + F1-gate recapture of baseline provenance)
tech-stack:
  added: []
  patterns:
    - ScriptedFleetClient mirrors Phase-3 ScriptedChatClient (deepcopy discipline, per-key script)
    - grounding substrate via production normalize()/mint_span (open_span round-trips)
    - RED stubs guarded by pytest.importorskip on verify.<mod> (skip == present-and-not-yet-green)
key-files:
  created:
    - tests/verify/__init__.py
    - tests/verify/conftest.py
    - tests/verify/fixtures/labeled_fp_candidates.json
    - tests/verify/fixtures/README.md
    - tests/verify/test_invariant_no_drop.py
    - tests/verify/test_verifier_readonly.py
    - tests/verify/test_orchestrator_consolidate.py
    - tests/verify/test_coverage_report.py
    - tests/verify/test_decorrelation.py
    - tests/verify/test_panel_family.py
    - tests/verify/test_consensus.py
    - tests/verify/test_grounding_reresolve.py
    - tests/verify/test_tail_gate.py
    - src/evals/baseline/phase5_f1_baseline.json
  modified: []
decisions:
  - "Phase-5 F1 baseline AUTHORED with provenance=authored-from-phase5-close-numbers (recall 6/32=0.1875, ~102-fp over-emit -> precision 0.0556, f1 0.0857). Recapture deferred to Plan 04 T3 in the MAIN tree — scoring the curated golden mvr1381_run3.json via `evals.run score` yields the OLD Phase-3 numbers (recall 0.071), NOT the Phase-5 deterministic-leg engine output, so recapturing it here would be dishonest. The Gap-3 provenance seam guarantees a real-corpus gate hard-fails on authored-* before it is trusted."
metrics:
  duration: ~30min (+ 2x 12min suite runs)
  completed: 2026-08-13
---

# Phase 7 Plan 01: Verification Test Scaffold + Precision Fixture + Falsifiable Baseline Summary

Minted the offline test scaffold (tests/verify/ + ScriptedFleetClient double), a balanced labeled
false-positive fixture so end-to-end precision is measurable (P6 had only 2/115), a committed
Phase-5 F1/precision baseline carrying an honest falsifiable `provenance` field, and 9 guarded RED
test stubs for VERIFY-01..04 + grounding + tail that Waves 1-3 turn green. No src/verify/ production
code was written.

## What was built

- **Task 1 — tests/verify package + ScriptedFleetClient (d64b42c).** `tests/verify/__init__.py` +
  `conftest.py`. `ScriptedFleetClient` is a deterministic per-model stand-in for
  `chat_completion_tools` with a `seen_messages_by_model` / `seen_tools_by_model` deepcopy seam (the
  decorrelation + write-disabled assertion surface). ChatTurn builders (`make_verdict_turn` emits a
  full 4-field VERDICT payload — verdict/confidence/rationale/grounding_span; `make_parse_fail_turn`).
  Candidate builders (deterministic/absence/tail + labeled FP/TP). A byte-exact grounding substrate
  via production `normalize()` + `mint_span` so `open_span` round-trips. No src/verify import.

- **Task 2 — labeled FP fixture + Phase-5 F1 baseline (2908a84).**
  `tests/verify/fixtures/labeled_fp_candidates.json`: 6 FP + 6 TP across ABSENCE/STRUCTURAL/REFERENCE,
  all pre-verification `confidence_tier:"full"`, each Fault-valid and re-openable, each with a
  STRUCTURE-based `why` rationale (+ a README) so the RECALL-05 generality guard cannot flag a
  corpus-specific constant. `src/evals/baseline/phase5_f1_baseline.json` with precision/recall/f1 and
  a mandatory honest `provenance` field. `beta_recall_baseline.json` byte-unchanged.

- **Task 3 — 9 guarded RED stubs (5ffd72f).** One test file per Test-Map row, each referencing its
  VERIFY req id, each with a real assertion body (not `pass`), each guarded by
  `pytest.importorskip("verify.<mod>")` so the suite is green now and every stub flips to a live
  assertion by a one-line module landing in a later wave.

## Verification

- `python3 -m pytest tests/verify/ -q` → 12 skipped, 0 failures, 0 errors (guarded RED stubs).
- No-endpoint full suite `python3 -m pytest -q -m "not integration and not slow"` →
  **691 passed, 23 skipped, 13 deselected, 0 failed, 0 errors** (scaffolding imports; non-stub tests pass).
- Fixture: 6 FP + 6 TP across 3 legs, all full-tier (asserted).
- `phase5_f1_baseline.json` has end_to_end{precision,recall,f1,tp,fp,fn} + provenance; `beta_recall_baseline.json` unchanged.

## RED stubs (present + guarded-skip as intended)

| Test file | Req | Guarded module |
|-----------|-----|----------------|
| test_invariant_no_drop.py | VERIFY-01 | verify.orchestrator |
| test_verifier_readonly.py | VERIFY-01 | verify.orchestrator |
| test_orchestrator_consolidate.py | VERIFY-02 | verify.orchestrator |
| test_coverage_report.py | VERIFY-02 | verify.coverage |
| test_decorrelation.py | VERIFY-03 | verify.orchestrator |
| test_panel_family.py | VERIFY-03 | verify.panel |
| test_consensus.py | VERIFY-01/03 | verify.consensus |
| test_grounding_reresolve.py | grounding | verify.grounding |
| test_tail_gate.py | VERIFY-04 | verify.tail |

## Deviations from Plan

**1. [Rule 3 — recapture path] Phase-5 F1 baseline authored, not recaptured (documented fallback).**
- Found during: Task 2.
- The plan's recapture branch scores "the frozen Phase-5 golden report". The only frozen golden
  present (`src/evals/dataset/golden/mvr1381_run3.json`) scores at end_to_end recall 0.071 via
  `evals.run score` — the OLD Phase-3 curated-golden numbers, NOT the Phase-5 deterministic-leg engine
  output (recall 6/32=0.1875 per `beta_recall_baseline.json`). Recapturing that golden would produce a
  dishonest baseline. Took the plan's explicit `authored-from-phase5-close-numbers` fallback; the
  mandatory `provenance` field + the Gap-3 hard-fail (Plan 04 T3) keep it falsifiable. No scope dropped.

**2. [note] `make_verdict_turn` emits all four VERDICT fields.** The plan's simplified interface block
listed only `verdict` + `grounding_span`; the real `src/schemas/llm.VERDICT` requires
`confidence` + `rationale` too. The builder emits all four so a scripted verdict validates (EXTEND, not redefine).

## Known Stubs

The 9 test files are intentional RED stubs (guarded by `importorskip`), not code stubs — they are the
deliverable of a Wave-0 scaffold plan and flip to live assertions as `src/verify/` modules land in
Plans 02-04. No production stub code was introduced.

## Self-Check: PASSED
