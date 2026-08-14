---
phase: 07-multi-agent-verification-interpretive-tail
plan: 04
subsystem: verify
tags: [interpretive-tail, driver-seam, verify-f1-gate, decorrelation, zero-tp-loss, gap-2, gap-3]
requires:
  - verify.orchestrator.verify_candidates (Plan 03)
  - verify.assemble.assemble_scored_report / downgraded_dedup_keys (Plan 03)
  - verify.panel.panel_for / verify.orchestrator.family_of (Plan 03)
  - agents.review.loop.run_review (Phase 3)
provides:
  - verify.tail.run_interpretive_tail (VERIFY-04 producer)
  - verify.driver.verify_and_assemble (Gap-2 single seam)
  - evals.run.cmd_verify_f1_gate + `verify-f1` subcommand (phase gate; Gap 1/2/3)
affects:
  - src/evals/run.py (additive: new subcommand + one baseline path constant)
tech-stack:
  added: []
  patterns:
    - "reuse-verbatim: interpretive tail drives the existing run_review loop; no new agent loop"
    - "single-seam: one verify_candidates fan-out for Phase-5 + tail (grep-verified == 1)"
    - "presence-keyed zero-TP-loss union: report.faults + retained DOWNGRADEd faults"
    - "authored-* provenance hard-fail on a real corpus run (falsifiability tripwire)"
key-files:
  created:
    - src/verify/tail.py
    - src/verify/driver.py
    - tests/verify/test_verify_driver.py
    - tests/verify/test_verify_f1_gate.py
  modified:
    - tests/verify/test_tail_gate.py
    - src/evals/run.py
decisions:
  - "Tail-gate test rewritten to the Task-1 producer contract (family tag + qwen-excluded panel); the Wave-0 RED stub's run_tail([...]) shape predated the frozen producer/driver split."
  - "Driver matches the REAL verify_candidates(candidates, fleet_client, *, corpus/manifest/ledger, reopen_*) signature, not the plan's illustrative completion=/nt_for= sketch."
  - "verify-f1 real-run zero-TP-loss reconstructs DOWNGRADEd fault objects from the gate's own candidate list (dedup_key ∈ downgraded_dedup_keys), avoiding a second fan-out while scoring the presence-keyed union."
metrics:
  duration_min: 40
  completed: 2026-08-14
  tasks_completed: "3 of 4 (Task 4 = reviewer-run live checkpoint)"
---

# Phase 7 Plan 04: Interpretive Tail + Driver Seam + verify-f1 Gate Summary

Precision-gated interpretive tail (Qwen `run_review` producer) + the single Gap-2 report-assembly
driver + a `verify-f1` phase gate that drives that driver and grades end-to-end F1 vs the frozen
Phase-5 baseline with a zero-TP-loss union and an authored-* real-run hard-fail. Tasks 1-3 complete
and green offline; Task 4 is the reviewer-run MAIN-tree live checkpoint.

## What shipped

- **Task 1 — `src/verify/tail.py` (`run_interpretive_tail`)** — reuses the existing Phase-3
  `run_review` loop on a Qwen-lineage producer under a TIGHT general budget (60k tok / 300s / 16
  turns, overridable). Each finding is already `emit_finding` byte-exact grounded; the tail only
  TAGS it `source="reviewer:qwen:<detail>"` so `family_of` returns `"qwen"` and `panel_for("qwen")`
  excludes the Qwen family (VERIFY-03 decorrelation). No new loop; no fan-out (grep-verified).
- **Task 2 — `src/verify/driver.py` (`verify_and_assemble`)** — combines Phase-5 candidates + tail
  candidates into ONE list, runs BOTH producers through EXACTLY ONE `verify_candidates` fan-out
  (grep `== 1`), then `assemble_scored_report` (KEEP-tier only). A DOWNGRADEd FP leaves
  `report.faults`; a DOWNGRADEd TP is retained in `coverage.reviewed_downgrade`. `enable_tail=False`
  is the Gap-4 escape hatch.
- **Task 3 — `evals.run.cmd_verify_f1_gate` + `verify-f1` subcommand** — DRIVES
  `verify_and_assemble` (Gap 2), computes end-to-end precision/recall/F1 via the frozen path, PASSES
  iff `F1 >= baseline.f1` AND no baseline-matched TP id is lost. Zero-TP-loss reads `report.faults`
  UNION the retained DOWNGRADEd faults (presence-keyed). Gap 3: authored-* provenance on a real
  corpus run HARD-FAILS (exit 1) with a re-capture directive; structured-skip only when the
  gitignored corpus is genuinely absent. Exposes precision, recall AND f1 for the Task-4 reviewer's
  recall-aware tail decision.

## Verification results (offline)

- `tests/verify/` — **20 passed** (was 13 passed + 1 skipped; `test_tail_gate` now GREEN, plus 2
  driver tests + 4 f1-gate tests). No prior verify test regressed.
- `verify-f1` offline test — **4 passed**: pass / lost-TP-fail / downgraded-TP-retained /
  authored-*-hard-fail. No live corpus call.
- Full no-endpoint suite (`-m "not integration and not slow"`) — **711 passed, 11 skipped, 13
  deselected**. No regression.
- Acceptance greps: `run_interpretive_tail` reuses `run_review` with 0 new loops + 0 `verify_candidates`
  calls; driver has EXACTLY ONE `verify_candidates(` call site (comments excluded); gate greps for
  `verify_and_assemble` + `phase5_f1_baseline` + `provenance` + `downgraded_dedup_keys`;
  `verify-f1 --help` exits 0.

