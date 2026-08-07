---
phase: "05"
plan: "04"
subsystem: "reference-graph-leg"
tags:
  - RECALL-03
  - D-REF1
  - D-REF2
  - D-REF3
  - D-REF4
  - D-REF5
  - D-RB3
  - D-GRD3
  - Ruling-6
  - VALUE_CONTRADICTION
  - cross-document
dependency_graph:
  requires:
    - "05-01: emit_reference_finding, issue_cached_span, ReferenceAnchor, guard_vocab"
    - "05-01: parse/docx.py hyperlinks key, parse/pdf.py links key (D-REF1)"
    - "05-01: tests/tools/test_emit_reference_finding.py (Wave-0 scaffold replaced)"
    - "04: edges.py (add_edge + get_edges with D-RB3 provenance enforcement)"
    - "04: ingest.corpus.CorpusIndex.cached_entry, ingest.manifest.CoverageManifest"
  provides:
    - "rulebook.references: extract_references (edge registration for all three edge kinds)"
    - "rulebook.references: detect_reference_anomalies (Ruling-6 concrete algorithm)"
    - "compare_values: local fallback implementation (D-REF4; try-import from structural)"
  affects:
    - "05-07: follow_reference uses edges registered by extract_references"
    - "05-06: gate CLI can register reference-gate using detect_reference_anomalies"
tech_stack:
  added: []
  patterns:
    - "Edge key: '{doc_id}:{span.start}' src_id / '{dst_doc_id}:{dst_start}' dst_id"
    - "compare_values try-import from structural with local fallback (Wave-3 parallel)"
    - "All regex patterns inside re.compile() (D-GRD3 / Pitfall 6)"
    - "Edge DoS cap: 1000 edges/doc with log.warning (T-05W2B-04)"
    - "Unit compatibility check before numeric comparison — abstain on mismatch"
    - "No fresh RetrievalLedger() — ledger always passed by caller (Ruling 1)"
key_files:
  created:
    - "src/rulebook/references.py: extract_references + detect_reference_anomalies (761 lines)"
  modified:
    - "tests/rulebook/test_references.py: 5 tests replacing Wave-0 importorskip scaffolds"
decisions:
  - "D-REF4 try-import fallback: compare_values defined locally in references.py as fallback when structural.py not yet present (Wave-3 parallel execution). The fallback is identical in logic to the plan specification — precision-derived comparator, no epsilon, abstain on unparseable."
  - "Ruling-6 VALUE_CONTRADICTION algorithm: iterates ALL col=0 label cells in dst tables, checks value at the paired value column (first numeric col != 0 in the row), compares via compare_values(dst_value, limit_raw, 'LEQ'). Compound A (0.10% <= 0.15%) returns False (compliant). Compound B (0.18% > 0.15%) returns True (violation emitted)."
  - "Unit extraction improvement: _LIMIT_PATTERNS updated to capture broader unit context ('mg/mL', 'ppm', etc.) so _units_compatible correctly identifies mismatches like mg/mL vs %."
  - "Provenance JSON: provenance_span_id is JSON-serialized SpanID dict so detect_reference_anomalies can recover the span without re-minting."
metrics:
  duration: "~1 hour"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 1
  commits: 1
  completed_date: "2026-08-07"
---

# Phase 5 Plan 04: Reference Graph Leg — extract_references + detect_reference_anomalies Summary

Cross-document reference graph leg (RECALL-03) with the Ruling-6 concrete edge-to-value resolution algorithm: hyperlink/textual_ref/value_crossref extraction into edges.py; UNRESOLVED_REF, ABSENT_TARGET (manifest-checked), and VALUE_CONTRADICTION detection with full unit-compatibility check; Compound B (0.18%) correctly flagged as VALUE_CONTRADICTION against NMT 0.15%, Compound A (0.10%) correctly NOT flagged.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create references.py + tests (TDD: RED → GREEN) | a7277a7 | src/rulebook/references.py, tests/rulebook/test_references.py |

## Implementation Notes

### references.py — extract_references

Reads the parsed corpus cache for each document and extracts three edge kinds:

