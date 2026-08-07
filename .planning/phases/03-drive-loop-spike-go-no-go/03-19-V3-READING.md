# Phase 03 — v3.2 GO/NO-GO Reading (against `e8de55a`)

Senior-reviewer gate reading of the v3.2 scored set, recorded verbatim. Set closed; no
re-roll. Numbers via the frozen `metrics`/`statistics` paths (`03-19-V3-RUN-NOTES.md`).

> Note: the v3.2 scored artifacts these numbers come from live at `runs/agent-run-v3.2-{1,2,3}.{json,jsonl,-summary.json}` (restored from `fe4c408` after commit `4ecf0af` overwrote the `agent-run-v3-*` names in place with the v3.3 set).

## Ruling (verbatim)

> REVIEWER RULING (v3.2, against e8de55a): NO-GO — clauses (a) and (b) both fail (overall
> 0.071 < baseline 0.107; regulatory regressed from v2 0.200 to 0.000; C-01 and B-08 lost all
> three runs). Set closed, no re-roll.

## Frozen-path numbers

| family | run1 | run2 | run3 | median | baseline |
|---|---:|---:|---:|---:|---:|
| absence_of_evidence | 0.000 | 0.000 | 0.000 | 0.000 | 0.091 |
| cross_reference_integrity | 0.286 | 0.286 | 0.286 | 0.286 | 0.286 |
| derivation_plausibility | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| regulatory_framing | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| overall (mvr1381) | 0.071 | 0.071 | 0.071 | **0.071** | 0.107 |

`found_set` identical all 3 runs: `{C-02, C-04, MS-01, MS-02, MS-04}` — **C-02 preserved;
C-01 and B-08 lost all runs.** Governing `prereg_commit_sha` = `e8de55a`.

## Reviewer diagnosis (verbatim) — corrects the executor's report

> Executor's report had one wrong claim reviewer verified on disk: run_oracles WAS called
> 3/2/5 times per run (JSONL row counts). The summary's 0/0/0 is a WIRING BUG at loop.py:368
> (checks isinstance(raw_result, list) but run_oracles_tool returns dict) — tracker never
> fires, coverage reminder consequently keeps telling the model to call a tool it already
> called (loop.py:202). That misled the "prompt problem" diagnosis.

**Executor correction, on the record:** the v3-run-notes r5/r6 claim that "`run_oracles` was
not called in any run" is **wrong**. Per the reviewer's JSONL row counts, `run_oracles` was
called 3/2/5 times; the summary `0/0/0` was the loop.py wiring bug. The true signal is
**called-but-leads-not-converted**, not un-called — a re-open/conversion gap, not a
tool-invocation gap.

## v3.3 remediation (drafted under prereg v3.3, held for adjudication)

- **U1** — fix the loop tracker + telemetry to read run_oracles' dict return (was
  `isinstance(list)`), so the summary reports real oracle engagement.
- **U2** — coverage reminder: flag "un-called" only when truly un-called; when
  called-but-no-lead-taken, flag "surfaced N leads, none re-opened — re-open with get_section".
- **U3** — absence lead (`expected_row_absent`) next_call now cites a **resolvable** rule
  (`21 CFR 211.194`), not the nonsense `read_guideline(citation='read_guideline enumerate')`.

## Decision-point note (reviewer's call — recorded, executor does not choose)

If v3.3 still fails to recover C-01 and B-08 in the median runs, the reviewer flagged a
decision point bigger than another remediation cycle (two months of iteration have not moved
recall past the pre-recalibration 0.071 on this corpus). Options the reviewer named:
(α) code-inject oracle leads at turn 1 (bypass prompt-steering); (β) restructure the loop's
role (deterministic pipeline for recall, agentic loop for verify/challenge only);
(γ) escalate the orchestrator to Claude via Anthropic SDK for reasoning-heavy synthesis,
local models for cheap fan-out. **The reviewer's call, not the executor's.**
