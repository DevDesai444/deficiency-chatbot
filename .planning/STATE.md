---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: executing
stopped_at: Phase 5 context gathered
last_updated: "2026-08-07T09:24:58.170Z"
last_activity: 2026-08-07 -- Phase 05 execution started
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 52
  completed_plans: 42
  percent: 81
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-05)

**Core value:** Given any directory of submission documents, reliably find the real FDA/ICH compliance deficiencies — all faults and only faults that exist — each cited to the exact passage that proves it.
**Current focus:** Phase 05 — deterministic-structural-cross-document-recall

## Current Position

Phase: 05 (deterministic-structural-cross-document-recall) — EXECUTING
Plan: 1 of 7
Status: Executing Phase 05
Last activity: 2026-08-07 -- Phase 05 execution started

## Performance Metrics

**Velocity:**

- Total plans completed: 45 (Phase 0: 4 · Phase 1: 9 · Phase 2: 9 · Phase 3: 20)
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0 | 4 | - | - |
| 1 | 9 | - | - |
| 2 | 9 | - | - |
| 3 | 20 | - | - |
| 04 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: Phase 3 scored-run + NO-GO close-out
- Trend: — (β phases not started)

**Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 03 P05 | 10min | 3 tasks | 5 files |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Roadmap-shaping decisions for current work:

- [β pivot 2026-08-05]: Phase 3 drive-loop spike is a confirmed **3rd NO-GO** (recall 0.071 < 0.107 baseline; {C-01,B-08} lost every run; absence_of_evidence=0.000). A model-driven loop on self-hosted local models cannot reliably do RECALL. **β adopted**: recall → general deterministic pipeline; agent → write-disabled verifier.
- [β roadmap]: Phases 0–3 preserved verbatim (0/1/2 Complete; 3 Complete-NO-GO, records retained as audit trail). β Phases 4–8 replace the superseded agentic-recall Phases 4–6.
- [β roadmap]: Dependency order — rulebook enrichment + absence enumeration (P4: RULES-06, RECALL-01) → deterministic structural + cross-doc + precedent recall (P5: RECALL-02/03/04/05) → Nemotron serving + weak-model reliability (P6: MODEL-01/02, RELIABILITY-01/02/03) → multi-agent verification + interpretive tail (P7: VERIFY-01..04) → cost governor (P8: COST-01/02/03). EVAL-01/02/03 stay in Phase 0 as the continuous gate.
- [β law — on-premise ONLY]: self-hosted open-weights only (Llama 3.3 70B + Qwen MoE + Nemotron-Super-49B on Databricks); no external LLM API (Claude/GPT) ever. Recall cannot be bought with a stronger hosted model. INF-V2-02 (Claude-orchestrator) permanently excluded.
- [β law — anti-overfitting]: every deterministic recall check stays rulebook/structure/graph-general; a guard test (RECALL-05) proves no submission-specific constant is embedded. The eval corpus is a proxy, never a target — any check tuned to recover a specific item on this corpus fails the guard and we stop.
- [β law — grounding + recall gate preserved]: every finding = verbatim source quote + cited rule; Phase 0 recall-by-family gates every β phase with zero-true-positives-lost.
- [Roadmap heritage]: Eval harness FIRST (Phase 0), run continuously as the gate. Rulebook (RULES-01..04) folded into Phase 2. Budgets/stop-conditions as CODE gates.

### Pending Todos

- **[Phase 5 / RECALL-05] Give the absence threshold real dynamic range.** Phase 4's absence-gate threshold `0.04` sits ABOVE the RRF score ceiling (~0.0328 = `2/(60+1)`, k=60 two-ranking fusion in `src/retrieval/hybrid.py`), so the retrieval leg is currently non-discriminative — every applicable requirement emits (a sanctioned D-ABS2 over-emit, pruned downstream). RECALL-05 must introduce a retrieval signal that actually separates addressed vs. absent requirements; until then Phase 7 inherits the full pruning load. Recorded in 04-VERIFICATION.md "Phase-5 Handoff / Known Limitation". **RECALL-05 scope was EXPANDED 2026-08-06 to also persist the per-submission retrieval index (build once at ingest, query-only embed at search) — see "Phase 5 Pre-Registered Decisions" below.**

