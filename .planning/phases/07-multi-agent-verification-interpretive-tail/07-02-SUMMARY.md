---
phase: 07-multi-agent-verification-interpretive-tail
plan: 02
subsystem: verification
tags: [verifier, decorrelation, consensus, grounding, on-prem, llm-jury, pydantic, byte-exact]

# Dependency graph
requires:
  - phase: 07-01
    provides: tests/verify/ scaffold + ScriptedFleetClient + labeled-FP fixture + 9 guarded RED stubs
  - phase: 06
    provides: verifier_prompt + reliability.coerce_and_validate + client.chat_completion_tools + VERIFIER_FLEET/MODEL_LINEAGE
provides:
  - "src/verify/panel.py — panel_for(producer_family) cross-family decorrelation over config.MODEL_LINEAGE/VERIFIER_FLEET"
  - "src/verify/verifier.py — verify_once: isolated write-disabled single verifier call; unsure/parse-fail/error => KEEP (never fabricated)"
  - "src/verify/grounding.py — is_grounded/grounding_reresolves: anchor-type-aware byte-exact re-resolution via ingest.anchors.open_span"
  - "src/verify/consensus.py — consensus: DOWNGRADE only on affirmative grounded majority; single-member panel rule; provably no candidate removal"
  - "src/verify/orchestrator.py — verify_candidates fan-out + consensus-apply-in-place + consolidate (downgrade-never-drop seam)"
  - "src/schemas/llm.py VERDICT.model — additive optional provenance field (EXTEND, not redefine)"
affects: [07-03 orchestrator/coverage, 07-04 interpretive tail, cost governor]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Verifier atoms as pure functions/thin wrappers over Phase-6 machinery — no framework, no new deps (openai pinned 1.109.1)"
    - "Recall invariant enforced in CODE (consensus.py + orchestrator mutate-in-place), never in a prompt"
    - "Decorrelation-in-code: verifier render omits producer CoT; panel excludes producer family via MODEL_LINEAGE"
    - "Byte-exact grounding branches on anchor type (submission_span_id vs absence claim_span_id/sub_threshold_hits)"

key-files:
  created:
    - src/verify/__init__.py
    - src/verify/panel.py
    - src/verify/verifier.py
    - src/verify/grounding.py
    - src/verify/consensus.py
    - src/verify/orchestrator.py
  modified:
    - src/schemas/llm.py

key-decisions:
  - "VERDICT extended with an additive optional `model` field (default='') — guided-decode/probe target (tool_schema_for_databricks) unchanged; probe still collects 6/9."
  - "Absence-branch grounding: claim span is the anchor-type selector; grounding = grounding_span verbatim substring of the re-opened source (byte-exact against open_span when the claim span opens against nt, else against nt.canonical). Deterministic branch stays a strict open_span integrity gate (tamper => False)."
  - "Single-member decorrelated panel (panel_size==1): a lone GROUNDED DOWNGRADE downgrades; lone ungrounded/unsure/KEEP => KEEP (RESEARCH Open Question 2, recall-safe)."
  - "General _DOWNGRADE_CONFIDENCE_FACTOR=0.5 confidence discount on DOWNGRADE — documented general constant, never zeroes/drops, no corpus/submission-specific token."

patterns-established:
  - "Read-only verifier tool list derived from the review registry's own GetSectionArgs/ReadGuidelineArgs via build_tool_schema; in-code (not prompt) guard rejects any emit/write/mutate tool."
  - "consensus consumes a normalized panel-verdict record {verdict, grounded, model} (dict or VERDICT); groundedness precomputed by the orchestrator, consensus stays strict on the bool."

requirements-completed: [VERIFY-01, VERIFY-03]

# Metrics
duration: 40min
completed: 2026-08-14
---

# Phase 7 Plan 02: Verifier Atoms (Wave 1) Summary

