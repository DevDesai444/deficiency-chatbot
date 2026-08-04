# Phase 03 Budget Calibration

## Reviewer Corpus Direction

Senior-reviewer direction for this continuation: calibration runs go on the HELD-OUT corpus only, with artifacts outside scored `runs/` paths. In the current eval registry, the only held-out real submission document is `spec32s41` (`data/32s41-Specification.pdf`). Scored documents `mvr1381` and `minispec` are excluded.

This is the option-c limitation from the plan: the corpus is genuinely held out, but it is a single document, so it cannot exercise multi-document allocation. The measured consumption is therefore a lower-bound/limited calibration signal for D-BUD5. The reviewer sets final ceilings at the checkpoint; the arithmetic below is only the pre-declared proposal mechanism.

Reviewer selection recorded from the work order: held-out corpus only; artifacts outside `runs/` scored paths.

## Pre-declared multiples (written before calibration executed)

- `max_tokens = 3 x median billed tokens`
- Billed tokens are `Sum(prompt_tokens + completion_tokens)` across all turns including tool results, per D-BUD5 and Pitfall 8.
- `max_wall_clock_s = 4 x median elapsed seconds`
- Wall-clock includes tool execution time, per D-BUD5.
- The two different multiples are intentional: tool-execution time is heavier-tailed than token count because `search_corpus` re-embeds the corpus per call (Pitfall 7) and Databricks rate-limit backoff reaches 60s per retry (`client.py:19`). A single multiple would make wall-clock the binding constraint for infrastructure reasons rather than agent reasons.

Other frozen loop values, restated for 03-17:

- `max_turns = 50`
- `dr_window = 3`
- `breaker_repeat = 3`
- `breaker_same_class = 4`
- `max_continuations = 5`

Pre-declaration commit SHA: `86572c8ab5bd478ca2646f21f64cb43e537bdb9b`. That commit predates the calibration artifacts.

## Calibration Invocation Contract

Calibration artifacts are written outside `.planning/phases/03-drive-loop-spike-go-no-go/runs/`, under `.planning/phases/03-drive-loop-spike-go-no-go/calibration/`.

The initial pre-declared provisional ceiling command was:

```bash
PYTHONPATH=src .venv/bin/python -m evals.run agent-run \
  --model databricks-meta-llama-3-3-70b-instruct \
  --run-prefix calibration-run \
  --document-split held-out \
  --max-tokens 250000 \
  --max-wall-clock 1800 \
  --out-dir .planning/phases/03-drive-loop-spike-go-no-go/calibration
```

That initial provisional `--max-tokens 250000` clipped run 1 at `251231` billed tokens, so it measured the ceiling rather than the run. The completed calibration samples were rerun with the same held-out split and prefix, with a larger provisional `--max-tokens 1000000` to avoid clipping:

```bash
PYTHONPATH=src .venv/bin/python -m evals.run agent-run \
  --model databricks-meta-llama-3-3-70b-instruct \
  --run-index 1 \
  --run-prefix calibration-run \
  --document-split held-out \
  --max-tokens 1000000 \
  --max-wall-clock 1800 \
  --out-dir .planning/phases/03-drive-loop-spike-go-no-go/calibration
```

```bash
PYTHONPATH=src .venv/bin/python -m evals.run agent-run \
  --model databricks-meta-llama-3-3-70b-instruct \
  --run-index 2 \
  --run-prefix calibration-run \
  --document-split held-out \
  --max-tokens 1000000 \
  --max-wall-clock 1800 \
  --out-dir .planning/phases/03-drive-loop-spike-go-no-go/calibration
```

These calibration runs are explicitly not among the 3. Their findings are neither scored nor quoted.

## Measurements

Only `RunSummary` counter artifacts are committed. FaultReport and JSONL artifacts are left uncommitted because calibration findings are neither scored nor quoted.

| Run | Completed | Stop reason | Billed tokens | Cached tokens | Wall-clock s | Model s | Tool s | Embedding s | Turns | Continuations | Usage missing |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | yes | `diminishing-returns` | 538401 | 0 | 76.948 | 67.135 | 9.409 | 9.060 | 29 | 1 | 0 |
| 2 | yes | `breaker` | 285158 | 0 | 55.492 | 46.634 | 8.448 | 8.260 | 23 | 1 | 0 |

Median billed tokens: `(538401 + 285158) / 2 = 411779.5`.

Median elapsed wall-clock seconds: `(76.948 + 55.492) / 2 = 66.220`.

Median model seconds: `(67.135 + 46.634) / 2 = 56.884`.

Median tool-execution seconds: `(9.409 + 8.448) / 2 = 8.928`.

Median embedding seconds: `(9.060 + 8.260) / 2 = 8.660`.

## Proposed Ceilings for Reviewer Confirmation

- Proposed `max_tokens = ceil(411779.5 x 3) = 1235339`
- Proposed `max_wall_clock_s = ceil(66.220 x 4) = 265`

D-BUD1(c) note: the original `250000` provisional token ceiling was too low for even the held-out single-document calibration and clipped the first attempt. The completed samples used a larger provisional ceiling only to avoid clipping the measurement. The proposed final token ceiling is high enough that reviewer confirmation is required before 03-17 consumes it.

## Reviewer-Confirmed Ceilings (03-16 ruling)

The senior reviewer confirmed the following final ceilings for 03-17 consumption. These SUPERSEDE the proposals above; the proposals are retained only as the pre-declared derivation record.

| Ceiling | Confirmed value | Derivation |
|---|---:|---|
| `max_tokens` | `1,600,000` | Pre-declared `3 x median billed tokens` = `ceil(411779.5 x 3) = 1235339`, then a `~1.3x` two-document adjustment (`1235339 x 1.3 = 1605941`, rounded to `1,600,000`). The calibration corpus was single-document (`spec32s41` only); scored 03-17 runs review **two** non-held-out documents, so the single-doc token measurement is a lower bound and is scaled up rather than consumed raw. |
| `max_wall_clock_s` | `600` | Set as a runaway backstop, not tuned to the `265` proposal. Two-document reviewing plus Databricks rate-limit backoff of up to `60s` per retry (`client.py:19`) makes wall-clock heavy-tailed for infrastructure reasons; `600` gives headroom so wall-clock is a backstop rather than the operative agent-reasoning stop. |
| `max_turns` | `80` | `29` turns were observed on the single calibration document; a `50` cap could bind once two documents are reviewed in one run. Raised to `80` so turns remain a backstop rather than an artificial stop at two-document scope. |
| `dr_window` | `3` | Confirmed unchanged. |
| `breaker_repeat` | `3` | Confirmed unchanged. |
| `breaker_same_class` | `4` | Confirmed unchanged. |
| `max_continuations` | `5` | Confirmed unchanged. |

**Ceilings are BACKSTOPS.** The operative stops are diminishing-returns and the breaker, not the ceilings. Both calibration runs ended via a DR/breaker stop (run 1 `diminishing-returns`, run 2 `breaker`), well inside every ceiling above — no run approached a token, wall-clock, or turn ceiling. The ceilings exist to bound a runaway loop, not to shape normal termination.

**Flag for the phase report — breaker tripped in calibration run 2.** Calibration run 2 stopped via `breaker`. This is recorded as a watch item: if the breaker trips in any *scored* 03-17 run, its `(reason_code, half)` matrix must be examined at the gate before the run's result is accepted, because a breaker stop can mask a loop pathology rather than a clean "nothing left to find" termination.
