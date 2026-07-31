---
phase: 02-retrieval-navigation-tools-rulebook
plan: 09
subsystem: retrieval-tools
tags: [rulebook, requirement-index, span-grounding, tools-04, cost-04, d-ri2]

# Dependency graph
requires:
  - phase: 02-retrieval-navigation-tools-rulebook (Plan 01)
    provides: "src/tools/oversized.py persist+preview+handle, src/tools/ledger.py, src/tools/errors.py, src/tools/textsplit.py"
  - phase: 02-retrieval-navigation-tools-rulebook (Plan 02/03)
    provides: "src/rulebook/store.py (lookup_citation, rulebook_nt_for) + real vendored eCFR/ICH/FDA content"
  - phase: 02-retrieval-navigation-tools-rulebook (Plan 06)
    provides: "src/rulebook/requirement_index.py::enumerate_requirements (D-RI2 server-side applicability resolver)"
provides:
  - "src/tools/read_guideline.py -- the 5th and final navigation tool, completing TOOLS-01"
  - "Dual-mode dispatch: citation=None -> compact enumerate rows (RULES-05); citation=<str> -> bounded, span-annotated fetch"
  - "TOOLS-04 persist+preview+handle on an oversized citation-mode fetch (same mechanism as get_section)"
  - "COST-04 still-current dedup stub on a repeat fetch of the same citation"
affects: [phase-3-agent-loop, phase-5-verifier]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-mode tool signature (one optional param toggles enumerate vs fetch) -- Read-with/without-offset shape, D-RI2(1)"
    - "get_section's _render_annotated pattern reused verbatim over the rulebook store (_render_annotated_rulebook)"

key-files:
  created:
    - src/tools/read_guideline.py
    - tests/tools/test_read_guideline.py
  modified:
    - .planning/phases/02-retrieval-navigation-tools-rulebook/deferred-items.md

key-decisions:
  - "Round-trip citation test isolated via a monkeypatched single RequirementEntry (not the real yaml) -- decouples read_guideline's own zero-translation code path from a discovered pre-existing data-granularity mismatch in the real committed requirement_index.yaml"
  - "TOOLS-04 scratch isolation via functools.partial-bound persist_range/load_range/advance_cursor names in the test module, not chdir -- chdir would also relocate the rulebook store's own relative default paths and break real-citation lookup"

patterns-established:
  - "Any future rulebook-adjacent test needing both a real citation lookup AND isolated oversized-scratch handling should monkeypatch the oversized function names in the consuming module's own namespace, never chdir"

requirements-completed: [TOOLS-01, TOOLS-04, RULES-05, COST-04]

# Metrics
duration: 30min
completed: 2026-07-31
---

# Phase 2 Plan 09: read_guideline (5th navigation tool) Summary

**`read_guideline` dual-mode tool (enumerate/fetch, D-RI2) completing all 5 navigation tools; real "21 CFR 211.166" fetch verified end-to-end with TOOLS-04 persist+preview+handle and COST-04 dedup**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-07-31T11:00Z (approx, from first exploration read)
- **Completed:** 2026-07-31T11:15Z
- **Tasks:** 2/2 completed
- **Files modified:** 2 created (`src/tools/read_guideline.py`, `tests/tools/test_read_guideline.py`), 1 modified (`deferred-items.md`)

## Accomplishments
- `read_guideline` implements the complete D-RI2 4-point contract: one optional `citation` param toggles enumerate (server-resolved applicability, never rule text) vs fetch (bounded, span-annotated rule text); an invalid `family` filter reuses `enumerate_requirements`'s own typed rejection, not a re-implementation.
- Fetch mode resolves a REAL Plan-02-03-vendored citation (`"21 CFR 211.166"`) end-to-end: `lookup_citation` -> `rulebook_nt_for` -> per-sentence `cat -n` span annotation, every printed span-ID `ledger.record_span`-ed.
- An oversized citation-mode fetch (proven with `max_chars=200` against the real 2213-char section) is NEVER truncated -- it persists the full range under a handle (`src/tools/oversized.py`, reused verbatim) and returns a bounded, annotated preview + that handle; a follow-up `handle=` call pages forward via `_resume_handle`, mirroring `get_section`'s own oversized branch exactly (plan-checker Blocker 2).
- COST-04 dedup: a repeat fetch of the identical citation returns the `[STILL_CURRENT]` stub via `ledger.check_and_mark_served`.
- All 5 navigation tools (`search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline`) now exist -- TOOLS-01 complete.

## Task Commits

Each task followed RED (test) -> GREEN (feat) TDD:

