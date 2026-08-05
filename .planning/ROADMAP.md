# Roadmap: DefPredict — Agentic FDA/ICH Compliance Reviewer

## Overview

This milestone evolves DefPredict from a one-shot single-document detector (measured at **~7% recall — 2 of 28 real deficiencies**) into a grounded reviewer that finds all real FDA/ICH deficiencies in an arbitrary PDF+DOCX corpus, cites every finding to both source and rule, and verifies it — fully **on-premise**. The spine is measurement: **Phase 0 stands up an eval harness that reports recall-by-failure-family and runs continuously as the gate on every later phase.** Ingestion (Phase 1) and the retrievable substrate + tools + rulebook (Phase 2) exist to feed the go/no-go **drive-loop spike (Phase 3)**.

**β pivot (2026-08-05).** Phase 3 is a confirmed **3rd NO-GO** (`03-19-V3.3-READING.md`: median recall `0.071` < baseline `0.107`; `{C-01, B-08}` lost every run; `absence_of_evidence = 0.000`). A model-driven loop on self-hosted local models **cannot reliably do recall**. The pre-registered decision adopts **β**: **recall moves to a general deterministic pipeline** (rulebook-requirement enumeration + structural/cross-document consistency), and **the agent is repurposed as a write-disabled verifier** (`VERDICT: KEEP | DOWNGRADE`, never DROP). The old agentic-recall Phases 4–6 are **superseded**; their success criteria are re-expressed as the deterministic β phases below.

**Three laws still govern every phase.** Anything load-bearing (grounding, budgets, coverage, stop conditions) is a **code gate, never a prompt instruction** (measured ignored 15–18× on local models); **no phase "improves" unless recall-by-family moves without losing a true positive**; and the code gate belongs at the **tool boundary**, rejecting the call, not in a downstream audit (Claude Code's `FileEditTool.validateInput` shape, applied to `emit_finding`).

**Two β laws added.** **On-premise ONLY** — self-hosted open-weights (Llama 3.3 70B + Qwen MoE + NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 on Databricks); **no external LLM API (Claude/GPT), ever** — recall cannot be bought with a stronger hosted model. **Anti-overfitting** — every deterministic recall check stays rulebook/structure/graph-**general**; a guard test proves no submission-specific constant is embedded. The eval corpus is a **proxy**, never a target: if a check is ever tuned to recover a specific item on *this* corpus, that is overfitting and we stop.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2, …): Planned milestone work. Phase 0 is the eval harness — sequenced first and run continuously as the gate on every phase below it.
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED), appearing between their surrounding integers in numeric order.
- Phases 0–3 are v1.0 heritage (preserved verbatim). Phase 3 is **COMPLETE — NO-GO**, superseded by the β pivot; its records are retained as the audit trail. Phases **4 onward** are the new β (Deterministic Recall + Agentic Verify) phases.

9 phases (0–8), granularity `standard`.

- [x] **Phase 0: Eval Harness** - Multi-doc ground-truth + per-stage metrics (recall-by-family); the continuous gate on every later phase (completed 2026-07-30)
- [x] **Phase 1: Ingestion Foundation** - Walk arbitrary nested PDF+DOCX, content-classify, converge on one document model, build the corpus index (v1.0 — verified complete 2026-08-05, 71 tests green)
- [x] **Phase 2: Retrieval, Navigation Tools & Rulebook** - Hybrid corpus retrieval + five span-ID tools + the FDA/ICH rulebook the agent reads (completed 2026-07-31)
- [x] **Phase 3: Drive-Loop Spike (GO/NO-GO)** - One tool-using agent grounding findings within code budgets — **NO-GO** (3rd consecutive; recall 0.071 < 0.107); superseded by β, records retained as audit trail (closed 2026-08-05)
- [ ] **Phase 4: Rulebook Enrichment + Absence Enumeration (β)** - Thicken thin ICH/FDA coverage to per-requirement granularity, then enumerate applicable required items and flag the absent ones — the fix for absence-of-evidence = 0.000
- [ ] **Phase 5: Deterministic Structural & Cross-Document Recall (β)** - Intra-doc structural checks + cross-document reference graph + precedent retrieval, all rulebook/structure/graph-general behind an anti-overfitting guard test
- [ ] **Phase 6: On-Prem Verifier Model + Weak-Model Reliability (β)** - Serve Nemotron-49B self-hosted, prove its tool-call/thinking probes, and harden weak-model tool-arg reliability (guided decoding + field-level errors + semantic coercion)
- [ ] **Phase 7: Multi-Agent Verification + Interpretive Tail (β)** - Isolated write-disabled verifier sub-agents (KEEP|DOWNGRADE, never DROP), decorrelated cross-family, orchestrator consolidate/dedup/coverage, plus the agentic interpretive-tail pass
- [ ] **Phase 8: Cost Governor (β)** - Prompt-cache stable prefix + escalating compaction + cheap-model triage so cost scales with docs that need deep reasoning, not corpus size

