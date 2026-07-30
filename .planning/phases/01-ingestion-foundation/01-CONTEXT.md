# Phase 1: Ingestion Foundation - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Turn the system's intake from **"one PDF path"** into **"an ingested corpus."** Phase 1 delivers:

1. A directory walker that ingests an arbitrary, deeply-nested tree of **PDF + DOCX** files — **no document-count or depth cap** — classifying each document by **content, never by folder name** (INGEST-01).
2. A **DOCX parse path** that converges on the *same* unified structured document model the PDF path emits, alongside the existing PyMuPDF/OCR pipeline (INGEST-02).
3. A per-submission **corpus index + coverage manifest** (INGEST-03).
4. The **span-anchor substrate** — one canonical normalized text stream per document, stable content-addressed span-IDs, and a re-open/verify primitive — that Phase 2's agent-facing navigation tools are built on top of. (Building the substrate here, tools in Phase 2, is an explicit decision — see D-19/D-20.)

**Explicitly NOT in this phase:** the agent-facing tools themselves (`search_corpus`/`get_section`/`emit_finding` — Phase 2), the rulebook (Phase 2), the agentic loop (Phase 3), and any rewire of `run_pipeline`/`upload.py`/the detection stack to consume a directory (deferred; see D-13).

</domain>

<decisions>
## Implementation Decisions

