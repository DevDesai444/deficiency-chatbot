---
phase: "05"
plan: "01"
subsystem: "shared-infrastructure"
tags:
  - D-ENV1
  - issue_cached_span
  - emit-gates
  - guard-vocab
  - parse-backfill
  - synthetic-fixtures
  - eval-integrity
dependency_graph:
  requires:
    - "04: faults.py (Fault, Tier, EvidenceClass), emit_finding.py (ToolRejected), errors.py (KNOWN_REASON_CODES)"
    - "04: ingest.anchors (mint_span, open_span, short_hash, HashMismatch)"
    - "04: tools.ledger (RetrievalLedger)"
    - "04: parse.docx (extract_docx), parse.pdf (extract_pdf)"
    - "04: evals.schema (load_eval_set)"
  provides:
    - "schemas.faults: StructuralAnchor, ReferenceAnchor, PrecedentAnchor; Fault.dedup_key, Fault.confidence_tier, Fault.leg_tag"
    - "tools.emit_finding: issue_cached_span, emit_structural_finding, emit_reference_finding, emit_precedent_finding"
    - "tools.errors: unanchored_structural, no_comparison_basis, unanchored_reference reason codes"
    - "rulebook.guard_vocab: AGGREGATE_LEXICON, REFERENCE_CUE_WORDS"
    - "parse.docx: hyperlinks key (D-REF1); parse.pdf: links key (D-REF1)"
    - "src/evals/baseline: structural_threshold.json, precedent_threshold.json"
    - "src/evals/dataset/synthetic_fixture: doc_a.pdf, doc_b.docx, doc_c.pdf"
    - "tests/fixtures/synthetic_submission_b: doc_x.pdf, doc_y.docx, fixture_manifest.json (Ruling 9)"
    - "tests/evals/test_eval_set_integrity.py (HARD CONDITION B guard)"
    - "tests/tools/test_emit_structural_finding.py, test_emit_reference_finding.py"
    - "tests/rulebook/test_structural.py, test_references.py, test_precedent_search.py (Wave-0 scaffolds)"
  affects:
    - "05-02 through 05-07: all plans consume the D-ENV1 envelope and emit gates"
    - "evals scorer: HARD CONDITION B test locks the eval set against accidental fixture inclusion"
tech_stack:
  added:
    - "fitz (PyMuPDF): PDF link annotation extraction; synthetic fixture PDF creation"
    - "python-docx: synthetic fixture DOCX creation"
    - "zipfile + xml.etree.ElementTree: DOCX hyperlink rels extraction"
  patterns:
    - "issue_cached_span: open_span (byte-exact) + ledger.record_span (issuance bridge)"
    - "D-STR6: rule_span_id nullable for arithmetic-only structural faults"
    - "D-CON1: dedup_key computed as SHA-256 of (doc_id, leg_tag, claim_span_id)"
    - "Ruling 2: only StrEnum members used (Tier.VERIFIED, Tier.ADVISORY, EvidenceClass.CODE_VERIFIED)"
    - "Ruling 9: fixture_manifest.json with arithmetic proof of each planted violation"
key_files:
  created:
    - "src/schemas/faults.py: StructuralAnchor, ReferenceAnchor, PrecedentAnchor classes; Fault extended"
    - "src/rulebook/guard_vocab.py: AGGREGATE_LEXICON, REFERENCE_CUE_WORDS frozensets"
    - "src/evals/baseline/structural_threshold.json"
    - "src/evals/baseline/precedent_threshold.json"
    - "src/evals/dataset/synthetic_fixture/doc_a.pdf"
    - "src/evals/dataset/synthetic_fixture/doc_b.docx"
    - "src/evals/dataset/synthetic_fixture/doc_c.pdf"
    - "tests/fixtures/synthetic_submission_b/doc_x.pdf"
    - "tests/fixtures/synthetic_submission_b/doc_y.docx"
    - "tests/fixtures/synthetic_submission_b/fixture_manifest.json"
    - "tests/tools/test_emit_structural_finding.py"
    - "tests/tools/test_emit_reference_finding.py"
    - "tests/rulebook/test_structural.py"
    - "tests/rulebook/test_references.py"
    - "tests/rulebook/test_precedent_search.py"
    - "tests/evals/test_eval_set_integrity.py"
  modified:
    - "src/tools/emit_finding.py: three new emit gate functions + issue_cached_span helper"
    - "src/tools/errors.py: three new reason codes"
    - "src/parse/docx.py: hyperlinks key added (D-REF1)"
    - "src/parse/pdf.py: links key added (D-REF1)"
    - "tests/ingest/test_docx_parse.py: _DOCX_KEYS assertion updated (Rule 1 fix)"
