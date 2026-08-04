# Plan 03-17 Summary — Commit the GO/NO-GO gate contract

**Status:** COMPLETE. Both documents committed after senior-reviewer sign-off. No scored
run executed. This plan declares no verdict.

## What was built

- **`03-REACHABILITY-CLASSIFICATION.md`** — all **32** scored GT items (28 `mvr1381` +
  4 `minispec`) in three buckets. The matcher-unreachable set was verified by **replaying
  `match.py`'s own `_anchor_tokens()`** over every anchor (not by trusting a table); it
  reproduced **exactly** `{A-07, B-03, B-06, C-03, D-01}`, so the dataset/matcher have not
  moved. Per-family ceilings computed from the classification: `absence 0.818`,
  `derivation 1.000`, `regulatory 1.000`, `cross_reference 0.571`; overall
  `23/28 = 0.821`. `tp_required = {C-01, C-02}`; protected `found_set = {B-08, C-01, C-02}`.
  Bucket 2 empty for both docs (capability-boundary fact). `match.py` untouched.
- **`03-GO-NOGO-PREREGISTRATION.md`** — all 11 sections + a decision register covering all
  26 decision IDs; confirmed-implications block verbatim; frozen ceilings; governing
  baseline median 0.107 with cross-arm harness identity; every pre-registered reading;
  sign-off boundary; amendment clause.

Preceding this plan, **plan 03-16's reviewer-confirmed ceilings** were recorded in
`03-BUDGET-CALIBRATION.md` (commit `a10aa76`): `max_tokens=1,600,000`,
`max_wall_clock_s=600`, `max_turns=80`, with `dr_window=3`, `breaker_repeat=3`,
`breaker_same_class=4`, `max_continuations=5` unchanged; ceilings-are-backstops note; and
the run-2 breaker-trip watch flag.

## Senior-reviewer reply (recorded verbatim, Task 3)

