# DefPredict — Agentic Regulatory Compliance Reviewer

## What This Is

DefPredict analyzes regulatory drug-submission document sets — arbitrary, deeply-nested folders of **PDF and DOCX** files — and surfaces **compliance deficiencies against FDA and ICH rules**, each finding grounded in a verbatim source quote. It is evolving from a single-document, one-shot detector into an **agentic reviewer**: a model-driven loop that navigates *any* document directory with general tools, gathers evidence, follows cross-references, and reasons like a smart FDA/ICH reviewer — so it generalizes to any submission instead of one pre-selected document.

For a regulatory analyst reviewing a drug submission, it answers: *"Where does this submission fail to comply with FDA/ICH requirements — and prove it with the exact text."*

## Core Value

Given **any** directory of submission documents (any format mix of PDF/DOCX, any folder names, any nesting depth, **any number of documents — no cap**), reliably find the real FDA/ICH compliance deficiencies — **all faults, and only faults that actually exist** — each one cited to the exact passage that proves it. Recall + precision, no hallucinated "blabber."

## Current Milestone: v2.0 — β: Deterministic Recall + Agentic Verify

**Goal:** Replace the v1.0 agentic-recall loop — a confirmed **3rd NO-GO** (`.planning/phases/03-drive-loop-spike-go-no-go/03-19-V3.3-READING.md`: median recall 0.071 < 0.107 baseline; C-01/B-08 lost every run; absence-of-evidence 0.000), which proved a model-driven loop on self-hosted local models cannot reliably do **recall** — with a **general deterministic recall pipeline** verified by isolated local-model sub-agents. DefPredict finds all real FDA/ICH deficiencies in any submission folder, fully on-premise, without chasing the eval metric.

**Target features:**
- **Recall / rulebook enumeration** — enumerate required FDA/ICH items, flag absent ones (the fix for absence = 0.000)
- **Recall / intra-document structural checks** — summary-vs-detail, spec exceedance
- **Recall / cross-document reference-graph integrity** — broken/absent cross-references, absent referenced docs, cross-doc value mismatches (submission-internal; not in the rulebook)
- **Recall / precedent retrieval** — over the past-deficiency corpus
- **Multi-agent verification** — isolated Nemotron verifier sub-agents (write-disabled, `VERDICT: KEEP|DOWNGRADE`), orchestrator consolidates + dedups
- **Interpretive-tail reasoning** — agentic, for deficiencies no rule can express
- **Rulebook enrichment** — thicken thin ICH/FDA coverage
- **Weak-model reliability hardening** — guided decoding, field-level tool errors, semantic coercion for the local verifier

**Foundation carried from v1.0:** Phase 0 (eval harness — continuous gate), Phase 1 (ingestion), Phase 2 (retrieval/tools/rulebook). Phase 3 (drive-loop spike) is superseded; its records are preserved as the audit trail.

**Hard constraints:** on-premise / privacy — self-hosted open-weights ONLY (Llama 3.3 70B + Qwen MoE + NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 on Databricks); **no external LLM APIs** (Claude/GPT excluded). **Guardrail:** recall checks stay rulebook+structure-general — no corpus hardcoding, no metric-chasing.

## Requirements

### Validated

<!-- Inferred from the existing codebase (brownfield). These already work today. -->

- ✓ Parse a single CTD PDF (digital + scanned via OCR) into a structured document model — existing (`src/parse/`, PyMuPDF + Databricks RapidOCR + geometry layout + section splitter)
- ✓ Deterministic-first single-document detection: oracles + checklists → concurrent LLM sub-agents → verify/tier/dedup → adversarial challenge → tiered `FaultReport` — existing (`src/agents/detection/`)
- ✓ Evidence-class + tier model (`code_verified`/`checklist`/`quote_anchored`/`model_judgment`; `verified`/`corroborated`/`advisory`) with recall-biased "downgrade-never-drop" invariant — existing (`src/schemas/faults.py`)
- ✓ Robust structured-output stack: strict JSON schema → truncation retry → `json_repair` → pydantic validate → moderator rescue → typed `ParseFailed` sentinel — existing (`src/llm/structured.py`)
- ✓ Vector-search precedent retrieval over a 500-row historical-deficiency KB (BAAI/bge-m3 → FAISS local / Databricks Vector Search) — existing (`src/retrieval/`, `src/databricks/vector.py`)
- ✓ UI model picker + dual local(Ollama)/Databricks serving; FastAPI + WebSocket + Next.js analyst UI; SQLite/Delta job store — existing (`src/api/`, `src/config.py`, `frontend/`)
- ✓ Partial redesign already reimplemented (uncommitted) on branch `CLI_for_folders`: `planning.py` / `summarise.py` / `sandwich.py` / `workers.py` (planner + summariser + sandwich + two-pass workers) — **build on this, do not clobber**

### Active

<!-- Building toward these. Hypotheses until shipped and validated against evals. -->

