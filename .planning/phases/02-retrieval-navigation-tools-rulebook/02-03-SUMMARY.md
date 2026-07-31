---
phase: 02-retrieval-navigation-tools-rulebook
plan: 03
subsystem: retrieval

# Dependency graph
requires:
  - phase: 02-retrieval-navigation-tools-rulebook (plan 02)
    provides: src/rulebook/store.py (RuleChunk, write_chunk, lookup_citation, all_chunks, rebuild_local_index), src/rulebook/edges.py
provides:
  - "A real, git-tracked rulebook/ snapshot: all 7 D-RB1 eCFR Title-21 parts (210/211/314/320/600/601/11), the 4 eval-scoped ICH guidelines (Q2(R2), Q3A(R2), Q3B(R2), Q6A), the 1 eval-relevant FDA guidance, and the precedent xlsm -- 13-row rulebook/manifest.yaml with sha256-verified provenance"
  - "src/rulebook/ecfr_parse.py -- eCFR XML -> the unified document-dict contract, reused by the unchanged Phase-1 substrate"
  - "src/rulebook/build.py -- one-time versioned fetch/parse/ingest orchestration for eCFR + ICH + FDA + precedent vendoring"
  - "src/rulebook/precedents.py -- D-PREC-audited precedent ingestion: 500 xlsm rows -> 385 deduped, provenance-carrying precedent chunks"
  - "215 eCFR + 4 ICH + 1 FDA rule chunks and 385 precedent chunks persisted in the local rulebook store, all citable and byte-exact re-openable"
