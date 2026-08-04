# Phase 03 GO/NO-GO Pre-Registration — v2 (post-NO-GO remediation)

> **Reviewer-approved with amendments A1 + A2 (applied below) and committed with its own
> SHA (recorded in `03-PHASE-REPORT.md`, never inside this file — D-GO5). No scored run may
> execute against v2 until the reviewer gives the run signal after on-disk verification of
> the remediation and this commit.** v1 (`c123f7e`) is closed NO-GO (see `03-19-EVIDENCE.md`).

**Same gate structure as v1, same frozen baseline, new SHA, three fresh scored runs.** Only
the deltas below change; every v1 criterion, rider, and pre-registered reading carries
forward unchanged. v1 lives at `03-GO-NOGO-PREREGISTRATION.md`.

## 0. What changed from v1 (the remediation; everything else is identical)

| ID | Change | Files |
|---|---|---|
| **R1** | `read_guideline` fetch mode TRIPLE-resolves: `lookup_citation` (whole-doc citation) → **requirement-index citation-display → provenance doc_id map (NEW)** → `rule_doc_id`. Every identifier the tool advertises resolves. `not_found` message rewritten to redirect ("enumerate, then pass a rule_doc_id; do not retry this call"). | `src/tools/read_guideline.py` |
| **R2** | Diminishing-returns armed only **after turn 5** (`dr_grace_turns=5`); the circuit breaker is unchanged and still fires during the grace window. | `src/agents/review/budget.py` |
| **R3** | System prompt adds absence-claim discipline: open the section before claiming a topic is absent; a contents/heading line is evidence of PRESENCE. | `src/agents/review/prompts.py` |
| **A1** | Run-summary provenance additionally records `code_head_sha` + `working_tree_dirty` (accounting regression test asserts both exist). | `src/agents/review/telemetry.py` |

New/updated tests: R1 composition test (30/30 round-trip of `citation` AND `rule_doc_id`
for all 15 entries), R2 DR-grace tests. Prompt guards (`test_no_eval_leakage`,
`test_prefix_stability`) remain green. The scoring machinery (`match.py`, `metrics.py`,
`gate.py`, `capture.py`), the matcher, and the baseline are **untouched** — so v2 is scored
under the same harness as v1 and the baseline arm (`HARNESS_VERSION` unchanged).

## 1. Gate criteria (D-GO1) — UNCHANGED from v1

Senior-reviewer confirmed implications, verbatim:
(a) zero-TP-lost protects **{B-08, C-01, C-02}**;
(b) zero families at freeze = **{derivation_plausibility, regulatory_framing}**; absence
path to GO requires **>= 3/11 (>= 2 net-new beyond B-08)**;
(c) gate inputs = **overall fp + recall_by_family only** (per-family fp excluded).

GO requires **(a)** a zero family moves off 0.0 with a grounded TP, OR absence reaches
>= 3/11, **AND (b)** `{B-08, C-01, C-02}` is not lost. Riders (i) derived arithmetic,
(ii) precision reported never gated / `fp > 125 ⇒ GO-WITH-CONCERNS`, (iii) measurement
integrity with absence as the named headline expectation — all carry forward from v1 §1.

## 2. Run procedure (D-GO2) — UNCHANGED

N=3, >= 2 pass; a failed/errored run is FAILING not a re-roll (sole exception: infra fault
with zero tool calls); config frozen before run 1, temp 0, any change voids the set;
headline is the **MEDIAN, never the max**; family-disagreement ⇒ GO-WITH-CONCERNS.

## 3. Model scope (D-GO3) — UNCHANGED

Recall gate on `databricks-meta-llama-3-3-70b-instruct` only. Qwen fidelity bar unchanged.
**v1 evidence:** Qwen FAILED both fidelity clauses and is disqualified on the outcome axis
(`03-19-EVIDENCE.md §5`); agnosticism stays PROVEN-on-fidelity / ASSERTED-on-outcome.

## 4. Reachability (D-GO4) — UNCHANGED

`03-REACHABILITY-CLASSIFICATION.md` still governs (committed with v1). Buckets and ceilings
unchanged: matcher-unreachable `{A-07,B-03,B-06,C-03,D-01}`; per-family max
`0.818/1.000/1.000/0.571`; overall `23/28 = 0.821`. The three D-GO4 readings carry forward.

## 5. Frozen numbers (D-BUD1) — one delta (`dr_grace_turns`)

| Knob | v2 value | vs v1 |
|---|---:|---|
| `max_tokens` | 1,600,000 | same |
| `max_wall_clock_s` | 600 | same |
| `max_turns` | 80 | same |
| `dr_window` | 3 | same |
| **`dr_grace_turns`** | **5** | **NEW (R2)** — DR armed only after turn 5 |
| `breaker_repeat` | 3 | same |
| `breaker_same_class` | 4 | same |
| `max_continuations` | 5 | same |

Calibration multiples, corpus, and the backstop semantics are unchanged from v1 §5. The
run command adds nothing new: `run.py` constructs `BudgetLedger` with the ceilings and
inherits `dr_grace_turns=5` from the dataclass default (no CLI change needed).

## 6. Governing baseline reference (D-LOOP2) — UNCHANGED

