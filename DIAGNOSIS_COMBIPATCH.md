# Diagnosis: Why DefPredict missed 7 Combipatch E&L deficiencies

Scope: why the pipeline surfaced 1 generic finding where an analyst found 7, and the
fixes that follow. Every root cause below was traced to a line and independently
re-verified against the code rather than inferred from the symptom.

---

## Why the pipeline missed all 7

Your pipeline missed every deficiency because it is architecturally optimized to critique what is *present* in a document against a small, category-labeled precedent library — and every one of the seven analyst findings requires a capability that architecture does not have. Six of seven (D1, D3, D4, D5, D6, D7) required consulting authoritative regulatory text (ICH Q3D(R2), M7, PQRI, USP <88>, FDA E&L) that lives nowhere in your retrieval layer — `src/retrieval/knowledge_base.py` only indexes 500 anonymized historical deficiency utterances, not regulations. Two (D2, D7) required an agent whose job is enumerating what SHOULD be in a document of this type and diffing against extraction — no such agent exists; every prompt in `src/llm/prompts.py` (EXTRACTION_AGENT, FLAW_DETECTION_AGENT, FLAW_MODERATOR) is oriented toward critiquing present content. Three (D1, D2, D6) required holding two spans from different sections in one context and comparing them — but `src/agents/extraction/group.py` (L121-127) discards `findings=[]` and the SelectorGroupChat in `src/agents/detection/group.py` processes categories independently. Two (D1, D5) required verifying that a number matches its derivation or that a table row's cell text agrees with its row label — no numerical or table-cell auditor exists, and `build_extraction_prompt` (`src/agents/extraction/agent.py:38-51`) truncates tables to 10 rows and flattens them with `" | ".join(row)`, destroying the very structure needed for the check. Finally, `FLAW_MODERATOR` (`src/llm/prompts.py:56-74`) requires corroboration from a second specialist — which structurally kills absence findings and single-precedent findings even when they *are* raised. The failure is over-determined: even if one agent had suspected D2 or D7, the moderator would have dropped it.

## Per-deficiency diagnosis

| ID | Title | Root cause bucket(s) | AI-native fix that addresses it | Confidence |
|---|---|---|---|---|
| D1 | AET typo 22.727 vs 8.72 µg/g (p.7) | Cross-reference (primary); Numerical verification; Guidance (AET formula) | Cross-Reference Auditor (primary); Guidance RAG (assists via ICH M7 SCT/AET formula) | High (~80%) |
| D2 | USP <88> not performed on pouch, no justification | Missing-content (primary); Cross-reference set-difference; Consensus/citation gate | Missing-Content Skeptic (primary); Guidance RAG (supplies USP <88> scope); Cross-Reference Auditor (secondary) | High (~85%) |
| D3 | Elemental E&L threshold: SCT-derived AET, not PDE | Guidance RAG (primary); Precedent transfer; Missing-content (secondary) | Guidance RAG (primary); Precedent Retriever (secondary — surfaces prior Scopolamine letter) | High (~85%) |
| D4 | Wrong route/class under ICH Q3D(R2) — parenteral vs cutaneous | Guidance RAG (primary); Precedent transfer; Mild cross-reference | Guidance RAG (primary — Q3D(R2) cutaneous PDE annex); Cross-Reference Auditor (assists on "transdermal" vs "parenteral PDEs used") | High (~85%) |
| D5 | Table 16 result column: Class 3 row mislabeled "Class 1" | Numerical/typo verification (primary); Span-citation gate | Cross-Reference Auditor (row_label vs cell_text conflict) | Medium-high (~75%) |
| D6 | Conclusion contradicts Annexure-4 (2-Butanone, 2-Pentanone) | Cross-reference (primary); Guidance ("reportable leachable"); Span citation | Cross-Reference Auditor (primary); Guidance RAG (assists on "reportable" definition) | High (~85%) |
| D7 | Leachable monitoring commitment missing | Missing-content (primary); Guidance RAG; Cross-reference (timepoints vs shelf life) | Missing-Content Skeptic (primary); Guidance RAG (supplies PQRI/FDA E&L expectation) | High (~85%) |

## The 4 AI-native fixes (ranked by leverage)

### 1. Guidance RAG over authoritative sources — HIGHEST LEVERAGE (6/7 deficiencies)

