# Phase 03 Baseline Remeasurement

This document records the D-LOOP2 baseline arm remeasurement performed before any agent-arm scored run exists.

## Senior Reviewer Ruling

RULING (senior reviewer, after independent diagnosis): **NEITHER number governs yet.** The `0.000` median is not a baseline; it is a measurement of a broken detector. The redesigned planner/worker chain emitted zero findings (`/tmp/census.json`: `planner_workers=10`, `planner_suspicions=0`, `workers_emitted=0`, `worker_failures=0`, `pre_verify=0`, `post_verify=0`, `pre_challenge=0`, `post_challenge=0`). A direct specialist probe on the TP-bearing sections also returned a validly parsed `findings=[]` with no failure recorded.

Consequences:

- `0.071` remains the committed historical reference. Nothing new is frozen.
- `03-12` stays OPEN.
- A blocking P0 repair task precedes `03-12` completion: `03-12-P0-PLAN.md`.
- The repair must fix the single-shot regression in the redesigned chain without touching the matcher, harness, committed golden captures, or baseline file (D-GO1(iii)).
- Acceptance for P0 is pre-registered: a live single-shot run must re-find both `C-01` and `C-02` in at least 2 of 3 runs, and the missing planner->workers composition test on the real TP-bearing sections must emit at least one candidate finding.
- After P0, `03-12` reruns all three baseline measurements from scratch and freezes whatever median the repaired detector produces, with any persistent `>0.03` divergence from `0.071` disclosed and attributed.
- Do not proceed to Wave 6 (`03-14`) until the repaired baseline is frozen.

Amended D-PRE1 order: P2 -> P1 -> boundary hunt -> P0 repair -> `03-12` rerun -> pre-registration -> agent runs.

Own-error note for the record: the regression predates commit `8760665` in working-tree behavior, but `8760665` committed the redesign without eval validation. The pre-registration checkpoint caught it before agent runs, which is the discipline working as designed.

## Frozen Configuration

- Model id: `databricks-meta-llama-3-3-70b-instruct`
- Temperature: `0` through the existing legacy detector structured-output path.
- Corpus attempted: non-held-out eval documents `mvr1381` and `minispec`; `spec32s41` remained held out.
- Governing serialized report: `mvr1381`, matching the committed `src/evals/baseline/recall_by_family.json` reference generated from `golden:mvr1381_run3`.
- Run-time git SHA before the run set was committed: `c72a31d745d83cae0ec212bfdcd858156d2f0d9b`
- Task 1 artifact commit: `890330f`
- Command shape used for each run:

```bash
PYTHONPATH=src RUN_INDEX=N .venv/bin/python -c '<one-off runner equivalent to evals.run cmd_run: load_eval_set; parse each non-held-out document; split/group sections; run_detection(..., model="databricks-meta-llama-3-3-70b-instruct"); write the mvr1381 FaultReport to baseline-runN.json; write capture_provenance(...) to baseline-runN-summary.json>'
```

The plan's nominal command, `.venv/bin/python -m evals.run run --model databricks-meta-llama-3-3-70b-instruct --out <path>`, currently writes metrics JSON rather than a serialized `FaultReport`. To keep `src/evals/run.py` and the legacy detector arm unchanged, the captures were produced from the one-off runner described above, using the same parse -> split -> group -> `run_detection` sequence as `cmd_run`.

All three runs completed without parse failures or rerolls.

## Re-Scoring Commands

Each committed capture was re-scored without an LLM call:

```bash
PYTHONPATH=src .venv/bin/python -m evals.run score --captured .planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run1.json
PYTHONPATH=src .venv/bin/python -m evals.run score --captured .planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run2.json
PYTHONPATH=src .venv/bin/python -m evals.run score --captured .planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run3.json
```

All three reproduced the same values: overall recall `0.000`, precision `0.000`, `tp=0`, `fp=0`, `fn=28`, and all four family recalls at `0.000`.

## Per-Family Recall

