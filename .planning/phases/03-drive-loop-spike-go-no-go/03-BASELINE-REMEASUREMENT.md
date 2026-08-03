# Phase 03 Baseline Remeasurement

This document records the 03-12 baseline rerun status after the senior-reviewer P0 contamination ruling.

## Senior Reviewer Ruling

The previously reported `0.107` median is **VOID** for eval leakage. It was produced after the detector repair while prompt/planner examples still contained eval-shaped answers:

- Prompt leak inherited from the redesign: the table-summary example used the literal `C-01`/`C-02` answer shape.
- Prompt leak added during repair: the product-spec exceedance example used `B-08`/`MS-04` exact values.

The committed historical `0.071` reference remains historical only. Nothing new is frozen here. The reviewer must confirm the governing D-LOOP2 reference before any pre-registration update or Wave 6 agent run.

## De-Leak Repair

- De-leak commit: `142bf922c09674c27b801efa44fe4488ec9395fd`
- Protected principles retained: summary-cell consistency, spec-exceedance-over-equivalency-framing, and do-not-delete-supported-contradictions.
- Prompt examples were replaced with synthetic values absent from eval anchors.
- Static eval-shaped planner seeds were replaced with structural table scans:
  - maximum-summary cells lower than a summarized row value
  - same-section NMT specification exceedances found from table content
- Leakage guard added: `tests/agents/detection/test_no_eval_leakage.py`.
- Guard result: `.venv/bin/pytest tests/agents/detection/test_no_eval_leakage.py tests/agents/detection/test_baseline_regression_guard.py tests/agents/detection/test_planner_redesign.py -q` -> `29 passed, 5 warnings`.

`src/evals/*`, the matcher, the harness, and committed golden captures were not changed.

## Frozen Run Shape Used

- Model id: `databricks-meta-llama-3-3-70b-instruct`
- Temperature: `0` through the existing detector structured-output path.
- Corpus attempted: non-held-out eval documents `mvr1381` and `minispec`; `spec32s41` remained held out.
- Serialized report: `mvr1381`.
- Run-time git SHA: `142bf922c09674c27b801efa44fe4488ec9395fd`
- Baseline artifacts:
  - `.planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run1.json`
  - `.planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run2.json`
  - `.planning/phases/03-drive-loop-spike-go-no-go/runs/baseline-run3.json`

The runner used the same parse -> split -> group -> `run_detection(..., model="databricks-meta-llama-3-3-70b-instruct")` sequence as the official detector arm, and wrote `capture_provenance(...)` sidecars. All three runs attempted both non-held-out documents and completed with `parse_failures={}`.

## Per-Run Found Sets

| Run | Faults emitted | `found_set` | Overall recall | Wall seconds | Notes |
|---:|---:|---|---:|---:|---|
| 1 | 2 | `["B-08", "C-01", "C-02"]` | 0.107 | 313.365 | Nonblank |
| 2 | 0 | `[]` | 0.000 | 613.188 | Blank; logged truncation retries and one LLM timeout retry |
| 3 | 2 | `["B-08", "C-01", "C-02"]` | 0.107 | 200.394 | Nonblank |

Protected baseline set `{C-01, C-02}` survived in 2 of 3 de-leaked runs.

## Recall By Family

Scored only through `evals.capture.load_captured` -> `evals.metrics.compute_metrics`.

| Family | run1 | run2 | run3 | min | median | max |
|---|---:|---:|---:|---:|---:|---:|
| `absence_of_evidence` | 0.091 | 0.000 | 0.091 | 0.000 | 0.091 | 0.091 |
| `cross_reference_integrity` | 0.286 | 0.000 | 0.286 | 0.000 | 0.286 | 0.286 |
| `derivation_plausibility` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `regulatory_framing` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| overall | 0.107 | 0.000 | 0.107 | 0.000 | 0.107 | 0.107 |

This table is a report to the reviewer, not a frozen governing baseline.

## Named Finding: Blank-Run Instability

`BASELINE-BLANK-RUN-INSTABILITY`: The prior official 03-12 run set had one blank run (`min=0.000`, 1-in-3 blank rate). The de-leaked rerun also has one blank run: run 2 emitted zero final `mvr1381` faults, so the de-leaked blank rate is again 1-in-3.

This instability is material for D-GO2. A later "above baseline" claim should be read against the median only with this variance disclosed.

## Frozen-Harness Metric Inconsistency

Metric regeneration reproduced the reviewer-identified inconsistency under the frozen `evals.metrics` path:

- Nonblank runs have overall `fp=0`.
- The same nonblank runs have per-family FP totals summing to `5`.
- Nonblank runs report verifier `{precision: 1.0, recall: 1.0}`; the blank run reports `n/a_phase0`.

This appears to be behavior of the frozen metric composition, not a P0 detector change. Per D-GO1(iii), no matcher or harness code was edited. Reviewer confirmation is required before treating these regenerated metrics as governing.

## Provenance

| Field | Value |
|---|---|
| `harness_version` | `1` |
| `matcher_version` | `1` |
| `matcher_content_sha256` | `e7857edf3f5c1579e27d95f8cf5c086a9e20a443268ef35de01429c488f2c0ca` |
| `baseline_sha256` | `e680eb8638c811b5b9b1a9c7a585223250fdea66f40cf88611b426ba281a0ae3` |
| `corpus_content_hash` | `e4df7729cdfb3c473b487e66b67404a7c58a7f05a02983fc140f2bd25501ade4` |
| `normalizer_version` | `nfc-wscollapse-gdehyph-lig/1-lex1` |
| `serializer_version` | `reading-order-cells/1` |
| `parser_version` | `pymupdf-blocks/2` |

`src/evals/baseline/recall_by_family.json` was not edited. The pre-registration was not updated. Wave 6 was not started.
