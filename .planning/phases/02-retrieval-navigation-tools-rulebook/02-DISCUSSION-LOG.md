# Phase 2: Retrieval, Navigation Tools & Rulebook - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-31
**Phase:** 2-retrieval-navigation-tools-rulebook
**Areas discussed:** Rulebook scope & sourcing, Requirement index (RULES-05), emit_finding gate
**Areas locked without debate:** follow_reference (user pre-locked the Phase-2 contract when selecting areas)

---

## Area selection

Presented 4 candidate gray areas (Rulebook scope & sourcing, Requirement index, follow_reference scope, emit_finding gate). User selected three to discuss and **pre-locked follow_reference inline**:
- **D-FR:** registered stub resolving same-document references + typed `cross_document_resolution_pending_phase_4` for cross-doc; never silent-empty, never faked. Phase 4 fills the same interface.

---

## Rulebook scope & sourcing

### Q1 — Breadth
| Option | Description | Selected |
|--------|-------------|----------|
| Backbone-complete CFR + eval-scoped ICH/FDA | Title-21 drug parts wholesale; ICH/FDA scoped to eval topics | ✓ |
| Eval-driven minimal (all three) | Only what the eval cites | |
| Broad all-sources | All CFR + full ICH Q/S/E/M + comprehensive FDA | |

**User's choice:** Option 1, with an explicit decoupling — **rule TEXT = CFR-complete** (read_guideline can cite any drug-relevant clause) but **RULES-05 index TRIGGERS = eval-scoped, expand on demand**. Bounds expensive curation while nothing blocks citing a rule the index doesn't yet enumerate. → **D-RB1**

### Q2 — Sourcing & storage
| Option | Description | Selected |
|--------|-------------|----------|
| Vendored, version-pinned snapshot | Fetch once, commit raw source, rebuild index deterministically | ✓ |
| Live-fetch at build, cached (not committed) | Gitignored cache, date-pinned | |
| Live-query at runtime | On-demand per run | |

**User's choice:** Option 1 as **source of truth** + a manually-built **Databricks KB as serving layer**. All three corpora (FDA rules, ICH rules, precedents incl. `defpredict.main.deficiency_kb` ~500 rows) parse through Phase-1's substrate → span-IDs on every rule/precedent chunk; a read_guideline citation passes the same emit gate as a submission quote. Serving = Databricks Delta + Vector Search + a Delta relation layer. Build scripts manual one-time; dynamic refresh post-v1. Precedents = supporting evidence, never a finding source alone. → **D-RB2**

### Q3 — Phase-2 relation/precedent boundary
| Option | Description | Selected |
|--------|-------------|----------|
| Thin edges, GraphRAG measured, precedents retrievable-not-a-tool | Minimal edge table now; multi-hop only if harness proves lift; precedents not a 6th tool | ✓ |
| Full relation/GraphRAG + precedent tool now | Complete multi-hop graph + 6th tool | |
| Rules only; precedents + relation layer deferred | Leanest, literal ROADMAP | |

**User's choice:** Option 1, with two additive-later constraints: **(a)** generic edge schema `(src_id, dst_id, edge_type, provenance_span_id)` — zero-migration multi-hop add; every edge carries provenance. **(b)** precedents ingest through the substrate NOW so a 6th tool is later tool-registration, not re-ingestion (deferred to Phase-3 evidence, not dropped). → **D-RB3**

---

## Requirement index (RULES-05)

### Q1 — Applicability mechanism
| Option | Description | Selected |
|--------|-------------|----------|
| Classification-driven via the edge table | Detected families → required requirements | ✓ (extended) |
| Retrieval/semantic applicability | Trigger fires on corpus semantic match | |
| Universal enumerate (applicability deferred) | All curated reqs, no filtering | |

**User's choice:** Option 1, **extended one level** to the UNION of (a) document-level `family→requirement` and (b) **submission-profile closure** `profile→family` — so a required family with **zero classified documents fires as "entire section absent."** Same edge schema; leans on the Phase-1 coverage manifest to assert the zero-document claim. → **D-RB4**