| Family | run1 | run2 | run3 | min | median | max | committed baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| `absence_of_evidence` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `derivation_plausibility` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `cross_reference_integrity` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.286 |
| `regulatory_framing` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| overall | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.071 |

## Per-Run Metrics

| Run | `tp` | `fp` | `fn` | `precision` | `anchor_rate` | `found_set` | faults emitted | wall seconds |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 0 | 0 | 28 | 0.000 | 0.000 | `[]` | 0 | 283.789 |
| 2 | 0 | 0 | 28 | 0.000 | 0.000 | `[]` | 0 | 226.139 |
| 3 | 0 | 0 | 28 | 0.000 | 0.000 | `[]` | 0 | 240.783 |

## Drift Check

`EXCEEDS`

- Committed overall reference: `0.071`
- Remeasured overall median: `0.000`
- Absolute difference: `0.071`
- Pre-registered materiality line: `0.030`

The remeasured median is materially below the committed reference and requires senior-reviewer confirmation before any agent arm runs.

## Protected Set

The protected baseline set is `{C-01, C-02}`. The remeasured baseline arm did not preserve either protected item:

| Run | `C-01` found? | `C-02` found? |
|---:|---|---|
| 1 | no | no |
| 2 | no | no |
| 3 | no | no |

This is a material finding about the reference itself, not about the future agent arm.

## Baseline Variance Reading

The overall recall spread was `min=0.000`, `median=0.000`, `max=0.000`, so run-to-run spread in this three-draw set was `0.000`.

"If the single-shot detector swings widely across its own 3 runs, 'above baseline' is a weaker claim than it looks, and the gate reading must say so."

In this set, the concern is not wide numeric swing. The concern is measurement stability versus the committed reference: all three fresh runs landed at zero recall and lost the protected set.

## Attribution

`03-P2-BASELINE-SHIFT.md` states that any change in the recall baselines between the committed values and the D-LOOP2 remeasurement is attributable to the P2 parser/cache state rather than to the agent loop. The observed overall shift is `-0.071` from the committed `0.071` to the remeasured median `0.000`.

The measured run-to-run variance across this set contributes `0.000` spread. The remaining `0.071` absolute movement is therefore not explained by variance inside the three fresh draws; it is the reportable post-P2 baseline-reference shift that the senior reviewer must confirm before pre-registration.

## What The Committed Baseline Could Not Record

The committed baseline JSON records no model id. This remeasurement records `databricks-meta-llama-3-3-70b-instruct`, making the proposed governing reference model-specific.

## Governing reference proposed for the pre-registration

Proposed governing median values for plan 03-17:

| Metric | Governing median |
|---|---:|
| `absence_of_evidence` | 0.000 |
| `derivation_plausibility` | 0.000 |
| `cross_reference_integrity` | 0.000 |
| `regulatory_framing` | 0.000 |
| overall | 0.000 |

Run-set git SHA before Task 1 commit: `c72a31d745d83cae0ec212bfdcd858156d2f0d9b`

Cross-arm provenance values the agent-run summaries must match:

| Field | Value |
|---|---|
| `harness_version` | `1` |
| `matcher_version` | `1` |
| `matcher_content_sha256` | `e7857edf3f5c1579e27d95f8cf5c086a9e20a443268ef35de01429c488f2c0ca` |
| `baseline_sha256` | `e680eb8638c811b5b9b1a9c7a585223250fdea66f40cf88611b426ba281a0ae3` |

Additional provenance carried by all three baseline sidecars:

| Field | Value |
|---|---|
| `baseline_path` | `src/evals/baseline/recall_by_family.json` |
| `corpus_content_hash` | `e1e6a956399cbf313ff33b8738b870615a5a83ed90389aa0f252687d60f269f2` |
| `normalizer_version` | `nfc-wscollapse-gdehyph-lig/1-lex1` |
| `serializer_version` | `reading-order-cells/1` |
| `parser_version` | `pymupdf-blocks/2` |
| `prereg_commit_sha` | `""` |

`src/evals/baseline/recall_by_family.json` was not edited.
