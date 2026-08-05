---
phase: 04-rulebook-enrichment-absence-enumeration
plan: 02
subsystem: grounding-gate
tags: [absence, grounding, emit-finding, schema, tdd]
requires:
  - "src/schemas/faults.py::Fault + ComplianceVerdict.GAP (existing)"
  - "src/tools/emit_finding.py::emit_finding dual byte-exact gate (existing, D-EF1)"
  - "src/ingest/anchors.py::open_span / HashMismatch"
  - "src/rulebook/store.py::rulebook_nt_for (RULEBOOK store membership)"
  - "src/tools/ledger.py::RetrievalLedger.was_issued"
provides:
  - "src/schemas/faults.py::CoverageAbsenceAnchor + RetrievalHit + Fault.absence_anchor"
  - "src/tools/emit_finding.py::emit_absence_finding (absence-typed grounding gate, D-GATE1/D-GATE2)"
  - "src/tools/errors.py::unanchored_absence reason code"
affects:
  - "Phase 4 Plan 03 (deterministic absence pass emits through emit_absence_finding)"
  - "Phase 7 verifier (RE-RUNS the negative from CoverageAbsenceAnchor)"
tech-stack:
  added: []
  patterns:
    - "Additive optional Fault field (no migration of existing instances)"
    - "Typed submission half (CoverageAbsenceAnchor) instead of a submission_span_id for never-mentioned / whole-section absences"
    - "Rule half stays byte-exact and UNCHANGED (D-EF1); optional claim span re-opened via the SAME open_span path"
    - "Every rejection is a typed ToolRejected with half populated, returned never raised"
key-files:
  created:
    - "tests/tools/test_emit_absence_finding.py"
  modified:
    - "src/schemas/faults.py"
    - "src/tools/emit_finding.py"
    - "src/tools/errors.py"
decisions:
  - "CoverageAbsenceAnchor field defaults are permissive (default_factory / '' / 0.0) so the re-derivability guard lives in the emit gate (unanchored_absence) rather than in pydantic construction — matches the plan's D-GATE2 gate-time validation."
  - "emit_absence_finding is a NEW function, not an overload of emit_finding, because an absence finding has no single submission_span_id (PATTERNS/D-GATE1)."
  - "Absence findings reuse ComplianceVerdict.GAP; no new verdict member added."
metrics:
  duration: ~9m
  completed: 2026-08-05
  tasks: 2
  files: 4
---

# Phase 4 Plan 02: emit_absence_finding + CoverageAbsenceAnchor Summary

Absence-typed grounding gate: an absence finding keeps its RULE half byte-exact (re-opens in the RULEBOOK store via `open_span`) but replaces the submission half with a typed, RE-DERIVABLE `CoverageAbsenceAnchor` (D-GATE1/D-GATE2), the single Phase-2↔Phase-4 integration seam Plan 03's deterministic absence pass emits through.

## What Was Built

- **`CoverageAbsenceAnchor` + `RetrievalHit`** (`src/schemas/faults.py`): the submission half of an absence finding — `profile`, `family`, `requirement_id`, `threshold`, `sub_threshold_hits` (below-threshold search hits), `manifest_span_ids`, and an optional `claim_span_id` (D-ABS4). Stores the exact enumerate inputs + retrieval evidence so the Phase-7 verifier RE-RUNS the negative rather than trusting a snapshot (D-GATE2). Round-trips through `model_dump()`/`model_validate()`.
- **`Fault.absence_anchor`** (additive optional field): a Fault can carry an anchor with `submission_span_id=None` and `verdict=ComplianceVerdict.GAP` (the already-present enum member — no new verdict).
- **`emit_absence_finding`** (`src/tools/emit_finding.py`): a new gate mirroring `emit_finding`'s structure. Rule half unchanged (D-EF1): no-rule-citation → not-retrieved → wrong-store → not-byte-exact, all `half="rule"`. Optional claim CORPUS span re-opened byte-exact via the SAME `corpus.cached_entry` + `open_span` path, with `half="submission"` rejections for never-issued / hash-drifted spans. Re-derivability guard: empty `requirement_id`/`family` → `unanchored_absence` (D-GATE2). Constructs a `Fault(verdict=GAP, evidence_class=CHECKLIST, submission_span_id=None, absence_anchor=...)`.
- **`unanchored_absence`** registered in `KNOWN_REASON_CODES` (`src/tools/errors.py`).
- **Tests** (`tests/tools/test_emit_absence_finding.py`, 10 tests): success path (GAP + anchor + no submission span), valid claim span re-opens byte-exact, fabricated/never-issued claim span REJECTED (`half="submission"`), no-rule-citation, rule not-retrieved, rule wrong-store, rule not-byte-exact, unanchored (empty requirement_id and empty family). All drive real Phase-1/Plan-02 primitives offline via tmp_path-scoped stores (D-RB6).

