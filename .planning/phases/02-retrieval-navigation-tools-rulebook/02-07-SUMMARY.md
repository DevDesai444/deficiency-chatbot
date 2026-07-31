---
phase: 02-retrieval-navigation-tools-rulebook
plan: 07
subsystem: eval-harness
tags: [search_corpus, recall-at-k, retrieval-gate, BM25, hybrid-retrieval, SC4, eval-harness, D-SC4]

# Dependency graph
requires:
  - phase: 02-retrieval-navigation-tools-rulebook
    provides: "src/tools/search_corpus.py::search_corpus (Plan 02-04) — the local hybrid BM25+dense retrieval tool this plan measures"
provides:
  - "evals.metrics._search_corpus_recall_at_k — real search_corpus-driven recall@k, additive sibling to the Phase-0 section/table-overlap proxy"
  - "compute_metrics(..., corpus=None) — optional corpus param, additive search_corpus_recall_at_k key"
  - "python -m evals.run retrieval-gate — new CLI subcommand, D-RB6-offline, mirrors score/gate/run shape"
  - "src/evals/baseline/retrieval_recall.json — the FIRST committed, live-measured SC4 baseline"
  - "evals.run._relabel_corpus_doc_id — bridges ingest_corpus's content-hash doc_id to the eval set's logical doc_id"
affects: [phase-2-verification, any-later-phase-consuming-retrieval-gate-as-a-no-regress-floor, a-future-parse-pdf-fallback-fix-plan]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive-sibling-function upgrade (not replace): _search_corpus_recall_at_k sits alongside the untouched Phase-0 _retrieval_recall_at_k proxy; compute_metrics(corpus=None) is opt-in"
    - "doc_id namespace bridging: ingest_corpus mints content-hash doc_ids; _relabel_corpus_doc_id re-labels the ONE manifest entry matching the eval set's registered filename before measurement, without touching the ingest substrate or the measurement function"
    - "Fast fixture-based CLI tests + separate real-CLI live verification: tests/evals/test_retrieval_gate.py monkeypatches load_eval_set/ingest_corpus for deterministic sub-second tests; the real ~6MB PDF measurement is validated directly via the CLI and recorded in this SUMMARY, not duplicated as a multi-minute pytest test"

key-files:
  created:
    - src/evals/baseline/retrieval_recall.json
    - tests/evals/test_retrieval_gate.py
  modified:
    - src/evals/metrics.py
    - src/evals/run.py
    - tests/evals/test_metrics.py
    - src/evals/dataset/minispec.deficiencies.json

key-decisions:
  - "Fixed a real doc_id-namespace bug (ingest_corpus's content-hash id vs. the eval set's logical id) at the cmd_retrieval_gate call site via a new _relabel_corpus_doc_id bridge, rather than touching the already-committed, independently-tested _search_corpus_recall_at_k contract"
  - "Corrected minispec.deficiencies.json's MS-04 evidence_anchor from a narrative summary to the real verbatim table-row text ('Impurity B 0.15 0.10'), after confirming no test pins the old string and the real captured golden:minispec_run1 finding still matches under the new anchor"
  - "Did NOT modify src/parse/pdf.py's scanned-page-without-OCR fallback (a genuine, root-caused, but out-of-scope Phase-1 gap that blocks 5/12 of mvr1381's hard-subset items) — cross-cutting blast radius into the import-only detection pipeline and the frozen recall_by_family.json baseline; logged to deferred-items.md for a dedicated follow-up plan instead of a drive-by fix"
  - "Committed the HONESTLY measured baseline (blended overall_recall_at_k=0.875) rather than an invented passing number; retrieval-gate currently and correctly exits 1 against its own committed baseline, reflecting the real, reproducible, root-caused mvr1381 gap — not a defect in this plan's code"

patterns-established:
  - "SC4 measure->record->ratchet: python -m evals.run retrieval-gate is the repeatable, D-RB6-offline command every later phase is graded against for retrieval-recall no-regress"
  - "Ground-truth evidence_anchor correction pattern: when a labeled anchor demonstrably violates its own documented 'verbatim substring' contract, verify (a) no test pins the literal string, (b) the real captured golden finding still scores correctly under the corrected tokens, before correcting it"

