# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-30)

**Core value:** Given any directory of submission documents, reliably find the real FDA/ICH compliance deficiencies — all faults and only faults that exist — each cited to the exact passage that proves it.
**Current focus:** Phase 0 — Eval Harness (the continuous gate on every later phase)

## Current Position

Phase: 0 of 6 (Eval Harness) — 7 phases total, numbered 0–6
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-07-30 — Roadmap created; 25 v1 requirements mapped across 7 phases (100% coverage)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: — (no data yet)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Roadmap-shaping decisions for current work:

- [Roadmap]: Eval harness sequenced FIRST (Phase 0) and run continuously as the gate — the only defense against the measured 7%-recall trap; recall-by-failure-family is the milestone's primary metric.
- [Roadmap]: FDA/ICH rulebook (RULES-01..04) folded into Phase 2 (before the spike) so the go/no-go loop risk is isolated from external rulebook-sourcing risk.
- [Roadmap]: Budgets/stop-conditions land as CODE gates in Phase 3 (AGENT-03); the full cost governor (triage + caching + compaction) hardens in Phase 6 (COST-01/02).
- [Roadmap]: Cross-document retrieval (reference graph + `follow_reference`) lands in Phase 4 — the prerequisite the deferred v2 threshold checks depend on.

### Pending Todos

None yet.

### Blockers/Concerns

- **Requirement count correction:** REQUIREMENTS.md footer (and the roadmap task) stated "24 v1 requirements," but the enumerated IDs total **25** (INGEST 3 + RULES 4 + TOOLS 2 + AGENT 3 + GROUND 3 + DETECT 5 + EVAL 3 + COST 2). All 25 are mapped; coverage counts updated to 25/25.
- **Uncommitted working tree:** a partial planner/summariser/sandwich/workers redesign is uncommitted on branch `CLI_for_folders` — build on it, do not clobber. Roadmapper made no commits.
- **Stale docs debt:** repo README/PIPELINE/DIAGNOSIS/RELIABILITY/PHASES describe a removed 3-layer AutoGen design — trust code, not those docs.

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Detection depth | Threshold-arithmetic (S2–S5, P3, Q3C/Q3D), method-validation/stability suites, semantic reference-graph contradictions (X3/X5/X6), biologics + Modules 1/2/4/5, resolution hints | Deferred to v2 | 2026-07-30 (requirements) |
| Infrastructure | Docling unified parse upgrade; optional Claude-orchestrator variant | Deferred to v2 | 2026-07-30 (requirements) |

## Session Continuity

Last session: 2026-07-30
Stopped at: ROADMAP.md + STATE.md written; REQUIREMENTS.md traceability populated (25/25 mapped). Awaiting user approval of the roadmap.
Resume file: None