### Phase 5 Pre-Registered Decisions (discuss 2026-08-06)

Senior-reviewer decisions made in a discuss session on 2026-08-06. **LOCKED — the next `/gsd-discuss-phase 5` must treat these as decided prior context and NOT re-litigate them; spend questioning only on the OPEN areas below.** Iron guardrail throughout: no submission-specific constant (batch no., doc name, spec value, section path) in any check — general by construction or it does not ship.

**Structural pillar (RECALL-02) — FULLY DECIDED:**

- **Scope = "two + labeled-aggregate recompute".** SC1's two checks (summary-vs-detail value mismatch; result-exceeds-spec-limit) PLUS one general family: a cell LABELED as an aggregate (Total/Sum/Maximum/Minimum/Average/Mean) that disagrees with a deterministic recompute over its own tabulated rows. Captures Table 19 (total 0.14% < single-largest 0.15%) and Table 20 (Max cell 11477 vs true 12601) as ONE general rule, not bespoke checks. The aggregate lexicon is a general label vocabulary (like a stopword list), NOT a corpus constant; the guard must assert it holds no corpus-specific token.
- **Det/interp litmus (= the guard's litmus) = "pure-computation-only".** A check is Phase-5 deterministic ONLY if its verdict is a pure computation (equality / ordering / arithmetic recompute) over ≥2 re-openable values, with ZERO domain-semantic judgment. "Is this the right statistic/method/interpretation?" (r² mislabel, retained outlier, absorptivity spread, linearity judgment) → Phase 7 interpretive tail. A compared "value" MAY resolve from a RULEBOOK rule span (e.g. a spec limit), not only a submission cell — so regulatory thresholds enter via the rulebook, never as inline float constants. Rejected: "allow documented rule-of-thumb" (invites corpus-tuned constants).
- **Grounding anchor = typed `StructuralAnchor`** (sibling of Phase-4 `CoverageAbsenceAnchor`): one claim span + **N** basis span-IDs + a relation enum `{EQUALS, LEQ/ordering, SUM|MAX|MIN|MEAN}` + expected-vs-actual. Re-derivable per D-GATE2 — the verifier RE-RUNS the computation, never trusts the stored snapshot. Cells resolved via `tables.py (table_id,row,col)→SpanID`; each basis span validated against its own store (CORPUS vs RULEBOOK). Rule span attached only when a rule supplies the limit. When a contributing cell is not cleanly addressable, over-emit with a scoping-confidence flag (D-ABS2), never silently drop.
- **Value normalization / tolerance = "exact, unit-aware, abstain-on-doubt" with PRECISION-DERIVED comparison (no epsilon constant).** One general normalizer (strip %, canonicalize NMT/≤/≥ into comparator tags); abstain (emit nothing) on unparseable/mismatched units. Tolerance is NOT a fixed epsilon (a tunable → guard risk) — instead compare at the stated decimal precision of the claim/limit operand (round the finer operand to that precision, then exact-equal or strict-greater). Zero free parameters (data-derived, guard-clean), recall-safe (only suppresses a difference below the coarser operand's own declared resolution), and it MATCHES the USP/ICH General-Notices rounding rule for spec compliance (0.104 vs NMT 0.10 → complies) — so limit-exceedance is regulatorily correct, not a naive exact-ordering false positive.
- **Input surface = addressable table cells ONLY** (`tables.py`). Table structure supplies the comparison relation (rows/cols/labels) for free; prose does not (prose value-pairing requires reading meaning → interpretive → Phase 7). A doc whose manifest reports table-tier unavailable is SKIPPED as a declared boundary — but LOGGED and routed to Phase 7's interpretive tail, never silently dropped (honours the PDF merged-cell best-effort caveat).

**RECALL-05 — EXPANDED to two jobs on the same retrieval surface (`retrieval/hybrid.py`, `tools/search_corpus.py`, `ingest/corpus.py`):**

1. **Dynamic range.** The RRF-fusion score ceiling `2/61 ≈ 0.0328` is below the `0.04` absence threshold, so `absence.py:142`'s "found → not absent" branch is a DEAD branch → emit-everything. Replace the RRF-rank artifact with a signal that actually separates addressed vs absent — reviewer steer: base the addressed/absent decision on an absolute dense-cosine similarity (0–1, real range) with a general threshold.
2. **Persist the per-submission retrieval index (folded in 2026-08-06, user decision).** Today `search_corpus` (`search_corpus.py:42/48/53`) re-chunks, rebuilds BM25, and RE-EMBEDS the ENTIRE submission on EVERY query — O(queries·corpus) embedding, which breaks the "any number of documents, no cap" promise once Phase 5 multiplies query count. Build the index ONCE at ingest (chunks + BM25 + dense embeddings), persist next to the Phase-1 doc cache keyed by the same content hash that makes ingest resumable; `search_corpus` LOADS the prebuilt index and embeds only the QUERY. Feasibility prerequisite, not just an optimization; NOT deferred to Phase 8 (that's the LLM/verifier cost layer).

**STILL OPEN — drive `/gsd-discuss-phase 5` questioning here (the other three of the four selected areas):**

- **Reference graph + contradictions (RECALL-03):** edge types (hyperlinks, "see §X", numeric value cross-refs); representation of broken/unresolved ref vs absent referenced content-or-doc vs cross-doc value contradiction; two-doc anchor shape; reuse of `follow_reference` + `edges.py` provenance (D-RB3: every edge carries a provenance span).
- **Precedent candidate mechanic (RECALL-04):** how precedent similarity surfaces candidates + anchor shape; MUST generalize to an unseen folder (match to OTHER submissions' past deficiencies, not self-recognition of seeded items).
- **Anti-overfitting guard (RECALL-05 guard):** provision a held-out fixture so SAME-LOGIC / THRESHOLD-TRANSFER / RENAME invariants actually execute in stock CI (today they `pytest.skip` without the gitignored corpus).

### Blockers/Concerns

- **Anti-overfitting guard is now CI-enforced but still corpus-gated in parts.** Phase 4 hardened it: NO-CONSTANT is structural (rejects CTD-family `3.2.[SP].` + hardcoded threshold floats), and `test.yml` runs coverage-gate + absence-gate every build plus a `pytest-slow` job. But SAME-LOGIC/THRESHOLD-TRANSFER/RENAME-INVARIANCE still `pytest.skip` in stock GitHub CI (gitignored held-out corpus). When Phase 5 formalizes RECALL-05, provision the held-out corpus (or a committed fixture) so the transfer invariants actually execute in CI.
- **Phase 3 NO-GO is the governing context.** Diagnosis: not wiring — a general reasoning weakness of the local model on lead→get_section→read_guideline→emit_finding conversion and on "a required item is ABSENT" reasoning. β must not re-attempt loop-driven recall. `absence_of_evidence` = 0.000 is the #1 gap Phase 4 exists to close.
- **Do not chase the metric.** mvr1381 is a proxy corpus. β's recall layer must stay general; RECALL-05's guard test is the enforcement, not a suggestion.
- **Build on committed redesign.** The planner/summariser/sandwich/workers redesign is committed and is HEAD — β builds on it (verifier + deterministic recall are sibling packages), does not clobber it.
- **Stale docs debt:** repo README/PIPELINE/DIAGNOSIS/RELIABILITY/PHASES describe a removed 3-layer AutoGen design — trust code, not those docs.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Detection depth | Threshold-arithmetic (S2–S5, P3, Q3C/Q3D), method-validation/stability suites, semantic reference-graph contradictions (X3/X5/X6), biologics + Modules 1/2/4/5, resolution hints (DET-V2-01..05) | Deferred to v2+ | 2026-07-30 (requirements) |
| Infrastructure | Docling unified parse upgrade (INF-V2-01) | Deferred to v2+ | 2026-07-30 (requirements) |
| Infrastructure | Optional Claude-orchestrator variant (INF-V2-02) | **Excluded** — on-premise/privacy constraint (no external LLM API) | 2026-08-05 (β pivot) |

## Session Continuity

Last session: 2026-08-06T20:17:01.666Z
Stopped at: Phase 5 context gathered
Resume file: .planning/phases/05-deterministic-structural-cross-document-recall/05-CONTEXT.md
