---
phase: 05-deterministic-structural-cross-document-recall
reviewed: 2026-08-08T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - src/rulebook/structural.py
  - src/rulebook/references.py
  - src/rulebook/precedent_search.py
  - src/rulebook/guard_vocab.py
  - src/tools/search_corpus.py
  - src/tools/follow_reference.py
  - src/tools/emit_finding.py
  - src/tools/errors.py
  - src/schemas/faults.py
  - src/ingest/corpus.py
  - src/parse/docx.py
  - src/parse/pdf.py
  - src/evals/run.py
  - src/evals/schema.py
  - src/evals/baseline/precedent_threshold.json
  - src/evals/baseline/structural_threshold.json
  - tests/evals/test_eval_set_integrity.py
  - tests/evals/test_generality_guard.py
  - tests/ingest/test_corpus_index_persistence.py
  - tests/ingest/test_docx_parse.py
  - tests/retrieval/test_hybrid.py
  - tests/rulebook/test_precedent_search.py
  - tests/rulebook/test_references.py
  - tests/rulebook/test_structural.py
  - tests/tools/test_emit_reference_finding.py
  - tests/tools/test_emit_structural_finding.py
  - tests/tools/test_follow_reference.py
  - tests/tools/test_search_corpus.py
findings:
  critical: 6
  warning: 9
  info: 4
  total: 19
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-08-08
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 5 built the three deterministic recall legs (structural aggregate-recompute, cross-document reference graph, precedent similarity) plus the per-submission retrieval surface. The grounding gate (`emit_finding.py`) is well-constructed: every leg re-opens spans byte-exact through `issue_cached_span`/`open_span` before a Fault can exist, and the security requirements (numpy `allow_pickle=False`, pre-compiled regex, DoS caps, no URI fetch) are largely honored. That is the strong part.

However, the review surfaced defects that directly threaten the two things this project exists to protect — **RECALL** (silently dropping real deficiencies) and **CORRECTNESS of the deterministic arithmetic** — plus one crash bug that takes the entire reference leg down on real DOCX input.

The highest-priority findings:

1. **DOCX hyperlink extraction crashes the whole reference leg** — `_extract_hyperlinks` always sets `paragraph_index=None`, and `extract_references` computes `para_idx * 50` on it, raising `TypeError`. Every real DOCX with a hyperlink aborts `extract_references` with no fault-isolation. (CR-01)
2. **The `references.py` fallback `compare_values` silently drops SUM/MAX/MIN/MEAN/`EQUALS` comparisons** (returns `None` for unknown comparators), diverging from the real engine and violating the "same engine, zero divergence" contract. (CR-02)
3. **`compare_values` mis-rounds when stated precision is 0** — `round(x, 0)` returns a float that can still differ, and the whole-number path can both false-positive and false-negative aggregate checks. (CR-03)
4. **Precision-derived comparison in `_scan_tables` can false-positive on rounding** — the recompute is force-formatted to `max(prec, 2)` decimals, defeating the coarser-operand rounding that D-STR4 promises. (CR-04)
5. **VALUE_CONTRADICTION re-emits per-numeric-row without entity matching**, contradicting the leg's own Ruling-6 label-matching design and over-emitting ungrounded contradictions (precision loss). (CR-05)
6. **Threshold JSON files are loaded via cwd-relative paths / not loaded at all** — `precedent_search.py` reads `"src/evals/baseline/precedent_threshold.json"` relative to cwd, and `structural_threshold.json` (value `0.0`) is never read by any structural code. The structural leg ships with **no threshold plumbing at all**, and the precedent threshold silently falls back to a hardcoded `0.6` from any non-root cwd. (CR-06)

## Critical Issues

### CR-01: DOCX hyperlink extraction raises `TypeError` and aborts the entire reference leg

**File:** `src/rulebook/references.py:305,310` (in concert with `src/parse/docx.py:154`)
**Issue:** `parse/docx.py::_extract_hyperlinks` builds every hyperlink dict with `"paragraph_index": None` (line 154). In `extract_references`, line 305 does `para_idx = hl.get("paragraph_index", 0)` — because the key is present with value `None`, `.get` returns `None`, not the `0` default. Line 310 then evaluates `min(para_idx * 50, ...)` → `None * 50` → `TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'`. This exception is raised *outside* the `try/except` that wraps `add_edge` (that try only starts at line 317), so it propagates out of `extract_references` entirely. Any real submission containing a DOCX with at least one relationship-based hyperlink crashes the reference-extraction pass — every cross-reference edge for the whole corpus is lost. Tests never catch this because the DOCX-hyperlink test (`test_docx_hyperlink_extraction`) injects a synthetic cache entry with `"paragraph_index": 0`, not the `None` the real parser emits.
**Fix:**
```python
# references.py, line 305
para_idx = hl.get("paragraph_index") or 0   # coerce None -> 0
```
Add a regression test that feeds a cache entry with `paragraph_index=None` (the real shape) through `extract_references` and asserts no exception.

