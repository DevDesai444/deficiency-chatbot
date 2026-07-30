# Phase 1: Ingestion Foundation - Research

**Researched:** 2026-07-30
**Domain:** Document parsing (PDF+DOCX) · text normalization with offset tracking · content classification · content-addressed span anchoring · corpus persistence
**Confidence:** HIGH (core mechanics empirically verified in-repo; two RISK flags on items 3 and 4)

## Summary

Phase 1 is a **substrate build**, not a feature. Almost every hard part is a *text-plumbing correctness problem* — build one canonical normalized text stream per document, keep a reversible offset map back to the raw source, mint content-addressed span-IDs over it, and serialize table cells into it with a `(table_id, row, col)` index — and only a small part is classification. The good news from investigation: **every load-bearing primitive the 31 locked decisions assume actually exists and behaves as decided.** I verified empirically that (a) python-docx 1.2.0's grid model heals both horizontal (`gridSpan`) and vertical (`vMerge`) merges to a single origin `_tc` element, giving D-31's "many coordinates → one span-ID" for free; (b) Unicode NFC preserves `µ`, `²`, and case (so D-25's NFC-not-NFKC choice is correct and unit-safe) but does **not** fold the ﬁ ligature (so D-25's "ligature fold" must be a *separate explicit op*, a finding the planner must encode); (c) the guarded-dehyphenation rule (D-26) passes all four locked fixtures with a ~15-line algorithm; and (d) a run/segment-based offset map round-trips all four normalization ops in O(log n) lookup and O(edits) memory — negligible at 500-doc scale.

The two real risks are **not** in the decided design — they are external dependencies. **RISK-1 (item 3, offset map):** the map is load-bearing and irreversible-to-redesign after the parser ships; the mitigation is to build it as a first-class `NormalizedText` value object with a property-based round-trip test *before* any consumer depends on it, and to treat "raw" as the **reading-order serialized pre-normalization text retained on disk**, not PDF byte offsets (geometry bridges to the physical page). **RISK-2 (item 4, RapidOCR):** whether the box-returning OCR endpoint is deployed is Databricks *runtime state* the repo cannot verify, and in any no-creds/CI environment OCR is skipped entirely (`ocr.py:78`). Phase 1 must therefore treat scanned-page flat-text as a **standing degradation it DETECTS and marks `parsed_partial`** (D-17), never a thing it fixes or blocks on. A concrete consequence the planner must accept: scanned-table reconstruction cannot be validated inside Phase 1's fidelity suite unless the box endpoint is live, so the fidelity gate runs on **digital PDFs + DOCX** (deterministic, endpoint-free) and scanned-table addressing is reported best-effort per D-30.

**Primary recommendation:** Build a new `src/ingest/` package with a 3-layer text model (physical source → raw serialized text → canonical text) as its spine. Land the `NormalizedText` + offset-map + span-ID core **first**, gate it with a round-trip property test, then layer the DOCX parser, the content classifier (deterministic-first, reusing `structured.py` for escalation), and the SQLite-backed corpus index/manifest on top. Reuse `section_splitter.py`, `layout.py`, `structured.py`, and the `evals/run.py` failure-manifest pattern verbatim; do not touch `upload.py`/`orchestrator.py` (D-13).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Copied verbatim from `01-CONTEXT.md`. These are settled — research is HOW, not WHETHER. (D-12 intentionally does not exist.)

**Classification — taxonomy & output**
- **D-01:** The content classifier emits, per document: a **free-form label/title** (inferred document type), an **optional CTD-family guess**, and a **raw continuous confidence score**. The corpus is **never locked to CTD** — a non-CTD document (cover letter, form, ad-hoc doc) is a first-class citizen with its own free-form label.
- **D-02:** **Non-CTD / low-confidence documents are first-class and always reviewed.** Every ingested doc is indexed and eligible for downstream review regardless of its CTD guess. CTD family is a **routing hint** for oracles/checklists, **never a gate** on whether a document is looked at.
- **D-03:** **No hard confidence threshold in Phase 1.** The classifier records the raw score and routes on it, but sets **no drop/skip cutoff**. Any cutoff is calibrated later by the eval harness.
- **D-04:** Classify at the **document level** and store a **section outline** in the index. Do **not** per-classify every section.

**Classification — taxonomy is data-driven**
- **D-05:** The CTD-family vocabulary moves **out of the `CTDSection` Python enum into a data-driven registry** (each entry: `id`, `label`, one-line **applicability trigger**). Adding Modules 1/2/4/5 or biologics families becomes a **data edit, not a code change**. This registry's shape deliberately **matches Phase 2's RULES-05 requirement index**.
- **D-06:** The **body keyword lexicon** used for classification lives in this **same registry**, keyed per family.

**Classification — mechanism**
- **D-07:** **Deterministic-first with LLM escalation.** A cheap deterministic first pass (regex/TOC/heading signals, extending the existing `ctd.py detect_ctd_section` seam to document level) classifies most docs LLM-free; escalate to a **cheap-model LLM classifier only when deterministic confidence is low or the doc is non-CTD**.
- **D-08:** **Classification signals = heading/TOC text + a data-driven body keyword lexicon.**
- **D-09:** **Filename / folder path is DELIBERATELY EXCLUDED as a classification signal** — not even a weak tie-breaker. A low-confidence tie **escalates**, it does not fall back to folder naming.
- **D-10:** **No separate letterhead/first-page signal.** *(Partially superseded by D-28.)*
- **D-27:** **The escalation rate is MEASURED and reported per run.** Ingestion records what fraction of documents each tier resolved (`regex` / `lexicon` / `llm`) and surfaces it in the run summary.
- **D-28:** **The deterministic tier MUST NOT assume a Table of Contents or heading markup exists.** The deterministic signal set therefore explicitly includes **the first N lines of the document as raw text**, independent of whether they are marked up as headings. This partially reopens D-10: the first-page title block is the primary signal for *ordinary CMC documents that lack heading markup*.
- **D-29:** **Classification records its TIER and its TRIGGERING EVIDENCE, not just a score.** Each classified document stores which tier resolved it (`regex` / `lexicon` / `llm`) and the **span-ID of the text that triggered the classification**.

**Entry point**
- **D-11:** **Library-first, CLI shell.** Ship a pure `ingest_corpus(root) -> CorpusIndex` library function, wrapped by a thin `python -m ingest <dir>` CLI. Evals and later phases **import the library**.
- **D-13:** The existing **single-file upload API (`upload.py`) and `run_pipeline` (`orchestrator.py`) stay UNTOUCHED this phase.**

**Persistence**
- **D-14:** **Persist to disk:** per-document parse cache + the corpus index/manifest, **content-hash keyed**. Re-runs **skip unchanged documents**; ingestion is **resumable after a mid-corpus failure**. The content-hash is the cache-invalidation key.
- **D-15:** Corpus-index **on-disk storage format** is a **planner call** — should follow existing job-store (Delta/SQLite) conventions where sensible.
- **D-32:** **The persisted cache retains the FULL canonical text** — not just the index, outline, and metadata. Reference **extraction** and **resolution** remain Phase 4 work; Phase 1's only obligation is to leave the text on disk.

**Failure & partial-parse handling**
- **D-16:** **Failures are first-class coverage-manifest rows; ingestion of a 500-doc corpus NEVER aborts on one bad file.** Manifest status vocabulary: **`parsed` / `parsed_partial` / `parse_failed` / `unsupported`**, each with a reason.
- **D-17:** **`parsed_partial` is a distinct, load-bearing status** (not `parsed`). A document that parses but **degrades** is recorded as `parsed_partial` **with what specifically degraded**. Live seam: `src/parse/ocr.py:122` — flat-text OCR silently loses scanned-page tables; that page/section must surface as `parsed_partial`.

**Availability tiers**
- **D-30:** **Three availability tiers, declared per document in the manifest.** Canonical text + span-IDs = ALWAYS; Section outline = best-effort (requires headings); Table cell addressing = best-effort (requires table reconstruction). Downstream phases read capability **from the manifest**, never by discovering it at runtime.

