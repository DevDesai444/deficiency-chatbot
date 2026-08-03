---
phase: 03-drive-loop-spike-go-no-go
plan: 09
subsystem: detection
tags: [oracle-demotion, grounding, checklist, pytest, detect-03]

requires:
  - phase: 03-drive-loop-spike-go-no-go
    provides: Grounding contract fields and review test substrate from plans 03-02 and 03-05
provides:
  - Demoted deterministic seed-pass tool for the review loop
  - S10 reference-standard absence check
  - General P10 stability-commitment absence check
  - D-ORC2 tests proving oracle leads issue no citable evidence before re-open
affects: [phase-03-review-loop, detect-03, d-orc1, d-orc2]

tech-stack:
  added: []
  patterns:
    - Tool-shaped deterministic seed pass returning typed leads instead of Faults
    - Corpus cache resolution for model-supplied doc_id
    - Absence leads direct the reviewer to read_guideline plus get_section

key-files:
  created:
    - src/agents/review/oracles_tool.py
    - tests/agents/review/test_oracles_tool.py
  modified:
    - src/agents/detection/checklists.py
    - src/tools/__init__.py

key-decisions:
  - "Resolved model-supplied doc_id only through CorpusIndex.cached_entry, never filesystem paths."
  - "Kept run_oracles_tool ledger-shaped but non-issuing so every lead must be re-opened before emit_finding accepts it."
  - "Represented absence leads as expected_element + scope_searched + next_call rather than synthesized findings."

patterns-established:
  - "D-ORC1 seed tool returns positive_leads, absence_leads, leads_surfaced, and check_errors."
  - "D-ORC2 structural guards: oracles_tool.py contains no record_span or span_id tokens."
  - "S10 required-elements use synonym sets for lot/batch, purity/potency, expiry/re-test, and qualification/CoA."

requirements-completed: [DETECT-03]

duration: 20min
completed: 2026-08-03
---

# Phase 03 Plan 09: Oracle Demotion Summary

**Deterministic S9/S10/P10 seed checks exposed as a non-issuing review tool with tests proving re-open-before-emit grounding**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-03T09:59:56Z
- **Completed:** 2026-08-03T10:19:52Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added S10 reference-standard qualification checks and a general P10 stability-commitment check beside the existing E&L-specific commitment check.
- Added `run_seed_checks` so S9/S10/P10 can run on demand outside legacy CTD/E&L checklist gating.
- Added `run_oracles_tool` as the seventh tool: it returns investigable positive and absence leads plus `leads_surfaced`, but never makes a lead citable.
- Added eight real-primitive tests proving no pre-issued evidence, emit-gate rejection before re-open, S9/S10/P10 leads, negative controls, S10 synonyms, per-check isolation, and typed unknown-doc rejection.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build S10 and generalize P10** - `6461203` (feat)
2. **Task 2: Build demoted oracle seed tool** - `07db4b7` (feat)
3. **Task 3: Prove oracle demotion behavior** - `24a7810` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified

- `src/agents/detection/checklists.py` - Adds reference-standard required elements, general stability commitment detection, and `run_seed_checks`.
- `src/agents/review/oracles_tool.py` - New non-issuing deterministic seed-pass tool over cached corpus entries.
- `src/tools/__init__.py` - Exports `run_oracles_tool` from the tools barrel.
- `tests/agents/review/test_oracles_tool.py` - Adds eight D-ORC1/D-ORC2 and DETECT-03 tests.
- `.planning/phases/03-drive-loop-spike-go-no-go/03-09-SUMMARY.md` - Plan completion record.

## Verification