### CR-02: `references.py` fallback `compare_values` drops SUM/MAX/MIN/MEAN/EQUALS — divergent engine, silent recall loss

**File:** `src/rulebook/references.py:85-116`
**Issue:** The module docstring (D-REF4, line 30-32) promises the reference leg "reuses `compare_values` from `rulebook.structural` identically (same normalizer, same precision-derived tolerance)." When the `try: from rulebook.structural import compare_values` at line 78 succeeds this holds — but the fallback defined at lines 85-116 handles only `LEQ`, `GEQ`, `EQ` and **returns `None` for every other comparator** (line 116). The real engine (`structural.py:122-129`) supports `SUM/MAX/MIN/MEAN/EQUALS` and uses the token `"EQUALS"`, while the fallback uses `"EQ"` — they are not the same set of tokens. If `structural.py` import ever fails (the documented Wave-3 parallel-execution scenario the fallback exists for), any reference-leg comparison that used a `SUM`/`EQUALS` relation would silently abstain (`None` → treated as "no fault"), dropping a real contradiction. This is a latent divergence between two copies of the "one engine."
**Fix:** Delete the fallback entirely and make the import hard (`from rulebook.structural import compare_values` with no `except`) — structural.py is committed, so the fallback is dead risk. If a fallback must remain, mirror the full comparator set and token spelling (`EQUALS`, `SUM`, `MAX`, `MIN`, `MEAN`) exactly, and add a test that asserts `references.compare_values` and `structural.compare_values` return identical results across the full comparator matrix.

### CR-03: `compare_values` whole-number rounding is wrong and can false-positive/false-negative aggregate checks

