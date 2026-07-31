# Roadmap: DefPredict — Agentic FDA/ICH Compliance Reviewer

## Overview

This milestone evolves DefPredict from a one-shot single-document detector (measured at **~7% recall — 2 of 28 real deficiencies**) into a grounded agentic reviewer that navigates an arbitrary PDF+DOCX corpus, cites every finding to both source and rule, and adversarially verifies it. The spine is measurement: **Phase 0 stands up an eval harness that reports recall-by-failure-family and runs continuously as the gate on every later phase.** From there the build is dependency-ordered to de-risk the central unknown early — ingestion (Phase 1) and the retrievable substrate + tools + rulebook (Phase 2) exist only to feed the go/no-go **drive-loop spike (Phase 3)**; once a single agent grounds reliably, Phase 4 fans out isolated sub-agents for the first cross-document findings, Phase 5 adds the grounded adversarial verifier, and Phase 6 hardens the cost governor that makes the uncapped-corpus promise real. Three laws govern every phase: anything load-bearing (grounding, budgets, coverage, stop conditions) is a **code gate, never a prompt instruction** (measured ignored 15–18× here); **no phase "improves" unless recall-by-family moves without losing a true positive**; and — added 2026-07-30 after reading the Claude Code source — **the code gate belongs at the tool boundary, rejecting the call, not in a downstream audit.** Claude Code makes ungrounded edits *impossible* (`FileEditTool.validateInput` refuses with typed errorCodes 6/7 when a file was not read, was only partially viewed, changed since read, or when `old_string` is not an exact unique match) rather than detecting them afterwards. Our `emit_finding` tool applies the same shape to findings.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2, …): Planned milestone work. Phase 0 is the eval harness — sequenced first and run continuously as the gate on every phase below it.
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED), appearing between their surrounding integers in numeric order.

7 phases (0–6), granularity `standard`.

- [x] **Phase 0: Eval Harness** - Multi-doc ground-truth + per-stage metrics (recall-by-family); the continuous gate on every later phase (completed 2026-07-30)
- [ ] **Phase 1: Ingestion Foundation** - Walk arbitrary nested PDF+DOCX, content-classify, converge on one document model, build the corpus index
- [ ] **Phase 2: Retrieval, Navigation Tools & Rulebook** - Hybrid corpus retrieval + five span-ID tools + the FDA/ICH rulebook the agent reads
- [ ] **Phase 3: Drive-Loop Spike (GO/NO-GO)** - One tool-using agent that grounds every finding to source + rule within hard code budgets — validate on Llama 3.3 70B / Qwen
- [ ] **Phase 4: Orchestrator + Sub-Agent Fan-Out** - Decompose + fan out isolated sub-agents + reference graph; first cross-document deficiencies (X1, X2)
- [ ] **Phase 5: Grounded Adversarial Verifier** - Tool-armed confirm/refute that drops a finding only on grounded refutation (recall invariant preserved)
- [ ] **Phase 6: Cost Governor** - Prompt-cache prefix + escalating compaction + cheap-model triage so cost scales with docs that need deep reasoning, not corpus size

## Phase Details

### Phase 0: Eval Harness
**Goal**: The system can measure precision and recall **by failure family** against a multi-document ground-truth set, so every later phase is gated on evidence, not assertion. This is the instrument that tells us whether becoming an agent moves the measured 7%-recall ceiling.
**Depends on**: Nothing (first phase; runs continuously as the gate on Phases 1–6)
**Requirements**: EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):
  1. A ground-truth eval set built from the existing ANDA deficiency data spans multiple documents and includes both PDF and DOCX source documents with hand-verified deficiency labels, plus at least one held-out corpus — no longer the single estradiol PDF (n=1).
  2. Running the harness reports per-stage metrics **separately**: retrieval recall@k, parse fidelity, anchor rate, verifier precision/recall, and end-to-end precision/recall **broken down by failure family** (absence-of-evidence, derivation-plausibility, cross-reference integrity, regulatory-framing).
  3. Any filter or change can be run through a **"zero true-positives-lost"** gate that fails loudly if a known real deficiency disappears from the output.
  4. The harness runs as a repeatable CI-style command and records baseline recall-by-family numbers, establishing the measured starting point every later phase must beat.
