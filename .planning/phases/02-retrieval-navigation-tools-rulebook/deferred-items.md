# Deferred Items — Phase 02

Out-of-scope discoveries logged during plan execution (not fixed, per the executor's scope
boundary: only auto-fix issues directly caused by the current task's own changes).

## From Plan 02-01 (retrieval navigation tools)

**Pre-existing failure: 19 tests in `tests/evals/` fail with
`AttributeError: 'Fault' object has no attribute 'cited_section_indices'`**

- **Found during:** whole-repo regression run (`PYTHONPATH=src python3 -m pytest -q`) after
  completing all 3 tasks of Plan 02-01.
- **Files involved:** `tests/evals/test_cli.py` (2 tests), `tests/evals/test_metrics.py` (17
  tests) — all reference `src/schemas/faults.py::Fault.cited_section_indices`, an attribute that
  does not exist in `Fault` at this plan's base commit (`efed2d4`, verified via
  `git show efed2d4:src/schemas/faults.py`).
- **Root cause:** `src/schemas/faults.py` is one of this plan's explicitly declared
  import-only/off-limits files (`<phase_2_hard_constraints>`) — Plan 02-01 never edits it. The
  attribute is presumably part of the uncommitted planner/summariser/sandwich/workers redesign
  visible as working-tree modifications in the main checkout (per `PROJECT.md`'s "Uncommitted
  working tree" blocker note) but not yet committed to `CLI_for_folders`, so it is absent from
  every Phase-2 execution worktree branched from `efed2d4`.
- **Not fixed:** entirely outside Plan 02-01's scope (`src/tools/`, `tests/tools/` only) and
  outside the off-limits file boundary. Flagged here for the phase orchestrator / whoever owns
  landing the `Fault.cited_section_indices` schema change.
- **Confirmed unrelated to this plan's changes:** `git diff --name-only efed2d4 HEAD -- <all
  off-limits files>` is empty across all 3 of Plan 02-01's task commits; the entire
  `tests/tools/` suite (29 tests) is green in isolation and in the full-suite run.