**File:** `src/rulebook/structural.py:118-129`
**Issue:** `prec = min(_stated_precision(claim_text), _stated_precision(ref_text))`. When either operand has no decimal places (e.g. an integer count "100", or a recompute rendered without decimals), `prec == 0`, and `round(claim_num, 0)` / `round(ref_num, 0)` are still `float`s. For SUM/MAX/MIN/MEAN the check is `rc != rr` — but `round(x, 0)` returns e.g. `0.0`, and float equality after rounding to 0 places treats `0.4` and `0.0`… actually collapses distinct values (`round(0.4,0)==round(-0.4,0)==0.0`), so a genuine mismatch of `0.4` vs `0.0` is rounded away → **false negative (recall loss)**. Conversely, when the MEAN recompute produces a value like `71.5` and the claim is `72`, `prec=0` rounds `71.5`→`72` (banker's rounding in Python: `round(71.5,0)==72.0`) which masks a real violation; a claim of `70` vs mean `70.5` rounds to `70` vs `70` — masked. The D-STR4 promise is "round to the coarser operand's stated decimal precision," but when the coarser operand is a whole number the rounding is far too aggressive and is not symmetric with how the recompute string is generated in `_scan_tables` (see CR-04). This directly corrupts the labeled-aggregate arithmetic that is the structural leg's entire job.
**Fix:** Do not round to 0 places to decide equality. When `prec == 0`, compare with a precision derived from the more precise operand, or compare the raw parsed floats with a precision-tolerance that reflects the *stated* granularity of the claim only (the value under test), never both. Add explicit tests for integer-valued aggregates (e.g. counts) and half-integer means (`71.5` vs stated `72`).

### CR-04: `_scan_tables` defeats precision-derived comparison by force-formatting the recompute to `max(prec, 2)` decimals

**File:** `src/rulebook/structural.py:393-394`
**Issue:**
```python
recomputed_str = str(round(recomputed, max(_stated_precision(claim_text), 2)))
is_violation = compare_values(claim_text, recomputed_str, relation)
```
The recompute is rendered to `max(claim_precision, 2)` decimal places, then handed to `compare_values`, which re-derives precision as `min(claim_prec, recompute_str_prec)`. Because the recompute string now always carries ≥2 decimals, the effective comparison precision is `min(claim_prec, ≥2)` = `claim_prec` — but the *value* being compared has been rounded to a different granularity than the claim. Example: claim `"0.1%"` (prec 1), true SUM `0.14`. `recomputed_str = str(round(0.14, 2)) = "0.14"`. `compare_values("0.1", "0.14", "SUM")`: `prec = min(1,2)=1`, `round(0.1,1)=0.1`, `round(0.14,1)=0.1` → `0.1 != 0.1` is False → **compliant**, correctly. But claim `"0.1%"`, true SUM `0.16`: `round(0.16,1)=0.2` vs `0.1` → violation. That part works, yet the `max(prec, 2)` floor means a claim stated at 0 decimals ("Total: 5", prec 0) compared to a recompute rounded to 2 decimals is still rounded by `compare_values` at `prec=0` (CR-03 territory). The two-stage rounding (once here to `max(prec,2)`, again inside `compare_values`) is not equivalent to "round both to the coarser operand's precision" and introduces cases where a real violation just under the claim's stated precision is masked. The design (D-STR4, docstring lines 33-34) explicitly forbids a fixed epsilon and promises coarser-operand rounding; this double-rounding is an ad-hoc substitute that does not honor that.
**Fix:** Pass the raw `recomputed` float (or its full-precision string) into `compare_values` and let the single, documented precision rule apply once. Remove the `max(_stated_precision(claim_text), 2)` fudge. Add a test where the true aggregate differs from the claim only in the last stated decimal place of the claim (boundary of the intended precision rule).

### CR-05: VALUE_CONTRADICTION iterates every numeric row and flags any that exceeds the limit — no entity/label matching, precision loss and over-emission

**File:** `src/rulebook/references.py:718-779`
**Issue:** Ruling 6 (docstring lines 562-569 and 718) specifies "Step 4: Label matching — find dst table row where col=0 text matches entity." The implementation abandons this: for the `col == 0` label cell it never compares the label to `entity_name`; it just picks the row's first numeric column (`_find_value_col`) and, if `value > limit`, emits a VALUE_CONTRADICTION for that row. So a src span that says "NMT 0.15% for **Compound X**" will flag **every** row in the dst table whose numeric value exceeds 0.15% — including rows for unrelated compounds that the limit does not govern. `entity_name` is extracted (line 704) but only ever inserted into the human-readable `detail` string (line 769); it is never used as a gate. This is a precision failure: it emits contradictions the evidence does not support (the limit may not apply to that row's entity), and each is a `scoping_confidence="full"` VIOLATION (line 753), not a low-confidence lead. It also risks duplicate emission when a table has several rows over the limit, none of which the reference actually addresses.
**Fix:** Restore the label-matching step: only emit `full` confidence when the dst row's col-0 label matches the referenced `entity_name` (case-insensitive containment both directions); emit `low` confidence (or abstain) for value-exceeds-limit rows with no label match, per D-REF3. Add a test with a multi-row dst table where only one row's label matches the src entity and assert exactly one full-confidence contradiction.

### CR-06: Thresholds are not correctly plumbed — precedent uses a cwd-relative path (silent 0.6 fallback); structural threshold JSON is never loaded

**File:** `src/rulebook/precedent_search.py:56,60-71`; `src/evals/baseline/structural_threshold.json` (unreferenced); `src/rulebook/structural.py` (no threshold load)
**Issue:** Two distinct NO-HARDCODING / threshold-plumbing violations:

(a) `precedent_search.py:56` sets `_THRESHOLD_PATH = "src/evals/baseline/precedent_threshold.json"` — a **cwd-relative** path. `_load_precedent_threshold` (line 60-71) opens it inside a broad `try/except Exception` that returns the inline `0.6` on ANY failure (line 71). Run from any directory other than the repo root (e.g. an installed package, a different working dir, or a test that `chdir`s), the `open()` raises `FileNotFoundError`, the except swallows it, and the leg silently uses the hardcoded `0.6`. The whole point of loading from JSON (D-PRC4, anti-overfitting) is defeated whenever cwd ≠ repo root, and there is no log/warning to reveal it. Contrast `evals/run.py`, which correctly builds baseline paths with `Path(__file__).parent / "baseline" / ...`.

