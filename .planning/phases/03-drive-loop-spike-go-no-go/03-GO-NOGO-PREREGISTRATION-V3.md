# Phase 03 GO/NO-GO Pre-Registration — v3 / v3.1 (post-v2-NO-GO remediation)

> **Reviewer-approved (S1–S5, §8 r1–r6, §10 preconditions incl. §10.3 v3-prefix command).
> The GOVERNING `prereg_commit_sha` is the SHA of the latest commit touching THIS file — the
> **v3.2** amendment commit (recorded in `03-PHASE-REPORT.md`, never inside this file — D-GO5),
> superseding v3.1 `fdbd535` and v3 `4b080e4`. No scored run may execute until the reviewer
> gives the run signal after on-disk verification of the v3.2 commit.** v2 (`3b63b75`) is
> closed NO-GO (see `03-19-V2-READING.md`).

## v3.1 amendment (T1 + T2 — oracle engagement made real)

The v3 GO on `4b080e4` was **revoked**: `run_oracles` produced 0 leads on both scored
documents because `_doc_from_cache` (`oracles_tool.py`) set `tables=[]` while
`cache["table_index"]` carried the real structured data — so S5 was theater on this corpus.
v3.1 fixes the substrate and adds the missing oracle shapes; **everything else in v3 stands
unchanged.**

| ID | Change | Files |
|---|---|---|
| **T1** | `_doc_from_cache` rebuilds grid tables from `cache["table_index"]` (headers + rows + `kind="grid"`); the flat-text page is preserved so text-based checks still fire. | `src/agents/review/oracles_tool.py` |
| **T2a** | `numeric_cross_reference` — a stated column extremum contradicted by the tabulated rows above it (conservative: explicit Maximum/Minimum row, >1% tolerance). Targets **C-01** (Table 20 Maximum 11477 vs tabulated 12601) and **C-02/MS-02** (stated Maximum 0.15 vs 0.19). | `src/agents/detection/oracles.py` |
| **T2b** | `expected_row_absent` — a rule-required attribute (`Any Unspecified Impurity`, `Total Impurities`) referenced on a page carrying an impurity/result table but with no tabulated row. Targets **B-08**. Zero-FP-preferred. | `src/agents/detection/oracles.py` |

**Live-corpus verification (the boundary-crossing composition test S5 never had):**
`run_oracles_tool` end-to-end on the real scored corpus surfaces leads naming **C-01
`11477`** (mvr1381) and **C-02 `0.15`** (minispec) — 8 leads on mvr1381, 13 on minispec,
0 check-errors (was 0/0/0). `tests/agents/review/test_oracle_leads_real_corpus.py` asserts
the target set fires or the build is red (bar tightened to all three in v3.2 below).

## v3.2 amendment (T2b-prose — B-08 reachable, variance-reduced)

v3.1 fired on C-01 and C-02 but **not B-08** (`Any Unspecified Impurity` is prose-only on
mvr1381, whose real grid table carries `result` in cells, not the header — so T2b's
header-only guard missed it). Losing B-08 alone still fails clause (b), and v2 hit B-08 only
1/3 times, so this small extension directly reduces run-set variance.

- **T2b-prose** — `expected_row_absent` now detects the "impurity/result grid table" from its
  header **OR its cells**, so a page carrying impurity/result data qualifies even when the
  attribute name lives only in prose. It still fires only on a case-insensitive **exact**
  whitelist match (`Any Unspecified Impurity`, `Total Impurities`) with **no** grid row label
  for it — no door opened to unrelated prose words. (`src/agents/detection/oracles.py`)
- **Tightened verification** — `test_oracle_leads_real_corpus.py` now asserts **ALL THREE** of
  {`11477`, `0.15`, `any unspecified impurity`} appear across the two docs' leads, not ≥1.

**Live-corpus verification (all three):** mvr1381 → `11477` (`numeric_cross_reference`) **and
`Any Unspecified Impurity` (`expected_row_absent`)**; minispec → `0.15`
(`numeric_cross_reference`). 10 leads on mvr1381, 13 on minispec, 0 check-errors. Full suite:
**504 passed, 11 skipped.**

