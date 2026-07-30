---
phase: 00-eval-harness
plan: 02
subsystem: testing
tags: [python-docx, pydantic-v2, eval-harness, ground-truth, held-out-corpus, breadth-expansion]

# Dependency graph
requires:
  - phase: 00-eval-harness plan 01
    provides: "src/evals/schema.py (FailureFamily/Confidence/GroundTruthDeficiency/EvalDocument/EvalSet/load_eval_set) + src/evals/dataset/documents.json + mvr1381.deficiencies.json (canonical 28-item estradiol set)"
provides:
  - "src/evals/dataset/docs/mini_spec.docx + minispec.deficiencies.json: a DOCX-format labeled target (3 planted deficiencies) for Phase 1's DOCX parse path (INGEST-02) to be gated against"
  - "src/evals/dataset/heldout32s41.deficiencies.json: 3 hand-verified deficiencies on the real, held-out 32s41 specification PDF (never used in the estradiol tuning set), anchors resolved against parse.pdf.extract_pdf's real output including table cells (checker note W5 applied)"
  - "src/evals/dataset/documents.json now registers 3 documents across 2 formats (pdf, docx) with 1 held_out=true entry"
  - "tests/evals/test_breadth.py: 6 assertions covering breadth, format mix, held-out presence, referential integrity, total count, and tuning-set stability"
affects: [00-03-metrics-engine, 00-04-score-and-baseline, phase-1-ingest-02-docx-parsing]

# Tech tracking
tech-stack:
  added:
    - "python-docx (already a pinned dependency; first in-repo use, as a deterministic fixture-document generator)"
  patterns:
    - "Deterministic fixture generator committed alongside its generated output (make_*.py + the artifact it writes), matching the plan's STRIDE register accept-with-review disposition for generated content"
    - "Held-out document registration: EvalDocument{held_out: true} + a same-shaped *.deficiencies.json labeled purely from the real parsed source; a synthetic-fixture fallback is reserved for when a held-out doc's anchors don't resolve against its real parse"
    - "doc_id-scoped invariant tests (filter eval_set.deficiencies by doc_id before asserting counts) so a single document's pinned count survives later breadth expansion without becoming a stale whole-set total"

key-files:
  created:
    - src/evals/make_docx_fixture.py
    - src/evals/dataset/docs/mini_spec.docx
    - src/evals/dataset/minispec.deficiencies.json
    - src/evals/dataset/heldout32s41.deficiencies.json
    - tests/evals/test_breadth.py
  modified:
    - src/evals/dataset/documents.json
    - tests/evals/test_schema.py

key-decisions:
  - "DOCX fixture table has 3 named component rows (Impurity A=0.08, B=0.15, C=0.19) plus 2 summary rows (Total impurities=0.14, Maximum=0.15) so the two arithmetic deficiencies are independently verifiable: total(0.14) < largest single component (B=0.15), and stated Maximum(0.15) != true max across components (C=0.19)"
  - "Used plain ASCII throughout generated DOCX/JSON content (hyphens, not em-dashes/curly quotes) to keep evidence_anchor substring-matching simple and avoid encoding pitfalls"
  - "For the held-out 32s41 PDF, parsed the real 13-page document first (pages 1-8 = the internal Raw Material Specification / Lab Test Report Form for Estradiol USP Hemihydrate; pages 9-13 = the attached USP and Ph. Eur. reference monographs for the same substance) and hand-picked 3 genuine cross-reference/absence-of-evidence findings against those attached compendial monographs, rather than invoking the plan's synthetic-fixture fallback"
  - "All 3 held-out deficiencies use confidence=likely (none are pure-arithmetic certain cases) per the plan's explicit guidance to set confidence honestly"
  - "Applied checker note W5 procedurally during verification (anchor resolution joins tables[].{headers,rows} plus blocks[].text) instead of editing 00-02-PLAN.md's literal acceptance-criteria text, which is out of this plan's files_modified scope; confirmed the fix is load-bearing -- 2 of 3 held-out anchors ('NMT 3.5%.', 'Report assay on as is basis.') live only in table cells and report as missing under a blocks-only join"
  - "[Rule 1 - Bug] Rescoped test_schema.py's test_exactly_28_deficiencies (renamed test_mvr1381_tuning_set_has_exactly_28_deficiencies, filtered by doc_id==mvr1381) after this plan's intentional breadth expansion grew the whole-set total from 28 to 34, which broke the old raw-total assertion"

requirements-completed: [EVAL-01]