(b) `structural_threshold.json` exists (value `0.0`) but **no code in `structural.py` (or anywhere) reads it**. The structural leg's comparison is purely precision-derived, which is by design — but that means the committed baseline threshold file is dead, and the "thresholds must load from the baseline JSON files, not be inlined" contract is only vacuously satisfied because there is no threshold at all. If any future structural tuning parameter is added it will have no plumbing to load from. At minimum this is a misleading artifact; combined with (a) it shows the threshold-loading discipline is not actually wired.
**Fix:** For (a), resolve the path relative to the module: `_THRESHOLD_PATH = Path(__file__).resolve().parents[2] / "evals" / "baseline" / "precedent_threshold.json"` (or thread it from the caller like `evals/run.py` does), and narrow the `except` to `(FileNotFoundError, json.JSONDecodeError, KeyError)` with a `logger.warning` before falling back so a missing file is loud, not silent. For (b), either wire `structural_threshold.json` into a real load path or delete the file and document that the structural leg is threshold-free by construction.

## Warnings

### WR-01: `_span_at_offset` fabricates hyperlink/link anchor spans at synthetic offsets unrelated to the actual reference location

**File:** `src/rulebook/references.py:305-312,341-343`
**Issue:** For hyperlinks the src span offset is computed as `min(para_idx * 50, len-80)` and for PDF links as `min(page_num * 100, len-80)` — arbitrary heuristics that do not point at where the hyperlink/link actually occurs in canonical text. The resulting `src_span` is then minted, stored as edge provenance, and later re-opened byte-exact and surfaced as the finding's evidence (`emit_reference_finding` line 464-465). The span *is* byte-exact re-openable (so the grounding gate passes), but it is byte-exact for the *wrong text* — the evidence quote shown to the analyst is 80 chars starting at an offset that has no relationship to the reference. This is a grounding-integrity concern: a finding that "re-opens" but cites text that does not contain the reference undermines the verbatim-anchor guarantee.
**Fix:** Anchor hyperlink/link edges at a real occurrence of the link anchor text in canonical (search for the target/anchor string), or record that no in-text offset is available and set `scoping_confidence="low"`. Do not mint a plausible-looking span at a fabricated offset.

### WR-02: Reference-anomaly detection double-counts / re-emits because edges are never de-duplicated

**File:** `src/rulebook/references.py:365-388` (extraction) and `545-781` (detection)
**Issue:** `_REF_PATTERNS` includes overlapping patterns (e.g. the generic "see/refer" pattern and the "§X" pattern and the "Table N" pattern can all match around the same location), and each match writes a separate edge with no de-duplication by `(src_id, dst_id, edge_type)`. `detect_reference_anomalies` then iterates all edges and emits a Fault per unresolved/absent edge. The `dedup_key` on the resulting Fault is `f"{src_span.doc_id}:{src_span.start}:null"` (emit_finding line 462) — but multiple distinct edges can share the same `src_span.start` (all anchored via `_span_at_offset` to the same coarse offset) or, conversely, near-duplicate references at slightly different offsets produce many near-identical UNRESOLVED_REF faults. The reference gate expecting "~22 UNRESOLVED_REF" (run.py line 725) suggests the fixture already produces a large, largely-redundant fault set. This inflates the reference leg's output with duplicates (precision noise) even if downstream dedup exists elsewhere.
**Fix:** De-duplicate edges at write time (unique index on `(src_id, dst_id, edge_type)` or an in-memory set before `add_edge`), and de-duplicate anomaly faults by `(anomaly, src_doc, dst_doc)` before returning.

### WR-03: `_extract_limit` regex `\w+` unit group swallows following words and can corrupt unit-compatibility checks

**File:** `src/rulebook/references.py:152-161,215-233`
**Issue:** Each `_LIMIT_PATTERNS` entry ends with `(?:%\s*(?:w/w)?|mg/mL|mg/g|ppm|ppb|g/L|\w+)?` — the trailing `\w+` alternative will match an arbitrary following word when none of the real units apply. E.g. "NMT 0.15 for" captures `"0.15 for"` as the raw limit, and `_units_compatible` then extracts unit `"for"`, comparing it against the dst cell's unit. This can cause spurious unit *mismatches* (abstain — recall loss) or, worse, coincidental matches. The `_units_compatible` normalization strips digits and spaces but keeps whatever `\w+` grabbed. Because `_extract_limit` returns `raw` including the stray word, the numeric parse still works but the unit gate becomes unreliable.
**Fix:** Remove the `\w+` catch-all from the unit alternation, or constrain it to a known unit token set. Anchor the unit to the immediate token after the number only.

