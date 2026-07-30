---
phase: 00-eval-harness
plan: 01
subsystem: testing
tags: [pydantic-v2, strenum, eval-harness, ground-truth, deficiency-detection]

# Dependency graph
requires: []
provides:
  - "src/evals/schema.py: FailureFamily, Confidence, GroundTruthDeficiency, EvalDocument, EvalSet models + load_eval_set() loader"
  - "src/evals/dataset/: documents.json (mvr1381 registry) + mvr1381.deficiencies.json (28-item canonical ground truth)"
  - "Canonical, reconciled 28-item estradiol reference set (W2 applied): 3 cross-file duplicates resolved, 1 genuine gt_D item folded in, 2 tp_required anchors preserved"
affects: [00-02-breadth-expansion, 00-03-metrics-engine]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "StrEnum + pydantic v2 BaseModel mirroring schemas/faults.py's style for all new eval types"
    - "Glob-based dataset loading (dataset/*.deficiencies.json) so later plans add documents without editing the loader"

key-files:
  created:
    - src/evals/__init__.py
    - src/evals/schema.py
    - src/evals/dataset/documents.json
    - src/evals/dataset/mvr1381.deficiencies.json
    - tests/evals/__init__.py
    - tests/evals/test_schema.py
  modified: []

key-decisions:
  - "W2 reconciliation: raw gt_A(14)+gt_B(9)+gt_C(7)+gt_D(7)=37 dedupes to 28, not by naive concatenation -- 3 cross-file duplicates were identified and merged/dropped within A/B/C, and exactly 1 of gt_D's 7 findings is genuinely new"
  - "Kept gt_C's own numbering intact (C-01..C-07, unmerged) since the plan explicitly anchors C-01=11477 and C-04=Table-19-0.14/0.15 -- the two duplicate-with-C hits (gt_D Finding 1, gt_D Finding 7) were resolved by dropping the gt_D copies, not by touching gt_C"
  - "Assigned tp_required=true to C-01 (11477) and C-02 (0.15) exactly as the plan specifies, and verified both anchors substring-match those literal values"

requirements-completed: [EVAL-01]

# Metrics
duration: ~30min
completed: 2026-07-30
---

# Phase 0 Plan 01: Ground-Truth Eval-Set Schema + 28-Item Estradiol Dataset Summary

**Pydantic v2 ground-truth data model (`FailureFamily`/`GroundTruthDeficiency`/`EvalDocument`/`EvalSet` + `load_eval_set()`) plus the canonical, reconciled 28-item estradiol deficiency dataset transcribed from `docs/eval/gt_A..D.md`, with the 30-item overcount from `gt_A+gt_B+gt_C` resolved per checker note W2.**

## Performance

- **Duration:** ~30 min (includes transcribing/cross-referencing four ground-truth markdown files totaling ~1,000 lines, the W2 30→28 reconciliation analysis, and recovering from a git staging mistake — see Issues Encountered)
- **Completed:** 2026-07-30
- **Tasks:** 2/2 completed
- **Files modified:** 6 (all newly created; zero existing files touched)

## Accomplishments

- Defined the eval-set data model (`src/evals/schema.py`): `FailureFamily` (4-member `StrEnum`), `Confidence`, `GroundTruthDeficiency`, `EvalDocument`, `EvalSet` (with `.families()` / `.tp_required()` helpers), and `load_eval_set()` — pure data module, no `agents.*` import, no network access, mirrors `schemas/faults.py`'s pydantic v2 style
- Registered the estradiol source document (`src/evals/dataset/documents.json`) pointing at `data/32s43-validation-related-compounds-method.pdf`
- Transcribed and reconciled the full 28-item ground truth (`src/evals/dataset/mvr1381.deficiencies.json`) from `docs/eval/gt_A_front.md` (14 raw), `gt_B_precision.md` (9 raw), `gt_C_equiv.md` (7 raw), `gt_D_cross.md` (7 raw findings) — applying checker note **W2** to resolve the 37-raw / 30-before-D overcount down to exactly 28 canonical, family-tagged, evidence-anchored items
- Preserved both `tp_required=true` anchors exactly as pinned: `C-01` (`"11477"`, Table 20 transcription error) and `C-02` (`"0.15"`, equivalency-study limit exceedance)
- 8-test suite in `tests/evals/test_schema.py`, all passing

## Task Commits

Each task was committed atomically, scoped to only the files each task created (verified via `git status --porcelain` and `git diff --stat` before and after each commit — no redesign file was staged, modified, or included):