**Span anchors**
- **D-18:** **Section identity = a content-addressed span-ID; heading text = a human-readable LABEL only.** Store BOTH.
- **D-19:** **Span-ID scheme = `{doc_id, start, end}`** — a char-offset range over **one canonical normalized text stream per document** — **plus a short content-hash** of the exact substring. Geometry (`bbox`, `page`) becomes **optional provenance hanging off the offsets, not the identity**.
- **D-20:** **Add a format-neutral canonical text + char-offset layer that BOTH parse paths populate.** PDF *additionally* fills `bbox`/`page`; **DOCX leaves them `null` — never synthetic.**
- **D-31:** **Table cells are ADDRESSABLE — dual addressing over one grounding contract.** Cells are **serialized INTO the canonical text stream in reading order** (ordinary char-range span-ID) **AND** a table index maps **`(table_id, row, col) → span-ID`**. **Serialization order MUST be deterministic and version-stamped.** **Merged cells map many coordinates to ONE span-ID.** Table-tier availability is **best-effort per D-30**.
- **D-21:** **Phase 1 builds the substrate; Phase 2 builds the tools.** Phase 1 delivers canonical text + stable span-ID generation + a **re-open/verify primitive**. Its contract is LOCKED: given a span-ID, return BOTH **(a) the RAW source substring** and **(b) the CANONICAL substring**; **or FAIL if the content-hash no longer verifies.**

**Canonical-text normalization**
- **D-22:** **The cited "verbatim quote" is the RAW source substring**, reconstructed via the canonical→raw offset map — NOT the canonical substring. "Verbatim" = **verbatim-in-source**.
- **D-23:** **A canonical→raw offset map is retained per document.**
- **D-24:** **The normalizer carries a version stamp recorded per document.**
- **D-25:** **Normalization = MODERATE:** Unicode **NFC** + **whitespace-collapse** + **PDF dehyphenation** + **ligature fold** (ﬁ→fi). Each op must be **reversible through the offset map**.
- **D-26:** **PDF dehyphenation MUST be GUARDED — this is a correctness gate.** (a) Never drop the hyphen when the char before it is a **digit**. (b) Otherwise drop only when the rejoined token is **more plausible** (lexicon check). (c) **Keep the hyphen while dropping the line break in all uncertain cases.** (d) Ambiguous forms made retrievable via the **Phase 2 index as alternate keys pointing at the same span-ID** — NOT by duplicating in the canonical stream (one form per span). Requires a **dedicated test fixture**.

### Claude's Discretion
- Corpus-index on-disk storage format (D-15) — planner decides, following existing Delta/SQLite conventions where sensible.
- Exact canonical-text schema shape and how deeply `bbox`/`page`/`reading_order` are threaded — planner/researcher settles (constrained by D-19/D-20: offsets are identity, geometry is optional provenance).

### Deferred Ideas (OUT OF SCOPE)
- Rewire `run_pipeline` / `upload.py` to consume a directory (D-13; Phase 3+).
- **Docling** unified parser (INF-V2-01; only if python-docx table fidelity proves insufficient).
- Section-level CTD tagging (rejected for Phase 1, D-04).
- Confidence-threshold calibration (eval harness, D-03).

### Known gap — uncovered, NOT decided
- **DOCX table → model mapping fidelity is UNCOVERED CONTEXT.** SC2 requires the parse-fidelity suite (merged cells, multi-page tables, borderless tables) to pass on the DOCX path, but the mapping approach was never selected. Treat as **open work with a hard acceptance bar**. Interacts directly with D-31: a mis-mapped table produces *wrong cell addressing*, silently corrupting X1. *(This research resolves most of it — see item 1 and item 5 below.)*
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support (this doc) |
|----|-------------|------------------------------|
| **INGEST-01** | Ingest arbitrary deeply-nested PDF+DOCX tree, no count/depth cap, content-classified (never folder name) | Item 6 (classification), Item 7 (walk + persistence). `os.walk`/`Path.rglob`; content-hash keyed cache; D-09 path-exclusion enforced by construction. Validated by SC1 rename-folders test. |
| **INGEST-02** | Parse DOCX into the **same** unified structured model as PDF | Item 1 (DOCX→model fidelity). python-docx 1.2.0 grid model + `_tc`-identity merge healing verified; borderless=trivial on DOCX; typed `ParseFailed` on complex-merge IndexError. Fills the `evals/run.py:174` DOCX seam. |
| **INGEST-03** | Per-submission corpus index + coverage manifest with per-document availability contract + typed statuses | Item 7. Manifest statuses `parsed/parsed_partial/parse_failed/unsupported`; D-30 availability tiers declared, not discovered. |
| **INGEST-04** | Span-anchor substrate: canonical stream + retained offset map + versioned normalizer + `{doc_id,start,end}`+hash span-IDs + re-open/verify primitive | Items 2, 3, 8. 3-layer text model; run-based offset map (round-trip verified); NFC/ligature finding; guarded dehyphenation algorithm. |
| **INGEST-05** | Every table cell addressable — serialized into canonical text (ordinary span-ID) + `(table_id,row,col)` index; merged cells resolve identically; deterministic version-stamped order | Items 1, 5. Reading-order serialization via `body.iterchildren()` (DOCX) / bbox order (PDF); `_tc`-origin merge dedup; PDF merged-cell RISK flagged. |
</phase_requirements>

## Architectural Responsibility Map

The "tiers" here are the ingestion pipeline's internal layers (this is a batch library, not a web app). Mapping each capability to its owning layer prevents the classic error of leaking normalization into the parser or geometry into identity.

| Capability | Primary Layer | Secondary Layer | Rationale |
|------------|---------------|-----------------|-----------|
| Directory walk, format dispatch, dedup by content-hash | **Corpus orchestrator** (`ingest/corpus.py`) | — | Owns "what files exist"; must never let one bad file abort the batch (D-16). |
| PDF → document dict | **Parse: PDF** (`parse/pdf.py`, existing) | Parse: OCR/layout | Unchanged fast path; already emits the dict shape. |
| DOCX → **same** document dict | **Parse: DOCX** (`ingest/docx_parse.py`, NEW) | — | Must converge on `extract_pdf`'s dict, nulling geometry (D-20). |
| Reading-order serialization (blocks + tables) | **Substrate: serializer** (`ingest/serialize.py`, NEW) | Parse | Produces the *raw serialized text*; table cells serialized here (D-31). |
| 4-op normalization + offset map | **Substrate: normalizer** (`ingest/normalize.py`, NEW) | — | The correctness gate (D-22–D-26). Owns raw↔canonical alignment; nothing else may normalize. |
| Span-ID mint + re-open/verify | **Substrate: anchors** (`ingest/anchors.py`, NEW) | Normalizer | Identity = canonical offsets (D-19); re-open returns raw+canonical (D-21). |
| `(table_id,row,col)` index | **Substrate: table index** (`ingest/tables.py`, NEW) | Anchors | Relational → span-ID (D-31); merged-cell dedup lives here. |
| Content classification | **Classification** (`ingest/classify.py`, NEW) | LLM (`structured.py`) | Deterministic-first, LLM escalation (D-07); consumes serialized text + registry. |
| Registry (families + lexicon) | **Data** (`ingest/registry/*.yaml|json`, NEW) | Classification | Data-driven, RULES-05-shaped (D-05/D-06). |
| Corpus index + coverage manifest persistence | **Persistence** (`ingest/store.py`, NEW) | SQLite (`databricks/delta.py` conventions) | Content-hash-keyed cache, resumable (D-14/D-15). |

**Boundary law:** geometry (`bbox`/`page`) flows *up to* the substrate as optional provenance and stops there — it may **never** enter a span-ID (D-19). Normalization happens in exactly one place (`ingest/normalize.py`); the parser emits raw text only.

## Project Constraints (from CLAUDE.md)

Directives extracted from `./CLAUDE.md` that the planner must honor with the same authority as locked decisions:

- **Stack lock:** python-docx is the **MVP DOCX path**; **Docling is v2-deferred** (INF-V2-01) — do NOT adopt it now. PyMuPDF stays the PDF fast path. python-docx bump `1.1 → 1.2` is noted (already installed at 1.2.0).
- **Grounding law:** no finding may exist without a verbatim source anchor (doc → section → span) + the rule it violates. Phase 1 builds the anchor half of this.
- **Generality law:** no assumptions about document count, folder names, or nesting depth; classification is content-driven (mirrors D-09).
- **Cost law:** keep 500+-doc ingestion mostly LLM-free and cheap (deterministic-first).
- **Branch:** all work on `CLI_for_folders`; **build on** the uncommitted `planning.py/summarise.py/sandwich.py/workers.py` redesign — do not clobber it. (Not Phase 1 scope, but do not break its imports.)
- **Stale-docs debt:** README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE describe a **removed AutoGen design** — trust code, not those docs. (`autogen-*` deps in `pyproject.toml` are dead weight; Phase 1 need not remove them but must not depend on them.)
- **GSD workflow:** file edits go through a GSD command; this research feeds `/gsd-plan-phase`.

