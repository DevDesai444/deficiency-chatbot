# Stack Research — Agentic FDA/ICH Compliance Reviewer (new milestone)

**Domain:** Agentic, tool-using document-review / RAG over large heterogeneous (PDF + DOCX) drug-submission corpora, with FDA + ICH rules as retrievable reference
**Researched:** 2026-07-30
**Confidence:** HIGH on library versions (live PyPI/npm) and rules-source licensing (official docs); MEDIUM on the "one right" agent-framework choice (a judgment call, laid out with criteria)

> **Scope note (subsequent milestone).** This does **not** re-research the existing, working stack: PyMuPDF PDF/OCR parse, pydantic v2, `json-repair`, the `structured.py` output pipeline, FAISS + `bge-m3`, FastAPI/WebSocket, Databricks/Ollama serving. Those are assets to build **on**. This document covers only what is **new** for the agentic, multi-document, FDA/ICH-compliance capability, and flags the few existing choices that should change.
>
> **Read this first — the SDK reality.** The system serves **OpenAI-compatible** models (Ollama + Databricks: Llama 3.3 70B, Qwen MoE) through the `openai` client. **The Anthropic Python SDK / Claude Agent SDK talk only to Claude** (Anthropic API, Bedrock, Vertex) — they cannot drive Llama/Qwen. So "use the Anthropic SDK" is only actionable if you add Claude access for the orchestrator. The primary recommendation below is therefore an OpenAI-compatible, **model-agnostic** loop, with a clearly-scoped "if you add Claude" variant. The Claude Code *patterns* (caching, compaction, sub-agents) are what you port — not necessarily the SDK.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Build-your-own tool loop on `openai`** | `openai` **2.50.0** (repo pins 1.40 — upgrade) | The agentic drive-loop: model requests evidence via tools, reasons, requests more, decides when done | You already own the hard parts (grounding, verification, compaction, budgets) in `structured.py`/`planning.py`/`workers.py`. Those are exactly what no framework does well for you. A thin hand-rolled loop over Chat Completions `tools=` keeps full control and stays model-agnostic across Ollama/Databricks. Aligns with the project's explicit "study Claude Code, build the loop" thesis. **HIGH** |
| **PydanticAI** (typed tool/agent layer) | **2.21.0** (v1.0 shipped Sep 2025; now v2) | Optional but recommended layer for typed tools + typed outputs + tool-call routing + usage limits, over the *same* OpenAI-compatible endpoints | Reuses your pydantic v2 investment: tool args and final outputs are validated against pydantic models automatically, which is exactly where heterogeneous local models (Llama/Qwen) misbehave. Model-agnostic — `OpenAIChatModel` + `OpenAIProvider(base_url=…)` points at Ollama/Databricks today and swaps to Claude by changing one string. Native MCP + Logfire. **HIGH** it works with your endpoints; **MEDIUM** on adopting it vs. pure hand-roll (decision criteria below) |
| **eCFR API — Title 21 (21 CFR)** | REST `versioner/v1` + GovInfo bulk XML | THE binding FDA rules as machine-readable reference (cGMP 21 CFR 210/211, NDA/ANDA 314, BA/BE 320, biologics 600/601) | **Public domain** (US Government work — no copyright). Clean XML with full CFR hierarchy → chunk by citation (`21 CFR 211.166`). This is the single best, most authoritative, most machine-consumable rules source and it is free. **HIGH** |
| **ICH guideline corpus** | PDFs at `database.ich.org` | The ICH Q/S/E/M guidelines (Q1 stability, Q2 validation, Q3 impurities, Q6 specs, Q8–Q12, etc.) as reference | The other half of "the rulebook." **Public license**: may be reproduced/adapted/redistributed *provided ICH copyright is acknowledged*. Delivered as PDFs → run through your existing PDF pipeline. **HIGH** on availability, **MEDIUM** on exact license wording (verify the notice text) |
| **LanceDB** (reference-corpus store) | **0.36.0** | Persistent, embedded vector+FTS store for the FDA/ICH **reference** corpus with hybrid search, metadata filtering, reranking | Embedded (no server), on-disk, columnar. Native **hybrid** BM25 (Tantivy) + dense vector in one query, metadata filters (part/section/source), and built-in reranking (RRF default; cross-encoder pluggable). Right tool for a rules corpus you build once and query constantly. Keep FAISS for the ephemeral per-submission index. **HIGH** |
| **`bge-reranker-v2-m3`** (via `FlagEmbedding` **1.4.0** or `sentence-transformers` **5.6.1** CrossEncoder) | model card `BAAI/bge-reranker-v2-m3` | Precision reranking after hybrid retrieval | 568M cross-encoder built on the **same `bge-m3`** you already embed with — natural pairing, no new embedding model, multilingual, 512-token pairs. Retrieve wide (BM25+dense) → rerank to a tight, high-precision top-k before it hits the LLM. Directly supports the "no-blabber" precision goal. **HIGH** |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **python-docx** | **1.2.0** (repo pins 1.1 — bump) | DOCX → your unified structured model | **Primary DOCX path (MVP).** Already a dependency. Lightweight, no ML deps; map paragraphs/tables/headings to the same dict model your PyMuPDF pipeline emits. Best when you want control and architectural symmetry with the existing parser. |
| **Docling** (+ `docling-core`) | **2.116.0** / **2.88.0** | Unified PDF **and** DOCX/PPTX/XLSX/HTML → one `DoclingDocument` (layout, reading order, tables) + built-in chunkers | **Upgrade path / evaluate**, if `python-docx` table & layout fidelity proves insufficient, or you want *one* parser for all formats with better tables. Heavier (pulls Torch + layout models). Can coexist: use for DOCX + hard PDFs, keep PyMuPDF for the digital-PDF fast path. |
| **PyMuPDF4LLM** | **1.28.0** | Markdown/chunk export from your existing PyMuPDF PDFs | Cheap add-on to your current PDF stack when you want LLM-ready markdown/chunks without adopting Docling. |
| **rank-bm25** | **0.2.2** | Lexical BM25 for the **ephemeral per-submission** corpus (exact IDs, batch numbers, spec values) | When you don't want to stand up LanceDB FTS for a transient run. Pairs with FAISS for a lightweight hybrid over one submission. (If you standardize on LanceDB, its Tantivy FTS supersedes this.) |
| **outlines** / **xgrammar** | **1.3.2** / **0.2.5** | Grammar-constrained decoding to *guarantee* JSON/enum tool-args from weaker local models | Belt-and-suspenders for tool-calls on Llama/Qwen. Prefer server-side: **vLLM/Databricks guided decoding** and **Ollama `format`/JSON-schema** use these engines under the hood. Complements (does not replace) your `json-repair` fallback. |
| **instructor** | **1.15.4** | Pydantic-validated structured extraction with auto-retry over the OpenAI client | Only if you want a turnkey structured-output helper. You already have a hardened `structured.py` — treat this as a reference/alternative, not a rewrite. |
| **regulations.gov API v4 client** (`httpx`) | API v4 | Machine-readable FDA **guidance** metadata + attachment PDFs (free `api.data.gov` key) | The programmatic route to FDA guidances (which are *not* in openFDA). Query `documents`/`dockets` → download PDF attachments → parse. |
| **openFDA bulk / API** (`httpx`) | drug label (SPL), Drugs@FDA, Orange Book, NDC | Complementary **structured drug reference** (approved labeling, application status), not rules | **CC0 1.0 / public domain**, JSON bulk + API. Use for cross-checks (e.g., proposed labeling vs. approved SPL), not as the guidance source. |
| **Ragas** | **0.4.3** | RAG-specific metrics (faithfulness, context precision/recall, answer relevance) | Continuous retrieval-quality dashboards for the reference-lookup layer. |
| **DeepEval** | **4.x** (`4.1.4`) | pytest-style LLM/agent eval, custom metrics, CI gates | Your primary harness for **precision/recall vs. ground-truth deficiencies** — custom metrics + CI/CD gating fit the "eval gates everything" decision. |
| **promptfoo** (npm) | **0.121.19** | Red-team / adversarial + multi-model matrix eval (YAML) | Guard the "no hallucinated blabber" contract; regression-test prompts across Llama/Qwen/(Claude). |
| **structlog** | (already present) | Structured run/telemetry logs incl. token & cost accounting | Extend for per-run budget ceilings and cache-hit metrics. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **Logfire** (PydanticAI-native) or OpenTelemetry | Agent-loop tracing: tool calls, token spend, cache hits, sub-agent fan-out | If you adopt PydanticAI, Logfire is one line. Otherwise emit OTel spans from the loop. Essential for cost control at corpus scale. |
| **DeepEval + pytest** | Eval-in-CI gate on the branch | `asyncio_mode=auto` already set; add an `evals/` suite seeded from ANDA/500-deficiency KB. |
| **uv / pip-tools** | Lock the new deps reproducibly | Pin Torch-heavy extras (Docling, rerankers) in an optional group to keep the base image lean. |

