# D-PREC Audit — `ANDA-TDDS-Deficiency Roadmap.xlsm` vs `defpredict.main.deficiency_kb`

**Auditor:** senior reviewer session · **Date:** 2026-07-31 · **Status:** COMPLETE — dedupe policy set below.
Method: direct reads of both sources (openpyxl over the xlsm; live SQL over the Delta table via the
`serverless-warehouse`), not assumptions.

## Verdict: they are the SAME dataset, byte-level

| Probe | xlsm (`CMC Def. RoadMap` sheet) | `defpredict.main.deficiency_kb` |
|---|---|---|
| Data rows | **500** (r3–r502; r1 title, r2 header) | **500** |
| Distinct deficiency texts | **385** (115 exact dups in 80 groups) | **385** |
| Blank `anda_number` rows | **83** | **83** (empty string) |
| ANDA distribution | 206463=147, 208528=57, 211293=53, 218384=51, 211396=49, … | identical, count-for-count |
| Schema | 9 named cols (ANDA #, Product Name, Dosage Form, CMC Section, Deficiency Type, Cohort Year, Category, Deficiency, Deficiency Response) | same 9 + `id` + `response_date` (the loader split the mixed-type response col) |

`deficiency_kb` is a load of this exact spreadsheet. There is **no second corpus** — zero cross-source
dedupe is needed. The local `data/deficiency_kb.faiss` (+`deficiency_kb_map.json`) is an embedding
sidecar of the same 500 rows.

Content profile: 8 ANDAs, all TDDS (patch) products; 29 deficiency types dominated by
Specification/CoA (86), Method/Val'n (65), Stability (59); CMC Section overwhelmingly Drug Product
(416/500). `Deficiency Response` is **not response text** — 462 empty / 37 dates / 1 string; only
response *dates* exist in this dataset.

## Dedupe & ingestion policy (D-PREC — decided)

1. **Source of truth = the vendored xlsm** (committed, hashed, offline — satisfies D-RB6). The
   Delta `deficiency_kb` is a derived load; the Phase-2 precedent corpus is built FROM THE XLSM
   through the Phase-1 substrate. Databricks precedent serving (when built) derives from the same
   build keyed by stable row identity — never treated as an independent source.
2. **Within-set dedupe: exact-text collapse at CHUNK level, full row provenance kept.** The 115
   exact-duplicate texts are largely boilerplate letter openings. Identical texts collapse to ONE
   retrievable precedent chunk carrying a LIST of provenance rows (anda_number, product, type,
   cohort). Retrieval never returns five copies of the same boilerplate (precision noise), and no
   provenance is lost (citability). Near-dup/semantic dedupe is explicitly NOT done now — exact
   only; anything fuzzier is measured later if retrieval quality demands it.
3. **Forward-fill the 83 blank-ANDA rows at ingestion** from the letter block above (spreadsheet
   merge semantics the original kb loader did not apply), stamping `anda_inferred: true` on those
   rows — inferred provenance is marked, never silently asserted. This is a strict improvement
   over the existing kb load.
4. **Row identity:** `precedent_row_id = sha256(anda_number|row_ordinal|deficiency_text)[:16]` —
   stable across rebuilds, independent of spreadsheet row renumbering.
5. **Expectation note for consumers:** this corpus contains what reviewers *cited* (deficiency
   text), not how sponsors *responded* — response text does not exist here.

## Coverage-gap finding (actioned)

At audit time, **no Phase-2 plan ingested precedents through the substrate** — 02-03 vendors the
file only (correctly blocked on this audit), 02-08 does not mention precedents. D-RB3(b) requires
ingestion NOW so later precedent-search exposure is a tool-registration, not a re-ingestion.
**Resolution: 02-03 amended with a precedent-ingestion task implementing the policy above.**
