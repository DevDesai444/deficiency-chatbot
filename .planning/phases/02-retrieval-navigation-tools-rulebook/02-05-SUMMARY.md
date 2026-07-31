---
phase: 02-retrieval-navigation-tools-rulebook
plan: 05
subsystem: agent-tools
tags: [pydantic, span-grounding, retrieval-ledger, hash-mismatch, typed-rejection, rulebook, fault-schema]

# Dependency graph
requires:
  - phase: 01-ingestion-foundation
    provides: "ingest.anchors.open_span/HashMismatch (the re-open/verify primitive, reused verbatim, called twice per finding), schemas.documents.SpanID/NormalizedText/OffsetRun"
  - phase: 02-retrieval-navigation-tools-rulebook (Plan 02-01)
    provides: "tools.ledger.RetrievalLedger (was_issued), tools.errors.ToolRejected (the typed rejection sentinel shape)"
  - phase: 02-retrieval-navigation-tools-rulebook (Plan 02-02)
    provides: "rulebook.store.rulebook_nt_for (RULEBOOK store read-back), rulebook.store.write_chunk/RuleChunk"
provides:
  - "emit_finding -- the ONLY path a Fault can exist through: dual byte-exact re-open (submission + rule spans), ledger-membership gate, store-membership gate, typed rejections on every failure path"
  - "A test-proven fabrication-rejection guarantee (TOOLS-03): a deliberately altered quote is REJECTED at the gate (ToolRejected, reason_code=not_byte_exact), never emitted then caught"
  - "A test-proven, in-code-documented demonstration that TOOLS-03's not_unique rejection is structurally unreachable under D-EF1's span-ID-only contract"