## Standard Stack

### Core (all already installed — verified by import this session)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **python-docx** | **1.2.0** (installed; latest, released 2025-06-16) | DOCX → unified document dict; merged-cell primitives (`grid_span`, `vMerge`, `_tc` identity) | The MVP DOCX path per CLAUDE.md. DOCX tables are *structural* (`<w:tbl>`), so borderless/merged are handled without geometry inference. `[VERIFIED: import docx; docx.__version__]` `[VERIFIED: pypi.org/pypi/python-docx/json]` |
| **PyMuPDF (fitz)** | **1.28.0** / MuPDF 1.29.0 (installed) | PDF fast path (unchanged); `page.find_tables()` | Already the PDF parser (`parse/pdf.py`). `[VERIFIED: import fitz]` |
| **tokenizers** | **0.21.0** (installed *transitively* via sentence-transformers) | Reference/fallback for offset-tracked normalization (`NormalizedString`) | The canonical implementation of "normalize while keeping char-offset alignment." Available at **zero new dependency cost**. `[VERIFIED: from tokenizers import NormalizedString]` |
| **json-repair** | ≥0.30 (installed) | Escalation-classifier malformed-output salvage (inside `structured.py`) | Already the L3 layer of the hardened structured stack. `[VERIFIED: pyproject.toml:26]` |
| **pydantic** | ≥2.7 (installed) | Unified model + `CorpusIndex`/manifest schemas | Project standard; `schemas/documents.py` is pydantic v2. `[VERIFIED: pyproject.toml:8]` |
| **stdlib:** `unicodedata`, `hashlib`, `bisect`, `pathlib`, `os.walk`, `zipfile`, `sqlite3`, `re` | 3.11 | NFC; content-hash; O(log n) offset lookup; walk; DOCX-as-zip guard; index store; classification regex | No new deps. `unicodedata.normalize("NFC", …)` behavior verified below. `[VERIFIED: Python 3.11.3]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **structlog** | ≥24.1 (installed) | Per-run telemetry incl. **escalation rate** (D-27), cache-hit metrics | Extend for the run summary. `[VERIFIED: pyproject.toml:33]` |
| **PyYAML** *or* stdlib `json` | — | Registry file format (D-05/D-06) | If registry is authored by humans, YAML is friendlier; JSON needs no new dep. Planner call. `[ASSUMED]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom run-based offset map | `tokenizers.NormalizedString` end-to-end | NormalizedString auto-composes alignment for NFC/replace, but **cannot express the guarded-dehyphenation decision** (lexicon+digit guard is external). You would drive replacements yourself anyway. Use custom map for full control; keep NormalizedString as the proven reference + fallback for the NFC leg. `[VERIFIED: tokenizers docs + local import]` |
| python-docx | Docling | Docling unifies PDF+DOCX with better tables but pulls Torch + layout models; **v2-deferred by CLAUDE.md/INF-V2-01**. Do not adopt in Phase 1. `[CITED: CLAUDE.md]` |
| PyMuPDF `find_tables` | `pymupdf_layout` add-on | PyMuPDF now *suggests* `pymupdf_layout` for "greatly improved page layout analysis" (printed at runtime this session), but it is a separate package and overlaps Docling's v2 role. Out of scope. `[VERIFIED: runtime notice]` |
| SQLite index | Delta/Parquet | Existing job store is **SQLite** (`databricks/delta.py:22`); follow it for the index metadata. Parquet only if a columnar scan of manifest rows is needed at scale. `[VERIFIED: src/databricks/delta.py:7,22]` |

**Installation:** No new hard dependencies required for Phase 1. Optional: `pip install pyyaml` if the registry is authored as YAML. python-docx already satisfies the DOCX path.

**Version verification note:** direct PyPI HTTP is sandboxed in this environment; versions above are the **installed** versions confirmed via `import` (authoritative for what Phase 1 code executes against), cross-checked with `pypi.org/pypi/python-docx/json` (WebFetch) and CLAUDE.md's PyPI-dated table (2026-07-30).

## Architecture Patterns

### System Architecture Diagram

Data flow (trace one document input → substrate output):

```
                       ingest_corpus(root)                        python -m ingest <dir>
                              │                                          │ (thin shell, D-11)
                              ▼                                          ▼
        ┌─────────────────────────────────────────┐
        │ CORPUS ORCHESTRATOR  (ingest/corpus.py)  │  os.walk / rglob, uncapped depth
        │  • enumerate *.pdf *.docx                 │  unsupported ext → manifest row (D-16)
        │  • content-hash each file (blake2b/sha256)│  cache hit? → skip-unchanged (D-14)
        └───────────────┬──────────────────────────┘  one file raises → parse_failed row, continue
                        │  per file (isolated try/except, evals/run.py:182 pattern)
          ┌─────────────┴─────────────┐
          ▼ (.pdf)                     ▼ (.docx)
  ┌──────────────────┐        ┌──────────────────────┐
  │ parse/pdf.py     │        │ ingest/docx_parse.py │  NEW — python-docx
  │ extract_pdf()    │        │ body.iterchildren()  │  geometry = null (D-20)
  │ (UNCHANGED)      │        │ → SAME document dict  │  _tc-identity merge heal
  └────────┬─────────┘        └──────────┬───────────┘
           └───────────┬─────────────────┘
                       ▼  ONE document dict {filename,pages:[{blocks,tables,figures}], toc}
        ┌──────────────────────────────────────────────────────────┐
        │ SUBSTRATE (the spine — all NEW, ingest/)                   │
        │                                                            │
        │  serialize.py ──► raw serialized text (reading order,      │
        │                    cells serialized in, D-31)              │
        │        │                                                   │
        │        ▼                                                   │
        │  normalize.py ─► canonical text  +  canon↔raw OFFSET MAP   │  4 ops, versioned (D-24/25/26)
        │        │                            (run-based, O(log n))  │  ← RISK-1: build+test FIRST
        │        ▼                                                   │
        │  anchors.py ──► span-ID {doc_id,start,end,hash}            │  identity = canonical offsets (D-19)
        │        │        re-open(span)→(raw, canonical) | FAIL      │  (D-21 contract)
        │        ▼                                                   │
        │  tables.py ───► (table_id,row,col) → span-ID index         │  merged→one span (D-31)
        └───────────────┬───────────────────────────┬───────────────┘
                        │                            │
                        ▼                            ▼
        ┌──────────────────────────┐   ┌──────────────────────────────┐
        │ classify.py (D-07)       │   │ store.py (D-14/15)           │
        │ regex→lexicon→LLM        │   │ per-doc cache (canonical text │
        │  ▲ registry (D-05/06)    │   │  RETAINED, D-32) + SQLite     │
        │  ▲ structured.py escalate│   │  corpus index + manifest      │
        │ emits {label,family,conf,│   │  (statuses + availability     │
        │  tier,trigger-span} D-29 │   │  tiers, D-30)                 │
        └──────────────────────────┘   └──────────────┬───────────────┘
                                                       ▼
                                              CorpusIndex  ──►  imported by evals/run.py, Phase 2 tools
```

### Recommended Project Structure

```
src/ingest/                     # NEW package — the directory-intake stack (top of a new tree)
├── __init__.py                 # exports ingest_corpus, CorpusIndex, open_span (re-open primitive)
├── __main__.py                 # `python -m ingest <dir>` thin CLI shell (D-11)
├── corpus.py                   # walk + dispatch + content-hash + per-file isolation (INGEST-01)
├── docx_parse.py               # python-docx → SAME document dict (INGEST-02, D-20)
├── serialize.py                # document dict → raw serialized reading-order text (D-31 cell order)
├── normalize.py                # 4-op normalizer + offset map + version stamp (INGEST-04, D-22..26)
├── anchors.py                  # span-ID mint + re-open/verify primitive (INGEST-04, D-19/21)
├── tables.py                   # (table_id,row,col)→span-ID index, merged-cell dedup (INGEST-05)
├── classify.py                 # deterministic-first + LLM escalation (INGEST-01, D-07/27/28/29)
├── store.py                    # cache + SQLite index + coverage manifest (INGEST-03, D-14/15/16/30)
├── manifest.py                 # CoverageManifest / status + availability schema (pydantic)
└── registry/
    ├── ctd_families.yaml        # id,label,applicability trigger (D-05) — RULES-05 shape
    └── body_lexicon.yaml        # per-family keyword lexicon (D-06)

src/schemas/documents.py         # EXTEND: add canonical-text/offset/span fields; CTDSection → registry-backed
tests/ingest/                    # NEW — mirrors src/ingest (see Validation Architecture)
```

