# Requirements: DefPredict — Agentic FDA/ICH Compliance Reviewer

**Defined:** 2026-07-30
**Core Value:** Given any directory of submission documents, reliably find the real FDA/ICH compliance deficiencies — all faults and only faults that exist — each cited to the exact passage that proves it.

**Scope framing:** The *infrastructure* (ingestion, rulebook, tools, loop, verifier, cost, eval) is fully general — any module, any directory, any nesting depth, no document-count cap. The v1 *deficiency check-kinds* are seeded from the CMC taxonomy + existing ANDA ground truth (what we can measure) and are designed to extend to more families/modules in v2. v1 is a general system whose first *measurable* checks are CMC — not an M3-locked system.

## v1 Requirements

### Ingestion (general corpus intake)

- [ ] **INGEST-01**: System ingests an arbitrary deeply-nested directory of PDF + DOCX documents with no document-count cap, classifying each document by content (never by folder name)
- [ ] **INGEST-02**: System parses DOCX into the same unified structured document model used for PDFs (alongside the existing PDF/OCR path)
- [ ] **INGEST-03**: System builds a per-submission corpus index and a coverage manifest of what the corpus contains — including a per-document **availability contract** (canonical text + span-IDs guaranteed; section outline and table addressing best-effort) and typed statuses `parsed / parsed_partial / parse_failed / unsupported`, so downstream phases read capability from the manifest instead of discovering it at runtime
- [ ] **INGEST-04**: Ingestion emits the **span-anchor substrate** every later phase grounds on: one canonical normalized text stream per document, a retained canonical→raw offset map, a versioned normalizer, stable content-addressed span-IDs (`{doc_id, start, end}` + substring hash), and a **re-open/verify primitive** that returns both the raw and canonical substrings for a span-ID or fails on hash mismatch. (Anchors are an ingestion property; Phase 2's `TOOLS-02` span-ID contract and `TOOLS-03` emit gate are built on this, not alongside it.)
- [ ] **INGEST-05**: Every reconstructed table cell is **addressable** — serialized into the canonical text so it carries an ordinary span-ID, and resolvable through a `(table_id, row, col)` index, with merged cells resolving identically from every coordinate they span and serialization order deterministic and version-stamped. (Phase 5's "code recomputation over two verbatim cells" and Phase 4's X1/X2 cell-level comparisons have no substrate without this.)

### Rulebook (FDA/ICH retrievable reference)

- [x] **RULES-01**: System ingests eCFR Title 21 (public-domain XML) as the retrievable rulebook backbone
- [x] **RULES-02**: System ingests ICH guidelines into the rulebook (storing the required copyright acknowledgment with each chunk)
- [x] **RULES-03**: System ingests FDA guidances (via regulations.gov) for the topics the eval set exercises
- [x] **RULES-04**: Every rule chunk is stored with `{source, citation, version/date, license, url}` metadata
- [x] **RULES-05**: The rulebook exposes a compact **requirement index** (citation + one-line applicability trigger) separate from full rule text, so the agent can *enumerate* what a submission must contain rather than only semantically searching what it does contain — the mechanism absence-of-evidence detection depends on; full rule text is fetched on demand (progressive disclosure)

### Navigation Tools

- [x] **TOOLS-01**: Agent has general tools — `search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline` — that return identifiers/snippets, not whole documents (JIT retrieval)
- [x] **TOOLS-02**: Tools return verbatim span-IDs so a finding's quote is *selected* from the source, never authored by the model (prevents citation drift)
- [x] **TOOLS-03**: Findings are emitted **only** through an `emit_finding` tool whose input validation re-resolves the cited span against the corpus and **rejects the call with a typed, self-correcting error** when the quote is not byte-identical, is not unique, was never retrieved this session, or carries no rule citation — grounding enforced at the tool boundary, not audited downstream
- [x] **TOOLS-04**: Tool results exceeding a size threshold are persisted to disk and returned as a bounded preview plus a re-openable handle; over-large `get_section` requests **fail with a narrow-your-range error rather than truncating** (a truncated result costs ~25k tokens, an error costs ~100 bytes)

### Agentic Loop

- [ ] **AGENT-01**: Detection runs as a model-driven, model-agnostic tool loop (reviewer requests evidence → reasons → requests more → stops on done/budget), replacing the one-shot pre-rendered call
- [ ] **AGENT-02**: An orchestrator decomposes a review into objectives and fans out isolated sub-agents that each return a distilled, cited finding set
- [ ] **AGENT-03**: Hard per-run budgets and a circuit breaker are enforced in code (stop conditions are code gates, not prompt instructions), **plus a diminishing-returns stop** — N consecutive steps yielding negligible new grounded evidence halts the loop before the ceiling, so budget is spent on progress rather than circling
- [ ] **AGENT-04**: The budget is **bidirectional — a FLOOR as well as a ceiling.** When the model emits no tool call (i.e. declares itself finished) but is still well under budget AND has not hit the diminishing-returns condition, the loop **does not accept the stop**: it injects a continuation nudge and runs another turn. The model's self-assessment of "done" is **not** a termination condition. Rationale (this is the recall requirement): our measured failure is 2/28 — an agent that stops after finding a few obvious faults reproduces exactly that ceiling, and no ceiling-only budget can prevent it. Verbatim precedent — Claude Code `query.ts:1338` `token_budget_continuation` + `utils/tokenBudget.ts:72`: *"Stopped at {pct}% of token target. Keep working — do not summarize."* Enforced in code, never as a prompt instruction. **Anti-abuse:** the nudge is bounded by the same diminishing-returns rule (AGENT-03) so it cannot loop forever, and every continuation is recorded in telemetry (count + tokens-at-stop + whether new grounded findings followed) so the spike measures whether nudging actually buys recall or just burns budget.

### Grounding & Verification

- [ ] **GROUND-01**: Every claimed deficiency is pinned to a verbatim, re-openable source quote the agent actually retrieved
- [ ] **GROUND-02**: A grounded adversarial verifier confirms or refutes each candidate against the source; an ungrounded challenge lowers confidence but never vetoes (recall invariant preserved)
- [ ] **GROUND-03**: Each finding is dual-cited — the submission passage AND the specific FDA/ICH rule clause it violates

### Detection (v1 compliance check-kinds)

- [ ] **DETECT-01**: System detects cross-document specification mismatch (X1: Quality Overall Summary 2.3 vs Module 3.2 body) — the flagship check
- [ ] **DETECT-02**: System detects cross-document value contradictions (X2)
- [ ] **DETECT-03**: System runs deterministic quick-win oracles: LOD/LOQ presence (S9), reference standards (S10), stability commitment (P10)
- [ ] **DETECT-04**: System emits a compliance verdict per finding tied to a cited FDA/ICH rule
- [ ] **DETECT-05**: System emits a coverage manifest so a "no deficiencies found" result is meaningful (states what was reviewed)

### Evaluation (harness first & continuous)

- [ ] **EVAL-01**: A ground-truth eval set is built from the existing ANDA deficiency data (PDF + DOCX, expanded beyond the current single-document set)
- [ ] **EVAL-02**: The harness reports per-stage metrics — retrieval recall@k, parse fidelity, anchor rate, verifier precision/recall, and end-to-end precision/recall by failure family
- [ ] **EVAL-03**: Every filter/change is gated by a "zero true-positives-lost" check against the eval set

### Cost Governor

- [ ] **COST-01**: A prompt-cache stable prefix + escalating context compaction let one agent reason over a corpus larger than the context window. **Cache-stability invariant:** nothing dynamic (rule lists, corpus manifests, document counts) may live in the system prompt or tool schemas — dynamic content goes in messages, or every corpus change busts the whole cached prefix
- [ ] **COST-02**: Cheap-model triage + per-run budget ceilings keep cost scaling with docs that need deep reasoning, not raw corpus size
- [ ] **COST-03**: Compaction clears **tool results (evidence) only — never reasoning or emitted findings** — retains the N most recent results, and **freezes every replacement decision by span-ID** so re-rendered turns are byte-identical. This is what makes the recall invariant survive compaction: the agent keeps what it concluded even after the bulk evidence is shed, and can re-open any shed span by handle
- [x] **COST-04**: Re-retrieving an unchanged span returns a "still current, refer to your earlier retrieval" stub instead of the full text (read deduplication)

## v2 Requirements

Deferred — tracked, not in the current roadmap.

### Detection depth
- **DET-V2-01**: Threshold-arithmetic deficiencies (impurities S2–S5, residual solvents Q3C, elemental Q3D, P3) — require cross-document retrieval to be solid first
- **DET-V2-02**: Method-validation (ICH Q2) and stability-adequacy (ICH Q1) deficiency suites
- **DET-V2-03**: Semantic reference-graph contradictions (X3 method inconsistency, X5 coverage gaps, X6 data-integrity/traceability)
- **DET-V2-04**: Biologics + Modules 1/2/4/5 check-kinds
- **DET-V2-05**: Suggested-resolution hints per finding

### Infrastructure
- **INF-V2-01**: Docling upgrade for unified PDF+DOCX parsing if python-docx table fidelity proves insufficient
- **INF-V2-02**: Optional Claude-orchestrator variant (additive; only if Claude access is added)

## Out of Scope

Explicitly excluded (anti-features). Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Auto-filing / submitting to FDA | Review/advisory tool; human stays in the loop |
| Final "approvable / not approvable" determination | Legal/regulatory sign-off is not the tool's role |
| Unbounded, ungrounded autonomy | Grounding is the license to operate; autonomy without it produces confident hallucination |
| Answer-key oracles as primary intelligence | Brittle, don't generalize; deterministic checks kept narrow, for stable facts only |
| Hardcoded module/folder layout | Must generalize to any directory/naming; classification is content-driven |
| Auto-drafting the deficiency response | Out of scope for v1; reviewer finds, humans respond |
| Full-corpus context stuffing | Defeats the retrieval/compaction design; won't scale |
| Uncalibrated numeric risk scores | Misleading without calibration; confidence is tied to evidence class instead |

## Traceability

Each v1 requirement maps to exactly one phase. See `.planning/ROADMAP.md` for phase detail and success criteria. Phases execute 0 → 6; Phase 0 (Eval Harness) also runs continuously as the gate on every later phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVAL-01 | Phase 0 — Eval Harness | Pending |
| EVAL-02 | Phase 0 — Eval Harness | Pending |
| EVAL-03 | Phase 0 — Eval Harness | Pending |
| INGEST-01 | Phase 1 — Ingestion Foundation | Pending |
| INGEST-02 | Phase 1 — Ingestion Foundation | Pending |
| INGEST-03 | Phase 1 — Ingestion Foundation | Pending |
| INGEST-04 | Phase 1 — Ingestion Foundation | Pending |
| INGEST-05 | Phase 1 — Ingestion Foundation | Pending |
| RULES-01 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-02 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-03 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-04 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-05 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-01 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-02 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-03 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-04 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| AGENT-01 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| AGENT-03 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| AGENT-04 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| GROUND-01 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| GROUND-03 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| DETECT-03 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| DETECT-04 | Phase 3 — Drive-Loop Spike (GO/NO-GO) | Pending |
| AGENT-02 | Phase 4 — Orchestrator + Sub-Agent Fan-Out | Pending |
| DETECT-01 | Phase 4 — Orchestrator + Sub-Agent Fan-Out | Pending |
| DETECT-02 | Phase 4 — Orchestrator + Sub-Agent Fan-Out | Pending |
| DETECT-05 | Phase 4 — Orchestrator + Sub-Agent Fan-Out | Pending |
| GROUND-02 | Phase 5 — Grounded Adversarial Verifier | Pending |
| COST-01 | Phase 6 — Cost Governor | Pending |
| COST-02 | Phase 6 — Cost Governor | Pending |
| COST-03 | Phase 6 — Cost Governor | Pending |
| COST-04 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |

**Coverage:**
- v1 requirements: 33 total *(INGEST 5 + RULES 5 + TOOLS 4 + AGENT 4 + GROUND 3 + DETECT 5 + EVAL 3 + COST 4 = 33)*
- Mapped to phases: 33 ✓
- Unmapped: 0 ✓
- Duplicates (mapped to >1 phase): 0 ✓

**Per-phase distribution:** Phase 0 → 3 · Phase 1 → 5 · Phase 2 → 10 · Phase 3 → 7 · Phase 4 → 4 · Phase 5 → 1 · Phase 6 → 3 (= 33).

**Note on category-vs-phase:** requirement prefixes are *categories*, not phases. Several categories split across phases by design — GROUND-01/03 land in Phase 3 while GROUND-02 lands in Phase 5; COST-04 lands in Phase 2 (it is tool-layer behavior) while COST-01/02/03 land in Phase 6.

---
*Requirements defined: 2026-07-30*
*Last updated: 2026-07-31 — count 33. Trail: 25 → 31 (2026-07-30, first Claude Code teardown: RULES-05, TOOLS-03/04, COST-03/04, AGENT-03 amended) → 32 (INGEST-04/05 span-anchor substrate + table addressing, less one reconciliation) → 33 (2026-07-31, second teardown of the loop layer: AGENT-04 bidirectional budget / continuation floor). RULES-01..05, TOOLS-01..04, COST-04 marked Complete after Phase 2 verification.*