**Four verifier atoms landed under src/verify/ — cross-family decorrelation panel, isolated write-disabled verify_once (unsure→KEEP, never fabricated), anchor-type-aware byte-exact grounding re-resolution, and the code-gated affirmative-grounded-majority consensus invariant — flipping all Wave-0 verifier-atom stubs GREEN.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-14 (session)
- **Completed:** 2026-08-14
- **Tasks:** 2 (plus one orchestrator seam deviation)
- **Files created:** 6 · **Files modified:** 1

## Accomplishments
- `panel.py` decorrelation: `panel_for("qwen")` returns no qwen-lineage model; `panel_for(None)` returns the full fleet; never-empty fallback with a structlog warning when a family owns the whole fleet. No hardcoded model names.
- `verifier.py` `verify_once`: family-aware `verifier_system_prompt`; renders ONLY claim + re-opened source + rule (no producer CoT); offers ONLY read-only get_section/read_guideline tools with an in-code write-tool guard; `finish_reason in {tool_parse_error, error}` / empty tool_calls / bad JSON / ParseFailed-after-one-bounded-retry all resolve to `"KEEP"`; a parsed VERDICT gets `.model` stamped.
- `grounding.py` `is_grounded`/`grounding_reresolves`: byte-exact via `ingest.anchors.open_span`; branches on anchor type — non-absence uses `submission_span_id` (HashMismatch => not grounded, tamper-safe); absence uses `absence_anchor.claim_span_id` else top `sub_threshold_hits` (mirrors `emit_absence_finding` R1). Never raises, never drops.
- `consensus.py` `consensus`: DOWNGRADE only on affirmative grounded majority (`len(grounded downgraders)*2 > panel_size`); ungrounded/split/lone/unsure => KEEP; single-member panel rule; provably no candidate removal (no `.pop`/`.remove`/`del`).
- `schemas/llm.py` VERDICT EXTENDED (additive optional `model`), not redefined — probe still collects.

## Task Commits

1. **Task 1: panel + verify_once + VERDICT.model extend** — `b9b481d` (feat)
2. **Task 2: grounding + consensus** — `5204a27` (feat)
3. **Orchestrator seam (deviation Rule 3): consensus-apply-in-place + consolidate** — `224dced` (feat)

## Files Created/Modified
- `src/verify/panel.py` — decorrelation panel selection over MODEL_LINEAGE/VERIFIER_FLEET.
- `src/verify/verifier.py` — the isolated, write-disabled single verifier call; unsure→KEEP.
- `src/verify/grounding.py` — anchor-type-aware byte-exact grounding re-resolution.
- `src/verify/consensus.py` — the affirmative-grounded-majority + single-member consensus invariant.
- `src/verify/orchestrator.py` — fan-out seam: verify_candidates (mutate-in-place, never drop) + consolidate.
- `src/verify/__init__.py` — package marker.
- `src/schemas/llm.py` — VERDICT.model additive field.

## Decisions Made
See `key-decisions` frontmatter. Core: VERDICT extend is additive/optional (probe-safe); absence grounding uses the claim span as anchor-selector + verbatim-substring gate; single-member panel downgrades only on a lone grounded DOWNGRADE.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created src/verify/orchestrator.py to flip the Wave-1 tests, which un-skipped two Plan-03 stubs — implemented their minimal invariant-preserving behavior to keep the suite green**
- **Found during:** Task 1 (test_decorrelation + test_verifier_readonly both `pytest.importorskip("verify.orchestrator")`)
- **Issue:** The two Wave-1 tests the contract requires GREEN import `verify.orchestrator.verify_candidates`, which the PLAN text defers to Plan 03. `importorskip` skips only on import failure, so creating the module also un-skipped `test_invariant_no_drop` (expects `verify_candidates` to return the SAME list with the candidate mutated in place, tier='low') and `test_orchestrator_consolidate` (expects `consolidate(...)` grouping by dedup_key). Leaving them failing would break the tests/verify suite (a regression).
- **Fix:** Landed a minimal `orchestrator.py`: `verify_candidates` fans out over the decorrelated panel, applies `consensus`, and on DOWNGRADE lowers confidence + flags `confidence_tier='low'` IN PLACE (returns the SAME list, never removes); `consolidate` groups by `Fault.dedup_key` (merge, never drop). This ENFORCES the recall invariant in code — it does not weaken any invariant. Groundedness in this seam is computed via `grounding.is_grounded` when an nt is resolvable, else non-empty grounding_span; consensus stays strict on the bool it is handed. The full get_section/read_guideline corpus re-open + byte-exact per-verdict grounding wiring remains Plan-03 scope (documented in the module).
- **Files modified:** src/verify/orchestrator.py
- **Verification:** `tests/verify/` = 10 passed, 2 skipped (coverage + tail still guarded-skip); static drop-verb scan clean; full no-endpoint suite 701 passed / 0 failed.
- **Committed in:** `224dced`

