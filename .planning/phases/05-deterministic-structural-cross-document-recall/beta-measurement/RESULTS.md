# β-Engine Recall Measurement — Real Eval Corpus (Phase 5 close)

**Date:** 2026-08-08 · **Branch:** CLI_for_folders · **Mode:** measurement only (no verdicts, no golden re-capture, no baseline/found_set edits; all frozen assets read-only).

## Method

- Ran the complete deterministic pipeline — **absence + structural + reference + precedent** legs — over each **non-held-out** eval document, each ingested in isolation (temp dir, single doc) so the **held-out witness `spec32s41` is excluded** (anti-circularity) and no cross-doc pollution occurs.
- Non-held-out docs: **mvr1381** (`data/32s43-validation-related-compounds-method.pdf`, PDF) and **minispec** (`src/evals/dataset/docs/mini_spec.docx`, DOCX).
- **Precedent leg structured-skips** as designed — `data/rulebook.faiss` is absent.
- Absence threshold read from the frozen `baseline/absence_threshold.json` (0.04).
- Combined grounded-candidate `FaultReport` captured per doc, then scored through the **frozen path** (`python -m evals.run score --captured … --doc-id …`). Captured reports + per-doc metrics committed alongside this note; machine-readable roll-up in `beta-measurement-summary.json`.
- Harness: `$CLAUDE_JOB_DIR/tmp/beta_measure.py` (not committed — scratch).

## Headline (frozen-path score, scoreable run)

| Doc | overall recall | tp | fp | fn | recall_by_family (all) | B-08 | C-01 | C-02 |
|-----|---------------|----|----|----|------------------------|------|------|------|
| mvr1381 | **0.000** | 0 | 109 | 28 | absence 0.000 · derivation 0.000 · cross_ref 0.000 · regulatory 0.000 | **not matched** | **not matched** | **not matched** |
| minispec | **0.000** | 0 | 1 | 4 | all 0.000 | n/a | n/a | n/a |

**No GT item is matched by the live deterministic engine on the real corpus** under the frozen matcher — including B-08, C-01, C-02. (For contrast, the committed baseline's `tp=2` (C-01, C-02) comes from the **curated golden report** `golden:mvr1381_run3`, not from a live deterministic run.)

## True engine emit profile (un-relabeled — real over-emit for Phase 7)

The scoreable run above requires a doc-id **relabel bridge** to map ingest's content-hash ids to eval ids; that bridge suppresses the structural leg (see Finding 1). The **true** per-leg emit (no relabel) is:

| Doc | absence | structural | reference | precedent | TOTAL |
|-----|---------|-----------|-----------|-----------|-------|
| mvr1381 | 8 | 3 | 101 (97 UNRESOLVED_REF + 4 VALUE_CONTRADICTION) | skipped (FAISS) | **112** |
| minispec | 1 | 2 | 0 | skipped (FAISS) | **3** |

The legs **do fire** on real data (structural finds MIN/MAX/MEAN table-aggregate mismatches on mvr1381). The dominant volume is **reference UNRESOLVED_REF (97 on mvr1381)** — references into documents not in the isolated corpus (incl. the excluded/other submissions) resolve to `unresolved`. This is the recall-biased over-emit the Phase-7 verifier prunes via `dedup_key`.

## Findings (flagged; no fixes applied — measurement only)

**Finding 1 — scoring bridge suppresses the structural leg (`wrong_store`).** `evals.run`'s `_relabel_corpus_doc_id` (needed to score by eval doc-id) renames the **manifest** doc_id but not the **corpus cache** (still keyed by content-hash). `emit_structural_finding` then rejects every structural candidate with `reason_code=wrong_store` (`claim_span_id.doc_id does not resolve in the CORPUS store`). Empirically: structural emits **3 (mvr1381) / 2 (minispec) without relabel**, **0 with relabel**. So the "structural = 0 / structural family recall 0.000" in the scoreable run is a **measurement-infra artifact, not an engine gap**. Absence and reference emit survive the relabel; structural does not. → Phase-6/7 (or a follow-up) needs a relabel that also re-keys the cache, or a scoring path that doesn't rename.

**Finding 2 — raw deterministic candidates do not match GT under the frozen matcher.** Even the surviving absence (8) + reference (101) candidates on mvr1381 match **0** GT items: `evals.match.matches()` requires a candidate to align with a specific GT deficiency record, and the recall-biased per-requirement / per-reference over-emit does not carry that identity. GT-matching in the committed baseline comes only from **curated golden faults**. → The deterministic engine is a grounded-candidate **generator**; converting candidates into GT-matching findings is the **Phase-7 verifier / interpretive-tail** job. These 0.000 figures are the honest **entry numbers** for that layer, not a regression against Phase 5's synthetic-fixture SCs (which validated the mechanisms by construction).

## Bearing on the golden ratchet (B-08 et al.)

The live deterministic engine matches **0 GT on the real corpus (B-08, C-01, C-02 all unmatched)**. So no golden `found_set` ratchet (B-08 included) is satisfiable from the engine's live output — independently reconfirming that adding B-08 to `found_set` would break, not strengthen, the zero-TP-lost gate. Any ratchet must follow a deliberate **golden re-capture** decision, reviewer-gated.

## Entry numbers handed to Phase 6/7

- Deterministic engine live recall on real corpus (frozen matcher): **0.000** (both docs) — grounded candidates only, no GT alignment yet.
- Over-emit to prune/verify: **mvr1381 ≈ 112 candidates** (dominated by 97 UNRESOLVED_REF; 4 VALUE_CONTRADICTION; 8 absence; 3 structural), **minispec ≈ 3**.
- Precedent leg unmeasured until `data/rulebook.faiss` is built (structured-skip today).
- Structural leg contributes on real data (3/2) but is invisible to the current scoring path — fix the relabel/cache bridge before trusting scored structural numbers.
