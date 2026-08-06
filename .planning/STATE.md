---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: ready_to_plan
stopped_at: Phase 04 complete (verified passed) — ready to plan Phase 05
last_updated: "2026-08-06T01:10:00Z"
last_activity: 2026-08-06 -- Phase 04 complete (3/3 plans, verified passed; absence 0.000→1.000)
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 45
  completed_plans: 42
  percent: 44
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-05)

**Core value:** Given any directory of submission documents, reliably find the real FDA/ICH compliance deficiencies — all faults and only faults that exist — each cited to the exact passage that proves it.
**Current focus:** Phase 5 — Deterministic Structural & Cross-Document Recall (β) — ready to plan

## Current Position

Phase: 5
Plan: Not started
Status: Ready to plan
Last activity: 2026-08-06

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

- **[Phase 5 / RECALL-05] Give the absence threshold real dynamic range.** Phase 4's absence-gate threshold `0.04` sits ABOVE the RRF score ceiling (~0.0328 = `2/(60+1)`, k=60 two-ranking fusion in `src/retrieval/hybrid.py`), so the retrieval leg is currently non-discriminative — every applicable requirement emits (a sanctioned D-ABS2 over-emit, pruned downstream). RECALL-05 must introduce a retrieval signal that actually separates addressed vs. absent requirements; until then Phase 7 inherits the full pruning load. Recorded in 04-VERIFICATION.md "Phase-5 Handoff / Known Limitation".

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

Last session: 2026-08-05T18:40:11.869Z
Stopped at: context exhaustion at 75% (2026-08-05)
Resume file: None
