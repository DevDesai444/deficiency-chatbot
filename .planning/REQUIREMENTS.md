# Requirements: DefPredict — Agentic FDA/ICH Compliance Reviewer

**Defined:** 2026-07-30
**Core Value:** Given any directory of submission documents, reliably find the real FDA/ICH compliance deficiencies — all faults and only faults that exist — each cited to the exact passage that proves it.

**Scope framing:** The *infrastructure* (ingestion, rulebook, tools, loop, verifier, cost, eval) is fully general — any module, any directory, any nesting depth, no document-count cap. The v1 *deficiency check-kinds* are seeded from the CMC taxonomy + existing ANDA ground truth (what we can measure) and are designed to extend to more families/modules in v2. v1 is a general system whose first *measurable* checks are CMC — not an M3-locked system.

## v1 Requirements

### Ingestion (general corpus intake)

- [x] **INGEST-01**: System ingests an arbitrary deeply-nested directory of PDF + DOCX documents with no document-count cap, classifying each document by content (never by folder name)
- [x] **INGEST-02**: System parses DOCX into the same unified structured document model used for PDFs (alongside the existing PDF/OCR path)
- [x] **INGEST-03**: System builds a per-submission corpus index and a coverage manifest of what the corpus contains — including a per-document **availability contract** (canonical text + span-IDs guaranteed; section outline and table addressing best-effort) and typed statuses `parsed / parsed_partial / parse_failed / unsupported`, so downstream phases read capability from the manifest instead of discovering it at runtime
- [x] **INGEST-04**: Ingestion emits the **span-anchor substrate** every later phase grounds on: one canonical normalized text stream per document, a retained canonical→raw offset map, a versioned normalizer, stable content-addressed span-IDs (`{doc_id, start, end}` + substring hash), and a **re-open/verify primitive** that returns both the raw and canonical substrings for a span-ID or fails on hash mismatch. (Anchors are an ingestion property; Phase 2's `TOOLS-02` span-ID contract and `TOOLS-03` emit gate are built on this, not alongside it.)
- [x] **INGEST-05**: Every reconstructed table cell is **addressable** — serialized into the canonical text so it carries an ordinary span-ID, and resolvable through a `(table_id, row, col)` index, with merged cells resolving identically from every coordinate they span and serialization order deterministic and version-stamped. (Phase 5's "code recomputation over two verbatim cells" and cross-document cell-level comparisons have no substrate without this.)

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

- [x] **AGENT-01**: Detection runs as a model-driven, model-agnostic tool loop (reviewer requests evidence → reasons → requests more → stops on done/budget), replacing the one-shot pre-rendered call
- [~] **AGENT-02**: An orchestrator decomposes a review into objectives and fans out isolated sub-agents that each return a distilled, cited finding set *(re-homed under β VERIFY-02)*
- [x] **AGENT-03**: Hard per-run budgets and a circuit breaker are enforced in code (stop conditions are code gates, not prompt instructions), **plus a diminishing-returns stop** — N consecutive steps yielding negligible new grounded evidence halts the loop before the ceiling, so budget is spent on progress rather than circling
- [~] **AGENT-04**: The budget is **bidirectional — a FLOOR as well as a ceiling.** *(Spike mechanism; the loop is no longer the recall driver under β. Preserved as audit trail; recall floor now enforced by deterministic enumeration, RECALL-01.)*

### Grounding & Verification

- [x] **GROUND-01**: Every claimed deficiency is pinned to a verbatim, re-openable source quote the agent actually retrieved
- [~] **GROUND-02**: A grounded adversarial verifier confirms or refutes each candidate against the source; an ungrounded challenge lowers confidence but never vetoes (recall invariant preserved) *(re-homed under β VERIFY-01)*
- [x] **GROUND-03**: Each finding is dual-cited — the submission passage AND the specific FDA/ICH rule clause it violates

### Detection (v1 compliance check-kinds)

- [~] **DETECT-01**: System detects cross-document specification mismatch (X1: Quality Overall Summary 2.3 vs Module 3.2 body) — the flagship check *(re-homed under β RECALL-03)*
- [~] **DETECT-02**: System detects cross-document value contradictions (X2) *(re-homed under β RECALL-03)*
- [x] **DETECT-03**: System runs deterministic quick-win oracles: LOD/LOQ presence (S9), reference standards (S10), stability commitment (P10)
- [x] **DETECT-04**: System emits a compliance verdict per finding tied to a cited FDA/ICH rule
- [~] **DETECT-05**: System emits a coverage manifest so a "no deficiencies found" result is meaningful (states what was reviewed) *(re-homed under β VERIFY-02)*

### Evaluation (harness first & continuous)

- [ ] **EVAL-01**: A ground-truth eval set is built from the existing ANDA deficiency data (PDF + DOCX, expanded beyond the current single-document set)
- [ ] **EVAL-02**: The harness reports per-stage metrics — retrieval recall@k, parse fidelity, anchor rate, verifier precision/recall, and end-to-end precision/recall by failure family
- [ ] **EVAL-03**: Every filter/change is gated by a "zero true-positives-lost" check against the eval set

### Cost Governor

- [ ] **COST-01**: A prompt-cache stable prefix + escalating context compaction let one agent reason over a corpus larger than the context window. **Cache-stability invariant:** nothing dynamic (rule lists, corpus manifests, document counts) may live in the system prompt or tool schemas — dynamic content goes in messages, or every corpus change busts the whole cached prefix
- [ ] **COST-02**: Cheap-model triage + per-run budget ceilings keep cost scaling with docs that need deep reasoning, not raw corpus size
- [ ] **COST-03**: Compaction clears **tool results (evidence) only — never reasoning or emitted findings** — retains the N most recent results, and **freezes every replacement decision by span-ID** so re-rendered turns are byte-identical
- [x] **COST-04**: Re-retrieving an unchanged span returns a "still current, refer to your earlier retrieval" stub instead of the full text (read deduplication)

## v2.0 Requirements (β — current milestone)

The v1.0 agentic-recall loop is a confirmed NO-GO (`03-19-V3.3-READING.md`: recall 0.071 < 0.107; {C-01,B-08} lost every run; absence_of_evidence=0.000). β moves **recall** to a general deterministic pipeline and repurposes the agent as a **verifier**. Mapped across β Phases 4–8 (Phase 0 eval harness stays the continuous gate; Phases 0–3 preserved). All recall checks stay rulebook/structure/graph-general — no corpus hardcoding.

### Deterministic Recall
- [ ] **RECALL-01**: System enumerates applicable FDA/ICH required items from the rulebook requirement index and flags any the submission does not address (absence detection), driven by the rulebook — not by knowledge of a specific corpus
- [ ] **RECALL-02**: System deterministically detects intra-document structural inconsistencies (summary-vs-detail value mismatch, reported result exceeding its spec limit) and emits them as grounded candidates
- [ ] **RECALL-03**: System builds a cross-document reference graph (hyperlinks, "see §X", numeric value cross-refs) and flags unresolved references, absent referenced content or documents, and cross-document value contradictions — submission-internal integrity the rulebook cannot express (subsumes DETECT-01/02)
- [ ] **RECALL-04**: System surfaces candidate deficiencies by similarity to the past-deficiency (precedent) corpus
- [ ] **RECALL-05**: Every deterministic recall check is rulebook/structure/graph-general; a guard test proves no submission-specific constant is embedded (anti-overfitting — the eval corpus is a proxy, never a target)

### Multi-Agent Verification
- [ ] **VERIFY-01**: Each candidate is judged by an isolated, write-disabled verifier sub-agent that re-opens the cited source + rule and returns a machine-parsed VERDICT: KEEP | DOWNGRADE (never DROP; unsure resolves to KEEP — the downgrade-never-drop recall invariant, enforced in code) (subsumes GROUND-02)
- [ ] **VERIFY-02**: An orchestrator fans out verifiers keyed on docId:sectionId:ruleId, consolidates and dedups, and reports coverage so a "no deficiencies found" result states what was reviewed (subsumes AGENT-02, DETECT-05)
- [ ] **VERIFY-03**: The verifier model is cross-family / decorrelated from the candidate source, so correlated errors cannot be rubber-stamped
- [ ] **VERIFY-04**: An agentic interpretive-tail pass surfaces grounded deficiencies that no deterministic rule expresses

### On-Prem Models
- [ ] **MODEL-01**: NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 is served self-hosted on Databricks as the verify/reasoning model alongside Llama 3.3 70B + Qwen MoE; no external LLM API is ever called
- [ ] **MODEL-02**: Nemotron pre-wiring probes pass — vLLM tool-call + `detailed thinking on/off` validated on real verification traces; tool-parser flags and quant confirmed for the target GPU

### Weak-Model Reliability
- [ ] **RELIABILITY-01**: Tool-call arguments are constrained by server-side guided decoding (vLLM guided_json / Ollama format) wherever the endpoint supports it
- [ ] **RELIABILITY-02**: Malformed tool-args receive field-level, actionable error feedback (which field, expected type), bounded by a retry cap
- [ ] **RELIABILITY-03**: Targeted semantic arg coercion handles weak-model failure modes (quoted numbers/booleans, single-key-wrapper unwrap) without loosening advertised schemas

### Rulebook enrichment
- [ ] **RULES-06**: The rulebook's ICH/FDA coverage is enriched to the per-requirement granularity RECALL-01 enumeration needs (currently ich=4, fda=1 chunks vs eCFR 215)

**Carried from v1.0:** EVAL-01/02/03 (harness — continuous gate, Phase 0) and COST-01/02/03 (cost governor, β Phase 8) remain in scope and are mapped below. INF-V2-02 (Claude-orchestrator) is now **excluded** by the on-premise/privacy constraint.

## Deferred / Future Requirements

Deferred — tracked, not in the current milestone.

### Detection depth
- **DET-V2-01**: Threshold-arithmetic deficiencies (impurities S2–S5, residual solvents Q3C, elemental Q3D, P3) — require cross-document retrieval to be solid first
- **DET-V2-02**: Method-validation (ICH Q2) and stability-adequacy (ICH Q1) deficiency suites
- **DET-V2-03**: Semantic reference-graph contradictions (X3 method inconsistency, X5 coverage gaps, X6 data-integrity/traceability)
- **DET-V2-04**: Biologics + Modules 1/2/4/5 check-kinds
- **DET-V2-05**: Suggested-resolution hints per finding

### Infrastructure
- **INF-V2-01**: Docling upgrade for unified PDF+DOCX parsing if python-docx table fidelity proves insufficient
- **INF-V2-02**: ~~Optional Claude-orchestrator variant~~ — **EXCLUDED** by the β on-premise/privacy constraint (no external LLM API, ever)

## Out of Scope

Explicitly excluded (anti-features). Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| External LLM API (Claude/GPT) for any role | On-premise/privacy constraint — self-hosted open-weights ONLY; recall cannot be bought with a stronger hosted model |
| Auto-filing / submitting to FDA | Review/advisory tool; human stays in the loop |
| Final "approvable / not approvable" determination | Legal/regulatory sign-off is not the tool's role |
| Unbounded, ungrounded autonomy | Grounding is the license to operate; autonomy without it produces confident hallucination |
| Answer-key oracles as primary intelligence | Brittle, don't generalize; deterministic checks kept narrow, for stable facts only |
| Recall checks tuned to the eval corpus | The eval corpus is a proxy, never a target — any check tuned to recover a specific item on this corpus is overfitting and we stop (RECALL-05 guard) |
| Hardcoded module/folder layout | Must generalize to any directory/naming; classification is content-driven |
| Auto-drafting the deficiency response | Out of scope for v1; reviewer finds, humans respond |
| Full-corpus context stuffing | Defeats the retrieval/compaction design; won't scale |
| Uncalibrated numeric risk scores | Misleading without calibration; confidence is tied to evidence class instead |

## Traceability

### v1.0 heritage (Phases 0–3 — preserved)

Phases 0–3 are v1.0 heritage. Phase 3 (Drive-Loop Spike) closed **NO-GO** on 2026-08-05; its records are retained as the audit trail. Requirements originally mapped to the superseded v1 Phases 4–6 (AGENT-02, DETECT-01/02/05, GROUND-02, COST-01/02/03) are **re-homed under β** below and marked here as *→ β*. See `.planning/ROADMAP.md` for phase detail and success criteria.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EVAL-01 | Phase 0 — Eval Harness | Complete |
| EVAL-02 | Phase 0 — Eval Harness | Complete |
| EVAL-03 | Phase 0 — Eval Harness | Complete |
| INGEST-01 | Phase 1 — Ingestion Foundation | Complete |
| INGEST-02 | Phase 1 — Ingestion Foundation | Complete |
| INGEST-03 | Phase 1 — Ingestion Foundation | Complete |
| INGEST-04 | Phase 1 — Ingestion Foundation | Complete |
| INGEST-05 | Phase 1 — Ingestion Foundation | Complete |
| RULES-01 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-02 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-03 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-04 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| RULES-05 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-01 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-02 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-03 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| TOOLS-04 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| COST-04 | Phase 2 — Retrieval, Navigation Tools & Rulebook | Complete |
| AGENT-01 | Phase 3 — Drive-Loop Spike (NO-GO) | Complete (spike) |
| AGENT-03 | Phase 3 — Drive-Loop Spike (NO-GO) | Complete (spike) |
| AGENT-04 | Phase 3 — Drive-Loop Spike (NO-GO) | Spike mechanism — recall floor → β RECALL-01 |
| GROUND-01 | Phase 3 — Drive-Loop Spike (NO-GO) | Complete (spike) |
| GROUND-03 | Phase 3 — Drive-Loop Spike (NO-GO) | Complete (spike) |
| DETECT-03 | Phase 3 — Drive-Loop Spike (NO-GO) | Complete (spike) |
| DETECT-04 | Phase 3 — Drive-Loop Spike (NO-GO) | Complete (spike) |
| AGENT-02 | *superseded v1 Phase 4* | → β VERIFY-02 |
| DETECT-01 | *superseded v1 Phase 4* | → β RECALL-03 |
| DETECT-02 | *superseded v1 Phase 4* | → β RECALL-03 |
| DETECT-05 | *superseded v1 Phase 4* | → β VERIFY-02 |
| GROUND-02 | *superseded v1 Phase 5* | → β VERIFY-01 |
| COST-01 | *superseded v1 Phase 6* | → β Phase 8 |
| COST-02 | *superseded v1 Phase 6* | → β Phase 8 |
| COST-03 | *superseded v1 Phase 6* | → β Phase 8 |

### v2.0 β (Phases 4–8 + carried Phase 0/8)

Each v2.0 requirement maps to exactly one β phase. Phase 0 (Eval Harness) also runs continuously as the gate on every β phase (zero-true-positives-lost).

| Requirement | Phase | Status |
|-------------|-------|--------|
| RULES-06 | Phase 4 — Rulebook Enrichment + Absence Enumeration | Pending |
| RECALL-01 | Phase 4 — Rulebook Enrichment + Absence Enumeration | Pending |
| RECALL-02 | Phase 5 — Deterministic Structural & Cross-Document Recall | Pending |
| RECALL-03 | Phase 5 — Deterministic Structural & Cross-Document Recall | Pending |
| RECALL-04 | Phase 5 — Deterministic Structural & Cross-Document Recall | Pending |
| RECALL-05 | Phase 5 — Deterministic Structural & Cross-Document Recall | Pending |
| MODEL-01 | Phase 6 — On-Prem Verifier Model + Weak-Model Reliability | Pending |
| MODEL-02 | Phase 6 — On-Prem Verifier Model + Weak-Model Reliability | Pending |
| RELIABILITY-01 | Phase 6 — On-Prem Verifier Model + Weak-Model Reliability | Pending |
| RELIABILITY-02 | Phase 6 — On-Prem Verifier Model + Weak-Model Reliability | Pending |
| RELIABILITY-03 | Phase 6 — On-Prem Verifier Model + Weak-Model Reliability | Pending |
| VERIFY-01 | Phase 7 — Multi-Agent Verification + Interpretive Tail | Pending |
| VERIFY-02 | Phase 7 — Multi-Agent Verification + Interpretive Tail | Pending |
| VERIFY-03 | Phase 7 — Multi-Agent Verification + Interpretive Tail | Pending |
| VERIFY-04 | Phase 7 — Multi-Agent Verification + Interpretive Tail | Pending |
| EVAL-01 | Phase 0 — Eval Harness (continuous gate) | Complete |
| EVAL-02 | Phase 0 — Eval Harness (continuous gate) | Complete |
| EVAL-03 | Phase 0 — Eval Harness (continuous gate) | Complete |
| COST-01 | Phase 8 — Cost Governor (β) | Pending |
| COST-02 | Phase 8 — Cost Governor (β) | Pending |
| COST-03 | Phase 8 — Cost Governor (β) | Pending |

**v2.0 Coverage:**
- v2.0 requirements to map: 21 *(RECALL 5 + VERIFY 4 + MODEL 2 + RELIABILITY 3 + RULES-06 1 = 15 new; + carried EVAL 3 + COST 3 = 6)*
- Mapped to β phases: 21 ✓ *(EVAL-01/02/03 held in Phase 0 as the continuous gate; COST-01/02/03 in Phase 8)*
- Unmapped: 0 ✓
- Duplicates (mapped to >1 phase): 0 ✓

**Per-β-phase distribution:** Phase 4 → 2 (RULES-06, RECALL-01) · Phase 5 → 4 (RECALL-02/03/04/05) · Phase 6 → 5 (MODEL-01/02, RELIABILITY-01/02/03) · Phase 7 → 4 (VERIFY-01/02/03/04) · Phase 8 → 3 (COST-01/02/03) · Phase 0 (continuous) → 3 (EVAL-01/02/03) = 21.

**Note on category-vs-phase:** requirement prefixes are *categories*, not phases. Under β, several v1 categories are re-homed by design — DETECT-01/02 → RECALL-03; GROUND-02 → VERIFY-01; AGENT-02/DETECT-05 → VERIFY-02; COST-01/02/03 → Phase 8. AGENT-04's recall floor is subsumed by deterministic enumeration (RECALL-01) since the loop is no longer the recall driver.

---
*Requirements defined: 2026-07-30*
*Last updated: 2026-08-05 — β pivot. v1 count 33 (all mapped; Phases 0–2 Complete, Phase 3 Complete-NO-GO). v2.0 adds 15 new requirements (RECALL 5 + VERIFY 4 + MODEL 2 + RELIABILITY 3 + RULES-06) + carries EVAL 3 (Phase 0) + COST 3 (Phase 8) = 21 mapped across β Phases 4–8. Trail: Phase 3 drive-loop NO-GO (3rd consecutive; recall 0.071 < 0.107; absence=0.000) → recall re-architected as general deterministic pipeline, agent repurposed as write-disabled verifier; INF-V2-02 Claude-orchestrator excluded by on-premise constraint.*