**2. [Rule 3 - Blocking] grounding API named `is_grounded(candidate, nt, grounding_span=...)` per the Wave-0 test, with a `grounding_reresolves` alias for the PLAN.md contract**
- **Found during:** Task 2 (test_grounding_reresolve.py calls `grounding.is_grounded`)
- **Issue:** PLAN.md `<action>`/acceptance names `grounding_reresolves(candidate, grounding_span_text, nt)`, but the frozen Wave-0 test calls `is_grounded(candidate, nt, grounding_span=...)`.
- **Fix:** Implemented `is_grounded` as the primary API and added `grounding_reresolves` as a thin alias (satisfies both the test and the `grep -q "def grounding_reresolves"` acceptance check).
- **Files modified:** src/verify/grounding.py
- **Verification:** both grounding tests pass; acceptance greps pass.
- **Committed in:** `5204a27`

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking).
**Impact on plan:** No scope creep beyond what was required to make the mandated Wave-0 stubs pass without weakening an invariant. The orchestrator seam is intentionally minimal; Plan 03 owns the full consolidate/coverage + corpus-grounding wiring.

## Issues Encountered
- Absence-branch grounding fixture (`absence_candidate()`) mints its claim span over `"...asserts..."` but the test passes `"...states..."` — a one-word prefix shift that de-aligns the span offsets, so a naive `open_span` HashMismatches. Resolved by treating the claim span as the anchor-type selector and grounding on the verbatim substring of the re-opened source (byte-exact when the claim span opens against nt, else against nt.canonical) — mirroring `emit_absence_finding`'s R1 evidence logic and keeping the deterministic branch a strict tamper-safe integrity gate.

## Threat Flags
None — no new network endpoint, auth path, file-access pattern, or schema-at-trust-boundary was introduced beyond the plan's `<threat_model>` (T-07-03..T-07-06 all mitigated: verifier read-only, off-value verdict => KEEP, on-prem guard on every call, ungrounded downgrade => KEEP).

## Known Stubs
- `src/verify/orchestrator.py` groundedness fallback (non-empty grounding_span when no corpus nt is supplied) and `_reopen_source`/`_reopen_rule` defaults are Plan-03 seams: the byte-exact per-verdict corpus re-resolution + get_section/read_guideline wiring land in Plan 03. Documented in-module; consensus stays strict on the grounded bool, so this does not weaken the recall/precision invariant. `verify.coverage` and `verify.tail` are not yet built (their Wave-0 tests correctly guarded-skip).

## Next Phase Readiness
- Plan 03 (orchestrator/coverage): wire `verify_candidates` re-open accessors to get_section/read_guideline over the real corpus + build the CoverageReport model (flips `test_coverage_report`). The consensus + grounding + decorrelation atoms are ready to compose.
- Plan 04 (interpretive tail): `verify.tail` + `test_tail_gate` still guarded-skip, awaiting the Qwen producer + same-consensus precision gate.
- MAIN-tree gate reminder: run `beta-recall-gate` (zero-TP-loss) once the orchestrator wires the corpus, in the main tree where the gitignored corpus + FAISS exist.

## Self-Check: PASSED

All 6 created files present (src/verify/{__init__,panel,verifier,grounding,consensus,orchestrator}.py) + VERDICT.model field present; all 3 task commits (b9b481d, 5204a27, 224dced) exist in git log.

---
*Phase: 07-multi-agent-verification-interpretive-tail*
*Completed: 2026-08-14*
