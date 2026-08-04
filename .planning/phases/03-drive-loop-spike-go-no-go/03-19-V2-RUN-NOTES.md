# Phase 03 — v2 scored-run notes (raw numbers only, no verdict)

Governing `prereg_commit_sha` = **`3b63b750caa8b6e4cac53e27a5e13789af7782c0`** (the §10.3
amendment). The v2 gate reading is the senior reviewer's, against that SHA. Nothing here
declares GO/NO-GO.

## Pre-run conditions (self-verified in order)

**(a) `git status --porcelain -- src/ tests/` — EMPTY** (system-under-test clean). HEAD at
run time: `3b63b750caa8b6e4cac53e27a5e13789af7782c0`. `working_tree_dirty=true` is expected
(standing out-of-scope files) and is scoped away from the binding check per §10.2.

**(b) §10.1 live probes — BOTH PASS:**
- 15-entry dual-resolve against the installed store: **15/15** (leg A display 0/15 by
  design, leg B `rule_doc_id` 15/15).
- R1 composition (`test_all_15_rows_round_trip_both_citation_and_rule_doc_id_30_of_30`):
  **30/30 PASS**.

**(d) post-run-1 provenance gate — PASS:** run 1 `prereg_commit_sha` = `code_head_sha` =
`3b63b75` (the amendment SHA). Runs 2-3 proceeded.

**(e) cross-run provenance:** all three `code_head_sha` identical and equal `3b63b75`; all
`prereg_commit_sha` = `3b63b75`; `working_tree_dirty=true` recorded truthfully on all three.

## Byte-frozen command (identical except `--run-index`)

```
.venv/bin/python -m evals.run agent-run \
  --model databricks-meta-llama-3-3-70b-instruct \
  --run-index <1|2|3> \
  --run-prefix agent-run-v2- \
  --max-tokens 1600000 --max-wall-clock 600 --max-turns 80 \
  --document-split scored \
  --out-dir .planning/phases/03-drive-loop-spike-go-no-go/runs \
  --prereg .planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION-V2.md
```

## Per-run summary (raw)

| Run | completed | stop_reason | turns | tool_calls | billed | cont | matched found_set |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | True | diminishing-returns | 35 | 33 | 930,289 | 1 | `['A-08']` |
| 2 | **False** | **ceiling** | 52 | 47 | 1,641,929 | 2 | `['A-01','A-03','A-08','B-08','C-02','C-04','C-06','MS-01','MS-02','MS-03','MS-04']` |
| 3 | True | breaker | 21 | 21 | 277,227 | 0 | `['A-08']` |

Run 2 was **budget-exhausted** (`stop_reason=ceiling`, `run_completed=False`,
`abort_reason=ceiling`) — recorded per D-GO2(i) as the reviewer weighs it; its findings are
the returned grounded partial.

## recall_by_family (mvr1381, governing) + medians via `statistics.median`

| family | run1 | run2 | run3 | **median** | baseline |
|---|---:|---:|---:|---:|---:|
| absence_of_evidence | 0.000 | 0.273 | 0.000 | **0.000** | 0.091 |
| cross_reference_integrity | 0.000 | 0.286 | 0.000 | **0.000** | 0.286 |
| derivation_plausibility | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 |
| regulatory_framing | 0.200 | 0.400 | 0.200 | **0.200** | 0.000 |
| **overall (mvr1381)** | 0.036 | 0.250 | 0.036 | **0.036** | 0.107 |

The median run (runs 1 and 3, both overall 0.036) has `found_set=['A-08']`;
`regulatory_framing` median is 0.200 (baseline 0.000). Reported as raw facts; the gate
reading is the reviewer's.

## tp / fp / fn (end_to_end, frozen path)

| Run | mvr1381 tp/fp/fn (prec) | minispec tp/fp/fn |
|---:|---|---|
| 1 | 1 / 1 / 27 (0.500) | 0 / 5 / 4 |
| 2 | 7 / 1 / 21 (0.875) | 4 / 10 / 0 |
| 3 | 1 / 3 / 27 (0.250) | 0 / 4 / 4 |

fp is reported, not gated (D-GO1(ii)); all runs are far under the 125 flag line.

## Pre-registered telemetry readings

- **D-TEL3 matrix `(reason_code, half)`** (reported separately, never summed): run1
  `{not_found|:1, range_too_large|:4}`; run2 `{not_found|:2, range_too_large|:2}`; run3
  `{not_found|:2, range_too_large|:1}`. `span_invention_count=0` and `rule_never_read_count=0`
  in all three runs.
- **§8 watch — `read_guideline` fetch:** successful `read_guideline` tool_calls 9 / 17 / 5;
  `read_guideline` rejections run1 `{range_too_large:3}`, run2 `{not_found:2,
  range_too_large:2}`, run3 `{not_found:2, range_too_large:1}`. **The v1 `not_found`-retry
  cascade did NOT recur** (v1's dominant `not_found` on unresolvable citations is gone;
  R1 resolves the advertised identifiers). The residual `read_guideline` rejections are
  `range_too_large` (oversized rulebook chunks → pagination), not resolution failures.
- **A2 — TOC/heading-line-cited findings** (heuristic: dotted-leader TOC line or
  section-number heading in the finding's evidence span): run1 **1/5**, run2 **6/12**, run3
  **3/4**. Diagnosis (raw): **R3 did NOT fully suppress the TOC/heading-line citation
  class** — findings citing table-of-contents / section-header lines still appear across all
  three runs. This is a Phase-4 carry-forward signal; not a verdict.
- **D-TEL5 continuation:** run1 `continuation_count=1`, nudge findings_before→after
  `[1→5]` (+4 new grounded findings); run2 `=2`, `[3→8]`,`[8→12]` (+5, +4); run3 `=0`
  (floor not exercised in run3). The nudge produced new grounded findings in runs 1 and 2
  (mechanism load-bearing where exercised); `continuation_count=0` in run 3 leaves the
  floor unexercised for that run.
- **D-ORC2 oracle conversion:** `surfaced/reopened/emitted = 0/0/0` in all runs —
  `run_oracles` was not invoked in any v2 run.

## Artifacts

Nine new committed under `runs/`: `agent-run-v2-{1,2,3}.json`, `.jsonl`, `-summary.json`.
The v1 `agent-run{1,2,3}.*` evidence is untouched (distinct `agent-run-v2-` prefix). No
verdict is declared in this document.
