# Phase 03 — v3 scored-run notes (raw numbers only, no verdict)

Governing `prereg_commit_sha` = **`e8de55aa4bbc1f75030a18ef05f79474ac61654d`** (v3.2). The v3.2
gate reading is the senior reviewer's, against that SHA. Nothing here declares GO/NO-GO.

## Pre-run conditions (self-verified in order)
- **(a)** `git status --porcelain -- src/ tests/` EMPTY; HEAD `e8de55a` through all 3 runs.
- **(b)** §10.1 probes: dual-resolve **15/15**, R1 composition **30/30**.
- **(c)** §10.4 oracle-lead pre-flight: leads name **all three** {`11477`, `0.15`, `Any Unspecified Impurity`} — PASS.
- **(d)** runs 1→2→3, `--run-prefix agent-run-v3-`, ceilings 3,200,000/1200/120, `--prereg …V3.md`, byte-identical except `--run-index`.
- **(e)** post-run-1 gate: `prereg_commit_sha` = `code_head_sha` = `e8de55a` — PASS.
- **(f)** all three `code_head_sha` identical = `e8de55a`; all `run_completed=True`; `working_tree_dirty=true` (truthful).

## Per-run summary (raw)

| Run | completed | stop_reason (breaker cause) | turns | tool_calls | billed | found_set |
|---:|---|---|---:|---:|---:|---|
| 1 | True | breaker (**same_class** `not_found\|`) | 25 | 23 | 307,154 | C-02, C-04, MS-01, MS-02, MS-04 |
| 2 | True | diminishing-returns | 26 | 24 | 338,393 | C-02, C-04, MS-01, MS-02, MS-04 |
| 3 | True | breaker (**same_class** `not_found\|`) | ~55 | 21 | (see summary) | C-02, C-04, MS-01, MS-02, MS-04 |

`found_set` is **identical across all three runs**.

## recall_by_family (mvr1381, governing) + medians via `statistics.median`

| family | run1 | run2 | run3 | median | baseline |
|---|---:|---:|---:|---:|---:|
| absence_of_evidence | 0.000 | 0.000 | 0.000 | 0.000 | 0.091 |
| cross_reference_integrity | 0.286 | 0.286 | 0.286 | **0.286** | 0.286 |
| derivation_plausibility | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| regulatory_framing | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| **overall (mvr1381)** | 0.071 | 0.071 | 0.071 | **0.071** | 0.107 |

**Protected `found_set {B-08, C-01, C-02}`:** only **C-02** preserved (all 3 runs); **C-01 and
B-08 lost in all 3 runs**. (C-04 also matched — cross_reference_integrity 2/7 = 0.286.)

**tp/fp/fn:** run1/run2 mvr `tp=2 fp=1 fn=26` (prec 0.667); run3 mvr `tp=2 fp=3 fn=26` (prec 0.400).
minispec run1/2 `tp=3 fp=1 fn=1`, run3 `tp=3 fp=3 fn=1`. fp reported, not gated; under 125.

## Pre-registered readings (§8)
- **(r1) stop reasons + breaker cause.** run1 breaker, run3 breaker — both **same_class** on
  consecutive `not_found|` (4 and 5 consecutive; `breaker_same_class=4`). run2 diminishing-returns.
  `span_invention=0`, `rule_never_read=0` all runs. S1 held: no `identical_args` trip from
  successful repeats.
- **§8 read_guideline fetch.** successful `read_guideline` calls 4/4/8; rejections `not_found`
  4/3/6 (+ `range_too_large`). The v1 identical-retry cascade did not recur as `identical_args`,
  but **`not_found` still occurs** and drove the same_class breaker in runs 1 & 3 — some
  citations the model chose still do not resolve.
- **(r2) coverage-reminder telemetry.** injections at turns [17,34,48] (run3 also 65);
  `coverage_reminder_count` 3/3/4. Findings emitted within 3 turns after each injection:
  run1 [0,0,0], run2 [0,1,0], run3 [0,0,0] — **almost always zero** (one instance, run2).
- **(r3) A2 TOC/heading-line-cited findings:** run1 1/2, run2 1/2, run3 3/4 — the class persists.
- **D-TEL5 continuation.** `continuation_count=1` each; nudge findings_before→after: run1 [2→2],
  run2 [2→2], run3 [2→4] (+2 in run3). which_bound: run2 `diminishing_returns`.
- **(r5) oracle engagement.** `run_oracles` was **NOT called in any run** — `oracle_leads
  surfaced/re-opened/emitted = 0/0/0` for all three, despite the S5 run_oracles-first prompt
  directive AND the coverage reminder flagging the un-called oracle. The oracle substrate is
  proven capable (§10.4 pre-flight surfaced all three targets live), but the model never invoked
  the tool.
- **(r6) oracle-lead coverage of missed protected TPs.** For **C-01** and **B-08** (both unfound):
  a `run_oracles` lead that names them **exists** (pre-flight: `11477` and `Any Unspecified
  Impurity`), but **was never surfaced to the model** because `run_oracles` was not called, and
  therefore **never re-opened**. Per r6's framing: the leads were not surfaced — but not because
  the oracle can't produce them (it can); rather the model did not invoke `run_oracles`. A
  model-compliance / prompt-adherence signal, recorded for the reviewer's localization.
- **(r4) C-01 watch.** C-01 unfound in all runs. No emitted fault's evidence contains `11477` or
  "theoretical plates" in any run — the model did not surface Table 20's theoretical-plates
  region into a finding. (Tool-result text is scrubbed from the JSONL, so this reflects emitted
  evidence, not every section opened; but no C-01 evidence reached the report.)

## Artifacts
Nine new: `agent-run-v3-{1,2,3}.json`, `.jsonl`, `-summary.json`. v1/v2 artifacts untouched
(distinct `agent-run-v3-` prefix). No verdict is declared in this document.
