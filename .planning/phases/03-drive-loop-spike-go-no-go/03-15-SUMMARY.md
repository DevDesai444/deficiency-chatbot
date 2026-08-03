---
phase: 03-drive-loop-spike-go-no-go
plan: 15
status: completed
subsystem: eval-agent-cli
tags: [agent-run, telemetry, d-ver1, events]
key-files:
  - src/evals/run.py
  - src/config.py
  - src/schemas/events.py
  - src/agents/event_bus.py
  - src/agents/review/loop.py
  - tests/evals/test_agent_run_cli.py
  - tests/agents/review/test_verify_nondropping.py
---

# 03-15 Summary: Both-Arms CLI + No-Lost-Findings Proof

## Outcome

Plan 03-15 is complete. The legacy `run` command remains intact, and `agent-run` now exists as a sibling CLI path that builds one corpus-wide review run with one `BudgetLedger`, one `RetrievalLedger`, and one `TurnLog`.

## Commits

| Commit | Type | Description |
|---|---|---|
| `100b5a1` | feat | Added the corpus-wide `agent-run` CLI, API detection-mode flag, additive review events, and D-VER1 tests |

## What Changed

- Added `python -m evals.run agent-run` with `--run-index`, `--run-prefix`, `--max-tokens`, `--max-wall-clock`, `--max-turns`, `--out-dir`, `--model`, and `--prereg`.
- `agent-run` writes the three required artifacts from one naming contract: `{prefix}{run_index}.json`, `{prefix}{run_index}.jsonl`, and `{prefix}{run_index}-summary.json`.
- The run summary provenance serializes `found_set`, including the matched GT ids for the emitted `FaultReport`.
- Added `Settings.detection_mode: Literal["legacy", "agent"] = "legacy"` for the API path only.
- Added additive review events: `agent_turn`, `tool_call`, `budget_update`, and `continuation`; event payloads carry only counters/tool names, not document text or tool args/results.
- Added D-VER1 proof tests showing legacy `verify_and_tier` drops agent-shaped findings while the shipped review path preserves finding count and identity.

## Frozen-Zone Proof

`src/evals/run.py` changed only by adding imports, `cmd_agent_run`, and the `agent-run` subparser registration.

Diff stat for `run.py` in `100b5a1`:

```text
src/evals/run.py | 135 +++++++++++++++++++++++++++++++++++++++++++++++++++++++
1 file changed, 135 insertions(+)
```

Acceptance greps confirmed:

- `cmd_run` / `run_detection` removals in the `run.py` diff: `0`
- `_join_source_text` / `_load_source_text` / `cmd_score` removals in the `run.py` diff: `0`
- `_write_metrics` usage inside `cmd_agent_run`: `0`
- `HARNESS_VERSION` was not bumped; `src/evals/__init__.py` remained clean
- `src/agents/detection/`, including `verify.py` and `challenge.py`, remained clean

The agent path routes loop output directly to `FaultReport` and frozen matching/metrics composition. It does not call `verify_and_tier` or `challenge_faults`; `test_agent_run_source_never_routes_through_dropping_passes` and `test_agent_path_never_imports_the_dropping_passes` guard that boundary.

## Reporting Note

On the agent path, `_verifier_metrics` degenerates to the same effective keep-set as `end_to_end`: `emit_finding` emits `CORROBORATED` findings, and the legacy verifier/challenge passes are bypassed because they are proven dropping. Phase reporting must present that metric as non-independent rather than as a separate verifier-arm measurement.

## Verification

- `PYTHONPATH=src .venv/bin/pytest tests/evals/test_agent_run_cli.py tests/agents/review/test_verify_nondropping.py -q` -> `11 passed, 5 warnings`
- `PYTHONPATH=src .venv/bin/pytest tests/evals -q` -> `94 passed, 5 warnings`
- `PYTHONPATH=src .venv/bin/pytest tests/agents/detection/test_no_eval_leakage.py tests/agents/review/test_prefix_stability.py tests/agents/review -q` -> `96 passed, 5 warnings`
- `PYTHONPATH=src .venv/bin/python -m evals.run --help | grep -q "agent-run"` -> pass
- `PYTHONPATH=src .venv/bin/python -m evals.run agent-run --help | grep -q -- "--run-prefix"` -> pass
- `PYTHONPATH=src .venv/bin/pytest -q` -> `479 passed, 11 skipped, 6 warnings`

## Deviations from Plan

None - plan executed exactly as written under the senior-reviewer frozen-zone amendment.

## Self-Check: PASSED

All 03-15 acceptance criteria were run or covered by the focused tests and greps above. No frozen scoring machinery, matcher, capture module, dataset, golden, or baseline file was edited.
