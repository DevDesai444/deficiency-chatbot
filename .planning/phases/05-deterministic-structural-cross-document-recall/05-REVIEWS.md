---
phase: 5
reviewers: [codex]
reviewed_at: 2026-08-07T08:09:13Z
plans_reviewed: [05-01-PLAN.md, 05-02-PLAN.md, 05-03-PLAN.md, 05-04-PLAN.md, 05-05-PLAN.md, 05-06-PLAN.md, 05-07-PLAN.md]
note: >
  Only codex was available as an independent reviewer. claude is this runtime (skipped
  for independence); gemini/opencode/qwen/cursor/coderabbit are not installed and no local
  model server was running. codex inspected the live source tree, so its findings carry
  file:line anchors. This is a single-reviewer pass — treat "Consensus" below as codex's
  prioritized findings, not multi-model agreement.
---

# Cross-AI Plan Review — Phase 5

## Codex Review

## Summary

The plans are strong at the roadmap level: they preserve the deterministic/general guardrail, split the work into sensible legs, and put verification commands on nearly every task. As written, though, the phase is **high risk** because several plan interfaces do not compose with the current code. The biggest blockers are: deterministic detectors use fresh ledgers while emit gates require issued spans; Wave 3 still has a `src/evals/run.py` write conflict; the shared envelope omits required `dedup_key` / top-level confidence tier; structural detection only really specifies aggregate checks despite claiming three families; and several enum/signature assumptions conflict with the existing code.

## Strengths

- Clear phase boundary: deterministic structural, reference-graph, precedent recall, plus anti-overfitting guard.
- Good intent around "general by construction": fixture_b, rename invariance, no-constant scan, and corpus-gated real eval are the right categories of checks.
- Good dependency insight for `emit_finding.py`: moving all new emit gates into Plan 01 avoids one major Wave 3 conflict.
- Good persistence motivation in Plan 02: replacing RRF score misuse and avoiding per-query corpus re-embedding are necessary.
- Strong insistence on grounded, re-openable spans and downgrade-not-drop behavior.

## Concerns

- **HIGH — Empty ledger vs emit-gate validation will block every detector.** Plans 03, 04, 05, 06, and 07 instantiate fresh `RetrievalLedger()` objects, then call emit gates that are planned to reject spans unless `ledger.was_issued(...)` is true. Current emit gates enforce this pattern in [emit_finding.py](/Users/DEVDESAI1/dev/deficiency-chatbot/src/tools/emit_finding.py:54). Deterministic scans over cache/table indexes do not naturally "issue" spans, so findings will likely all become `ToolRejected`.

- **HIGH — Plan 01 assumes enum values that do not exist.** Existing [faults.py](/Users/DEVDESAI1/dev/deficiency-chatbot/src/schemas/faults.py:18) has `Tier.VERIFIED/CORROBORATED/ADVISORY` and `EvidenceClass.CODE_VERIFIED/CHECKLIST/QUOTE_ANCHORED/MODEL_JUDGMENT`. Plans reference `Tier.CANDIDATE`, `EvidenceClass.RETRIEVED`, and uppercase string values like `"VERIFIED"` / `"CODE_VERIFIED"`, which are not current enum values.

- **HIGH — D-ENV1 is not fully implemented in Plan 01.** The decisions require a shared envelope with `dedup_key` and a single confidence-tier field. Plan 01 adds anchors and `leg_tag`, but no `dedup_key` and no top-level `confidence_tier`. D-CON1 consolidation cannot work as specified.

- **HIGH — Wave 3 still has a file conflict.** Plans 03 and 04 both modify `src/evals/run.py` in the same wave, even though Plan 04 says there is "no file overlap." Move gate registration to a later integration plan or serialize those plans.