affects: [02-05, 02-06, 02-09, 02-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live vendoring script (fetch -> parse -> Phase-1 substrate -> store.write_chunk), never at runtime from a tool -- the SSRF mitigation boundary"
    - "One-time build orchestration with never-abort-on-one-bad-item discipline (D-16), mirrored from ingest/corpus.py"
    - "Provenance-list-in-own-table pattern for a chunk whose metadata needs a LIST (precedent_provenance keyed by doc_id), rather than changing RuleChunk's schema"

key-files:
  created:
    - src/rulebook/ecfr_parse.py
    - src/rulebook/build.py
    - src/rulebook/precedents.py
    - rulebook/manifest.yaml
    - rulebook/ecfr/title-21/part-{210,211,314,320,600,601,11}.xml
    - rulebook/ich/{Q2-R2_Guideline_2023-11-30,Q3A-R2_Guideline,Q3B-R2_Guideline,Q6A_Guideline}.pdf
    - rulebook/fda/analytical-procedures-and-methods-validation-for-drugs-and-biologics.pdf
    - rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm
    - tests/rulebook/test_ecfr_parse.py
    - tests/rulebook/test_metadata.py
    - tests/rulebook/test_ich_ingest.py
    - tests/rulebook/test_fda_ingest.py
    - tests/rulebook/test_precedents.py
  modified:
    - src/rulebook/store.py

key-decisions:
  - "Vendored binaries committed as regular git blobs, not Git LFS -- all files are well within normal git blob range (max 4.04MB xlsm; PDFs 137KB-1.3MB), and every downstream consumer (other agents, CI, the orchestrator's merge) can read them with zero extra tooling, consistent with this phase's D-RB6 offline-by-default discipline"
  - "rebuild_local_index() fixed to embed one chunk per encode() call, not one bulk call over the whole corpus -- a single bulk call segfaults the CPU sentence-transformers backend on this length-variable real corpus (19 to ~71k chars per chunk) regardless of batch_size; proven stable for all 215 eCFR chunks, deferred for the full 220-chunk corpus (see Deviations)"
  - "RULES-04's non-empty-url metadata check scoped to network-fetched sources (ecfr/ich/fda); the precedent row's empty url is by design (D-PREC: locally vendored, never fetched), not a completeness gap"

patterns-established:
  - "Rule-text sources (eCFR/ICH/FDA) parse into the SAME {filename,page_count,toc,pages:[...]} dict extract_pdf/extract_docx emit, then flow through the UNCHANGED Phase-1 substrate -- no parallel canonicalization path for rules vs. submissions"

requirements-completed: [RULES-01, RULES-02, RULES-03, RULES-04]

# Metrics
duration: 50min
completed: 2026-07-31
---

# Phase 02 Plan 03: FDA/ICH Rulebook Vendoring + Precedent Ingestion Summary

**Live-vendored 215 eCFR Title-21 sections (7 parts), 4 ICH guidelines, 1 FDA guidance, and 385 D-PREC-deduped precedent chunks into a git-tracked `rulebook/` snapshot, all byte-addressable through the unchanged Phase-1 substrate.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-07-31T08:00Z (approx.)
- **Completed:** 2026-07-31T08:48Z
- **Tasks:** 4
- **Files modified:** 26 (23 created, 1 modified across production; 5 test files created)

## Accomplishments

- All 7 D-RB1 eCFR Title-21 parts (210, 211, 314, 320, 600, 601, 11) fetched LIVE from the real eCFR REST API (edition date `2026-07-29`, matching the plan's live-verified interfaces exactly) and ingested as 215 individually-citable section chunks
- All 4 eval-scoped ICH guidelines (Q2(R2), Q3A(R2), Q3B(R2), Q6A) and the 1 eval-relevant FDA guidance fetched LIVE from `database.ich.org` and the stable `fda.gov` URL, every byte size matching the plan's pre-verified table exactly
- Every ICH chunk (including the 3 pre-2015 PDFs that embed zero "copyright" occurrences of their own) carries the exact `ICH_LEGAL_NOTICE` acknowledgment, applied as a uniform stored constant rather than scraped per-PDF (Pitfall 4)
- The precedent xlsm vendored (copy + hash + manifest row only, per D-PREC's vendor-never-audit boundary) and then, per the now-completed audit policy, ingested: 500 real rows -> 385 exact-text-deduped chunks, 83 forward-filled blank-ANDA rows stamped `anda_inferred`, every number matching `02-PRECEDENT-AUDIT.md` exactly
- `rulebook/manifest.yaml`: 13 rows (7 ecfr + 4 ich + 1 fda + 1 precedent), every non-error row's `sha256` verified against the actual committed file
- Every rule and precedent chunk's span re-opens byte-exact via the same `ingest.anchors.open_span` primitive submission spans use — the grounding contract holds end-to-end for the rulebook too

## Task Commits

1. **Task 1: ecfr_parse.py — eCFR XML -> the unified document-dict contract** - `0fd277f` (feat)
2. **Task 2: build.py — fetch/ingest orchestration + LIVE eCFR vendoring (all 7 D-RB1 parts)** - `a4aa4b9` (feat)
3. **Task 3: LIVE ICH + FDA vendoring + precedent copy-only vendoring + manifest completion** - `be9f725` (feat)
4. **Task 4: precedents.py — ingest the vendored xlsm per the COMPLETED D-PREC audit policy** - `99b316a` (feat)

_Note: no separate plan-metadata commit — this SUMMARY.md is committed alongside per the worktree/parallel-executor protocol (orchestrator owns STATE.md/ROADMAP.md)._

## Files Created/Modified

- `src/rulebook/ecfr_parse.py` - `parse_ecfr_sections()`: eCFR DIV8/SECTION XML -> the same dict shape `extract_pdf` emits
- `src/rulebook/build.py` - `fetch_ecfr_part`/`build_ecfr`/`build_ich`/`build_fda`/`vendor_precedent`/`main`: one-time versioned fetch/parse/ingest orchestration
- `src/rulebook/precedents.py` - `ingest_precedents`/`get_provenance`: D-PREC-audited precedent ingestion (forward-fill + exact dedupe + provenance table)
- `src/rulebook/store.py` - `rebuild_local_index()` fixed to embed one chunk per `encode()` call (see Deviations)
- `rulebook/manifest.yaml` - 13-row RULES-04 metadata manifest
- `rulebook/ecfr/title-21/part-{210,211,314,320,600,601,11}.xml` - 7 live-fetched eCFR part XML files
- `rulebook/ich/*.pdf` (4 files), `rulebook/fda/*.pdf` (1 file) - live-fetched ICH/FDA guideline PDFs
- `rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm` - vendored copy of the precedent spreadsheet
- `tests/rulebook/test_ecfr_parse.py`, `test_metadata.py`, `test_ich_ingest.py`, `test_fda_ingest.py`, `test_precedents.py` - new test coverage (10 new tests)

## Decisions Made

- **No Git LFS for vendored binaries.** LFS is available and pre-configured globally on this machine, but every vendored file (max 4.04MB) is well within normal git blob range; committing as regular blobs avoids a hard git-lfs dependency for every future reader of this worktree's history (other parallel agents, CI, the orchestrator's merge), consistent with D-RB6's "offline, no special infra" discipline.
- **`rebuild_local_index()` embeds one chunk per `encode()` call.** A single bulk `embed_texts(texts, ...)` call over the whole corpus segfaults the CPU sentence-transformers backend on this real, length-variable rulebook corpus regardless of `batch_size` (root cause: `SentenceTransformer.encode()` pre-processes/sorts the FULL input list before its internal batch loop runs). Looping one `encode()` call per chunk is proven stable for all 215 eCFR chunks (verified: index built, `21 CFR 211.166` resolves via `lookup_citation`).
- **`_HEADER_MAP` and `anda_number` type fixes in `precedents.py`** — see Deviations; both are corrections against the REAL vendored file, not design choices.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `rebuild_local_index()` segfaults on a real, length-variable corpus**
- **Found during:** Task 2 (calling `rebuild_local_index()` after the first live eCFR vendoring run)
- **Issue:** The Plan 02-02-authored `rebuild_local_index()` called `embed_texts(texts)` (default `batch_size=8`) over the whole persisted-chunk list in one call. Against 215 real eCFR chunks (lengths 19-45,880 chars — this function had never previously run against real, non-trivial data), this segfaults the CPU `sentence-transformers` backend. A follow-up attempt with `batch_size=1` on the same single bulk call also segfaulted; the crash is tied to the SIZE of the input list passed to one `encode()` call, not batch padding.
- **Fix:** Changed to `np.stack([embed_texts([text], batch_size=1)[0] for text in texts])` — one fresh, single-item `encode()` call per chunk. Verified end-to-end: all 215 chunks (including the largest, 45,880 chars, individually ~31s) embed successfully, the FAISS index builds, and `lookup_citation('21 CFR 211.166')` resolves correctly.
- **Files modified:** `src/rulebook/store.py`
- **Verification:** Full background run completed cleanly (exit 0); `data/rulebook.faiss`/`data/rulebook_map.json` created; all 24 rulebook tests still pass.
- **Committed in:** `a4aa4b9` (Task 2 commit)

**2. [Rule 1 - Bug] Precedent `_HEADER_MAP` didn't match the real spreadsheet's header text**
- **Found during:** Task 4 (first live run of `ingest_precedents` against the real vendored xlsm)
- **Issue:** `02-PRECEDENT-AUDIT.md`'s prose shorthand ("Cohort Year", "Category") doesn't match the actual on-sheet header cells, which read `"Cohort Year of Deficiency"` and `"Category of Deficiency"`. Read-by-name silently dropped both columns from every row (no match -> field excluded).
- **Fix:** Updated `_HEADER_MAP` to the verified, exact on-sheet header strings.
- **Files modified:** `src/rulebook/precedents.py`
- **Verification:** `test_forward_fill_stamps_anda_inferred` passes; provenance rows carry non-empty `cmc_section`/`deficiency_type`/`cohort_year`/`category`.
- **Committed in:** `99b316a` (Task 4 commit)

**3. [Rule 1 - Bug] `anda_number` is Excel-numeric (int), not text — citation string join crashed**
- **Found during:** Task 4 (same first live run)
- **Issue:** `', '.join(andas)` raised `TypeError: sequence item 0: expected str instance, int found` because `anda_number` cells are stored as numeric type in the source spreadsheet.
- **Fix:** `str()`-coerce each `anda_number` before building the `andas` set/sort/join. All ANDA numbers in this dataset are same-length 6-digit values, so lexical string sort matches numeric sort — no ordering regression.
- **Files modified:** `src/rulebook/precedents.py`
- **Verification:** `test_ingest_precedents_dedupes_to_385_chunks` and the full precedent test suite pass; citation strings render correctly (e.g., `"Precedent deficiency (3 occurrence(s) across ANDA 206463, 208528)"`).
- **Committed in:** `99b316a` (Task 4 commit)

**4. [Rule 1 - Test bug] RULES-04 metadata-completeness test too strict for the vendor-only precedent row**
- **Found during:** Task 3 (extending `test_metadata.py` for the full 13-row manifest)
- **Issue:** `test_every_chunk_has_required_metadata_and_no_placeholder_date` required non-empty `url` on every row, but the plan's own `vendor_precedent()` sets `url=""` by design — a locally-copied file has no source URL. RULES-04's `<interfaces>` scopes the metadata-completeness contract to "eCFR, ICH, FDA" chunks specifically, not the vendor-only precedent row.
- **Fix:** Exempted `url` from the completeness check specifically for `source == "precedent"` rows, rather than weakening the check for the network-fetched sources it's meant to guard.
- **Files modified:** `tests/rulebook/test_metadata.py`
- **Verification:** Both `test_metadata.py` tests pass; the check still catches a genuinely missing `url` on any ecfr/ich/fda row.
- **Committed in:** `be9f725` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (all Rule 1 - bugs), plus 1 deferred known issue (below).
**Impact on plan:** All four fixes were required for correctness against REAL data this plan's own live runs produced — none are scope creep; three were only discoverable by actually running the code against the real vendored files (exactly what this plan's "no design sketch, live-fetched content" objective calls for).

## Known Issues (Deferred, not blocking)

**`rebuild_local_index()` is unreliable for the FULL 220-chunk corpus (215 ecfr + 4 ich + 1 fda) on this machine.** The per-item-loop fix (Deviation 1) fully resolves the issue for all 215 eCFR chunks. Adding the 4 ICH + 1 FDA chunks — each a WHOLE-PDF chunk (not per-section like eCFR), up to ~71,366 chars for `ich-Q2-R2` — pushes at least one single-item `encode()` call past several minutes of runtime before a native crash. This is a CPU-backend scaling limit on long individual sequences, not a batching issue (the earlier fix's root cause).

This does **not** block any Task 2/3/4 acceptance criterion: none of them gate on `rebuild_local_index()`/FAISS-index existence. The SQLite-backed path every test and citation lookup actually exercises (`write_chunk`/`lookup_citation`/`all_chunks`/`read_chunk_nt`) is fully populated and verified working for all 220 rule chunks plus all 385 precedent chunks. `rebuild_local_index()` is documented as "safe to re-run — fully deterministic from the persisted chunk store," so a future environment (or a follow-up that chunks/truncates the embedding input for the dense leg) can rebuild the local FAISS index without re-vendoring anything. Flagging here for whichever plan first actually depends on the local dense-search leg (`rulebook_search`'s local backend currently has zero agent-facing callers in Phase 2, per `store.py`'s own tracking comment).

## Issues Encountered

- The worktree was initially based on a stale commit (missing Wave 1's `src/rulebook/store.py`/`edges.py`); recovered via the sanctioned `git reset --hard` to `CLI_for_folders` tip (`3f9d3b4`) per the worktree-base-recovery protocol before any work began.
- `Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm` is gitignored and therefore absent from the fresh worktree checkout (untracked files don't propagate to a new worktree). Copied from the main repo's working tree into this worktree's `Sample Data/` (a plain filesystem copy of an already-gitignored file — no git operation, no tracked-file impact) so Task 3's `vendor_precedent()` could read its documented default source path.

## User Setup Required

None - no external service configuration required. All network fetches (eCFR REST API, `database.ich.org`, `fda.gov`) used public, unauthenticated endpoints.

## Next Phase Readiness

- `read_guideline` (Plan 02-09) and `emit_finding` (Plan 02-05) now have REAL, byte-addressable rule text to cite against — 215 eCFR sections spanning all 7 drug-relevant Title-21 parts, plus 4 ICH guidelines and 1 FDA guidance.
- The requirement index (Plan 02-06) has real chunks to validate its provenance spans against.
- Precedent chunks (385, provenance-carrying) are retrievable from the local store via `rulebook.precedents.get_provenance` but are supporting evidence only — no agent tool registered yet (D-RB3(b), deliberately deferred to Phase-3 evidence-gated tool registration).
- Databricks serving (Plan 02-08) can build FROM this same vendored `rulebook/` snapshot + local chunk store — D-RB2's "vendored snapshot = source of truth" contract is now real, not aspirational.
- Minor follow-up opportunity (not a blocker): the local FAISS dense-search leg needs a longer-sequence-safe rebuild strategy before any plan starts depending on `rulebook_search`'s local backend for ICH/FDA-sourced (whole-PDF) chunks specifically.

---
*Phase: 02-retrieval-navigation-tools-rulebook*
*Completed: 2026-07-31*

## Self-Check: PASSED

- All 13 production/vendored files verified present on disk (src/rulebook/{ecfr_parse,build,precedents}.py, rulebook/manifest.yaml, a sample eCFR/ICH/FDA/precedent vendored file each).
- All 5 new test files verified present on disk.
- All 4 task commit hashes (`0fd277f`, `a4aa4b9`, `be9f725`, `99b316a`) verified present in `git log`.