# Metrics
duration: ~25min
completed: 2026-07-30
---

# Phase 0 Plan 02: Multi-Document, Multi-Format, Held-Out Breadth Expansion Summary

**Added a python-docx-generated DOCX fixture with 3 planted deficiencies and registered the real 32s41 specification PDF as a held-out document with 3 hand-verified deficiencies, growing the eval set from 1 document/28 deficiencies to 3 documents/2 formats/34 deficiencies with anchors verified against the actual parsed source (including table cells, per checker note W5).**

## Performance

- **Duration:** ~25 min (estimated -- includes parsing and hand-reviewing the 13-page held-out PDF against its own attached USP/Ph. Eur. monographs)
- **Completed:** 2026-07-30
- **Tasks:** 3/3 completed
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments

- Built a deterministic `python-docx` fixture generator (`src/evals/make_docx_fixture.py`) producing a one-page mock impurities specification with 2 planted arithmetic-integrity deficiencies and 1 planted absence-of-evidence deficiency, all hand-verified against the generated document's actual table/paragraph text
- Parsed the real held-out `data/32s41-Specification.pdf` (13 pages, via `parse.pdf.extract_pdf`) and hand-labeled 3 genuine deficiencies found by comparing the internal Estradiol raw-material specification against the USP and Ph. Eur. reference monographs attached later in the same PDF -- no synthetic fallback was needed
- Applied checker note W5: verified all 3 held-out anchors resolve against blocks *and* table-cell text; confirmed 2 of the 3 anchors are table-only content that would have forced the synthetic-fallback path under the plan's literal (blocks-only) acceptance command
- Expanded `src/evals/dataset/documents.json` to 3 documents spanning both `pdf` and `docx` formats, with 1 `held_out: true` entry
- Added `tests/evals/test_breadth.py` (6 tests) and rescoped one stale Plan-01 test in `tests/evals/test_schema.py` so the full `tests/evals/` suite (14 tests) passes end-to-end post-expansion

## Task Commits

Each task was committed atomically, scoped to only that task's own files (verified via `git status --porcelain` and `git diff --cached --stat` before every commit; any pre-staged unrelated redesign file was unstaged via `git restore --staged` before staging/committing, per the working-tree protection protocol):

1. **Task 1: Generate a planted-deficiency DOCX fixture + its labels** - `f03b844` (feat)
2. **Task 2: Register the 32s41 specification PDF as a held-out labeled document** - `0b3ce0b` (feat)
3. **Task 3: Validate the expanded, multi-format, held-out set** - `8e0b233` (test)

**Plan metadata:** commit created after this SUMMARY (see below)

## Files Created/Modified

- `src/evals/make_docx_fixture.py` - deterministic `python-docx` generator for the `mini_spec.docx` fixture (89 lines)
- `src/evals/dataset/docs/mini_spec.docx` - generated one-page mock impurities specification with 3 planted deficiencies
- `src/evals/dataset/minispec.deficiencies.json` - 3 `GroundTruthDeficiency` records for `doc_id=minispec`
- `src/evals/dataset/heldout32s41.deficiencies.json` - 3 `GroundTruthDeficiency` records for `doc_id=spec32s41`, hand-verified against the real parsed PDF
- `src/evals/dataset/documents.json` - appended `minispec` (docx) and `spec32s41` (pdf, `held_out=true`) entries
- `tests/evals/test_breadth.py` - 6 tests asserting the expanded set's breadth invariants
- `tests/evals/test_schema.py` - rescoped the stale whole-set "exactly 28" pin to a `doc_id==mvr1381`-filtered assertion

## Decisions Made

