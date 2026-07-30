# Architecture Research

**Domain:** Agentic FDA/ICH compliance reviewer over arbitrary deeply-nested PDF+DOCX corpora (model-driven loop + corpus-navigation tools + retrieval + isolated sub-agents + grounded adversarial verifier + context compaction)
**Researched:** 2026-07-30
**Confidence:** HIGH on the agentic patterns (verified against Anthropic primary sources + the existing codebase); MEDIUM on the reference-graph and guidelines-corpus specifics (fewer authoritative sources, more design latitude)

## The One-Sentence Thesis

**The existing detection topology — `planner → workers → verify → challenge` — is already an orchestrator-worker + evaluator-optimizer shape. The milestone is not a rewrite; it is (a) lifting the substrate from *one parsed document* to *an ingested corpus*, and (b) swapping each *one-shot pre-rendered "sandwich" call* for a *tool-using drive loop*.** Everything below follows from that reframe. The uncommitted `planning.py / summarise.py / sandwich.py / workers.py` redesign is the seam to build on, not clobber.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  L6  GUIDELINES CORPUS (the rulebook — retrievable reference, not oracles) │
│      FDA guidances + ICH guidelines → chunk → embed → guidelines index     │
│                              ▲ read_guideline                              │
├──────────────────────────────────────────────────────────────────────────┤
│  L0  CORPUS INGESTION & INDEX  (foundation — content-driven, no folder cx) │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │  walker  │→│ parse    │→│  content   │→│ corpus     │ │  reference   │  │
│  │ (PDF+DOC)│ │ PDF|DOCX │ │ classifier │ │ index +    │ │  graph       │  │
│  └──────────┘ └──────────┘ └────────────┘ │ vec index  │ │ (xref edges) │  │
│                             (doc model)    └───────────┘ └──────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│  L1  NAVIGATION TOOLS  (the agent's hands — return IDs+snippets, not docs) │
│  search_corpus · open_doc · get_section · follow_reference · read_guideline│
├──────────────────────────────────────────────────────────────────────────┤
│  L3  ORCHESTRATION            L2  DRIVE LOOP (per sub-agent, isolated)      │
│  ┌────────────────┐          ┌───────────────────────────────────────┐    │
│  │ orchestrator   │  spawn   │  think → call tool → observe → decide  │    │
│  │ (reads INDEX,  │─────────▶│  … repeat until done|budget …          │    │
│  │  decomposes,   │  N×      │  → distilled, cited findings (1-2k tok)│    │
│  │  guarantees    │◀─────────│                                        │    │
│  │  coverage)     │  return  └───────────────────────────────────────┘    │
│  └───────┬────────┘                                                        │
│          │ consolidate (dedup + tier)                                      │
│          ▼                                                                  │
│  L4  GROUNDED ADVERSARIAL VERIFIER  (per candidate, isolated, tool-armed)  │
│      re-open source + rule → confirm|refute (evidence-forced verdict)       │
├──────────────────────────────────────────────────────────────────────────┤
│  L5  COST GOVERNOR (cross-cutting): prompt-cache prefix · compaction ·      │
│      cheap-model triage · hard per-run budgets · sub-agent isolation        │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼  FaultReport (existing schema, +doc_id)
                            event_bus / WebSocket → Next.js analyst UI
```

Direction of flow: ingestion builds **static indexes** bottom-up (L0/L6). At review time the orchestrator (L3) reads only the lightweight **index/manifest**, fans out isolated drive-loops (L2) that pull content **just-in-time** through tools (L1), consolidates, then the verifier (L4) re-grounds each survivor. The cost governor (L5) wraps every LLM call.

### Component Responsibilities

| Component | Responsibility (owns) | Typical Implementation |
|-----------|----------------------|------------------------|
| **Corpus walker** | Enumerate every PDF/DOCX under an arbitrary nested root; assign stable content-hash `doc_id`; no cap on count/depth | `os.walk` + suffix filter + `hashlib`; yields `{doc_id, path, ext}` |
| **Parse (PDF)** | One PDF → plain-dict document model (pages→blocks→tables/sections) | **Reuse** `parse/pdf.py` + `ocr.py` + `layout.py` + `section_splitter.py` |
| **Parse (DOCX)** | One DOCX → the **same** document model | **New**: `python-docx`/`mammoth` → converge on `schemas/documents.py` shape |
| **Content classifier** | Label each doc by **content** (module/doc-type), never folder name | **New**: zero-shot LLM over leading text + headings + TOC; cheap model |
| **Corpus index (manifest)** | The navigable map: `{doc_id, path, classification, title, outline[section_ids+headings], page_count}` | **New**: SQLite/JSON manifest; the "lightweight identifier" layer |
| **Corpus vector index** | Semantic retrieval over section chunks of the whole corpus | **Reuse** bge-m3 + FAISS / Databricks Vector Search; **new** index instance |
| **Reference graph** | Edges between doc/section nodes from hyperlinks, "see §X", "Table Y", value cross-refs | **New**: extractor + adjacency store; powers `follow_reference` + cross-doc consistency |
| **Guidelines index** | FDA/ICH rule text, retrievable by topic | **New**: separate ingestion + embed on same vector infra; powers `read_guideline` |
| **Navigation tools** | Deterministic functions the agent calls; token-efficient returns | **New**: `search_corpus / open_doc / get_section / follow_reference / read_guideline` |
| **Drive loop** | One sub-agent's reason→act→observe cycle; grounding discipline; stops on done/budget | **New** loop over **extended** `llm/client.py` (add tool-call turn handling) |
| **Orchestrator** | Read index, decompose review into isolated sub-agent task specs, guarantee coverage | **Evolve** `planning.py` (ReviewPlan → task specs; keep `_ensure_coverage`) |
| **Consolidator** | Collect distilled findings, dedup, tier | **Evolve** `verify.py` (keep anchoring + dedup + tier; key on `doc_id`) |
| **Grounded verifier** | Re-open source + cited rule per candidate; evidence-forced confirm/refute | **Evolve** `challenge.py` (give it tools instead of a pre-rendered excerpt) |
| **Cost governor** | Cache prefix mgmt, compaction trigger, cheap-model triage, budget ceilings | **New** cross-cutting; **reuse** model-picker/dual-serving/config |
| **Eval harness** | Precision/recall vs ground truth; gates every phase | **New**; seed from ANDA data / 500-deficiency KB → `docs/eval/` |

## Recommended Project Structure

```
src/
├── parse/                    # REUSE as-is (PDF) + ADD docx path
│   ├── pdf.py                #   existing PyMuPDF+OCR → doc model
│   ├── docx.py               #   NEW — Word → same doc model
│   └── section_splitter.py   #   existing — physical→logical sections
├── corpus/                   # NEW — L0 ingestion & index
│   ├── walker.py             #   arbitrary nested PDF+DOCX discovery, doc_id
│   ├── classifier.py         #   content-driven doc-type (never folder name)
│   ├── index.py              #   manifest {doc_id, classification, outline...}
│   ├── embed.py              #   chunk+embed → corpus vector index (reuse infra)
│   └── refgraph.py           #   cross-reference edge extraction + store
├── guidelines/               # NEW — L6 rulebook
│   ├── ingest.py             #   FDA/ICH corpus → chunk → embed
│   └── index.py              #   guidelines vector index
├── tools/                    # NEW — L1 the agent's hands
│   ├── search_corpus.py
│   ├── open_doc.py
│   ├── get_section.py
│   ├── follow_reference.py
│   ├── read_guideline.py
│   └── registry.py           #   tool schemas (JSON) for the model + dispatch
├── agents/
│   ├── loop.py               #   NEW — L2 generic drive loop (tool-use turns)
│   └── review/               #   EVOLVE the uncommitted redesign
│       ├── orchestrator.py   #     from planning.py (decompose→task specs)
│       ├── subagent.py       #     from workers.py (one-shot → tool loop)
│       ├── consolidate.py    #     from verify.py (dedup+tier, key on doc_id)
│       ├── verifier.py       #     from challenge.py (tool-armed refute gate)
│       ├── compaction.py     #     from summarise.py/sandwich.py (repurposed)
│       └── deterministic.py  #     DEMOTE oracles.py+checklists.py → seed hints
├── llm/                      # REUSE — client.py (+tool-call loop), structured.py
├── retrieval/                # REUSE — bge-m3, vector_search, precedent KB
├── schemas/                  # REUSE — faults.py, documents.py (+ corpus/tool types)
└── cost/                     # NEW — L5 governor: budgets, cache prefix, triage
```

### Structure Rationale

- **`corpus/` is new and foundational** — it is the substrate swap (one doc → many). Nothing agentic can start until a directory can be walked, parsed, classified by content, and indexed.
- **`tools/` is a hard boundary** — tools are deterministic, side-effect-light functions with JSON schemas. The agent never touches the index, filesystem, or vector store directly; it only calls tools. This is what makes the loop testable and cost-bounded.
- **`agents/review/` mirrors the existing `agents/detection/` file-for-file** so the evolution is legible: each new file has a named ancestor. Keep `agents/detection/` intact until `review/` passes eval, then retire it.
- **`cost/` is separate** because budgets/caching/triage are cross-cutting policy, not business logic — they wrap every call regardless of which agent makes it.

## Architectural Patterns

### Pattern 1: The Drive Loop (replaces the one-shot call)

**What:** A ReAct-style loop — the model receives a task + tool schemas, then repeats `think → call tool → observe result → decide` until it emits a terminal "done" signal or hits a budget ceiling. This is the *primitive* that generalizes to arbitrary corpora, because the model — not a pre-baked slice — chooses what evidence to pull next.

**When to use:** Every sub-agent review task. It is the direct replacement for `workers.py`'s `structured_call` over a fixed `render_sandwich(...)`.

**Trade-offs:** Far more capable and general; ~15× the tokens of a one-shot call ([Anthropic multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system)). Must be budget-bounded or it "scours endlessly / continues when it already had sufficient results" (a documented failure mode).

```python
def drive_loop(task: TaskSpec, tools: ToolRegistry, budget: Budget) -> DistilledFindings:
    messages = [system_prompt(cached=True), user(task.render())]     # stable prefix cached
    for step in range(budget.max_steps):
        resp = chat_with_tools(messages, tools.schemas, model=task.model)
        if resp.tool_calls:
            for call in resp.tool_calls:
                messages.append(tool_result(call, tools.dispatch(call)))  # observation
            continue
        return parse_distilled(resp)          # model chose to stop → cited findings
    return partial(messages)                  # budget hit → return what's grounded so far
```

**Feasibility (verified HIGH):** OpenAI-compatible `tools`/`tool_calls` works on the existing serving stack — Databricks Foundation Model APIs expose function calling for Llama 3.3 70B (128k ctx), and Ollama supports tool calling for Qwen 3/2.5 and Llama 3.x. `llm/client.py` already speaks the OpenAI SDK; it needs a tool-call turn handler, not a new client.

### Pattern 2: Tools Return Identifiers, Not Documents (just-in-time retrieval)

**What:** Tools hand back **lightweight identifiers + snippets**, and only `get_section` returns full (section-bounded) text. The agent navigates a map and pulls content progressively — it never loads the corpus. Anthropic's guidance is explicit: prefer "lightweight identifiers (file paths, stored queries, web links)" over full data objects, mirroring how Claude Code uses `glob`/`grep` instead of ingesting the repo ([context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

**Tool interfaces (recommended):**

| Tool | Signature | Returns | Notes |
|------|-----------|---------|-------|
| `search_corpus` | `(query, filters?, k=8)` | `[{doc_id, section_id, snippet, score}]` | Semantic+keyword over corpus vec index. IDs+snippets only. |
| `open_doc` | `(doc_id)` | `{title, classification, outline:[{section_id, heading}], pages}` | The **outline**, not the text — progressive disclosure. |
| `get_section` | `(doc_id, section_id)` | `{heading, text, tables}` | The *only* heavy return; bounded to one section. |
| `follow_reference` | `(from doc_id/section_id, ref_text)` | `[{doc_id, section_id}]` | Resolves "see §X"/"Table Y"/hyperlink via reference graph. |
| `read_guideline` | `(query \| rule_id, k=5)` | `[{rule_id, text, source}]` | Retrieves FDA/ICH rule text; **separate** index from submissions. |

**When to use:** Always, for corpus > a few docs. **Trade-off:** runtime exploration is slower than pre-computed context, but avoids context pollution and keeps each agent focused ([context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)). **Small-corpus fast path:** for 1–3 tiny docs, the existing sandwich (focus-full + others-summary) can still be cheaper than a loop — keep it as an optional shortcut, not the default.

**Tool-design discipline (from Anthropic):** keep the set **minimal** — "if a human engineer can't say which tool to use, an agent can't either." Five tools is the right order of magnitude; resist bloat.

### Pattern 3: Orchestrator–Worker with Isolated Sub-Agents

**What:** A lead/orchestrator reads only the index, decomposes the review into **self-contained task specs**, and spawns N isolated sub-agents in parallel. Each sub-agent has its **own context window, tools, and trajectory, does not know the others exist, and returns a distilled 1–2k-token cited summary**. The orchestrator synthesizes ([multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system), [context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

**Task spec must contain** (Anthropic: vague specs cause "duplicate work, gaps, or missed information"): `objective · scope/boundaries · output format · tool guidance · budget`.

**Decomposition axes** for this domain: per-document, per-section-cluster, or per-review-theme (e.g. "elemental impurities across the corpus", "stability data consistency", "method validation completeness"). Themes exploit the reference graph for cross-document consistency.

**When to use:** breadth-first review where evidence exceeds one context window and splits into independent strands — exactly this domain. **Trade-off:** not for tightly interdependent reasoning; the 90.2%-over-single-agent result and the 15× token cost both come from isolation.

**Reuse the proven safety net:** `planning.py`'s `_ensure_coverage` (every section owned by ≥1 specialist even if the planner under-assigns) and `workers.py`'s **open-sweep pass** (a planner-independent mechanical sweep of every section) are exactly the guards against Anthropic's "leave gaps" failure — carry them forward verbatim as `orchestrator` invariants over `doc_id × section_id`.

### Pattern 4: Grounded Adversarial Verifier (the precision gate)

**What:** Each survived candidate goes to an isolated verifier sub-agent that must **confirm or refute against the re-opened source**. Unlike today's `challenge.py`, which is *handed* a pre-rendered excerpt, the verifier has tools — it re-opens the cited passage (`get_section`), resolves the cited rule (`read_guideline`), follows references, and returns an **evidence-forced verdict**. A grounded refutation (a verbatim passage that resolves the concern, or an arithmetic recomputation over cited cells) **drops** the finding; anything ungrounded leaves it standing.

**When to use:** every soft (non-deterministic) candidate. Mirrors Anthropic's separate **CitationAgent** pass that verifies "all claims are properly attributed to their sources."

**Reuse the existing gate wholesale:** `challenge.py`'s grounded-refutation logic and the `_arithmetic_refutation` recompute (`parse_limit`/`parse_number`/`satisfies`, both cells must appear verbatim) are the precision counterpart to the oracles and transfer directly — only the *context acquisition* changes from "pre-rendered" to "tool-pulled." Preserve the **recall invariant**: the verifier drops **only** on grounded refutation; it never vetoes on vibes.

### Pattern 5: Reference Graph over Cross-Referencing Documents

**What:** At ingest, extract edges — hyperlinks (PDF/DOCX carry them), textual "see section X", "Table Y", and value cross-references — into a directed graph whose nodes are docs/sections. `follow_reference` traverses it; cross-document consistency checks (spec limits, methods, batch numbers) walk it to compare values at both endpoints.

**When to use:** as soon as fan-out spans multiple documents (Phase D). GraphRAG-style graphs "model cross-document relationships offline, facilitating multi-hop evidence capture within a single retrieval step" ([Graph RAG survey](https://dl.acm.org/doi/10.1145/3777378)).

**Trade-off / recommendation:** **do not** build a full LLM-extracted entity-relation knowledge graph with community summarization first — that is heavyweight and slow to construct. Start with a **lightweight, mostly-deterministic** edge set (hyperlinks + regex "see §"/"Table N" + numeric value matches); this is closer to LightRAG/ephemeral-graph approaches and is enough for `follow_reference` and consistency checks. Escalate to richer graph reasoning only if eval demands it.

### Pattern 6: Context Compaction & Distilled Returns

**What:** Two related moves. (1) **Compaction** — when a sub-agent's loop nears the window, summarize the trajectory (preserve decisions, open questions, cited evidence; discard raw tool outputs) and continue from the summary + the most-recent items. Claude Code compacts to "compressed context plus the five most recently accessed files." (2) **Distilled return** — a sub-agent returns 1–2k tokens of cited findings, never its raw transcript, so orchestrator context stays clean ([context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

**Reuse:** `summarise.py` already *is* a compaction engine — it condenses prose, **carries tables verbatim (never through the model)**, and has a **fidelity guard** that reverts to full prose if any number/named-entity vanished. Repurpose it as the compaction primitive (losing a number is exactly how a cross-section fault goes invisible — the guard already prevents that). The "clear old tool results first" heuristic is the cheapest compaction lever — apply it before summarizing.

### Pattern 7: Cost Governor (makes the loop economically viable)

**What:** Cross-cutting policy wrapping every call: **prompt caching** of a stable prefix (system prompt + tool schemas), **cheap-model triage**, **hard budgets**, and **sub-agent isolation** (one-time exploration cost). Token usage explains ~80% of the variance in multi-agent performance, so managing it *is* managing quality-per-dollar ([multi-agent](https://www.anthropic.com/engineering/multi-agent-research-system)).

- **Prompt caching:** put the cache breakpoint as late as possible in the *stable* content (system + tool JSON schemas), and keep dynamic content (tool results, timestamps) *after* it. 5–10× input-cost reduction on multi-turn loops; naive full-context caching can *increase* latency. **"Don't break the cache"** — a single dynamic byte before the prefix voids it.
- **Cheap-model triage:** a small model runs content classification and a corpus relevance/shortlist pass; escalate to the 70B only for docs/sections that warrant deep reasoning. This is the mechanism behind "cost scales with docs that need deep reasoning, not raw corpus size."
- **Hard budgets:** per-run token + per-agent max-steps ceilings; the loop returns its grounded partial on hit (never a hard crash). Guards Anthropic's "50 subagents for a simple query" failure.

## Data Flow

### Ingestion Flow (build-time, bottom-up, once per corpus)

```
root dir ──walker──▶ [doc_id, path, ext]
                        │
              ┌─────────┴─────────┐
          PDF ▼                   ▼ DOCX
        parse/pdf.py          parse/docx.py
              └─────────┬─────────┘
                        ▼  document model (schemas/documents.py)
                 content classifier (cheap LLM, by content)
                        ▼
        ┌───────────────┼────────────────┐
        ▼               ▼                 ▼
  corpus index    chunk+embed →     refgraph (xref edges)
  (manifest)      corpus vec index
        └───────────────┴────────────────┘  ← the navigable substrate

  (parallel track)  FDA/ICH corpus ──▶ chunk+embed ──▶ guidelines index
```

### Review Flow (run-time, top-down, per submission)

```
orchestrator.read(corpus index)          # reads MANIFEST only, never full docs
      │  decompose → [TaskSpec × N]  (coverage-guaranteed)
      ▼
  sub-agent drive loop × N  (isolated, parallel, budget-bounded)
      │   think ▸ search_corpus / open_doc / get_section /
      │         follow_reference / read_guideline ▸ observe ▸ repeat
      │   (compaction on window pressure)
      ▼   distilled cited findings (1-2k tok each)
  consolidator  → dedup + tier  (evolve verify.py; key on doc_id×section×title)
      ▼   candidate deficiencies
  grounded verifier × M  (isolated, tool-armed)
      │   re-open source + rule ▸ confirm | refute
      ▼   drop ONLY on grounded refutation (recall invariant preserved)
  FaultReport (existing schema + doc_id)  →  event_bus/WebSocket  →  UI
```

Two grounding checkpoints, both mandatory: (1) each finding carries a verbatim quote the sub-agent actually retrieved; (2) the verifier independently re-opens that quote and the cited rule. A finding that survives both is, by construction, "no blabber."

## Reuse vs Replace vs New — against the existing defpredict pipeline

This is the load-bearing deliverable. Verdicts are code-level, from reading the current modules.

### REUSE as-is (do not touch — these are assets)

| Existing | Why it survives the milestone unchanged |
|----------|------------------------------------------|
| `llm/client.py` | OpenAI-compatible chat + retry/backoff/rate-limit handling. Needs a **tool-call turn loop added**, but the transport, client singleton, and resilience are done. |
| `llm/structured.py` | Defense-in-depth structured output (L1 strict schema → truncation retry → json_repair → pydantic → moderator rescue → typed sentinel). Use it for final finding emission and any structured tool return. |
| `schemas/faults.py` | `Fault`/`FaultReport`/`EvidenceClass`/`Tier` — the **output contract and the recall-biased "downgrade-never-drop" invariant hold as-is**. Add a `doc_id` field for corpus provenance. |
| `schemas/documents.py` | The parsed document model. **The DOCX path must converge on this shape** — it is the interop contract between parse and everything above. |
| `parse/pdf.py`, `ocr.py`, `layout.py`, `section_splitter.py` | PDF→doc-model pipeline. Untouched; the corpus walker simply calls it per PDF. |
| `retrieval/` + `databricks/vector.py` | bge-m3 + FAISS/Databricks Vector Search + the 500-row precedent KB. **Same infra hosts the new corpus and guidelines indexes**; precedent retrieval stays as a sub-agent aid. |
| `verify.py` helpers `_norm` / `_doc_corpus` / `_anchored` | Verbatim evidence anchoring — the mechanical core of the grounding guarantee. Generalize the corpus blob from one doc to the retrieved sections. |
| `challenge.py` `_arithmetic_refutation` (+`parse_limit`/`parse_number`/`satisfies`) | Recompute-a-claimed-violation logic. Transfers directly into the new verifier. |
| model picker / dual local+Databricks serving / `config.py` / `event_bus` + WebSocket | Serving, model selection, job store, and streaming. Extend event types for agent steps; otherwise reuse. |

### EVOLVE (build on the uncommitted redesign — the seam)

| From | To | What changes / what is kept |
|------|-----|------------------------------|
| `planning.py` (`ReviewPlan`, `WorkerAssignment`, `_ensure_coverage`, `_sanitize`, `_fallback_plan`) | `orchestrator` | Emits **task specs for tool-using agents over a corpus** instead of section indices for one document. **Keep** the coverage guarantee, index sanitization, and fallback-plan safety net verbatim — they prevent blind spots. |
| `workers.py` (specialist + open-reviewer fan-out, `SuspicionVerdict.deficiency_exists` gate) | `subagent` (drive loop) | One-shot `structured_call` over a rendered sandwich → **tool-using loop**. **Keep** the two-pass idea (themed specialists + planner-independent open sweep) and the "confirmed ≠ deficiency; require `deficiency_exists`" discipline. |
| `verify.py` (`verify_and_tier`, dedup, tiering, self-negation drop) | `consolidator` | **Keep** dedup + evidence-class/tier logic + the code-enforced self-negation filter. Extend the dedup key with `doc_id` for cross-document merges. |
| `challenge.py` (grounded-refutation gate) | `verifier` | Give it **tools** to re-open source/rule instead of a pre-rendered excerpt. **Keep** the gate semantics: drop only on grounded refutation; ungrounded → small confidence bump. |
| `summarise.py` + `sandwich.py` (lossless summariser, fidelity guard, focus-full/context-summary assembly) | `compaction` utilities + small-corpus fast path | Repurpose the summariser as the **compaction primitive** (prose condensed, tables verbatim, number/entity fidelity guard). Keep the sandwich as an optional small-doc shortcut. |

### REPLACE or DEMOTE (do not carry the old assumptions forward)

| Existing behavior | Verdict | Reason |
|-------------------|---------|--------|
| "Load the whole document as a sandwich into one call" as the **primary** context strategy | **Demote to fast-path only** | Fatal at corpus scale; the drive loop + JIT tools is the general path. |
| `oracles.py` + `checklists.py` as a **source of findings** | **Demote to a deterministic seed pass** | PROJECT scopes answer-key oracles out as primary intelligence. Keep them only for stable structural/consistency facts and to **seed suspicions**; do not expand them. |
| `ctd.py` / `detect_ctd_section` as the **only** classifier (CTD number from leading text) | **Replace with content classifier** | Fixed CTD-path assumptions violate the folder-name-agnostic / content-driven requirement. Keep CTD detection as *one input signal* to the new classifier, not the router. |
| `orchestrator.run_pipeline(pdf_path, ...)` (single-PDF entry) | **Replace with corpus entry** | New entry walks a directory; the per-PDF parse it wraps is reused underneath. |

### NEW (net-new, no ancestor)

Corpus walker · DOCX parser · content classifier · corpus index/manifest · corpus vector index · reference graph + `follow_reference` · the five navigation tools + tool registry/dispatch · guidelines corpus ingestion + `read_guideline` + guidelines index · generic drive loop · cost governor (budgets, cache-prefix mgmt, cheap-model triage, compaction trigger) · eval harness.

## Build Order & Dependencies

Ordered to **de-risk the central unknown early** (does an agentic tool loop actually work, grounded, on these models over this corpus?) while respecting the dependency DAG. Each phase is eval-gated.

```
A ─▶ B ─▶ C ─▶ D ─▶ E ─▶ F
             (C is the spike; A,B exist only to feed it)
guidelines corpus: parallel track, must land by end of C
eval harness:      thin slice in A, grows through F
```

| Phase | Delivers | Depends on | Reuse / Evolve |
|-------|----------|------------|----------------|
| **A — Ingestion foundation** | walker + **DOCX parse** (converge on doc model) + content classifier + corpus index/manifest; thin eval harness | Nothing (uses existing PDF parse) | Reuse `parse/*`, `schemas/documents.py`; new `corpus/` |
| **B — Retrieval + tools** | chunk+embed corpus → corpus vec index; `search_corpus` / `open_doc` / `get_section`; tool registry | A | Reuse `retrieval/` infra; new `tools/` |
| **C — The spike: single drive loop** | one tool-using agent that navigates the corpus, gathers evidence, **grounds every finding**, stops on done/budget; guidelines corpus + `read_guideline`; hard budgets | B (+ guidelines track) | Extend `llm/client.py` (tool loop); reuse `structured.py`, faults schema, anchoring |
| **D — Scale out** | orchestrator decomposition + **isolated sub-agent fan-out** + consolidator (dedup/tier); reference graph + `follow_reference`; cross-document consistency | C | Evolve `planning.py`→orchestrator, `verify.py`→consolidator; new `refgraph` |
| **E — Precision** | **grounded adversarial verifier** (tool-armed confirm/refute) | D | Evolve `challenge.py`→verifier; reuse arithmetic refutation |
| **F — Economics** | cost governor hardening: prompt-cache prefix, compaction, cheap-model triage, budget tuning; full eval gate | C–E | Reuse model picker; evolve `summarise.py`→compaction |

**Critical-path notes:**
- **DOCX must land in A** — the corpus is PDF+DOCX; the loop cannot be validated on a partial corpus.
- **C is the go/no-go phase.** If the tool loop can't ground reliably on Llama/Qwen here, D–F are moot. Keep it a *single* agent to isolate the risk before multiplying cost by N.
- **`read_guideline` gates grounding** (findings must cite a rule), so the guidelines track must finish by end of C — run it in parallel with A/B since it's an independent ingestion.
- **`follow_reference` / reference graph is Phase D**, not C — cross-document navigation only matters once fan-out spans documents. Don't block the spike on it.
- **Budgets appear in C** (as a guardrail so the spike can't run away); the *full* governor hardens in F.
- **Eval harness is not a final phase** — a thin precision/recall slice must exist by C to measure the loop; it grows into the gate by F.

## Scaling Considerations

Scale here is **corpus size**, not user count. The governing principle (PROJECT): *cost should scale with docs that need deep reasoning, not raw corpus size.*

| Corpus scale | Architecture posture |
|--------------|----------------------|
| **1–10 docs** | Drive loop is fine; the sandwich fast-path may be *cheaper* for tiny docs — offer it as a shortcut. Reference graph optional. |
| **10–100 docs** | Full orchestrator + fan-out + reference graph. Prompt caching and distilled returns start to matter. Compaction rarely triggers. |
| **100–1000+ docs (real target)** | **Cheap-model triage is mandatory** — shortlist the docs/sections worth 70B deep review; do not fan out over everything. Budgets, caching, and compaction are load-bearing, not optional. The reference graph prevents re-deriving cross-doc relationships per agent. |

### Scaling Priorities

1. **First bottleneck: token cost of indiscriminate fan-out.** Fix with cheap-model triage + hard budgets before adding agents. (Anthropic: "50 subagents for a simple query.")
2. **Second bottleneck: broken prompt cache.** A dynamic byte before the stable prefix silently voids the 5–10× saving. Fix with disciplined cache-prefix boundaries.
3. **Third bottleneck: context-window pressure in deep loops.** Fix with compaction (clear tool results → summarize with fidelity guard) before it degrades reasoning.

## Anti-Patterns

### Anti-Pattern 1: Context stuffing (load the corpus/doc into the window)
**What people do:** Render everything into one prompt — the current sandwich, scaled up. **Why it's wrong:** impossible past a few docs; degrades reasoning even when it fits ("more tokens makes agents worse"). **Instead:** JIT retrieval — tools return IDs+snippets; only `get_section` returns bounded full text.

### Anti-Pattern 2: Folder-name / fixed-CTD-path routing
**What people do:** Infer document meaning from folder names or hardcoded "M3 / 3.2.S.4.1" paths. **Why it's wrong:** folders are named anything and nested arbitrarily; PROJECT scopes this out. **Instead:** content-driven classification; treat any path/CTD signal as one hint, never the router.

### Anti-Pattern 3: Oracles as the source of intelligence
**What people do:** Grow the deterministic checklist/oracle battery to "catch more." **Why it's wrong:** answer-keys don't generalize to new submissions. **Instead:** guidelines-as-retrievable-reference + model reasoning; keep deterministic checks only for stable structural facts and to seed suspicions.

### Anti-Pattern 4: Ungrounded findings ("blabber")
**What people do:** Let the model assert a deficiency it can't quote. **Why it's wrong:** confident hallucination destroys precision — the whole point. **Instead:** mandatory verbatim anchor at emission + independent re-grounding by the adversarial verifier.

### Anti-Pattern 5: The unbounded loop
**What people do:** Let the agent run until it "feels done." **Why it's wrong:** cost blowup; "scouring endlessly / continuing when it already had enough." **Instead:** hard max-steps/token budgets + explicit done signal + coverage-not-exhaustion; return the grounded partial on budget hit.

### Anti-Pattern 6: Chatty sub-agents
**What people do:** Return raw tool transcripts to the orchestrator. **Why it's wrong:** pollutes orchestrator context, erasing the isolation benefit. **Instead:** distilled 1–2k-token cited returns; keep detailed context inside the sub-agent.

### Anti-Pattern 7: Breaking the cache
**What people do:** Put timestamps/tool results/dynamic IDs before the stable prefix. **Why it's wrong:** voids prompt caching — silently pays full price. **Instead:** stable cached prefix (system + tool schemas) first, dynamic content strictly after the breakpoint.

### Anti-Pattern 8: Over-decomposition
**What people do:** Spawn a sub-agent per document regardless of corpus size. **Why it's wrong:** linear cost in corpus size, defeating the "deep reasoning only where needed" principle. **Instead:** triage first, fan out over what warrants it; scale effort to complexity.

### Anti-Pattern 9: A vetoing verifier
**What people do:** Let the verifier drop findings on judgment. **Why it's wrong:** kills the recall-biased invariant. **Instead:** drop **only** on grounded refutation (verbatim resolving passage or arithmetic recompute); everything else survives, tiered.

## Integration Points

### External Services

| Service | Integration Pattern | Notes / gotchas |
|---------|---------------------|-----------------|
| LLM serving (Databricks FM APIs / Ollama) | OpenAI-compatible `tools`/`tool_calls` | **Verified available** for Llama 3.3 70B (Databricks, 128k ctx) and Qwen 3/2.5 + Llama 3.x (Ollama). Validate tool-call reliability + JSON-arg fidelity per model in Phase C; keep `structured.py` as the fallback for malformed tool args. |
| Vector search (FAISS / Databricks Vector Search) | Reuse `databricks/vector.py` + bge-m3 | Add two index instances (corpus, guidelines) alongside the precedent KB. Watch index-refresh cost on large corpora. |
| FDA/ICH open corpus | Batch ingest → chunk → embed | **External dependency to source** (ICH publishes guidelines; FDA guidances are public). Licensing/format vary — treat sourcing as its own de-risking task in the guidelines track. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| parse (PDF+DOCX) ↔ everything above | plain-dict **document model** | The interop contract. DOCX must converge on `schemas/documents.py` or the whole stack forks. |
| agent ↔ world | **tools only** (JSON schema in, IDs/snippets out) | The agent never touches index/FS/vector store directly — this is what keeps the loop testable and cost-bounded. |
| orchestrator ↔ sub-agents | self-contained TaskSpec down, distilled findings up | No shared mutable state; isolation is the design. |
| review layer ↔ UI | `FaultReport` + `event_bus`/WebSocket | Existing contract; extend event types for agent steps (tool calls, budgets). |

## Sources

- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — compaction, note-taking/external memory, sub-agent isolation (1–2k-token distilled returns), tool design (minimal set, return identifiers), just-in-time retrieval. **HIGH**
- [Anthropic — Building a multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — orchestrator-worker, task-spec contents, CitationAgent verification pass, 3–5 (→10+) subagents, effort scaling, 15× token cost, 90.2% over single-agent, long-run failure modes/checkpoints. **HIGH**
- [Anthropic — Building effective agents](https://www.anthropic.com/research/building-effective-agents) — orchestrator-workers vs parallelization, evaluator-optimizer patterns. **HIGH**
- [Databricks — Function calling (Foundation Model APIs)](https://docs.databricks.com/aws/en/machine-learning/model-serving/function-calling) + [Llama 3.3 on Databricks](https://www.databricks.com/blog/making-ai-more-accessible-80-cost-savings-meta-llama-33-databricks) — OpenAI-compatible tool calling, Llama 3.3 70B 128k ctx. **HIGH**
- [Ollama — Tool calling](https://docs.ollama.com/capabilities/tool-calling) — Qwen 3/2.5 + Llama 3.x tool support. **HIGH**
- [ACM — Graph Retrieval-Augmented Generation: A Survey](https://dl.acm.org/doi/10.1145/3777378) + [HopRAG](https://arxiv.org/html/2502.12442) — cross-document graphs, multi-hop retrieval; motivates a *lightweight* reference graph over full GraphRAG. **MEDIUM**
- [arXiv — Don't Break the Cache: Prompt Caching for Long-Horizon Agentic Tasks](https://arxiv.org/pdf/2601.06007) + practitioner guides — cache stable prefix, exclude dynamic tool results, 5–10× multi-turn saving. **MEDIUM**
- [Towards Data Science — Agentic RAG: Let the Agent Search](https://towardsdatascience.com/agentic-rag-let-the-agent-search/) — ReAct retrieve/act/observe loop, search-open-read-verify, self-evaluation before answering. **MEDIUM**
- Existing codebase (read this session): `agents/orchestrator.py`, `agents/detection/{pipeline,planning,workers,summarise,sandwich,verify,challenge}.py`, `llm/{client,structured}.py`, `schemas/{faults,documents}.py`, `retrieval/knowledge_base.py`, `.planning/PROJECT.md`. **HIGH** (primary source for reuse-vs-replace).

---
*Architecture research for: agentic FDA/ICH compliance reviewer over PDF+DOCX corpora*
*Researched: 2026-07-30*
