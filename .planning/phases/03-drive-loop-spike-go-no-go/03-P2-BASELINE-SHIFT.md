# P2 Baseline Shift Disclosure

Plan 03-01 re-ran the SC4 retrieval gate after the `rapidocr-fallback` parser fix and parser-versioned cache invalidation. The gate was run offline by forcing `parse.pdf.ocr_page` to return `None`, matching the D-RB6 local path and avoiding a live Databricks OCR call.

## Measured Shift

| Metric | Committed pre-P2 | Post-P2 measured | Delta | Attribution |
|---|---:|---:|---:|---|
| `retrieval_recall` overall recall@k | 0.875 | 0.857 | -0.018 | P2 parse fix |
| `retrieval_recall` exact-identifier subset | 0.643 (mvr1381 7/12) | 0.571 (mvr1381 6/12, minispec 2/2) | -0.071 | P2 parse fix |
| `recall_by_family` overall | 0.071 | **not re-measured in this plan** | - | see plan 03-12 (D-LOOP2) |

Gate output:

```text
RETRIEVAL-GATE FAILED: exact-identifier subset not 100% -- {'mvr1381': {'overall': 0.7142857142857143, 'exact_identifier_subset': 0.5, 'n': 28, 'n_hard': 12}, 'minispec': {'overall': 1.0, 'exact_identifier_subset': 1.0, 'n': 4, 'n_hard': 2}}
```

## Which Anchors Moved

No `mvr1381` exact-identifier anchor became newly reachable in the offline post-P2 measurement. A direct old-behavior simulation (discarding blocks/figures on `rapidocr-fallback` pages) and the post-P2 parser both measured 6/12 for the hard subset in this environment.

Post-P2 reachable hard anchors:

- `A-01` — `99.9%`
- `A-05` — `377.49`
- `A-09` — `<1226>`
- `C-01` — `11477`
- `C-02` — `0.15`
- `C-04` — `0.14`

Post-P2 still-unreachable hard anchors:

- `A-02` — `13439`
- `A-10` — `0.92%`
- `A-12` — `05/10/2016`
- `B-04` — `6559.876`
- `B-05` — `27.0%`
- `B-07` — `9.83`

## D-PRE1(a) Attribution Statement

Any change in the recall baselines between the committed values and the D-LOOP2 re-measurement is attributable to the P2 parse fix and the cache invalidation delivered in plan 03-01, not to the agent loop.

## What Is Deliberately Not Done Here

`src/evals/baseline/recall_by_family.json` is not rewritten by this plan; D-LOOP2 (plan 03-12) re-measures it live 3x and the reviewer confirms any new reference.

Neither committed baseline JSON under `src/evals/baseline/` was edited. The retrieval-gate failure is preserved as a measurement result rather than silenced by ratcheting the baseline inside this plan.
