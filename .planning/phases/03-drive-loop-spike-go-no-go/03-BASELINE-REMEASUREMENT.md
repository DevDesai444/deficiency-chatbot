# Phase 03 Baseline Remeasurement

This document records the D-LOOP2 baseline arm remeasurement performed before any agent-arm scored run exists.

## Senior Reviewer Ruling

RULING (senior reviewer, after independent diagnosis): **NEITHER number governs yet.** The `0.000` median from the first 03-12 attempt was not a baseline; it measured a broken detector. The redesigned planner/worker chain emitted zero findings (`/tmp/census.json`: `planner_workers=10`, `planner_suspicions=0`, `workers_emitted=0`, `worker_failures=0`, `pre_verify=0`, `post_verify=0`, `pre_challenge=0`, `post_challenge=0`). A direct specialist probe on the TP-bearing sections also returned a validly parsed `findings=[]` with no failure recorded.

Consequences:

- `0.071` remains the committed historical reference until the repaired 03-12 rerun is confirmed.
- A blocking P0 repair task preceded `03-12` completion: `03-11-P0-PLAN.md`.
- The repair fixed the redesigned chain without touching the matcher, harness, committed golden captures, or baseline file (D-GO1(iii)).
- P0 acceptance passed: live single-shot runs re-found both `C-01` and `C-02` in 3 of 3 runs, and the planner->workers composition guard on the real TP-bearing sections emits a candidate finding.
- This 03-12 rerun now freezes the repaired detector's measured median for senior-reviewer confirmation.
- Do not proceed to Wave 6 (`03-14`) until this repaired baseline is confirmed.

Amended D-PRE1 order: P2 -> P1 -> boundary hunt -> P0 repair -> `03-12` rerun -> pre-registration -> agent runs.

## Frozen Configuration

- Model id: `databricks-meta-llama-3-3-70b-instruct`
- Temperature: `0` through the existing legacy detector structured-output path.
- Corpus attempted: non-held-out eval documents `mvr1381` and `minispec`; `spec32s41` remained held out.
- Governing serialized report: `mvr1381`, matching the committed `src/evals/baseline/recall_by_family.json` reference generated from `golden:mvr1381_run3`.
- Run-time git SHA before this repaired run set: `3dc5a8e05f2233becf74383b0a066876fa3755f3`
- Command shape used for each run:

```bash
PYTHONPATH=src .venv/bin/python -u - <<'PY'
# one-off runner equivalent to evals.run cmd_run:
# load_eval_set; parse each non-held-out document; split/group sections;
# run_detection(..., model="databricks-meta-llama-3-3-70b-instruct");
# write the mvr1381 FaultReport to baseline-runN.json;
# write capture_provenance(...) to baseline-runN-summary.json
PY
```

The plan's nominal command, `.venv/bin/python -m evals.run run --model databricks-meta-llama-3-3-70b-instruct --out <path>`, writes metrics JSON rather than a serialized `FaultReport`. To keep `src/evals/run.py` and the legacy detector arm unchanged, the captures were produced from the one-off runner described above, using the same parse -> split -> group -> `run_detection` sequence as `cmd_run`.

Run 1 logged an OCR endpoint timeout on page 47 and continued through the parser fallback; no parse failure was recorded and no reroll was taken. All three runs completed with `parse_failures={}`.

## Re-Scoring Commands

Each committed capture is re-scorable without an LLM call:

```bash
PYTHONPATH=src .venv/bin/python -m evals.run score --captured .planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run1.json
PYTHONPATH=src .venv/bin/python -m evals.run score --captured .planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run2.json
PYTHONPATH=src .venv/bin/python -m evals.run score --captured .planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run3.json
```

## Per-Family Recall

| Family | run1 | run2 | run3 | min | median | max | committed baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| `absence_of_evidence` | 0.091 | 0.091 | 0.000 | 0.000 | 0.091 | 0.091 | 0.000 |
| `derivation_plausibility` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `cross_reference_integrity` | 0.286 | 0.286 | 0.000 | 0.000 | 0.286 | 0.286 | 0.286 |
| `regulatory_framing` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| overall | 0.107 | 0.107 | 0.000 | 0.000 | 0.107 | 0.107 | 0.071 |