1. **Task 1: Define the eval-set data model and loader** — `4399528` (feat)
2. **Task 2: Encode the 28-item estradiol ground truth + register the estradiol document** — `6ab420c` (feat)

**Plan metadata:** commit created after this SUMMARY (see below)

## Files Created/Modified

- `src/evals/__init__.py` — empty package marker
- `src/evals/schema.py` — `FailureFamily`, `Confidence`, `GroundTruthDeficiency`, `EvalDocument`, `EvalSet`, `load_eval_set()` (110 lines)
- `src/evals/dataset/documents.json` — 1-entry document registry (`mvr1381` → the estradiol method-validation PDF)
- `src/evals/dataset/mvr1381.deficiencies.json` — the 28 canonical `GroundTruthDeficiency` records
- `tests/evals/__init__.py` — empty package marker
- `tests/evals/test_schema.py` — 8 assertions: loads; `==28`; non-empty anchors; all 4 families present; `==2` tp_required; `>=8` certain (actual 11); tp anchors contain `11477`/`0.15`; `mvr1381` registered

## Decisions Made

### W2 reconciliation — how 37 raw items became 28 canonical items

The checker flagged that `gt_A(14) + gt_B(9) + gt_C(7) = 30` already exceeds the pinned 28 before folding in `gt_D` at all, and asked for an explicit reconciliation. Cross-reading all four files line-by-line against `docs/eval/MEASUREMENT.md`'s own "Missed (26/28) ... by failure family" breakdown (which independently confirmed several of the mappings below) produced this accounting:

**Raw total:** 14 + 9 + 7 + 7 = 37

**3 cross-file duplicates resolved within A/B/C (-3, before folding in D):**

| Dropped/merged | Kept as | Reason |
|---|---|---|
| gt_A Finding 7 ("range doesn't cover claimed LOQ-150%, LOD/LOQ fixed at 10%/20% dilution") | `B-01` | Same underlying fact as gt_B Finding 1 ("LOD/LOQ not derived by stated method, fixed 10%/20% dilution, LOQ=2xLOD"), same evidence (Table 7/9, Appendix 9/10 sample names). `B-01`'s framing is the more rigorous/complete of the two (matches `MEASUREMENT.md`'s own wording almost verbatim) so it was kept as canonical. |
| gt_A Finding 11 ("Table 1 restates 0.15% as meeting the 0.10% criterion, drops the footnote that would reveal 0.14% total < 0.15% component") | fully covered by `C-02` + `C-04` | `MEASUREMENT.md`'s own "Found by the detector (2/28)" item #2 description is a fusion of gt_A-11 + gt_C-2's wording — confirming they are the same central deficiency. gt_A-11's footnote-drop clause is the Table-1-side mirror of `C-04`'s Table-19-side arithmetic finding, so nothing distinct survives once both are already present. |
| gt_B Finding 8 ("LOQ accuracy not demonstrated, contrary to its own §1.4.4 definition; 6 replicate injections measure repeatability only") | `A-08` (orig gt_A Finding 9) | Same underlying gap (no accuracy data across the range; only single-level recovery in Table 13) applied at the whole-report level (`A-08`) vs. the LOQ-specific instance (`B-08[orig]`) — judged as one deficiency viewed from two angles, not two. |

**gt_D's 7 findings: 6 duplicates dropped, exactly 1 genuinely new item kept:**

