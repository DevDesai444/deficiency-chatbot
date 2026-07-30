# Requirements: DefPredict — Agentic FDA/ICH Compliance Reviewer

**Defined:** 2026-07-30
**Core Value:** Given any directory of submission documents, reliably find the real FDA/ICH compliance deficiencies — all faults and only faults that exist — each cited to the exact passage that proves it.

**Scope framing:** The *infrastructure* (ingestion, rulebook, tools, loop, verifier, cost, eval) is fully general — any module, any directory, any nesting depth, no document-count cap. The v1 *deficiency check-kinds* are seeded from the CMC taxonomy + existing ANDA ground truth (what we can measure) and are designed to extend to more families/modules in v2. v1 is a general system whose first *measurable* checks are CMC — not an M3-locked system.

## v1 Requirements

### Ingestion (general corpus intake)

- [ ] **INGEST-01**: System ingests an arbitrary deeply-nested directory of PDF + DOCX documents with no document-count cap, classifying each document by content (never by folder name)
- [ ] **INGEST-02**: System parses DOCX into the same unified structured document model used for PDFs (alongside the existing PDF/OCR path)
- [ ] **INGEST-03**: System builds a per-submission corpus index and a coverage manifest of what the corpus contains

### Rulebook (FDA/ICH retrievable reference)

- [ ] **RULES-01**: System ingests eCFR Title 21 (public-domain XML) as the retrievable rulebook backbone
- [ ] **RULES-02**: System ingests ICH guidelines into the rulebook (storing the required copyright acknowledgment with each chunk)
- [ ] **RULES-03**: System ingests FDA guidances (via regulations.gov) for the topics the eval set exercises
- [ ] **RULES-04**: Every rule chunk is stored with `{source, citation, version/date, license, url}` metadata

### Navigation Tools

- [ ] **TOOLS-01**: Agent has general tools — `search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline` — that return identifiers/snippets, not whole documents (JIT retrieval)
- [ ] **TOOLS-02**: Tools return verbatim span-IDs so a finding's quote is *selected* from the source, never authored by the model (prevents citation drift)

### Agentic Loop

- [ ] **AGENT-01**: Detection runs as a model-driven, model-agnostic tool loop (reviewer requests evidence → reasons → requests more → stops on done/budget), replacing the one-shot pre-rendered call
- [ ] **AGENT-02**: An orchestrator decomposes a review into objectives and fans out isolated sub-agents that each return a distilled, cited finding set
- [ ] **AGENT-03**: Hard per-run budgets and a circuit breaker are enforced in code (stop conditions are code gates, not prompt instructions)

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

- [ ] **COST-01**: A prompt-cache stable prefix + escalating context compaction let one agent reason over a corpus larger than the context window
- [ ] **COST-02**: Cheap-model triage + per-run budget ceilings keep cost scaling with docs that need deep reasoning, not raw corpus size

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

Populated during roadmap creation — each v1 requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| _(to be filled by roadmapper)_ | — | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 24 ⚠️

---
*Requirements defined: 2026-07-30*
*Last updated: 2026-07-30 after initial definition*