## Per-Run Metrics

| Run | `tp` | `fp` | `fn` | `precision` | `anchor_rate` | `found_set` | faults emitted | wall seconds |
|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 1 | 3 | 0 | 25 | 1.000 | 1.000 | `["B-08", "C-01", "C-02"]` | 2 | 314.060 |
| 2 | 3 | 0 | 25 | 1.000 | 1.000 | `["B-08", "C-01", "C-02"]` | 2 | 238.356 |
| 3 | 0 | 0 | 28 | 0.000 | 0.000 | `[]` | 0 | 455.986 |

## Drift Check

`EXCEEDS`

- Committed overall reference: `0.071`
- Repaired remeasured overall median: `0.107`
- Absolute difference: `0.036`
- Pre-registered materiality line: `0.030`

The repaired remeasured median is materially above the committed historical reference and requires senior-reviewer confirmation before any agent arm runs.

## Protected Set

The protected baseline set is `{C-01, C-02}`.

| Run | `C-01` found? | `C-02` found? |
|---:|---|---|
| 1 | yes | yes |
| 2 | yes | yes |
| 3 | no | no |

The repaired baseline arm preserves the protected set in 2 of 3 runs. Run 3 is a material variance finding about the reference itself: the worker path produced candidates, but the live run's final challenged report contained zero mvr1381 findings.

## Baseline Variance Reading

The overall recall spread was `min=0.000`, `median=0.107`, `max=0.107`, so the three-draw spread was `0.107`.

"If the single-shot detector swings widely across its own 3 runs, 'above baseline' is a weaker claim than it looks, and the gate reading must say so."

This set does swing widely: two runs find `["B-08", "C-01", "C-02"]`, while one run emits no final mvr1381 findings. Later "above baseline" claims should be read against the median, but the gate report must disclose that the single-shot reference has a zero-finding draw inside its own N=3 set.

## Attribution

`03-P2-BASELINE-SHIFT.md` states that parse/cache changes can move the baseline reference and must be attributed rather than folded silently into variance. The first 03-12 attempt then showed an additional detector-regression failure: the redesigned planner/worker chain could emit no findings. P0 repaired that detector path by restoring table-contradiction sensitivity, routing bounded Table 19/Table 20 suspicions, preserving untitled worker findings, and preventing challenge from refuting summary-cell contradictions merely because source rows have different labels.

The observed overall shift is `+0.036` from the committed `0.071` to the repaired median `0.107`. The within-set spread is `0.107`, so this is not a stable point estimate. The median increase is attributable to the repaired detector once again finding the historical protected set in two runs, plus one additional absence-of-evidence TP (`B-08`) in those same runs; the zero third run remains a material variance/stability finding to surface at the gate.

## What The Committed Baseline Could Not Record

The committed baseline JSON records no model id. This remeasurement records `databricks-meta-llama-3-3-70b-instruct`, making the proposed governing reference model-specific.

## Governing reference proposed for the pre-registration

Proposed governing median values for plan 03-17:

| Metric | Governing median |
|---|---:|
| `absence_of_evidence` | 0.091 |
| `derivation_plausibility` | 0.000 |
| `cross_reference_integrity` | 0.286 |
| `regulatory_framing` | 0.000 |
| overall | 0.107 |

Run-set git SHA before this 03-12 rerun: `3dc5a8e05f2233becf74383b0a066876fa3755f3`

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
| `corpus_content_hash` | `e4df7729cdfb3c473b487e66b67404a7c58a7f05a02983fc140f2bd25501ade4` |
| `normalizer_version` | `nfc-wscollapse-gdehyph-lig/1-lex1` |
| `serializer_version` | `reading-order-cells/1` |
| `parser_version` | `pymupdf-blocks/2` |
| `prereg_commit_sha` | `""` |

`src/evals/baseline/recall_by_family.json` was not edited.