Frozen median **0.107** overall, per-family `absence 0.091 / cross_ref 0.286 / derivation
0.000 / regulatory 0.000`, found_set **{B-08, C-01, C-02}**, blank-run 1/3, drift
`0.036 > 0.03` confirmed under the divergence clause. Model
`databricks-meta-llama-3-3-70b-instruct`. Cross-arm identity unchanged:
`harness_version=1`, `matcher_version=1`,
`matcher_content_sha256=e7857edf3f5c1579e27d95f8cf5c086a9e20a443268ef35de01429c488f2c0ca`,
`baseline_sha256=e680eb8638c811b5b9b1a9c7a585223250fdea66f40cf88611b426ba281a0ae3`.
`03-BASELINE-REMEASUREMENT.md` (`5afb4d7`) still governs.

## 7. Productivity definition (D-BUD2) — UNCHANGED

New spans OR emit-gate finding OR first-time `requirement_id` enumeration (Pitfall-4 clause).

## 8. Pre-registered readings — UNCHANGED (with one v1-informed emphasis)

All v1 §8 readings carry forward verbatim (D-TEL3 matrix reported separately never summed;
D-TEL4 >= 95% post-repair, GO-WITH-CONCERNS below; D-TEL5 three continuation readings incl.
`continuation_count = 0 ⇒ UNPROVEN, not validated`; D-ORC2 conversion; Pitfall-6 fallback
verbatim; Pitfall-3 turn-indexed fidelity). **v1-informed watch:** the dominant v1 failure
was `not_found` on unresolvable citations; v2 must show that rule fetch now succeeds — the
diagnosis section must report the `read_guideline` fetch success rate and confirm the
`not_found`-retry cascade did not recur.

**A2 — new pre-registered reading (TOC/heading absence-FP class).** Count, per run, the
absence-family findings whose submission span is a **table-of-contents or heading line**
(the v1 false-positive class — run 2 emitted 2 findings that scored as fp). Report the
count per run, and the diagnosis **must state whether R3 suppressed it** — i.e. whether the
absence-claim discipline stopped the loop from citing a heading/contents line as evidence.
A persistent TOC/heading-FP count means R3 did not land and is a Phase-4 carry-forward.

## 9. Sign-off boundary (D-GO5) — UNCHANGED

*"The GO/NO-GO call is the senior reviewer's ... it does not declare the verdict."* On a
clean NO-GO, Phases 4-6 do not auto-proceed.

## 10. Entry-gate status — carried forward + remediation

v1 §10 entry gates unchanged; item 5 remains CLOSED (15/15 dual-resolve). **v2 pre-run
preconditions:**

1. Immediately before run 1, re-run BOTH the 15-entry dual-resolve probe AND the R1 30/30
   composition check against the installed store, recording both in run-1 provenance — so
   the remediation is proven live before the scored set, and store drift cannot silently
   reintroduce the confounder.
2. **A1 — one identical HEAD, clean system-under-test.** All 3 scored runs MUST execute at a
   single identical git HEAD: the three `code_head_sha` values must be identical or the set
   is void. `working_tree_dirty` is recorded truthfully and is EXPECTED to be true in this
   repository (standing out-of-scope files: `CLAUDE.md`, `frontend/**`,
   `rulebook/manifest.yaml`, `docs/databricks-*`, `.agent*/`, `.planning` scratch). The
   binding cleanliness requirement is scoped to the system under test:
   `git status --porcelain -- src/ tests/` MUST be empty immediately before run 1 and remain
   so through run 3 (output logged in the run notes). Dirty `rulebook/manifest.yaml` is
   covered by precondition 1's live probes, which prove the installed store surface
   immediately pre-run.
3. **Explicit `--prereg` path.** The frozen run command MUST pass
   `--prereg .planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION-V2.md`
   explicitly (run.py's default points at the closed v1 file and is deliberately NOT edited).
   The full byte-frozen command line, recorded at amendment time:

   ```
   .venv/bin/python -m evals.run agent-run \
     --model databricks-meta-llama-3-3-70b-instruct \
     --run-index <1|2|3> \
     --run-prefix agent-run \
     --max-tokens 1600000 \
     --max-wall-clock 600 \
     --max-turns 80 \
     --document-split scored \
     --out-dir .planning/phases/03-drive-loop-spike-go-no-go/runs \
     --prereg .planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION-V2.md
   ```

   After run 1, confirm its summary's `prereg_commit_sha` equals this amendment's SHA
   (recorded in `03-PHASE-REPORT.md`) before runs 2-3 proceed.

## 11. Amendment clause (D-GO5) — UNCHANGED

*"Amending this document after any spike run begins voids the run set — all 3 re-run from
scratch."* v2's commit SHA (assigned at commit, recorded in `03-PHASE-REPORT.md` and every
run summary's `prereg_commit_sha`, never inside this file) replaces `c123f7e` as the
governing contract for the fresh set.

---

**Resolved:** the two existing tests that asserted pre-remediation behavior were updated
under reviewer authorization (`test_read_guideline.py` renamed to
`test_both_advertised_identifiers_resolve_in_fetch_mode`, asserting the display citation now
resolves; `test_continuation_floor.py::test_nudge_bounded_by_dr` gained `dr_grace_turns=0`
to isolate the DR↔nudge interaction from the grace window). Remediation committed at
`f8a3d0c`; full suite **492 passed, 11 skipped**. `not_found` coverage moved to the new
composition test.