**Plans**: 4 plans
- [x] 00-01-PLAN.md — Eval-set schema + the 28-item estradiol ground truth, family-tagged (EVAL-01)
- [x] 00-02-PLAN.md — Ground-truth breadth: planted-deficiency DOCX + held-out spec PDF (EVAL-01)
- [x] 00-03-PLAN.md — Deterministic scorer: per-stage + by-failure-family metrics from a captured run (EVAL-02)
- [x] 00-04-PLAN.md — Zero-true-positives-lost gate + CI-style command + committed baseline (EVAL-03)
**Research flag**: Ground-truth breadth (multi-doc-type + PDF/DOCX + held-out corpus) is real de-risking work — schedule the expansion inside this phase.

### Phase 1: Ingestion Foundation
**Goal**: The system ingests an arbitrary, deeply-nested directory of mixed PDF+DOCX documents — content-classified and uncapped — into one unified structured document model with a navigable corpus index. This is the substrate swap: one document → an ingested corpus.
**Depends on**: Phase 0 (eval harness gates parse fidelity)
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05
**Success Criteria** (what must be TRUE):
  1. Pointing the system at an arbitrarily nested folder of mixed PDF and DOCX files ingests **every** document with no count or depth cap, and each is classified by **content** — renaming or reorganizing folders does not change what gets ingested or how it is classified (rename-folders regression test passes).
  2. A DOCX document parses into the **identical** structured document model used for PDFs, and the same parse-fidelity suite (merged cells, multi-page tables, borderless tables) passes on both paths — emitting a typed `ParseFailed` rather than passing a corrupt table downstream.
  3. After ingestion, the system exposes a per-submission **corpus index and coverage manifest** listing every document, its content-derived classification, title, and section outline.
  4. Parse fidelity on both the PDF and DOCX paths meets the Phase 0 harness threshold — no regression in the parse-fidelity metric versus the existing PDF baseline.
  5. Every reconstructed table cell is **addressable**: it carries an ordinary span-ID (byte-exact, re-openable) and resolves through a `(table_id, row, col)` index; merged cells resolve identically from every coordinate they span; and a document whose tables could not be reconstructed reports **table-tier unavailable** in the coverage manifest rather than appearing complete. Without this, Phase 5 SC1's "code recomputation over two verbatim cells" and Phase 4's X1/X2 cell-level comparisons have no substrate to run on.
  6. Ingestion declares a per-document **availability contract** — canonical text + span-IDs guaranteed for anything that parses; section outline and table addressing best-effort — so downstream phases read capability from the manifest instead of discovering it at runtime. A flat, structureless document still grounds; it is simply reported as having no outline.
**Plans**: 9 plans
- [x] 01-01-PLAN.md — Test infrastructure + committed merged-cell DOCX fixture (Wave 0 foundation)
- [x] 01-02-PLAN.md — Canonical-text/span-ID schema + reading-order serializer + security limits
- [x] 01-03-PLAN.md — Normalizer + reversible offset map (RISK-1 offset round-trip gate)
- [x] 01-04-PLAN.md — DOCX parser converging on the PDF dict + section-splitter guard
- [x] 01-05-PLAN.md — Data-driven CTD-family registry + D-05 enum→registry migration
- [x] 01-06-PLAN.md — Span-anchor re-open/verify primitive + (table_id,row,col) cell addressing
- [x] 01-07-PLAN.md — Coverage manifest (statuses + availability tiers) + resumable content-hash store
- [x] 01-08-PLAN.md — Content classifier: deterministic-first + measured LLM escalation
- [x] 01-09-PLAN.md — Corpus orchestrator + CLI shell + eval-harness DOCX seam

