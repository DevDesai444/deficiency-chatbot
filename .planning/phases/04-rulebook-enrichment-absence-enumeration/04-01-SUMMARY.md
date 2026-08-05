---
phase: 04-rulebook-enrichment-absence-enumeration
plan: 01
subsystem: rulebook
tags: [ich, ecfr, requirement-index, coverage-gate, faiss, byte-exact-spans, absence-enumeration]

# Dependency graph
requires:
  - phase: 02-retrieval-navigation-tools-rulebook
    provides: "requirement_index loader gate + enumerate_requirements + build_requirement_edges + generic edge table + build_ich offline-first vendoring + emit_finding grounding gate"
  - phase: 01-ingestion-foundation
    provides: "byte-exact span primitives (mint_span/open_span), D-05 family registry, CoverageManifest, rulebook store"
provides:
  - "ICH Q1A(R2) stability guideline vendored + ingested (ich rulebook chunks 4 -> 5)"
  - "Requirement index grown 15 -> 25 per-requirement entries decomposing Q1A/Q3A/Q3B/Q6A"
  - "profile_requires_family closure edges expanded 2 -> 4 (spec-family whole-section absence, D-SEC1)"
  - "Committed, ratcheted coverage baseline (coverage_baseline.json)"
  - "python -m evals.run coverage-gate: no-regress floor + per-absence-deficiency traceability floor"
affects: [04-02, 04-03, absence-enumeration, RECALL-01, Phase-7-verifier]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "measure -> record -> ratchet coverage bar (mirrors cmd_retrieval_gate; no baked target number)"
    - "traceability floor as a code gate (>=1 firing index entry per absence_of_evidence eval deficiency)"
    - "LLM-draft per-requirement index entry validated by the byte-exact loader gate as acceptance authority"

key-files:
  created:
    - "rulebook/ich/Q1A-R2_Guideline.pdf (vendored, date-pinned 2003-02-06, sha256 in manifest)"
    - "src/evals/baseline/coverage_baseline.json"
  modified:
    - "src/rulebook/build.py (ICH_GUIDELINES += Q1A-R2)"
    - "rulebook/manifest.yaml (new ich Q1A(R2) row; 13 -> 14 rows)"
    - "src/rulebook/requirement_index.yaml (15 -> 25 entries)"
    - "src/rulebook/requirement_index.py (version 4 -> 5; +2 spec-clause closure edges)"
    - "src/evals/run.py (cmd_coverage_gate + coverage-gate subcommand)"
    - "src/tools/__init__.py (lazy PEP-562 barrel; circular-import fix)"

key-decisions:
  - "Q1A(R2) placed first in ICH_GUIDELINES; date-pinned to the R2 publication date 2003-02-06"
  - "10 new per-requirement entries across Q1A (stability, 3.2.S.7/3.2.P.7), Q3A (impurities, 3.2.S.4.1), Q3B (degradants, 3.2.P.5), Q6A (specs, 3.2.S.4.1/3.2.P.5)"
  - "New closure edges drug_substance->3.2.S.4.1 and drug_product->3.2.P.5, each with a byte-exact 21 CFR 314.50 spec-clause provenance span"
  - "coverage-gate ratchets ALL measured sources (incl. precedent) as a no-regress floor; traceability floor treats an un-ingestable submission as a failure, never a silent skip"

patterns-established:
  - "Coverage no-regress floor: baseline JSON of per-source chunk counts + per-family entry counts, gated as measured >= committed"
  - "Traceability floor gate: enumerate_requirements over each absence_of_evidence submission must return >=1 entry"
---

# Phase 4 Plan 01: Rulebook Enrichment + Absence-Enumeration Coverage Floor Summary

Enriched the ICH/FDA rulebook and requirement index from their thin Phase-2 baseline (ich=4 chunks; 15 index entries almost all in family 3.2.S.4.3/ICH Q2) to per-requirement granularity: vendored + ingested ICH Q1A(R2) stability, decomposed Q1A/Q3A/Q3B/Q6A into 10 new byte-exact-grounded index entries (15 -> 25), expanded the profile→family closure with two 21 CFR 314.50 spec-clause edges, and recorded a ratcheted coverage baseline enforced by a new `coverage-gate` CLI that also holds the D-ENR1 traceability floor (>=1 firing index entry per absence_of_evidence eval deficiency).

## What Was Built

- **Task 1 (81956f4):** Added `("Q1A-R2", "ICH Q1A(R2)", "2003-02-06", <database.ich.org URL>, rulebook/ich/Q1A-R2_Guideline.pdf)` to `ICH_GUIDELINES`. `build_ich` fetched the PDF once (264104 bytes), ran it through `extract_pdf` + `_ingest_and_persist` (storing `ICH_LEGAL_NOTICE` per chunk), wrote a manifest row with computed sha256, and `rebuild_local_index()` joined `ich-Q1A-R2` into FAISS. ICH rulebook coverage 4 -> 5 chunks (SC1).
- **Task 2 (ca6b80a):** Grew `requirement_index.yaml` 15 -> 25 with per-requirement entries (Q1A-BATCH-SELECTION / TESTING-FREQUENCY / SIGNIFICANT-CHANGE; Q3A-IDENTIFICATION-THRESHOLD / RESULTS-PRECISION; Q3B-IDENTIFICATION-THRESHOLD / TOTAL-DEGRADATION-REPORTING; Q6A-DESCRIPTION / MICROBIAL-LIMITS / UNIFORMITY-DOSAGE-UNITS). Every `provenance_span_id` was minted with `mint_span` over the persisted rulebook chunk and re-opens byte-exact through the loader gate. Bumped `REQUIREMENT_INDEX_VERSION` 4 -> 5 with a v4->v5 changelog. Expanded `profile_requires_family` closure 2 -> 4 (drug_substance->3.2.S.4.1, drug_product->3.2.P.5), each edge carrying a real byte-exact 21 CFR 314.50 spec-clause span verified before persistence.
- **Task 3 (ad7394d):** Recorded `coverage_baseline.json` (measured post-enrichment: ich=5, total_entries=25, per-family counts). Added `cmd_coverage_gate` + the `coverage-gate` subcommand (lazy imports, LLM-free, Databricks-free). It enforces (a) a per-source/per-family no-regress floor and (b) the traceability floor: for every `absence_of_evidence` eval deficiency (mvr1381 x11, spec32s41 x2, minispec MS-03), the ingested submission fires >=1 applicable requirement (measured: 8 each). `python -m evals.run coverage-gate` exits 0.

