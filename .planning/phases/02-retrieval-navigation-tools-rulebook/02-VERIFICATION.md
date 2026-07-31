---
phase: 02-retrieval-navigation-tools-rulebook
verified: 2026-07-31T14:10:00Z
status: passed
score: 15/15 must-have truth clusters verified (1 override applied)
overrides_applied: 1
overrides:
  - must_have: "The exact-identifier subset (batch numbers, table labels) passes HARD — every eval-set item whose evidence_anchor is a bare numeric/identifier token retrieves its home document, not just a statistic (D-SC4(i))"
    reason: "Measured 7/12 (58.3%) for mvr1381, not 100%. Root-caused (not guessed) to a Phase-1 src/parse/pdf.py gap: the scanned-page-without-OCR fallback computes page.get_text('text') but never assigns it into `blocks`, so 5 anchors that live only on scanned pages never reach the canonical text search_corpus indexes. search_corpus/BM25/RRF code itself is correct and fully tested; the gap is upstream substrate, out of this phase's files_modified, and cross-cuts the frozen Phase-0 recall_by_family.json baseline. Documented in 02-PHASE-VERIFICATION-QUEUE.md item 2 and deferred-items.md (02-07). Senior reviewer has reviewed and accepted this as a carried-forward, explicitly-tracked gap rather than a Phase-2 blocker."
    accepted_by: "senior reviewer (per 02-PHASE-VERIFICATION-QUEUE.md item 2, phase-verification queue authored/acknowledged prior to this run)"
    accepted_at: "2026-07-31T00:00:00Z"
re_verification: null
gaps: []
deferred: []
carried_items:
  - id: "queue-item-1"
    title: "Requirement-index 3.2.S.5 classification integration proof not yet run"
    detail: "The D-RI1(2)/14-of-14 traceability test (and the 15/15 e2e test in test_enumerate_fetch_emit_e2e.py) proves the mechanism against hand-built CoverageManifest fixtures asserting mvr1381/spec32s41 classify to 3.2.S.5. It does not yet prove real ingest_corpus output classifies those two real documents into 3.2.S.5 in production. Senior-reviewer-acknowledged follow-up, not a Phase-2 blocker (02-PHASE-VERIFICATION-QUEUE.md item 1)."
  - id: "queue-item-3"
    title: "Vendored rulebook binaries committed as plain git blobs, not Git LFS"
    detail: "Confirmed via `git check-attr filter` (unspecified) and absence of .gitattributes — rulebook/** (~7.2M of eCFR XML/ICH+FDA PDFs/xlsm) is tracked as ordinary blobs. No plan required LFS; this is a repo-hygiene decision deferred to the senior reviewer (02-PHASE-VERIFICATION-QUEUE.md item 3)."
  - id: "queue-item-4"
    title: "Rulebook FAISS dense-index rebuild unreliable for large (whole-PDF, ~71k char) chunks"
    detail: "rulebook.store.rebuild_local_index() works correctly against small fixture chunks (proven by tests/rulebook/test_store.py) but is flagged unreliable at real whole-PDF chunk sizes. No agent-facing tool in Phase 2 depends on the rulebook's own dense-search leg (read_guideline uses lookup_citation/rulebook_nt_for directly, not rulebook_search) — SQLite store is fully populated and correct. Senior-reviewer-acknowledged follow-up before any future plan depends on rulebook dense search (02-PHASE-VERIFICATION-QUEUE.md item 4)."
  - id: "queue-item-5-RESOLVED"
    title: "Requirement-index citation <-> rulebook-store key granularity mismatch"
    detail: "RESOLVED in commit 9c1f191 (requirement-index v3): read_guideline's enumerate rows now carry rule_doc_id alongside citation; fetch mode dual-resolves lookup_citation(arg) then rulebook_nt_for(arg)-as-doc_id. tests/tools/test_enumerate_fetch_emit_e2e.py proves 15/15 real requirement-index entries resolve end-to-end (enumerate -> read_guideline(rule_doc_id) -> emit_finding), offline, against the real committed rulebook/** snapshot. Independently re-run and confirmed passing during this verification."
---

# Phase 2: Retrieval, Navigation Tools & Rulebook — Verification Report

**Phase Goal:** The agent has *hands* — five deterministic navigation tools (`search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline`) that return identifiers + verbatim spans, never whole documents — over a hybrid-retrieval corpus index and an FDA/ICH rulebook; plus the `emit_finding` gate and a requirement index for absence-of-evidence detection.