### Phase 2: Retrieval, Navigation Tools & Rulebook
**Goal**: The agent has hands — five deterministic navigation tools that return **identifiers and verbatim spans, never whole documents** — over a hybrid-retrieval corpus index and an FDA/ICH rulebook it can consult like a reviewer reading the rulebook. Landing the rulebook here (before the spike) isolates the go/no-go loop risk from external-sourcing risk.
**Depends on**: Phase 1
**Requirements**: TOOLS-01, TOOLS-02, TOOLS-03, TOOLS-04, RULES-01, RULES-02, RULES-03, RULES-04, RULES-05, COST-04
**Success Criteria** (what must be TRUE):
  1. The agent can call `search_corpus`, `open_doc`, `get_section`, `follow_reference`, and `read_guideline`; each returns lightweight identifiers/snippets (only `get_section` returns bounded full text) — never a whole document (just-in-time retrieval).
  2. Every tool result carries a verbatim **span-ID** so a finding's quote is *selected* from the source, not authored by the model — re-opening the span reproduces the text byte-for-byte (citation-drift prevention).
  3. `read_guideline` retrieves rule text from a rulebook built from **eCFR Title 21** (public-domain XML backbone), **ICH guidelines** (required copyright acknowledgment stored per chunk), and **FDA guidances** for the topics the eval set exercises — every rule chunk carrying `{source, citation, version/date, license, url}`.
  4. Hybrid (dense + exact/BM25) retrieval over the corpus index meets a measured **retrieval recall@k** threshold on the Phase 0 eval set's known answer spans — exact identifiers (batch numbers, table labels) retrieve their home document, not just the semantically-nearest chunk.
  5. An **`emit_finding` tool is the only path by which a finding can exist**, and its input validation *rejects* the call — with a typed, self-correcting error — when the cited quote is not byte-identical to the stored span, is not unique, was never retrieved in this session, or carries no rule citation. A test proves a deliberately fabricated quote **cannot be emitted**, rather than being emitted and caught later.
  6. The rulebook exposes a compact **requirement index** (citation + one-line applicability trigger) that the agent can enumerate cheaply, distinct from full rule text fetched on demand. This is the mechanism for `absence_of_evidence` (measured **0/11** — the #1 recall gap): semantic search over a submission cannot surface a requirement the submission never mentions, so *what must be present* has to be enumerable independent of the corpus.
  7. Oversized tool results are persisted and returned as a bounded preview plus a re-openable handle; an over-large `get_section` **fails with a narrow-your-range error rather than truncating**.
  8. Re-retrieving an unchanged span returns a "still current — refer to your earlier retrieval" stub instead of the full text (read deduplication), with the hit rate reported. Built here, not in Phase 6: it lives inside the retrieval tools, and a reviewer re-opens the same spec table many times per run — every Phase 3–5 eval iteration pays for its absence.
**Plans**: 9 plans
- [x] 02-01-PLAN.md — Tool layer foundation: RetrievalLedger + ToolRejected + textsplit + open_doc/get_section/follow_reference (TOOLS-01/02/04, COST-04, D-FR)
- [x] 02-02-PLAN.md — Rulebook storage primitives: RuleChunk local store (SQLite+FAISS+BM25) + the generic edge table (RULES-04, D-RB3, D-RB6)
- [ ] 02-03-PLAN.md — Rulebook sourcing: eCFR/ICH/FDA vendoring + build orchestration, real live-fetched content committed to rulebook/ (RULES-01/02/03/04, D-RB1, D-RB2, D-PREC)
- [ ] 02-04-PLAN.md — search_corpus: local hybrid (FAISS+BM25+RRF) per-submission retrieval tool (TOOLS-01, D-RB5)
- [ ] 02-05-PLAN.md — emit_finding: the dual byte-exact grounding gate, the only path a finding can exist through (TOOLS-03, D-EF1)
- [ ] 02-06-PLAN.md — Requirement index: loader gate + authored v1 data + edges + ground-truth traceability + senior-reviewer checkpoint (RULES-05, D-RI1, D-RB4)
- [ ] 02-07-PLAN.md — Eval harness extension: real search_corpus-driven recall@k + retrieval-gate CI command + committed SC4 baseline (D-SC4)
- [ ] 02-08-PLAN.md — Databricks rulebook serving: Delta population + client-side-cosine query, completing the two-backend dispatch (D-RB2, D-RB6)
- [ ] 02-09-PLAN.md — read_guideline: the 5th tool, dual enumerate/fetch mode tying store + requirement index together (TOOLS-01/04, RULES-05, COST-04, D-RI2)
**Research flag**: Rulebook sourcing is its own de-risking sub-track — ICH exact license/notice wording, FDA-guidance completeness via regulations.gov, and eCFR version pinning have real external uncertainty. (`follow_reference`'s full reference-graph backing completes in Phase 4.)

### Phase 3: Drive-Loop Spike (GO/NO-GO)
**Goal**: Prove the central unknown — a **single** tool-using agent can navigate the corpus on Llama 3.3 70B / Qwen, ground every finding to a re-openable source quote **and** a cited rule, and stop within hard code budgets. If the loop can't ground reliably here, Phases 4–6 are moot; keep it one agent to isolate the risk before multiplying cost by N.
**Depends on**: Phase 2
**Requirements**: AGENT-01, AGENT-03, GROUND-01, GROUND-03, DETECT-03, DETECT-04
**Success Criteria** (what must be TRUE):
  1. Detection runs as a **model-driven, model-agnostic tool loop** (request evidence → reason → request more → stop on done/budget) that replaces the one-shot pre-rendered call, and it emits reliable tool-call arguments on **both** Llama 3.3 70B and Qwen (the go/no-go validation), with `structured.py` as the malformed-arg fallback.
  2. Every finding the agent emits is pinned to a **verbatim quote it actually retrieved** (re-opening the span reproduces it byte-for-byte) AND **dual-cited** to the specific FDA/ICH rule clause it violates, with a **compliance verdict** per finding tied to that rule.
  3. Hard per-run token/step/wall-clock budgets and a **circuit breaker** are enforced **in code, not prompt** — a runaway load test halts at the ceiling and returns the grounded partial, never crashing or overspending — **plus a diminishing-returns stop**: N consecutive steps yielding negligible new grounded evidence halt the loop *before* the ceiling, so budget buys progress rather than circling.
  4. Deterministic quick-win oracles (LOD/LOQ presence S9, reference standards S10, stability commitment P10) run as a **demoted seed pass** that feeds the loop — not as the primary source of findings.
  5. On the Phase 0 eval set, the grounded loop moves **recall-by-failure-family above the single-shot baseline** — the go signal that becoming-an-agent *adds missing check-kinds*, not just a nicer loop around the same 7% ceiling.
**Plans**: TBD
**Research flag**: Per-model tool-call reliability + JSON-arg fidelity on Llama 3.3 70B / Qwen MoE over long loops is the go/no-go unknown and needs empirical validation, not just design.

### Phase 4: Orchestrator + Sub-Agent Fan-Out
**Goal**: Scale the proven loop — an orchestrator decomposes a review into objectives and fans out **isolated, budget-bounded** sub-agents that each return a distilled cited finding set; a reference graph makes cross-document navigation reachable so the system catches its first cross-document deficiencies. Cross-document retrieval lands here (the prerequisite the deferred v2 threshold checks depend on).
**Depends on**: Phase 3
**Requirements**: AGENT-02, DETECT-01, DETECT-02, DETECT-05
**Success Criteria** (what must be TRUE):
  1. An orchestrator reads **only the corpus manifest** (never full docs), decomposes the review into self-contained task specs, and fans out **isolated** sub-agents that each return a distilled 1–2k-token cited finding set — the orchestrator consolidates and dedups keyed on `doc_id`.
  2. A reference graph completes `follow_reference` (hyperlinks + "see §X" + numeric value cross-refs), and the system catches at least one **cross-document specification mismatch (X1** — QOS 2.3 vs Module 3.2 body**)** and one **cross-document value contradiction (X2)** end-to-end.
  3. A mechanical corpus-wide **coverage sweep** guarantees every document/section is *seen* by ≥1 pass (not only what retrieval ranked highly), and renaming folders does not change findings.
  4. Every run emits a **coverage manifest** stating what was reviewed and what could not be located, so a "no deficiencies found" result is meaningful — never an unqualified "compliant."
  5. On the Phase 0 eval set, cross-document (X-family) recall improves versus Phase 3 with **zero true positives lost** from the single-agent baseline.
**Plans**: TBD
**Research flag**: Reference-graph extraction depth (lightweight deterministic edges vs. escalation) is a MEDIUM-confidence design bet — start lightweight, escalate only if eval demands it.

### Phase 5: Grounded Adversarial Verifier
**Goal**: Add the precision gate that lands *with* the cross-document findings — a tool-armed adversarial verifier re-opens each candidate's source and cited rule and returns an evidence-forced verdict, dropping a finding **only** on grounded refutation. Grounding (established from Phase 3) and the verifier land together: the verifier can only refute-or-confirm what carries a re-openable anchor.
**Depends on**: Phase 4
**Requirements**: GROUND-02
**Success Criteria** (what must be TRUE):
  1. Each surviving candidate goes to an isolated verifier sub-agent that **re-opens** the cited passage (`get_section`) and rule (`read_guideline`) with tools — not a pre-rendered excerpt — and must produce a **grounded refutation** (a verbatim resolving passage, or a code recomputation over two verbatim cells) to drop it.
  2. An **ungrounded challenge lowers confidence but never vetoes** — the recall-biased "downgrade-never-drop" invariant is preserved and enforced in code.
  3. The verifier is **cross-family / different-persona** (temperature 0, no access to the generator's reasoning — only the claim + source) so it cannot rubber-stamp correlated errors.
  4. On the Phase 0 eval set, verifier precision/recall is measured **independently**, and adding verification iterations does **not** lower end-to-end F1 (no self-correction degradation), with zero true positives lost.
**Plans**: TBD

### Phase 6: Cost Governor
**Goal**: Make the uncapped-corpus promise real — a prompt-cache stable prefix, escalating context compaction, and cheap-model triage so one agent reasons over a corpus far larger than its context window and **cost scales with docs that need deep reasoning, not raw corpus size.** Hardens the budget guardrail introduced in Phase 3 under a synthetic large-corpus load test.
**Depends on**: Phase 5 (wraps every agent call from Phases 3–5; hardens the Phase 3 budget guardrail)
**Requirements**: COST-01, COST-02, COST-03
**Success Criteria** (what must be TRUE):
  1. A **stable cached prompt prefix** (system + tool schemas) plus **escalating context compaction** let a single agent reason over a corpus far larger than the context window — and a finding provable in small context is **still found** inside a large-corpus run (no compaction / lost-in-the-middle regression; the number/entity fidelity guard holds).
  1b. Compaction clears **tool results (evidence) only — never reasoning or emitted findings** — keeps the N most recent, and **freezes each replacement decision by span-ID** so re-rendered turns are byte-identical. This is *why* criterion 1 holds: the agent retains what it concluded after the bulk evidence is shed, and re-opens any shed span by handle.
  1c. **Cache-stability invariant enforced by test:** no dynamic content (rule lists, corpus manifest, document counts) appears in the system prompt or tool schemas — a test asserts the rendered prefix is byte-identical across two runs over *different* corpora. Getting this wrong silently forfeits the entire caching lever.
  1d. The read-deduplication built in Phase 2 (COST-04) holds under compaction — a span shed by compaction and re-opened by handle does **not** return the "still current" stub, since the model can no longer see the earlier retrieval.
  2. **Cheap-model triage** shortlists the documents/sections worth deep reasoning so a synthetic **large-corpus load test** shows cost scaling with docs that need deep reasoning — not raw corpus size — while staying within per-run budget ceilings.
  3. Every run records tokens/cost/steps in the job store, and the **full eval gate** (recall-by-family + zero-true-positives-lost) passes at corpus scale.
**Plans**: TBD
**Research flag**: Prompt-caching mechanics differ across Ollama/Databricks (provider-side APC) vs. Claude (`cache_control`) — verify the actual cost lever available before designing to it.

## Progress

**Execution Order:**
Phases execute in numeric order: 0 → 1 → 2 → 3 → 4 → 5 → 6.
Phase 0 (Eval Harness) is also the **continuous gate**: its recall-by-family metrics gate every later phase, so it is revisited on every phase transition — not "completed and forgotten."

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Eval Harness | 4/4 | Complete   | 2026-07-30 |
| 1. Ingestion Foundation | 0 / 9 | Not started | - |
| 2. Retrieval, Navigation Tools & Rulebook | 0 / 9 | Not started | - |
| 3. Drive-Loop Spike (GO/NO-GO) | 0 / TBD | Not started | - |
| 4. Orchestrator + Sub-Agent Fan-Out | 0 / TBD | Not started | - |
| 5. Grounded Adversarial Verifier | 0 / TBD | Not started | - |
| 6. Cost Governor | 0 / TBD | Not started | - |
