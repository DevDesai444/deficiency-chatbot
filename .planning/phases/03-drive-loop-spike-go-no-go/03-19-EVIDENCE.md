# Phase 03 — 03-19 Gate Evidence & NO-GO Record (against `c123f7e`)

The senior reviewer's GO/NO-GO reading of the committed spike set, made against the
pre-registration `c123f7e66a170d7fa6715122a00bbf262a62f4aa`. **Ruling: NO-GO.** The set is
closed; no re-roll. This document records the numbers, the ruling, and the root cause; the
remediation is drafted under a NEW pre-registration (v2, held for reviewer adjudication).

## 1. The `c123f7e` scored set (raw, frozen paths)

Three runs on `databricks-meta-llama-3-3-70b-instruct`, one frozen config (max_tokens
1,600,000 / max_wall_clock 600 / max_turns 80, temp 0), all carrying
`prereg_commit_sha=c123f7e`.

| Run | run_completed | stop_reason | turns | tool_calls | billed | faults | fp | matched found_set |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | True | diminishing-returns | 7 | 7 | 46,869 | 0 | 0 | `[]` |
| 2 | True | **breaker** | 19 | 17 | 204,516 | 2 | 2 | `[]` |
| 3 | True | diminishing-returns | 7 | 7 | 47,112 | 0 | 0 | `[]` |

**recall_by_family median (mvr1381), via `statistics.median`:** every family **0.000**;
**overall 0.000** (baseline median 0.107). Matched `found_set` **empty** in all three —
the baseline `{B-08, C-01, C-02}` was not reproduced. fp 0/2/0 (precision reported, not
gated; under the 125 line).

## 2. Ruling

**NO-GO.** Gate criteria D-GO1(a)/(b) not met: no zero family moved off 0.0, the
absence path did not reach 3/11, and the protected `found_set` was not preserved. Recorded
against `c123f7e`; the set is closed; no re-roll (D-GO2(i)).

## 3. Root-cause chain (reviewer-verified)

1. **Enumerate-row `citation` values resolve 0/15 in fetch mode.** The requirement-index
   `citation` field is a rich subsection/glossary display string that matches neither
   `lookup_citation`'s whole-document keys nor a rulebook doc_id. A model that enumerated
   (`read_guideline()` no-arg) and round-tripped `row['citation']` into fetch mode got
   `not_found` for every entry.
2. **Cascade to `not_found` → early stops.** The dominant rejection across the scored set
   was `not_found|` (run1 ×2, run2 ×4, run3 ×2 — unknown/unresolvable identifiers). Run 2's
   model **retried the identical failing call 4×** until the same-class breaker stopped it
   (`stop_reason=breaker`; §5 watch item confirmed). Runs 1 and 3 stalled and hit
   diminishing-returns at turn 7.
3. **Zero exploration → zero findings.** With rule fetch blocked, the enumerate→fetch→emit
   chain never completed; `run_oracles` was never invoked; `span_invention_count=0` and
   `rule_never_read_count=0` in all runs (the model was not inventing spans — it could not
   retrieve rules at all).

The §10 pre-run dual-resolve probe (15/15 on the installed store) confirmed the *rulebook
store* was intact; the failure was the **tool's citation-resolution surface**, not the
corpus — so the `absence_of_evidence` 0/11 is attributable to the fetch-resolution gap the
remediation targets, consistent with the pre-registration's attribution discipline.

## 4. Telemetry readings (as pre-registered)

- **D-TEL5 continuation floor:** `continuation_count=0` in runs 1 and 3 ⇒ the floor **was
  not exercised and is UNPROVEN, not validated**; run 2 exercised it once (1 of 5).
- **D-TEL3 matrix:** dominated by `not_found|` (see root cause). `not_byte_exact|submission`
  = 0 and `not_retrieved_this_session|rule` = 0 all runs.
- **Breaker watch item (§5):** recurred in scored run 2 (`{not_found|:4, range_too_large|:1}`)
  — examined here; it is a symptom of the identical-retry cascade, not a distinct fault.

## 5. Qwen disqualification (D-GO3(ii))

`databricks-qwen35-122b-a10b` probe (`probe-`, not among the 3): **FAIL both clauses** —
post-repair conformance 1/5 = 20% (four unrepairable `read_guideline` calls, same-class
breaker at 4), 0 findings through the emit gate. Reasoning-list `content` envelope observed.
Agnosticism remains PROVEN-on-fidelity / ASSERTED-on-outcome; Qwen is **disqualified** from
the outcome axis on this evidence.

## 6. Low-ceiling confirmation (D-BUD6) — PASS

`lowceiling-` (not among the 3), `--max-tokens 8000`: `stop_reason=ceiling`,
`run_completed=False`, grounded partial returned, no crash. `billed_tokens=11,285` is a
**one-turn overshoot** inherent to a stop-when-exceeded gate (the crossing request
completes before the post-turn check), not runaway; the exact bound is proven offline by
`test_runaway.py`. The code gate behaves identically under a live model.

## 7. Remediation (Phase-3 scope, under prereg v2)

- **R1** — `read_guideline` fetch now TRIPLE-resolves: `lookup_citation` → requirement-index
  citation-display map → `rule_doc_id`. The `not_found` message rewritten to teach the
  recovery path ("enumerate, then pass a rule_doc_id; do not retry this call"). New
  composition test rounds BOTH `citation` and `rule_doc_id` for all 15 entries → **30/30**.
- **R2** — diminishing-returns armed only after turn 5 (grace window); breaker unchanged.
- **R3** — prompt adds absence-claim discipline (open the section before claiming absence; a
  heading/contents line is evidence of presence). Prompt guards stay green.
- **Prereg v2** — same gate structure, same frozen baseline (0.107, `{B-08, C-01, C-02}`),
  new SHA, three fresh scored runs. Drafted separately; **held for reviewer adjudication**.

## 8. Implementation status (for the reviewer)

R1/R2/R3 implemented; new R1/R2 tests pass; prompt guards
(`test_no_eval_leakage`, `test_prefix_stability`) green. **Two EXISTING tests now fail
because they assert the pre-remediation behavior R1/R2 fix, and both files are outside the
work order's allowed-files list — the executor did NOT edit them and is holding the commit
for reviewer authorization** (details in the plan report / SUMMARY). No scored run was
executed under the remediation; no verdict is declared here beyond the reviewer's NO-GO on
`c123f7e`.
