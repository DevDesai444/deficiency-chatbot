# Phase 03 Boundary-Crossing Audit

## Search Method

This audit searched `src/` for producer and boundary names matching:

```text
enumerate classify build_ _key lookup resolve index mint serialize
```

Commands used:

```bash
rg -n "def .*?(enumerate|classify|build_|.*_key|lookup|resolve|index|mint|serialize)|class .*?(.*Index|.*Registry)|enumerate|classify|build_|_key|lookup|resolve|index|mint|serialize" src --glob '*.py'
rg -n "enumerate_requirements|read_guideline|emit_finding|lookup_citation|classify_document|ingest_corpus|cache_key|read_doc_cache|parse_span_ref|run_oracles_tool|get_section|build_corpus_index|build_multi_corpus_index|mint_span|serialize_document|rulebook_nt_for|open_span|follow_reference|search_corpus|open_doc" tests src --glob '*.py'
```

For each candidate producer, I checked its consumers and then searched `tests/` for a test that calls the real producer, feeds its output to the real consumer, and uses committed artifacts or a fixture built through the genuine pipeline. The tell was a hand-written intermediate: literal manifests, dicts, cache keys, span strings, or citation strings where production computes the value.

Classifications:

- `COMPOSED` means a pytest node drives the real producer output into the real consumer.
- `UN-COMPOSED` means both sides have coverage, but the searched test surface did not compose the real boundary on real artifacts.
- `N/A` means the producer and consumer are in the same module with no serialization or identifier boundary between them.

## Candidate Chains

