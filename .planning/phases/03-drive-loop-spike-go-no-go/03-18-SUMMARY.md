# Plan 03-18 Summary — the measurement (raw numbers only, no verdict)

**This plan reports. It does not judge.** The GO/NO-GO reading is the senior reviewer's at
plan 03-19, against the committed pre-registration `c123f7e`. No statement of GO, NO-GO,
pass or fail appears here.

## Pre-flight

- **Telemetry fix (reviewer amendment):** committed `9d6ab9b` — `BudgetLedger.total_tool_calls`
  property + typed `tool_call`/`rejection` JSONL rows + regression test. `eb28867`
  exonerated (one-line log truncation, unrelated). Guards green
  (`test_prefix_stability`, `test_no_eval_leakage`).
- **Re-smoke (after the fix, unscored, `smoke-` prefix, scratch dir outside `runs/`):**
  `total_tool_calls=3` (was 0), JSONL row types `tool_call:3` + `turn:4`, protocol holds.
- **Smoke A1/A4/A3 (settled before the scored set):** A4 tool-message protocol on
  Databricks **holds** across turns (prompt tokens accumulate 2957→8311, no 400s); A1
  `usage` present but `cached_tokens=0` (cache payoff unmeasured until Phase 6, blocks
  nothing); A3 schemas validated on the first live turn (no `BadRequestError`).
- **§10 pre-run dual-resolve probe (installed store, immediately before run 1):**
  leg A (`lookup_citation` display) **0/15** (by design), leg B (`rule_doc_id` fallback)
  **15/15**, dual-resolve **15/15 — PASS**. Store has not drifted; the `absence_of_evidence`
  rule-retrieval confounder is not present.

## Frozen configuration (identical across all 3 runs, only `--run-index` differs)

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
  --prereg .planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION.md
