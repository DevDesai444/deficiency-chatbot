---
phase: "05"
plan: "03"
subsystem: "structural-leg"
tags:
  - RECALL-02
  - D-STR1
  - D-STR2
  - D-STR3
  - D-STR4
  - D-STR5
  - D-STR6
  - D-GEN2
  - D-GRD3
  - Ruling-5
dependency_graph:
  requires:
    - "05-01: StructuralAnchor, emit_structural_finding, issue_cached_span, guard_vocab.AGGREGATE_LEXICON"
    - "05-01: synthetic fixture doc_b.docx (Table 1: Total Impurities X2a/X2b; Table 2: Max X2c)"
    - "04: Fault, Tier.VERIFIED, EvidenceClass.CODE_VERIFIED"
    - "04: ingest.tables (table_index cell addressing)"
    - "04: tools.ledger (RetrievalLedger)"
  provides:
    - "rulebook.structural: detect_structural_inconsistencies (RECALL-02 pure function)"
    - "rulebook.structural: compare_values, _stated_precision, _find_value_column, _infer_relation"
    - "rulebook.structural: _contains_aggregate_word, _deduplicate_basis (table-primitive helpers)"
    - "tests/rulebook/test_structural.py: 5 passing tests (Ruling 5 real fixture shape)"
    - "tests/tools/test_emit_structural_finding.py: 2 new gate tests (Wave-2 fill-out)"
  affects:
    - "05-06 (RECALL-05 guard): anti-overfitting guard must pass NO-CONSTANT scan on structural.py"
    - "05-07 (Plan 06): structural-gate CLI registration in run.py (deferred per Ruling 4)"
    - "Phase 7: result-exceeds-spec-limit for prose-stated limits (explicitly deferred per D-STR5)"
tech_stack:
  added: []
  patterns:
    - "Word-level AGGREGATE_LEXICON matching (_contains_aggregate_word): multi-word labels like 'Total Impurities' matched by word membership, not exact string"
    - "Numeric-basis deduplication: only cells with parseable numeric text counted as basis (prevents header row inclusion)"
    - "Paired-column pattern: label col (col 0) paired with value col (max-numeric col), both in same row"
    - "D-STR4 precision-derived comparator: round(claim, min(prec_claim, prec_ref)) vs round(ref, same)"
key_files:
  created:
    - "src/rulebook/structural.py: detect_structural_inconsistencies + 7 helper functions (503 lines)"
  modified:
    - "tests/rulebook/test_structural.py: replaced importorskip scaffold with 5 real tests (Ruling 5)"
    - "tests/tools/test_emit_structural_finding.py: added test_fabricated_claim_span_rejected + test_merged_cell_dedup_abstains (Wave-2 fill-out)"
decisions:
  - "D-STR6 honored: rule_span_id=None for labeled-aggregate recompute (pure arithmetic checks)"
  - "Ruling 1 honored: detect_structural_inconsistencies receives ledger from caller; no fresh RetrievalLedger() created"
  - "Ruling 4 honored: src/evals/run.py NOT modified; structural-gate CLI deferred to Plan 06"
  - "D-STR5 honored: docs with tables='unavailable' logged and skipped; docs without table_index logged and skipped"
  - "Phase 7 deferral explicit in module docstring: result-exceeds-spec-limit for prose-located limits deferred per D-STR5+D-STR2"
  - "Word-level AGGREGATE_LEXICON matching: 'Total Impurities'.words.contains('total') -> SUM; exact-match would have silently missed all multi-word aggregate labels"
metrics:
  duration: "~22 minutes"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
  commits: 2
  completed_date: "2026-08-07"
---

# Phase 5 Plan 03: RECALL-02 Structural Inconsistency Leg Summary

Deterministic labeled-aggregate recompute engine over addressable table cells: ONE general algorithm using explicit table-primitive operations (Ruling 5) that detects SUM/MAX/MIN/MEAN aggregate mismatches, with D-STR4 precision-derived comparison (no epsilon), D-STR5 graceful skipping of unavailable tables, D-STR6 nullable rule span, and Ruling 1 ledger pass-through. Tests match the REAL doc_b.docx two-column fixture table shape.

