---
phase: 00-eval-harness
plan: 04
subsystem: testing
tags: [argparse, ci-gate, eval-harness, pymupdf, unittest-mock, no-llm-scoring]

# Dependency graph
requires:
  - phase: 00-eval-harness plan 01
    provides: "src/evals/schema.py (EvalSet/GroundTruthDeficiency/load_eval_set/EvalSet.tp_required()) + the canonical 28-item mvr1381 ground truth"
  - phase: 00-eval-harness plan 03
    provides: "src/evals/match.py (score/MatchResult), src/evals/metrics.py (compute_metrics/format_table), src/evals/capture.py (golden_report/load_captured), and the committed golden fixture (src/evals/dataset/golden/mvr1381_run3.json)"
provides:
  - "src/evals/gate.py: baseline_found_ids/check_gate/true_positives_lost -- the zero-true-positives-lost gate (EVAL-03); a run that loses a previously-found GT id fails and names it, a superset still passes"
  - "src/evals/run.py: `python -m evals.run {score,gate,run}` -- a single repeatable CI-style command; score/gate are LLM-free (detection stack imported lazily, never at module top); run reuses parse->detect headlessly (NOT run_pipeline), recording a parse_failure per document instead of crashing"
  - "src/evals/baseline/recall_by_family.json + docs/eval/BASELINE.md: the committed 2/28 (7.1%) recall-by-family starting point and the {C-01,C-02} found-set the gate protects, both derived from compute_metrics(golden_report(), ...) -- no hand-guessed numbers"
  - "W1 fully closed: score's printed/written metrics AND the committed baseline both carry a real, code-computed anchor_rate (0.581), never the 'n/a_no_source' sentinel"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CI-style eval CLI: argparse subparsers dispatching to pure evals.* functions; score/gate stay import-light (detection stack imported lazily inside handler bodies, never at module top) so --help/score/gate never pull in LLM-calling dependencies"
    - "Zero-true-positives-lost gate: baseline found-set (tp_required union committed extra ids) must remain a <= subset of a new run's matched_gt_ids; only losing a previously-found id fails, a superset always passes"
    - "Eval-only OCR-network suppression: unittest.mock.patch('parse.ocr.get_settings', ...) scoped to a `with` block around the harness's own extract_pdf call, forcing ocr_page's documented no-creds fallback without touching shared parse/config modules or the live `run` subcommand's real (OCR-enabled) parse"

key-files:
  created:
    - src/evals/gate.py
    - src/evals/run.py
    - src/evals/baseline/recall_by_family.json
    - docs/eval/BASELINE.md
    - tests/evals/test_gate.py
    - tests/evals/test_cli.py
  modified:
    - .gitignore

key-decisions:
  - "Forced parse.ocr.ocr_page's no-creds fallback (via unittest.mock.patch on parse.ocr.get_settings, scoped to a context manager) during the eval harness's own source-text parse only -- real Databricks creds in .env made every one of the ~28 scanned-flagged pages in the 55-page mvr1381 PDF block on its own 60s httpx timeout (~28 minutes total, confirmed by letting one uninstrumented run complete), directly contradicting this plan's own threat model ('score/gate ... touch neither network nor LLM'). The live `run` subcommand's direct extract_pdf call is untouched (keeps full OCR fidelity, matching real detection input)."
  - "tests/evals/test_cli.py's gate tests pass an explicit --baseline temp file rather than relying on the default src/evals/baseline/recall_by_family.json path, since that committed file is Task 3's own deliverable created after this CLI -- keeps Task 2's own verification (`uv run pytest tests/evals/test_cli.py -x`) order-independent of Task 3. The committed baseline's own found-set/tp are pinned separately by tests/evals/test_gate.py's TestCommittedBaseline (Task 3), which does exercise the real default path."
  - "Committed baseline JSON includes anchor_rate (0.581) and a code-computed precision (0.074) beyond the plan's minimal illustrative sketch ({generated_from, overall:{recall,tp,fn}, recall_by_family, found_set}) -- W1's explicit intent is that the baseline itself record a real anchor_rate, and both extra fields are directly computed via compute_metrics(), never hand-guessed."
  - "BASELINE.md states both precision numbers side by side (MEASUREMENT.md's human-reviewed 16% per-finding label rate vs. this harness's deterministic 7.4% distinct-GT-id rate) with an explicit note that they measure different things and are not a discrepancy -- avoids a future reader flagging 16% vs 7.4% as a bug."
  - "docs/eval/last_metrics.json and last_run_metrics.json (score/run's default --out) added to .gitignore as regenerated CLI output, not source -- consistent with data/*'s existing 'never commit built artifacts' convention."