Add a second vector store parallel to your existing deficiency KB, indexing chunked ICH quality guidelines, FDA CDER guidances, USP general chapters, and PQRI recommendations. Retrieval happens in three stages inside detection: (A) an LLM router picks a shortlist of relevant guidance IDs given document type, (B) `_build_context_for_flaw_type` in `src/agents/detection/group.py` fetches top-k chunks within that shortlist keyed on section content, (C) each candidate finding triggers a self-RAG retrieval keyed on the finding's own claim text. Extend `FlawFinding` in `src/schemas/flaws.py` with required `guidance_citations` and `document_span` fields, and add a deterministic substring verifier (`src/verification/citations.py`, new) that confirms every quoted span exists verbatim in a retrieved chunk. The LLM decides *whether* a rule applies; the verifier only confirms the quote is real.

**Recovers:** D1 (AET formula grounding), D3 (SCT vs PDE), D4 (Q3D(R2) cutaneous annex), D5 (peripheral), D6 ("reportable leachable" definition), D7 (E&L monitoring expectation).

**Adversarial verify:** all three lenses REFUTED. **Hard-coding**: the design enumerates a static regulatory allow-list (Q3D, M7, USP <88>, etc.) — this must be reframed as an *initial ingestion set that grows via an LLM-driven "guidance-gap" surfacing loop*, and success criteria must be topic-based ("finding cites an authoritative source on elemental route selection"), not ID-based. **Coverage**: LLM-generated queries seeded only by section text may miss chunks that don't lexically match ("SCT" never appears in a document using "PDE") — mitigate with hybrid query expansion (LLM proposes 3 synonymous queries, union the results). **Integration**: schema mutation of `FlawFinding` breaks the fine-tuned suggestor/evaluator — ship citations as an *additive optional* field first, migrate the suggestor prompt in a second wave.

**Effort:** ~14 engineer-days (ingestion + Delta tables + 3-stage retrieval + schema + verifier + eval harness).

**Files:** `src/retrieval/knowledge_base.py`, `src/retrieval/vector_search.py`, `src/agents/detection/group.py`, `src/agents/detection/agent.py`, `src/llm/prompts.py`, `src/schemas/flaws.py`, new `src/verification/citations.py`, new `scripts/ingest_guidance.py`.

### 2. Missing-Content Skeptic — HIGH LEVERAGE (D2, D7 primary; D3/D4 secondary)

A new specialist that runs after extraction and in parallel with the flaw SelectorGroupChat. It generates an Expected Content Manifest at runtime — an LLM enumerates the artifacts a competent reviewer would expect for *this specific document classification*, grounded only in retrieved guidance chunks (each expected item must carry a verbatim quote from a retrieved chunk, verified by substring). Then a hybrid Presence Verifier runs per item: deterministic anchor sweep over raw section text + an LLM presence classifier that reads the raw section and returns present/absent/ambiguous with a quote. An `absent` verdict emitted only when both signals agree becomes an `AbsenceFinding` with `finding_kind="absence"`, and the moderator's corroboration rule is relaxed for this class (dual-signal agreement replaces second-specialist corroboration — this is the fix for the D2/D7 filtering trap the missing-content audit identified in `src/llm/prompts.py:56-74`).

**Recovers:** D2 (USP <88> for pouch enumerated as expected, anchor sweep misses), D7 (leachable monitoring commitment enumerated, sweep misses). Secondary: D3/D4 where the document reads coherent but externally incomplete.

**Adversarial verify:** all three lenses REFUTED. **Hard-coding**: same regulatory allow-list criticism as Fix 1 — solve at the RAG layer once, this fix inherits the fix. **Coverage**: k=12 retrieval may not surface the exact USP <88>/PQRI chunk needed — raise k, run parallel queries with LLM-generated topic reformulations, and fail loudly (log "no expected item generated") rather than silently dropping. **Integration**: absence-corroboration carve-out must not bypass the span-citation gate — enforce that AbsenceFinding requires *two* citations (guidance quote + section anchor list), stronger than presence findings, not weaker.

**Effort:** ~5-7 engineer-days, gated on Fix 1 shipping first (needs the guidance RAG).

**Files:** new `src/agents/skeptic/` module (`manifest.py`, `verifier.py`, `agent.py`), `src/llm/prompts.py` (new EXPECTED_CONTENT_GENERATOR and PRESENCE_VERIFIER, amended FLAW_MODERATOR), `src/agents/detection/group.py`, `src/agents/detection/agent.py`, `src/schemas/flaws.py` (add `finding_kind`, `AbsenceFinding`).

### 3. Cross-Reference Auditor — HIGH LEVERAGE (D1, D5, D6 primary; D2 secondary)