## Completed Tasks

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create structural.py (RECALL-02 detection pass) | 2bddbf5 | src/rulebook/structural.py |
| 2 | Tests + structural.py fixes (Ruling 5 real fixture shape) | bc5b841 | tests/rulebook/test_structural.py, tests/tools/test_emit_structural_finding.py |

## Implementation Notes

### structural.py — Detection Algorithm

`detect_structural_inconsistencies(corpus, manifest, ledger, rulebook_cache_dir)` is the public API. It:

1. Iterates `manifest.documents`; skips any doc where `tables != 'addressable'` (D-STR5)
2. Checks `cache['table_index']` is non-empty before scanning
3. Calls `_scan_tables(corpus, doc_id, ledger, rulebook_cache_dir)` for each addressable doc
4. Returns the flat list of all grounded Faults

`_scan_tables` implements the Ruling 5 explicit table-primitive algorithm:
- `_get_table_cells(cache)` parses `table_index` with `key.split(",", 2)` (Pitfall 1)
- `_find_value_column(cells, cell_texts)` counts numeric-looking cells per column; returns the column with most numeric entries
- `_contains_aggregate_word(text)` checks if any WORD in the cell text is in AGGREGATE_LEXICON (word-level, not exact — handles "Total Impurities", "Maximum Measured Value", etc.)
- `_infer_relation(label_text)` maps word-level aggregate keywords to SUM/MAX/MIN/MEAN
- Basis spans are value-column cells for non-aggregate rows that have NUMERIC text (filters header-row values like "% w/w")
- `_deduplicate_basis(basis)` deduplicates by (doc_id, start, end) (Pitfall 2 — merged cells)
- `compare_values(claim, ref, comparator)` applies D-STR4: `round(val, min_precision)` comparison

Emits via `emit_structural_finding(corpus, rule_span_id=None, anchor, ledger)` (D-STR6, Ruling 1).

### Phase 7 Deferral (D-STR5 + D-STR2)

The module docstring contains the explicit deferral note per Ruling 5:

> "result-exceeds-spec-limit for prose-located values is DEFERRED TO PHASE 7 interpretive tail per D-STR5 (prose value-pairing requires reading meaning = domain-semantic judgment, which fails D-STR2 pure-computation litmus). This leg implements the labeled-aggregate recompute family which is purely arithmetic."

This resolves the SC1 gap: there is NO silent omission — the boundary is documented.

### D-STR4 Correctness

`compare_values('0.104', '0.10', 'LEQ') == False`:
- prec = min(stated_precision('0.104')=3, stated_precision('0.10')=2) = 2
- round(0.104, 2) = 0.10, round(0.10, 2) = 0.10
- 0.10 <= 0.10 -> complies (False = no violation)

Naive exact comparison would give 0.104 > 0.10 = True (false positive). D-STR4 prevents this.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AGGREGATE_LEXICON exact-match silently missed multi-word aggregate labels**
- **Found during:** Task 2, test `test_aggregate_violation_detected_two_column_table`
- **Issue:** Algorithm checked `text.strip().lower() in AGGREGATE_LEXICON` — but "Total Impurities".strip().lower() = "total impurities" which is NOT in AGGREGATE_LEXICON (which contains "total" only). The exact-match would silently miss ALL multi-word aggregate label cells (the most common form in regulatory tables: "Total Impurities", "Maximum Measured Value", etc.)
- **Fix:** Added `_contains_aggregate_word(text)` helper that splits text on word boundaries and checks if ANY word is in AGGREGATE_LEXICON. Updated `_infer_relation` with same word-level matching. This is fully general (D-GEN2 — no submission-specific strings), using only AGGREGATE_LEXICON (D-GRD3).
- **Files modified:** `src/rulebook/structural.py`
- **Commit:** bc5b841