| # | Chain | Producer `file:line` | Consumer `file:line` | Classification | Evidence / disposition |
|---|---|---|---|---|---|
| 1 | Rendered span-ID string -> `parse_span_ref` -> `was_issued` -> `open_span` | `src/tools/get_section.py:36`, `src/tools/search_corpus.py:39`, `src/tools/read_guideline.py:33`, `src/tools/open_doc.py:14`, `src/tools/follow_reference.py:21` | `src/agents/review/spanref.py:42`, `src/tools/emit_finding.py:40` | `COMPOSED` | `tests/agents/review/test_spanref_roundtrip.py::test_rendered_span_reaches_emit_finding_and_produces_a_fault`; seed chain 1 CLOSED by plan 03-06. |
| 2 | `run_oracles_tool` lead -> lead `heading_hint` -> `get_section` -> `parse_span_ref` -> `emit_finding` | `src/agents/review/oracles_tool.py:125` | `src/tools/get_section.py:51`, `src/tools/emit_finding.py:40` | `UN-COMPOSED` | Seed chain 2 OPEN entering this plan. Plan 03-09 has rejection coverage for an un-re-opened lead, but no positive lead-to-accepted-finding composition test yet. |
| 3 | `cache_key` including parser version -> `read_doc_cache` / `CorpusIndex.cached_entry` -> downstream tools | `src/ingest/store.py:36`, `src/ingest/corpus.py:121` | `src/ingest/store.py:70`, `src/ingest/corpus.py:53` | `COMPOSED` | `tests/ingest/test_store.py::test_parser_version_bump_invalidates_cache`; seed chain 3 CLOSED by plan 03-01. |
| 4 | `classify_document` real output -> requirement applicability via `enumerate_requirements` / `read_guideline` | `src/ingest/classify.py:138`, `src/ingest/corpus.py:143` | `src/rulebook/requirement_index.py:161`, `src/tools/read_guideline.py:33` | `COMPOSED` | `tests/rulebook/test_requirement_index_integration.py::test_real_ingest_families_enumerate_corrected_basis_requirements`; documented by `03-P1-CLASSIFICATION-PROOF.md`. |
| 5 | `enumerate_requirements` rows -> `read_guideline(rule_doc_id)` -> `emit_finding` | `src/rulebook/requirement_index.py:161` | `src/tools/read_guideline.py:33`, `src/tools/emit_finding.py:40` | `COMPOSED` | `tests/tools/test_enumerate_fetch_emit_e2e.py::test_enumerate_fetch_emit_15_of_15_resolve_end_to_end`; Phase-2 queue item 5 material chain. |
| 6 | Requirement-index provenance span -> `rulebook_nt_for` -> `open_span` loader gate | `src/rulebook/requirement_index.py:68` | `src/rulebook/store.py:76`, `src/ingest/anchors.py:56` | `COMPOSED` | `tests/rulebook/test_requirement_index.py::test_loader_rejects_hash_drift`; `tests/rulebook/test_requirement_index.py::test_real_requirement_index_loads_against_vendored_rulebook`. |
| 7 | `lookup_citation` whole-document store key -> `read_guideline` fetch mode -> ledger-issued rule span | `src/rulebook/store.py:136` | `src/tools/read_guideline.py:74` | `COMPOSED` | `tests/tools/test_read_guideline.py::test_fetch_mode_reads_real_store_citation`; `tests/tools/test_enumerate_fetch_emit_e2e.py::test_real_store_citation_path_still_resolves_via_lookup_citation`. |
| 8 | `serialize_document` cell ranges -> `build_table_index` -> `open_span` table cell proof | `src/ingest/serialize.py:27` | `src/ingest/tables.py:24`, `src/ingest/anchors.py:56` | `COMPOSED` | `tests/ingest/test_tables.py::test_build_table_index_maps_cells_to_reopenable_spans`; `tests/ingest/test_tables.py::test_merged_coordinates_share_origin_span`. |
| 9 | `mint_span` -> `open_span` byte-exact re-open | `src/ingest/anchors.py:46` | `src/ingest/anchors.py:56` | `COMPOSED` | `tests/ingest/test_anchors.py::test_minted_span_reopens_byte_exact`; `tests/rulebook/test_store.py::test_written_chunk_span_reopens_byte_exact_via_open_span`. |
| 10 | `search_corpus` chunk span -> ledger -> `open_span` | `src/tools/search_corpus.py:39` | `src/ingest/anchors.py:56`, `src/tools/emit_finding.py:40` | `COMPOSED` | `tests/tools/test_search_corpus.py::test_search_corpus_returns_bounded_span_grounded_ledger_recorded_results`; plus chain #1 emit path. |
| 11 | `open_doc` outline span -> ledger -> loop-side parse/open path | `src/tools/open_doc.py:14` | `src/agents/review/spanref.py:42`, `src/ingest/anchors.py:56` | `COMPOSED` | `tests/agents/review/test_spanref_roundtrip.py::test_open_doc_outline_span_survives_the_round_trip`. |
| 12 | `follow_reference` same-document resolution -> outline span -> loop-side parse/open path | `src/tools/follow_reference.py:21` | `src/agents/review/spanref.py:42`, `src/ingest/anchors.py:56` | `COMPOSED` | `tests/agents/review/test_spanref_roundtrip.py::test_follow_reference_resolved_span_survives_the_round_trip`. |
| 13 | `build_corpus_index` / `build_multi_corpus_index` fixture builders -> `CorpusIndex.cached_entry` real cache shape | `tests/tools/conftest.py:26`, `tests/agents/review/conftest.py:146` | `src/ingest/corpus.py:53` | `COMPOSED` | `tests/agents/review/test_conftest_smoke.py::test_build_multi_corpus_index_persists_three_real_entries`; fixtures route through `serialize_document -> normalize -> build_table_index -> write_doc_cache`. |
| 14 | `build_response_format` / `build_tool_schema` schema derivation -> static tool schema consumers | `src/llm/structured.py:76`, `src/llm/structured.py:109` | `tests/unit/test_tool_schema_derivation.py:89` | `COMPOSED` | `tests/unit/test_tool_schema_derivation.py::test_build_tool_schema_matches_databricks_constraints`; schema work is covered as derivation output, not a real-data corpus chain. |
| 15 | `safe_resolve` path normalization -> `ingest_corpus` file walk | `src/ingest/limits.py:73` | `src/ingest/corpus.py:108` | `COMPOSED` | `tests/ingest/test_corpus.py::test_symlink_escape_is_rejected_and_does_not_abort_batch`; security boundary but not an enumerate/classify/build chain. |
| 16 | Internal section heading discovery -> `_build_section` -> `split_document` output | `src/parse/section_splitter.py:172` | `src/parse/section_splitter.py:248` | `N/A` | Same-module parser assembly; no serialized identifier crosses into a separately tested consumer. |

16 candidate chains examined, 1 UN-COMPOSED.

## Seed Chain Status

| Seed | Required chain | Status |
|---|---|---|
| 1 | rendered span-ID string -> `parse_span_ref` -> `was_issued` -> `open_span` | `COMPOSED`; closed by `tests/agents/review/test_spanref_roundtrip.py::test_rendered_span_reaches_emit_finding_and_produces_a_fault`. |
| 2 | `run_oracles` lead -> `get_section` -> `emit_finding` | `UN-COMPOSED`; positive path remains open until Task 2 writes `tests/integration/test_composition_chains.py::test_oracle_lead_reopened_becomes_an_accepted_finding`. |
| 3 | `cache_key` -> parse output -> served cache entry | `COMPOSED`; closed by `tests/ingest/test_store.py::test_parser_version_bump_invalidates_cache`. |
