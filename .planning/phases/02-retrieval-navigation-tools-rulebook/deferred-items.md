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

## From Plan 02-07 (SC4 retrieval-gate)

**Root-caused, NOT fixed: `src/parse/pdf.py::extract_pdf`'s scanned-page-without-OCR fallback
silently drops the page's own native text instead of using it as block content, blocking SC4's
hard 100% exact-identifier-subset gate for `mvr1381`**

- **Found during:** Task 2's live baseline-generation run (`python -m evals.run retrieval-gate`).
  The first live measurement returned `overall=0.0`/`exact_identifier_subset=0.0` uniformly
  across every GT item — traced to (and fixed, see `c948034`) a `doc_id` namespace mismatch
  between `ingest_corpus`'s content-hash ids and the eval set's logical ids. After that fix, real
  numbers appeared (`mvr1381`: `overall=0.75`, `exact_identifier_subset=7/12=0.583`; `minispec`:
  `overall=1.0`, `exact_identifier_subset=2/2=1.0` after a separate, narrow MS-04 ground-truth
  anchor fix — see the commit message). `mvr1381`'s remaining 5-item hard-subset gap
  (`A-02`/`A-10`/`A-12`/`B-05`/`B-07`) is the subject of this entry.
- **Root cause, verified empirically (not guessed):** all 5 missing anchors ("13439", "0.92%",
  "05/10/2016", "27.0%", "9.83") are genuinely absent — in every reasonable formatting
  variant — from `mvr1381`'s own ingested canonical text (checked directly against the persisted
  `data/ingest_cache/*.json` cache entry). Tracing `src/parse/pdf.py::extract_pdf`'s scanned-page
  branch (`src/parse/pdf.py:214-238`): when `is_scanned_page(page)` is true and `ocr_page(page)`
  returns `None` (no Databricks creds — this repo's and this gate's permanent, D-RB6-mandated
  state), the code sets `source = "rapidocr-fallback"` and computes `text = page.get_text("text")`
  — but **never assigns this `text` into `blocks`** (`blocks` stays `[]`, initialized at the top of
  the loop and never populated in this specific branch). The digital-page branch two lines below
  DOES build blocks (`blocks = _digital_blocks(page, tables)`); the OCR-success branch also builds
  blocks (`text, ocr_tables, blocks, figures, ocr_source = ocr_result`). Only this ONE fallback
  branch computes a `text` value and then drops it before it reaches the page dict — contradicting
  `parse/ocr.py`'s own module docstring ("OCR is skipped and the caller falls back to whatever
  text layer exists"). `is_scanned_page` flags roughly half of `mvr1381`'s pages (scan-heavy
  appendices/chromatogram printouts, per `src/evals/run.py`'s own pre-existing `_no_network_ocr`
  docstring) — exactly where these 5 anchors' source tables/appendices/approval-page live.
