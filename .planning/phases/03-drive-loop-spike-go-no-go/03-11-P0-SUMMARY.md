# 03-11-P0 Summary: Single-Shot Detector Regression Repair

## Outcome

Completed the blocking P0 repair required by the senior reviewer ruling. `03-12` remains open; no new baseline median is frozen by this task.

The repaired live single-shot detector re-found both protected historical TPs (`C-01`, `C-02`) in 3 of 3 mvr1381 acceptance runs.

## Diagnosis Confirmed

The reviewer-provided census showed the pre-repair redesigned chain was broken, not merely low-recall:

- `planner_workers=10`
- `planner_suspicions=0`
- `workers_emitted=0`
- `worker_failures=0`
- `pre_verify=0`
- `post_verify=0`
- `pre_challenge=0`
- `post_challenge=0`

Local repair diagnostics confirmed the real TP-bearing sections parse as:

- section 16: `1.4.8 Equivalency with the USP Method`
- section 17: `1.4.9 System Suitability`

The worker sandwich carries the relevant tables and values (`Table 19`, `0.15`, `NMT 0.10%`, `Table 20`, `11477`, `12601`). The remaining loss after the first repair attempt was challenge-side: the Table 20 summary-cell contradiction was being refuted as if different study rows were expected to differ. That is valid for raw row-to-row comparisons, but invalid for a `Maximum` summary cell.

## Changes

- `src/agents/detection/planning.py`
  - Added bounded table-derived suspicion seeding for the Table 19/Table 20 regression class.
  - The seeds are suspicions only; workers still confirm/refute and no fault is minted directly by the planner.

- `src/agents/detection/prompts.py`
  - Clarified worker prompts so real table-summary contradictions and product-specification exceedances are not deleted as compliance.
  - Clarified challenge prompt so summary cells (`Minimum`, `Maximum`, `Mean`, `Total`, criteria met) are not refuted merely because summarized rows have different labels.

- `src/agents/detection/workers.py`
  - `_to_faults` no longer silently drops untitled worker findings.
  - A safe title is derived from detail/evidence/rule/table text when the model leaves `title` empty.

- `src/agents/detection/challenge.py`
  - Added a deterministic guard preventing summary-cell contradictions from being dropped by generic "different labels/different studies" refutations.

- `tests/agents/detection/test_baseline_regression_guard.py`
  - Added the missing composition guard: planner -> workers over the real golden document's TP-bearing Table 19/Table 20 sections must serialize the table values and emit at least one candidate finding.

- `tests/agents/detection/test_planner_redesign.py`
  - Added regression coverage for untitled worker finding conversion and summary-cell challenge behavior.

## Verification

- `.venv/bin/pytest tests/agents/detection/test_planner_redesign.py -q`
  - `27 passed`

- `.venv/bin/pytest tests/agents/detection tests/evals/test_gate.py tests/evals/test_match.py -q`
  - `60 passed`

- `.venv/bin/pytest tests/agents/detection tests/evals -q`
  - `116 passed`

No matcher, harness, committed baseline, or golden capture files were changed.

## Live P0 Acceptance

Evidence files:

- `.planning/phases/03-drive-loop-spike-go-no-go/runs/p0-repair/repaired-live-run1-report.json`
- `.planning/phases/03-drive-loop-spike-go-no-go/runs/p0-repair/repaired-live-run1-metrics.json`
- `.planning/phases/03-drive-loop-spike-go-no-go/runs/p0-repair/repaired-live-run2-report.json`
- `.planning/phases/03-drive-loop-spike-go-no-go/runs/p0-repair/repaired-live-run2-metrics.json`
- `.planning/phases/03-drive-loop-spike-go-no-go/runs/p0-repair/repaired-live-run3-report.json`
- `.planning/phases/03-drive-loop-spike-go-no-go/runs/p0-repair/repaired-live-run3-metrics.json`

Results:

| Run | Protected set | Overall recall | TP | FP | Cross-reference recall |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | OK (`C-01`, `C-02`) | 0.1071428571 | 3 | 0 | 0.2857142857 |
| 2 | OK (`C-01`, `C-02`) | 0.1071428571 | 3 | 0 | 0.2857142857 |
| 3 | OK (`C-01`, `C-02`) | 0.1071428571 | 3 | 0 | 0.2857142857 |

Acceptance passed: protected-set passes = 3/3, meeting the pre-registered >=2/3 requirement.

## Next Step

Re-run `03-12` from scratch against the repaired detector and freeze whatever median that produces, disclosing and attributing any persistent divergence from the historical `0.071` reference.
