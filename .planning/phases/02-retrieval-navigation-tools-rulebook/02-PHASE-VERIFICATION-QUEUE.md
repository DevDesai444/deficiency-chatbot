# Phase 2 — Senior-Reviewer Verification Queue

Items the senior reviewer must resolve at **phase verification** (none block plan execution; recorded during 02-06 finalize and Wave 3). Phase verification does NOT auto-run — it waits for the senior reviewer.

## 1. Requirement-index 3.2.S.5 classification assumption (integration proof)
The D-RI1(2) traceability test (14/14) passes against **hardcoded manifests** that assume `mvr1381` and `spec32s41` classify to family **3.2.S.5** (reference-standard content). A green test proves *"IF the profile includes 3.2.S.5, the CFR entries fire"* — it does NOT prove real ingestion tags these docs 3.2.S.5.
**Action:** run real `ingest_corpus` on `mvr1381` + `spec32s41` and confirm 3.2.S.5 is classified, so `CFR-211160B-SOUND-BASIS` / `CFR-211194-CALCULATIONS` fire in production, not only in the unit fixture. If real classification differs, re-tag the two entries from the manifest (entries are correct; only the linkage needs integration proof).

## 2. SC4 exact-identifier hard subset = 7/12 (not 100%)
`retrieval-gate` (02-07) exits 1 against its own baseline: `mvr1381`'s exact-identifier hard subset is 7/12 because 5 anchors sit on **scanned PDF pages with no offline OCR** (D-RB6 forbids Databricks in CI). Root cause: a Phase-1 `src/parse/pdf.py` gap — the OCR-less scanned-page fallback computes but **discards** `page.get_text("text")`. See `deferred-items.md` (02-07). **Decision needed:** fix the pdf.py fallback (may shift the frozen Phase-0 `recall_by_family` baseline — cross-cutting) vs. accept the documented offline limitation vs. re-scope the SC4 hard-subset bar.

## 3. Vendored rulebook binaries committed as plain blobs (no Git LFS)
`rulebook/**` (7 eCFR XML + 5 PDFs + 1 xlsm, ~7.2M) committed as regular git blobs because LFS wasn't configured at vendoring time (02-03). **Decision needed:** migrate `rulebook/**` to Git LFS (`.gitattributes`) vs. leave as-is.

## 4. Rulebook FAISS dense-index rebuild unreliable for large PDF chunks
`rulebook.store.rebuild_local_index()` is unreliable for the whole-PDF chunks (~71k chars) — the local FAISS dense leg of the *rulebook* (02-03 deferred item). The SQLite store (`lookup_citation`/`all_chunks`) is fully populated and is what `read_guideline` + the loader gate use; no agent-facing tool depends on the rulebook dense leg this phase. **Action:** longer-sequence-safe rebuild before any future plan depends on rulebook dense search.
