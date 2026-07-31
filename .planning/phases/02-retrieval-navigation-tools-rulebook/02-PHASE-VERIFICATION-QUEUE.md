# Phase 2 — Senior-Reviewer Verification Queue → Phase-3 Entry Gating

**Phase 2 VERIFIED (passed, `02-VERIFICATION.md`).** Senior-reviewer disposition of the items below:

| Item | Disposition |
|---|---|
| **5** (RULES-05 enumerate→fetch→emit) | **RESOLVED** (`9c1f191`, 15/15 e2e) |
| **2** → **P1** (3.2.S.5 real-ingestion classification proof) | **PHASE-3 EXECUTION PRECONDITION** — must be green before the drive loop runs (it corrupts the recall number Phase 3 measures). **Runs AFTER P2** (the 3.2.S.5 classification signal may itself sit on the OCR-less scanned pages P2 recovers). |
| **1** → **P2** (SC4 7/12 — reclassified: PARSE gap, not retrieval) | **PHASE-3 EXECUTION PRECONDITION** — `src/parse/pdf.py` drops the embedded text layer on OCR-less scanned pages (the parsed_partial-honesty gap from Phase 1); fix recovers the 5 anchors, lifts SC4 toward 12/12, update SC4 baseline. **NOT an override — fixing the cause.** |
| **code-review 2** (scoped to un-crossed-boundary hunt) | **ENTRY CRITERION into Phase-3 execution** — not a style pass; hunt for more enumerate→X / build→Y / classify→Z chains unit-tested each side but never composed on real data (3 found this phase). |
| **3** (LFS), **4** (rulebook FAISS rebuild) | tracked hygiene, non-blocking |

**Gate:** Phase-3 execution starts only after P1 + P2 green AND senior-reviewer confirm. Phase-3 *planning* (`/gsd-discuss-phase 3`) may proceed in parallel now.

---

Original recorded items (detail retained below):

## 1. Requirement-index 3.2.S.5 classification assumption (integration proof)
The D-RI1(2) traceability test (14/14) passes against **hardcoded manifests** that assume `mvr1381` and `spec32s41` classify to family **3.2.S.5** (reference-standard content). A green test proves *"IF the profile includes 3.2.S.5, the CFR entries fire"* — it does NOT prove real ingestion tags these docs 3.2.S.5.
**Action:** run real `ingest_corpus` on `mvr1381` + `spec32s41` and confirm 3.2.S.5 is classified, so `CFR-211160B-SOUND-BASIS` / `CFR-211194-CALCULATIONS` fire in production, not only in the unit fixture. If real classification differs, re-tag the two entries from the manifest (entries are correct; only the linkage needs integration proof).

## 2. SC4 exact-identifier hard subset = 7/12 (not 100%)
`retrieval-gate` (02-07) exits 1 against its own baseline: `mvr1381`'s exact-identifier hard subset is 7/12 because 5 anchors sit on **scanned PDF pages with no offline OCR** (D-RB6 forbids Databricks in CI). Root cause: a Phase-1 `src/parse/pdf.py` gap — the OCR-less scanned-page fallback computes but **discards** `page.get_text("text")`. See `deferred-items.md` (02-07). **Decision needed:** fix the pdf.py fallback (may shift the frozen Phase-0 `recall_by_family` baseline — cross-cutting) vs. accept the documented offline limitation vs. re-scope the SC4 hard-subset bar.

## 3. Vendored rulebook binaries committed as plain blobs (no Git LFS)
`rulebook/**` (7 eCFR XML + 5 PDFs + 1 xlsm, ~7.2M) committed as regular git blobs because LFS wasn't configured at vendoring time (02-03). **Decision needed:** migrate `rulebook/**` to Git LFS (`.gitattributes`) vs. leave as-is.

## 4. Rulebook FAISS dense-index rebuild unreliable for large PDF chunks
`rulebook.store.rebuild_local_index()` is unreliable for the whole-PDF chunks (~71k chars) — the local FAISS dense leg of the *rulebook* (02-03 deferred item). The SQLite store (`lookup_citation`/`all_chunks`) is fully populated and is what `read_guideline` + the loader gate use; no agent-facing tool depends on the rulebook dense leg this phase. **Action:** longer-sequence-safe rebuild before any future plan depends on rulebook dense search.

## 5. Requirement-index citation ↔ rulebook-store key granularity mismatch (D-RI2 / D-EF1(5) end-to-end) — MATERIAL
Empirically found in 02-09: **all 15 requirement-index `citation` strings fail to resolve** via `rulebook.store.lookup_citation`. The index citations are **subsection/glossary-level** (`"21 CFR 211.160(b)"`, `"ICH Q6A -- 3.3(e) Water Content"`, `"ICH Q2(R2) -- Glossary: Specificity/Selectivity"`) but the store keys are **document-level** (`ecfr-211.160`, `ICH Q6A`, …). The **loader gate still passes** (it validates the *provenance span's doc_id*, which resolves) — but the D-RI2/D-EF1(5) **"enumerate → fetch → emit, zero translation" contract fails on real data**: an agent enumerating the index then calling `read_guideline(citation=…)` (or `emit_finding` with that rule citation) gets `not_found`. `read_guideline`'s own code is proven correct (controlled entry + the real `"21 CFR 211.166"` path both work end-to-end). Detail: 02-09 `deferred-items.md`.
**Action (requirement-index v2→v3, senior-reviewer):** align the index `citation` field with what `lookup_citation` keys on — either (a) store/resolve subsection-level citations in the rulebook, (b) make `lookup_citation` citation-normalization-aware, or (c) set the index citations to the document-level keys the store already has. **Must resolve before Phase 3 wires the agent loop** (the enumerate→emit chain is the RULES-05 headline mechanism).