1. **DOCX hyperlinks** (`cache["hyperlinks"]`) — each hyperlink rels entry is walked, target resolved against corpus doc_ids/filenames, edge registered with `edge_type="hyperlink"`.
2. **PDF links** (`cache["links"]`) — link annotations from `page.get_links()` (added by Plan 01 parse backfill), same resolution path.
3. **Textual references** (`_REF_PATTERNS` over canonical text) — five general regex patterns covering "see/refer/per §X", table numbers, figure numbers, CTD section refs (in `re.compile()` — D-GRD3/Pitfall-6 exempt), section numbers. Cue words from `REFERENCE_CUE_WORDS` (D-GRD3 registered allowlist). Value cross-refs (`_LIMIT_PATTERNS` with adjacency cue-word filter) additionally register `edge_type="value_crossref"` edges.

Edge key format (documented in module docstring for Plan 07 `follow_reference` compatibility):
- `src_id = "{doc_id}:{span.start}"`
- `dst_id = "{dst_doc_id}:{dst_start}"` or `"unresolved"`

DoS cap: 1000 edges per document per edge kind (T-05W2B-04). URIs stored as strings, never fetched (T-05W2B-01). Regex patterns fixed, not constructed from input (T-05W2B-02).

### references.py — detect_reference_anomalies

Iterates all edges from the database and applies the full Ruling-6 pipeline:

**UNRESOLVED_REF:** `dst_id == "unresolved"` → emit with `scoping_confidence="full"`.

**ABSENT_TARGET (D-REF5):**
- Target doc not in manifest → `scoping_confidence="full"` (genuinely absent).
- Target doc in manifest but `parse_failed`/`unsupported` → `scoping_confidence="low"` (declared boundary, route to Phase 7).

**VALUE_CONTRADICTION (Ruling 6 — full pipeline):**
- Step A: `_extract_limit(src_text)` via `_LIMIT_PATTERNS` — captures numeric value AND unit string ("0.15%", "0.15 mg/mL").
- Step B: entity name extraction from src text (general pattern, no corpus constant).
- Step C: target table selection from `dst_cache["table_index"]` grouped by table_id.
- Step D: label matching — iterate all `col=0` cells in each table.
- Step E: unit compatibility check — `_units_compatible(limit_raw, value_text)` — abstain on mismatch (mg/mL vs % → no Fault).
- Step F: `compare_values(dst_value, limit_raw, "LEQ")` — True = violation.
- Confidence: `"full"` when edge exists (hyperlink/textual_ref/value_crossref); `"low"` for label-match-only (D-REF3).

**Ruling-6 arithmetic verified:**
- `compare_values("0.10%", "0.15%", "LEQ")` → 0.10 ≤ 0.15 → `False` (Compound A COMPLIES — no Fault).
- `compare_values("0.18%", "0.15%", "LEQ")` → 0.18 > 0.15 → `True` (Compound B VIOLATION → Fault emitted).

### D-REF4 parallel-execution fallback

Since structural.py is written by the sibling Plan 03 executor in Wave 3, it may not be committed when references.py first runs in CI. The module uses:

```python
try:
    from rulebook.structural import compare_values
except ImportError:
    def compare_values(claim_text, ref_text, comparator): ...  # identical logic
```

Once structural.py is committed, the real import takes over automatically. The fallback is identical in algorithm — precision-derived comparator, no epsilon, abstain on unparseable.

### Test suite — 5 tests