## TDD Gates

- **RED**: `tests/tools/test_emit_absence_finding.py` failed collection (`emit_absence_finding` did not exist).
- **GREEN**: reason code registered + `emit_absence_finding` implemented → 10 passed.

## Threat Model Coverage

- **T-04-05** (spoofed rule span) — mitigated: rule half keeps the D-EF1 byte-exact chain (was_issued + RULEBOOK-store membership + open_span). Proven by `test_absence_rule_span_*`.
- **T-04-06** (fabricated narrative-claim span) — mitigated: claim span re-opens byte-exact via the same open_span/corpus.cached_entry path; fabricated/never-issued spans fail `not_byte_exact`/`not_retrieved_this_session`. Proven by `test_absence_fabricated_claim_span_not_byte_exact_cannot_be_emitted` + `test_absence_never_issued_claim_span_is_rejected`.
- **T-04-07** (non-re-derivable absence snapshot) — mitigated: anchor stores enumerate inputs + sub-threshold hits + manifest span-IDs; `unanchored_absence` blocks an anchor that cannot be re-run. Proven by `test_absence_unanchored_*`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing test dependency `rank_bm25`**
- **Found during:** Task 1 (running the baseline test harness).
- **Issue:** `import tools` transitively imports `retrieval.lexical`, which imports `rank_bm25` — not installed in the environment, so the entire `tests/tools/` suite failed at collection.
- **Fix:** `pip install rank_bm25` (0.2.2, the version pinned in CLAUDE.md's stack table). Environment-only; no source change.
- **Files modified:** none (environment).
- **Commit:** n/a (no repo change).

**2. [Rule 1 - Bug] Plan's Task 1 verify command omitted the required `title` field**
- **Found during:** Task 1.
- **Issue:** The plan's literal `python -c` verify constructed `Fault(absence_anchor=a, verdict=GAP)` with no `title`, but `Fault.title` is a required field on the existing (off-limits) schema — the command raised a pydantic `ValidationError`, not because the new code was wrong but because the verify command was invalid against the real schema.
- **Fix:** Supplied `title='Absence'` in the verify invocation. The behavior the command asserts (anchor round-trips, Fault constructs with GAP + `submission_span_id is None`) is otherwise satisfied exactly. Confirmed `OK`.
- **Files modified:** none (verify command only).
- **Commit:** n/a.

## Commits

- `242e7db` — feat(04-02): add CoverageAbsenceAnchor + Fault.absence_anchor schema
- `643ee30` — feat(04-02): add emit_absence_finding gate + unanchored_absence reason code

## Known Stubs

None — both deliverables are fully wired and test-proven. `CoverageAbsenceAnchor`'s consumer (Plan 03's deterministic absence pass) lands in a later plan by design; the anchor + gate are complete and independently exercised.

## Self-Check: PASSED

- All 4 key files present on disk.
- Both commits (`242e7db`, `643ee30`) exist in git history.
- `CoverageAbsenceAnchor`, `emit_absence_finding`, `unanchored_absence` all present.
- `pytest tests/tools/` → 81 passed (10 new absence tests + no regression).
