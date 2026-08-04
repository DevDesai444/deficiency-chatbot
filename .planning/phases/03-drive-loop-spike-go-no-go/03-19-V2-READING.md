# Phase 03 — v2 GO/NO-GO Reading (against `3b63b75`)

Senior-reviewer gate reading of the v2 scored set, recorded verbatim. The set is closed; no
re-roll. Numbers via the frozen `metrics` / `statistics` paths (see `03-19-V2-RUN-NOTES.md`).

## Ruling (verbatim)

> REVIEWER RULING (v2, against 3b63b75): NO-GO — clause (a) PASSED (regulatory unlock,
> grounded, all runs; run 2 additionally hit absence 3/11), clause (b) FAILED (C-01 lost in
> all runs; B-08/C-02 lost in the median runs). Set closed, no re-roll.

## Frozen-path numbers this reading rests on

| family | run1 | run2 | run3 | median | baseline |
|---|---:|---:|---:|---:|---:|
| absence_of_evidence | 0.000 | 0.273 | 0.000 | 0.000 | 0.091 |
| cross_reference_integrity | 0.000 | 0.286 | 0.000 | 0.000 | 0.286 |
| derivation_plausibility | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| regulatory_framing | 0.200 | 0.400 | 0.200 | **0.200** | 0.000 |
| overall (mvr1381) | 0.036 | 0.250 | 0.036 | 0.036 | 0.107 |

- **Clause (a) — PASSED.** `regulatory_framing` moved off 0.0 with a grounded TP in **all
  three** runs (median 0.200; the grounded match is `A-08`). Run 2 additionally reached
  `absence_of_evidence = 0.273` (3/11 net-new beyond B-08).
- **Clause (b) — FAILED.** The protected `found_set {B-08, C-01, C-02}` was not preserved:
  `C-01` was lost in **all** runs; `B-08` and `C-02` appear only in run 2 (the ceiling run),
  lost in the median runs 1 and 3 (`found_set=['A-08']`).

## Governing provenance

`prereg_commit_sha` for the set = **`3b63b750caa8b6e4cac53e27a5e13789af7782c0`** (all three
runs; `code_head_sha` identical). Run 2 was budget-exhausted (`run_completed=False`,
`ceiling`). v3 remediation (S1–S4) is drafted under a new pre-registration; this ruling is
the closing record for the v2 set.
