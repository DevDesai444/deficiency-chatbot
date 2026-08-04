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

## 2. v1 gate outcome (03-19) — NO-GO on `c123f7e`

Senior-reviewer ruling against `c123f7e`: **NO-GO**, set closed, no re-roll. Overall recall
median **0.000** (baseline 0.107); families 0.000/0.000/0.000/0.000; stop reasons
DR/breaker/DR; fp 0/2/0; matched `found_set` empty all three. Root cause: enumerate-row
`citation` resolved 0/15 in fetch → `not_found` cascade (run 2 retried the identical call
4× into the breaker) → zero exploration. Full record: `03-19-EVIDENCE.md`. Qwen disqualified
(FAIL both fidelity clauses); low-ceiling confirmation PASS.

## 3. Remediation + pre-registration v2 provenance

| Field | Value |
|---|---|
| Remediation commit (R1/R2/R3 + tests + evidence) | `f8a3d0ccad359ec91bfc02830a9a295952cbea21` |
| v2 pre-registration commit (`prereg_commit_sha` for the fresh set) | `e4ff7016598010c17b2e87a0b76006909e069121` |
| v2 pre-registration file | `03-GO-NOGO-PREREGISTRATION-V2.md` |
| Governing baseline (unchanged) | `03-BASELINE-REMEASUREMENT.md` (`5afb4d7`), median 0.107, found_set `{B-08, C-01, C-02}` |
| Config delta from v1 | `dr_grace_turns=5` (R2); all other frozen numbers unchanged |
| A1 provenance additions | run summaries now record `code_head_sha` + `working_tree_dirty`; all 3 scored runs must run at one identical, clean HEAD (§10) |

Full suite at the remediation commit: **492 passed, 11 skipped**. The v2 SHA is recorded
here and will be carried into every fresh run's `prereg_commit_sha`; it is **not** embedded
inside the v2 file (a commit's own hash cannot live in the file it contains). **No scored
run has executed under v2** — the run signal comes from the reviewer after on-disk
verification of both commits.

## 4–N. Fresh-set results, telemetry, diagnosis, verdict

*Placeholders — authored after the reviewer-signalled v2 scored runs. No content yet.*