- [ ] **Corpus ingestion**: walk an arbitrary, deeply-nested directory of **PDF + DOCX**; classify each document by **content** (not folder name); no limit on document count or nesting depth
- [ ] **DOCX parsing**: add a Word-document parse path alongside the existing PDF/OCR pipeline, converging on the same structured model
- [ ] **Agentic loop**: convert detection from a one-shot function into a model-driven loop where the LLM requests evidence, reasons, requests more, and decides when it is done
- [ ] **General corpus-navigation tools** the reviewer calls on demand: `search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline`
- [ ] **Grounding discipline**: every claimed deficiency pinned to a verbatim quote the agent actually retrieved and can re-open to verify (the precision / "no-blabber" guarantee)
- [ ] **Adversarial verifier** sub-agent: must refute-or-confirm each candidate deficiency against the source before it survives (evidence-forced verdict)
- [ ] **Isolated sub-agents**: fan out over documents / sections / review-themes, each returning distilled, cited findings; orchestrator consolidates + dedups
- [ ] **Retrieval + context compaction**: reason over a corpus far larger than the context window (never load the whole directory)
- [ ] **FDA + ICH rules as retrievable reference**: source and ingest an **open-source corpus of FDA guidances + ICH guidelines**; consulted like a reviewer reading the rulebook — NOT hardcoded as answer-key oracles
- [ ] **Compliance objective**: report where the submission violates or fails to meet a specific FDA/ICH requirement, citing both the submission passage and the rule
- [ ] **Cross-document consistency**: catch contradictions across the corpus (spec limits, methods, batch numbers, values) via the reference graph
- [ ] **Cost controls**: prompt caching, context compaction, cheap-model triage, sub-agent isolation, hard per-run budgets — so cost scales with docs that need deep reasoning, not raw corpus size
- [ ] **Eval harness**: measure precision/recall against ground truth — seeded from the existing ANDA deficiency data / 500-deficiency KB; artifacts under `docs/eval/`

### Out of Scope

- Hardcoded per-submission "answer-key" oracles as the *primary* intelligence — brittle, don't generalize; deterministic checks are kept ONLY for stable structural/consistency facts, not as the source of findings
- Overfitting to folder names or a fixed module layout (hardcoding "M3", "3.2.S.4.1" paths) — structure is inferred from content
- Any fixed ceiling on document count or folder nesting depth
- Auto-filing or submitting anything to the FDA — this is a review/advisory tool; a human stays in the loop
- Final legal/regulatory determination — it surfaces cited compliance issues for expert review; it is not the decision-maker

## Context

**Domain:** FDA/ICH regulatory review of drug submissions (CTD/eCTD-style: Modules 1–5, e.g. Module 3 CMC — drug substance/product specs, method validation, impurities, stability). Real submissions are deeply-nested folder trees of hundreds of documents; the "500 documents" sample lives entirely inside a single module's nested subfolders. Documents reference each other (hyperlinks, "see section X", value cross-references).

**Existing architecture (from a full deep-dive this session):** `orchestrator.run_pipeline` = parse → detect. Parse (`src/parse/`) turns one PDF into plain-dict pages→blocks→tables/sections. Detect (`src/agents/detection/`) runs deterministic oracles + checklists, then concurrent LLM specialists/reviewers (one-shot `structured_call` over a pre-rendered slice), then verify/tier/dedup, then an adversarial challenge pass, emitting a tiered `FaultReport`. Results stream to a Next.js UI over WebSocket (activity only) with results delivered by REST polling.

**The core gap this project closes:** today the detection LLMs are *one-shot* — spoon-fed a fixed pre-selected slice of ONE document, with no tools, no exploration, no ability to open another file / follow a reference / verify against source. That cannot generalize to arbitrary directories no matter how strong the model. The redesign makes the reviewer an **agent** (drive-loop + general tools + grounding + verification), which is why it generalizes — the same lesson Claude Code embodies for codebases.

**Cost lessons (from studying Claude Code's source this session):** the agentic loop is expensive but made viable by prompt caching (one stable cached prefix), escalating context compaction (bounded working set), isolated sub-agents (one-time exploration cost), cheap-model triage, and hard budget ceilings.

**Known debt to avoid inheriting:** the repo's markdown docs (README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE) describe a *removed* 3-layer AutoGen design and are stale; several config knobs and modules are dead (AutoGen deps, `serving.py`, consensus-round settings). Trust code, not those docs.

## Constraints

- **Tech stack:** Python 3.11+, FastAPI, PyMuPDF (PDF) + a DOCX parser to add, pydantic v2, OpenAI-compatible LLMs (local Ollama / Databricks serving: Llama 3.3 70B, Qwen MoE), FAISS / Databricks Vector Search, Next.js frontend.
- **Grounding:** no finding may exist without a verbatim source anchor (doc → section → span) plus the rule it violates.
- **Generality:** no assumptions about document count, folder names, or nesting depth; classification is content-driven.
- **Cost/latency:** the agentic loop must be actively managed (caching / compaction / cheap-triage / budgets).
- **Branch:** all work on `CLI_for_folders`; a partial planner/summariser/sandwich/workers redesign is already uncommitted here — build on it, don't overwrite it.
- **Data:** PDF + DOCX inputs; ground-truth evals seeded from existing ANDA deficiency data; FDA/ICH rules to be sourced from an open corpus.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent, not function | One-shot pre-selected context can't generalize; a model-driven loop with tools does (Claude Code study) | — Pending |
| Guidelines as retrievable reference, not oracles | Answer-keys don't generalize to new submissions; intelligence + reference does | — Pending |
| Grounding mandatory (verbatim quote per fault) | Prevents confident hallucination while staying general ("no blabbering") | — Pending |
| Content-driven, folder-name-agnostic, no doc cap | Folders can be named anything and nested arbitrarily; corpora are unbounded | — Pending |
| Cost via caching + compaction + cheap triage + isolation + budgets | Makes the agentic loop economically viable at corpus scale | — Pending |
| Eval harness gates everything | "Reliable" must be measured (precision/recall), not asserted | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-05 — milestone v2.0 (β) started after the v1.0 agentic-recall spike NO-GO*