## Verification Results

- `build_ich(update_manifest=False)` produces no error rows and includes the Q1A(R2) row — PASS.
- `load_requirement_index()` returns 25 entries (>15), every entry byte-exact through the loader gate — PASS.
- `python -m evals.run coverage-gate` exits 0: `COVERAGE-GATE OK` with `traceability_firing_per_absence_doc={minispec:8, mvr1381:8, spec32s41:8}` — PASS.
- `grep -iE "mvr1381|spec32s41|heldout32s41" requirement_index.yaml` returns nothing — no corpus constant (D-GEN2) — PASS.
- Full `tests/rulebook tests/tools tests/evals` suite: 223 passed, 0 failed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Broke a pre-existing tools<->requirement_index circular import**
- **Found during:** Setup (before Task 1) — the plan's own Task-2 verify command (`from rulebook.requirement_index import ...` as first import) and `tests/rulebook/test_requirement_index_integration.py` collection both failed at base commit 326ea31.
- **Issue:** `src/tools/__init__.py` eagerly imported `agents.review.oracles_tool`, which chains `agents.review -> registry -> tools.read_guideline -> rulebook.requirement_index`; importing `rulebook.requirement_index` FIRST re-entered it mid-load (before `enumerate_requirements` was defined) and raised a circular `ImportError`.
- **Fix:** Made `run_oracles_tool` a PEP-562 lazy attribute in `tools/__init__.py` (mirrors `ingest`'s lazy barrel), deferring the `agents.review` chain until first access. Public API unchanged (`from tools import run_oracles_tool` still works).
- **Files modified:** src/tools/__init__.py
- **Commit:** 07fb5e2

**2. [Rule 1 - Baseline test updates] Updated tests asserting the pre-enrichment baseline**
- **Found during:** Task 3 regression sweep — 5 tests hard-coded the Phase-2 counts the plan intentionally moves.
- **Issue/Fix:** ich 4->5 chunks (`test_ich_ingest`, `test_metadata` manifest 13->14 rows), `REQUIREMENT_INDEX_VERSION` 4->5 (`test_requirement_index`), and the two boundary-crossing composition tests 15/15->25/25 and 30/30->50/50 (`test_enumerate_fetch_emit_e2e`, `test_read_guideline_dual_resolve`) — the `_ALL_*_MANIFEST` fixtures now classify one document into each of the 6 (was 4) families that carry index entries. The composition tests still assert the full enumerate->fetch->emit chain end-to-end (the codebase's boundary-crossing-bug guard is preserved, just at the new count).
- **Files modified:** tests/rulebook/test_ich_ingest.py, tests/rulebook/test_metadata.py, tests/rulebook/test_requirement_index.py, tests/tools/test_enumerate_fetch_emit_e2e.py, tests/tools/test_read_guideline_dual_resolve.py
- **Commit:** ad7394d

## Notes for Downstream Plans

- **Store must be built first (D-RB6):** `data/` is gitignored, so a fresh worktree/CI must run `build_ecfr()/build_ich()/build_fda()` (offline from the committed `rulebook/**` snapshot) + `rebuild_local_index()` before the loader gate / coverage-gate can run. The submission PDFs the traceability floor ingests (`data/32s43-*.pdf`, `data/32s41-*.pdf`) are also gitignored local corpus.
- **Absence enumerator (Plan 03, RECALL-01) is the missing consumer:** the enriched index + the new 3.2.S.4.1 / 3.2.P.5 closure edges are what `enumerate_requirements` walks; the coverage-gate's traceability floor is the CI proof that the index is not blind to any absence eval deficiency.
- **Coverage baseline records `precedent=385`:** these chunks are the Phase-2 precedent ingest, present in the established store. A future rebuild that does not ingest precedent chunks will (correctly) trip the no-regress floor.

## Threat Flags

None — this plan introduces no new network endpoints, auth paths, or trust boundaries beyond the vendored-source and LLM-drafted-entry boundaries already mitigated in the plan's threat register (sha256 on the Q1A PDF, byte-exact loader gate on every index entry, ICH copyright per chunk, version bump on the index change).

## Self-Check: PASSED

- Created files present: rulebook/ich/Q1A-R2_Guideline.pdf, src/evals/baseline/coverage_baseline.json, 04-01-SUMMARY.md
- Commits present: 07fb5e2 (fix), 81956f4 (Task 1), ca6b80a (Task 2), ad7394d (Task 3)
