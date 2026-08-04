# Phase 03 — Drive-Loop Spike GO/NO-GO — Phase Report

> **Status: IN PROGRESS.** This report is authored by plan 03-19 after the scored spike
> runs complete. Only §1's pre-registration provenance anchor is populated now (plan 03-17,
> wave 9), because D-GO5 requires the pre-registration's commit SHA to be recorded in the
> phase report. All other sections are placeholders owned by 03-19 and MUST NOT be
> interpreted as results — no scored run has executed.

## 1. Pre-registration provenance (D-GO5)

The GO/NO-GO gate contract was committed **before any scored spike run existed**, so gate
criteria are provably timestamped ahead of results.

| Field | Value |
|---|---|
| `prereg_commit_sha` | `c123f7e66a170d7fa6715122a00bbf262a62f4aa` |
| Pre-registration | `03-GO-NOGO-PREREGISTRATION.md` |
| Reachability classification (same commit) | `03-REACHABILITY-CLASSIFICATION.md` |
| Governing baseline | `03-BASELINE-REMEASUREMENT.md` (`5afb4d7`), median overall `0.107`, found_set `{B-08, C-01, C-02}` |
| Frozen ceilings | `03-BUDGET-CALIBRATION.md` (`a10aa76`): `max_tokens=1,600,000`, `max_wall_clock_s=600`, `max_turns=80` |

**Ordering guard (run once, wave 9 — plan 03-17):** at the pre-registration commit, no
`runs/` JSON artifact ending in run-index `1|2|3` existed under any `--run-prefix` apart
from the baseline and calibration families that legitimately predate it. The guard glob
carries no literal `run`, so a decoy prefix could not slip past. Result: **empty (pass).**
This result is cited from `03-17-SUMMARY.md`, not regenerated.

Every scored run's summary carries this `prereg_commit_sha` via `capture_provenance`
(plan 03-08). Amending the pre-registration after any run begins voids the run set (D-GO5).

## 2–N. Results, telemetry, diagnosis, verdict

*Placeholders — authored by plan 03-19 after the scored runs. No content yet.*