## Deviations from Plan

### Auto-fixed / reconciled

**1. [Rule 3 - Blocking] Tail-gate test rewritten to the Task-1 producer contract.**
- **Found during:** Task 1.
- **Issue:** The Wave-0 RED stub asserted `tail.run_tail([candidate], fleet_client=...)` — a
  verify-and-downgrade shape that predates the frozen producer/driver split. Task 1's `<action>`
  specifies a PRODUCER (`run_interpretive_tail`) that emits tagged grounded candidates and does NOT
  fan out; the DOWNGRADE-not-drop path is asserted via the driver (Task 2).
- **Fix:** Rewrote `test_tail_gate.py` to the Task-1 contract exactly as `<action>` prescribes —
  (a) `family_of(candidate) == "qwen"`, (b) `panel_for(family_of(candidate))` excludes qwen — driven
  offline via a scripted `run_review`. The precision gate is NOT weakened: the tail still crosses the
  same consensus verifier, now through the driver's single fan-out.
- **Files:** `tests/verify/test_tail_gate.py`. **Commit:** 6cf9218.

**2. [Rule 3 - Blocking] Driver matches the REAL `verify_candidates` signature.**
- **Found during:** Task 2.
- **Issue:** The plan's illustrative driver signature named `completion=`/`nt_for=` kwargs that the
  Plan-03 `verify_candidates(candidates, fleet_client, *, corpus, manifest, ledger, reopen_*)` does
  not expose.
- **Fix:** `verify_and_assemble` passes the fleet client positionally as `fleet_client` and forwards
  the real `corpus`/`manifest`/`ledger` + `reopen_*` injection seams. Single-fan-out invariant intact.
- **Files:** `src/verify/driver.py`. **Commit:** 675770f.

**3. [Rule 3 - Blocking] verify-f1 real-run zero-TP-loss reconstructs DOWNGRADEd fault objects
   without a second fan-out.**
- **Found during:** Task 3.
- **Issue:** `CoverageReport` stores DOWNGRADEd dedup_keys, not fault objects; the matcher keys on
  evidence anchors, so the zero-TP-loss union needs the DOWNGRADEd faults' text.
- **Fix:** The gate builds the per-doc candidate list itself (to drive the driver), so it recovers
  the DOWNGRADEd faults as `[c for c in candidates if c.dedup_key in downgraded_dedup_keys(coverage)]`
  and scores `report.faults + those` for the presence-keyed union — no extra `verify_candidates` call
  (the driver still owns the single fan-out). Offline path uses `--report` + `--downgraded`.
- **Files:** `src/evals/run.py`, `tests/verify/test_verify_f1_gate.py`. **Commit:** 2ae3c17.

No hard law was weakened: the tail's precision gate, the driver's single fan-out, and the gate's
authored-* hard-fail are all intact and grep/test-verified.

## Task 4 — reviewer-run live checkpoint (READY, NOT run here)

Task 4 (`checkpoint:human-verify`, `autonomous:no`) is the MAIN-tree LIVE gate. It requires the
gitignored eval corpus + live on-prem fleet + `DATABRICKS_HOST`/`DATABRICKS_TOKEN` — a subagent
worktree run is meaningless (MEMORY: beta-recall-gate). It was NOT attempted. Exact reviewer commands
(MAIN tree, corpus present, creds set):

1. `python3 -m pytest tests/verify/ -q` — expect all green.
2. `python3 -m pytest -q` — full no-endpoint suite green (no deterministic-recall regression).
3. **Gap 3 — re-capture the baseline:** run `python3 -m evals.run score` on the frozen Phase-5
   golden report and write `src/evals/baseline/phase5_f1_baseline.json` with
   `"provenance": "recaptured-main-tree"` (confirm aggregate recall ≈ 0.1875 within rounding; if not,
   STOP and report). The committed baseline is still `authored-from-phase5-close-numbers`, so
   `verify-f1` WILL hard-fail a live run until this is done — that is the Gap-3 tripwire working.
4. `python3 -m evals.run beta-recall-gate` — expect PASS (zero baseline-matched TP lost).
5. `python3 -m evals.run verify-f1` — expect `PASS: verify-f1` (end-to-end F1 >= re-captured baseline
   AND zero TP lost). Must hard-fail if the baseline is still authored-* (complete step 3 first).
6. **Gap 4 — recall-aware tail decision:** if step 5 passes with the tail on, also run
   `python3 -m evals.run verify-f1 --no-tail` and compare precision, recall AND f1 (all three are
   printed) plus the count of baseline-unmatched real deficiencies the tail newly recovers. KEEP the
   tail if it recovers >=1 real deficiency without dropping precision below the re-captured baseline;
   DISABLE (`--no-tail`) only if it lowers precision below baseline with no recall gain. General rule
   only — no corpus-specific id may be named as a keep/disable condition.
7. `python3 -m pytest -m integration tests/evals/test_verifier_probe.py` — fleet conformance green;
   confirm no external LLM endpoint was contacted.

Resume signal: type "approved" once the baseline is re-captured (provenance `recaptured-main-tree`)
and `beta-recall-gate` + `verify-f1` both PASS in the MAIN tree, or describe the failure.

## Self-Check: PASSED

- Files: `src/verify/tail.py`, `src/verify/driver.py`, `tests/verify/test_verify_driver.py`,
  `tests/verify/test_verify_f1_gate.py` — all FOUND.
- Commits: 6cf9218, 675770f, 2ae3c17 — all FOUND.