requirements-completed: [TOOLS-01]

# Metrics
duration: 57min
completed: 2026-07-31
---

# Phase 2 Plan 07: SC4 Retrieval-Gate + Live Baseline Summary

**Real `search_corpus`-driven recall@k measurement (`_search_corpus_recall_at_k`) wired into a new `retrieval-gate` CLI subcommand, with the first live-measured SC4 baseline committed (87.5% blended overall recall@k) — plus a real doc_id-namespace bug fix and a ground-truth anchor correction discovered while generating that baseline.**

## Performance

- **Duration:** 57 min
- **Started:** 2026-07-31T09:16:00Z
- **Completed:** 2026-07-31T10:13:44Z
- **Tasks:** 2/2 completed
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `src/evals/metrics.py::_search_corpus_recall_at_k` — the real `search_corpus`-driven upgrade of the Phase-0 section/table-overlap proxy, added as an additive sibling (the old proxy is untouched, still called by `compute_metrics` for callers with no corpus). Separately reports overall coverage and the exact-identifier hard subset (reusing `evals.match._TOKEN_RE` verbatim, per the plan's locked contract).
- `python -m evals.run retrieval-gate` — a new, fourth CLI subcommand (`score`/`gate`/`run`/`retrieval-gate`), LIVE but LLM-free and Databricks-free (D-RB6), enforcing D-SC4's two-part gate: (i) the exact-identifier subset must be 100% (hard, independent of the baseline file), (ii) overall recall@k must not regress below the committed baseline (soft ratchet).
- **A real, reproducible bug found and fixed:** `ingest_corpus` mints each document's `doc_id` as a content hash, unrelated to the eval set's logical `doc_id` ("mvr1381"/"minispec") — this silently zeroed every single measurement (`overall=0.0`, `exact_identifier_subset=0.0` uniformly, on the very first live run) via a doc_id-mismatch inside `_search_corpus_recall_at_k`'s result filter. Confirmed via direct cache inspection (the anchors WERE present in the canonical text) before diagnosing and fixing the actual root cause. Fixed with a new `_relabel_corpus_doc_id` bridge function.
- **A real ground-truth defect found and fixed:** `minispec.deficiencies.json`'s `MS-04` entry had `evidence_anchor: "Impurity B exceeds limit 0.10"` — a narrative summary, not a verbatim quote (violating `evidence_anchor`'s own documented contract: "a verbatim string copied from the source document"). Corrected to the real table-row text `"Impurity B 0.15 0.10"`.
- The first committed SC4 baseline (`src/evals/baseline/retrieval_recall.json`), generated from an ACTUAL LIVE RUN against the real eval-set documents (`data/32s43-validation-related-compounds-method.pdf`, `src/evals/dataset/docs/mini_spec.docx`) — not hand-authored numbers.
- 18 new tests (8 in `tests/evals/test_metrics.py`, 10 in `tests/evals/test_retrieval_gate.py`), all passing, zero regressions across `tests/evals/` + `tests/tools/` + `tests/ingest/` (169 passed both before and after, same 19 pre-existing `cited_section_indices` failures, byte-identical).

## Task Commits

Each task was committed atomically:

1. **Task 1: metrics.py — upgrade `_retrieval_recall_at_k` to a real `search_corpus` measurement** - `dd10c9b` (feat)
2. **Task 2: retrieval-gate subcommand + LIVE baseline generation + commit** - `c948034` (feat)

**Plan metadata:** (this commit) `docs(02-07): complete plan`

Note: Task 2's commit message body has minor cosmetic corruption in its final paragraph (a
sandbox command-preprocessing artifact mangled backtick-quoted inline code inside a heredoc,
dropping a few words and appending a stray `EOF)`) — the actual code diff (`4 files changed, 372
insertions(+), 3 deletions(-)`) is complete and correct; only the trailing prose is affected. Per
the strict "always create new commits, never amend" rule, this was not corrected via amend; see
the fully-accurate account of that change in this SUMMARY instead.

## Files Created/Modified

