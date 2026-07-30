# Phase 1: Ingestion Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-30
**Phase:** 01-ingestion-foundation
**Areas discussed:** Classification taxonomy, Classification mechanism, Entry point + persistence, Cross-format span anchors, Canonical-text normalization, Eager-vs-lazy parse boundary

---

## Classification taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| CTD guess + confidence + free label | Inferred free-form type/title AND optional CTD-family guess + confidence; corpus never locked to CTD | ✓ |
| Free-form label only | Fully general, no fixed vocabulary; needs a mapping layer for existing CTD-keyed oracles/checklists | |
| CTD enum only | Extend CTDSection to doc level; simplest but is the hardcoded-module-layout anti-feature | |

**Unit sub-question — User's choice:** Document + section outline, **with a load-bearing correction**: heading text is the section's human-readable *label*, not its identity. **Identity must be the content-addressed span-ID** (decided in the span-anchors area). Rationale: headings repeat within a doc and drift across re-parse/format, breaking the byte-exact, unique-resolution contract Phase 2's TOOLS-03 emit gate depends on. Store both.

**Vocabulary sub-question — User's choice:** Data-driven registry (id, label, applicability trigger) — adding Modules 1/2/4/5 / biologics becomes a data edit; shape aligns with Phase 2 RULES-05.

**Non-CTD handling — User's choice:** First-class, always reviewed. CTD family is a routing hint, never a gate.

**Confidence threshold — User's choice:** Emit raw score, no hard gate in Phase 1; calibrate downstream via the eval harness.

---

## Classification mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic-first, LLM escalation on low confidence | Cheap regex/TOC/heading first pass; LLM only when confidence low or non-CTD | ✓ |
| Deterministic-only | No LLM in ingestion; inherits today's literal-CTD-number brittleness | |
| LLM classifier per document | Most robust, but a model call on every one of 500+ docs | |

**Signals — User's choice:** Heading/TOC text + data-driven body keyword lexicon. **Filename/path DELIBERATELY EXCLUDED** (user's explicit override of the offered "filename as weak hint" option): it conflicts with SC1's rename-folders regression test (path could flip classification in tie cases), and the tie-break role is already filled by LLM escalation. Letterhead/first-page cues not added — non-CTD docs fall to low confidence → LLM escalation → free-form label.

---

## Entry point + persistence

| Option | Description | Selected |
|--------|-------------|----------|
| Directory CLI, library-first | `python -m ingest <dir>` thin shell over `ingest_corpus(root)`; upload API + run_pipeline untouched | ✓ |
| Library function only | No CLI; branch name promises a folder CLI | |
| Rewire run_pipeline + API now | Most integrated; risks the uncommitted redesign + pulls Phase 3 concerns in | |

**Persistence — User's choice:** Persist parse cache + index to disk (content-hash keyed, resumable, skip-unchanged).

**Failures — User's choice:** First-class manifest entries, never crash — **plus a `parsed_partial` status** (user addition) for docs that parse but degrade (OCR flat text, tables not reconstructed, pages skipped), recording *what* degraded. Mirrors Claude Code `isPartialView`; live seam at `src/parse/ocr.py:122`.

---

## Cross-format span anchors

| Option | Description | Selected |
|--------|-------------|----------|
| doc_id + char-offset range over canonical text, hash-checked | `{doc_id,start,end}` + content-hash; identical for PDF/DOCX; geometry optional | ✓ |
| Pure content-hash of the span text | Not unique ("0.15%" recurs); needs offsets anyway | |
| Structural path (doc→section→block index) | Indices renumber across re-parse — the drift rejected | |

**Model-fit sub-question — User's choice:** Add a format-neutral canonical text + offset layer both paths share; geometry stays PDF-only optional. Delivers SC2's "identical structured model."

**Scope-line sub-question — User's choice:** Phase 1 builds the substrate (canonical text + span-ID generation + re-open/verify primitive); Phase 2 builds the agent tools on top.

---

## Canonical-text normalization

| Option | Description | Selected |
|--------|-------------|----------|
| Raw source substring is the citation; canonical internal-only | Verbatim = verbatim-in-source, findable in the actual PDF | ✓ (citation-text) |
| Canonical substring is the citation | "Verbatim" silently means verbatim-in-canonical — not a real regulatory citation | |
| Minimal normalization (NFC + strip controls) | Simplest map, but leaves line-wrap/hyphenation noise for retrieval | |
| Moderate (NFC + whitespace-collapse + PDF dehyphenation + ligature fold) | Robust matching, each op reversible via the offset map | ✓ (normalize level) |
| Aggressive (NFKC + case-fold + punct-normalize) | Best fuzzy recall but lossy map, discards spec/unit-relevant distinctions | |

**User's constraints (locked as requirements):**
- **Guarded dehyphenation** — the naive "trailing `-` → delete+join" rule is forbidden. Never drop the hyphen when the preceding char is a digit (`95.0-\n105.0%`); otherwise drop only when the rejoined token is more plausible (lexicon check); keep the hyphen + drop the line break in uncertain cases; index BOTH forms where ambiguous. A **correctness gate needing a dedicated test fixture** (hyphenated spec ranges + chemical names), not a tuning knob.
- **Canonical→raw offset map retained** per document (so the raw quote is always renderable).
- **Normalizer version stamp recorded per document** — else a normalization change is indistinguishable from corpus tampering and mass-invalidates stored findings with no migration path.

---

## Eager-vs-lazy parse boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Eager full parse once, persisted | Full parse (canonical text + tables + span-IDs) first run, persisted, skip-unchanged after | ✓ |
| Lazy: enumerate + classify + outline, defer body text | Contradicts substrate-in-Phase-1; span-IDs wouldn't exist until retrieval | |
| You decide | — | |

**Notes:** User accepted eager-parse-once (disk persistence makes it a one-time price) with the guarded-dehyphenation constraint above applied to the canonical text produced.

---

## Claude's Discretion

- Corpus-index on-disk storage format — planner's call, following existing Delta/SQLite conventions.
- Exact canonical-text schema shape / how deeply geometry fields are threaded — planner/researcher, constrained by "offsets are identity, geometry is optional provenance."

## Deferred Ideas

- Rewire `run_pipeline` / `upload.py` to a directory — Phase 3+.
- Docling unified parser — v2 (INF-V2-01).
- Section-level CTD tagging — revisit only if later evals demand per-section precision.
- Confidence-threshold calibration — eval harness, not ingestion.
- Corpus-index storage format — planner within Phase 1.