A new specialist positioned after extraction, before/alongside the detection group. Extraction agents are extended to emit a `ClaimLedger` — structured tuples `{claim_id, section_id, span_start, span_end, kind, value, unit, context}` — for every numeric statement, table cell, and declarative claim. `kind` is model-emitted `str`, not enum. The auditor receives the full ledger plus the raw text of every cited section (not truncated), and its prompt says only: *"Group claims that refer to the same underlying quantity, table cell, or declarative assertion. For each group, decide agree/disagree/insufficient-evidence. Emit findings only for disagreements, citing both spans verbatim."* No units table, no formula bank, no regex — the LLM decides what "same" means. Verification is deterministic substring match of both quoted spans against source text. To ship this, `src/agents/extraction/group.py:121-127` must stop discarding findings, and `FLAW_MODERATOR` must whitelist `INTERNAL_CONSISTENCY` from the corroboration rule (span-match replaces second-specialist corroboration).

**Recovers:** D1 (AET stated 22.727 in one place, 8.72 in another — grouped by shared entity "AET"), D5 (Table 16 Class 3 row label vs "Class 1" cell content), D6 (main conclusion vs Annexure-4 observations). Secondary: D2 (components list vs USP <88> results as set-difference).

**Adversarial verify:** hard-coding CONFIRMED (clean), coverage REFUTED, integration REFUTED. **Coverage** is the real risk: the auditor only fires on claims that landed in the ledger, and current 4000-char extraction truncation in `src/agents/extraction/agent.py:47-49` can drop the derivation appendix side of D1's contradiction — remove truncation for sections containing numeric tables, or chunk-and-summarize instead of hard-truncate. **Integration**: the `INTERNAL_CONSISTENCY` corroboration carve-out and the ledger schema must be validated against the fine-tuned suggestor/evaluator contract before merge — pilot on a shadow branch with the 8B running on both old and new schemas.

**Effort:** ~3-4 engineer-days. No new infrastructure, no new dependencies. Cheapest of the four.

**Files:** `src/agents/extraction/schemas.py` (add `Claim`, `claim_ledger` field on `IntermediateReport`), `src/agents/extraction/agent.py` (extend prompt, drop truncation for numeric sections), `src/agents/extraction/group.py` (serialize ledger, stop discarding findings), new `src/agents/detection/consistency_auditor.py`, `src/agents/detection/group.py` (register + selector prompt), `src/llm/prompts.py` (new CONSISTENCY_AUDITOR_SYSTEM, amended FLAW_MODERATOR).

### 4. Precedent Retriever — MEDIUM LEVERAGE (D3 primary)

A retrieval-and-reasoning layer that surfaces prior deficiency letters scoped to sponsor, product family, API, and content topic — currently impossible because your KB stores anonymized patterns with no metadata. Extend `src/retrieval/knowledge_base.py` with a `PrecedentStore` carrying `sponsor`, `sponsor_aliases`, `product_family`, `route_of_admin`, `api`, and `content_topics` (topics LLM-tagged at ingest, not hard-coded). Retrieval is three-stage: metadata pre-filter (sponsor OR family OR API overlap) → topic filter (LLM-tagged intersection) → semantic rerank. A dedicated Precedent Skeptic agent receives hits with a scope-match vector `{sponsor, family, api, topic_overlap}` and decides applicability with explicit dis-analogy reasoning. Cross-sponsor precedents are tagged and require stronger moderator corroboration; same-sponsor precedents can survive on rationale + scope match alone.

**Recovers:** D3 (prior Scopolamine SCT letter). Contributes to D4 if a prior cutaneous Q3D(R2) letter exists.

**Adversarial verify:** all three lenses REFUTED. **Hard-coding**: the example content_topics enumeration was illustrative — the design must state clearly that topics are LLM-tagged at ingest with an open vocabulary, not a hand-authored list. **Coverage**: heavily dependent on whether the Scopolamine letter is FOIA-available (unknown) or in the sponsor's own records (requires DPA amendment) — build in an "empty result" path that degrades gracefully to Fix 1's guidance RAG. **Integration**: same `IntermediateReport` mutation risks as Fix 3; single-agent acceptance rule needs validation against the suggestor/evaluator.

**Effort:** ~10 engineer-days including 1-week-parallel legal DPA amendment; ~6-day FOIA/EPAR-only MVP.

**Files:** `src/retrieval/knowledge_base.py` (new `PrecedentStore`), schema migration, new precedent skeptic agent in `src/agents/detection/`, `src/agents/detection/group.py`, `src/llm/prompts.py` (moderator relaxation for precedent findings + rationale requirement).

## Recommended sequence

**Wave 1 (weeks 1-2): Cross-Reference Auditor.** Cheapest (~3-4 days), no external dependencies, immediate recovery on D1/D5/D6, exposes real regressions in the extraction contract that Waves 2-3 depend on (claim ledger, no-truncation for numeric sections, non-discarded findings). Ship it first as a scoped shadow-branch pilot so you validate the moderator carve-out and ledger schema against the fine-tuned suggestor/evaluator before those contracts change for the bigger fixes.