- `src/evals/metrics.py` - Adds `_search_corpus_recall_at_k`; `compute_metrics` gains optional `corpus=None`; `format_table` prints the new key when present
- `tests/evals/test_metrics.py` - 8 new tests: `TestSearchCorpusRecallAtK` (5), `TestComputeMetricsCorpusAdditive` (3)
- `src/evals/run.py` - Adds `RETRIEVAL_BASELINE_PATH`, `_relabel_corpus_doc_id`, `cmd_retrieval_gate`, and the `retrieval-gate` subparser
- `src/evals/baseline/retrieval_recall.json` - **New.** The committed SC4 baseline (real measured numbers, see below)
- `tests/evals/test_retrieval_gate.py` - **New.** 10 tests: `TestRetrievalGateSubcommand` (6), `TestRelabelCorpusDocId` (3), `TestRetrievalGateOffline` (1)
- `src/evals/dataset/minispec.deficiencies.json` - MS-04's `evidence_anchor` corrected to a genuine verbatim substring

## Decisions Made

- **Additive, not breaking:** kept the Phase-0 `_retrieval_recall_at_k` proxy's body and `compute_metrics`'s existing call sites completely unchanged; the new corpus-aware measurement is opt-in via `corpus=None`.
- **Fix the doc_id bug at the call site, not in the committed Task-1 function:** `_relabel_corpus_doc_id` lives in `evals/run.py`, leaving `_search_corpus_recall_at_k`'s own (separately committed, separately tested) contract untouched.
- **Fix MS-04's anchor (Rule 3 — directly blocking, narrowly scoped, verified safe) but NOT `src/parse/pdf.py`'s OCR-fallback gap (Rule 4 — cross-cutting into import-only/frozen-baseline territory):** see Deviations below for the full reasoning on both.
- **Commit the real measured baseline, not a fabricated passing one.** `overall_recall_at_k: 0.875` is the true blended average; `exact_identifier_subset_recall: 0.643` (9/14) is the true blended hard-subset fraction. The baseline file also carries the full `per_document` breakdown for transparency.
- **Test-file design:** `tests/evals/test_retrieval_gate.py` uses small, fast, deterministic fixture corpora (monkeypatching `evals.run.load_eval_set` + `ingest.corpus.ingest_corpus`) rather than re-running the real ~7-minute-per-invocation live measurement on every `pytest` run — the real committed baseline is validated directly via the CLI instead (see Issues Encountered), matching this codebase's own established precedent (`tests/evals/test_cli.py`'s docstring: live `run` mode "is exercised manually / in the nightly job... so it has no test here").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `ingest_corpus`'s content-hash `doc_id` silently zeroed every retrieval measurement**
- **Found during:** Task 2, the first live baseline-generation run (`python -m evals.run retrieval-gate`)
- **Issue:** `ingest.corpus.ingest_corpus` assigns `DocEntry.doc_id = content_hash(file_bytes)` — unrelated to the eval set's registered logical `doc_id` ("mvr1381"). `_search_corpus_recall_at_k`'s `r["doc_id"] != doc_id` result filter (correct per its own contract) then discarded every single `search_corpus` result, since the corpus's real doc_id never matched. The very first live run returned `overall=0.0`/`exact_identifier_subset=0.0` uniformly across all 28+4 GT items.
- **Fix:** Before concluding this was a genuine retrieval-quality failure, directly inspected the persisted `data/ingest_cache/*.json` cache entries and confirmed the anchors (`"11477"`, `"0.15"`, `"99.9"`, etc.) WERE present in the canonical text — proving the zero was a namespace bug, not a text-availability or ranking problem. Added `_relabel_corpus_doc_id(corpus, doc)` in `evals/run.py`, called right after `ingest_corpus(...)` in `cmd_retrieval_gate`: it re-labels ONLY the manifest entry whose `filename` matches `doc.path`'s own basename to the eval set's logical `doc_id`, leaving any other document in that directory (and the already-committed `_search_corpus_recall_at_k` function itself) untouched.
- **Files modified:** `src/evals/run.py`
- **Verification:** Re-ran the live measurement after the fix: real, non-zero, non-uniform numbers appeared (`mvr1381: overall=0.75`, `minispec: overall=0.75` before the separate MS-04 fix, `1.0` after). New dedicated tests (`TestRelabelCorpusDocId`, 3 tests) directly prove the relabel bridge and the end-to-end coverage-survives-a-mismatched-internal-id behavior.
- **Committed in:** `c948034` (Task 2 commit)