See `key-decisions` in frontmatter above for the full list. Highlights:
- The DOCX fixture's table shape (3 component rows + 2 summary rows) makes both arithmetic deficiencies independently verifiable without ambiguity.
- The held-out labels came from genuinely reading the real 32s41 PDF (including its own attached USP/Ph. Eur. reference monographs) rather than reaching for the plan's synthetic fallback -- preserving the "real held-out corpus" intent the checker note flagged as being at risk.
- W5 was applied procedurally (at verification time) rather than by editing the plan document, since `00-02-PLAN.md` is not in this plan's `files_modified`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rescoped a stale whole-set count pin in `tests/evals/test_schema.py`**
- **Found during:** Task 3 (running the full `tests/evals/` suite per the plan's own `<verification>` requirement)
- **Issue:** Plan 01's `test_exactly_28_deficiencies` asserted `len(eval_set.deficiencies) == 28` -- true only while `mvr1381` was the sole document. This plan's glob-based breadth expansion (the loader design `schema.py` was explicitly built for, per its own docstring: "a later plan can add a new document's label file without editing this loader") intentionally grows the total to 34, which is exactly this plan's purpose. Every other Plan 01 test remained valid (all assert non-count invariants: non-empty anchors, family coverage, `tp_required` count, minimum certain-confidence count, `mvr1381` registration).
- **Fix:** Renamed the test to `test_mvr1381_tuning_set_has_exactly_28_deficiencies` and filtered `eval_set.deficiencies` by `doc_id == "mvr1381"` before asserting `== 28`, preserving the original invariant's actual intent (the canonical estradiol tuning set is untouched) instead of a now-stale whole-set total. `tests/evals/test_breadth.py` separately asserts the new whole-set total (`>= 34`).
- **Files modified:** `tests/evals/test_schema.py`
- **Verification:** `uv run pytest tests/evals/ -x` -- 1 failed / 7 passed before the fix, 14 passed after
- **Committed in:** `8e0b233` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug fix)
**Impact on plan:** Necessary to satisfy the plan's own stated verification bar (`pytest tests/evals/ -x` passing, Plan 01 + Plan 02 tests together). No scope creep -- the fix is a single rescoped assertion in a file this plan's `<verification>` section already required to pass.

## Issues Encountered

- **Pre-staged unrelated redesign files (git index, not content).** At session start, the unrelated uncommitted `CLI_for_folders` redesign (`src/agents/detection/challenge.py`, `pipeline.py`, `planning.py`, `prompts.py`, `sandwich.py`, `summarise.py`, `workers.py`; `src/llm/client.py`, `structured.py`; `src/schemas/faults.py`; `tests/agents/detection/test_planner_redesign.py`; `tests/unit/test_detection.py`) was already partially **staged** in the git index (the same pre-existing condition 00-01's executor documented and recovered from). Before each of the 3 task commits, `git status --porcelain` confirmed this, and `git restore --staged <path>` (index-only, non-destructive to the working tree) was used to unstage every protected file so that only each task's own explicit files were ever staged or committed. Verified at the end of execution via `git diff --stat` (working-tree content matches the session-start snapshot) and via file mtimes on the still-untracked redesign files (all dated Jul 29, before this session) -- no redesign file was read for editing, Edited, Written, or committed; their content is byte-for-byte unchanged, only their git-index staged/unstaged status changed as required by the protection protocol.
- **One failed commit attempt, no side effects.** The first Task 2 commit attempt used a `git commit -m "$(cat <<'EOF' ... EOF)"` heredoc whose body contained both an apostrophe and embedded double quotes, which the shell rejected with a syntax error before `git commit` ever ran. `git status --porcelain` confirmed nothing was committed and the intended 2 files were still cleanly staged. Recovered by writing the message to a scratch file and using `git commit -F <file> --`, which was then used for all subsequent commits in this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `load_eval_set()` now returns 3 documents (2 formats: pdf, docx; 1 held-out) and 34 deficiencies -- Plan 03's metrics engine and Plan 04's score/baseline generation both iterate `load_eval_set().deficiencies` unchanged by this expansion; no schema or loader changes were needed (glob-based design from Plan 01 worked exactly as intended).
- DOCX parsing itself remains unbuilt (Phase 1 / INGEST-02 scope, as instructed by this plan's objective) -- until then, `minispec`'s 3 deficiencies will correctly show as a 100% parse-fidelity miss in the harness. This is the intended, documented Phase-0 behavior, not a bug.
- The held-out `spec32s41` document and its 3 labels are ready for later phases' held-out (never-tuned-against) evaluation runs.
- No blockers.

## Self-Check: PASSED

- FOUND: src/evals/make_docx_fixture.py
- FOUND: src/evals/dataset/docs/mini_spec.docx
- FOUND: src/evals/dataset/minispec.deficiencies.json
- FOUND: src/evals/dataset/heldout32s41.deficiencies.json
- FOUND: tests/evals/test_breadth.py
- FOUND commit: f03b844 (Task 1)
- FOUND commit: 0b3ce0b (Task 2)
- FOUND commit: 8e0b233 (Task 3)
- `uv run pytest tests/evals/ -x` -- 14 passed
- `git status --porcelain` re-verified: only this plan's own files were ever staged/committed; all protected redesign files remain in their pre-session working-tree state

---
*Phase: 00-eval-harness*
*Completed: 2026-07-30*