---

## Installation

```bash
# --- Agent loop + typed tools (model-agnostic over your OpenAI-compatible endpoints) ---
pip install -U "openai>=2.50" "pydantic-ai>=2.21"          # bump openai from 1.40; pydantic-ai optional-but-recommended

# --- DOCX (MVP path) + optional unified parser upgrade ---
pip install -U "python-docx>=1.2" "pymupdf4llm>=1.28"
pip install "docling>=2.116"                                # optional: unified PDF+DOCX parser (pulls Torch)

# --- Retrieval at scale: reference-corpus store + reranking ---
pip install -U "lancedb>=0.36" "FlagEmbedding>=1.4"         # bge-reranker-v2-m3 pairs with your existing bge-m3
pip install "rank-bm25>=0.2.2"                              # lightweight lexical for the ephemeral per-run index

# --- Constrained decoding for reliable tool-args on local models (optional) ---
pip install "outlines>=1.3" "xgrammar>=0.2.5"

# --- Rules ingestion clients (stdlib httpx already present) ---
#   eCFR:            GET https://www.ecfr.gov/api/versioner/v1/full/{YYYY-MM-DD}/title-21.xml   (public domain)
#   eCFR structure:  GET https://www.ecfr.gov/api/versioner/v1/structure/{YYYY-MM-DD}/title-21.json
#   eCFR bulk:       https://www.govinfo.gov/bulkdata/ECFR/title-21   (XML)
#   FDA guidance:    https://api.regulations.gov/v4/documents?...&api_key=KEY  (+ attachment PDFs)  free key: api.data.gov
#   openFDA (CC0):   https://api.fda.gov/drug/label.json  |  bulk: https://download.open.fda.gov/...
#   ICH (pub. lic.): https://database.ich.org/sites/default/files/<GUIDELINE>.pdf

# --- Eval ---
pip install -U "deepeval>=4.1" "ragas>=0.4.3"
npm install -g promptfoo@0.121                              # or: npx promptfoo@latest

# --- Remove dead weight (see "What NOT to Use") ---
# pip uninstall autogen-agentchat autogen-ext                # AutoGen design was removed per PROJECT.md
```