### WR-04: `_infer_relation` defaults ambiguous aggregate labels to SUM, silently guessing the arithmetic

**File:** `src/rulebook/structural.py:215-236`
**Issue:** Any aggregate label whose words do not include max/min/average/mean falls through to `return "SUM"` (line 236). "Total" → SUM is defensible, but a label like "Overall" or "Combined" or a mislabeled "Range"/"Count" cell that happens to contain an AGGREGATE_LEXICON word (or was flagged by `_contains_aggregate_word`) will be recomputed as a SUM. Because the comparison then decides violation on `recomputed_sum != claim`, a cell that is genuinely a MAX or a COUNT will be reported as a SUM mismatch — a false positive (precision loss) with a confidently-worded detail string ("recompute … gives X (relation: SUM)"). The engine guesses the operation rather than abstaining when the relation is ambiguous.
**Fix:** Abstain (skip the cell, log `abstain ambiguous_relation`) when no specific relation keyword is present and only a generic "total"/"sum" token justifies a SUM; require that the label unambiguously implies the operation before emitting. At minimum lower `scoping_confidence` to "low" for defaulted relations.

### WR-05: `_find_value_column` picks the single global value column; multi-value tables silently mis-pair claim and basis

**File:** `src/rulebook/structural.py:180-196,308-362`
**Issue:** `_find_value_column` returns the one column with the most numeric cells for the *entire table*. Real regulatory tables routinely have several numeric columns (e.g. "Result | Limit | % of Limit", or per-timepoint stability columns). The scan then treats *only* that one column as claim+basis and ignores the others, so an aggregate stated in a different numeric column is never checked (recall loss), and basis cells summed across a column that mixes results and limits produce a nonsense recompute (false positive). There is no per-column or per-header disambiguation.
**Fix:** Iterate candidate value columns (all columns whose cells are majority-numeric), pairing the aggregate label with the claim in each numeric column and recomputing per column; or use header text to select the correct value column. Add a multi-numeric-column test.

### WR-06: `detect_precedent_candidates` treats any `emit_precedent_finding` non-`ToolRejected` as a Fault, including `None`

**File:** `src/rulebook/precedent_search.py:250-253`
**Issue:** The success branch is `else: faults.append(result)` after `if isinstance(result, ToolRejected):`. If `emit_precedent_finding` ever returns `None` (or anything that is neither a `Fault` nor a `ToolRejected`), it is appended to `faults` as if it were a valid finding. The other legs guard with `isinstance(result, Fault)` (structural.py:434, references.py:628 etc.); precedent uses the looser inverse check. The precedent test even stubs `emit_precedent_finding` to `return None` (`test_precedent_search.py:206`), confirming `None` is a reachable return in tests — the production gate returns a `Fault`, but the asymmetry is a latent bug that would put non-Faults into a `list[Fault]`.
**Fix:** Change to `if isinstance(result, Fault): faults.append(result)` for symmetry with the other legs.

### WR-07: `follow_reference` returns the first resolved edge, ignoring `ref_text` — wrong target when a src span has multiple edges

**File:** `src/tools/follow_reference.py:110-123`
**Issue:** In the cross-doc branch, the loop returns the *first* edge whose `dst_id != "unresolved"` regardless of whether it corresponds to the `ref_text` being resolved. A single src offset can carry several edges (multiple references near the same coarse offset — see WR-01/WR-02), so `follow_reference(doc, "Table 3", ...)` may resolve to whatever edge happens to be first in the DB result order, not the one for "Table 3". `ref_text` is only echoed back in the `label` field (line 121), never used to select among candidate edges.
**Fix:** Filter candidate edges by matching `ref_text` against edge metadata (e.g. store the matched reference text on the edge and compare), or return all resolved candidates and let the caller disambiguate. At minimum document that resolution is offset-based, not text-based.

### WR-08: `_extract_entity_name` regex is over-broad and will match generic capitalized prose, mislabeling contradictions