1. `test_docx_hyperlink_extraction` — D-REF1: DOCX `hyperlinks` key → `edge_type="hyperlink"` edge registered.
2. `test_textual_ref_pattern_matches` — D-REF1: "See Table 3 in Document B" → `textual_ref` edge.
3. `test_absent_target_manifest_check` — D-REF5: manually added edge to non-existent doc_id → `ABSENT_TARGET` Fault with `scoping_confidence="full"`.
4. `test_value_contradiction_compound_b_correct` — Ruling 6: X1 arithmetic: Compound B (0.18%) > NMT 0.15% = VIOLATION emitted; detail contains "0.18". No Compound-A-only fault (0.10% COMPLIES).
5. `test_value_contradiction_unit_mismatch_abstains` — D-REF4/D-STR4: `src_limit="0.15 mg/mL"`, `dst_value="0.18%"` → unit mismatch → abstain → no VALUE_CONTRADICTION Fault.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unit extraction needed richer pattern to capture non-percent units**
- **Found during:** Task 1 (test_value_contradiction_unit_mismatch_abstains test failure)
- **Issue:** `_LIMIT_PATTERNS` captured only `%` and `% w/w` as units in the capture group but not `mg/mL`. Result: `_extract_limit("NMT 0.15 mg/mL ...")` returned `limit_raw = "0.15"` (no unit), causing `_units_compatible("0.15", "0.18%")` to incorrectly return True (both treated as unitless).
- **Fix:** Extended `_LIMIT_PATTERNS` capture group to include `mg/mL|mg/g|ppm|ppb|g/L|\w+` units so `limit_raw` preserves the unit string.
- **Files modified:** `src/rulebook/references.py` (pattern update before commit)
- **Commit:** a7277a7 (fixed inline before commit, not a separate commit)

**2. [Rule 3 - Blocking] D-REF4 try-import from structural needed for parallel Wave-3 execution**
- **Found during:** Task 1 implementation (structural.py not yet in worktree)
- **Issue:** Plan says `from rulebook.structural import compare_values` but structural.py is written by the sibling Plan 03 executor and may not exist at test time.
- **Fix:** Added `try: from rulebook.structural import compare_values except ImportError: <local impl>` pattern. Local fallback is identical in logic to the plan specification. Auto-fixed under Rule 3 (blocking issue) — documented here per deviation protocol.
- **Files modified:** `src/rulebook/references.py`

### Plan Confirmations (Non-Deviations)

- `emit_finding.py` NOT modified (B5 fix confirmed).
- `run.py` NOT modified (Ruling 4 confirmed).
- `structural.py` NOT touched (per-leg isolation — sibling executor owns it).
- `precedent_search.py` NOT touched (sibling executor).
- No fresh `RetrievalLedger()` created in references.py (Ruling 1).

## Known Stubs

None. All detection paths are implemented. The `compare_values` import fallback is not a stub — it is a full identical implementation for parallel-wave isolation.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: edge_table_provenance | `src/rulebook/references.py` | Edge provenance spans are JSON-serialized SpanID dicts in the edges table. Tampered edge provenance is validated at emit_reference_finding call time via issue_cached_span + open_span HashMismatch check (T-05W2B-03). |

## Test Results

```
tests/rulebook/test_references.py::test_docx_hyperlink_extraction PASSED
tests/rulebook/test_references.py::test_textual_ref_pattern_matches PASSED
tests/rulebook/test_references.py::test_absent_target_manifest_check PASSED
tests/rulebook/test_references.py::test_value_contradiction_compound_b_correct PASSED
tests/rulebook/test_references.py::test_value_contradiction_unit_mismatch_abstains PASSED
tests/tools/test_emit_reference_finding.py::test_emit_reference_finding_importable PASSED
tests/tools/test_emit_reference_finding.py::test_reference_finding_full_candidate PASSED
tests/tools/test_emit_reference_finding.py::test_reference_finding_unanchored_rejected PASSED
tests/tools/test_emit_reference_finding.py::test_reference_finding_value_contradiction_low_confidence PASSED

9 passed, 5 warnings in 0.05s
```

D-GRD3 self-check: `_has_inline_ctd_literal` returns `[]` for references.py (CTD extractor regex inside `re.compile()` is exempt).
Ruling-6 algorithm check: `compare_values`, `LEQ`, `scoping_confidence`, `REFERENCE_CUE_WORDS` all present in references.py.

## Self-Check: PASSED

All created/modified files confirmed present:
- `src/rulebook/references.py` — extract_references + detect_reference_anomalies + compare_values fallback present. 761 lines (min_lines: 120).
- `tests/rulebook/test_references.py` — 5 tests, all passing.
- `tests/tools/test_emit_reference_finding.py` — 4 tests from Plan 01, still passing.

Commit confirmed:
- a7277a7: feat(05-04): reference graph leg — extract_references + detect_reference_anomalies

HARD confirms:
- emit_finding.py NOT modified in this plan.
- run.py NOT modified in this plan.
- No STATE.md or ROADMAP.md writes (orchestrator owns those after the wave).