affects: ["Phase 3 (agent drive loop wires emit_finding as the 6th/final tool)", "Phase 5 (adversarial verifier re-opens rule_span_id's citation via guidance_refs)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual-store grounding gate: open_span called exactly twice per finding, once against the CORPUS NormalizedText, once against the RULEBOOK NormalizedText -- never a third, parallel re-implementation of hash verification"
    - "Ledger-before-hash ordering: ledger.was_issued() is checked BEFORE open_span's byte-exactness check, so a span the model never actually retrieved is rejected regardless of whether it would have hash-matched (closes the 'lucky guess' spoofing threat, T-02-19)"
    - "Typed ToolRejected sentinel returned (never raised) on every failure path -- ordering: no_rule_citation -> not_retrieved_this_session (submission) -> not_retrieved_this_session (rule) -> wrong_store (submission) -> wrong_store (rule) -> not_byte_exact (submission) -> not_byte_exact (rule) -> success"
    - "Raw/canonical divergence as a uniqueness proof: two spans over textually-identical canonical text (same hash) but different offsets are distinguished by minting one occurrence through the ligature-fold normalization path (raw 'speciﬁcity' -> canonical 'specificity'), so a test can assert which SPECIFIC offset's evidence was returned, not just that the text matched"

key-files:
  created:
    - src/tools/emit_finding.py
    - tests/tools/test_emit_finding.py
  modified: []

key-decisions:
  - "Added a rulebook_cache_dir passthrough parameter (default rulebook.store.DEFAULT_RULEBOOK_CACHE_DIR) to emit_finding, threaded into rulebook_nt_for's cache_dir argument -- the plan's given interface signature/code omitted this, but every existing rulebook.store consumer (including all of tests/rulebook/test_store.py) explicitly threads an isolated cache_dir for D-RB6 offline test isolation; without it, Task 2's fixture-based tests could not resolve a rule span without depending on (or leaking into) the shared data/ directory."

patterns-established:
  - "A tool-boundary grounding gate is the ONLY constructor of its output type (Fault) -- no other code path in src/tools/ or src/agents/ may construct a QUOTE_ANCHORED Fault directly."

requirements-completed: [TOOLS-03]

# Metrics
duration: ~12min
completed: 2026-07-31
---

# Phase 2 Plan 05: emit_finding Grounding Gate Summary

**`emit_finding` — the dual byte-exact grounding gate that is the only path a `Fault` can exist through, with a test that proves a fabricated quote is rejected at the tool boundary, not emitted then caught.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-31 (worktree base recovery + context gathering)
- **Completed:** 2026-07-31T08:26:15Z
- **Tasks:** 2/2
- **Files modified:** 2 (both created)

## Accomplishments
- `emit_finding` re-opens BOTH the submission quote and the cited rule clause via `ingest.anchors.open_span` (reused verbatim, never reimplemented) before a `Fault` can exist.
- Every one of the five D-EF1 rejection paths (not-retrieved, not-byte-exact, wrong-store x2, no-citation) is independently proven by an honestly-named test — no test combines multiple sub-cases under a name that only describes a subset of what it checks.
- The central acceptance test (`test_fabricated_quote_cannot_be_emitted`) proves REJECTION by asserting the return *type* (`ToolRejected`, not `Fault`) after tampering one character of an otherwise-legitimately-issued span — matching the ROADMAP's `FileEditTool.validateInput` analogy exactly.
- `test_span_id_unique_by_construction` proves — not merely documents — that TOOLS-03's `not_unique` rejection condition is structurally unreachable: two spans over textually-identical canonical content (same hash, different offsets, one routed through ligature-fold normalization so its RAW form diverges) both resolve cleanly, and the success path's `Fault.evidence` traces to the cited span's own offset specifically.
- The success path constructs a `Fault` with `evidence_class=QUOTE_ANCHORED`, `evidence` equal to the freshly re-opened RAW submission substring, and `guidance_refs` carrying both the rule citation and `requirement_id` — reusing the existing, unmodified `schemas.faults.Fault`/`EvidenceClass`.

## Task Commits

Each task was committed atomically:

1. **Task 1: emit_finding.py — dual re-open, ledger, and store-membership validation** - `c88fba7` (feat)
2. **Task 2: the fabrication-rejection proof + full, honestly-named rejection-path test suite** - `a4bd589` (test)

**Plan metadata:** (this commit) `docs(02-05): complete emit_finding grounding-gate plan`

_Note: Task 1 ships the plan's fully-specified implementation code (no ambiguity requiring a preceding failing test of its own — see TDD Gate Compliance below); Task 2 is the substantive RED-then-immediately-GREEN proof suite, run and passing on first execution against Task 1's already-correct implementation._

## Files Created/Modified
- `src/tools/emit_finding.py` - The grounding gate: `emit_finding(corpus, submission_span_id, rule_span_id, ledger, verdict, requirement_id="", rule_citation="", title="", detail="", rulebook_cache_dir=DEFAULT_RULEBOOK_CACHE_DIR) -> Fault | ToolRejected`. Checks, in order: `rule_span_id is None` -> ledger membership (submission, then rule) -> store membership (submission via `corpus.cached_entry`, then rule via `rulebook_nt_for`) -> byte-exactness (`open_span` x2, `HashMismatch` caught) -> `Fault` construction.
- `tests/tools/test_emit_finding.py` - 7 tests: the fabrication-rejection proof, all 5 D-EF1 rejection paths (each independently, honestly named), and the grounded success path. Builds real fixtures end-to-end via `build_corpus_index` (Plan 02-01) + `fixture_chunk`/`write_chunk` (Plan 02-02) — no hand-rolled fakes.

## Decisions Made
- **Added `rulebook_cache_dir` parameter to `emit_finding`** (Rule 3 — blocking-issue auto-fix). The plan's given Task-1 code interface called `rulebook_nt_for(rule_span_id.doc_id)` with no `cache_dir` argument, defaulting to the module's shared `data/rulebook_cache` path. Every existing `rulebook.store` consumer — including all of `tests/rulebook/test_store.py` and the `fixture_chunk` builder Task 2's own `<action>` block directs tests to use — explicitly threads an isolated `cache_dir` for D-RB6's offline test-isolation discipline (tests must never depend on or leak into the shared `data/` directory). Without this parameter, Task 2's tests could not resolve a rulebook chunk written to a `tmp_path`-scoped store, since `emit_finding` would look in the wrong (and non-test-isolated) location. The parameter defaults to `rulebook.store.DEFAULT_RULEBOOK_CACHE_DIR`, so the plan's literal production call shape (omitting the argument) is preserved; only test callers need to pass it explicitly. Verified no leakage: `data/rulebook_cache/` does not exist on disk after the full test run.
- Kept the plan's given Task-1 code otherwise verbatim, including its two required in-code design notes (`structurally UNREACHABLE`, `KNOWN LIMITATION`) — both preserved exactly as specified so the acceptance-criteria greps for them pass.
- `test_span_id_unique_by_construction`'s two same-text, different-offset spans use the ligature-fold normalization path (raw `"speciﬁcity"` → canonical `"specificity"`, mirroring the already-proven `normalize("ﬁle").canonical == "file"` fixture in `tests/ingest/test_normalize.py`) rather than the guarded-dehyphenation path, specifically to avoid any dependency on the committed dehyphenation lexicon's word list — keeping the proof deterministic and lexicon-independent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `rulebook_cache_dir` passthrough parameter to `emit_finding`**
- **Found during:** Task 1 (writing `emit_finding.py`), confirmed necessary while designing Task 2's fixtures
- **Issue:** The plan's given code calls `rulebook_nt_for(rule_span_id.doc_id)` with no `cache_dir` argument. `rulebook_nt_for`'s real signature (`src/rulebook/store.py`) takes an explicit `cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR`, and every existing test of the rulebook store (`tests/rulebook/test_store.py`, 15+ call sites) passes an isolated `tmp_path`-scoped `cache_dir` — never the default — per D-RB6's offline/isolated-test discipline. Task 2's own `<action>` block directs tests to build rule fixtures via `fixture_chunk` + `write_chunk`, both of which return/require a `tmp_path`-scoped `cache_dir`. Without a way to pass that same directory into `emit_finding`, its rule-span lookups would target the wrong (shared, non-isolated) directory and never resolve, making every rule-grounded test path unimplementable without breaking test isolation.
- **Fix:** Added `rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR` as an additional keyword parameter to `emit_finding`, threaded into the `rulebook_nt_for(rule_span_id.doc_id, cache_dir=rulebook_cache_dir)` call. Default value preserves the plan's literal production call shape.
- **Files modified:** `src/tools/emit_finding.py`
- **Verification:** All 7 tests in `tests/tools/test_emit_finding.py` pass using isolated `tmp_path`-scoped rulebook stores; confirmed `data/rulebook_cache/` does not exist on disk after the full suite runs (no leakage into the shared directory).
- **Committed in:** `c88fba7` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for Task 2's tests to exist at all without violating D-RB6's offline/isolation discipline or depending on shared, mutable `data/` state. No scope creep — the fix is additive (a new optional parameter with a backward-compatible default) and touches only the one file the plan already scoped for Task 1.

## TDD Gate Compliance

Both tasks carry `tdd="true"`, but the plan's own structure pairs them as **implementation-first, proof-second** rather than the classic single-task RED→GREEN cycle: Task 1's `<action>` block gives the complete `emit_finding` implementation verbatim (no ambiguity to test-drive), and Task 1's own `<done>` criterion states "full test coverage is Task 2" — Task 1's `<verify>` is an import smoke check, not a pytest run. Task 2 is the substantive test-writing task, and its 7 tests passed on first run against Task 1's already-committed implementation (no red-then-fix cycle was needed; the implementation matched the specified behavior exactly).

Git log gate sequence: `feat(02-05)` (`c88fba7`) precedes `test(02-05)` (`a4bd589`) — the reverse of the canonical `test` → `feat` ordering. This is a deliberate plan-level design choice (the plan pre-verifies its own implementation via extensive plan-checker review referenced throughout the plan text — "plan-checker Blocker 1/2", "plan-checker Warning 2/6"), not a process deviation on this execution's part. Flagged here per the TDD gate-compliance instruction for transparency.

## Issues Encountered
None beyond the one documented deviation above. All 7 new tests passed on first execution; no debugging cycle was required.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `emit_finding` is ready to be wired as the 6th agent-facing tool once Phase 3's drive loop exists; its signature (`corpus`, `submission_span_id`, `rule_span_id`, `ledger`, `verdict`, `requirement_id`, `rule_citation`, `title`, `detail`) already matches D-RI2(3)'s "enumerate → citation → read_guideline(citation) → issued rule span-IDs → emit" zero-translation flow.
- The known, documented limitation that `schemas.faults.Fault` has no structured `rule_span_id` output field (only `guidance_refs: list[str]`) remains open for a future phase (Phase 5's verifier) if it needs to re-open the *exact* rule span a `Fault` cites — resolving it requires either a `Fault` schema change (currently off-limits) or a side-channel span store. Documented in-code (`KNOWN LIMITATION` comment in `emit_finding.py`) and here for visibility; not a regression of this plan.
- No blockers for this plan's own scope. Whole-phase-so-far regression (`tests/tools/` + `tests/rulebook/`, 58 tests) is green.

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*

## Self-Check: PASSED

- FOUND: `src/tools/emit_finding.py`
- FOUND: `tests/tools/test_emit_finding.py`
- FOUND: `.planning/phases/02-retrieval-navigation-tools-rulebook/02-05-SUMMARY.md`
- FOUND: commit `c88fba7` (Task 1)
- FOUND: commit `a4bd589` (Task 2)