1. **Test file (both tasks' tests, written upfront):** `2e9a59b` (test) -- RED: `ModuleNotFoundError` since `src/tools/read_guideline.py` didn't exist yet.
2. **Task 1: enumerate mode:** `0b58c1a` (feat) -- GREEN: enumerate dispatch + `handle`/stub wiring; `pytest -k enumerate` (3 tests) passes.
3. **Task 2: fetch mode:** `afb856e` (feat) -- GREEN: `_fetch_citation`/`_resume_handle`/`_render_annotated_rulebook` implemented; full file (9 tests) passes; full Phase 2 suite (`tests/tools/ tests/rulebook/`, 115 tests) passes with zero regressions.

_Note: the test file for BOTH tasks landed in a single `test(...)` commit (`2e9a59b`) since it was authored upfront covering the full plan's behavior spec; Task 1's `-k enumerate` filter and Task 2's fetch-mode tests were verified as genuinely RED before their respective `feat` commits (confirmed via `pytest -k enumerate` at Task 1 and a pre-implementation full-file run at Task 2, both showing the expected failures)._

**Deferred-items update:** part of the final metadata commit (not a task commit) -- documents the citation-granularity finding below.

## Files Created/Modified
- `src/tools/read_guideline.py` - The 5th navigation tool: dual-mode enumerate/fetch dispatch, `_fetch_citation`, `_resume_handle`, `_render_annotated_rulebook`.
- `tests/tools/test_read_guideline.py` - 9 tests: enumerate compact-row shape, family-filter narrowing, invalid-family rejection, zero-translation round-trip (controlled entry), real-citation fetch + annotation, not-found rejection, COST-04 dedup stub, TOOLS-04 oversized persist+preview+handle (2 variants).
- `.planning/phases/02-retrieval-navigation-tools-rulebook/deferred-items.md` - New "From Plan 02-09" entry documenting the citation-granularity mismatch (see Deviations below).

## Decisions Made
- Used `functools.partial`-bound `persist_range`/`load_range`/`advance_cursor` (monkeypatched onto `tools.read_guideline`'s own imported names) for TOOLS-04 scratch isolation in tests, instead of `monkeypatch.chdir` -- chdir would also relocate `rulebook.store`'s relative default paths (`data/rulebook_cache`, `data/defpredict.db`), breaking the real-citation lookup the fetch-mode tests depend on.
- The zero-translation round-trip test uses a monkeypatched single `RequirementEntry` (citation aligned with a real store key) rather than a real enumerate row, isolating `read_guideline`'s own code-path correctness from a discovered pre-existing data issue (see Deviations).

## Deviations from Plan

### Auto-fixed Issues
None — no bugs/missing functionality/blockers arose in this plan's own file scope (`src/tools/read_guideline.py`, `tests/tools/test_read_guideline.py`) that needed inline fixing.

### Out-of-Scope Discovery (logged, not fixed — Scope Boundary rule)

**1. [Pre-existing, Plan 02-06 data] Real `requirement_index.yaml` citations don't resolve via `lookup_citation`**
- **Found during:** Task 1, designing the D-RI2(3)/D-EF1(5) zero-translation round-trip test.
- **Issue:** Built the full real rulebook snapshot (ecfr+ich+fda) and edges, then ran `lookup_citation(e.citation)` for all 15 real `requirement_index.yaml` entries — every single one returns `NOT FOUND`. Root cause: `rulebook.store` keys chunks by whole-source-document citation (e.g. `"21 CFR 211.166"`, `"ICH Q2(R2)"`), while Plan 02-06's reviewed index uses finer subsection/topic-level human-readable citations (e.g. `"21 CFR 211.166(a)"`, `"ICH Q2(R2) -- Glossary: Specificity/Selectivity"`) — a granularity mismatch between two independently-designed schemas.
- **Not fixed:** `rulebook/requirement_index.yaml` is outside this plan's `files_modified`, and D-RI1(3) requires any change to it go through a senior-reviewer session with a version bump (v2 -> v3) — not a drive-by edit from this tool-implementation plan (Rule 4: needs a human decision on re-citation vs. finer store chunking).
- **Verified `read_guideline`'s own code is correct:** `test_zero_translation_citation_round_trip` proves the TOOL performs zero translation using a controlled entry whose citation format aligns with a real store key; `test_fetch_mode_resolves_real_citation_and_annotates_with_span_ids` proves real end-to-end resolution works for citations that DO match the store's key format (`"21 CFR 211.166"`).
- **Concrete effect:** today, an agent that enumerates then immediately fetches the returned citation gets a `not_found` rejection for all 15 real requirement-index entries — this blocks the full `enumerate -> read_guideline(citation) -> emit_finding` flow's practical usability until Plan 02-06's data is re-reviewed. Logged in full in `deferred-items.md` under "From Plan 02-09" with a recommended follow-up.
- **Impact on plan:** None on this plan's own deliverable or test suite (both fully green); flagged for phase-level visibility since it affects the locked D-EF1(5) contract's real-data behavior.

---

**Total deviations:** 0 auto-fixed; 1 out-of-scope discovery logged (not fixed).
**Impact on plan:** read_guideline itself is fully correct and tested; the discovery is a pre-existing upstream (Plan 02-06) data issue requiring senior-reviewer attention, not a defect introduced here.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- All 5 navigation tools (`search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline`) exist, are span-grounded, bounded, and dedup'd — Phase 3's agent-loop go/no-go spike has a complete tool surface to call.
- **Blocker/concern for the phase orchestrator:** the requirement-index citation-granularity mismatch (see Deviations) should be resolved via a senior-reviewer session on `rulebook/requirement_index.yaml` before Phase 3 wires the full `enumerate -> read_guideline(citation) -> emit_finding` agent flow end-to-end, or the agent will hit `not_found` on every real requirement citation it tries to fetch back.

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*