### Pattern 1: The 3-Layer Text Model (the mental model for D-19..D-26)

**What:** Three distinct text representations, each with a defined role. Confusing them is the single biggest correctness trap in this phase.

| Layer | What it is | Located by | Role | Stored? |
|-------|-----------|-----------|------|---------|
| **Physical source** | The actual PDF/DOCX bytes on disk | `bbox`+`page` (PDF only; DOCX has none) | Human opens it to *see* the quote | file on disk |
| **Raw serialized text** | Reading-order concatenation of extracted block/cell text, **before** normalization; preserves case, ligatures, hyphenation | char offset (the "raw" side of the map) | The **verbatim citation** (D-22) — findable by a human because spelling/case/ligature preserved | **yes, on disk (D-32)** |
| **Canonical text** | Raw serialized text after NFC + whitespace-collapse + guarded-dehyphenation + ligature-fold | char offset = **span-ID identity** (D-19) | Internal matching / dedup / addressing | **yes, on disk (D-32)** |

**Key insight the planner must encode:** "raw" in "canonical→raw offset map" means the **raw *serialized* text**, NOT PDF byte offsets. The parser already transforms the physical source (span joining in `pdf.py:_join_spans`, OCR reconstruction, table extraction). Geometry (`bbox`/`page`) is the separate bridge from a raw-serialized span back to the *physical* page for human eyes. This three-way split is exactly why D-20 can null DOCX geometry without breaking grounding — offsets over the canonical stream are well-defined with zero geometry.

### Pattern 2: Reading-Order Serialization (DOCX)

**What:** DOCX has no geometry, so reading order = document (XML body) order. python-docx's high-level `.paragraphs`/`.tables` lists **lose interleaving**.
**When:** Building the raw serialized text and the deterministic table serialization order (D-31).
**Example:**
```python
# Source: verified this session (python-docx 1.2.0). MUST walk the body, not .paragraphs/.tables.
from docx.oxml.ns import qn
def iter_block_items(document):
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.split('}')[-1]
        if tag == 'p':
            yield ('paragraph', child)       # → LayoutBlock (bbox=None, page=None per D-20)
        elif tag == 'tbl':
            yield ('table', child)           # → ExtractedTable, cells serialized in row-major order
# .paragraphs=[Intro,Between,Closing] + .tables=[T1,T2] cannot reconstruct [Intro,T1,Between,T2,Closing];
# body.iterchildren() yields exactly that order — deterministic, version-stampable.
```

### Pattern 3: Merged-Cell Dedup by `_tc` Identity (DOCX)

**What:** python-docx's grid model returns the **same underlying `<w:tc>` element** for every `(row,col)` a merge spans — for BOTH horizontal (`gridSpan`) and vertical (`vMerge`) merges. `id(cell._tc)` is therefore the merged-cell identity, and the **origin** is the first `(row,col)` where that `_tc` appears in row-major order.
**When:** Building the `(table_id,row,col) → span-ID` index (D-31): every spanned coordinate must resolve to the origin cell's single span-ID.
**Example:**
```python
# Source: verified this session. A 3x3 with (0,0)-(0,1) horizontal + (1,2)-(2,2) vertical merge:
#   row0 → 3 cells but only 2 DISTINCT _tc ids; the merged pair shares one _tc.
#   vertical continuation cells return the SAME _tc as their 'restart' origin.
def cell_spans(table):
    origin = {}                                  # tc_id -> (min_row, min_col)
    coord_to_origin = {}
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            k = id(cell._tc)
            if k not in origin:
                origin[k] = (r, c)               # first appearance = origin (row-major)
            coord_to_origin[(r, c)] = origin[k]  # every spanned coord → the one origin
    # index: (table_id, r, c) -> span_id_of(origin cell's serialized range)
    return coord_to_origin
```

### Pattern 4: Run-Based Offset Map (canonical↔raw)

**What:** Represent the alignment as a sorted list of *runs* — contiguous segments where canonical and raw advance together, plus one entry per edit (composition, collapse, deletion, expansion). Look up a canonical offset with `bisect` over run starts → O(log n). Memory = O(number of edits), not O(chars).
**When:** INGEST-04 offset map (D-23); the mechanism that makes the raw citation (D-22) always renderable.
**Example:**
```python
# Each run: (canon_start, canon_len, raw_start, raw_len, kind). Unchanged spans are one big run.
# NFC 'e´'(2 raw)->'é'(1 canon):   run(canon_len=1, raw_len=2)      composition (many→one)
# collapse '   '(3)->' '(1):        run(canon_len=1, raw_len=3)      many→one
# dehyphen '-\n' dropped:           run(canon_len=0, raw_len=2)      deletion (raw longer)
# ligature 'ﬁ'(1 raw)->'fi'(2 canon):run(canon_len=2, raw_len=1)     expansion (canon longer) ← only expanding op
def canon_range_to_raw(runs, cs, ce):
    import bisect
    starts = [r[0] for r in runs]
    i = bisect.bisect_right(starts, cs) - 1
    j = bisect.bisect_right(starts, ce - 1) - 1
    raw_start = runs[i][2] + (cs - runs[i][0] if runs[i][1] else 0)
    raw_end   = runs[j][2] + runs[j][3]        # deletions on the boundary attach to the raw span (correct: a
    return raw_start, raw_end                  #   canon range spanning a dropped hyphen returns the hyphen in raw)
```

### Anti-Patterns to Avoid

- **Normalizing inside the parser.** Keeps you from ever reconstructing the raw quote. Normalization lives only in `ingest/normalize.py`; `pdf.py`/`docx_parse.py` emit raw text.
- **Using string offsets into `page.get_text("text")` as the canonical stream.** That text is per-page, drops nothing consistently, and is not the reading-order serialization tables need. Serialize explicitly (`serialize.py`).
- **Letting a span-ID carry `bbox`/`page`.** Geometry drifts across re-parse; identity must be pure canonical offsets + hash (D-19). Geometry hangs off the span as optional provenance.
- **Duplicating both hyphenation forms in the canonical stream** (D-26d) — breaks offset math (one form per span). Alternate forms are Phase 2 index keys, not canonical text.
- **Trusting `.paragraphs`+`.tables` for DOCX order** — loses interleaving (verified). Walk the body.
- **Inventing synthetic page numbers for DOCX** (D-20) — recreates the fake-geometry trap the whole span scheme exists to avoid.
- **Counting a merged cell N times** — dedup by `_tc` identity before serializing, or the same text appears once per spanned coordinate and offsets inflate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unicode NFC | Custom composition tables | `unicodedata.normalize("NFC", s)` | Stdlib, correct, versioned with Python. Verified behavior below. |
| Offset-tracked NFC leg | Naive per-char reimplementation | `tokenizers.NormalizedString` (installed) as reference/fallback | Rust-backed, battle-tested alignment; already a transitive dep. |
| DOCX merged-cell resolution | XML `gridSpan`/`vMerge` parsing from scratch | python-docx `cell._tc` identity + `cell.grid_span` | The library already heals the grid; `id(_tc)` is the merge key. Verified. |
| DOCX table structure | Geometry inference (as PDF needs) | python-docx `table.rows[r].cells` | DOCX tables are structural; borders are styling. Borderless is trivial here. |
| Malformed LLM classification output | New parser | `structured.py structured_call(...)` (existing L1–L6 stack) | Hardened: strict decode → truncation retry → json_repair → validate → moderator rescue → typed `ParseFailed`. Reuse verbatim (D-07). |
| "One bad file must not crash the batch" | Custom orchestration | The `evals/run.py:171-195` per-item try/except + failures dict pattern | Exactly D-16; the harness that imports you already uses it. |
| Job/index store | New DB abstraction | `sqlite3` following `databricks/delta.py` conventions | D-15 says follow existing job-store; it's SQLite. |
| Content hashing | Custom | `hashlib.blake2b` (fast) or `sha256` of file bytes | Cache key + invalidation (D-14). |
| O(log n) offset lookup | Linear scan / per-char array | `bisect` over run-start array | O(n) map breaks the 500-doc scale target; run-based is O(edits) memory, O(log n) lookup. |

**Key insight:** the moat in this phase is *correctness of the alignment and addressing*, not parsing cleverness. Every parsing sub-problem has a mature library answer; spend the engineering budget on the offset map and merged-cell addressing (the two things that silently corrupt X1 if wrong) and on their property tests.