> Senior-reviewer adjudication on the four items + ONE required change, then commit:
>
> (1) max_turns = 80 FREEZES. The 03-16 reviewer ruling supersedes plan 03-17's literal 50
> — that text predates calibration (29 turns observed on ONE document; scored runs review
> two). Record the supersession note as you drafted it.
>
> (2) REQUIRED CHANGE — rewrite §10's residual blocker: verification-queue item 5 is
> CLOSED, by reviewer measurement (2026-08-04, against the real local store, 605 chunks):
> lookup_citation resolving 0/15 is BY DESIGN — index citations are rich display strings,
> and the v3 contract resolves via the rule_doc_id fallback, which the reviewer measured at
> 15/15 on the live store. The E2E test is NOT synthetic-fixture-scoped: it builds from the
> real committed rulebook/** snapshot (same chunks, same span-IDs). Your first-leg-only
> measurement was the right instinct pointed at the wrong leg. Replace the "full
> absence_of_evidence live path is unproven" conclusion accordingly — as written it would
> cause a 1/11 absence stall in the scored runs to be misattributed to a rulebook gap that
> does not exist. ADD to §10 as a 03-18 PRE-RUN PRECONDITION: immediately before run 1,
> re-run the 15-entry dual-resolve probe against the installed store (offline, seconds) and
> record its 15/15 output in run-1 provenance — so store drift between now and the runs
> cannot silently reintroduce the confounder.
>
> (3) Baseline supersession handling APPROVED as drafted ({B-08, C-01, C-02} / 0.107
> governing, confirmed-implications block verbatim, drift verdict recorded under the
> divergence clause).
>
> (4) Immutability acknowledged — that is the design. After run 1 begins, any amendment
> voids all three runs.
>
> §8 CONFIRMED: I accept every pre-registered reading as binding after a bad result —
> including "continuation_count = 0 means the floor is UNPROVEN, not validated," and "below
> the fidelity floor is GO-WITH-CONCERNS, never NO-GO." §5/§6 numbers verified against my
> 03-16 and 03-12 rulings. Bucket-1 = {A-07, B-03, B-06, C-03, D-01} verified (your
> tokenization replay matches the plan). Bucket-2 empty confirmed as a capability-boundary
> fact. All 26 decision IDs present.
>
> APPROVED — after the §10 rewrite, commit BOTH documents in one explicitly-staged commit
> (user's dirty files excluded), record the SHA in the SUMMARY and 03-PHASE-REPORT.md §1,
> run the ordering guard once, confirm _git_sha_of resolves, then STOP. Do not run anything
> scored.

## §10 change applied per the required change

`03-GO-NOGO-PREREGISTRATION.md` §10 now records **verification-queue item 5 as CLOSED**:
`lookup_citation` resolving 0/15 is by design (display-string leg); the v3 dual-resolve
contract resolves via the `rule_doc_id` fallback leg, reviewer-measured **15/15** on the
live store (2026-08-04, 605 chunks). The E2E test builds from the real committed
`rulebook/**` snapshot, not a synthetic fixture. The "absence_of_evidence live path
unproven" conclusion was removed; the path **is proven**, so an absence stall may not be
attributed to a rulebook gap. A **03-18 pre-run precondition** was added: re-run the
15-entry dual-resolve probe against the installed store immediately before run 1 and
record its 15/15 output in run-1 provenance, guarding against store drift.

## Commit and provenance

- **Pre-registration commit SHA (`prereg_commit_sha`):**
  `c123f7e66a170d7fa6715122a00bbf262a62f4aa`
- Both `03-GO-NOGO-PREREGISTRATION.md` and `03-REACHABILITY-CLASSIFICATION.md` are in that
  **single** commit (`docs(03-17): commit GO/NO-GO pre-registration + reachability (D-GO5)`).
- **Clean-tree confirmation** (the property that keeps D-GO1 rider (iii) checkable and
  D-GO5's amendment clause enforceable):
  - `git diff --quiet -- <prereg>` → **unstaged CLEAN**
  - `git diff --cached --quiet -- <prereg>` → **staged CLEAN**
- **`_git_sha_of` resolvability:**
  `PYTHONPATH=src .venv/bin/python -c "from agents.review.telemetry import _git_sha_of; ..."`
  → resolved `c123f7e66a170d7fa6715122a00bbf262a62f4aa`.
- The SHA is **not embedded inside** the pre-registration (`grep -c "$SHA" <prereg>` → `0`):
  a commit's own hash cannot live in the file that commit contains.

## Prefix-agnostic ordering guard (run once, at wave 9)

Command run verbatim:

```
ls .planning/phases/03-drive-loop-spike-go-no-go/runs/*[123].json 2>/dev/null \
  | grep -v -E '/(baseline|calibration)-run[123]\.json$'
```

**Output: empty.** At the commit, no `runs/` JSON artifact ending in run-index `1|2|3`
exists under **any** `--run-prefix`, apart from the baseline (`baseline-run{1,2,3}.json`)
and calibration families that legitimately predate it. The glob carries **no literal
`run`**, so a decoy prefix (`probe-`, `lowceiling-`, `smoke-`, or a bare `x`) would be
caught too. Plans 03-18 and 03-19 **cite this result**; they do not re-run the guard
(from wave 10 the scored artifacts legitimately exist).

## Carried forward to 03-18 / 03-19

- **03-18 must pass `--prereg <path>`** so `capture_provenance` writes
  `prereg_commit_sha = c123f7e66a170d7fa6715122a00bbf262a62f4aa` into every run summary.
- **03-18 pre-run precondition:** re-run the 15-entry dual-resolve probe against the
  installed rulebook store immediately before run 1; record its 15/15 output in run-1
  provenance (§10).
- **03-19 §1** carries the pre-registration SHA and the ordering-guard result from this
  SUMMARY rather than regenerating them.
- **Watch item:** the breaker tripped in calibration run 2 — if it trips in any scored run,
  examine its `(reason_code, half)` matrix at the gate before accepting that run.

## Boundary

No task in this plan declared GO or NO-GO. The verdict is the senior reviewer's, made
against this committed contract. 03-18/03-19 remain unexecuted. Nothing scored was run.
