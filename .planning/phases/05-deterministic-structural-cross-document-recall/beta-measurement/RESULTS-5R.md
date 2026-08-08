# β-Engine Recall Re-Measurement (5R) — Real Eval Corpus

**Date:** 2026-08-08 · **Branch:** CLI_for_folders · **After:** 5R-R1 (evidence population) + 5R-R2 (relabel/cache bridge fix). **Mode:** measurement only (read-only frozen assets; no golden/baseline/found_set/matcher edits).

## Pre-registered targets (stated BEFORE the run — reviewer protocol)

1. **C-01 matched on mvr1381** (structural MAX 11477-vs-12601).
2. **C-02 + MS-01 + MS-02 matched on minispec**.
3. **Overall recall > 0.071** (baseline floor) on at least the aggregate.
4. **B-08 measured and reported either way** — its localization may need more than R1/R2; report, do not force.

Method identical to the prior measurement: non-held-out mvr1381 + minispec; spec32s41 held-out excluded; all four legs (precedent structured-skips, FAISS absent); scored via frozen `evals.run score --captured`. Captured reports overwrite the prior (pre-5R) ones in this dir; pre-5R numbers are preserved in `RESULTS.md` + git history.

## Actuals (frozen `evals.run score --captured`)

| Doc | overall recall | tp | fp | fn | recall_by_family |
|-----|---------------|----|----|----|------------------|
| mvr1381 | **0.179** | 5 | 100 | 23 | absence 0.091 · derivation 0.200 · cross_ref 0.143 · regulatory 0.400 |
| minispec | **0.250** | 1 | 2 | 3 | cross_ref 0.333 (others 0.000) |
| **aggregate** | **0.1875** (6/32) | 6 | 102 | 26 | — |

**Matched GT IDs:** mvr1381 → `A-09, A-11, B-01, C-01, C-06`; minispec → `MS-01`.

**Over-emit profile (Phase-7 handoff):** mvr1381 **112 emitted → 5 matched** (absence 8, structural 3, reference 101 = 97 UNRESOLVED_REF + 4 VALUE_CONTRADICTION; precedent skipped); minispec **3 emitted → 1 matched** (absence 1, structural 2). The 100/2 FP is the recall-biased over-emit the Phase-7 verifier prunes via `dedup_key`.

## Pre-registered targets — scorecard

1. **C-01 on mvr1381 — ✅ MET** (`C-01_matched=true`; structural MAX 11477-vs-12601, evidence carries `11477 | basis: …`).
2. **C-02 + MS-01 + MS-02 on minispec — ⚠️ PARTIAL.** `MS-01` **matched ✅**. `MS-02` **not matched**. `C-02` is an *mvr1381* GT id (not minispec) in the eval set and is **not matched** — the target wording appears to have conflated it. Reported honestly rather than forced.
3. **Overall recall > 0.071 — ✅ MET** (mvr1381 0.179, minispec 0.250, aggregate 0.1875 — all above the 0.071 floor; up from **0.000** pre-5R).
4. **B-08 measured & reported — ✅ (reported).** `B-08` **not matched** by the live engine on mvr1381; its localization needs more than R1/R2 (a specific structural/reference alignment) — flagged for Phase 7, not forced.

## Net

The 0.000 was a **delivery failure**, now fixed: with evidence populated (R1) and the relabel/cache bridge repaired (R2) the live deterministic engine recovers **6/32 GT items (0.1875 aggregate)** on the real corpus through the frozen matcher, clearing the 0.071 floor, with C-01 caught end-to-end. Remaining fn (incl. B-08, C-02, MS-02, MS-03/04) + the ~102 FP over-emit are the true entry numbers handed to Phase 6/7. **Golden-ratchet / B-08 `found_set` rulings await the reviewer on this data** (B-08 still unmatched by the live engine → a ratchet would still require a deliberate golden re-capture).