## Runtime State Inventory

Phase 1 is **largely greenfield** (net-new `src/ingest/` package — verified: no existing `ingest_corpus`/`CorpusIndex`/`span_id`/`canonical_text`/`offset_map` code in `src/` or `tests/`). It is not a rename/migration phase. However, one decided change (D-05, `CTDSection` enum → data-driven registry) touches existing consumers, and one new artifact (the on-disk cache) becomes stored runtime state. Documented so the planner sequences the enum migration and cache invalidation correctly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **New this phase:** content-hash-keyed parse cache + SQLite corpus index will store canonical text (D-32) + normalizer/serializer version stamps. No *pre-existing* stored state to migrate. | Design cache with `normalizer_version` in the key/row so a D-24 version bump invalidates cleanly (the migration path D-24 exists to provide). |
| Live service config | **RapidOCR Databricks endpoint** `defpredict-rapidocr` — its deployed variant (boxed vs flat-text) is runtime state NOT in git (see RISK-2 / item 4). | None in Phase 1 code. Redeploy is an out-of-band ops task; Phase 1 only DETECTS flat-text and marks `parsed_partial`. |
| OS-registered state | None. | None — verified: no schedulers/daemons introduced. |
| Secrets/env vars | `databricks_host`/`databricks_token` (existing `config.py:12-13`) gate OCR; absent → OCR skipped (`ocr.py:78`). No new secrets. | None — reuse existing settings. |
| Build artifacts / installed packages | `CTDSection` **enum consumers**: `checklists.py:14,31-36` (`_VALIDATION_SECTIONS` set), `pipeline.py:17,42` (`detect_ctd_section`, `describe_document`), `catalog.py` (parallel `CANONICAL_DOMAINS` registry already registry-shaped). These import the enum. | D-05 migration: keep `CTDSection` values as registry `id`s so string-valued keys still match; update the three consumers to read the registry. `catalog.py:CANONICAL_DOMAINS` is already the target shape — align, don't duplicate. |

**Migration-safety note (D-05):** `CTDSection` is a `StrEnum` whose *values* are the CTD citations (`"3.2.S.4.1"`). If the registry keys reuse those exact strings, `checklists.py`'s set-membership (`ctd in _VALIDATION_SECTIONS`) and `catalog.py`'s aliases keep working with a thin compatibility shim. Do **not** renumber. This is a code edit, not a data migration (no stored enum values on disk yet).

## Common Pitfalls

### Pitfall 1: Treating "NFC + ligature fold" as one step
**What goes wrong:** You call `unicodedata.normalize("NFC", s)` expecting ﬁ→fi and it stays ﬁ; ligatures survive into the canonical stream and break matching/dedup for "specification"-class words.
**Why it happens:** Ligatures (U+FB01 ﬁ, U+FB02 ﬂ, etc.) are **compatibility** characters — decomposed only by **NFKC/NFKD**, never NFC/NFD. `[VERIFIED: unicodedata NFC('ﬁ')='ﬁ' len 1; NFKC('ﬁ')='fi' len 2]`
**How to avoid:** Implement ligature fold as a **separate explicit op** (an explicit map for the handful of Latin ligatures, applied with offset tracking), NOT by switching to NFKC. NFKC would also destroy `µ→μ` and `²→2`, corrupting units (see Pitfall 2). Order: NFC → whitespace-collapse → guarded-dehyphenation → explicit ligature map.
**Warning signs:** canonical text still contains ﬁ/ﬂ; or, if you "fixed" it with NFKC, `µg/g` became `μg/g` and `cm²` became `cm2`.

### Pitfall 2: Reaching for NFKC/aggressive normalization
**What goes wrong:** Unit and compatibility distinctions that matter in CMC specs get flattened: `µ` (micro sign U+00B5) → `μ` (Greek mu), `²` → `2`, full-width/half-width digits merged.
**Why it happens:** NFKC looks "more normalized." D-25 explicitly rejects it. `[VERIFIED: NFKC('µ')='μ', NFKC('²')='2']`
**How to avoid:** Use NFC only (D-25 is technically correct and unit-safe — this research confirms the decision, not just restates it).
**Warning signs:** oracle number/unit comparisons (`oracles.py parse_limit`) start matching things they shouldn't, or AET µg/g vs µg/patch (oracles.py:149) stops distinguishing units.

### Pitfall 3: Naive dehyphenation corrupting spec ranges / chemical names
**What goes wrong:** `95.0-\n105.0%` → `95.0105.0%`; `2-\nethylhexanoic acid` → `2ethylhexanoic acid`. Silent, and it corrupts *both* the canonical text and the meaning of the raw-offset map (D-26).
**Why it happens:** The naive "line ends with `-` → delete + join" rule. CMC text carries real hyphens.
**How to avoid:** The guarded rule (D-26), which this research **prototyped and verified passes all four fixtures** (see Code Examples). Ship it as a dedicated unit with the locked fixtures as the gate.
**Warning signs:** any digit immediately followed by digits where a hyphen was; chemical-name tokens fused.