### Q2 — Authoring
| Option | Description | Selected |
|--------|-------------|----------|
| LLM-draft → human-review → versioned data | LLM extracts triggers from rule text, human gates | ✓ |
| Hand-authored from scratch | Human writes each entry | |
| Fully LLM-derived, no review | Auto-generated | |

**User's choice:** Option 1, hardened by **(1)** an in-code loader gate (provenance span re-opens byte-exact, citation resolves, tags in D-05 registry — fails at LOAD); **(2)** a ground-truth traceability test (every Phase-0 absence deficiency has ≥1 firing entry — the MS-04 lesson); **(3)** diffable versioned review artifact, version bumped on change. → **D-RI1**

### Q3 — Enumerate surface
| Option | Description | Selected |
|--------|-------------|----------|
| Enumerate mode on read_guideline (stays 5 tools) | One optional param toggles index-vs-text | ✓ |
| Distinct 6th tool (list_requirements) | Separate tool | |
| Data-only in Phase 2, wired in Phase 3 | No agent-facing enumerate yet | |

**User's choice:** Option 1, with a 4-point contract: one optional `citation` param; **server-side** applicability (agent can't invent families; family filter validates or typed-rejects); returns stable requirement IDs usable directly in emit_finding; both modes TOOLS-04-bounded (over-large fails narrow-your-range, never truncates). → **D-RI2**

---

## emit_finding gate

### Q1 — Rule-citation validation
| Option | Description | Selected |
|--------|-------------|----------|
| Dual byte-exact grounding (both halves via open_span) | submission_span + rule_span both re-opened | ✓ |
| Submission verbatim; rule = validated identifier | Rule named, not quoted verbatim | |
| Rule = required non-empty field only | No rulebook validation in Phase 2 | |

**User's choice:** Option 1, with a 4-point contract: **(1)** agent passes **span-IDs on both halves, never retypes text** (selected-not-authored applies to the rule half); **(2)** store-membership validated (rule span in rulebook store, submission span in corpus store); **(3)** repeat-read cost solved by COST-04 read-dedup + the verdict needs the rule text anyway; **(4)** the gate proves **GROUNDING, not RELEVANCE** — relevance is the Phase-5 verifier's job. → **D-EF1**

---

## Final locks (before writing CONTEXT.md)

User added five closing decisions:
- **D-RB5** — two-index split: submission corpus LOCAL/ephemeral (FAISS dense + BM25/exact); rulebook + precedents on Databricks; lexical leg carries SC4 exact-identifier cases; harness embedding pinned local bge-m3.
- **D-RB6** — offline contract: tests + eval harness never touch Databricks; deterministic local build is contract-identical to Databricks serving via a config switch.
- **D-PREC** — build-time task: audit the ANDA xlsm vs `deficiency_kb`, set dedupe policy from the data; owner senior reviewer.
- **D-SC4** — recall@k bar = measure → record → ratchet, plus a HARD exact-identifier functional subset; no invented threshold.
- **D-GRAN** — span granularity: selection from ISSUED inline span-IDs (`cat -n` pattern); emit accepts only session-issued IDs; issuance granularity is the planner's knob, the select-not-construct contract is locked.

---

## Claude's Discretion

- TOOLS-04 size thresholds + COST-04 hit-rate reporting details.
- Hybrid-fusion mechanics for search_corpus (RRF vs weighted; dense/lexical weights) within D-RB5 + SC4's hard subset.
- Issuance granularity (sentence/row/cell) per D-GRAN.
- Corpus-index + edge-table on-disk formats (follow Delta/SQLite conventions).
- Reranker (bge-reranker-v2-m3) now-vs-later — measured precision lever.

## Deferred Ideas

- Multi-hop GraphRAG traversal — only if harness proves recall-by-family lift (D-RB3).
- Precedent-search as a 6th agent tool — Phase-3-evidence-gated (D-RB3).
- Cross-document follow_reference traversal — Phase 4 (D-FR).
- Dynamic rulebook refresh — post-v1 (D-RB2).
- Rule-citation relevance judgment — Phase 5 verifier (D-EF1).