**Wave 2 (weeks 2-4): Guidance RAG.** Highest coverage (6/7) but the longest build (~14 days) and the one that must ship *before* the Missing-Content Skeptic (Wave 3 depends on it). Start ingestion (Q3D(R2), M7(R2), Q3C(R8), USP <88>/<661>/<1663>/<1664>, PQRI PODP, FDA CCS) in parallel with Wave 1. Land as additive optional citation fields first, then migrate the suggestor/evaluator in a follow-up so you don't break your fine-tune's contract in one shot.

**Wave 3 (week 4-5): Missing-Content Skeptic.** ~5-7 days, unlocks D2 and D7 which are the two "conclusion looks fine, review missed the omission" failures that most embarrass the pipeline in front of regulators. Requires Wave 2's guidance RAG to be live.

**Wave 4 (weeks 5-7): Precedent Retriever.** Lowest coverage (D3 mostly), highest legal friction (sponsor DPA). Start the legal amendment in Wave 1 so it lands in parallel. Ship the FOIA/EPAR-only MVP first; sponsor-corpus ingestion follows once the DPA is signed.

This ordering does the cheapest-highest-value thing first (Cross-Ref), unblocks the broadest-coverage fix next (Guidance RAG), lands the second architectural addition on top of it (Skeptic), and finishes with the fix whose ROI depends on unpredictable data availability.

## What NOT to do (guardrails against hard-coding)

Reject any of these if they surface during implementation:

1. **A YAML/JSON checklist of "required E&L artifacts" for the Skeptic.** The manifest must be LLM-generated per document from retrieved guidance chunks. If a teammate proposes a static `expected_items_for_document_type` map, that's a rulebook.
2. **A regex or unit-normalization table in the Cross-Reference Auditor** (e.g., "µg/g ↔ mg/kg conversion map"). The LLM decides equivalence; the verifier only checks that the two quoted spans exist verbatim.
3. **A `route_to_class_list` map for D4** (e.g., `cutaneous → [Class 1, Class 2A]`). This must come from a retrieved ICH Q3D(R2) chunk that the LLM reasons over.
4. **A hard-coded content_topics enum in the Precedent Store.** Topics must be LLM-tagged at ingest with an open string vocabulary. The example enum in the design was illustrative only.
5. **A formula bank for AET recomputation** (SCT × safety factor / patch weight). If you need to catch D1's arithmetic error, retrieve the M7 SCT formulation from guidance RAG and let the LLM reason — do not import SymPy.
6. **A category-specific corroboration matrix in the moderator.** The two carve-outs (INTERNAL_CONSISTENCY, absence with dual-signal, precedent with rationale) are structural — any further per-category exceptions become a rules engine.
7. **Fixed success criteria that name specific guidance IDs** ("must cite ICH_Q3D_R2 §5.2.1"). Evaluate on topic coverage ("finding cites an authoritative source on cutaneous elemental route selection"), which lets the LLM find the right source without you naming it.
8. **A static list of "expected annexures" for cross-reference.** The auditor discovers annexure references from the extracted claim ledger; do not enumerate them.

If a rule feels like it will make eval numbers go up this week, it will make the system brittle next quarter. Every one of these shortcuts recreates the exact "critique only what's present against a finite catalog" trap that caused the seven misses.

## Bottom line

Your system missed all seven deficiencies because it can only critique what it can see, against a small library of what it has seen before — and none of the seven deficiencies are catchable that way. Six required consulting regulatory text your retrieval layer doesn't index (`src/retrieval/knowledge_base.py` holds 500 anonymized precedent utterances, zero ICH/FDA/USP chapters). Two required an agent that enumerates what should be in the document and diffs against extraction — no such agent exists; every prompt in `src/llm/prompts.py` is oriented toward critiquing present content. Three required comparing two spans from different sections in one context — but extraction discards findings at `src/agents/extraction/group.py:121-127` and detection processes categories independently. Two required verifying a number matches its derivation or a table row's cell agrees with its label — no numerical or table-cell auditor exists, and extraction destroys the table structure via `text[:4000]` truncation and `" | ".join(row)` flattening. Even where a lone specialist might have suspected something, `FLAW_MODERATOR`'s corroboration rule would have dropped it because absence and single-precedent findings cannot structurally corroborate. The failure isn't a bug you can patch; it's four missing capabilities. Build them in the order above and you recover all seven — but only if you resist the temptation to shortcut any of them with a rulebook.