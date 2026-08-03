# Phase 03 Budget Calibration

## Reviewer Corpus Direction

Senior-reviewer direction for this continuation: calibration runs go on the HELD-OUT corpus only, with artifacts outside scored `runs/` paths. In the current eval registry, the only held-out real submission document is `spec32s41` (`data/32s41-Specification.pdf`). Scored documents `mvr1381` and `minispec` are excluded.

This is the option-c limitation from the plan: the corpus is genuinely held out, but it is a single document, so it cannot exercise multi-document allocation. The measured consumption is therefore a lower-bound/limited calibration signal for D-BUD5. The reviewer sets final ceilings at the checkpoint; the arithmetic below is only the pre-declared proposal mechanism.

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

## Calibration Invocation Contract

Calibration artifacts are written outside `.planning/phases/03-drive-loop-spike-go-no-go/runs/`, under `.planning/phases/03-drive-loop-spike-go-no-go/calibration/`.

Every calibration invocation must pass:

```bash
PYTHONPATH=src .venv/bin/python -m evals.run agent-run \
  --model databricks-meta-llama-3-3-70b-instruct \
  --run-prefix calibration-run \
  --document-split held-out \
  --max-tokens 250000 \
  --max-wall-clock 1800 \
  --out-dir .planning/phases/03-drive-loop-spike-go-no-go/calibration
```

These calibration runs are explicitly not among the 3. Their findings are neither scored nor quoted.

## Measurements

Pending. No calibration command had been executed when the pre-declared multiples above were written.