**File:** `src/rulebook/references.py:848-860`
**Issue:** `_ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z])\b|([A-Z][a-z]+(?:\s+\w+){0,2})")` matches almost any capitalized word (and up to two following words), so "See Analytical" or "Not More" or "The Specification" become the "entity". Since (after CR-05 is fixed) `entity_name` should gate which rows are flagged, an over-broad extractor will either match the wrong entity or match noise, degrading precision. Even in the current code it produces misleading `Referenced entity: 'The Specification'` detail lines.
**Fix:** Constrain entity extraction to the noun phrase adjacent to the limit expression, or to tokens that appear as col-0 labels in the dst table (intersect candidates with dst row labels). Abstain when no confident entity is found rather than returning a generic phrase.

### WR-09: `structural.py` and `references.py` import `logging`/`ToolRejected` but never use them (dead imports; inconsistent logger)

**File:** `src/rulebook/structural.py:46,59`; `src/rulebook/references.py:53,66`
**Issue:** `structural.py` imports `logging` (line 46) but uses `structlog` for `log`; the `logging` import is unused. Both `structural.py` (line 59) and `references.py` (line 66) import `ToolRejected` but never reference it (emit gates return it, callers only `isinstance(result, Fault)`). `references.py` also imports `logging` and builds `log = logging.getLogger(__name__)` while `structural.py` uses `structlog` — inconsistent logging backends across sibling modules in the same phase. Dead imports and mixed loggers are minor but signal the modules were assembled without a final lint pass.
**Fix:** Remove unused `logging`/`ToolRejected` imports; standardize on one logger (structlog) across the recall legs.

## Info

### IN-01: `_search_rulebook_faiss_with_scores` clamps nothing — cosine can exceed [0,1] on non-normalized vectors

**File:** `src/rulebook/precedent_search.py:74-102`
**Issue:** The function documents "cosine_score in [0, 1] for L2-normalized vectors" but does not verify the FAISS index vectors are L2-normalized nor clamp the returned inner product. If the rulebook FAISS asset was built without normalization, `dist` is a raw inner product outside [0,1], and the absolute-threshold semantics silently break. Low severity because the index is expected to be normalized, but there is no guard.
**Fix:** Assert/normalize at query time, or clamp `float(dist)` into `[−1, 1]` and log if out of range.

### IN-02: `structural_threshold.json` and `precedent_threshold.json` carry `measured_on: "synthetic_fixture"` and placeholder values

**File:** `src/evals/baseline/structural_threshold.json:1-7`; `src/evals/baseline/precedent_threshold.json:1-7`
**Issue:** Both baselines are self-described placeholders ("Placeholder; will be updated after … measurement", "Initial value 0.6; update after empirical measurement on mvr1381"). The precedent threshold `0.6` was never measured on the real corpus, so the leg ships with an untuned recall bar. Not a code defect, but the recall/precision behavior of the precedent leg is currently arbitrary.
**Fix:** Measure and record real thresholds before relying on precedent-leg output; until then treat precedent findings as advisory only (which the leg does — `Tier.ADVISORY`).

### IN-03: `_build_doc_first_lines` first-line heuristic (`len >= 4`) can pick a page number or boilerplate as the doc "heading"

**File:** `src/rulebook/references.py:240-261`
**Issue:** The first non-empty line ≥4 chars is taken as the doc's heading for outline matching. Many parsed docs begin with a running header, page label, or date, so the "heading" used for `_find_doc_by_outline` resolution may be boilerplate, causing missed or wrong cross-doc resolutions (recall/precision). Heuristic, not incorrect per se.
**Fix:** Prefer `doc.title`/outline labels over the raw first line; use the first line only as a last resort and skip lines matching page-label/date patterns.

### IN-04: Broad `except Exception` blocks swallow errors across the recall legs without surfacing to callers

**File:** `src/rulebook/references.py:326,356,387,425,600`; `src/tools/search_corpus.py:151,223`; `src/ingest/corpus.py:145,185,195`
**Issue:** Consistent with the D-16 never-abort contract, but several catch-all handlers log at `warning`/`debug` and continue, which can mask systematic failures (e.g. every `add_edge` failing, or every sidecar load falling back to the O(corpus) legacy path) behind a green run. The provenance-recovery `except Exception: pass`-style fallback at references.py:600 will silently mint a fresh span when provenance JSON is corrupt, changing the finding's evidence without signal.
**Fix:** Where a never-abort contract applies, keep the catch but emit a counted telemetry metric (e.g. `add_edge_failures`, `sidecar_fallbacks`) so a systemic failure is visible in the run summary rather than only in scattered warning logs.

---

_Reviewed: 2026-08-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