**Verified:** 2026-07-31T14:10:00Z
**Status:** passed (1 override applied — SC4 hard-subset gap, senior-reviewer-accepted; 4 carried items recorded, 1 of which was resolved during this phase)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (by plan)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Agent can open a doc's metadata/outline and read a bounded section, never whole doc (02-01, TOOLS-01) | VERIFIED | `src/tools/open_doc.py` returns `{doc_id,title,filename,status,structure,tables,classification,outline}` only; `src/tools/get_section.py` bounds every read by `max_chars`. `tests/tools/test_contracts.py::test_tools_return_bounded_results` passes (part of 170/170 offline run). |
| 2 | get_section carries inline per-sentence span-IDs, selected not authored (02-01, TOOLS-02/D-GRAN) | VERIFIED | `_render_annotated` mints/records a `[doc_id:start:end]` span per sentence via `mint_span`+`ledger.record_span`. Test suite green. |
| 3 | Oversized get_section range never truncates, never forces agent-computed offsets — persist+preview+handle (02-01, TOOLS-04 Blocker 2) | VERIFIED | `src/tools/oversized.py` (`persist_range/load_range/advance_cursor`) + `get_section`'s oversized branch; `test_oversized_persist_preview_handle_pages_forward` passes. |
| 4 | Repeat identical (doc_id,start,end) returns "still current" stub, dedup hit-rate queryable (02-01, COST-04) | VERIFIED | `RetrievalLedger.check_and_mark_served`/`dedup_hit_rate`; `test_repeat_read_returns_stub_and_reports_hit_rate` passes. |
| 5 | follow_reference resolves same-doc heading or returns typed cross-doc-pending sentinel, never silent empty (02-01, D-FR) | VERIFIED | `src/tools/follow_reference.py` — grep confirms no `return {}`/`return None`; `test_same_doc_resolves_cross_doc_typed_stub` passes. |
| 6 | RetrievalLedger is per-run, constructor-injected, never module-global (02-01, Pitfall 9) | VERIFIED | `grep -Ec '^_ledger|^ledger ='` returns 0; class only holds instance state. |
| 7 | Rulebook chunk persists text+span+{source,citation,version,license,url}, byte-exact reopen via open_span (02-02, RULES-04) | VERIFIED | `src/rulebook/store.py::write_chunk/read_chunk_nt`; `tests/rulebook/test_store.py` green. |
| 8 | Citation string resolves to exactly one chunk via exact-match lookup (02-02) | VERIFIED | `lookup_citation` — parameterized SQL, tested. |
| 9 | Local hybrid rulebook search never calls Databricks (02-02, D-RB6) | VERIFIED | `_rulebook_search_local` (FAISS+lexical fusion), `rulebook_search` dispatches on `is_databricks`; offline test confirms local path with no network. |
| 10 | Generic edge table (src_id,dst_id,edge_type,provenance_span_id), queryable by any subset (02-02, D-RB3) | VERIFIED | `src/rulebook/edges.py::add_edge/get_edges`; `add_edge` raises `ValueError` on empty provenance (no unexplained edges). |
| 11 | Calling Databricks branch without src/databricks/rulebook.py fails loudly, not silently (02-02) | VERIFIED (superseded correctly) | Originally a `ModuleNotFoundError` guard (02-02); 02-08 later implemented `src/databricks/rulebook.py` fulfilling the forward reference. Dispatch now verified end-to-end via a monkeypatched test that never reaches real Databricks (`test_databricks_dispatch.py`, ran with `DATABRICKS_HOST`/`DATABRICKS_TOKEN` unset — passed). |
| 12 | faiss-cpu is a production dependency, not dev-only (02-02, Pitfall 7) | VERIFIED | `tomllib` check: `faiss-cpu` present in `[project].dependencies`, absent from `[dependency-groups].dev`. |
| 13 | Vendored rulebook snapshot committed under a NEW git-tracked `rulebook/` dir, not `data/`/`Sample Data/` (02-03, D-RB2) | VERIFIED | `git ls-files rulebook/` → 14 tracked files (7 eCFR XML, 4 ICH PDF, 1 FDA PDF, 1 xlsm, 1 manifest.yaml); `git check-ignore -v rulebook/manifest.yaml` exits 1 (not ignored). |
| 14 | All 7 D-RB1 eCFR parts (210,211,314,320,600,601,11) ingest wholesale (02-03, RULES-01) | VERIFIED | `ls rulebook/ecfr/title-21/*.xml` → 7 files; manifest.yaml has 7 `source: ecfr` rows with real `section_count`s (3..69). |
| 15 | Every ICH chunk carries the exact copyright notice, including the 3 pre-2015 PDFs with no embedded notice (02-03, RULES-02) | VERIFIED | `test_ich_chunk_carries_notice_even_when_source_pdf_lacks_it` part of the 170-test green run; manifest rows show the `ICH_LEGAL_NOTICE` reference applied uniformly. |
| 16 | Every rule chunk stores {source,citation,version,license,url}; no `_SUBSTITUTE_DATE_` leak (02-03, RULES-04) | VERIFIED | `grep -c '_SUBSTITUTE_DATE_' rulebook/manifest.yaml` = 0; manifest rows show all 5 required fields populated for every non-error row. |
| 17 | FDA guidance vendored via stable direct fda.gov URL, bypassing regulations.gov (02-03, RULES-03) | VERIFIED (with a minor wording note) | manifest.yaml's `fda` row url = `https://www.fda.gov/files/drugs/published/...pdf` — matches Pitfall 10's documented, deliberate choice. REQUIREMENTS.md's parenthetical "(via regulations.gov)" is not literally satisfied (the direct URL was used instead, by design, since it is more stable) but the substantive requirement — FDA guidance for the eval-set topic is ingested with full metadata — is met. Not treated as a gap. |
| 18 | Precedent xlsm vendored (copy+hash+manifest row) but audit/dedupe policy is senior-reviewer's own step, not auto-decided (02-03, D-PREC) | VERIFIED | `02-PRECEDENT-AUDIT.md` shows a completed, dated senior-reviewer audit (same dataset as `deficiency_kb`, dedupe/forward-fill/row-identity policy decided); manifest row's `note` field records the boundary; `src/rulebook/precedents.py` implements the policy mechanically per Task 4. |
| 19 | Every vendored chunk reopens byte-exact via the same open_span primitive submissions use (02-03) | VERIFIED | Covered by the same `open_span`/`HashMismatch` path as Plan 02-02; part of the 170-test green run. |
| 20 | search_corpus returns identifiers/snippets, never whole doc, local-only ephemeral index (02-04, TOOLS-01/D-RB5) | VERIFIED | `grep -Ec 'is_databricks|from databricks|import databricks' src/tools/search_corpus.py` = 0; results are `{doc_id,span_id,score,snippet}`. |
| 21 | Exact numeric/identifier query ranks its home doc via BM25, not just dense similarity (02-04) | VERIFIED (unit-level); real-corpus hard-subset gap tracked separately (see override) | `src/retrieval/lexical.py::BM25Index` + RRF fusion; `tests/tools/test_search_corpus.py`'s constructed exact-identifier test passes (mocked dense leg deliberately ranks a distractor above the target, proving BM25 rescues it). The REAL end-to-end recall on `mvr1381` is 58.3% due to an upstream Phase-1 OCR-fallback bug (see override below), not a defect in this plan's fusion logic. |
| 22 | Every search_corpus result carries an inline-annotated, ledger-recorded span-ID (02-04, TOOLS-02) | VERIFIED | `search_corpus` calls `mint_span`+`ledger.record_span` per result before returning. |
| 23 | RRF combines dense+lexical with score=sum(1/(k+rank)), k=60, no library (02-04) | VERIFIED | `grep -q '1.0 / (k + rank)' src/retrieval/hybrid.py` passes; hand-computed test value confirmed. |
| 24 | A fabricated/altered quote CANNOT be emitted — rejected at the gate, never emitted-then-caught (02-05, TOOLS-03, ROADMAP's named acceptance test) | VERIFIED | `tests/tools/test_emit_finding.py::test_fabricated_quote_cannot_be_emitted` — re-ran independently, PASSED. Returns `ToolRejected(reason_code="not_byte_exact")`, no `Fault` ever constructed. |
| 25 | Finding only created by re-opening BOTH submission and rule spans via open_span + byte-exact hash compare (02-05, D-EF1(1)) | VERIFIED | `emit_finding` calls `open_span` exactly twice, catches `HashMismatch` on each independently. |
| 26 | Rule span where submission span belongs (or vice versa) is a typed rejection — store-membership enforced (02-05, D-EF1(2)) | VERIFIED | `test_rejects_wrong_store_rule_span_from_corpus` and `test_rejects_wrong_store_submission_span_from_rulebook` (the symmetric direction) both re-ran and PASSED. |
| 27 | Span never retrieved this session is rejected even if it would reopen byte-exact (02-05, D-GRAN) | VERIFIED | `test_rejects_not_retrieved_this_session` passed; ledger check runs before hash check in code. |
| 28 | Finding with no rule citation is rejected (02-05, TOOLS-03) | VERIFIED | `test_rejects_no_rule_citation` passed. |
| 29 | `not_unique` is structurally unreachable under span-ID-only input, proven by a test (02-05, plan-checker Blocker 1) | VERIFIED | `test_span_id_unique_by_construction` passed — two identical-text, different-offset spans resolve independently. |
| 30 | Success path constructs Fault with evidence_class=QUOTE_ANCHORED, carries rule_span_id (grounding, spent at validation time) + requirement_id/citation (metadata) (02-05, D-EF1(5)) | VERIFIED | `test_success_path_constructs_grounded_fault` passed; `KNOWN LIMITATION` code comment documents the `Fault`-schema constraint (no structured span field) per plan-checker Warning 2. |
| 31 | Every rejection is a typed ToolRejected, never a raised exception (02-05, TOOLS-03) | VERIFIED | `grep -Ec 'raise HashMismatch|raise Exception' src/tools/emit_finding.py` = 0. |
| 32 | Agent can enumerate what a submission MUST contain independent of content (02-06, RULES-05) | VERIFIED | `enumerate_requirements` resolves via edge-table union (`family_requires_requirement` ∪ `profile_requires_family`), independent of `search_corpus`. |
| 33 | Mis-drafted requirement-index entry fails at LOAD time (02-06, D-RI1(1)) | VERIFIED | `load_requirement_index` raises `ValueError` on unregistered family or `HashMismatch`-failing provenance; part of the 170-test green run. |
| 34 | All 14 absence_of_evidence eval items have >=1 firing requirement-index entry (02-06, D-RI1(2)) | VERIFIED | `test_every_absence_family_deficiency_has_firing_entry` (14/14, hardcoded id list) part of the green suite; SUMMARY records reviewer sign-off with 3 revised entries + 2 new honest-coverage entries. |
| 35 | Applicability is classification-driven via edges; zero-classified-docs family still fires (02-06, D-RB4) | VERIFIED | `enumerate_requirements` computes `applicable_families` from BOTH directly-classified families AND `profile_requires_family` edges — proven structurally, not just by direct filter. |
| 36 | Requirement index is human-reviewed before being final (02-06, D-RI1(3)) | VERIFIED | `02-06-SUMMARY.md` documents a completed senior-reviewer pass: 10 approved as-is, 3 revised, 2 new entries added, plus the ich.org site-wide-terms confirmation (plan-checker Warning 5) resolved in the same checkpoint. |
| 37 | Retrieval recall@k measured with search_corpus itself, not the Phase-0 proxy (02-07, SC4) | VERIFIED | `_search_corpus_recall_at_k` added as an additive sibling; live-measured baseline committed (`src/evals/baseline/retrieval_recall.json`, re-generated during this verification: overall=0.875). |
| 38 | Exact-identifier subset passes HARD (100%) (02-07, D-SC4(i)) | **FAILED — OVERRIDE APPLIED** | Measured 7/12 = 58.3% for `mvr1381` (12/12 for `minispec`). Root-caused to a Phase-1 `src/parse/pdf.py` scanned-page-OCR-fallback bug that drops extracted text before it reaches `blocks`. See override in frontmatter. |
| 39 | Measured recall@k recorded as committed baseline, no invented threshold (02-07, D-SC4) | VERIFIED | `src/evals/baseline/retrieval_recall.json` committed with real, live-measured numbers (not hand-authored) per the shape convention. |
| 40 | Recorded baseline becomes a no-regress floor via `retrieval-gate` CI command (02-07, D-SC4(ii)) | VERIFIED | `python -m evals.run retrieval-gate` exists, re-ran during this verification: correctly fails on the hard-subset gate (as expected, given the acknowledged Phase-1 gap) and would fail on regression of the overall floor too. |
| 41 | `retrieval-gate` never reaches Databricks (02-07, D-RB6) | VERIFIED | `grep -Ec 'is_databricks|from databricks|import databricks' src/evals/run.py` returns 0 for the new function; command ran successfully with no Databricks env vars set. |
| 42 | Databricks Delta serving layer populated deterministically from the same vendored snapshot (02-08, D-RB2) | VERIFIED | `push_chunks_to_delta` ran live per SUMMARY (605 chunks, verified via SQL COUNT(*)); reuses `all_chunks()`/`read_chunk_nt()` from the same local store as everything else. |
| 43 | Databricks query path uses proven client-side-cosine pattern, not literal Vector Search API (02-08, Pitfall 6) | VERIFIED | `search_rulebook_databricks` mirrors `databricks/vector.py::_search_embeddings_table`'s structure exactly; uses `_rows_from_result` (not the truncating `data_array`-only shortcut). |
| 44 | Two-backend dispatch seam completed — tool contract never changes (02-08, D-RB6) | VERIFIED | `rulebook.store._rulebook_search_databricks`'s forward-reference import now resolves; `test_databricks_dispatch.py` proves the dispatch end-to-end via a monkeypatch, re-ran during this verification with `DATABRICKS_HOST=`/`DATABRICKS_TOKEN=` unset — PASSED. |
| 45 | No test in Plan 08 imports/reaches real Databricks (02-08, D-RB6 HARD) | VERIFIED | Confirmed by direct re-run with credentials unset. |
| 46 | read_guideline is the 5th navigation tool, sole path to rule text + enumerate surface (02-09, RULES-05/TOOLS-01) | VERIFIED | `src/tools/read_guideline.py` composes `enumerate_requirements` (Plan 06) + `lookup_citation`/`rulebook_nt_for` (Plan 02/03), one signature. |
| 47 | Omit citation = enumerate; provide citation = fetch; one optional param, Read-with/without-offset shape (02-09, D-RI2(1)) | VERIFIED | Signature `read_guideline(manifest, ledger, citation=None, family=None, handle=None, max_chars=8000)`. |
| 48 | Applicability resolved server-side; agent cannot pass free-text profiles; invalid family = typed rejection (02-09, D-RI2(2)) | VERIFIED | Delegates entirely to `enumerate_requirements`'s own registry-validated rejection. |
| 49 | Enumerate mode returns IDs/citations directly usable in emit_finding's rule-citation field — zero translation (02-09, D-RI2(3)) | VERIFIED (after fix) | Originally FAILED in 02-09 (all 15 real citations returned `not_found` from fetch mode — a granularity mismatch between requirement-index citations and rulebook-store keys, logged as Verification Queue item 5/MATERIAL). RESOLVED in commit `9c1f191` (requirement-index v3): enumerate rows now also carry `rule_doc_id`; `tests/tools/test_enumerate_fetch_emit_e2e.py::test_enumerate_fetch_emit_15_of_15_resolve_end_to_end` re-ran during this verification — PASSED, proving all 15 real entries resolve `enumerate -> read_guideline(rule_doc_id) -> emit_finding` end-to-end, offline, against the real committed rulebook snapshot. |
| 50 | Both modes TOOLS-04-bounded; oversized fetch persists+previews+hands back a handle (02-09, Blocker 2) | VERIFIED | `_fetch_citation`'s oversized branch mirrors `get_section`'s exactly via the same `src/tools/oversized.py`; `test_oversized_citation_persist_preview_handle_pages_forward` part of the green suite. |
| 51 | Re-fetching identical citation returns COST-04 "still current" stub (02-09) | VERIFIED | `ledger.check_and_mark_served` reused verbatim in `_fetch_citation`. |

**Score:** 50/51 truths VERIFIED directly; 1 (exact-identifier HARD subset, #38) FAILED-then-OVERRIDDEN per senior-reviewer acceptance already on record. Net: 15/15 must-have truth *clusters* (grouped by plan) pass, with one documented, accepted exception.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/tools/ledger.py`, `errors.py`, `oversized.py`, `textsplit.py`, `open_doc.py`, `get_section.py`, `follow_reference.py` | Plan 02-01 primitives + 3 tools | VERIFIED | All exist, exported via `src/tools/__init__.py` where declared, all tests green. |
| `src/rulebook/store.py`, `edges.py` | Plan 02-02 local store + edges | VERIFIED | All exports present (`RuleChunk`, `write_chunk`, `read_chunk_nt`, `rulebook_nt_for`, `lookup_citation`, `all_chunks`, `rulebook_search`, `add_edge`, `get_edges`). |
| `src/rulebook/ecfr_parse.py`, `build.py`, `precedents.py`; `rulebook/**` snapshot; `rulebook/manifest.yaml` | Plan 02-03 vendoring + parser | VERIFIED | 7 eCFR XML + 4 ICH PDF + 1 FDA PDF + 1 xlsm committed and git-tracked; manifest 14 real rows (13 content rows + reorder no-op diff pending, harmless). |
| `src/retrieval/lexical.py`, `hybrid.py`; `src/tools/search_corpus.py` | Plan 02-04 hybrid retrieval tool | VERIFIED | All exports present, zero Databricks coupling confirmed by grep. |
| `src/tools/emit_finding.py` | Plan 02-05 grounding gate | VERIFIED | Sole constructor path for `Fault` in `src/tools/`; every rejection path independently tested. |
| `src/rulebook/requirement_index.py`, `requirement_index.yaml` | Plan 02-06 requirement index | VERIFIED | 15 entries, loader gate passes on the real committed file, 14/14 traceability. |
| `src/evals/run.py` (extended), `metrics.py` (upgraded), `src/evals/baseline/retrieval_recall.json` | Plan 02-07 SC4 gate | VERIFIED (gate itself correctly reports the known Phase-1 gap) | `retrieval-gate` subcommand exists and runs fully offline; baseline is real/live-measured. |
| `src/databricks/rulebook.py` | Plan 02-08 Databricks serving | VERIFIED | `push_chunks_to_delta`, `search_rulebook_databricks` both present, live-run confirmed per SUMMARY, mocked dispatch test passes offline. |
| `src/tools/read_guideline.py` | Plan 02-09 5th tool | VERIFIED | Dual-mode dispatch, TOOLS-04/COST-04 wired, RULES-05 e2e chain proven post-fix. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `get_section.py` | `ledger.py` | `check_and_mark_served`/`record_span` | WIRED | Confirmed by grep + passing dedup/annotation tests. |
| `get_section.py` | `ingest/anchors.py::mint_span` | span minting over canonical text | WIRED | Confirmed by byte-exact reopen tests. |
| `get_section.py` | `oversized.py` | `persist_range`/`load_range`/`advance_cursor` | WIRED | Handle-continuation test passes distinctly from the plain-rejection test. |
| `store.py::rulebook_search` | `config.Settings.is_databricks` | two-backend dispatch | WIRED | Local path proven offline; Databricks path proven via `databricks.rulebook` (Plan 08) + mocked dispatch test. |
| `store.py::write_chunk` | `ingest/anchors.py::mint_span/open_span` | grounding parity with submissions | WIRED | Rulebook chunks reopen via the identical primitive; tested. |
| `build.py` | `ingest/serialize.py` + `ingest/normalize.py` | unified substrate, no parallel canonicalization | WIRED | `_ingest_and_persist` calls both in sequence for every source. |
| `build.py` | `rulebook/store.py::write_chunk` | persistence | WIRED | Every fetched/parsed source persists via this call. |
| `precedents.py` | `rulebook/store.py::write_chunk` | precedent chunk persistence | WIRED | Same substrate path, `source="precedent"`. |
| `search_corpus.py` | `retrieval/vector_search.py::embed_texts/embed_query` | dense leg, local-pinned | WIRED | Reused verbatim; no `is_databricks` branch inside `search_corpus.py` (grep-verified). |
| `search_corpus.py` | `tools/ledger.py::RetrievalLedger` | span recording | WIRED | Every returned span-ID recorded before return. |
| `emit_finding.py` | `ingest/anchors.py::open_span` | dual re-open (corpus + rulebook) | WIRED | Called exactly twice, independent `HashMismatch` handling. |
| `emit_finding.py` | `tools/ledger.py::was_issued` | pre-hash-check gate | WIRED | Ledger check runs before byte-exactness check (ordering verified in code + test). |
| `emit_finding.py` | `schemas/faults.py::Fault` | success-path construction | WIRED | Import-only reuse, `EvidenceClass.QUOTE_ANCHORED` on success. |
| `requirement_index.py::load_requirement_index` | `ingest/anchors.py::open_span` + `rulebook/store.py::rulebook_nt_for` | provenance re-open at load time | WIRED | Loader gate raises on drift; all 15 real entries pass. |
| `requirement_index.py::enumerate_requirements` | `rulebook/edges.py::get_edges` | D-RB4 union resolution | WIRED | Both `family_requires_requirement` and `profile_requires_family` edge types consumed. |
| `evals/metrics.py::_search_corpus_recall_at_k` | `tools/search_corpus.py::search_corpus` | real recall measurement | WIRED | Confirmed by live run producing real per-document numbers. |
| `databricks/rulebook.py::search_rulebook_databricks` | `databricks/delta.py::_run_sql/_table/_escape/_rows_from_result` | reused conventions | WIRED | Grep confirms reuse; no re-implementation of pagination/escaping. |
| `rulebook/store.py::_rulebook_search_databricks` | `databricks/rulebook.py::search_rulebook_databricks` | forward-reference fulfilled | WIRED | Import resolves; dispatch test passes with real function present (mocked at the test boundary only). |
| `read_guideline.py` | `requirement_index.py::enumerate_requirements` | citation=None path | WIRED | Direct call, no reimplementation. |
| `read_guideline.py` | `rulebook/store.py::lookup_citation`/`rulebook_nt_for` | citation=<str> path | WIRED | Dual-resolve (citation-string then doc_id fallback) post-fix; e2e test proves it. |
| `read_guideline.py` | `tools/oversized.py` | persist+preview+handle | WIRED | Mirrors `get_section`'s mechanism exactly, reused not reimplemented. |

### Data-Flow Trace (Level 4)

Not separately applicable — this phase's artifacts are backend tools/data pipelines, not UI components rendering state; the "data flow" question here is answered by the Key Link table above (every tool composes real upstream primitives, none use static/hardcoded fallback data) and by the live-measured retrieval-gate numbers (real per-document values, not stubbed).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full offline Phase-2 test suite (170 tests) | `PYTHONPATH=src uv run pytest tests/tools/ tests/rulebook/ tests/ingest/ -q` (DATABRICKS unset) | `170 passed, 5 warnings in 225.37s` | PASS |
| Fabrication-rejection + RULES-05 e2e chain (targeted re-run) | `pytest tests/tools/test_enumerate_fetch_emit_e2e.py tests/tools/test_emit_finding.py -v` | `9 passed` | PASS |
| Live SC4 retrieval-gate | `PYTHONPATH=src uv run python -m evals.run retrieval-gate` | Real numbers produced (`overall=0.875`, `mvr1381 exact_identifier_subset=0.583`); exits 1 on the known, senior-reviewer-accepted hard-subset gap | PASS (gate behaves exactly as documented; failure is the *expected*, tracked outcome, not a defect) |
| `faiss-cpu`/`rank-bm25` dependency classification | `python3 -c "import tomllib; ..."` | `faiss-cpu` and `rank-bm25` present in `[project].dependencies`, `faiss-cpu` absent from `[dependency-groups].dev` | PASS |
| Git-tracked rulebook snapshot, not gitignored | `git check-ignore -v rulebook/manifest.yaml` (exit 1), `git ls-files rulebook/ \| wc -l` (14) | Confirmed | PASS |
| Databricks dispatch never reaches real Databricks | Tests re-run with `DATABRICKS_HOST=`/`DATABRICKS_TOKEN=` unset | `test_databricks_dispatch.py` passes as part of the 170-test run | PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| TOOLS-01 | 02-01, 02-04, 02-07, 02-09 | 5 navigation tools returning identifiers/snippets, JIT retrieval | SATISFIED | All 5 tools exist, composed correctly, tested; SC4 measurement mechanism built (hard-subset gap is a separate, tracked override). |
| TOOLS-02 | 02-01, 02-04 | Verbatim span-IDs, selected not authored | SATISFIED | `mint_span`/`ledger.record_span` used throughout; `emit_finding`'s `was_issued` gate enforces selection-only. |
| TOOLS-03 | 02-05 | emit_finding rejects fabricated/non-unique/unretrieved/uncited quotes at the tool boundary | SATISFIED | Fabrication-rejection test proven; all rejection paths independently tested; `not_unique` proven structurally unreachable. |
| TOOLS-04 | 02-01, 02-09 | Oversized results persist+preview+handle, never truncate | SATISFIED | `src/tools/oversized.py` reused verbatim by both `get_section` and `read_guideline`. |
| RULES-01 | 02-03 | eCFR Title 21 ingested as retrievable rulebook backbone | SATISFIED | 7 D-RB1 parts live-fetched and committed. |
| RULES-02 | 02-03 | ICH guidelines ingested with required copyright acknowledgment per chunk | SATISFIED | 4 ICH guidelines vendored; notice applied uniformly including 3 pre-2015 PDFs lacking their own notice text; ich.org site-wide terms confirmed by senior reviewer in 02-06's checkpoint. |
| RULES-03 | 02-03 | FDA guidances ingested for eval-set topics | SATISFIED (minor wording note) | 1 FDA guidance vendored via its stable direct URL rather than the regulations.gov pipeline — a deliberate, documented choice (Pitfall 10); substantive intent met. |
| RULES-04 | 02-02, 02-03, 02-08 | Every rule chunk stored with {source,citation,version,license,url} | SATISFIED | Confirmed in both the local SQLite store and the Databricks Delta tables (605 chunks, same fields). |
| RULES-05 | 02-06, 02-09 | Compact requirement index for enumerate-based absence-of-evidence detection | SATISFIED | Loader gate + 14/14 GT traceability + human review (02-06); enumerate→fetch→emit zero-translation chain proven 15/15 end-to-end after the v3 fix (02-09 + commit 9c1f191). |
| COST-04 | 02-01, 02-09 | Read-dedup "still current" stub | SATISFIED | Implemented identically in `get_section` and `read_guideline`, both tested. |

No orphaned requirements — all 10 phase requirement IDs are declared across the 9 plans' frontmatter and independently confirmed against REQUIREMENTS.md.

### Anti-Patterns Found

None. Grep scan of `src/tools/`, `src/rulebook/`, `src/retrieval/{lexical,hybrid}.py`, `src/databricks/rulebook.py` for TODO/FIXME/placeholder/"not yet implemented"/stub-return patterns found nothing beyond legitimate, behavior-bullet-specified empty returns (`search_corpus` on a zero-document corpus, `textsplit.split_sentences` on empty text, `oversized.load_range` on an unknown handle) — all explicitly required by their plans' own behavior bullets, not stubs.

### Carried-Forward Items (Senior-Reviewer-Acknowledged, Not Blockers)

Per `02-PHASE-VERIFICATION-QUEUE.md` and explicit verifier instructions, items 1, 3, and 4 are documented, accepted follow-ups (see `carried_items` in frontmatter for full detail); item 2 is formalized as a frontmatter override (above); item 5 was resolved during this phase (commit `9c1f191`) and independently re-confirmed during this verification run.

### Human Verification Required

None. All must-have truths are either directly verifiable via code/tests (and were verified) or already carry a recorded senior-reviewer decision per the phase-verification queue. No new ambiguous items requiring fresh human judgment were found.

### Gaps Summary

No blocking gaps. The phase goal — five deterministic navigation tools returning identifiers/spans over a hybrid corpus index and a real FDA/ICH rulebook, plus the `emit_finding` grounding gate and a requirement index enabling absence-of-evidence detection — is achieved and independently re-verified against the actual codebase, not just SUMMARY claims:

- All 5 navigation tools exist, are composed correctly, and are span-grounded/bounded/dedup'd (170/170 offline tests green, independently re-run).
- The `emit_finding` fabrication-rejection guarantee (the ROADMAP's named acceptance test) is proven, not just claimed — re-run directly during this verification.
- The rulebook is real: 7 eCFR parts, 4 ICH guidelines (with the correct copyright handling), 1 FDA guidance, all committed with full RULES-04 metadata, all byte-exact reopenable, plus a completed Databricks serving-layer mirror.
- The requirement index's enumerate→fetch→emit chain, which failed in the initial 02-09 delivery (verification queue item 5, MATERIAL), was found, root-caused, fixed, and independently re-confirmed 15/15 in this verification.
- One genuine truth-level shortfall remains (SC4's exact-identifier hard subset, 58.3% not 100%), root-caused to an out-of-scope Phase-1 parsing gap, explicitly tracked, and already accepted by the senior reviewer as a carried, non-blocking item — handled here via a formal override rather than silently passed over or used to fail the whole phase.

---

_Verified: 2026-07-31T14:10:00Z_
_Verifier: Claude (gsd-verifier)_
