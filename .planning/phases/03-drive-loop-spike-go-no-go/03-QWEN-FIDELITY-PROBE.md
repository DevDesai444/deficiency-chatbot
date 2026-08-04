# Qwen Tool-Fidelity Probe (D-GO3(ii)) — measurement, not a verdict

Fidelity measurement only. It does **not** touch the recall gate (D-GO3(i): the frozen
baseline was produced on Llama; running the recall gate on a different model would change
two variables at once). This document reports each pre-registered clause PASS/FAIL against
its own bar and states no phase verdict.

## Run configuration

| Field | Value |
|---|---|
| Model endpoint | `databricks-qwen35-122b-a10b` |
| Prefix (excluded from the 3) | `probe-` (written at run time) |
| Budget | `--max-tokens 400000 --max-wall-clock 300 --max-turns 40` |
| Corpus | scored split (`mvr1381`, `minispec`) |
| Artifacts | `runs/probe-1.json`, `runs/probe-1.jsonl`, `runs/probe-1-summary.json` |
| `prereg_commit_sha` | `c123f7e66a170d7fa6715122a00bbf262a62f4aa` |

Observed: `turns=2`, `stop_reason=breaker`, `billed_tokens=5431`, `total_tool_calls=1`
(one valid dispatch), `pre_repair_malformed=0`, `post_repair_malformed=4`,
`rejections_by_code_half={'post_repair_malformed|': 4}`, `found_set=[]`, 0 faults,
`run_completed=True`.

## Turn-indexed fidelity (Pitfall 3 — degradation-with-depth, not averaged away)

JSONL row trace (row `turn_index` shown):

| row | type | detail |
|---:|---|---|
| 1 | turn | finish=tool_calls, pt=2288, ct=105 |
| 2 | tool_call | `read_guideline` — **the one valid dispatch** |
| 3 | turn | finish=tool_calls, pt=2766, ct=272 |
| 4 | repair (post) | `read_guideline` |
| 5 | rejection | `read_guideline` `post_repair_malformed` half=`''` |
| 6 | repair (post) | `read_guideline` |
| 7 | rejection | `read_guideline` `post_repair_malformed` half=`''` |
| 8 | repair (post) | `read_guideline` |
| 9 | rejection | `read_guideline` `post_repair_malformed` half=`''` |
| 10 | repair (post) | `read_guideline` |
| 11 | rejection | `read_guideline` `post_repair_malformed` half=`''` |

- First valid tool call: model turn 1 (`read_guideline` enumerate). **First malformed
  call: model turn 2** (`first_malformed_turn_index=4` in JSONL-row terms). Every call
  from turn 2 onward was an unrepairable `read_guideline` argument.
- Tool-call attempts: **5 total = 1 valid + 4 `post_repair_malformed`** (`structured.py`
  could not repair the 4). The D-BUD3 same-class breaker tripped at the 4th consecutive
  `post_repair_malformed|` rejection (`breaker_same_class=4`), ending the run.
- Additional observation: Qwen returned a reasoning-list `content` shape (a pydantic
  serialization warning `Expected str … input_value=[{'type':'reasoning', …}]`), i.e. its
  response envelope differs from the flat-string `content` the OpenAI tool path assumes.

## Clause (a) — schema-conformant tool calls at >= 95% of turns

- **Pre-repair malformed rate:** `0` pre-dispatch repairs recorded, but 4 of 5 tool-call
  attempts were unrepairable post-dispatch, so pre-repair conformance is **1/5 = 20%**
  (only turn 1's call was directly valid).
- **Post-repair conformant:** **1/5 = 20%** — `structured.py` repaired none of the 4
  malformed `read_guideline` calls (all became `post_repair_malformed`, which the bar
  counts as failures).
- **Result: FAIL** against the >= 95% post-repair bar.

## Clause (b) — >= 1 finding through the emit gate

- **0 findings** passed the emit gate (`found_set=[]`, `faults_found=False`). The run
  never reached `emit_finding`; it stalled on malformed `read_guideline` calls and the
  breaker stopped it.
- **Result: FAIL.**

## `optional_param_near_miss` counter (Pitfall 6)

The registry maintains `optional_param_near_miss` (`registry.py`), but the `agent-run`
CLI / `RunSummary` schema does **not** persist it, so it is **not available from the
committed run artifact** — a telemetry-coverage gap to flag for Phase 4. From the evidence
that is captured: the observed failure was `post_repair_malformed` (wholesale unrepairable
arguments), **not** the documented one-optional-parameter near-miss pattern. On this
probe the Pitfall-6 remedy (split multi-mode tools into 11 single-mode schemas) is
therefore **not clearly indicated** — the args were not "almost correct with one optional
param missing" but unparseable/unvalidatable outright. Recorded as observed; the counter
itself was not measurable here.

## Honest scope statement (verbatim, D-GO3(iii))

*"Model-agnosticism is PROVEN on the tool-fidelity axis and ASSERTED on the outcome axis.
Phase 4 inherits that as a stated assumption, not a settled fact — if Phase 4 fans out on
Qwen for cost reasons it must first confirm outcome parity."*

On this probe the tool-fidelity axis was **exercised and Qwen did not meet the bar**
(both clauses FAIL). No recall figure is stated for this run, and this document states no
phase GO/NO-GO.