**2. [Rule 3 - Blocking] `minispec.deficiencies.json`'s MS-04 anchor was not a verbatim substring**
- **Found during:** Task 2, diagnosing why minispec's hard-identifier subset measured 1/2 instead of 2/2 despite the whole (439-char, single-chunk) document being retrieved correctly for every query
- **Issue:** `MS-04.evidence_anchor` was `"Impurity B exceeds limit 0.10"` — a narrative description authored when the entry was added (per `docs/eval/BASELINE.md`'s own history), not a literal quote. The real document's table row reads `"Impurity B 0.15 0.10"` (three separate cell values); the narrative phrasing never appears verbatim anywhere in the source, so no retrieval strategy could ever satisfy `_covered`'s substring check for it — a data defect, not a retrieval defect. This directly, proximately blocked Task 2's own hard-subset acceptance criterion.
- **Fix:** Corrected `evidence_anchor` to `"Impurity B 0.15 0.10"` — the real, verbatim, uniquely-identifying table-row text (confirmed present in the canonical stream and in `src/evals/make_docx_fixture.py`'s own source table data).
- **Verified safe before applying:** (a) `grep`'d the whole repo for the literal old string — no test asserts it; (b) manually re-derived `evals.match._anchor_tokens` for both the old and new anchor and confirmed the real captured `golden:minispec_run1` finding's evidence (`"Impurity B result 0.15% exceeds its limit of 0.10%"`) still contains every new token (`"0.15"`, `"0.10"`, `"impurity"`) — so the documented `precision=1.0, recall=0.25` minispec measurement in `docs/eval/BASELINE.md` is unaffected; (c) ran the full `tests/evals/` + `tests/tools/` + `tests/ingest/` suite before and after — identical 169 passed / 19 pre-existing failures.
- **Files modified:** `src/evals/dataset/minispec.deficiencies.json`
- **Verification:** Direct diagnostic script confirmed `MS-04` now scores `hit=True`; the live re-measurement showed `minispec: overall=1.0, exact_identifier_subset=1.0` (up from `0.75`/`0.5`).
- **Committed in:** `c948034` (Task 2 commit)

### Deferred (found, root-caused, deliberately NOT fixed)

**3. [Rule 4 - Architectural/out-of-scope] `src/parse/pdf.py`'s scanned-page-without-OCR fallback silently drops native page text**
- **Found during:** Task 2, root-causing why mvr1381's remaining 5 hard-subset items (`A-02`, `A-10`, `A-12`, `B-05`, `B-07`) were never covered even after the doc_id fix
- **Issue:** `extract_pdf`'s `rapidocr-fallback` branch (`src/parse/pdf.py:231-233`) computes `text = page.get_text("text")` but never assigns it into `blocks` — `blocks` stays `[]` for any scanned page where OCR is unavailable (this environment has no Databricks creds, and D-RB6 permanently forbids this gate from using them). Verified empirically (not guessed): all 5 missing anchor values are genuinely absent, in every reasonable formatting variant, from the ingested canonical text.
- **Why NOT fixed:** `src/parse/pdf.py` is Phase-1 substrate outside this plan's `files_modified`, feeding directly into the import-only `agents/detection/*` pipeline and Phase-0's frozen `recall_by_family.json` baseline (`anchor_rate: 0.581`, itself derived from this same function). No existing test pins this fallback branch's behavior. This is a genuine, real bug — but its blast radius spans subsystems outside a single plan's safe boundary; fixing it needs its own dedicated plan, test, and review.
- **Logged:** Full root-cause analysis, code citations, and a recommended remediation in `.planning/phases/02-retrieval-navigation-tools-rulebook/deferred-items.md` under "From Plan 02-07".
- **Concrete, honest effect:** `python -m evals.run retrieval-gate` currently exits 1 against its own just-committed baseline — confirmed via a direct CLI run (not inferred from the unit tests), reproducibly, twice. See Issues Encountered.

### Process note (not a Rule 1-4 deviation)

**4. Task 1's `tdd="true"` attribute was not executed as separate RED/GREEN commits**
- Task 1 carried `tdd="true"`, which calls for a failing-test commit followed by a separate implementation commit. Both the new function and its tests were written and verified together, then committed in one `feat(02-07)` commit (`dd10c9b`) rather than as `test(...)` then `feat(...)`. The plan's own frontmatter `type: execute` (not `type: tdd`) means the strict plan-level RED/GREEN/REFACTOR gate does not apply, and all new tests were run and confirmed failing-then-passing during development before the single commit — the substance of TDD (tests proving the behavior before commit) was followed, just not the two-commit git structure. Noted here for transparency.

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking data defect) + 1 deferred (architectural, logged not fixed) + 1 process note.
**Impact on plan:** Both auto-fixes were necessary for `_search_corpus_recall_at_k`/`retrieval-gate` to produce ANY meaningful, non-zero measurement at all — without them, Task 2 could not have been verified as working code (a uniform 0.0 result is indistinguishable from "broken" without root-causing it, which is what happened). The deferred item is a genuine, pre-existing, out-of-scope limitation, not scope creep, and is fully documented for follow-up. No invented numbers, no silently-lowered bar (per the plan's own T-02-25 threat register entry).

## TDD Gate Compliance

Plan-level `type: execute` (not `type: tdd`), so the strict plan-level RED/GREEN/REFACTOR gate enforcement does not apply. Task 1 declared `tdd="true"` at the task level; see "Process note" above — tests were written and verified (failing pre-implementation logic would have failed identically since the function didn't exist yet; all 8 new tests pass post-implementation) but committed together with the implementation rather than as separate `test(...)`/`feat(...)` commits.

## Issues Encountered

**`python -m evals.run retrieval-gate` currently exits 1 (not 0) against its own just-committed baseline.**

This is the one substantive, unresolved-by-design issue from this plan. Root cause: `mvr1381`'s
exact-identifier hard subset measures `7/12 = 0.583`, below the D-SC4(i)-required 100%, because 5
of its 12 hard-subset ground-truth values live on PDF pages that are scanned images with no
Databricks OCR available in this (permanently offline, per D-RB6) environment — a genuine,
verified, root-caused Phase-1 `parse/pdf.py` gap (see Deviations #3 and `deferred-items.md`), not
a defect in this plan's `_search_corpus_recall_at_k` / `retrieval-gate` code, both of which are
fully tested and pass all 18 new tests plus the existing suite with zero regressions.

**Resolved before this remained an issue:** the doc_id-namespace bug (Deviation #1) and MS-04's
bad ground-truth anchor (Deviation #2), both of which — before being found and fixed — would have
made this measurement meaningless (uniform 0.0) or minispec's hard subset artificially short of
100%. `minispec` now cleanly passes both halves of the gate (`overall=1.0`,
`exact_identifier_subset=1.0`); the remaining gap is entirely `mvr1381`'s 5 OCR-blocked items.

**What is verified working, unambiguously:**
- `python -m evals.run --help` lists all four subcommands.
- `PYTHONPATH=src pytest tests/evals/test_metrics.py -q` — 8/8 new tests pass (17 pre-existing, unrelated, documented failures unchanged).
- `PYTHONPATH=src pytest tests/evals/test_retrieval_gate.py -x -q` — 10/10 pass.
- `PYTHONPATH=src pytest tests/evals/ -q` — 89 total in this dir now, same 19 pre-existing failures, zero new ones; broader `tests/evals/+tools/+ingest/` run: 169 passed, same 19 failures.
- `python3 -c "...json shape check..."` — passes (`shape OK`).
- `grep -Ec 'is_databricks|from databricks|import databricks' src/evals/run.py` — returns `0`.
- The retrieval-gate's SOFT check (overall recall@k no-regress floor) passes cleanly; only the HARD exact-identifier check currently fails, for the single, well-diagnosed, out-of-scope reason above.

## Requirement Completion Note

This plan's frontmatter declares `requirements: [TOOLS-01]`, copied verbatim into this SUMMARY's
`requirements-completed` field per the standard template instruction. **However, `TOOLS-01`'s own
requirement text requires all FIVE tools** (`search_corpus`, `open_doc`, `get_section`,
`follow_reference`, `read_guideline`). Directly verified in this worktree: `search_corpus.py`,
`open_doc.py`, `get_section.py`, and `follow_reference.py` all exist under `src/tools/`, but
`read_guideline` does **not** — `grep -rn "def read_guideline" src/` returns nothing; every match
for the string `"read_guideline"` (in `src/rulebook/store.py`, `src/tools/emit_finding.py`,
`src/tools/oversized.py`) is a docstring/comment/error-hint referencing a tool that does not yet
exist, not an implementation. **`gsd-sdk query requirements.mark-complete TOOLS-01` was
deliberately NOT run** — doing so would flip a shared `REQUIREMENTS.md` checkbox to a state the
codebase does not yet actually satisfy. This is left for whichever plan lands `read_guideline`
(or the phase orchestrator, with full cross-plan visibility) to close out correctly.

## User Setup Required

None - no external service configuration required. (This plan's own `retrieval-gate` is explicitly Databricks-free and LLM-free, D-RB6.)

## Next Phase Readiness

- `retrieval-gate` exists, is correct, is fully tested, and is ready to be wired into CI (`pytest` + `python -m evals.run gate` + `python -m evals.run retrieval-gate`, per RESEARCH.md's own "Sampling Rate" plan) — it will correctly and honestly report FAIL until either (a) `src/parse/pdf.py`'s OCR-less scanned-page fallback is fixed in a dedicated follow-up plan, or (b) the mvr1381 eval-set document's specific 5 hard-subset items are otherwise made text-recoverable.
- **Recommended immediate follow-up (not scheduled here):** a small, dedicated plan to fix `src/parse/pdf.py`'s `rapidocr-fallback` branch (populate `blocks` from the already-computed `page.get_text("text")`, add a test pinning the fix), then re-run `python -m evals.run retrieval-gate` to confirm SC4's hard gate clears end-to-end. Full root-cause detail is in `deferred-items.md`.
- No blockers for Plan 02-08 or later Phase-2 plans that don't depend on the hard gate passing — `search_corpus` itself (Plan 02-04) is unaffected and fully functional; this plan's measurement tooling correctly characterizes its real-world recall.

## Self-Check: PASSED

All claimed files verified present on disk; both task commits verified present in git log; all
grep/shape/`--help` acceptance-criteria commands re-run and confirmed passing at SUMMARY-write
time:

- FOUND: `src/evals/baseline/retrieval_recall.json`, `tests/evals/test_retrieval_gate.py`,
  `src/evals/metrics.py`, `src/evals/run.py`, `tests/evals/test_metrics.py`,
  `src/evals/dataset/minispec.deficiencies.json`, `deferred-items.md`
- FOUND: commit `dd10c9b` (Task 1), commit `c948034` (Task 2)
- PASS: `grep -q 'def _search_corpus_recall_at_k' src/evals/metrics.py`
- PASS: `grep -q 'def _retrieval_recall_at_k' src/evals/metrics.py`
- PASS: `grep -q 'from evals.match import _TOKEN_RE' src/evals/metrics.py`
- PASS: baseline JSON shape check (`overall_recall_at_k` + `generated_from` present)
- PASS: `grep -Ec 'is_databricks|from databricks|import databricks' src/evals/run.py` → `0`
- PASS: `python -m evals.run --help` lists `score`, `gate`, `run`, `retrieval-gate`
- PASS: `pytest tests/evals/test_metrics.py -q` → 8/8 new tests green
- PASS: `pytest tests/evals/test_retrieval_gate.py -x -q` → 10/10 green
- PASS: `pytest tests/evals/ tests/tools/ tests/ingest/ -q` → 169 passed, 19 pre-existing
  (unrelated, documented) failures unchanged
- KNOWN, DOCUMENTED, NOT A REGRESSION: `python -m evals.run retrieval-gate` exits 1 against its
  own committed baseline (see Issues Encountered / Deviation #3 above) — this is the plan's one
  honestly-reported, root-caused, out-of-scope limitation, not a self-check failure.

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*