- **HIGH — Structural plan claims three check families but only designs aggregate recompute.** Plan 03 does not concretely implement summary-vs-detail mismatch or result-exceeds-spec-limit. The planted `doc_c.pdf` exceedance is prose, but D-STR5 restricts Phase 5 to addressable table cells, so that success criterion is not actually covered.

- **HIGH — Structural table algorithm likely will not detect the proposed fixture.** The fixture uses label/value table shape like `Impurity | % w/w`, with `Total Impurities` in the label column and `0.12%` in the value column. The proposed algorithm scans the label cell itself and then basis "same column" or "left in row," so it will read labels instead of numeric values unless label-value pairing is specified.

- **HIGH — Reference anomaly detection is under-specified.** Plan 04 says "determine anomaly" and "numeric value cross-refs," but does not define how a table-level reference resolves to a specific value row, how labels align, or how X1 is derived. The fixture text also contains an internal inconsistency: it describes `Compound A 0.10%` vs `NMT 0.15%` as a contradiction, but that complies; the contradiction is `Compound B 0.18% > NMT 0.15%`.

- **HIGH — `follow_reference` Plan 07 omits an actual current signature mismatch.** Current [follow_reference.py](/Users/DEVDESAI1/dev/deficiency-chatbot/src/tools/follow_reference.py:18) has no `db_path`; Plan 07 tests call `db_path=...`. The plan must explicitly add `db_path` and update/verify all call sites.

- **MEDIUM — Plan 02 `.npy` atomic write is wrong if implemented literally.** `np.save(tmp_path, arr)` appends `.npy` when the suffix is not `.npy`, so writing to `{final}.tmp` can create `{final}.tmp.npy` and make `os.replace(tmp, final)` fail. Use an opened file handle or a temp path ending in `.npy`.

- **MEDIUM — Persisted index lookup lacks a clear key source.** Sidecars are keyed by cache key, but `search_corpus` needs to know each doc's key at query time. If `CorpusIndex`/manifest does not expose that key, Plan 02 needs to add it or maintain an index manifest.

- **MEDIUM — Dense score handling can zero lexical-only hits.** Plan 02 stores dense scores only for `dense_order`; fused lexical-only hits get `0.0` despite having computable cosine scores. Since legacy computes scores for all chunks, store dense scores for all chunk ids or compute for every fused id.

- **MEDIUM — Anti-overfitting guard is too source-scan-heavy.** Regex scans are useful tripwires, but they are easy to bypass via imported constants, string joins, generated patterns, or fixture tuning. Behavior-based transfer tests should be the primary guard, with source scans as secondary.

- **MEDIUM — CTD literal policy is inconsistent.** Context says guard must reject CTD-family section paths, while Plan 04/06 exempts CTD regex inside `re.compile`. That may be valid as a general extractor, but the exemption needs to be explicitly encoded as "registered general pattern," not a blanket `re.compile` carve-out.

- **MEDIUM — Precedent verification is too weak for SC3.** Plan 06 reports precedent but does not hard-fail if no precedent candidate appears. Plan 05 has unit tests with monkeypatched FAISS, but the phase success criterion says the system surfaces precedent candidates and measures that family.

- **MEDIUM — Plan 05 threshold constant conflicts with its own guard.** It says `0.6` may appear inside `_load_precedent_threshold`, but the verification regex rejects all inline floats except `0.0`/`1.0`. Either exempt the threshold-loader function or remove the fallback literal.

- **LOW — Fixture binary artifacts need reproducibility.** Committing PDFs/DOCX is fine, but the plan should also commit a small generator script or fixture manifest containing the planted facts. Otherwise fixture intent is hard to diff and audit.

## Suggestions