> Versions are live from PyPI/npm on 2026-07-30. `pydantic` itself is at **2.13.4** (you're `>=2.7`, compatible).

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Build-your-own loop on `openai` (+ optional PydanticAI) | **Claude Agent SDK** (`claude-agent-sdk`, MIT) | You add Claude for the orchestrator and want its exact agent-loop machinery (tool exec, context mgmt, sub-agents, permissions) for free. Trade-off: **locks the orchestrator to Anthropic models** and to Anthropic-style prompt caching. Strong fit given the team's Claude Code study — worth a *scoped spike* for the orchestrator only, with cheap local models still doing worker/triage. |
| Build-your-own loop (+ PydanticAI) | **LangGraph 1.2.10** | You need **durable, resumable, human-in-the-loop** orchestration as an explicit state machine (checkpointing, replay) for very long corpus runs. Mature, used in production at scale. Cost: heavy abstractions that will fight your bespoke grounding/compaction. Consider only for the outer orchestrator if runs must survive process restarts. |
| PydanticAI as typed layer | **instructor** | You want *only* structured extraction (no agent/tool orchestration) with minimal surface area. |
| LanceDB (reference corpus) | **Qdrant 1.18** / **pgvector** | You need a networked, multi-tenant server or you already run Postgres. Qdrant is excellent for large shared indexes; overkill for an embedded, per-project reference store. Keep **FAISS** for the transient per-submission index (already integrated). |
| `python-docx` (MVP) → Docling (upgrade) | **unstructured** | You need its many-format connectors *and* accept the trade-offs below — generally **not** recommended (see What NOT to Use). |
| eCFR + ICH + regulations.gov | **Commercial regulatory feeds** (e.g., vendor APIs) | You need curated, cross-linked, versioned regulatory intelligence and can pay/license. Out of scope for an "open-source corpus" milestone. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **AutoGen** (`autogen-agentchat`, `autogen-ext`) | The 3-layer AutoGen design was **removed**; still in `pyproject.toml` as dead weight. Heavy, opinionated multi-agent abstractions that fight a grounded, cost-controlled loop. | Your own loop on `openai` (+ optional PydanticAI). Delete the deps. |
| **Anthropic SDK as the *only* client** | It cannot drive your Ollama/Databricks Llama/Qwen endpoints. Adopting it wholesale strands your existing serving + model-picker. | Model-agnostic OpenAI-compatible loop; add the Anthropic/Claude Agent SDK **only** for a Claude orchestrator variant. |
| **LangChain (core abstractions) as the framework** | Abstraction sprawl over retrievers/chains obscures the grounding + verification logic that is your whole moat; version churn. | Thin hand-rolled loop; borrow patterns, not the framework. LangGraph (not LangChain) only if you truly need durable state machines. |
| **`unstructured` as the parser** | Advanced features are being steered to its **paid API**; open-source parse quality reportedly regressed; heavy dependency tree. | `python-docx` (MVP) + **Docling** (unified upgrade) + your existing PyMuPDF. |
| **openFDA for the *rules*** | openFDA has drug **labels/NDC/Drugs@FDA/Orange Book/enforcement** — **no guidance-document dataset** and no CFR. Treating it as the rulebook is a dead end. | **eCFR Title 21** (binding rules) + **regulations.gov / FDA site** (guidances) + **ICH** (guidelines). Use openFDA only as complementary structured reference. |
| **Replacing `structured.py` wholesale** | It's a hardened asset (schema → truncation retry → `json_repair` → validate → moderator rescue → typed `ParseFailed`). | Keep it; layer typed tool-args (PydanticAI) and optional constrained decoding on top. |
| **Scraping ICH without the copyright notice** | ICH content is copyrighted; the public license requires **acknowledging ICH copyright**. | Store the attribution with each ICH chunk; surface it in citations. |

---

## Stack Patterns by Variant

**If serving stays fully local/OSS (Ollama + Databricks Llama/Qwen):**
- Loop = `openai` client (+ PydanticAI), tools = your `search_corpus`/`open_doc`/`get_section`/`follow_reference`/`read_guideline`.
- Reliability = server-side **guided decoding** (vLLM/Databricks) or Ollama `format`/JSON-schema for tool-args; `json-repair` as fallback.
- Cost = **server-side automatic prefix caching** (vLLM/Databricks APC; Ollama KV reuse) with a *stable cached prefix* (system + tool schemas + guideline preamble). Note: prefix caching is provider-side and **not** the same API as Anthropic `cache_control`.

**If you add Claude for the orchestrator (recommended spike):**
- Orchestrator/verifier on Claude via **Anthropic SDK 0.120.2** (or **Claude Agent SDK**), with explicit **`cache_control` breakpoints** on the stable prefix (≈10% input cost on cache hits) — the caching lever the project's cost model assumes.
- Keep **cheap local models** for worker fan-out and triage; escalate to Claude only for hard reasoning/verification. This is the cost-optimal split.
- PydanticAI makes this a per-agent model-string swap; a raw loop needs a small client abstraction over both SDKs.

**If DOCX/table fidelity is the bottleneck:**
- Promote **Docling** to the unified parser for DOCX + complex PDFs; keep PyMuPDF for the digital-PDF fast path. Converge both on your existing dict model via a Docling→model adapter.
- Watch for legacy **`.doc`** (binary): `python-docx` and Docling handle `.docx` only — pre-convert `.doc` with headless **LibreOffice** (`soffice --convert-to docx`).

**If the reference corpus grows / is shared across runs:**
- LanceDB scales on-disk with bitmap metadata indices; if you need a networked multi-tenant server, graduate the reference corpus to **Qdrant**. Per-submission ephemeral index stays on **FAISS**.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `openai` 2.50.0 | `pydantic` 2.13.x, Python 3.11 | Major bump from repo's 1.40 — v2 changed some client internals; smoke-test `structured.py`'s client calls. |
| `pydantic-ai` 2.21.0 | `pydantic` 2.x, `openai` 2.x, Python ≥3.10 | `OpenAIChatModel` + `OpenAIProvider(base_url=…)` targets Ollama/Databricks; swap `model=` for Claude. |
| `docling` 2.116.0 | `docling-core` 2.88.0, Torch ≥2.x, Python ≥3.10,<4.0 | Heavy (layout models). Isolate in an optional dependency group; can conflict with `finetune` group's Torch pin — align versions. |
| `lancedb` 0.36.0 | `tantivy` 0.26 (FTS), pyarrow | Embedded; hybrid FTS+vector + RRF/cross-encoder rerank built in. |
| `FlagEmbedding` 1.4.0 / `sentence-transformers` 5.6.1 | `bge-m3`, `bge-reranker-v2-m3` | Reranker shares the `bge-m3` lineage you already embed with — no new base model. |
| `anthropic` 0.120.2 (if added) | Python ≥3.9; `anthropic[bedrock]`/`[vertex]` for those routes | Only reaches Claude models — additive to, not a replacement for, the OpenAI-compatible path. |
| `autogen-*` | — | **Remove**; dead per PROJECT.md. |

---

## FDA / ICH Rules Sources — the retrievable rulebook (most important)

Legend: **Open?** = free & redistributable · **Machine-readable?** = structured vs. PDF-only · **Ingest** = how to pull it.

| Source | What it is | Open / License | Machine-readable? | Ingest | Confidence |
|--------|-----------|----------------|-------------------|--------|-----------|
| **eCFR — Title 21 (21 CFR)** | The **binding** FDA regulations: 210/211 (cGMP), 314 (NDA/ANDA), 320 (BA/BE), 600/601 (biologics), 11 (e-records) | **Public domain** (US Gov work; "no restrictions on re-use… not subject to copyright") | **Yes — clean XML + REST API** | REST: `GET /api/versioner/v1/full/{date}/title-21.xml`; hierarchy: `/api/versioner/v1/structure/{date}/title-21.json`; bulk: `govinfo.gov/bulkdata/ECFR/title-21`. Chunk by section → key each chunk by citation (`21 CFR 211.166`). | **HIGH** |
| **ICH Guidelines (Q/S/E/M)** | The core quality/safety/efficacy guidance the reviewer reasons against (Q1 stability, Q2 validation, Q3A–D impurities, Q6A specs, Q8–Q12, etc.) | **Public license** — "may be used, reproduced, incorporated…, adapted, modified, translated or distributed under a public license **provided ICH's copyright… is acknowledged**" | **PDF only** → parse | Enumerate from ICH topic pages (Quality/Safety/Efficacy/Multidisciplinary); PDFs live at `https://database.ich.org/sites/default/files/<name>.pdf`. Run through your PDF pipeline; store ICH copyright line with each chunk. | **HIGH** availability / **MEDIUM** exact license text (verify notice) |
| **FDA Guidance Documents** | FDA's *current thinking* guidances (CMC, stability, impurities, dissolution, ANDA submission, etc.) — non-binding but what reviewers cite | **US Gov work → public-domain content**, delivered as PDFs; **no official bulk dump** | **Semi** — metadata via API, body is PDF | Programmatic: **regulations.gov API v4** (`/v4/documents`, `/v4/dockets`, free `api.data.gov` key) → JSON metadata + downloadable **attachment PDFs**. Fallback: scrape the FDA guidance search table + `fda.gov/media/{id}/download`. | **HIGH** (route) / **MEDIUM** (completeness of any single query) |
| **openFDA** (complementary, *not* rules) | Drug **labeling (SPL)**, Drugs@FDA, Orange Book, NDC, enforcement | **CC0 1.0 Universal** (public domain; attribution requested, not required) | **Yes — JSON API + bulk zips** | API `https://api.fda.gov/drug/label.json`; bulk `download.open.fda.gov`. Use for cross-checks (proposed vs. approved labeling, application status) — **not** as the guidance corpus. | **HIGH** |

**Recommended rulebook build order:** (1) **eCFR Title 21** — highest authority, cleanest ingest, zero license friction → the backbone. (2) **ICH Q-series** — the CMC/quality reasoning your Module-3 use case leans on. (3) **FDA guidances** via regulations.gov for the specific topics your evals exercise (stability, impurities, dissolution, method validation, ANDA). (4) **openFDA** only where a structured cross-check adds precision. Store every rule chunk with `{source, citation, version/date, license, url}` so each finding cites **submission passage → rule** and passes the grounding contract.

**Ingestion notes:**
- eCFR XML is versioned by date — pin an ingest date so citations are reproducible; re-pull on a schedule to catch amendments.
- ICH and FDA guidances are PDFs — reuse the existing PyMuPDF (or Docling) parser; keep section anchors so `follow_reference`/`read_guideline` can re-open exact passages.
- regulations.gov v4 is rate-limited per API key — cache aggressively; you're building a corpus once, not querying live per run.

---

## Sources

- **PyPI JSON API** (live, 2026-07-30) — authoritative current versions: `openai` 2.50.0, `pydantic-ai` 2.21.0, `anthropic` 0.120.2, `langgraph` 1.2.10, `docling` 2.116.0 / `docling-core` 2.88.0, `lancedb` 0.36.0, `FlagEmbedding` 1.4.0, `sentence-transformers` 5.6.1, `ragas` 0.4.3, `deepeval` 4.1.4, `rank-bm25` 0.2.2, `python-docx` 1.2.0, `pymupdf4llm` 1.28.0, `outlines` 1.3.2, `xgrammar` 0.2.5, `instructor` 1.15.4, `pydantic` 2.13.4; npm `promptfoo` 0.121.19 — **HIGH**
- **Context7** (`/pydantic/pydantic-ai`, `/ds4sd/docling`, `/vibrantlabsai/ragas`, `/confident-ai/deepeval`) — library identity, version lineage (PydanticAI v0→v1→v2), capabilities — **HIGH**
- **eCFR Developer Resources / GovInfo `usgpo/bulk-data` ECFR guide** — Title 21 XML bulk + `versioner/v1` REST endpoints; **public-domain** confirmation ("U.S. Government works are not subject to copyright") — **HIGH**
- **open.fda.gov/license & /data/downloads** — **CC0 1.0** dedication; drug label/NDC/Drugs@FDA/Orange Book datasets; **no guidance dataset** — **HIGH**
- **regulations.gov API v4 (open.gsa.gov)** — `/v4/{documents,dockets,comments}` JSON, free key, FDA guidance dockets + PDF attachments — **HIGH**
- **ICH documents on `database.ich.org`** (E6_R2_Addendum, S12, E19, Q11 deck) — verbatim public-license notice ("…adapted, modified, translated or distributed under a public license provided ICH's copyright… is acknowledged") — **MEDIUM-HIGH** (verify canonical wording on the current legal-notice page)
- **Anthropic — "Effective context engineering for AI agents"** — compaction (budget-reduce → snip → microcompact → collapse → auto-compact) and **just-in-time retrieval** (pull by identifier/query, don't preload) — validates the tool-based navigation design — **HIGH**
- **Anthropic prompt-caching docs / write-ups** — `cache_control` prefix caching (~10% input cost on hits); note this is Claude-specific vs. vLLM/Ollama automatic prefix caching — **MEDIUM**
- **LanceDB docs (hybrid search, rerankers)** — native BM25 (Tantivy) + vector + RRF/cross-encoder rerank + metadata filters, embedded/on-disk — **HIGH**
- **BAAI `bge-reranker-v2-m3` model card / reviews** — 568M cross-encoder on `bge-m3`, pairs with existing embeddings — **HIGH**
- **PydanticAI docs (OpenAI/Ollama providers)** — `OpenAIChatModel` + `OpenAIProvider(base_url=…)` drives Ollama/OpenAI-compatible endpoints; typed tools + structured output — **HIGH**
- **2025–2026 parser comparisons (LlamaIndex insights, link.sc, Docling arXiv 2501.17887)** — Docling strong for structured RAG output; `unstructured` steering to paid API / quality regressions — **MEDIUM**
- **2025–2026 eval-framework comparisons (DeepEval, Braintrust, genai.qa)** — Ragas = RAG metrics, DeepEval = broad + CI, promptfoo = red-team/multi-model — **MEDIUM**

---
*Stack research for: agentic FDA/ICH regulatory-compliance reviewer over PDF+DOCX corpora (subsequent milestone; builds on existing PyMuPDF/pydantic/FAISS/FastAPI system)*
*Researched: 2026-07-30*