decisions:
  - "D-STR6 honored: rule_span_id is Optional[SpanID] = None in emit_structural_finding — pure arithmetic checks carry no rule span"
  - "Ruling 1 resolved: issue_cached_span bridges cache-derived spans into RetrievalLedger via open_span + record_span"
  - "Ruling 2 enforced: no Tier.CANDIDATE or EvidenceClass.RETRIEVED in source — only VERIFIED, ADVISORY, CODE_VERIFIED"
  - "Ruling 3 enforced: Fault.dedup_key and Fault.confidence_tier both present on D-ENV1 envelope"
  - "Ruling 9 implemented: fixture_manifest.json with per-violation arithmetic proofs (X1–X3, Y1–Y2)"
  - "HARD CONDITION B: frozen eval-set integrity test locks doc_ids=['minispec','mvr1381','spec32s41'] and deficiency_count=35"
  - "THRESHOLD-TRANSFER: fixture_b (dissolution vocabulary) separate from fixture_a (impurity vocabulary)"
metrics:
  duration: "~3 hours"
  tasks_completed: 3
  tasks_total: 3
  files_created: 19
  files_modified: 4
  commits: 3
  completed_date: "2026-08-07"
---

# Phase 5 Plan 01: Wave 0 Foundation — D-ENV1 Envelope and Shared Infrastructure Summary

D-ENV1 FULL envelope (StructuralAnchor / ReferenceAnchor / PrecedentAnchor + dedup_key + confidence_tier on Fault), three deterministic emit gates behind the issue_cached_span bridge, general-vocabulary allowlist, parse-layer hyperlink/link backfill, arithmetically-verified synthetic fixtures, and Wave-0 test scaffolds — all committed and green.

## Completed Tasks

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1a | D-ENV1 FULL envelope + issue_cached_span + three emit gates | f46be6f | faults.py, emit_finding.py, errors.py |
| 1b | guard_vocab + parse hyperlink/link backfill + threshold stubs + composition test | 6ecee93 | guard_vocab.py, parse/docx.py, parse/pdf.py, structural_threshold.json, precedent_threshold.json, test_emit_structural_finding.py |
| 1c | Synthetic fixtures + Wave-0 test scaffolds + eval-set integrity (HARD CONDITION B) | 2dab7a1 | doc_a.pdf, doc_b.docx, doc_c.pdf, doc_x.pdf, doc_y.docx, fixture_manifest.json, test_eval_set_integrity.py, test_rulebook_*.py |

## Implementation Notes

### Task 1a: D-ENV1 FULL Envelope

Added three typed anchor classes to `src/schemas/faults.py` before the `Fault` class:

- `StructuralAnchor`: claim_span_id, basis_span_ids, relation (Literal[EQUALS/LEQ/GEQ/SUM/MAX/MIN/MEAN]), expected_value, actual_value, comparison_store, scoping_confidence
- `ReferenceAnchor`: src_span_id, dst_span_id, edge_type, anomaly, scoping_confidence
- `PrecedentAnchor`: submission_span_id, precedent_doc_ids, similarity_scores, threshold, anda_excluded

Extended `Fault` with six optional fields (all default=None, no existing field changed):
`structural_anchor`, `reference_anchor`, `precedent_anchor`, `leg_tag` (Literal["ABSENCE","STRUCTURAL","REFERENCE","PRECEDENT"]), `dedup_key` (str), `confidence_tier` (Literal["full","low"])

Added to `src/tools/emit_finding.py`:

- `issue_cached_span(ledger, span_id, nt)`: calls `open_span()` for byte-exact verification, then `ledger.record_span()` — bridges cache-derived spans into the issuance gate (Ruling 1)
- `emit_structural_finding()`: nullable rule_span_id (D-STR6), validates claim + basis spans via issue_cached_span, requires ≥1 unique basis span, returns Fault(tier=Tier.VERIFIED, evidence_class=EvidenceClass.CODE_VERIFIED, leg_tag="STRUCTURAL")
- `emit_reference_finding()`: validates src_span_id via issue_cached_span, returns Fault(tier=Tier.VERIFIED, leg_tag="REFERENCE")
- `emit_precedent_finding()`: validates submission_span_id via issue_cached_span, returns Fault(tier=Tier.ADVISORY, confidence_tier="low", leg_tag="PRECEDENT")

Added three reason codes to `src/tools/errors.py`: `unanchored_structural`, `no_comparison_basis`, `unanchored_reference`.

### Task 1b: guard_vocab + Parse Backfill + Threshold Stubs

`src/rulebook/guard_vocab.py` (D-GRD3): two frozensets separating general aggregate vocabulary from corpus-specific tokens:
- `AGGREGATE_LEXICON = frozenset({"total","sum","maximum","max","minimum","min","average","mean"})`
- `REFERENCE_CUE_WORDS = frozenset({"see","refer","table","section","module","figure","appendix","as described in","as stated in","per","referenced in"})`