- `grep -c -i "reference standard" src/agents/detection/checklists.py` -> `6`
- `grep -c "_STABILITY_COMMITMENT_PATTERNS\|def stability_commitment" src/agents/detection/checklists.py` -> `4`
- `grep -c "def run_seed_checks" src/agents/detection/checklists.py` -> `1`
- `grep -c "def leachable_commitment" src/agents/detection/checklists.py` -> `1`
- `git diff -U0 src/agents/detection/checklists.py | grep '^-' | grep -v '^---' | grep -c "def run_checklists"` -> `0`
- `grep -c "try:" src/agents/detection/checklists.py` -> `1`
- `.venv/bin/pytest tests/agents tests/unit -q` -> `96 passed, 11 skipped`
- `grep -c "def run_oracles_tool" src/agents/review/oracles_tool.py` -> `1`
- `grep -c "record_span" src/agents/review/oracles_tool.py` -> `0`
- `grep -c "span_id" src/agents/review/oracles_tool.py` -> `0`
- `grep -c "raise " src/agents/review/oracles_tool.py` -> `0`
- `grep -c "positive_leads\|absence_leads\|leads_surfaced" src/agents/review/oracles_tool.py` -> `5`
- `grep -c "run_oracles_tool" src/tools/__init__.py` -> `2`
- `grep -c "cached_entry" src/agents/review/oracles_tool.py` -> `1`
- `grep -c "D-ORC1\|D-ORC2\|Pitfall 9" src/agents/review/oracles_tool.py` -> `3`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -c "from tools import run_oracles_tool; print(run_oracles_tool.__name__)"` -> `run_oracles_tool`
- `.venv/bin/pytest tests/agents/review/test_oracles_tool.py::test_no_prerecorded_spans -x -q` -> `1 passed`
- `.venv/bin/pytest tests/agents/review/test_oracles_tool.py::test_s9_s10_p10_leads -x -q` -> `1 passed`
- `.venv/bin/pytest tests/agents/review/test_oracles_tool.py -x -q` -> `8 passed`
- `grep -c "def test_no_prerecorded_spans\|def test_s9_s10_p10_leads" tests/agents/review/test_oracles_tool.py` -> `2`
- `grep -c "def test_a_present_element_produces_no_absence_lead" tests/agents/review/test_oracles_tool.py` -> `1`
- `grep -c "not_retrieved_this_session" tests/agents/review/test_oracles_tool.py` -> `1`
- `grep -c "leads_surfaced" tests/agents/review/test_oracles_tool.py` -> `1`
- `grep -c "Mock\|MagicMock\|patch(" tests/agents/review/test_oracles_tool.py` -> `0`
- `.venv/bin/pytest tests/agents/review tests/tools -q` -> `110 passed`
- `.venv/bin/pytest tests/agents tests/tools tests/unit -q` -> `210 passed, 11 skipped`
- `.venv/bin/pytest -q` -> `416 passed, 11 skipped`

## Decisions Made

- Used `CorpusIndex.cached_entry(doc_id)` as the sole bridge from a model-supplied `doc_id` to deterministic checks.
- Reconstructed the deterministic input as a one-page extract-style text document from cached reading-order text; this preserves absence checks and text-based oracle leads without reintroducing model-controlled paths.
- Kept absence leads non-citable by returning expected element, searched scope, and explicit `read_guideline`/`get_section` instructions instead of manufactured source spans.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 1's planned `test_oracles_tool.py -k s9_s10_p10` verification target did not exist until Task 3, where the plan assigned that file. Structural checks and the existing regression suite passed after Task 1; the targeted S9/S10/P10 test passed after Task 3.
- Concurrent Wave 3 working-tree files were present during execution. They were not staged or modified by this plan.

## Known Stubs

None. Stub-pattern scan found only local accumulator initializers and explicit empty `half` values for typed rejections/tests; none are UI-facing placeholders or unwired data sources.

## Threat Flags

None. The new tool surface is the plan-registered `doc_id` and ledger trust boundary, mitigated by cache-only lookup and non-issuing leads.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plans 03-10 and 03-11 can depend on `run_oracles_tool` as the seventh tool, with `leads_surfaced` available as the oracle-lead conversion denominator and D-ORC2 pinned by tests.

## Self-Check: PASSED

- Created/modified files exist: `src/agents/review/oracles_tool.py`, `tests/agents/review/test_oracles_tool.py`, `src/agents/detection/checklists.py`, `src/tools/__init__.py`, this summary.
- Task commits found in git history: `6461203`, `07db4b7`, `24a7810`.
- No accidental tracked-file deletions were reported by the per-task post-commit checks.

---
*Phase: 03-drive-loop-spike-go-no-go*
*Completed: 2026-08-03*