| gt_D Finding | Verdict |
|---|---|
| 1 (Table 20 Max 11477 vs true max 12601) | Duplicate of `C-01` — near-identical wording and evidence |
| 2 (Table 17 notebook citation: body cites `...56`, Table 1 cites `...46`) | **NEW — kept as `D-01`.** Not covered by any A/B/C item; independently confirmed by `MEASUREMENT.md`'s own `cross_reference_integrity` bullet ("Table 17's notebook citation differs between the body (8133/...56) and Table 1 (8133/...46)") |
| 3 (LOD/LOQ fixed 10%/20% dilution, contradicts stated SD-of-response method) | Duplicate of `B-01` |
| 4 (Estradiol RS potency 99.9% w/o water-content correction) | Duplicate of `A-01` |
| 5 (Specificity: 3/5 solutions missing, incl. control sample) | Duplicate of `A-03` |
| 6 (Sensitivity solution no result/criterion, area 485 < LOD mean 629) | Duplicate of `B-06` (the "area 485 vs. mean 629" comparison from gt_D was folded into `B-06`'s title as it sharpens the same finding) |
| 7 (Table 19: total 0.14% < largest 0.15%) | Duplicate of `C-04` |

**Net: 37 raw − 3 (A/B/C internal dedup) − 6 (gt_D duplicates dropped) + 1 (gt_D genuine new item) = 28.**

This lands on `~11 CERTAIN-grade` items (actual count: 11), which matches `MEASUREMENT.md`'s own aside ("deduplicated to 28 distinct (~11 CERTAIN-grade)") almost exactly — a strong independent cross-check that this reconciliation is correct.

**Final family distribution:** `absence_of_evidence`=11, `cross_reference_integrity`=7, `derivation_plausibility`=5, `regulatory_framing`=5 (sums to 28). This roughly tracks `MEASUREMENT.md`'s own architecture-lessons ranking of "Assertion-vs-evidence sweep" as the single largest missing-capability bucket.

**ID scheme:** kept `gt_C`'s numbering fully intact (`C-01`..`C-07`, unmerged) since the plan explicitly anchors `C-01` = `11477` and `C-04` = the Table-19 `0.14`/`0.15` pair — both of gt_D's C-duplicates were resolved by dropping the gt_D copy, never by touching gt_C. `gt_A`'s 12 surviving items were renumbered contiguously `A-01`..`A-12` (original items 7 and 11 dropped, per above); `gt_B`'s 8 surviving items renumbered contiguously `B-01`..`B-08` (original item 8 dropped); `gt_D` contributes a single `D-01`. Full source-item traceability is preserved in the table above.

## Deviations from Plan

None outside of the explicitly-instructed W2 checker-note reconciliation (documented above), which the plan's `<checker_notes>` context directed the executor to apply. No Rule 1–4 auto-fixes were required — all code passed acceptance criteria and tests on first implementation.

## Issues Encountered

**Git staging scope violation, self-caught and fully corrected before this SUMMARY was written.** After staging only `src/evals/__init__.py` and `src/evals/schema.py` via explicit `git add <path> <path>`, the first `git commit -m "..."` (no pathspec) committed the *entire index*, which still held the unrelated, already-staged `CLI_for_folders` redesign files (`planning.py`, `sandwich.py`, `summarise.py`, `workers.py`, `test_planner_redesign.py`, plus already-staged modifications to `challenge.py`, `pipeline.py`, `prompts.py`, `client.py`, `faults.py`) from before this session started. This was caught immediately by inspecting the commit's file list. Recovery: `git reset --soft HEAD~1` (non-destructive — moves the branch pointer back only; index and working tree are untouched) restored the exact pre-commit state, then the commit was redone using an explicit pathspec (`git commit -m "..." -- src/evals/__init__.py src/evals/schema.py`), which commits only the named paths and leaves all other staged content untouched for a future commit. Verified via `git diff --stat HEAD~1 HEAD` (showed only the 2 intended files) and `git status --porcelain` (showed the redesign files in exactly their original `MM`/`M `/`AM`/`A `/` M` states, byte-for-byte unchanged). The second task commit used the same explicit-pathspec pattern from the start and required no correction. **No redesign file content was ever altered, lost, or committed** — confirmed by this diff check both times.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `load_eval_set()` and the `EvalSet`/`GroundTruthDeficiency` shape are now a fixed contract: Plan 02 (breadth expansion) can add new documents by dropping a new `<doc>.deficiencies.json` file + a `documents.json` entry, with zero changes to `schema.py` (glob-based loading, verified in tests).
- Plan 03 (metrics engine) can score detector output against `load_eval_set().deficiencies` — family membership via `.failure_family`, the zero-TP-lost gate via `.tp_required()`.
- No blockers.

## Self-Check: PASSED

- FOUND: src/evals/__init__.py
- FOUND: src/evals/schema.py
- FOUND: src/evals/dataset/documents.json
- FOUND: src/evals/dataset/mvr1381.deficiencies.json
- FOUND: tests/evals/__init__.py
- FOUND: tests/evals/test_schema.py
- FOUND commit: 4399528 (Task 1)
- FOUND commit: 6ab420c (Task 2)
- `uv run pytest tests/evals/` — 8 passed
- `git diff --stat HEAD~1 HEAD` re-verified clean for both task commits; `git status --porcelain` re-verified the redesign files unchanged from the session's original snapshot

---
*Phase: 00-eval-harness*
*Completed: 2026-07-30*