**Same gate structure and frozen baseline as v1/v2, new SHA, three fresh scored runs.** Only
the S1–S4 deltas below change; every v1/v2 criterion, rider, and pre-registered reading
carries forward unchanged.

## 0. What changed from v2 (S1–S4; everything else identical)

| ID | Change | Files |
|---|---|---|
| **S1** | The identical-args circuit breaker counts **only identical calls whose result was REJECTED** — successful repeats (dedup-neutralized) never kill a run. `same_class` breaker unchanged. (Forensic: v2 run 3 died `breaker` at turn 21 while healthy.) | `src/agents/review/budget.py`, `loop.py` |
| **S2** | (i) a **nudge resets the DR productivity window** (the model gets a full fresh window to comply with "keep working"); (ii) **`dr_window` 3 → 5**. (Forensic: v2 run 1's nudge yielded findings 1→5, then DR fired before the cycle completed.) | `src/agents/review/budget.py`, `loop.py` |
| **S3** | Ceilings raised (backstops, not operative stops): **`max_tokens` 1,600,000 → 3,200,000; `max_wall_clock_s` 600 → 1200; `max_turns` 80 → 120**. Ceiling-abort still records `run_completed=False`. (Forensic: v2 run 2 was cut while productive at 1.64M / 52 turns.) | frozen numbers + run command only |
| **S4** | **Coverage reminder**: every 8 turns the loop injects a code-computed user message listing unaddressed coverage (manifest documents not yet opened / opened-but-empty). Dynamic content in a MESSAGE, never the static prefix (COST-01). Telemetry logs each injection turn. (Targets clause (b): v2 proved B-08/C-02 findable; the median runs were never steered back to them.) | `src/agents/review/loop.py`, `telemetry.py` |
| **S5** | **Force oracle engagement**: the prompt directs `run_oracles` **first** (before enumerate-driven fetch) — oracles surface concrete numeric leads (impurity exceedances, arithmetic inconsistencies) that seed the search. The S4 coverage reminder additionally reports oracle engagement (leads surfaced vs findings emitted), so an un-called oracle or an unaddressed lead visibly counts as unaddressed coverage. (Evidence: `run_oracles` was 0/0/0 across all three v2 runs, yet C-01/C-02 are exactly the profile oracles target.) | `src/agents/review/prompts.py`, `loop.py` |

New/updated tests: S1 breaker (`test_breaker_rejected_only.py`: 3 successful → no trip, 3
rejected → trip); S2 (`test_dr_grace.py`: `dr_window` default 5, nudge resets window); S4
(`test_coverage_reminder.py`: injected+logged, not in the prefix); S5
(`test_oracle_engagement.py`: scripted 8-turn run contains >=1 `run_oracles` tool_call;
reminder flags un-called / unused oracles). Four existing breaker/accounting tests updated to
the S1 contract (identical **rejected** calls trip). Prompt guards (`test_no_eval_leakage`,
`test_prefix_stability`) green. Scoring machinery untouched — v3 is scored under the same
harness as v1/v2/baseline (`HARNESS_VERSION` unchanged). **Full suite at draft time:
503 passed, 11 skipped.**

## 1. Gate criteria (D-GO1) — UNCHANGED

Confirmed implications verbatim: (a) zero-TP-lost protects **{B-08, C-01, C-02}**; (b) zero
families at freeze = **{derivation_plausibility, regulatory_framing}**, absence path
requires **>= 3/11**; (c) gate inputs = overall fp + recall_by_family only. GO requires a
zero family off 0.0 with a grounded TP (or absence >= 3/11) **AND** `{B-08, C-01, C-02}`
preserved. Riders (i)–(iii) carry forward from v1 §1.

## 2. Run procedure (D-GO2) — UNCHANGED

N=3, >= 2 pass; failed/errored (incl. budget exhaustion) is FAILING not a re-roll (sole
exception: infra fault, zero tool calls); config frozen before run 1, temp 0; headline is
the MEDIAN never the max; family-disagreement ⇒ GO-WITH-CONCERNS.

## 3. Model scope (D-GO3) — UNCHANGED

Recall gate on `databricks-meta-llama-3-3-70b-instruct` only. Qwen disqualified on prior
evidence (FAIL both fidelity clauses); agnosticism PROVEN-on-fidelity / ASSERTED-on-outcome.

## 4. Reachability (D-GO4) — UNCHANGED

`03-REACHABILITY-CLASSIFICATION.md` governs. matcher-unreachable `{A-07,B-03,B-06,C-03,D-01}`;
per-family max `0.818/1.000/1.000/0.571`; overall `23/28 = 0.821`. Three readings carry forward.

## 5. Frozen numbers — S2/S3 deltas

| Knob | v3 value | vs v2 |
|---|---:|---|
| `max_tokens` | **3,200,000** | 1,600,000 → 3,200,000 (S3) |
| `max_wall_clock_s` | **1200** | 600 → 1200 (S3) |
| `max_turns` | **120** | 80 → 120 (S3) |
| `dr_window` | **5** | 3 → 5 (S2ii) |
| `dr_grace_turns` | 5 | same |
| `breaker_repeat` | 3 | same number; S1 changes semantics (rejected-only) |
| `breaker_same_class` | 4 | same |
| `max_continuations` | 5 | same |
| coverage-reminder cadence | every 8 turns | NEW (S4) |

Ceilings remain **backstops**; the operative stops are diminishing-returns and the breaker.
`run.py` inherits `dr_window`/`dr_grace_turns` from the dataclass defaults; the ceilings are
passed on the command line (§10.3).

## 6. Governing baseline (D-LOOP2) — UNCHANGED

Median **0.107** overall; per-family `absence 0.091 / cross_ref 0.286 / derivation 0.000 /
regulatory 0.000`; found_set **{B-08, C-01, C-02}**; drift confirmed. Cross-arm identity
unchanged (`harness_version=1`, `matcher_version=1`,
`matcher_content_sha256=e7857e…`, `baseline_sha256=e680eb…`). `03-BASELINE-REMEASUREMENT.md`
(`5afb4d7`) governs.

## 7. Productivity definition (D-BUD2) — UNCHANGED

New spans OR emit-gate finding OR first-time `requirement_id` enumeration.

## 8. Pre-registered readings — carried forward + four v2-informed additions

All v1/v2 §8 readings carry forward (D-TEL3 matrix separate never summed; D-TEL4 >= 95%
post-repair; D-TEL5 three continuation readings incl. `continuation_count=0 ⇒ UNPROVEN`;
D-ORC2; Pitfall-6 fallback; Pitfall-3 turn-indexed). New for v3:

- **(r1) Stop reasons with breaker cause.** Each run's `stop_reason` is reported, and for any
  `breaker` stop the cause (`identical_args` vs `same_class`) and its `(reason_code, half)`
  matrix at the trip. S1 predicts healthy runs no longer die on `identical_args` from
  successful repeats.
- **(r2) Coverage-reminder telemetry.** Report per run: `coverage_reminder_count`, the
  injection turn indices, and — from the JSONL — how many `emit_finding` successes landed
  within 3 turns after each injection. Zero findings-after-injection across all runs ⇒ the
  reminder burns budget and S4 is reconsidered in Phase 4.
- **(r5) Oracle engagement (S5).** Report per run whether `run_oracles` was invoked and the
  D-ORC2 conversion (`leads surfaced / re-opened / emitted`). v2 was 0/0/0 in all runs; v3
  must show `run_oracles` is now called early. If it is called but leads are surfaced and
  not emitted, that is the D-ORC2 low-emit reading (oracles surfacing noise or leads ignored).
- **(r6) Oracle-lead coverage of missed protected TPs (v3.1).** For each of {C-01, C-02, B-08}
  **not found** in the run, record whether a `run_oracles` lead **named it** AND whether the
  model **re-opened** that lead. A v3.1 NO-GO with a recall-driven root cause on a lead we
  surfaced but the model ignored is a **prompt problem**; one we never surfaced is an
  **oracle problem**. This localizes any residual miss to the right layer.
- **(r3) A2 TOC/heading absence-FP count** carried forward (dotted-leader/section-heading
  cited findings per run; v2 was 1/5, 6/12, 3/4). The diagnosis states whether the count fell.
- **(r4) C-01 watch.** `C-01` (`'11477'`, Table 20) was lost in **all** v2 runs. Per run, if
  `C-01` is unfound, **record whether its section (Table 20) was ever opened** (a
  `get_section`/`open_doc` span for the relevant offset range) — distinguishing "never
  navigated to it" from "read it but did not emit".

## 9. Sign-off boundary (D-GO5) — UNCHANGED

The GO/NO-GO call is the reviewer's; the executor reports numbers and telemetry and does not
declare the verdict. On a clean NO-GO, Phases 4-6 do not auto-proceed.

## 10. Entry-gate status + pre-run preconditions (ALL v2 preconditions carried forward)

Item 5 CLOSED (15/15 dual-resolve). v3 pre-run preconditions:

1. **Live probes** immediately before run 1: 15-entry dual-resolve **15/15** AND R1
   composition **30/30** against the installed store; recorded in run-1 notes.
2. **Provenance triple / one clean HEAD.** All 3 runs at a single identical `code_head_sha`
   (or void); `prereg_commit_sha` == the v3 commit SHA on every run; `working_tree_dirty`
   recorded truthfully (expected true for standing out-of-scope files). Binding cleanliness
   scoped to the system under test: `git status --porcelain -- src/ tests/` empty before run
   1 through run 3 (logged).
3. **Explicit `--prereg` + collision-free prefix.** The frozen command MUST pass
   `--prereg …03-GO-NOGO-PREREGISTRATION-V3.md` explicitly (run.py default = closed v1) and
   `--run-prefix agent-run-v3-` (v1 `agent-run*` and v2 `agent-run-v2*` artifacts are
   immutable evidence; a colliding prefix would overwrite them). After run 1, confirm its
   summary's `prereg_commit_sha` equals the **v3.1** commit SHA before runs 2-3.
4. **Oracle-lead pre-flight (v3.1, tightened v3.2).** Immediately before run 1,
   `run_oracles_tool` on the scored corpus MUST return leads whose text names **ALL THREE** of
   {C-01 `11477`, C-02 `0.15`, B-08 `Any Unspecified Impurity`}. **Any target missing = STOP,
   no runs** (the oracle substrate regressed). Same assertion as
   `test_oracle_leads_real_corpus.py`, run live against the installed corpus, alongside the
   §10.1 15/15 + 30/30 probes.

   ```
   .venv/bin/python -m evals.run agent-run \
     --model databricks-meta-llama-3-3-70b-instruct \
     --run-index <1|2|3> \
     --run-prefix agent-run-v3- \
     --max-tokens 3200000 --max-wall-clock 1200 --max-turns 120 \
     --document-split scored \
     --out-dir .planning/phases/03-drive-loop-spike-go-no-go/runs \
     --prereg .planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION-V3.md
   ```

## 11. Amendment clause (D-GO5) — UNCHANGED

Amending after any spike run begins voids the run set. The **v3.2** commit SHA — the latest
commit touching this file, recorded in `03-PHASE-REPORT.md`, never inside this file — is the
governing `prereg_commit_sha`, superseding v3.1 `fdbd535` and v3 `4b080e4`.

---

**Approved and committed.** This file's commit SHA (recorded in `03-PHASE-REPORT.md`, never
inside this file) is the governing `prereg_commit_sha` for the v3 set. No scored run runs
until the reviewer's run signal after on-disk verification of the commit; then the §10
preconditions and the 3 runs execute under the v2 conditional protocol.