- Add a deterministic span-issuance contract before Plans 03–05: either detectors call a helper like `issue_cached_span(ledger, span_id)` after byte-exact validation, or new emit gates accept cache-originated deterministic spans through a separate validation path.
- Fix Plan 01 schema first: add `dedup_key`, top-level `confidence_tier`, and use existing enum values unless the plan explicitly extends `Tier` / `EvidenceClass` with tests for backward compatibility.
- Move all `src/evals/run.py` CLI wiring for structural/reference/precedent into Plan 06 or Plan 07 to remove the Wave 3 conflict.
- Rewrite Plan 03 around explicit table model primitives: label cell, value cell, numeric column/row basis, units, comparator, and Decimal rounding. Add tests matching the real fixture table shape, not a simplified one-column test.
- Make result-exceeds-spec-limit table-based in the fixture, or defer that part honestly to Phase 7. Do not use prose in Phase 5 if D-STR5 remains binding.
- Strengthen Plan 04 with a concrete value-contradiction algorithm: reference edge resolution, target table selection, label matching, comparator extraction, unit compatibility, and confidence downgrade rules.
- Add a real `precedent-gate` that hard-fails only when the local rulebook FAISS asset is available, and reports a structured skip otherwise. Include it in `phase5-gate`.
- Replace broad source regex scans with an AST/token-based guard plus registered allowlists for general vocab, regex patterns, and algorithm constants.

## Risk Assessment

**Overall risk: HIGH as written.** The architecture is directionally sound, but several blockers would prevent the plans from passing their own gates without ad hoc fixes during execution. The most important corrections are the ledger/emit contract, schema compatibility, Wave 3 file conflict, and concrete structural/reference algorithms. After those are tightened, the phase drops to medium risk: still complex, but much more executable and enforceable.

---

## Consensus Summary

Single independent reviewer (codex) this pass — no cross-model agreement to compute. The findings below are codex's prioritized issues, grouped for the planner to action via `/gsd-plan-phase 5 --reviews`.

### Agreed Strengths

- Deterministic/general guardrail preserved; clean leg boundaries (structural / reference-graph / precedent / anti-overfitting guard).
- Per-task verification commands and grounded, re-openable spans with downgrade-never-drop discipline.
- Sound dependency call: consolidating all new emit gates into Plan 01 to avoid a Wave 3 conflict.

### Agreed Concerns (highest priority — the blockers to fix before execution)

1. **Span-issuance vs emit-gate contract (HIGH).** Deterministic detectors use fresh `RetrievalLedger()`s but emit gates reject non-issued spans (`emit_finding.py:54`) → every deterministic finding risks `ToolRejected`. Define a cache-origin span-issuance path before Plans 03–05.
2. **Schema drift in Plan 01 (HIGH).** Plans reference non-existent `Tier.CANDIDATE` / `EvidenceClass.RETRIEVED` and uppercase string enum values vs the real `faults.py:18` enums. Reconcile or explicitly extend with backward-compat tests.
3. **D-ENV1 envelope incomplete (HIGH).** Missing `dedup_key` and top-level `confidence_tier` → D-CON1 consolidation can't work. Land the full envelope in Plan 01.
4. **Wave 3 file conflict (HIGH).** Plans 03 and 04 both write `src/evals/run.py` in the same wave. Serialize or move gate wiring to Plan 06/07.
5. **Structural leg under-specified (HIGH).** Three families claimed, only aggregate recompute designed; table algorithm reads label cells not values; result-exceeds-spec is prose while D-STR5 binds Phase 5 to addressable cells.
6. **Reference-anomaly algorithm under-specified + fixture bug (HIGH).** No edge→value resolution defined; fixture mislabels the contradiction (real one is `Compound B 0.18% > NMT 0.15%`).
7. **`follow_reference` signature mismatch (HIGH).** Plan 07 tests pass `db_path=` but current `follow_reference.py:18` has no such param.

### Divergent Views

None — single reviewer.

### Actionable next step

Fixes cluster in **Plan 01** (envelope + enums + emit-gate contract) and **Wave 3 sequencing** — address those first, then the per-leg algorithm specificity in Plans 03/04. Re-plan with:

```
/gsd-plan-phase 5 --reviews
```