- **Not fixed:** `src/parse/pdf.py` is Phase-1 substrate, outside Plan 02-07's `files_modified`
  (`src/evals/run.py`, `src/evals/metrics.py`, `src/evals/baseline/retrieval_recall.json`,
  `tests/evals/test_metrics.py`, `tests/evals/test_retrieval_gate.py`). It feeds directly into
  `agents/detection/*` (explicitly import-only for this phase) and Phase-0's frozen, committed
  `src/evals/baseline/recall_by_family.json` (`anchor_rate: 0.581`, derived from this same
  function via `_load_source_text`) — a fix here has cross-cutting blast radius beyond a single
  plan's safe boundary (Rule 4: significant structural modification), and no existing test
  currently pins/protects this fallback branch's behavior (`grep -rln "rapidocr-fallback"
  tests/` returns nothing), so a fix would need its own dedicated test + review, not a
  drive-by patch from an unrelated plan.
- **Concrete effect:** `python -m evals.run retrieval-gate` currently exits 1 against its own
  just-committed baseline (`src/evals/baseline/retrieval_recall.json`) — confirmed via a direct
  CLI run, not inferred. The gate, the baseline-recording discipline, and the code implementing
  both are all correct and fully tested (10/10 new tests green); the FAILURE is an honest,
  reproducible measurement of a real, pre-existing, out-of-scope parse-fidelity gap, not a defect
  in this plan's own deliverables.
- **Recommended follow-up (not scheduled by this plan):** a dedicated Phase-1/parse-fidelity plan
  should populate `blocks` from the already-computed `text` in the `rapidocr-fallback` branch
  (mirroring `_digital_blocks`'s shape, at minimum a single flat `LayoutBlock`), add a test pinning
  the fix, and then re-run `python -m evals.run retrieval-gate` to confirm the hard-subset gate
  clears. Until then, this specific, well-diagnosed gap is the known reason SC4's hard gate does
  not yet pass end-to-end for `mvr1381`.

## From Plan 02-09 (read_guideline -- 5th navigation tool + D-RI2 enumerate contract)

**Root-caused, NOT fixed: every real `rulebook/requirement_index.yaml` entry's `citation` field
fails the D-RI2(3)/D-EF1(5) "zero translation" round-trip through `read_guideline`'s own fetch
mode -- `lookup_citation(entry.citation)` returns `None` for all 15 committed entries**

- **Found during:** Task 1's round-trip test design (`read_guideline(citation=None)` row ->
  `read_guideline(citation=<that row's citation>)`). Verified empirically (not guessed): built the
  real committed rulebook snapshot (`build_ecfr`/`build_ich`/`build_fda`, all `update_manifest=False`)
  + `build_requirement_edges()`, then ran `lookup_citation(e.citation)` for every entry returned by
  `load_requirement_index()` -- **all 15 return `NOT FOUND`**, zero exceptions.
- **Root cause:** `rulebook.store.write_chunk` keys each rulebook chunk by a WHOLE-SOURCE-DOCUMENT
  citation (e.g. `"21 CFR 211.166"` for a full eCFR section, `"ICH Q2(R2)"` for an entire ~50k-char
  guideline PDF, per `rulebook/build.py`'s `ICH_GUIDELINES`/`ECFR_PARTS` tables). Plan 02-06's
  `requirement_index.yaml` (reviewer-approved v2) instead used finer, subsection/topic-level
  human-readable citation strings for readability (e.g. `"21 CFR 211.166(a)"`,
  `"ICH Q2(R2) -- Glossary: Specificity/Selectivity"`, `"ICH Q6A -- 3.3(e) Water Content"`) -- a
  granularity mismatch between the two independently-designed schemas, not a bug in either file in
  isolation.
- **Not fixed:** `rulebook/requirement_index.yaml` is Plan 02-06's reviewed data artifact --
  outside Plan 02-09's declared `files_modified` (`src/tools/read_guideline.py`,
  `tests/tools/test_read_guideline.py`), and D-RI1(3) explicitly requires any change to that file
  go through a senior-reviewer session with an index version bump (currently `v2`) -- not a
  drive-by edit from an unrelated tool-implementation plan (Rule 4: this is exactly the kind of
  change that needs a human decision, not an auto-fix).
- **Concrete effect:** `read_guideline`'s own fetch-mode code is correct and fully tested
  end-to-end against real vendored content (`"21 CFR 211.166"` resolves, bounds, dedups, and
  pages forward correctly) -- proven by `tests/tools/test_read_guideline.py`'s fetch-mode suite.
  `test_zero_translation_citation_round_trip` proves the TOOL itself performs zero translation
  using a controlled entry whose citation format aligns with a real store key. What is NOT
  currently true is that this round-trip holds for the REAL, currently-committed
  `requirement_index.yaml` data -- an agent that calls `read_guideline()` to enumerate, then
  passes the returned `citation` straight into `read_guideline(citation=...)` per the locked
  D-EF1(5) flow, gets a `not_found` `ToolRejected` for every one of the 15 real entries today.
- **Recommended follow-up (not scheduled by this plan):** a senior-reviewer session on
  `rulebook/requirement_index.yaml` (Plan 02-06 owner) should either (a) re-cite every entry's
  `citation` field to the exact whole-document citation string `rulebook.store` already uses, or
  (b) extend `rulebook.store`/`rulebook.build` to key finer-grained sub-chunks so the reviewer's
  more specific citations resolve directly -- either fix needs its own version bump
  (`REQUIREMENT_INDEX_VERSION` v2 -> v3) and re-run of the ground-truth traceability test
  (`tests/rulebook/test_requirement_index.py::test_every_absence_family_deficiency_has_firing_entry`).