```

- Temperature fixed at 0 (`chat_completion_tools` default). Git HEAD at run time:
  `9d6ab9b9e3871fcbd1b3f636e0b13e5ed834d80e`.
- **`--max-turns 80`** is the reviewer-confirmed 03-16 value frozen in the pre-registration
  §5, superseding plan 03-18's literal `--max-turns 50` (that text predates calibration).
  Reviewer confirmed the supersession in the 03-18 work order.
- Nothing changed between runs (D-GO2(ii)).

## Scored-run raw results (frozen `metrics`/`statistics` paths only)

Provenance: all three summaries carry `prereg_commit_sha =
c123f7e66a170d7fa6715122a00bbf262a62f4aa`, matching the committed pre-registration; every
D-TEL1(i) provenance field populated; each `agent-run{N}.json` re-scores LLM-free via
`evals.capture.load_captured` / `evals.run score`.

| Run | run_completed | stop_reason | turns | total_tool_calls | billed_tokens | continuation_count | faults emitted | matched found_set |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | True | `diminishing-returns` | 7 | 7 | 46,869 | 0 | 0 | `[]` |
| 2 | True | `breaker` | 19 | 17 | 204,516 | 1 | 2 (both fp) | `[]` |
| 3 | True | `diminishing-returns` | 7 | 7 | 47,112 | 0 | 0 | `[]` |

**recall_by_family — `mvr1381` (governing scored doc; matches the frozen baseline table):**

| family | run1 | run2 | run3 | **median** | baseline median |
|---|---:|---:|---:|---:|---:|
| absence_of_evidence | 0.000 | 0.000 | 0.000 | **0.000** | 0.091 |
| cross_reference_integrity | 0.000 | 0.000 | 0.000 | **0.000** | 0.286 |
| derivation_plausibility | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 |
| regulatory_framing | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 |
| **overall** | 0.000 | 0.000 | 0.000 | **0.000** | 0.107 |

`end_to_end` per run (`mvr1381`): run1 tp=0 fp=0 fn=28; run2 tp=0 **fp=2** fn=28; run3 tp=0
fp=0 fn=28. `minispec`: run1 tp=0 fp=0 fn=4; run2 tp=0 **fp=2** fn=4; run3 tp=0 fp=0 fn=4.
Precision is **reported, not gated** (D-GO1(ii)); fp is well under the 125 flag line.
Overall recall median computed via `statistics.median([0.000, 0.000, 0.000]) = 0.000`.

**Matched `found_set` is empty in all three runs** — the baseline `found_set
{B-08, C-01, C-02}` was not reproduced. (Stated as a raw fact; the gate reading is the
reviewer's.)

### Pre-registered telemetry readings (recorded, not interpreted)

- **D-TEL3 matrix `(reason_code, half)` — reported separately, never summed:**
  run1 `{not_found|: 2}`; run2 `{not_found|: 4, range_too_large|: 1}`; run3 `{not_found|: 2}`.
  `span_invention_count` (`not_byte_exact|submission`) = **0** all runs;
  `rule_never_read_count` (`not_retrieved_this_session|rule`) = **0** all runs. The
  dominant rejection is `not_found|` — the model invoked **tool names that do not exist**.
- **D-TEL4 fidelity (Llama):** `pre_repair_malformed=0` and `post_repair_malformed=0` in all
  three scored runs; no `structured.py` repairs were needed. `first_malformed_turn_index=0`
  (no malformed-arg call). (The `not_found` rejections are unknown-tool-name calls, a
  distinct class from malformed-args.)
- **D-TEL5 continuation:** `continuation_count = 0` in runs 1 and 3, `= 1` in run 2. Per the
  pre-registration, `continuation_count = 0` across a run means its nudge floor **was not
  exercised and is UNPROVEN, not validated**; run 2 exercised it once (1 of a permitted 5).
- **D-ORC2 oracle conversion:** `oracle_leads_surfaced/reopened/emitted = 0/0/0` in all
  runs — `run_oracles` was not invoked by the model in any scored run.

### WATCH ITEM for the 03-19 gate read — the breaker tripped in scored run 2

Pre-registration §5 flagged that the breaker tripped in calibration run 2 and required its
`(reason_code, half)` matrix be examined at the gate **if it recurs in a scored run**. It
recurred: **run 2 `stop_reason=breaker`**. Its rejection matrix at the trip was
`{not_found|: 4, range_too_large|: 1}` (17 tool calls over 19 turns). Recorded here for
the reviewer's gate examination; not interpreted.

## Qwen tool-fidelity probe (D-GO3(ii)) — `03-QWEN-FIDELITY-PROBE.md`

Model `databricks-qwen35-122b-a10b`, `probe-` prefix (not among the 3). Result:
`stop_reason=breaker` at 4 consecutive `post_repair_malformed`, 2 turns, 1 valid dispatch,
0 findings.
- **Clause (a) FAIL** — post-repair conformance 1/5 = 20% (`structured.py` repaired none of
  4 malformed `read_guideline` calls), far below the >= 95% bar.
- **Clause (b) FAIL** — 0 findings through the emit gate.
- `optional_param_near_miss` is **not persisted** by the `RunSummary` schema (Phase-4
  telemetry gap); the observed pattern was wholesale `post_repair_malformed`, not the
  one-optional-param near-miss, so Pitfall 6's single-mode-tool remedy is not clearly
  indicated. Qwen also returned a reasoning-list `content` envelope (pydantic warning).
- Honest scope recorded verbatim: agnosticism PROVEN on the tool-fidelity axis and
  ASSERTED on the outcome axis.

## Real-model low-ceiling confirmation (D-BUD6) — `03-LOW-CEILING-CONFIRMATION.md`

Llama, `lowceiling-` prefix, `--max-tokens 8000`. `stop_reason=ceiling`,
`run_completed=False`, `abort_reason=ceiling`, `budget_exhausted=True`, no crash, grounded
partial (0 findings) returned. `billed_tokens=11,285` — a one-turn overshoot inherent to a
stop-when-exceeded gate (not runaway; the exact bound is proven offline by
`test_runaway.py`). **Declared NOT among the 3.**

## Artifacts committed (explicitly staged; user's dirty files excluded)

- Nine scored: `runs/agent-run{1,2,3}.json`, `.jsonl`, `-summary.json`.
- Probe: `runs/probe-1.json`, `.jsonl`, `-summary.json`.
- Low-ceiling: `runs/lowceiling-1.json`, `.jsonl`, `-summary.json`.
- Docs: `03-QWEN-FIDELITY-PROBE.md`, `03-LOW-CEILING-CONFIRMATION.md`, this summary.
- The unscored smoke run stayed in `smoke-scratch/` (outside `runs/`) and is **not**
  committed.

## Handoff to 03-19

The reviewer's gate read against `c123f7e` consumes: overall recall median **0.000** vs
baseline **0.107**; matched `found_set` **empty** (baseline `{B-08, C-01, C-02}` not
reproduced); zero families moved off 0.0; the **run-2 breaker trip** watch item with its
`(reason_code, half)` matrix; `continuation_count = 0` in 2 of 3 runs (floor UNPROVEN);
`run_oracles` never invoked; the dominant `not_found` unknown-tool-name rejection pattern;
and the Qwen fidelity FAIL on both clauses. No task here declares the verdict.