patterns-established:
  - "A CLI's fast/deterministic subcommands (score, gate, --help) never import a heavy/optional/LLM-calling dependency at module top; only the subcommand handler that actually needs it imports it lazily, inside its own function body."
  - "When a shared parsing/detection module's optional network dependency (Databricks OCR) would make an otherwise-deterministic eval path silently network-dependent, scope a monkeypatch (unittest.mock.patch) tightly around just that one call site instead of changing the shared module's own behavior or config."

requirements-completed: [EVAL-03]

# Metrics
duration: ~30min
completed: 2026-07-30
---

# Phase 0 Plan 04: Enforcement Layer -- Zero-TP-Lost Gate, CI CLI, Committed Baseline Summary

**A zero-true-positives-lost CI gate (`src/evals/gate.py`) wired into a single `python -m evals.run {score,gate,run}` command, plus a committed `recall_by_family.json`/`BASELINE.md` pinning the measured 7.1% (2/28) recall-by-family starting point -- with a real, code-computed `anchor_rate` (0.581) in both the CLI and the committed baseline (checker note W1), after discovering and fixing a live Databricks-OCR network dependency that turned the "LLM-free" `score` path into a ~28-minute hang.**

## Performance

- **Duration:** ~30 min (includes diagnosing and fixing an unplanned live-network hang -- see Deviations)
- **Completed:** 2026-07-30
- **Tasks:** 3/3 completed
- **Files modified:** 7 (6 created, 1 modified: `.gitignore`)

## Accomplishments

- Built `src/evals/gate.py`: `baseline_found_ids` (protected set = `tp_required()` union committed extra ids), `check_gate` (`GateResult(ok, lost, matched)`), `true_positives_lost` (grep-able alias) -- entirely built on `evals.match.score`, no new matching logic
- Built `src/evals/run.py`: `python -m evals.run score|gate|run`, `main(argv=None) -> int`. `score`/`gate` are LLM-free and import-light; `run` reuses the orchestrator's parse->detect sequence headlessly (`extract_pdf` -> `split_document`/`group_sections` -> `run_detection`, `job_id=""`, NOT `run_pipeline` -- zero Databricks job-store writes) and records a `parse_failure` per document (e.g. the DOCX `minispec` doc, which has no parse path at Phase 0) instead of crashing the whole run
- Closed checker note W1 for real: `score` and baseline generation both parse `mvr1381`'s own PDF via `extract_pdf`, join block text + table-cell text, and pass it as `compute_metrics`' `source_text` -- `anchor_rate` now reports `0.581` everywhere, never the permanent `"n/a_no_source"` sentinel
- Diagnosed and fixed a real ~28-minute network hang this same W1 change introduced (see Deviations) -- `score` now runs in ~3.5s
- Committed `src/evals/baseline/recall_by_family.json` (found_set `["C-01","C-02"]`, `overall.tp=2`, `recall_by_family` with the real 4-family breakdown, real `anchor_rate`) and `docs/eval/BASELINE.md` (human-readable record, links back to `MEASUREMENT.md`, states the `python -m evals.run gate` enforcement rule)
- 70/70 tests pass across the full `tests/evals/` suite (54 pre-existing + 10 gate + 6 CLI); `ruff check` clean on all 6 new/modified files

## Task Commits

Each task was committed atomically, scoped to only that task's own files (verified via `git status --porcelain` before every commit; no redesign file was ever staged):