### Pitfall 4: PDF merged cells silently mis-addressed
**What goes wrong:** `page.find_tables().extract()` fills spanned/merged cells with **empty strings and provides no span metadata** — so on the PDF path you cannot reliably tell "merged" from "genuinely empty," and the `(table_id,row,col)` index can point a spanned coordinate at the wrong cell. This *silently corrupts X1* (D-31, known gap).
**Why it happens:** PyMuPDF's table finder returns a rectangular grid of strings; merge information is lost. `[VERIFIED: find_tables().extract() returns '' for the spanned slot; Table exposes only bbox/row_count/col_count/rows/extract/header]`
**How to avoid:** (1) Full merged-cell fidelity is achievable on the **DOCX path** (`_tc` identity — verified). (2) On the **PDF path**, mark a table's merged-cell resolution **best-effort/unverified** in the manifest (D-30 table tier) when the grid is non-rectangular or has interior empties adjacent to filled cells; do not claim merged-cell addressability you can't back. (3) The SC2 merged-cell fidelity test should run on a **DOCX** fixture (where it's provable) plus a digital-PDF fixture where the merge is detectable; scanned/complex PDF merges are reported, not guaranteed.
**Warning signs:** a table with visually merged headers whose `(0,0)` and `(0,1)` resolve to different span-IDs when they should be one.

### Pitfall 5: DOCX complex-merge `IndexError`
**What goes wrong:** Reading a table with non-uniform/complex merges raises `IndexError` / "list index out of range" inside python-docx (documented issues #1434, #992, #232).
**Why it happens:** Malformed or non-rectangular merged layouts break the grid healer.
**How to avoid:** Wrap DOCX table reconstruction in try/except → emit typed `ParseFailed` for that table and mark the doc `parsed_partial` with reason "table N: complex merge unreadable" (D-16/D-17/INGEST-02's "typed ParseFailed rather than a corrupt table"). Never let it crash the batch. `[CITED: github.com/python-openxml/python-docx issues #1434, #992, #232]`
**Warning signs:** stack trace from `row.cells` on real submission DOCX; a corrupt/rectangular-looking table that lost rows.

### Pitfall 6: Cache that can't resume or silently serves stale parses
**What goes wrong:** A crash at doc 480 restarts from zero; or a normalizer change serves cached canonical text that no longer matches current code, and every stored span-ID silently drifts.
**Why it happens:** Cache keyed only on file path/content without the normalizer version.
**How to avoid:** Cache key = `content_hash(file_bytes)` **+ `normalizer_version` + `serializer_version`** (D-14/D-24). Write each doc's cache entry atomically (temp file → rename) so a mid-write crash leaves no half-entry; on resume, skip files whose (hash, versions) tuple is already present. `[ASSUMED: standard atomic-write practice]`
**Warning signs:** re-run reparse count > changed-file count; hash-verify failures after a code change with no data change.

## Code Examples

### NFC / ligature / unit behavior (the finding behind D-25)
```python
# Source: verified this session, Python 3.11.3 unicodedata
import unicodedata as u
u.normalize("NFC",  "ﬁ")   # 'ﬁ'  (len 1) — NFC does NOT fold the ligature
u.normalize("NFKC", "ﬁ")   # 'fi'  (len 2) — only NFKC does (but NFKC is rejected by D-25)
u.normalize("NFC",  "µ")   # 'µ'   — micro sign preserved (NFKC→'μ' Greek mu, unit-corrupting)
u.normalize("NFC",  "²")   # '²'   — superscript preserved (NFKC→'2', corrupts cm²)
u.normalize("NFC",  "é")  # 'é' (len 1 from len 2) — NFC composition is many→one (offset map must handle)
# ⇒ Normalizer = NFC (unit-safe) + SEPARATE explicit ligature map {ﬁ:fi, ﬂ:fl, ﬀ:ff, ﬃ:ffi, ﬄ:ffl}
```

### Guarded dehyphenation (D-26) — verified against all four fixtures
```python
# Source: prototyped + verified this session. Results:
#   '95.0-\n105.0%'          -> '95.0-105.0%'          (KEEP: digit before hyphen)       ✓ D-26a
#   '2-\nethylhexanoic acid' -> '2-ethylhexanoic acid' (KEEP: digit before hyphen)       ✓ D-26a
#   'specifi-\ncation'       -> 'specification'        (DROP: rejoined token plausible)  ✓ D-26b
#   'well-\nknown'           -> 'well-known'           (KEEP hyphen, drop linebreak)      ✓ D-26c
import re
def guarded_dehyphenate(text, is_plausible_word):
    def repl(m):
        left, right = m.group(1), m.group(2)
        if left and left[-1].isdigit():
            return f"{left}-{right}"                       # (a) never after a digit
        if is_plausible_word((left + right).lower()):
            return f"{left}{right}"                        # (b) rejoin only if more plausible
        return f"{left}-{right}"                           # (c) keep hyphen, drop linebreak (uncertain)
    return re.sub(r"(\S*?)-\n(\S+)", repl, text)
# is_plausible_word: a lexicon check. Build from (1) a general English word list (stdlib/wordfreq),
# UNION (2) a domain term list harvested from the eCFR/ICH corpus + the existing catalog.py domains,
# so 'chromatography'/'impurities' count as plausible. Ambiguous → keep hyphen; expose BOTH forms as
# Phase-2 index keys pointing at the same span-ID (D-26d), NOT as two canonical forms.
```

### DOCX → same document dict, geometry nulled (D-20)
```python
# Source: verified this session (python-docx 1.2.0). Converges on parse/pdf.py's dict shape.
import docx
def extract_docx(path) -> dict:
    d = docx.Document(path)
    blocks, tables = [], []
    order = 0
    for kind, el in iter_block_items(d):          # body.iterchildren() — reading order
        if kind == 'paragraph':
            text = el.text or ""
            if text.strip():
                blocks.append({"role": "paragraph", "text": text, "bbox": None, "page": None,
                               "reading_order": order, "style": _style_from_run(el), "lines": []})
                order += 1
        else:  # table
            try:
                tables.append(_docx_table_to_extracted(el, page=None))   # None geometry (D-20)
            except Exception as exc:                                     # Pitfall 5
                tables.append({"_parse_failed": f"table complex-merge unreadable: {exc}"})
    return {"filename": Path(path).name, "page_count": None, "toc": _docx_toc(d),
            "pages": [{"page_number": None, "blocks": blocks, "tables": _clean(tables), "figures": []}]}
# section_splitter.split_document consumes this unchanged: it sorts by (page, reading_order); with
# page=None it must sort by reading_order alone — a one-line guard in the splitter's sort key.
```

### Re-open / verify primitive (INGEST-04, D-21 contract)
```python
# Source: design grounded in D-19/D-21/D-24. Lives in ingest/anchors.py (ingestion-owned).
from dataclasses import dataclass
@dataclass(frozen=True)
class SpanID:
    doc_id: str; start: int; end: int; hash: str          # offsets over CANONICAL stream (D-19)

def open_span(span: SpanID, doc) -> tuple[str, str]:      # doc = loaded cache entry
    canonical = doc.canonical_text[span.start:span.end]
    if short_hash(canonical, doc.normalizer_version) != span.hash:
        raise HashMismatch(span, expected=span.hash)      # FAIL (D-21) — tamper/version drift
    raw_s, raw_e = canon_range_to_raw(doc.offset_map, span.start, span.end)
    raw = doc.raw_serialized_text[raw_s:raw_e]            # the verbatim citation (D-22)
    return raw, canonical                                  # BOTH, never one (D-21)
# Phase 2's emit_finding mints a SpanID from a retrieved range and calls open_span to re-resolve
# byte-exactly (TOOLS-03). Arbitrary ranges are valid span-IDs; the section outline and table index
# just provide NAMED spans on top.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Section identity = heading text (`section_splitter.py` "section identity is heading text only") | Content-addressed span-ID; heading = label only (D-18) | This phase | Headings repeat/drift; span-IDs are byte-exact + unique + tamper-evident. |
| Geometry-first model (`bbox`/`page` on every block, `schemas/documents.py`) | Offset-first identity, geometry = optional provenance (D-19/D-20) | This phase | DOCX (no geometry) grounds identically to PDF. |
| Per-page flat text via `blocks_to_text` (`layout.py:452`) / `_join_source_text` (`evals/run.py:51`) | One canonical reading-order stream per doc + retained raw + offset map | This phase | Tables carry relational addressing; quotes are re-openable. |
| `CTDSection` StrEnum (`schemas/documents.py:8`) | Data-driven registry (D-05), RULES-05-shaped | This phase | New families = data edit, not code change. |
| Single-file `run_pipeline(pdf_path)` (`orchestrator.py:17`) | `ingest_corpus(root) -> CorpusIndex` (D-11), upload/orchestrator untouched (D-13) | This phase | Corpus intake, not one document. |

**Deprecated/outdated:**
- AutoGen 3-layer design (`autogen-*` in `pyproject.toml:22-23`) — removed; do not depend on it (CLAUDE.md, MEMORY.md).
- The stale README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE docs — trust code.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Registry authored as YAML/JSON is acceptable; format is a planner call (D-15 discretion) | Standard Stack / Supporting | Low — cosmetic; both are dependency-light. |
| A2 | Atomic temp-file-then-rename gives crash-safe resumable cache | Pitfall 6 | Low — standard practice; verify on the target FS. |
| A3 | A plausibility lexicon can be built from stdlib wordlist ∪ eCFR/ICH/`catalog.py` domain terms and is "good enough" for D-26b | Code Examples (dehyphenation) | Medium — a thin lexicon over-keeps hyphens (safe: D-26c default) but under-rejoins wrapped words; tune against fixtures. Fails *safe* (keeping a hyphen never corrupts a spec range). |
| A4 | The escalation-classifier prompt + `structured.py` reliably yields `{label, family, confidence}` on the cheap local models | Item 6 / classify.py | Medium — heterogeneous local models misbehave on structured args; `structured.py` L1–L6 is the mitigation, but per-model reliability is a Phase 3 unknown. In Phase 1 the LLM tier is a *fraction* of docs (D-27 measures it), so blast radius is bounded. |
| A5 | PDF digital tables in the eval corpus are rectangular enough that merged-cell RISK is DOCX-provable and PDF-best-effort suffices for SC2 | Pitfall 4 / Validation | Medium — if a flagship X1 PDF has merged headers, PDF addressing must improve or that doc is table-tier best-effort. Reported honestly per D-30. |
| A6 | eCFR/ICH corpus (Phase 2) is a suitable source for the domain-term half of the lexicon | Code Examples | Low — it's additive; the general wordlist stands alone if the corpus isn't ready. |

## Open Questions (RESOLVED)

1. **Where does the span-ID hash sit — over canonical or raw substring?**
   - What we know: D-19 says "content-hash of the exact substring"; offsets are over the canonical stream; D-21 re-open verifies the hash and returns both layers.
   - What's unclear: hashing the *canonical* substring detects normalizer drift cleanly (recommended); hashing the *raw* substring gives stronger physical-source-tamper evidence.
   - Recommendation: hash the **canonical** substring + `normalizer_version` (matches "offsets over canonical stream"); optionally also store a raw hash if source-tamper detection is wanted later. Falls under the D-15 "exact schema shape" discretion — planner decides, low risk either way.

2. **First-N-lines title block (D-28): N and where it comes from for a flat DOCX.**
   - What we know: D-28 mandates first-N raw lines as a deterministic signal, independent of heading markup.
   - What's unclear: N (lines vs chars) and whether it's the first N `body.iterchildren()` paragraphs or first N of the serialized stream.
   - Recommendation: first ~15 non-empty serialized lines OR first ~1000 chars of canonical text, whichever shorter; store the triggering span-ID (D-29). Tune against the eval corpus.

3. **Registry file format + compatibility shim shape for the enum migration (D-05).**
   - What we know: `catalog.py:CANONICAL_DOMAINS` is already registry-shaped; `CTDSection` values are the CTD citations reused by `checklists.py`/`pipeline.py`.
   - What's unclear: whether to keep a thin `CTDSection`-compatible accessor or fully replace call sites.
   - Recommendation: keep the citation strings as registry `id`s + a compatibility accessor so the three consumers change minimally; full replacement is not required for Phase 1.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python-docx | DOCX path (INGEST-02) | ✓ | 1.2.0 | — (hard requirement) |
| PyMuPDF (fitz) | PDF path (unchanged) | ✓ | 1.28.0 / MuPDF 1.29.0 | — |
| tokenizers (NormalizedString) | Offset-map reference/fallback | ✓ (transitive) | 0.21.0 | Custom run-based map (recommended primary anyway) |
| json-repair | Escalation salvage (via structured.py) | ✓ | ≥0.30 | — |
| pydantic v2 | Schemas | ✓ | ≥2.7 | — |
| stdlib unicodedata/hashlib/bisect/zipfile/sqlite3 | Normalize, hash, lookup, DOCX-zip guard, index | ✓ | 3.11.3 | — |
| **RapidOCR endpoint** (`defpredict-rapidocr`) | Scanned-PDF table reconstruction | **✗ (unverifiable)** | — | **Detect flat-text → `parsed_partial` (D-17); do NOT block.** See RISK-2. |
| Databricks creds (`databricks_host`/`token`) | OCR + LLM escalation calls | ✗ in local/CI (by design) | — | OCR skipped (`ocr.py:78`); classification degrades to deterministic-only tier for that run. |
| Sample PDFs (`SAMPLE_DATA_DIR`) | PDF fidelity tests | ✗ by default (gitignored `data/`) | — | Tests `skip_if_no_samples` (existing pattern, `test_parse.py:16`); DOCX fixture (`mini_spec.docx`) is committed and endpoint-free. |

**Missing dependencies with no fallback:** none block Phase 1 code.
**Missing dependencies with fallback:**
- RapidOCR box endpoint / Databricks creds — Phase 1 **detects and reports** their absence (parsed_partial + availability tier), which is the correct behavior, not a blocker. The committed `mini_spec.docx` + digital PDFs make the fidelity suite run without any endpoint.

## Validation Architecture

Test framework and infra detected in-repo; the Nyquist `VALIDATION.md` is generated from this section. `nyquist_validation` is **enabled** (config.json:`workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | **pytest 8.2+** with **pytest-asyncio** (`asyncio_mode=auto`) `[VERIFIED: pyproject.toml:36,54-57]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `pythonpath=["src"]`, `testpaths=["tests"]`) |
| Quick run command | `pytest tests/ingest/ -x -q` |
| Full suite command | `pytest` (all) **plus** the eval gate `python -m evals.run gate` and live `python -m evals.run run --gate` |
| Fixture conventions | inline `_block()/_grid()` builders (`test_section_splitter.py:29-38`); `offline`/`_no_network_ocr` monkeypatch to force no-creds path (`test_section_splitter.py:20-26`, `evals/run.py:76`); `skip_if_no_samples` for corpus-dependent PDF tests (`test_parse.py:16`). **No conftest.py exists yet** — add `tests/ingest/conftest.py` for shared fixtures. |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| INGEST-01 | **Rename-folders regression (SC1):** ingest tmp corpus in layout A and renamed layout B → per-content-hash classification + ingested set **identical** (proves D-09 path-exclusion) | unit | `pytest tests/ingest/test_corpus.py::test_rename_folders_invariant -x` | ❌ Wave 0 |
| INGEST-01 | Uncapped depth + mixed PDF/DOCX walked; unsupported ext → `unsupported` manifest row (not crash) | unit | `pytest tests/ingest/test_corpus.py::test_walk_uncapped_and_unsupported -x` | ❌ Wave 0 |
| INGEST-02 | `mini_spec.docx` parses into the unified dict; 5-row/3-col impurities table reconstructs so the 3 planted deficiencies are findable (fills `evals/run.py:174` DOCX seam) | unit + eval | `pytest tests/ingest/test_docx_parse.py -x` then `python -m evals.run run` (minispec no longer a parse_failure) | ❌ Wave 0 |
| INGEST-02 | **Merged-cell fidelity (SC2):** DOCX fixture with horizontal `gridSpan` + vertical `vMerge` → every spanned coord resolves to one origin span-ID | unit | `pytest tests/ingest/test_docx_parse.py::test_merged_cells_resolve_to_origin -x` | ❌ Wave 0 |
| INGEST-02 | **Multi-row / borderless / nested tables (SC2):** borderless DOCX table enumerates (trivial); nested table via `cell.tables`; complex-merge → typed `ParseFailed`, not crash (Pitfall 5) | unit | `pytest tests/ingest/test_docx_parse.py::test_table_edge_cases -x` | ❌ Wave 0 |
| INGEST-02/SC4 | **No parse-fidelity regression:** existing PDF `parse_fidelity`/`anchor_rate` numbers (`evals/metrics.py:100-122`) do not drop after the canonical-text refactor | eval gate | `python -m evals.run run --gate` (zero-TP-lost) | ✅ (harness exists; add DOCX rows) |
| INGEST-04 | **Offset-map round-trip property test (RISK-1):** for random raw strings incl. ligatures/double-spaces/wrapped-hyphens/composables, `open_span` reproduces the raw substring byte-exactly for every canonical range | property (unit) | `pytest tests/ingest/test_normalize.py::test_offset_roundtrip -x` | ❌ Wave 0 |
| INGEST-04 | **Guarded-dehyphenation fixture (D-26):** the four locked cases (`95.0-\n105.0%`, `2-\nethylhexanoic acid`, wrapped-word, uncertain) map to expected canonical forms | unit | `pytest tests/ingest/test_normalize.py::test_guarded_dehyphenation -x` | ❌ Wave 0 |
| INGEST-04 | **NFC/ligature/unit invariants:** ﬁ→fi via explicit map (not NFKC); `µ`/`²`/case preserved; normalizer version stamped | unit | `pytest tests/ingest/test_normalize.py::test_normalization_invariants -x` | ❌ Wave 0 |
| INGEST-04 | **Span re-open byte-exactness + hash fail (INGEST-04/D-21):** re-open returns byte-identical raw+canonical; a tampered stream / wrong version → `HashMismatch` | unit | `pytest tests/ingest/test_anchors.py::test_reopen_and_hash_mismatch -x` | ❌ Wave 0 |
| INGEST-05 | **Merged-cell identical resolution (D-31):** every `(row,col)` a merge spans returns the SAME span-ID (DOCX provable; digital-PDF where detectable) | unit | `pytest tests/ingest/test_tables.py::test_merged_resolves_identically -x` | ❌ Wave 0 |
| INGEST-05 | **Deterministic serialization order:** same document parsed twice → identical `(table_id,row,col)→span` map and identical offsets (version-stamped) | unit | `pytest tests/ingest/test_tables.py::test_serialization_deterministic -x` | ❌ Wave 0 |
| INGEST-03 | Manifest declares statuses + availability tiers up front; a flat/structureless doc reports `structure: flat` but still grounds; scanned-table-lost doc reports `tables: unavailable` (D-30) | unit | `pytest tests/ingest/test_store.py::test_manifest_availability_tiers -x` | ❌ Wave 0 |
| INGEST-03 | Cache resumability: crash-simulated mid-corpus run resumes without reparsing unchanged docs; normalizer-version bump invalidates (D-14/D-24) | unit | `pytest tests/ingest/test_store.py::test_cache_resume_and_invalidate -x` | ❌ Wave 0 |
| INGEST-01/03 | **Never-crash batch (D-16):** a deliberately corrupt PDF + a `.doc`/`.xlsx` in the tree → those become `parse_failed`/`unsupported` rows, all good docs still ingested | unit | `pytest tests/ingest/test_corpus.py::test_one_bad_file_never_aborts -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ingest/ -x -q` (fast, endpoint-free, no creds — all substrate/DOCX/classification units run offline).
- **Per wave merge:** `pytest` (full unit + integration) + `python -m evals.run gate`.
- **Phase gate:** full suite green **and** `python -m evals.run run --gate` shows `mini_spec.docx` parsing (no longer a `parse_failure`) with **zero true positives lost** and no drop in PDF `parse_fidelity`/`anchor_rate` (SC4).

### Wave 0 Gaps
- [ ] `tests/ingest/conftest.py` — shared fixtures: a merged-cell DOCX builder (extend `make_docx_fixture.py` style), a synthetic document-dict factory, `offline` OCR monkeypatch reused from `test_section_splitter.py`.
- [ ] `tests/ingest/test_normalize.py` — offset round-trip property test + guarded-dehyphenation fixtures + NFC/ligature invariants (RISK-1 gate — write FIRST).
- [ ] `tests/ingest/test_anchors.py` — span mint + re-open byte-exactness + hash-mismatch.
- [ ] `tests/ingest/test_docx_parse.py` — DOCX→dict fidelity, merged/nested/borderless, ParseFailed.
- [ ] `tests/ingest/test_tables.py` — `(table_id,row,col)`→span, merged identical-resolution, determinism.
- [ ] `tests/ingest/test_corpus.py` — rename-folders invariant, uncapped walk, never-crash batch.
- [ ] `tests/ingest/test_store.py` — manifest tiers, cache resume/invalidate.
- [ ] A committed **merged-cell DOCX fixture** (new; `mini_spec.docx` has no merges) — required for SC2.
- [ ] Extend the eval set / `evals/run.py` so DOCX has a live parse path (removes the `format != "pdf"` skip at `evals/run.py:174`).

## Security Domain

`security_enforcement` is not set to false, and ingestion parses **untrusted** drug-submission files from arbitrary sources — this section is required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | **yes** | Treat every PDF/DOCX as hostile: size caps, page/entry caps, timeouts, resource limits before parsing. |
| V12 File & Resources | **yes** | Path-traversal-safe walk; reject symlink escapes; cap total files/bytes; DOCX-as-zip decompression-bomb guard. |
| V6 Cryptography | partial | Content-hash uses `hashlib` (blake2b/sha256) — a *checksum*, not a security boundary; do not hand-roll. |
| V2 Authentication | no | Batch library, no auth surface (CLI/local). |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Local filesystem batch. |

### Known Threat Patterns for {PDF/DOCX batch ingestion}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **DOCX zip / decompression bomb** (a few KB expanding to GBs) | Denial of Service | DOCX is a ZIP; before `docx.Document(path)`, inspect with `zipfile`: cap uncompressed size and entry count, reject absurd compression ratios. Enforce a per-file byte ceiling. `[ASSUMED: standard zip-bomb guard]` |
| **Malformed / adversarial PDF** (parser crash, memory blowup) | DoS / Tampering | Per-file try/except → `parse_failed` row (D-16, never aborts batch); wall-clock/memory cap per document; cap page count. PyMuPDF is C — treat exceptions AND process-level hangs as possible. |
| **Path traversal / symlink escape on the walk** | Elevation / Info Disclosure | Resolve real paths; refuse to follow symlinks out of `root`; never write cache outside a controlled cache dir keyed by content-hash (not by attacker-controlled filename). |
| **Filename/path as attack vector into classification** | Tampering | Already mitigated by D-09 (path excluded from classification signals) — a hostile folder name cannot flip a document's class. |
| **Resource exhaustion at 500-doc scale** | DoS | Bounded concurrency, streaming per-file (don't hold 500 parsed docs in memory), on-disk cache; the batch degrades to `parse_failed` rows rather than OOM. |
| **XXE / external entity in DOCX XML** | Info Disclosure | python-docx uses `lxml`; ensure external-entity resolution is not enabled when handling untrusted XML parts. `[ASSUMED: verify lxml parse settings]` |
| **Zip-slip in DOCX part names** (`../` in an entry path) | Path traversal | Never extract DOCX parts to disk by their internal names; python-docx reads in-memory, but any custom part handling must sanitize names. `[ASSUMED]` |

**Planner action:** include a `threat_model` note and a small `ingest/limits.py` (byte/page/entry/time caps) consumed by both parse paths *before* the heavy parse call. These caps also directly serve the D-16 "never abort" and 500-doc-scale goals.

## Sources

### Primary (HIGH confidence — verified in-session)
- **Local Python 3.11.3 `unicodedata`** — NFC does not fold ﬁ (only NFKC); NFC preserves `µ`/`²`/case; NFC composition is many→one. The empirical basis for confirming D-25 and the ligature-fold finding.
- **Local `python-docx` 1.2.0** (`import docx`) — `_Cell.grid_span` exists; `cell.merge()`; `gridSpan`/`vMerge` in XML; grid model heals both merge types to one `_tc`; `body.iterchildren()` required for reading order; `cell.tables` for nested; no `.pages`; borderless table round-trips.
- **Local `PyMuPDF` 1.28.0 / MuPDF 1.29.0** (`import fitz`) — `find_tables().extract()` returns strings with `''` for spanned slots and **no** span metadata (PDF merged-cell RISK); Table exposes bbox/row_count/col_count/rows/extract/header; runtime suggests `pymupdf_layout`.
- **Local `tokenizers` 0.21.0** (`from tokenizers import NormalizedString`) — available transitively via sentence-transformers.
- **Repo code (file:line anchors throughout)** — `schemas/documents.py`, `parse/pdf.py`, `parse/layout.py`, `parse/section_splitter.py`, `parse/ocr.py` (esp. `:122` flat-text seam, `:78` no-creds skip), `agents/detection/ctd.py`, `checklists.py`, `catalog.py`, `oracles.py`, `pipeline.py`, `llm/structured.py`, `llm/client.py`, `evals/run.py` (`:51`, `:76`, `:174`, `:182`), `evals/metrics.py` (`:100`, `:104`), `evals/make_docx_fixture.py`, `orchestrator.py`, `databricks/delta.py` (`:7`, `:22`), `config.py`, `pyproject.toml`.
- **`pypi.org/pypi/python-docx/json`** (WebFetch) — python-docx 1.2.0 latest, released 2025-06-16.

### Secondary (MEDIUM confidence — official docs / issue tracker)
- **python-docx docs — Table Merge Cells** (`python-docx.readthedocs.io/en/latest/dev/analysis/features/table/cell-merge.html`) — gridSpan/vMerge mechanics; `len()` counts the layout grid ignoring merges.
- **python-docx issues #1434, #992, #232** (github.com/python-openxml/python-docx) — merged-cell `IndexError`/"list out of range"; "detecting merged cells remains a documented limitation" → the ParseFailed mitigation.
- **HuggingFace tokenizers — Normalizers / NormalizedString** (huggingface.co/docs/tokenizers) — the reference design for offset-tracked normalization (`normalize()` preserves alignment; `normalize_str()` does not).
- **Unicode UAX #15 / FAQ-Normalization** (unicode.org) — NFC = canonical decomposition then composition; compatibility (ligatures/superscripts) only under NFK*.

### Tertiary (LOW confidence — flagged for validation)
- Zip-bomb / XXE / zip-slip mitigations for DOCX — standard practice, stated from training knowledge `[ASSUMED]`; the planner should confirm lxml parse settings and add explicit caps.
- Plausibility-lexicon construction (A3) — approach is sound but the exact word source and threshold need tuning against the D-26 fixtures.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every library verified installed by import + version cross-checked.
- DOCX fidelity (item 1) / merged cells (item 5): **HIGH** for DOCX (`_tc` identity empirically verified), **MEDIUM** for PDF (find_tables loses merge metadata — RISK flagged).
- Normalization + ligature/NFC finding (item 2): **HIGH** — empirically verified; dehyphenation prototype passes all four locked fixtures.
- Offset map (item 3): **HIGH** on feasibility/round-trip/complexity (all four ops shown invertible under run-based map, O(log n)/O(edits)); **RISK-1** is sequencing (build+test first), not feasibility.
- RapidOCR (item 4): **HIGH** on the code-level distinction (`isinstance list vs str`, `ocr.py:112-122`); **RISK-2** is the un-verifiable deployment/creds state — mitigation is to detect+report, never block.
- Classification (item 6): **MEDIUM** — deterministic tier is well-grounded (extends `ctd.py`); LLM-escalation reliability on local models is an acknowledged Phase-3 unknown, bounded by D-27's measured rate.
- Persistence (item 7): **HIGH** — SQLite convention exists (`databricks/delta.py`); patterns standard.
- Re-open primitive (item 8): **HIGH** — contract fully specified by D-21; design grounded.

**Research date:** 2026-07-30
**Valid until:** ~2026-08-29 (30 days; stack is stable — python-docx/PyMuPDF/pydantic move slowly. Re-verify RapidOCR endpoint deployment state at plan time.)