Parse-layer backfill (D-REF1):
- `src/parse/docx.py`: `_extract_hyperlinks()` reads `word/_rels/document.xml.rels` via zipfile/ET, capped at 1000 (log warning T-05W0-04), returns [] on any error (T-05W0-01). `extract_docx()` return dict gains `"hyperlinks"` key.
- `src/parse/pdf.py`: link collection loop after main page loop using `page.get_links()`, each wrapped in try/except. `extract_pdf()` return gains `"links"` key.

Threshold stubs: `src/evals/baseline/structural_threshold.json` and `precedent_threshold.json` both set `threshold: 0.0` (D-STR4/D-PRC4 stubs measured on synthetic fixture, not corpus-tuned).

Composition test `tests/tools/test_emit_structural_finding.py` — THE Ruling 1 Wave-0 gate: builds real corpus cache entry, creates fresh empty `RetrievalLedger()`, verifies `was_issued()` is False, calls `issue_cached_span()`, verifies `was_issued()` is True, then calls `emit_structural_finding()` and verifies returns Fault (GREEN).

### Task 1c: Synthetic Fixtures + Wave-0 Scaffolds

Fixture A (`src/evals/dataset/synthetic_fixture/`): three-document impurity validation set with planted violations:
- `doc_a.pdf`: 3-page Analytical Validation Summary with "NMT 0.15% for any single impurity" limit, PDF link annotation pointing to doc_b.docx
- `doc_b.docx`: Analytical Procedures with Table 1 (Compound B 0.18% > NMT 0.15% [X1]; Total Impurities sum mismatch [X2a/X2b]) and Table 2 (Maximum Measured Value 42.3 < true max 57.8 [X2c])
- `doc_c.pdf`: Analytical Specifications with Impurity C 0.22% > NMT 0.10% [X3], deferral note per D-STR5

Fixture B (`tests/fixtures/synthetic_submission_b/`): dissolution domain, different vocabulary for THRESHOLD-TRANSFER:
- `doc_x.pdf`: Stability Report with "NMT 80% at 30 minutes" dissolution limit, PDF link to doc_y.docx
- `doc_y.docx`: Table A (Total Average 63% < individual reading 65% [Y1]) and Table B (Maximum Release 66% < true max(61,72,68)=72% [Y2])
- `fixture_manifest.json`: Ruling 9 — all violations with arithmetic proofs (X1: 0.18>0.15, X2a: 0.12<0.18, X2b: sum mismatch, X2c: 57.8>42.3, Y1: 63≠71.5, Y2: 72>66)

Wave-0 test scaffolds (pytest.importorskip pattern for Wave-2 modules):
- `tests/rulebook/test_structural.py`: 5 stubs for rulebook.structural
- `tests/rulebook/test_references.py`: 4 stubs for rulebook.references
- `tests/rulebook/test_precedent_search.py`: 4 stubs for rulebook.precedent_search

Eval-set integrity test `tests/evals/test_eval_set_integrity.py` (HARD CONDITION B):
- `test_eval_set_doc_ids_unchanged`: frozen to ['minispec', 'mvr1381', 'spec32s41']
- `test_eval_set_deficiency_count_unchanged`: frozen to 35
- `test_synthetic_fixture_is_invisible_to_scorer`: asserts top-level *.deficiencies.json == frozen list — all 3 GREEN

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_docx_parse.py for new hyperlinks key**
- **Found during:** Task 1b (D-REF1 parse backfill)
- **Issue:** Adding `"hyperlinks"` key to `extract_docx()` return dict caused `tests/ingest/test_docx_parse.py::test_dict_shape_matches_extract_pdf` to fail: `AssertionError: {'filename', 'hyperlinks', 'page_count', 'pages', 'toc'} != {'filename', 'page_count', 'pages', 'toc'}`
- **Fix:** Changed `_PDF_KEYS` assertion to `_DOCX_KEYS = _PDF_KEYS | {"hyperlinks"}` in the test file; updated assertion to `assert set(d) == _DOCX_KEYS`
- **Files modified:** `tests/ingest/test_docx_parse.py`
- **Commit:** 2dab7a1 (included in Task 1c commit)

### Directed Additions (Not Deviations)

**HARD CONDITION B (reviewer-mandated): Eval-set integrity test**

Per reviewer standing constraints, created `tests/evals/test_eval_set_integrity.py` with frozen values captured from `load_eval_set()` at plan-authoring time. Froze `doc_ids = ['minispec','mvr1381','spec32s41']` and `deficiency_count = 35`. Makes accidental inclusion of synthetic fixture into scored eval set structurally impossible in CI. All 3 tests GREEN.

## Known Stubs

The following are intentional stubs with documented rationale — they will be resolved in Wave-2 plans:

| Stub | File | Reason |
|------|------|--------|
| `threshold: 0.0` | `src/evals/baseline/structural_threshold.json` | D-STR4: general threshold, not corpus-tuned; Wave-2 Plan 05-03 calibrates on fixture data |
| `threshold: 0.0` | `src/evals/baseline/precedent_threshold.json` | D-PRC4: general absolute dense-cosine threshold; Wave-2 Plan 05-05 calibrates |
| `pytest.skip(...)` bodies | `tests/rulebook/test_structural.py`, `test_references.py`, `test_precedent_search.py` | Wave-0 scaffolds: bodies intentionally skipped until Wave-2 modules exist (importorskip pattern) |

## Deferred Items

**Pre-existing out-of-scope failure:** `tests/agents/review/test_oracle_leads_real_corpus.py` and `test_oracle_wiring.py` raise errors due to missing real corpus data (`data/32s43-validation-related-compounds-method.pdf` not in worktree — gitignored large files). These are pre-existing and unrelated to Plan 01 changes. Logged to `deferred-items.md`.

**Pre-existing baseline regression guard failure:** `tests/evals/test_baseline_regression_guard.py` fails for the same reason (missing real data files). Pre-existing, out of scope.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: synthetic_fixture_scoring_isolation | `src/evals/dataset/synthetic_fixture/` | New subdirectory at dataset/ could be accidentally glob-included if scorer changes to recursive glob. HARD CONDITION B test guards this at CI level. |

## Test Results

```
Composition test (Ruling 1 Wave-0 gate):
  tests/tools/test_emit_structural_finding.py::test_issue_cached_span_enables_emit_gate - PASSED

Eval-set integrity (HARD CONDITION B):
  tests/evals/test_eval_set_integrity.py::test_eval_set_doc_ids_unchanged - PASSED
  tests/evals/test_eval_set_integrity.py::test_eval_set_deficiency_count_unchanged - PASSED
  tests/evals/test_eval_set_integrity.py::test_synthetic_fixture_is_invisible_to_scorer - PASSED

Reference finding tests:
  tests/tools/test_emit_reference_finding.py::test_emit_reference_finding_importable - PASSED
  tests/tools/test_emit_reference_finding.py::test_reference_finding_full_candidate - PASSED
  tests/tools/test_emit_reference_finding.py::test_reference_finding_unanchored_rejected - PASSED
  tests/tools/test_emit_reference_finding.py::test_reference_finding_value_contradiction_low_confidence - PASSED

Wave-0 scaffolds (importorskip):
  tests/rulebook/test_structural.py - SKIPPED (rulebook.structural not yet implemented)
  tests/rulebook/test_references.py - SKIPPED (rulebook.references not yet implemented)
  tests/rulebook/test_precedent_search.py - SKIPPED (rulebook.precedent_search not yet implemented)
```

## Self-Check: PASSED

All created files confirmed present:
- `src/schemas/faults.py` - StructuralAnchor, ReferenceAnchor, PrecedentAnchor present
- `src/tools/emit_finding.py` - issue_cached_span + 3 emit gates present
- `src/rulebook/guard_vocab.py` - AGGREGATE_LEXICON, REFERENCE_CUE_WORDS present
- `src/parse/docx.py` - hyperlinks key present
- `src/parse/pdf.py` - links key present
- `src/evals/baseline/structural_threshold.json` - present
- `src/evals/baseline/precedent_threshold.json` - present
- `src/evals/dataset/synthetic_fixture/doc_a.pdf` - present
- `src/evals/dataset/synthetic_fixture/doc_b.docx` - present
- `src/evals/dataset/synthetic_fixture/doc_c.pdf` - present
- `tests/fixtures/synthetic_submission_b/doc_x.pdf` - present
- `tests/fixtures/synthetic_submission_b/doc_y.docx` - present
- `tests/fixtures/synthetic_submission_b/fixture_manifest.json` - present
- `tests/evals/test_eval_set_integrity.py` - present
- `tests/tools/test_emit_structural_finding.py` - present
- `tests/tools/test_emit_reference_finding.py` - present
- `tests/rulebook/test_structural.py` - present
- `tests/rulebook/test_references.py` - present
- `tests/rulebook/test_precedent_search.py` - present

All commits confirmed:
- f46be6f: feat(05-01): D-ENV1 FULL envelope + issue_cached_span + three emit gates
- 6ecee93: feat(05-01): guard_vocab + parse hyperlink/link backfill + thresholds + composition test
- 2dab7a1: feat(05-01): synthetic fixtures + Wave-0 test scaffolds + eval-set integrity test

HARD CONDITION A verified: no `*.deficiencies.json` at `src/evals/dataset/` top level.
HARD CONDITION B verified: eval-set integrity test frozen and GREEN.