**2. [Rule 1 - Bug] Header row cells counted as basis values**
- **Found during:** Task 2, test `test_single_basis_abstains`
- **Issue:** Basis collection included ALL value-column cells including row 0 (the header row, e.g. "% w/w"). "% w/w" is non-numeric (parse returns None) but still counted as a basis SPAN, making `len(unique_basis) >= 2` even when only one data row existed. This caused the algorithm to attempt a recompute with 1 numeric value and emit a false positive.
- **Fix:** Changed basis deduplication to deduplicate only NUMERIC-PARSEABLE basis cells. The `unique_basis` list is now built from `basis_spans_numeric` (only spans whose cell text parses as float), not from all value-column spans. The abstain condition `len(unique_basis) < 2` now correctly counts independent numeric data cells, not raw span count.
- **Files modified:** `src/rulebook/structural.py`
- **Commit:** bc5b841

**3. [Rule 1 - Note] Plan verification command has a Python bug**
- **Found during:** Task 1 verification
- **Issue:** Plan's `<verify>` code calls `inspect.getsource(detect_structural_inconsistencies.__module__)` but `.__module__` returns a string (module name), not a module object. `getsource` requires a module object and raises `TypeError`.
- **Fix:** Used `import rulebook.structural as _mod; inspect.getsource(_mod)` instead. Substance of the check (AGGREGATE_LEXICON in src, value_col in src) passes correctly.
- **Impact:** Plan verification commands adjusted; all assertions pass.

## Known Stubs

None — structural_threshold.json remains at 0.0 placeholder (set by Plan 01), intentional per D-STR4: the comparison engine has zero free parameters; threshold is precision-derived from data, not a tuned constant.

## Threat Flags

None — the structural leg does not add new network endpoints, auth paths, or schema changes at trust boundaries. Hash verification is enforced by `issue_cached_span` via Plan 01's emit gate (T-05W2A-01 through T-05W2A-03 all mitigated through existing infrastructure).

## Test Results

```
tests/rulebook/test_structural.py::test_aggregate_violation_detected_two_column_table - PASSED
tests/rulebook/test_structural.py::test_precision_derived_complies - PASSED
tests/rulebook/test_structural.py::test_unavailable_table_tier_skipped - PASSED
tests/rulebook/test_structural.py::test_single_basis_abstains - PASSED
tests/rulebook/test_structural.py::test_fixture_cosine_regime - PASSED
tests/tools/test_emit_structural_finding.py::test_issue_cached_span_enables_emit_gate - PASSED
tests/tools/test_emit_structural_finding.py::test_issue_cached_span_rejects_hash_mismatch - PASSED
tests/tools/test_emit_structural_finding.py::test_emit_structural_finding_null_rule_span_accepted - PASSED
tests/tools/test_emit_structural_finding.py::test_emit_structural_finding_empty_basis_rejected - PASSED
tests/tools/test_emit_structural_finding.py::test_fabricated_claim_span_rejected - PASSED
tests/tools/test_emit_structural_finding.py::test_merged_cell_dedup_abstains - PASSED
Total: 11 passed
```

## Self-Check: PASSED

Files confirmed present:
- `src/rulebook/structural.py` - 503 lines (min_lines: 100 satisfied)
- `tests/rulebook/test_structural.py` - 308 lines
- `tests/tools/test_emit_structural_finding.py` - 314 lines
- `src/evals/baseline/structural_threshold.json` - present (threshold: 0.0)

Commits confirmed:
- 2bddbf5: feat(05-03): implement detect_structural_inconsistencies (RECALL-02)
- bc5b841: feat(05-03): tests + structural.py fixes (Ruling 5 real table shape)

Isolation verified:
- `src/tools/emit_finding.py`: NOT modified (B5 fix confirmed)
- `src/evals/run.py`: NOT modified (Ruling 4 confirmed)
- No frozen eval assets touched
- Only structural leg files staged (per Explicit staging constraint)