## Phase Details

### Phase 0: Eval Harness
**Goal**: The system can measure precision and recall **by failure family** against a multi-document ground-truth set, so every later phase is gated on evidence, not assertion. This is the instrument that tells us whether becoming an agent moves the measured 7%-recall ceiling.
**Depends on**: Nothing (first phase; runs continuously as the gate on Phases 1–8)
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
  5. Every reconstructed table cell is **addressable**: it carries an ordinary span-ID (byte-exact, re-openable) and resolves through a `(table_id, row, col)` index; merged cells resolve identically from every coordinate they span; and a document whose tables could not be reconstructed reports **table-tier unavailable** in the coverage manifest rather than appearing complete. Without this, Phase 5's cell-level structural/cross-document comparisons have no substrate to run on.
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
  8. Re-retrieving an unchanged span returns a "still current — refer to your earlier retrieval" stub instead of the full text (read deduplication), with the hit rate reported. Built here, not in Phase 8: it lives inside the retrieval tools, and a reviewer re-opens the same spec table many times per run — every downstream eval iteration pays for its absence.
**Plans**: 9 plans
- [x] 02-01-PLAN.md — Tool layer foundation: RetrievalLedger + ToolRejected + textsplit + open_doc/get_section/follow_reference (TOOLS-01/02/04, COST-04, D-FR)
- [x] 02-02-PLAN.md — Rulebook storage primitives: RuleChunk local store (SQLite+FAISS+BM25) + the generic edge table (RULES-04, D-RB3, D-RB6)
- [x] 02-03-PLAN.md — Rulebook sourcing: eCFR/ICH/FDA vendoring + build orchestration, real live-fetched content committed to rulebook/ (RULES-01/02/03/04, D-RB1, D-RB2, D-PREC)
- [x] 02-04-PLAN.md — search_corpus: local hybrid (FAISS+BM25+RRF) per-submission retrieval tool (TOOLS-01, D-RB5)
- [x] 02-05-PLAN.md — emit_finding: the dual byte-exact grounding gate, the only path a finding can exist through (TOOLS-03, D-EF1)
- [x] 02-06-PLAN.md — Requirement index: loader gate + authored v1 data + edges + ground-truth traceability + senior-reviewer checkpoint (RULES-05, D-RI1, D-RB4)
- [x] 02-07-PLAN.md — Eval harness extension: real search_corpus-driven recall@k + retrieval-gate CI command + committed SC4 baseline (D-SC4)
- [x] 02-08-PLAN.md — Databricks rulebook serving: Delta population + client-side-cosine query, completing the two-backend dispatch (D-RB2, D-RB6)
- [x] 02-09-PLAN.md — read_guideline: the 5th tool, dual enumerate/fetch mode tying store + requirement index together (TOOLS-01/04, RULES-05, COST-04, D-RI2)
**Research flag**: Rulebook sourcing is its own de-risking sub-track — ICH exact license/notice wording, FDA-guidance completeness via regulations.gov, and eCFR version pinning have real external uncertainty. (`follow_reference`'s full reference-graph backing completes in Phase 5.)

### Phase 3: Drive-Loop Spike (GO/NO-GO)
**Goal**: Prove the central unknown — a **single** tool-using agent can navigate the corpus on Llama 3.3 70B / Qwen, ground every finding to a re-openable source quote **and** a cited rule, and stop within hard code budgets. If the loop can't ground reliably here, Phases 4–6 are moot; keep it one agent to isolate the risk before multiplying cost by N.
**Depends on**: Phase 2
**Outcome**: **COMPLETE — NO-GO** (closed 2026-08-05). Third consecutive NO-GO (v2, v3.2, v3.3). Median overall recall `0.071` < baseline `0.107`; protected set `{B-08, C-01, C-02}` lost two of three (C-01 and B-08 absent from all three runs); `absence_of_evidence` = `0.000` across all runs. Diagnosis: not a wiring/plumbing problem — a **general reasoning weakness** of the local model on lead→`get_section`→`read_guideline`→`emit_finding` conversion and on "a required item is ABSENT" reasoning. **Superseded by β**: recall moves to a general deterministic pipeline (Phases 4–5) and the agent is repurposed as a write-disabled verifier (Phase 7). Records (`03-19-V3.3-READING.md`, prereg, scored artifacts) are **retained as the audit trail**; requirements AGENT-01/03, GROUND-01/03, DETECT-03/04 marked Complete against the spike, AGENT-02/04 and DETECT-01/02/05 re-homed under β.
**Requirements**: AGENT-01, AGENT-03, AGENT-04, GROUND-01, GROUND-03, DETECT-03, DETECT-04
**Success Criteria** (what must be TRUE):
  1. Detection runs as a **model-driven, model-agnostic tool loop** (request evidence → reason → request more → stop on done/budget) that replaces the one-shot pre-rendered call, and it emits reliable tool-call arguments on **both** Llama 3.3 70B and Qwen (the go/no-go validation), with `structured.py` as the malformed-arg fallback.
  2. Every finding the agent emits is pinned to a **verbatim quote it actually retrieved** (re-opening the span reproduces it byte-for-byte) AND **dual-cited** to the specific FDA/ICH rule clause it violates, with a **compliance verdict** per finding tied to that rule.
  3. Hard per-run token/step/wall-clock budgets and a **circuit breaker** are enforced **in code, not prompt** — a runaway load test halts at the ceiling and returns the grounded partial, never crashing or overspending — **plus a diminishing-returns stop**.
  3b. The budget is **bidirectional**: when the model emits no tool call but is under budget and not in diminishing returns, the loop **refuses the stop** and injects a continuation nudge (`"Keep working — do not summarize"`), in code.
  4. Deterministic quick-win oracles (LOD/LOQ presence S9, reference standards S10, stability commitment P10) run as a **demoted seed pass** that feeds the loop — not as the primary source of findings.
  5. On the Phase 0 eval set, the grounded loop moves **recall-by-failure-family above the single-shot baseline** — the go signal that becoming-an-agent *adds missing check-kinds*. **RESULT: NOT MET — recall 0.071 < 0.107; NO-GO.**
**Plans**: 20 plans in 11 waves (scored set closed at NO-GO; remaining plans 03-12/14/15/16/17/18/19 not carried into β)

Plans:
- [x] 03-01-PLAN.md — P2: `pdf.py` embedded-text fallback fix + `PARSER_VERSION` in `cache_key` + cache purge/re-ingest + baseline-shift disclosure (D-PRE1 step 1)
- [x] 03-02-PLAN.md — Grounding contract additions: `ToolRejected.half`, `KNOWN_REASON_CODES`, `ComplianceVerdict`, `Fault.rule_span_id`/`verdict`, harness versions (D-TEL2/3, D-VER2)
- [x] 03-03-PLAN.md — `chat_completion_tools` + `ChatTurn`; Databricks-legal tool-schema derivation; dependency/STATE hygiene (AGENT-01, D-LOOP3)
- [x] 03-04-PLAN.md — P1: real-ingestion 3.2.S.5 classification proof + verification-queue item 5 closure check (D-PRE1 step 2)
- [x] 03-05-PLAN.md — Review package scaffold + Wave-0 offline test doubles (ScriptedChatClient / ForcedRunaway / ReplayClient, multi-doc corpus) + D-RB6 CI
- [x] 03-06-PLAN.md — `spanref.py` single parse/mint path + GROUND-01 round-trip composition test across all 5 rendering tools
- [x] 03-07-PLAN.md — `BudgetLedger`: every AGENT-03/AGENT-04 stop condition as code, with the frozen N values
- [x] 03-08-PLAN.md — `telemetry.py`: per-turn JSONL, provenanced `RunSummary`, all five D-TEL signal groups, atomic writes
- [x] 03-09-PLAN.md — `run_oracles` as the 7th tool; S10 built, P10 generalized; D-ORC2 no-pre-recorded-spans (DETECT-03)
- [x] 03-10-PLAN.md — Boundary-crossing hunt: enumerated chain audit + a composition test per chain (D-PRE1 step 3)
- [x] 03-11-PLAN.md — `registry.py`: 7 flat arg models, schema derivation, dispatch, pre/post-repair split, Pitfall-6 fallback
- [x] 03-11-P0-PLAN.md — **BLOCKING P0 repair**: fix redesigned single-shot detector regression; prove planner->workers on real TP sections emits a candidate and `{C-01,C-02}` are re-found in ≥2/3 live runs
- [x] 03-12-PLAN.md — D-LOOP2 baseline re-measured 3x; median + variance + drift check; reviewer confirms the governing reference (D-PRE1 step 4)
- [x] 03-13-PLAN.md — `loop.py` + static `prompts.py` + `run_review`; D-LOOP4 prefix stability; tool-message protocol (AGENT-01)
- [x] 03-14-PLAN.md — Stop-condition wiring, AGENT-04 continuation floor, D-LOOP5 rejection turns, D-BUD6 forced-runaway load test
- [x] 03-15-PLAN.md — `evals.run agent-run` subcommand (per-run budget, corpus-wide), D-VER1 non-dropping proof, additive UI events (D-LOOP1)
- [x] 03-16-PLAN.md — D-BUD1 budget calibration; reviewer decides the calibration corpus then freezes the ceilings
- [x] 03-17-PLAN.md — 3-bucket reachability classification + `03-GO-NOGO-PREREGISTRATION.md` authored, signed off and committed before any scored run (D-GO5, D-PRE1 step 5)
- [x] 03-18-PLAN.md — The 3 scored agent runs + Qwen fidelity probe + real-model low-ceiling confirmation (D-GO2, D-GO3(ii), D-BUD6)
- [x] 03-19-PLAN.md — Cross-run comparison + telemetry diagnosis + phase report; **senior-reviewer NO-GO decision** (D-GO5 sign-off)

**Research flag**: Per-model tool-call reliability + JSON-arg fidelity on Llama 3.3 70B / Qwen MoE over long loops was the go/no-go unknown. **Answered: NO-GO** — recall is not reliably reachable by a local-model drive loop; β pivots recall to deterministic code.

---

## β Phases (Deterministic Recall + Agentic Verify)

The phases below replace the superseded v1.0 agentic-recall Phases 4–6. Dependency-ordered: enrich the rulebook and enumerate absences → deterministic structural + cross-document + precedent recall → serve the on-prem verifier model and harden weak-model reliability → multi-agent verification + interpretive tail → cost governor. **Phase 0's recall-by-family harness gates every β phase with zero-true-positives-lost. All recall checks stay rulebook/structure/graph-general — no corpus hardcoding.**

### Phase 4: Rulebook Enrichment + Absence Enumeration (β)
**Goal**: Close the #1 recall gap — `absence_of_evidence = 0.000` — with the general mechanism absence detection actually requires: enumerate the FDA/ICH required items applicable to a submission from the rulebook's requirement index, check which the submission does not address, and emit each absence as a grounded candidate. Absence is inherently a rulebook-enumeration problem (you cannot read what is not present), so the rulebook must first be thickened from its current thin coverage (ich=4, fda=1 chunks vs eCFR 215) to the per-requirement granularity enumeration needs. Driven by the rulebook, **never** by knowledge of a specific corpus.
**Depends on**: Phase 2 (rulebook store + requirement index + `read_guideline`), Phase 1 (coverage manifest — what the submission contains)
**Requirements**: RULES-06, RECALL-01
**Success Criteria** (what must be TRUE):
  1. The rulebook's ICH/FDA coverage is enriched to **per-requirement granularity** — each enrichable requirement carries a citation, a one-line applicability trigger, and the full rule text fetchable on demand — so the requirement index the enumerator walks is no longer sparse (ich/fda coverage measurably increased from the ich=4/fda=1 baseline, with `{source, citation, version/date, license, url}` and the ICH copyright acknowledgment preserved on every new chunk).
  2. Given a submission's coverage manifest, the system **enumerates the applicable required items** (applicability driven by the rulebook trigger + content-derived document classification, not folder names) and **flags each required item the submission does not address**, emitting it as a grounded absence candidate dual-cited to the rule — recovering `absence_of_evidence` above the `0.000` floor on the Phase 0 eval set.
  3. Enumeration is **corpus-general**: a guard test proves the absence check embeds no submission-specific constant — running it against a held-out corpus produces absence candidates from the *same* rulebook logic, and renaming/reorganizing folders does not change which requirements are deemed applicable.
  4. Every absence candidate is **grounded and re-openable** — it names the rule clause it violates and the coverage-manifest evidence that the required item is absent — so a downstream verifier can re-open both sides; a "no absences" result states which required items *were* satisfied (coverage is meaningful).
**Plans**: 3 plans in 2 waves
- [x] 04-01-PLAN.md — Rulebook + requirement-index enrichment: vendor ICH Q1A(R2), decompose Q3A/Q3B/Q6A per-requirement, expand closure edges, coverage baseline + traceability gate (RULES-06)
- [x] 04-02-PLAN.md — Emit-gate absence variant: CoverageAbsenceAnchor schema + emit_absence_finding (byte-exact rule half, re-derivable anchor) (RECALL-01)
- [ ] 04-03-PLAN.md — Deterministic absence pass: enumerate_requirements ∘ search_corpus ∘ emit_absence_finding, mvr1381-tuned threshold, absence-gate (recover absence>0.000), D-GEN3 generality CI guard (RECALL-01)

### Phase 5: Deterministic Structural & Cross-Document Recall (β)
**Goal**: Own the rest of recall in general deterministic code — intra-document structural inconsistencies (summary-vs-detail value mismatch, reported result exceeding its spec limit), a cross-document reference graph (hyperlinks, "see §X", numeric value cross-refs) that flags unresolved references / absent referenced content or documents / cross-document value contradictions, and precedent-similarity candidates over the past-deficiency corpus. This completes `follow_reference`'s reference-graph backing and subsumes the old cross-document checks (X1/X2). Every check emits a grounded candidate and stays rulebook/structure/graph-general behind an enforced anti-overfitting guard.
**Depends on**: Phase 4 (absence candidates share the same grounded-candidate contract), Phase 1 (addressable table cells + span-anchors), Phase 2 (`follow_reference` + precedent retrieval store)
**Requirements**: RECALL-02, RECALL-03, RECALL-04, RECALL-05
**Success Criteria** (what must be TRUE):
  1. The system **deterministically detects intra-document structural inconsistencies** — a summary value that disagrees with its detail value, and a reported result that exceeds its stated spec limit — computed over two verbatim, re-openable cells and emitted as grounded candidates dual-cited to source (and rule where one applies).
  2. The system builds a **cross-document reference graph** and flags **unresolved references, absent referenced content or documents, and cross-document value contradictions** — catching at least one cross-document specification mismatch (X1: QOS 2.3 vs Module 3.2 body) and one cross-document value contradiction (X2) end-to-end on the Phase 0 eval set. This is submission-internal integrity the rulebook cannot express.
  3. The system **surfaces candidate deficiencies by similarity to the past-deficiency (precedent) corpus**, each carrying its source anchor, so precedent recall is measured as its own family on the harness.
  4. **Anti-overfitting is enforced by a guard test**: every deterministic recall check (structural, reference-graph, precedent) is rulebook/structure/graph-general — the guard asserts no submission-specific constant (batch number, doc name, spec value, section path) is embedded in check logic, and the checks run unchanged against a held-out corpus. The eval corpus is a proxy; any check tuned to recover a specific item on *this* corpus fails the guard.
  5. On the Phase 0 eval set, combined deterministic recall (absence + structural + cross-document + precedent) moves **recall-by-family above the 0.071 baseline** with **zero true positives lost**, and every emitted candidate is grounded to a re-openable verbatim quote.
**Plans**: TBD

### Phase 6: On-Prem Verifier Model + Weak-Model Reliability (β)
**Goal**: Stand up the reasoning/verification model the β verifier runs on — NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5, served **self-hosted on Databricks** alongside Llama 3.3 70B + Qwen MoE, with **no external LLM API ever called** — and prove it is production-wired before Phase 7 depends on it. Because the verifier still runs on weaker open-weights models, harden tool-call reliability here: server-side guided decoding, field-level actionable errors, and targeted semantic arg coercion — so the KEEP|DOWNGRADE verdicts in Phase 7 parse reliably instead of dropping findings to malformed args.
**Depends on**: Phase 2 (tool layer + `structured.py` fallback the reliability hardening extends), Phase 3 records (the measured weak-model tool-arg failure modes this phase addresses)
**Requirements**: MODEL-01, MODEL-02, RELIABILITY-01, RELIABILITY-02, RELIABILITY-03
**Success Criteria** (what must be TRUE):
  1. Nemotron-Super-49B-v1.5 is **served self-hosted on the company's Databricks** and reachable through the OpenAI-compatible model dispatch as the verify/reasoning model — a test asserts **no external LLM endpoint (Claude/GPT) is ever configured or called**, so the on-premise/privacy constraint holds by construction.
  2. **Nemotron pre-wiring probes pass on real verification traces**: vLLM tool-call works, `detailed thinking on/off` is validated, and the tool-parser flags + quantization are confirmed for the target GPU — the model reliably returns a machine-parsable `VERDICT` on a real claim + source + rule input.
  3. **Tool-call arguments are constrained by server-side guided decoding** (vLLM `guided_json` / Ollama `format`) wherever the endpoint supports it, and a malformed-arg emits **field-level actionable feedback** (which field, expected type) bounded by a retry cap — measurably reducing the weak-model tool-arg failure rate versus the Phase 3 baseline.
  4. **Targeted semantic arg coercion** handles the observed weak-model failure modes (quoted numbers/booleans, single-key-wrapper unwrap) **without loosening the advertised schemas** — a test proves the advertised schema is unchanged while the coercion recovers previously-rejected valid intents.
**Plans**: TBD

### Phase 7: Multi-Agent Verification + Interpretive Tail (β)
**Goal**: Repurpose the agent as the β **verifier** — the role the NO-GO proved it can do that recall it cannot. Each deterministic candidate is judged by an isolated, write-disabled verifier sub-agent that re-opens the cited source + rule and returns a machine-parsed `VERDICT: KEEP | DOWNGRADE` (**never DROP**; unsure resolves to KEEP — the downgrade-never-drop recall invariant, enforced in code). An orchestrator fans out verifiers keyed on `docId:sectionId:ruleId`, consolidates and dedups, and reports coverage. The verifier model is cross-family / decorrelated from the candidate source so correlated errors cannot be rubber-stamped. Finally, an agentic **interpretive-tail** pass surfaces grounded deficiencies no deterministic rule can express — the narrow, precision-gated place the loop still earns its keep. Subsumes GROUND-02, AGENT-02, DETECT-05.
**Depends on**: Phase 5 (grounded deterministic candidates to verify), Phase 6 (Nemotron verifier model + weak-model reliability)
**Requirements**: VERIFY-01, VERIFY-02, VERIFY-03, VERIFY-04
**Success Criteria** (what must be TRUE):
  1. Each candidate goes to an **isolated, write-disabled** verifier sub-agent that **re-opens** the cited source (`get_section`) and rule (`read_guideline`) — not a pre-rendered excerpt — and returns a machine-parsed `VERDICT: KEEP | DOWNGRADE`. It **can never DROP**; an unsure/ungrounded verdict resolves to **KEEP** and only lowers confidence — the downgrade-never-drop recall invariant, enforced in **code**, proven by a test that no verifier path removes a candidate.
  2. An **orchestrator** fans out verifiers keyed on `docId:sectionId:ruleId`, **consolidates and dedups**, and emits a **coverage report** so a "no deficiencies found" result states exactly what was reviewed and what could not be located — never an unqualified "compliant."
  3. The verifier is **cross-family / decorrelated** from the candidate source (different model persona than the deterministic-candidate producer, no access to any generator reasoning — only the claim + source + rule), so correlated errors cannot be rubber-stamped; a test asserts the verifier cannot see the producer's chain.
  4. An **agentic interpretive-tail pass** surfaces grounded deficiencies that no deterministic rule expresses, each pinned to a re-openable verbatim quote + cited rule — and on the Phase 0 eval set, adding verification + interpretive-tail iterations **does not lower end-to-end F1** and loses **zero true positives** versus the Phase 5 deterministic output.
**Plans**: TBD

### Phase 8: Cost Governor (β)
**Goal**: Make the uncapped-corpus promise real for the β architecture — a prompt-cache stable prefix, escalating context compaction, and cheap-model triage so verification and the interpretive tail reason over a corpus far larger than the context window and **cost scales with docs that need deep reasoning, not raw corpus size.** Hardens the budget guardrail from Phase 3 under a synthetic large-corpus load test, entirely on self-hosted serving (provider-side prefix caching, not an external `cache_control` API).
**Depends on**: Phase 7 (wraps every verifier/interpretive agent call), Phase 2 (COST-04 read-dedup it builds on)
**Requirements**: COST-01, COST-02, COST-03
**Success Criteria** (what must be TRUE):
  1. A **stable cached prompt prefix** (system + tool schemas) plus **escalating context compaction** let an agent reason over a corpus far larger than the context window — and a finding provable in small context is **still found** inside a large-corpus run (no compaction / lost-in-the-middle regression). **Cache-stability invariant enforced by test:** no dynamic content (rule lists, corpus manifest, document counts) appears in the system prompt or tool schemas — a test asserts the rendered prefix is byte-identical across two runs over *different* corpora.
  2. Compaction clears **tool results (evidence) only — never reasoning or emitted findings/verdicts** — keeps the N most recent, and **freezes each replacement decision by span-ID** so re-rendered turns are byte-identical; the Phase 2 read-dedup (COST-04) holds under compaction (a span shed by compaction and re-opened by handle does not return the "still current" stub).
  3. **Cheap-model triage** shortlists the documents/sections worth deep reasoning so a synthetic **large-corpus load test** shows cost scaling with docs that need deep reasoning — not raw corpus size — while staying within per-run budget ceilings, and every run records tokens/cost/steps in the job store.
  4. The **full eval gate** (recall-by-family + zero-true-positives-lost) passes at corpus scale — cost governance does not cost recall.
**Plans**: TBD
**Research flag**: Prompt-caching mechanics differ across Ollama vs. Databricks (provider-side automatic prefix caching) — verify the actual on-prem cost lever available before designing to it. (Anthropic `cache_control` is excluded by the on-premise constraint.)

## Progress

**Execution Order:**
Phases execute in numeric order: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8.
Phase 3 is closed at **NO-GO** and superseded by β; β work resumes at Phase 4.
Phase 0 (Eval Harness) is also the **continuous gate**: its recall-by-family metrics gate every later phase (including every β phase, with zero-true-positives-lost) — not "completed and forgotten."

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Eval Harness | 4/4 | Complete | 2026-07-30 |
| 1. Ingestion Foundation | 9/9 | Complete | 2026-07-31 |
| 2. Retrieval, Navigation Tools & Rulebook | 9/9 | Complete | 2026-07-31 |
| 3. Drive-Loop Spike (GO/NO-GO) | 20/20 | Complete — NO-GO (superseded by β) | 2026-08-05 |
| 4. Rulebook Enrichment + Absence Enumeration (β) | 0 / TBD | Not started | - |
| 5. Deterministic Structural & Cross-Document Recall (β) | 0 / TBD | Not started | - |
| 6. On-Prem Verifier Model + Weak-Model Reliability (β) | 0 / TBD | Not started | - |
| 7. Multi-Agent Verification + Interpretive Tail (β) | 0 / TBD | Not started | - |
| 8. Cost Governor (β) | 0 / TBD | Not started | - |
