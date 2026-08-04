# Real-Model Low-Ceiling Confirmation (D-BUD6)

**This run is declared NOT among the 3 scored runs (D-BUD6).**

Plan 03-14's synthetic forced-runaway driver proves the AGENT-03 ceiling gate offline
(`tests/agents/review/test_runaway.py`). This run confirms the **same code gate** behaves
identically under a live tool-calling model.

## Run configuration

| Field | Value |
|---|---|
| Model | `databricks-meta-llama-3-3-70b-instruct` (baseline-matched) |
| Prefix (excluded from the 3) | `lowceiling-` (written at run time) |
| Deliberately low ceiling | `--max-tokens 8000` |
| Other bounds | `--max-wall-clock 600 --max-turns 80` |
| Artifacts | `runs/lowceiling-1.json`, `.jsonl`, `-summary.json` |
| `prereg_commit_sha` | `c123f7e66a170d7fa6715122a00bbf262a62f4aa` |

## Observed behavior

| Check | Result |
|---|---|
| `stop_reason` | **`ceiling`** ✓ (the token-ceiling gate fired) |
| `run_completed` / `abort_reason` | `False` / `ceiling` ✓ (aborted-vs-completed is self-evident) |
| `report.stop_reason` / `budget_exhausted` | `ceiling` / `True` ✓ |
| Grounded partial returned | Yes — a valid `FaultReport` was returned (0 findings emitted before the ceiling; an empty grounded partial, no crash) |
| Every finding carries evidence | Vacuously satisfied (0 findings) |
| Crash | None |
| `turns` / `total_tool_calls` | 3 / 2 |
| `billed_tokens` | **11,285** |

## Overshoot note (reported honestly, not gamed)

`billed_tokens=11,285` exceeds the `8,000` ceiling by one turn's worth. This is the
**inherent semantics of a stop-when-exceeded gate**, not overspend: `over_ceiling()` is
`billed_tokens >= max_tokens`, checked at the turn boundary, so the model request that
crosses the threshold completes before the loop stops on the next check — an in-flight
request cannot be un-sent. The gate fired **promptly** (3 turns) and did **not** run away;
the bounded one-turn overshoot would be identical at the 1,600,000 scored ceiling. The
exact-bound behavior is separately proven offline by `test_runaway.py`; this run confirms
the gate trips and returns a grounded partial under a real model.

This document states no recall figure and no phase GO/NO-GO.