1. **Task 1: Zero-true-positives-lost gate (src/evals/gate.py)** - `adf3435` (feat)
2. **Task 2: CI-style command (src/evals/run.py)** - `c70ace0` (feat, includes the W1 OCR-network-hang fix and the `.gitignore` addition)
3. **Task 3: Record the committed baseline** - `650c021` (feat, includes a `ruff` SIM300 fix to Task 1's `test_gate.py` folded into this commit since Task 3 already touches that file)

**Plan metadata:** commit created after this SUMMARY (see below)

## Files Created/Modified

- `src/evals/gate.py` (73 lines) - `baseline_found_ids`, `GateResult`, `check_gate`, `true_positives_lost`
- `src/evals/run.py` (247 lines) - `main`, `build_parser`, `cmd_score`/`cmd_gate`/`cmd_run`, `_load_source_text`/`_join_source_text` (W1), `_no_network_ocr` (the OCR-hang fix)
- `src/evals/baseline/recall_by_family.json` (18 lines) - `generated_from`, `overall` (recall/precision/tp/fp/fn), `recall_by_family` (4 families), `anchor_rate`, `found_set`
- `docs/eval/BASELINE.md` (73 lines) - human-readable baseline record linking back to `MEASUREMENT.md`
- `tests/evals/test_gate.py` (102 lines, 10 tests) - baseline_found_ids union behavior, gate pass/fail on the golden run, doctored-report TP-loss regression tests, the committed-baseline CI test
- `tests/evals/test_cli.py` (99 lines, 6 tests) - `--help`, `score` (default + `--captured`, four families written), `gate` (pass + fail-and-name-the-lost-id, via a self-contained temp baseline)
- `.gitignore` (+3 lines) - `docs/eval/last_metrics.json` / `last_run_metrics.json` (regenerated CLI output, not source)

## Decisions Made

See `key-decisions` in frontmatter above for the full list. Highlights:

- **Scoped an `unittest.mock.patch` around `parse.ocr.get_settings`, not a shared-module change**, to force the OCR no-creds fallback during the eval harness's own source-text parse. This is the minimal-blast-radius fix: it touches only `src/evals/run.py` (my own file), leaves `parse/pdf.py`/`parse/ocr.py`/`config.py` completely untouched, and does not change the live `run` subcommand's real parse (which legitimately wants full OCR fidelity, since it's an actual detection input, not just an anchor-verification text blob).
- **`test_cli.py`'s gate tests avoid the default baseline path on purpose** -- Task 2's own files must verify cleanly before Task 3 exists. This is a real (minor) plan sequencing wrinkle: the plan's Task 2 action text says "`main(["gate"])` returns 0 on the golden baseline," which would need the Task-3-only committed baseline file if read as "use the default path." Read instead as "gate mechanics work correctly against a golden-run-appropriate baseline," satisfied via an explicit `--baseline` temp file -- the committed-default-path behavior is separately and authoritatively pinned by Task 3's own test.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] W1's real-PDF parse hung for ~28 minutes on live Databricks OCR network timeouts**

- **Found during:** Task 2, first manual run of `PYTHONPATH=src uv run python -m evals.run score --captured src/evals/dataset/golden/mvr1381_run3.json` (the plan's own acceptance command) after wiring W1's `extract_pdf` source-text parse
- **Issue:** `data/32s43-validation-related-compounds-method.pdf` is a real 55-page document; PyMuPDF's `is_scanned_page` heuristic flags 28 of those pages as scanned (large embedded images / glyphless fonts -- likely appendix/chromatogram-printout pages). Real `DATABRICKS_HOST`/`DATABRICKS_TOKEN` values are configured in this environment's `.env`, so `extract_pdf` -> `ocr_page` fired one live `httpx` POST per flagged page, each blocking up to its own 60s timeout when the endpoint proved unreachable from this sandbox. A background run was left to complete uninstrumented and confirmed it does eventually finish (exit 0) -- just after ~28 minutes, entirely network-timeout-bound. This directly breaks the plan's own threat model claim ("score/gate ... touch neither network nor LLM") and makes the "fast CI-style command" unusable in practice.
- **Fix:** Added `_no_network_ocr()` (a `contextlib.contextmanager` wrapping `unittest.mock.patch("parse.ocr.get_settings", return_value=Settings(databricks_host="", databricks_token=""))`) around the harness's own `extract_pdf` call in `_load_source_text` only. `ocr_page` already treats empty host/token as its documented "local dev without creds" path (instant `None`, no network attempt) -- this forces that path for exactly this one call site. Verified the resulting joined source text (48,774 chars from the ~27 non-scanned pages' block text + all 55 pages' table-cell text, since table extraction runs before the scanned-page branch) still contains all three key anchor tokens (`"11477"`, `"12601"`, `"0.15"`), so `anchor_rate` stays a real, meaningful number (0.581), not degraded to near-zero by the lost pages.
- **Files modified:** `src/evals/run.py` only
- **Verification:** `time PYTHONPATH=src uv run python -m evals.run score --captured ...` now completes in ~3.5s (was ~28 min); `anchor_rate: 0.581` printed and written; full `tests/evals/` suite (70 tests) passes; `ruff check` clean
- **Committed in:** `c70ace0` (Task 2 commit)

**2. [Scope boundary - deferred, not fixed] `parse/pdf.py`'s scanned-but-no-OCR fallback silently drops a page's block text**

- **Found during:** the same investigation above -- with OCR forced off, every page `is_scanned_page` flags falls back to `source="rapidocr-fallback"` with `blocks=[]` (the raw `page.get_text("text")` value is used only for page-label detection, never stored in the returned page dict's `blocks` list). This is a pre-existing gap in `extract_pdf`'s fallback branch (`src/parse/pdf.py`), unrelated to this plan's own changes and out of this plan's `files_modified` scope.
- **Disposition:** Deferred, not fixed (SCOPE BOUNDARY: pre-existing behavior in a file this plan does not own). Logged here rather than in a separate `deferred-items.md` since it is a single, already-fully-described item. Confirmed inconsequential for this plan's own purpose: the joined source text still resolves all three key anchor tokens (Table 20/Table 19's values live on non-scanned pages or inside preserved table cells), so `anchor_rate` is unaffected in practice. A future phase touching `parse/pdf.py` (e.g. the planned DOCX/agentic-parsing work) should populate `blocks` from the raw text in this fallback branch too.

---

**Total deviations:** 2 (1 auto-fixed Rule 1 bug, 1 deferred out-of-scope discovery)
**Impact on plan:** The OCR-hang fix was necessary for the plan's own "score/gate touch neither network nor LLM" threat-model claim and for `score` to be usable as a "fast CI-style command" at all -- no scope creep, fix is fully contained to the one new file this plan owns (`src/evals/run.py`). The deferred item is genuinely out of scope (a different, pre-existing module) and does not block or weaken this plan's own success criteria (verified the anchors still resolve).

## Issues Encountered

None beyond the deviation above (which is documented there, not repeated here).

## User Setup Required

None - no external service configuration required. (The OCR-hang fix specifically means `score`/`gate` no longer depend on Databricks OCR reachability at all, regardless of `.env` contents.)

## Next Phase Readiness

- The eval harness is now a complete, enforced loop: `python -m evals.run score` measures, `python -m evals.run gate` enforces, `python -m evals.run run --gate` does both against a live model. Any later phase that changes `agents.detection.*` should run `python -m evals.run gate` before merging -- it will fail loudly and name the lost id(s) if C-01 or C-02 (or any id a future baseline update adds to `found_set`) stops being found.
- `src/evals/baseline/recall_by_family.json` is the mechanical "did recall-by-family move up without losing a TP" reference every later phase is measured against; updating it (to record a new, higher baseline) is a deliberate, reviewable act (`found_set` shrinking would fail `tests/evals/test_gate.py`'s `TestCommittedBaseline`).
- Phase 0 (Eval Harness) is functionally complete per its own plan sequence (00-01 through 00-04); ROADMAP Phase 0 success criteria 3 (repeatable CI-style harness) and 4 (zero-TP-lost gate + committed baseline) are satisfied by this plan specifically.
- Per this execution's explicit instructions, `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` were intentionally NOT modified by this executor -- the orchestrator is expected to reconcile phase-completion bookkeeping separately.
- No blockers. The one deferred item (`parse/pdf.py`'s scanned-fallback losing block text) is worth a small fix whenever that file is next touched, but does not block anything today.

## Self-Check: PASSED

- FOUND: src/evals/gate.py
- FOUND: src/evals/run.py
- FOUND: src/evals/baseline/recall_by_family.json
- FOUND: docs/eval/BASELINE.md
- FOUND: tests/evals/test_gate.py
- FOUND: tests/evals/test_cli.py
- FOUND commit: adf3435 (Task 1)
- FOUND commit: c70ace0 (Task 2)
- FOUND commit: 650c021 (Task 3)
- `uv run pytest tests/evals/ -x` -- 70 passed
- All task-level acceptance criteria re-verified passing: `grep -c` function/pattern checks on `gate.py`/`run.py`/`recall_by_family.json`/`BASELINE.md`, `--help`/`score`/`gate` CLI invocations, the exact `gate-pass`/`baseline-ok` one-liners, and the top-level `<verification>` block (`pytest tests/evals/ -x`, `evals.run gate` exit 0, zero `run_pipeline(` calls, `BASELINE.md` recall content)
- `ruff check` clean on all 6 files created/modified by this plan
- `git status --porcelain` re-verified after every commit: only this plan's own files were ever staged/committed; all protected redesign files (`src/agents/detection/{challenge,pipeline,prompts,verify,planning,sandwich,summarise,workers}.py`, `src/llm/{client,structured}.py`, `src/schemas/faults.py`, `tests/agents/detection/test_planner_redesign.py`, `tests/unit/test_detection.py`) remain in their pre-session working-tree state, byte-for-byte unchanged; `.planning/STATE.md` and `.planning/ROADMAP.md` were never touched

---
*Phase: 00-eval-harness*
*Completed: 2026-07-30*
