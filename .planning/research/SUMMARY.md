# Project Research Summary

**Project:** DefPredict — Agentic FDA/ICH Regulatory Compliance Reviewer
**Domain:** Agentic, tool-using document review / RAG over large heterogeneous (PDF + DOCX) drug-submission corpora, with FDA + ICH rules as retrievable reference
**Researched:** 2026-07-30
**Confidence:** HIGH (pitfalls corroborated by the project's own measured runs; stack/versions verified live; architecture verified against Anthropic primary sources + the existing codebase)

## Executive Summary

DefPredict is a **grounded adversarial reviewer, not an author** — and that single product identity governs everything. The market is saturated with pharma-AI *authoring* tools; almost nothing acts as a *critic* that finds where a submission fails and proves it with the exact text. The technical milestone is likewise not a rewrite: the existing `planner -> workers -> verify -> challenge` topology is already an orchestrator-worker + evaluator-optimizer shape. The work is (a) lifting the substrate from *one parsed document* to *an ingested corpus*, and (b) swapping each *one-shot pre-rendered "sandwich" call* for a *tool-using drive loop*. The uncommitted `planning.py / summarise.py / sandwich.py / workers.py` redesign on `CLI_for_folders` is the seam to build on — not clobber.

The recommended approach is a **model-agnostic, build-your-own tool loop on the `openai` client** (the serving stack is OpenAI-compatible Llama/Qwen via Ollama+Databricks; the Anthropic/Claude Agent SDK cannot drive those models — it is only an additive "Claude orchestrator" spike). Around that loop: **LanceDB** (persistent hybrid store) for the FDA/ICH **rulebook** and **FAISS** (ephemeral) for the per-submission index; **python-docx** for the new DOCX path converging on the existing document model; a five-tool navigation surface (`search_corpus / open_doc / get_section / follow_reference / read_guideline`) that returns **identifiers, not documents**; isolated sub-agents returning distilled cited findings; and a grounded adversarial verifier. The rulebook is sourced open, in a strict authority hierarchy: **eCFR Title 21 (public domain, clean XML) -> ICH Q/S/E/M guidelines -> FDA guidances via regulations.gov -> openFDA** for structured cross-checks only.

The dominant risk is unambiguous and **all four researchers surfaced it independently: the real problem is RECALL, not precision.** The system has already measured itself — run 3 scored precision 16–24% but **recall 7% (2 of 28 real deficiencies)**, and *every* fix that session was a filter that removed wrong findings; none moved recall. The milestone therefore has one spine: **stand up the eval harness FIRST and gate every phase on recall-by-failure-family.** The becoming-an-agent thesis only pays off if it *adds missing check kinds* (assertion-vs-evidence sweeps, derivation-plausibility, summary/total integrity, regulatory-premise review) rather than hardening the same 7%-recall ceiling with a nicer loop. Four cross-cutting laws follow: **"prompt != enforcement"** (load-bearing rules must be code gates — measured ignored 15–18x here); **cross-document retrieval must precede impurity-threshold checks** (dose/route parameters live in a different doc than the impurity table); **grounding + the adversarial verifier land together** (a verifier can only refute-or-confirm what carries a re-openable anchor); and **cost governance is load-bearing substrate**, not a feature, or the "no cap on corpus size" promise is fiction.

## Key Findings

### Recommended Stack

Build on the existing assets (PyMuPDF/OCR parse, pydantic v2, `structured.py`, FAISS+bge-m3, FastAPI/WebSocket, model picker) — this is a subsequent milestone, not a greenfield. Adopt only what the new agentic capability requires, and stay **model-agnostic** because the serving stack is OpenAI-compatible Llama/Qwen. See `STACK.md`.

**Core technologies:**
- **Build-your-own tool loop on `openai` 2.50** (repo pins 1.40 — upgrade) — the agentic drive-loop; you already own the hard parts (grounding, verification, compaction, budgets); a thin hand-rolled loop keeps full control and stays cross-model.
- **PydanticAI 2.21 (optional typed layer)** — typed tool-args + typed outputs over the *same* OpenAI-compatible endpoints; reuses pydantic v2; one-string swap to Claude if the orchestrator spike happens.
- **LanceDB 0.36 (persistent) + FAISS (ephemeral)** — LanceDB embedded hybrid BM25+dense+rerank for the build-once/query-constantly FDA/ICH rulebook; keep FAISS for the transient per-submission index.
- **python-docx 1.2** — primary DOCX path for MVP, converging on the existing `schemas/documents.py` model (Docling is the upgrade path only if table fidelity proves insufficient).
- **bge-reranker-v2-m3** — precision reranking after hybrid retrieval; shares the `bge-m3` lineage already embedded with, no new base model.
- **DeepEval 4.1 + Ragas 0.4 + promptfoo** — the eval-in-CI gate (P/R by family), RAG retrieval metrics, and red-team/multi-model regression.

**Rulebook source hierarchy (the most important stack decision):** (1) **eCFR Title 21** — highest authority, public domain, clean versioned XML -> the backbone; (2) **ICH Q-series** — the CMC reasoning the Module-3 use case leans on (PDF; store the required ICH copyright acknowledgment with every chunk); (3) **FDA guidances** via regulations.gov API v4 for the topics evals exercise; (4) **openFDA (CC0)** for structured cross-checks only — it has **no rules/guidance dataset**, so treating it as the rulebook is a dead end. Store every rule chunk with `{source, citation, version/date, license, url}`.

**Explicit removals:** delete the dead **AutoGen** deps (the 3-layer design was removed); do **not** adopt the Anthropic SDK as the *only* client (it strands the local endpoints); do **not** rewrite the hardened `structured.py`.

### Expected Features

DefPredict competes in near-empty whitespace: a grounded reviewer over an arbitrary corpus. See `FEATURES.md`. Findings are organized by a **DET / HYB / JUD** detection-difficulty axis and an **S (drug substance) / P (drug product) / X (cross-cutting)** deficiency taxonomy — the key insight being that many "easy" threshold checks (S2–S5, P3) are actually HYB and depend on X-class cross-document retrieval to key the threshold correctly.

**Must have (table stakes):**
- Corpus ingestion — multi-format (PDF+DOCX), nested, uncapped — real submissions are hundreds of files.
- Content-based document classification (never folder names).
- Evidence-cited findings (verbatim quote + re-openable locator) — the core precision guarantee.
- Rule-linked verdict per finding (dual citation: submission passage **and** guideline clause).
- Cross-document consistency checking — the single most common real CMC deficiency (QOS 2.3 vs 3.2 spec mismatch).
- Structured, drillable report + coverage manifest — "no deficiencies found" is worthless without knowing what was reviewed.

**Should have (differentiators):**
- **Grounded adversarial verification (refute-or-confirm)** — the headline differentiator; answers the legal-AI hallucination crisis.
- **Dual-grounded, guideline-linked findings** — auditable in seconds.
- **Agentic reference-following navigation** + **reference-graph cross-document contradiction detection** — what makes it generalize to arbitrary corpora.
- **Deterministic-first oracle layer for stable facts only** — high-precision floor at low cost (kept narrow, never the source of intelligence).
- **Calibrated confidence tied to evidence class** + **precedent retrieval** overlay on judgment findings.

**Defer (v2+):** threshold-arithmetic deficiencies (S2–S5, P3) until cross-doc retrieval is solid; stability-adequacy and method-validation suites; reference-graph semantic contradictions (X3/X5/X6); biologics + Modules 4–5; suggested-resolution hints.

**Anti-features (documented to stop scope creep):** auto-filing to FDA; final "approvable/not" determination; unbounded ungrounded autonomy; answer-key oracles as primary intelligence; hardcoded module/folder layout; auto-drafting the deficiency response; full-corpus context stuffing; uncalibrated numeric risk scores.

### Architecture Approach

A layered agentic system where ingestion builds **static indexes bottom-up**, and at review time the orchestrator reads only the lightweight **manifest**, fans out isolated budget-bounded drive-loops that pull content **just-in-time** through tools, consolidates, then a tool-armed verifier re-grounds each survivor. A cost governor wraps every call. Crucially, `agents/review/` mirrors the existing `agents/detection/` file-for-file so the evolution is legible — each new file has a named ancestor. See `ARCHITECTURE.md`.

**Major components:**
1. **Corpus ingestion & index (L0, new)** — walker + DOCX parse + content classifier + manifest + corpus vector index + reference graph; the foundational substrate swap.
2. **Guidelines corpus (L6, new)** — FDA/ICH rulebook ingested as a *separate* retrievable index (parallel track).
3. **Navigation tools (L1, new)** — the five deterministic tools; the hard boundary that keeps the agent out of the filesystem/index and makes the loop testable and cost-bounded.
4. **Drive loop + orchestrator + isolated sub-agents (L2/L3, evolve)** — from `planning.py`/`workers.py`; keep `_ensure_coverage` and the open-sweep pass verbatim as breadth guards.
5. **Consolidator + grounded adversarial verifier (evolve)** — from `verify.py`/`challenge.py`; keep the arithmetic-refutation recompute and downgrade-never-drop invariant.
6. **Cost governor (L5, new)** — prompt-cache prefix, cheap-model triage, hard budgets, compaction (repurpose `summarise.py`'s fidelity guard).

### Critical Pitfalls

The top five are the cross-cutting laws every phase must obey. See `PITFALLS.md` (grounded in `docs/eval/MEASUREMENT.md`).

1. **Precision theater — recall never moves.** Every past fix was a filter (precision 2.4%->24%, recall pinned at 7%). *Avoid:* make **recall-by-failure-family the primary milestone metric**; add the *missing check kinds* (assertion-vs-evidence sweep, summary/total integrity oracle, regulatory-premise reviewer); gate every filter behind "zero true positives lost."
2. **Eval harness FIRST and continuous.** Shipping without ground-truth P/R makes recall regressions invisible; n=1 (one estradiol PDF) overfits. *Avoid:* scaffold the harness before the loop; expand to multi-doc + a held-out corpus; separate per-stage metrics (retrieval recall@k, parse fidelity, anchor rate, verifier P/R, end-to-end P/R by family).
3. **Prompt != enforcement.** Soft rules were ignored 15–18x here (the model wrote "This is not a finding." and shipped the finding). *Avoid:* anything load-bearing (grounding anchor, arithmetic, budgets, coverage, stop conditions) is a **code gate downstream of the model** — the model proposes, code disposes.
4. **Retrieval misses = silent recall gaps; cross-document retrieval must precede thresholds.** A fault only exists if retrieval surfaces it, and impurity thresholds (S2–S5, P3) need dose/route from *another* document. *Avoid:* hybrid retrieval + over-fetch/re-rank + `follow_reference`; keep a mechanical corpus-wide coverage sweep; measure recall@k.
5. **Grounding + adversarial verifier land together, and the verifier must be code-grounded.** A same-family verifier rubber-stamps (self-enhancement/sycophancy); confirmation from model-authored evidence adds confident noise. *Avoid:* refutation counts only on a verbatim-anchored passage or a code recompute over two verbatim cells; ungrounded challenge lowers confidence, never vetoes (preserve the recall invariant). Prefer cross-family/persona verification.

Also load-bearing: **runaway loops/cost** (hard code ceilings + circuit breaker + cheap triage, or a $2k–8k incident), **parse/table corruption** (both current true-positive families are table arithmetic; DOCX doubles the surface), **compaction dropping the deciding number** (extend the `summarise.py` fidelity guard to agent memory; re-open-don't-recall), **structural overfitting** (content-driven classification; rename-folders regression test), **regulatory over-trust** (FDA issued its first AI-over-reliance warning letter April 2026 — never emit unqualified "compliant"; coverage manifest + human-in-the-loop by design).

## Implications for Roadmap

The architecture research supplies a de-risked **A->F build order** (de-risk the central unknown — does a grounded tool loop work on Llama/Qwen? — early). Overlay the pitfalls' non-negotiable sequencing law: **Phase 0 eval harness comes first and runs continuously as the gate on every phase below.** Suggested phases:

### Phase 0: Eval Harness (FIRST, continuous)
**Rationale:** Pitfalls 1 & 11 — recall regressions are invisible without ground truth; this is the instrument that tells you whether the agentic loop helps at all. Sequenced before the loop, run as a CI-style gate on every later phase.
**Delivers:** Multi-document ground-truth set (expand beyond the one estradiol PDF; PDF *and* DOCX; >=1 held-out corpus); per-stage metrics (retrieval recall@k, parse fidelity, anchor rate, verifier P/R, end-to-end P/R **by failure family**); "true-positives-lost = 0" gate on every filter change.
**Addresses:** Eval harness (Active requirement).
**Avoids:** Pitfall 1 (precision theater), Pitfall 11 (weak evals / Goodhart).

### Phase A: Ingestion Foundation
**Rationale:** The substrate swap (one doc -> many); nothing agentic can start until a directory can be walked, parsed, content-classified, and indexed. DOCX *must* land here — the loop can't be validated on a partial corpus.
**Delivers:** Corpus walker + **DOCX parse path** (converge on `schemas/documents.py`) + content classifier + corpus index/manifest; thin eval slice.
**Uses:** python-docx; reuse `parse/*`, `schemas/documents.py`.
**Implements:** L0 ingestion (new `corpus/`).
**Avoids:** Pitfall 7 (parse/table corruption — run the same parse-fidelity suite on both paths; adversarial table fixtures), Pitfall 10 (structural overfit — content-driven classification; rename-folders regression test).

### Phase B: Retrieval + Tools
**Rationale:** The agent needs hands before it can drive; tools are a hard boundary that makes the loop testable and cost-bounded.
**Delivers:** chunk+embed corpus -> corpus vector index; `search_corpus` / `open_doc` / `get_section`; tool registry returning **span-IDs + verbatim text, not free-authored quotes**.
**Uses:** LanceDB (rulebook) + FAISS (per-submission); bge-reranker-v2-m3; hybrid dense+BM25.
**Implements:** L1 navigation tools.
**Avoids:** Pitfall 6 (retrieval misses — hybrid + over-fetch/re-rank + recall@k), Pitfall 2 (citation drift — tools return `span_id`, quote is *selected* not *authored*).

### Phase C: The Spike — Single Drive Loop (GO / NO-GO)
**Rationale:** The central unknown. If a single tool-using agent can't ground reliably on Llama/Qwen over this corpus, D–F are moot. Keep it *one* agent to isolate the risk before multiplying cost by N. The guidelines/rulebook track (parallel to A/B) must finish here — findings must cite a rule.
**Delivers:** one tool-using agent that navigates the corpus, grounds every finding, stops on done/budget; FDA/ICH rulebook + `read_guideline`; **hard budgets from day one**.
**Uses:** the `openai` tool loop (extend `llm/client.py`); reuse `structured.py`, faults schema, anchoring; eCFR->ICH->FDA rulebook ingestion.
**Implements:** L2 drive loop.
**Avoids:** Pitfall 4 (prompt!=enforcement — budgets/stop/circuit-breaker as code), Pitfall 5 (runaway loop), Pitfall 3 (advisory framing baked in).

### Phase D: Scale Out — Orchestrator + Sub-Agent Fan-Out
**Rationale:** Once one loop grounds reliably, decompose and parallelize; cross-document navigation (`follow_reference`) only matters once fan-out spans documents — and is the prerequisite for correct impurity thresholds.
**Delivers:** orchestrator decomposition + isolated sub-agent fan-out + consolidator (dedup/tier keyed on `doc_id`); reference graph + `follow_reference`; first cross-document consistency (X1 spec mismatch, X2 value contradiction).
**Uses:** evolve `planning.py`->orchestrator (keep `_ensure_coverage`), `verify.py`->consolidator; lightweight mostly-deterministic reference graph (not full GraphRAG).
**Implements:** L3 orchestration + reference graph.
**Avoids:** Pitfall 6/10 (mechanical coverage sweep, no structural hardcoding), Pitfall 8 (distilled returns, no chatty sub-agents).

### Phase E: Precision — Grounded Adversarial Verifier
**Rationale:** Grounding + verifier land together; the verifier re-grounds each survivor with tools instead of a pre-rendered excerpt. Ships *with* D's cross-doc findings, not after.
**Delivers:** tool-armed confirm/refute verifier; evidence-forced verdict.
**Uses:** evolve `challenge.py`->verifier; reuse `_arithmetic_refutation` (both cells verbatim).
**Implements:** L4 verifier.
**Avoids:** Pitfall 9 (verifier gamed — code-grounded refutation only; cross-family/persona; measure verifier P/R and that iterations don't lower F1), Pitfall 2 (re-open-don't-recall).

### Phase F: Economics — Cost Governor Hardening
**Rationale:** Cost controls are the substrate that makes the uncapped-corpus promise real; budgets appear in C as a guardrail, the *full* governor hardens here under a synthetic large-corpus load test.
**Delivers:** prompt-cache stable prefix, escalating compaction (repurpose `summarise.py` fidelity guard), cheap-model triage, budget tuning; full eval gate.
**Uses:** reuse model picker/dual serving; provider-side prefix caching (vLLM/Ollama) or Claude `cache_control` if the orchestrator spike lands.
**Implements:** L5 cost governor.
**Avoids:** Pitfall 5 (runaway cost — load-test in budget), Pitfall 8 (compaction evidence loss).

### Phase Ordering Rationale
- **Eval-first is non-negotiable** — all four researchers converged on it; it is the only defense against the measured 7%-recall trap and Goodhart overfitting to n=1.
- **DOCX in A, rulebook by end of C, `follow_reference` in D** — dependency-forced: partial corpus can't validate the loop; findings can't cite rules without the rulebook; cross-doc navigation is meaningless before fan-out.
- **C is the pivot** — isolate the go/no-go risk on a single agent before paying 15x tokens x N sub-agents.
- **Grounding + verifier (E) are coupled to D** — a verifier needs re-openable anchors; ship them together.
- **Cross-document retrieval precedes threshold arithmetic** — the "easy" impurity checks (S2–S5, P3) are deferred to a post-D capability phase because their thresholds depend on X-class dose/route retrieval.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-research-phase`):
- **Phase A (rulebook sourcing sub-track):** ICH exact license/notice wording (MEDIUM), FDA-guidance completeness via regulations.gov, and eCFR versioning cadence are external de-risking tasks with real uncertainty.
- **Phase C:** per-model tool-call reliability + JSON-arg fidelity on Llama 3.3 70B / Qwen MoE (the go/no-go unknown) needs empirical validation, not just design.
- **Phase D:** reference-graph extraction depth (lightweight deterministic edges vs. escalation) — MEDIUM-confidence design latitude in the research.
- **Phase F:** prompt-caching mechanics differ across Ollama/Databricks (provider-side APC) vs. Claude (`cache_control`) — verify the actual cost lever available before designing to it.

Phases with standard patterns (lighter research):
- **Phase B:** hybrid retrieval + rerank over LanceDB/FAISS is well-documented; reuse existing infra.
- **Phase E:** the grounded-refutation gate already exists in `challenge.py`; evolution, not invention.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions live from PyPI/npm; rules-source licensing from official docs. MEDIUM only on the framework judgment call (hand-roll vs PydanticAI vs Claude spike) and exact ICH license wording. |
| Features | MEDIUM-HIGH | Deficiency taxonomy HIGH (ICH text + FDA OGD literature); feature landscape MEDIUM (the agentic-*reviewer* niche is nascent, triangulated from legal-AI + emerging pharma tools). |
| Architecture | HIGH | Agentic patterns verified against Anthropic primary sources + the existing codebase (reuse/replace verdicts are code-level). MEDIUM on reference-graph and guidelines-corpus specifics. |
| Pitfalls | HIGH | Corroborated by the project's *own measured runs* (`docs/eval/MEASUREMENT.md`), existing code gates, current FDA enforcement, and literature. |

**Overall confidence:** HIGH — unusually well-grounded because the system has already measured itself; the failure modes are observed, not hypothetical.

### Gaps to Address
- **Ground-truth breadth:** the 28-item set is n=1 (one estradiol PDF). Expanding to multi-doc-type + PDF/DOCX + a held-out corpus is real work and blocks trustworthy recall measurement — schedule inside Phase 0, not after.
- **Rulebook sourcing is its own de-risking task:** ICH license notice text (verify canonical wording), FDA-guidance completeness, and eCFR version pinning — run as a parallel track through A–C.
- **Per-model tool-call fidelity is unproven:** whether Llama 3.3 70B / Qwen MoE emit reliable tool-args over long loops is the Phase C go/no-go — keep `structured.py` as the malformed-arg fallback.
- **Reference-graph depth is a design bet:** start lightweight (hyperlinks + regex "see section" + numeric value matches); escalate only if eval demands it.
- **Claude orchestrator spike is optional and additive:** only actionable if Claude access is added; do not let it strand the OpenAI-compatible path.

## Sources

### Primary (HIGH confidence)
- `docs/eval/MEASUREMENT.md` (in-repo) — measured precision 2.4%->24%, recall 7% (2/28); "every fix was a filter"; "prompt != enforcement" measured twice; missed-family taxonomy. The single most authoritative source.
- Existing codebase — `agents/detection/{planning,workers,summarise,sandwich,verify,challenge}.py`, `llm/{client,structured}.py`, `schemas/{faults,documents}.py` — the uncommitted redesign on `CLI_for_folders` and the reuse-vs-replace verdicts.
- Anthropic engineering — *Effective context engineering*, *Building a multi-agent research system*, *Building effective agents* — drive loop, orchestrator-worker, distilled returns, just-in-time retrieval, prompt caching, failure modes.
- eCFR Developer Resources / GovInfo bulk-data — Title 21 XML + REST, public-domain confirmation. open.fda.gov/license (CC0). regulations.gov API v4. Databricks/Ollama function-calling docs.
- PyPI/npm live versions (2026-07-30) + Context7 (PydanticAI, Docling, Ragas, DeepEval).

### Secondary (MEDIUM confidence)
- FDA CMC deficiency literature — FDA Perspectives "Common Deficiencies in ANDAs" (Parts 1–3); IJPS systematic review (chemistry ~34% of ANDA deficiencies; QOS 2.3 vs 3.2 mismatch).
- FDA first AI-over-reliance warning letter, April 2026 (Purolea) — DLA Piper, RAPS, EBG, ECA/GMP.
- Graph-RAG / retrieval survey, "Don't Break the Cache," long-document financial-QA retrieval failures, lost-in-the-middle / context rot, shortcut learning / OOD, self-verification limitations, Goodhart / LLM-as-judge.
- ICH guideline PDFs (Q1/Q2/Q3A–D/Q6A) — HIGH on substance, MEDIUM on exact license notice wording.
- Parser comparisons (Docling arXiv, LlamaIndex) and eval-framework comparisons (DeepEval/Ragas/promptfoo).

### Tertiary (LOW confidence)
- Agentic-*reviewer* competitor landscape (Peer AI, Weave Bio, Narrativa, Celegence; Harvey/GC AI legal-AI) — nascent niche, triangulated; informs positioning, not implementation.

---
*Research completed: 2026-07-30*
*Ready for roadmap: yes*
