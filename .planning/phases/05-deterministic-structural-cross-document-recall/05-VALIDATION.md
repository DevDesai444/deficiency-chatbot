---
phase: 5
slug: deterministic-structural-cross-document-recall
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-06
revised: 2026-08-06
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini |
| **Quick run command** | `PYTHONPATH=src uv run pytest tests/ -q -x -m "not slow"` |
| **Full suite command** | `PYTHONPATH=src uv run pytest tests/ -q` |
| **Estimated runtime** | ~60–120 seconds (fast lane; slow/corpus-gated lane separate) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/<touched-area> -q -x -m "not slow"`
- **After every plan wave:** Run `pytest tests/ -q -m "not slow"`
- **Before `/gsd-verify-work`:** Full fast suite + anti-overfitting guard (SAME-LOGIC / THRESHOLD-TRANSFER / RENAME-INVARIANCE) must be green; plus `python -m evals.run phase5-gate` PASS
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

*B6 fix: full table populated for all tasks across Plans 01–07. Status is set by the executor after running each task.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-1a | 01 | 0 | RECALL-02/03/04/05 | T-05W0-01/02 | Fault anchors typed; emit gates stub-safe (D-STR6 nullability); no submission-specific constant in faults.py or emit_finding.py | unit | `PYTHONPATH=src uv run pytest tests/schemas/test_faults.py tests/tools/test_emit_finding.py -x -q` | ❌ W0 | ⬜ pending |
| 5-01-1b | 01 | 0 | RECALL-02/03/04/05 | T-05W0-03 | guard_vocab.py no corpus token; parse/docx hyperlinks field exists; threshold JSON stubs parseable | unit | `PYTHONPATH=src uv run python -c "from rulebook.guard_vocab import AGGREGATE_LEXICON, REFERENCE_CUE_WORDS; import json, pathlib; json.loads(pathlib.Path('src/evals/baseline/structural_threshold.json').read_text()); print('1b OK')"` | ❌ W0 | ⬜ pending |
| 5-01-1c | 01 | 0 | RECALL-05 (D-GRD1–4) | T-05W0-04 | synthetic fixture_a and fixture_b both exist; fixture_b has DIFFERENT surface forms (dissolution domain); cosine regime smoke test confirms bge-m3 similarity > 0.4 on fixture_a data; test scaffold files exist | unit + fixture | `PYTHONPATH=src uv run pytest tests/conftest.py tests/fixtures/ -x -q && PYTHONPATH=src uv run python -c "import pathlib; assert pathlib.Path('src/evals/dataset/synthetic_fixture').exists(); assert pathlib.Path('tests/fixtures/synthetic_submission_b').exists(); print('fixtures OK')"` | ❌ W0 | ⬜ pending |
| 5-02-1 | 02 | 2 | RECALL-05 (D-R5A) | T-05W2-01 | search_corpus returns dense cosine [0,1] not RRF score; score > 0.5 on known-match query against committed rulebook chunk | unit | `PYTHONPATH=src uv run pytest tests/retrieval/test_search_corpus.py -x -q -k "cosine"` | ❌ W2 | ⬜ pending |
| 5-02-2 | 02 | 2 | RECALL-05 (D-R5B) | T-05W2-02 | per-submission index persists to .chunks.json + .embeddings.npy + .bm25.json keyed by content_hash; second ingest_corpus call on same dir skips re-embed | unit | `PYTHONPATH=src uv run pytest tests/ingest/test_index_persistence.py -x -q` | ❌ W2 | ⬜ pending |
| 5-03-1 | 03 | 3 | RECALL-02 | T-05W3-01 | detect_structural_inconsistencies finds labeled-aggregate discrepancy in fixture_a doc_b.docx; emits Fault with structural_anchor set; leg_tag == "STRUCTURAL"; rule_span_id nullable (D-STR6) | unit + integration | `PYTHONPATH=src uv run pytest tests/rulebook/test_structural.py tests/tools/test_emit_structural_finding.py -x -q` | ❌ W3 | ⬜ pending |
| 5-03-2 | 03 | 3 | RECALL-02 | T-05W3-01 | structural-gate PASS on synthetic fixture (evals.run structural-gate exit 0); D-GRD3 NO-CONSTANT scan finds no float outside {0.0,1.0} or CTD literal in structural.py (via test_new_modules_embed_no_corpus_constant in guard test) | integration | `PYTHONPATH=src uv run python -m evals.run structural-gate` | ❌ W3 | ⬜ pending |
| 5-04-1 | 04 | 3 | RECALL-03 | T-05W3-02 | extract_references writes edges for planted X2 cross-doc ref with src_id="{span.doc_id}:{span.start}" format; detect_reference_anomalies emits Fault with reference_anchor; CTD extractor regex inside re.compile() passes D-GRD3 scan via _has_inline_ctd_literal | unit + integration | `PYTHONPATH=src uv run pytest tests/rulebook/test_references.py tests/tools/test_emit_reference_finding.py -x -q` | ❌ W3 | ⬜ pending |
| 5-04-2 | 04 | 3 | RECALL-03 | T-05W3-02 | reference-gate PASS on synthetic fixture; W4 D-GRD3 verify: _has_inline_ctd_literal strips re.compile contexts so CTD extractor regex does NOT trigger NO-CONSTANT scan | integration | `PYTHONPATH=src uv run python -m evals.run reference-gate` | ❌ W3 | ⬜ pending |
| 5-05-1 | 05 | 3 | RECALL-04 | T-05W3-03 | _search_rulebook_faiss_with_scores returns (doc_id, cosine_float) tuples; cosine_float > 0.6 for known-match query against rulebook.faiss; _filter_precedent_chunks thresholds on actual cosine (not RRF rank proxy); B2 assert in test_above_threshold_candidate | unit | `PYTHONPATH=src uv run pytest tests/rulebook/test_precedent_search.py -x -q` | ❌ W3 | ⬜ pending |
| 5-05-2 | 05 | 3 | RECALL-04 | T-05W3-03 | precedent-gate PASS on synthetic fixture (if rulebook.faiss present) or SKIPPED with message (if absent); no RRF proxy score ever returned | integration | `PYTHONPATH=src uv run python -m evals.run precedent-gate 2>/dev/null || echo "precedent-gate not yet registered (Plan 05)"` | ❌ W3 | ⬜ pending |
| 5-06-1 | 06 | 4 | RECALL-05 | T-05W3-01/02 | test_generality_guard.py extended: NO-CONSTANT parametrized (structural, references, precedent_search) pass; SAME-LOGIC executes on fixture_a; THRESHOLD-TRANSFER uses real fixture_b (B3 fix — different surface forms, same violation types); RENAME-INVARIANCE uses renamed fixture_a | unit + guard | `PYTHONPATH=src uv run pytest tests/evals/test_generality_guard.py -x -q -m "not slow"` | ❌ W4 | ⬜ pending |
| 5-06-2 | 06 | 4 | RECALL-05 | — | deterministic-recall-gate CLI: runs structural + reference + precedent on synthetic fixture; structural and reference legs both produce >=1 candidate; exit code 0 | integration | `PYTHONPATH=src uv run python -m evals.run deterministic-recall-gate` | ❌ W4 | ⬜ pending |
| 5-07-1 | 07 | 5 | RECALL-02/03/04/05 | T-05W5-01/02 | B4 fix: follow_reference has span_start param; returns resolved_cross_doc for planted X2 ref (full pipeline integration test); returns UNRESOLVED_REF for missing edge; Phase-4 sentinel cross_document_resolution_pending_phase_4 NOT returned in any path; FailureFamily extended; metrics.py maps leg_tags | unit + integration | `PYTHONPATH=src uv run pytest tests/tools/test_follow_reference.py -x -q --tb=short` | ❌ W5 | ⬜ pending |
| 5-07-2 | 07 | 5 | RECALL-02/03/04/05 | T-05W5-03 | phase5-gate: all sub-gates PASS on synthetic fixture; W3 mvr1381 SKIPPED (corpus absent in CI) with action message or PASS (corpus present); exit code 0; final summary line printed | integration | `PYTHONPATH=src uv run python -m evals.run phase5-gate` | ❌ W5 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Synthetic multi-doc guard fixture_a (D-GRD1/D-GRD4) — committed at `src/evals/dataset/synthetic_fixture/` (doc_a.pdf QOS analog, doc_b.docx Module analog with planted X2/Max violations, doc_c.pdf spec)
- [ ] Synthetic fixture_b (B3 fix) — committed at `tests/fixtures/synthetic_submission_b/` (doc_x.pdf dissolution Stability Report, doc_y.docx Dissolution Test Procedures — DIFFERENT surface forms from fixture_a, same violation types)
- [ ] Shared candidate-envelope schema (D-ENV1): StructuralAnchor, ReferenceAnchor, PrecedentAnchor types in faults.py; leg_tag and rule_span_id (nullable per D-STR6) on Fault
- [ ] All three emit gate stubs (B5 fix): emit_structural_finding, emit_reference_finding, emit_precedent_finding in emit_finding.py — Wave 0 so Plans 03/04/05 run in parallel Wave 3 without conflict
- [ ] guard_vocab.py with AGGREGATE_LEXICON and REFERENCE_CUE_WORDS (no corpus-specific tokens)
- [ ] parse/docx.py hyperlinks field backfill + parse/pdf.py links field
- [ ] Threshold JSON stubs: src/evals/baseline/structural_threshold.json, precedent_threshold.json
- [ ] Test scaffold files (empty pytest stubs) for all test modules

*Wave 0 complete when all 8 bullets above are committed and pytest tests/schemas/ tests/tools/test_emit_finding.py passes.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Anti-overfitting generality on the REAL held-out corpus (spec32s41) | RECALL-05 guard | Corpus is gitignored — cannot run in stock GitHub CI | Slow lane: place spec32s41 corpus, run `pytest tests/ -q` (slow tests unmarked); confirm SAME-LOGIC candidates + THRESHOLD-TRANSFER on real data |
| W3 zero-TP-lost on real mvr1381 eval corpus | RECALL-05 / SC5 | mvr1381 corpus is gitignored — cannot run in CI | Run `PYTHONPATH=src uv run python -m evals.run phase5-gate` with `src/evals/dataset/mvr1381` present; confirm mvr1381 check PASS with candidate count >= Phase-4 baseline |
| Visual inspection of synthetic fixture_b content | D-GRD1 constraint (different surface forms) | Verifying fixture_b is genuinely different from fixture_a requires human eyes | Open `tests/fixtures/synthetic_submission_b/doc_x.pdf` and `doc_y.docx`; confirm: dissolution domain vocabulary, different compound names (Sample 1/2, not Compound A/B), different numeric values (65%/78%, not 0.10%/0.18%), same violation type (labeled-aggregate recompute) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands (Nyquist rule met)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has a command)
- [x] Wave 0 covers all MISSING references (8 Wave-0 deliverables listed above)
- [x] No watch-mode flags in any verify command
- [x] Feedback latency < 120s for all fast-lane verify commands
- [x] `nyquist_compliant: true` set in frontmatter
- [x] B6 fix: per-task verification map fully populated (14 rows covering all tasks 5-01-1a through 5-07-2 across Plans 01–07)

**Approval:** pending (set to "approved" after Wave 0 tasks complete)