### Classification — taxonomy & output
- **D-01:** The content classifier emits, per document: a **free-form label/title** (inferred document type), an **optional CTD-family guess**, and a **raw continuous confidence score**. The corpus is **never locked to CTD** — a non-CTD document (cover letter, form, ad-hoc doc) is a first-class citizen with its own free-form label.
- **D-02:** **Non-CTD / low-confidence documents are first-class and always reviewed.** Every ingested doc is indexed and eligible for downstream review regardless of its CTD guess. CTD family is a **routing hint** for oracles/checklists, **never a gate** on whether a document is looked at. (Recall-first: a real deficiency must not hide in a doc the classifier shrugged at.)
- **D-03:** **No hard confidence threshold in Phase 1.** The classifier records the raw score and routes on it, but sets **no drop/skip cutoff**. Any cutoff is calibrated later by the eval harness. (Honors the "uncalibrated numeric risk scores" anti-feature.)
- **D-04:** Classify at the **document level** and store a **section outline** in the index (satisfies ROADMAP Phase 1 SC3). Do **not** per-classify every section (rejected: multiplies cost, contradicts `section_splitter.py`'s deliberate "no CTD classification" design).

### Classification — taxonomy is data-driven
- **D-05:** The CTD-family vocabulary moves **out of the `CTDSection` Python enum into a data-driven registry** (each entry: `id`, `label`, one-line **applicability trigger**). Adding Modules 1/2/4/5 or biologics families (v2 DET-V2-04) becomes a **data edit, not a code change**. This registry's shape deliberately **matches Phase 2's RULES-05 requirement index** — same `{citation/id, one-line trigger}` shape — so the two align.
- **D-06:** The **body keyword lexicon** used for classification (see D-08) lives in this **same registry**, keyed per family.

### Classification — mechanism
- **D-07:** **Deterministic-first with LLM escalation.** A cheap deterministic first pass (regex/TOC/heading signals, extending the existing `ctd.py detect_ctd_section` seam to document level) classifies most docs LLM-free; escalate to a **cheap-model LLM classifier only when deterministic confidence is low or the doc is non-CTD**. Keeps 500+-doc ingestion mostly offline/cheap while still handling docs that never print a literal "3.2.S.4.1".
- **D-08:** **Classification signals = heading/TOC text + a data-driven body keyword lexicon.** (Reuses parse output; TOC/headings already extracted by `section_splitter.py`.)
- **D-09:** **Filename / folder path is DELIBERATELY EXCLUDED as a classification signal** — not even a weak tie-breaker. Rationale: it would put **Phase 1 SC1's rename-folders regression test** in conflict (path could flip classification in tie cases), and the tie-break role is **already filled by LLM escalation** (D-07). A low-confidence tie **escalates**, it does not fall back to folder naming.
- **D-10:** **No separate letterhead/first-page signal.** Non-CTD documents surface naturally as low deterministic confidence → LLM escalation → free-form label (D-07). No dedicated cover-page classifier needed.

### Entry point
- **D-11:** **Library-first, CLI shell.** Ship a pure `ingest_corpus(root) -> CorpusIndex` library function, wrapped by a thin `python -m ingest <dir>` CLI (branch is literally `CLI_for_folders`). Evals and later agent phases **import the library**; the CLI is ergonomics only.
- **D-13:** The existing **single-file upload API (`src/api/routes/upload.py`) and `run_pipeline` (`src/agents/orchestrator.py`) stay UNTOUCHED this phase.** Rewiring them to consume a directory is explicitly deferred — it would couple ingestion to the mid-redesign detection pipeline and pull Phase 3 loop concerns into Phase 1.

### Persistence
- **D-14:** **Persist to disk:** per-document parse cache + the corpus index/manifest, **content-hash keyed**. Re-runs **skip unchanged documents**; ingestion is **resumable after a mid-corpus failure**. (Essential: Phase 3–5 eval iterations must not re-parse 500 docs each time; a crash at doc 480 must not restart from zero.) The content-hash is the cache-invalidation key — settled, not a planner question.
- **D-15:** Corpus-index **on-disk storage format** is a **planner call** (deferred to planning, not decided here) — should follow existing job-store (Delta/SQLite) conventions where sensible.

### Failure & partial-parse handling
- **D-16:** **Failures are first-class coverage-manifest rows; ingestion of a 500-doc corpus NEVER aborts on one bad file.** (Mirrors the existing `evals/run.py` "record parse_failure, skip, never crash" pattern.) Manifest status vocabulary: **`parsed` / `parsed_partial` / `parse_failed` / `unsupported`**, each with a reason. Unsupported = legacy `.doc`, `.xlsx`, bare images, etc.
- **D-17:** **`parsed_partial` is a distinct, load-bearing status** (not `parsed`). A document that parses but **degrades** — scanned pages OCR'd to flat text, tables not reconstructed, pages skipped — is recorded as `parsed_partial` **with what specifically degraded**, never silently passed as fully `parsed`. This **mirrors Claude Code's `isPartialView`**: content the model has only partially seen must be marked so **downstream grounding refuses to treat it as complete evidence**. Live seam today: `src/parse/ocr.py:122` — when the `defpredict-rapidocr` endpoint returns flat text (old/redeployed variant), the parser returns `payload, [], [], []`, so **scanned-page tables are silently lost**. That page/section must surface as `parsed_partial`.

### Span anchors — the substrate the whole grounding contract rests on
- **D-18:** **Section identity = a content-addressed span-ID; heading text = a human-readable LABEL only.** Store BOTH. Rationale: headings **repeat within a document and drift across re-parse/format**, which would break the **byte-exact, unique-resolution contract** Phase 2's TOOLS-03 `emit_finding` gate depends on. (This is the correction that forced the anchor scheme to be decided in Phase 1.)
- **D-19:** **Span-ID scheme = `{doc_id, start, end}`** — a char-offset range over **one canonical normalized text stream per document** — **plus a short content-hash** of the exact substring. Re-opening a span returns the substring and **re-verifies the hash**: byte-exact + unique + tamper-evident, with **identical machinery for PDF and DOCX**. Geometry (`bbox`, `page`) becomes **optional provenance hanging off the offsets, not the identity**. (Rejected: pure content-hash — not unique, "0.15%" recurs; structural path — indices renumber across re-parse.)
- **D-20:** **Add a format-neutral canonical text + char-offset layer that BOTH parse paths populate.** PDF *additionally* fills `bbox`/`page` as provenance; **DOCX leaves them null/synthetic with no penalty**. Offsets are the **shared spine** of the unified model — this is the concrete mechanism that delivers Phase 1 SC2's "**identical** structured document model for PDF and DOCX." Geometry degrades gracefully.
- **D-21:** **Phase 1 builds the substrate; Phase 2 builds the tools.** Phase 1 delivers: canonical text + stable span-ID generation + a **re-open/verify primitive** (given a span-ID → return byte-exact text, or fail). Phase 2's agent-facing tools (`search_corpus`/`get_section`/`emit_finding`) are built ON TOP. Anchors are an **ingestion property**, owned by the layer that creates the text; the tools that exploit them are navigation.

### Canonical-text normalization (correctness gate, not a tuning knob)
- **D-22:** **The cited "verbatim quote" is the RAW source substring**, reconstructed via the canonical→raw offset map — NOT the canonical substring. Canonical text exists **only** for internal matching / addressing / dedup. "Verbatim" therefore means **verbatim-in-source**: the citation is always findable by a human reviewer opening the actual PDF/DOCX. **A regulatory citation that can't be located in the source document is not a citation.**
- **D-23:** **A canonical→raw offset map is retained per document** (LOCKED requirement). Every canonical offset maps back to a raw-source offset so the raw quote (D-22) can always be rendered.
- **D-24:** **The normalizer carries a version stamp recorded per document** (LOCKED requirement). The content-hash makes an offset shift **fail loudly** (correct), but **without a version stamp a normalization change is indistinguishable from corpus tampering** and mass-invalidates every stored finding **with no migration path**. The version stamp gives the migration path.
- **D-25:** **Normalization = MODERATE:** Unicode **NFC** + **whitespace-collapse** + **PDF dehyphenation** + **ligature fold** (ﬁ→fi). Each op must be **reversible through the offset map** (D-23). (Rejected: *Minimal* — leaves PDF line-wrap/hyphenation noise for Phase 2 retrieval to fight; *Aggressive* NFKC/case-fold/punct-normalize — discards case/compatibility distinctions that matter in specs/units and makes the raw map lossy — over-normalizing for a grounding-first system.)
- **D-26:** **PDF dehyphenation MUST be GUARDED — this is a correctness gate.** The naive "line ends with `-` → delete and join" rule is **forbidden** because CMC text carries real hyphens:
  - `95.0-\n105.0%` must **not** become `95.0105.0%` (spec range).
  - `2-\nethylhexanoic acid` must **not** become `2ethylhexanoic acid` (chemical name).
  - **Rule:** (a) **Never drop the hyphen when the character before it is a digit.** (b) Otherwise drop the hyphen **only when the rejoined token is more plausible than the hyphenated one** (lexicon check). (c) **Keep the hyphen while dropping the line break in all uncertain cases.** (d) Where genuinely ambiguous, **index BOTH forms for retrieval** rather than picking one.
  - **Corrupted canonical text silently breaks matching AND the meaning of the raw-offset map**, so this is a **correctness gate requiring a dedicated test fixture** with hyphenated spec ranges and chemical names — not a tuning knob.

### Claude's Discretion
- Corpus-index on-disk storage format (D-15) — planner decides, following existing Delta/SQLite conventions where sensible.
- Exact canonical-text schema shape and how deeply `bbox`/`page`/`reading_order` are threaded — planner/researcher settles after mapping consumption across parse + detection (constrained by D-19/D-20: offsets are identity, geometry is optional provenance).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase governance
- `.planning/ROADMAP.md` — Phase 1 goal + Success Criteria 1–4 (the acceptance contract); "code gate at the tool boundary" law.
- `.planning/REQUIREMENTS.md` — INGEST-01/02/03 (this phase); TOOLS-01..04 + RULES-05 (Phase 2 — the contract Phase 1's substrate must feed); anti-features list (Out of Scope table).
- `.planning/PROJECT.md` — Key Decisions table (content-driven / no-doc-cap / grounding-mandatory); "Known debt to avoid inheriting" (stale README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE docs describe a REMOVED AutoGen design — do not trust their file refs).

### Document model & parse pipeline (the seams Phase 1 extends)
- `src/schemas/documents.py` — the unified model to converge on; `CTDSection` enum to migrate to a data-driven registry (D-05); geometry-shaped fields (`bbox`/`page`/`reading_order`) that DOCX can't fill (D-20).
- `src/parse/pdf.py` — existing PyMuPDF extraction (`extract_pdf`) — the PDF path DOCX must produce a compatible model beside.
- `src/parse/section_splitter.py` — format-agnostic dict→section transform; its deliberate "no CTD classification — section identity is heading text only" design is the seam D-18 corrects (identity → span-ID).
- `src/parse/ocr.py` §102–133 — the `defpredict-rapidocr` flat-text degradation at line 122 (`payload, [], [], []`) that D-17 `parsed_partial` must catch.
- `src/parse/layout.py` — block/line grouping (reversible), relevant to the canonical text + offset layer (D-20).

### Classification (the seam D-07 extends)
- `src/agents/detection/ctd.py` — `detect_ctd_section` regex classifier (today: section-text-level, literal-CTD-number-only) → extend to document level, deterministic-first pass.
- `src/agents/detection/checklists.py`, `src/agents/detection/catalog.py`, `src/agents/detection/oracles.py` — the CTDSection consumers whose keying must keep working after the enum→registry migration (D-05).

### Entry point & persistence
- `src/agents/orchestrator.py` — `run_pipeline(pdf_path,...)`, the single-file entry to leave UNTOUCHED (D-13); the shape a future directory entry parallels.
- `src/api/routes/upload.py` — single-file upload route, leave UNTOUCHED (D-13).
- `src/evals/run.py` — the CI-style harness that will IMPORT the ingest library; its "record parse_failure, skip, never crash" pattern is the model for D-16.
- `src/evals/make_docx_fixture.py` — generates `mini_spec.docx` (planted-deficiency DOCX), the labeled DOCX target that currently records as a parse-fidelity MISS until the Phase 1 DOCX path (INGEST-02) lands; docstring names the 3 planted deficiencies.

### LLM plumbing (for the escalation classifier)
- `src/llm/structured.py` — hardened structured-output stack (schema → truncation retry → json_repair → validate → moderator rescue → typed `ParseFailed`) — the malformed-arg fallback the LLM classifier escalation (D-07) must use.
- `src/llm/client.py` — OpenAI-compatible client (Ollama/Databricks) for the cheap-model classifier call.

### External deps
- `pyproject.toml` — `python-docx>=1.1` already pinned (bump to 1.2 noted in CLAUDE.md); Docling is v2-deferred (INF-V2-01), NOT this phase.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`src/parse/section_splitter.py`**: already format-agnostic — consumes a plain document dict (blocks/tables/figures) and emits sections with **no CTD classification**. The DOCX path should produce the same dict shape and reuse this splitter rather than a parallel one.
- **`src/agents/detection/ctd.py` `detect_ctd_section`**: the deterministic-first classifier seam — extend from section-text to document-level, feed the data-driven registry.
- **`src/evals/run.py`**: "parse-fail → record & skip, never crash" is the exact pattern for D-16's manifest; and it's the consumer that will import `ingest_corpus`.
- **`src/llm/structured.py`**: reuse verbatim as the malformed-output fallback for the LLM escalation classifier — do NOT reinvent.

### Established Patterns
- **Geometry-first document model** (`bbox`/`page`/`reading_order` on every block/table): the constraint D-20 works around by adding a format-neutral canonical-text+offset layer both paths share, letting DOCX null the geometry.
- **Typed `ParseFailed` over silent corruption**: extend this ethos to `parsed_partial` (D-17) — degradation is surfaced, never swallowed.
- **Deterministic-first, LLM-as-escalation**: the project-wide ethos (oracles/checklists before LLM specialists) — classification (D-07) follows the same shape.

### Integration Points
- New `ingest_corpus(root) -> CorpusIndex` library is the top of a new directory-intake stack; imported by `src/evals/run.py` and (later) Phase 3+ agent code. It does NOT wire into `run_pipeline`/`upload.py` this phase (D-13).
- Canonical-text + span-ID substrate (D-19/D-21) is the handoff surface to Phase 2's navigation tools.

</code_context>

<specifics>
## Specific Ideas

- **`isPartialView` analogy (D-17):** the user explicitly modeled `parsed_partial` on Claude Code's partial-view marking — partially-seen content must be flagged so grounding refuses to treat it as complete evidence.
- **Guarded-dehyphenation fixtures (D-26):** concrete must-not-corrupt cases the test fixture has to include: `95.0-\n105.0%` (spec range, digit-before-hyphen) and `2-\nethylhexanoic acid` (chemical name, rejoin-implausible). Ambiguous cases → index both forms.
- **Registry ↔ RULES-05 alignment (D-05):** the classification registry is intentionally the same `{id, one-line trigger}` shape as Phase 2's requirement index — build it once, reuse.

</specifics>

<deferred>
## Deferred Ideas

- **Rewire `run_pipeline` / `upload.py` to consume a directory** — deferred past Phase 1 (D-13); belongs with the agentic-loop integration (Phase 3+).
- **Docling unified parser** — v2 (INF-V2-01); only if `python-docx` table fidelity proves insufficient.
- **Section-level CTD tagging** — rejected for Phase 1 (D-04); if a later phase's evals demand per-section family precision, revisit.
- **Confidence-threshold calibration** — deferred to the eval harness (D-03); no cutoff baked into ingestion.
- **Corpus-index storage format** — planner's call within Phase 1 (D-15), noted so it isn't treated as pre-decided.

None of the above are scope creep — they were raised, bounded, and consciously placed.

</deferred>

---

*Phase: 1-ingestion-foundation*
*Context gathered: 2026-07-30*
