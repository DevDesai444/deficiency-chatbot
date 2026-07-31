# Phase 2: Retrieval, Navigation Tools & Rulebook - Context

**Gathered:** 2026-07-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Give the agent **hands**: five deterministic navigation tools — `search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline` — that return **identifiers and verbatim spans, never whole documents** (just-in-time retrieval), built on top of Phase 1's span-anchor substrate. Plus:

1. A **hybrid-retrieval submission index** (`search_corpus`) — local, ephemeral, dense+lexical.
2. An **FDA/ICH rulebook** the agent consults like a reviewer (`read_guideline`), sourced from eCFR Title 21 + ICH + FDA guidances.
3. A compact **requirement index** (RULES-05) that enumerates *what a submission must contain* independent of what it does contain — the absence-of-evidence mechanism against the measured 0/11 recall gap.
4. The **`emit_finding` gate** (TOOLS-03) — the *only* path by which a finding can exist; it re-resolves both cited spans and rejects fabricated quotes at the tool boundary with a typed, self-correcting error.
5. **Oversized-result handling** (TOOLS-04) and **read deduplication** (COST-04) inside the tools.

**Explicitly NOT in this phase:** the drive loop that *calls* these tools (Phase 3); cross-document reference-graph traversal (Phase 4 — `follow_reference` ships a same-doc stub here); the adversarial verifier and rule-*relevance* judgment (Phase 5); multi-hop GraphRAG traversal unless the harness proves recall lift; precedent-search as an agent tool (Phase-3-evidence-gated); dynamic rulebook refresh (post-v1).

**Decision-ID note:** the canonical IDs are below. In discussion a couple of interim labels were used — *applicability* = **D-RB4**, *enumerate contract* = **D-RI2** — reconciled here.

</domain>

<decisions>
## Implementation Decisions

### follow_reference — Phase-2 contract (this area was locked, not debated)
- **D-FR:** `follow_reference` ships as a **registered stub that RESOLVES same-document references** (section/heading refs within one doc — Phase 1's outline already supports this) and returns a typed **`cross_document_resolution_pending_phase_4`** for anything crossing a document boundary. **Never a silent empty result, never a faked edge.** An honest, *declared* capability boundary (D-30 availability-contract discipline). Phase 4's full reference graph fills the **same interface** without changing the contract, giving the Phase-3 go/no-go spike a real tool to call.

### Rulebook — breadth (text vs curation are decoupled axes)
- **D-RB1:** **Rule TEXT = CFR-complete; index TRIGGERS = eval-scoped.** Ingest the drug-relevant Title-21 parts **wholesale** (210/211 cGMP, 314 NDA/ANDA, 320 BA/BE, 600/601 biologics, 11 e-records) from public-domain XML, so `read_guideline` can cite *any* drug-relevant clause. ICH guidelines + FDA guidances are **eval-scoped** (the expensive/license-sensitive PDF sources). The RULES-05 requirement-index **triggers** stay eval-scoped and **expand on demand**. Consequence: *nothing blocks citing a rule the index doesn't yet enumerate* — cheap text breadth, bounded curation depth.

### Rulebook — sourcing & serving
- **D-RB2:** **Vendored snapshot = source of truth → manually-built Databricks KB = serving layer**, built deterministically from the snapshot.
  - **Committed, date-pinned raw sources:** eCFR Title-21 XML, ICH/FDA PDFs, and the `Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm` precedents (LFS if large) — reproducible, offline evals, byte-stable citations.
  - **All three corpora — FDA rules, ICH rules, precedents (incl. existing `defpredict.main.deficiency_kb` ~500 rows) — parse through Phase 1's ingestion substrate**, so every rule/precedent chunk carries canonical text + re-openable span-IDs, and **a `read_guideline` citation passes the same emit gate as a submission quote.** RULES-04 metadata `{source, citation, version/date, license, url}` + the required **ICH copyright notice** stored per chunk.
  - **Serving = Databricks Delta + Vector Search** (bge/gte endpoints, already READY) for hybrid semantic+keyword, **plus a Delta relation layer** (Rule ↔ CTD-section ↔ failure-family ↔ precedent).
  - **Build scripts are versioned one-time manual runs**; dynamic refresh is **post-v1**.
  - **Precedents = supporting evidence** (what reviewers cite), **never a finding source alone** — every finding still grounds in THIS submission + the rule it violates.
  - *(This deliberately supersedes CLAUDE.md's LanceDB reference-store recommendation — the user's Databricks Vector Search is already provisioned.)*

### Rulebook — Phase-2 relation/precedent boundary
- **D-RB3:** **Thin edges now, GraphRAG measured, precedents retrievable-not-a-tool.** Phase 2 builds the vendored snapshot + Databricks serving + a **minimal edge table** for exact-citation lookup and requirement-index applicability. Multi-hop GraphRAG traversal is *domain GraphRAG whose recall lift is MEASURED by the Phase-0 harness, not assumed* — if it doesn't move recall-by-family it **stays a thin edge table, not an architecture.** Two additive-later build constraints:
  - **(a) Generic edge schema `(src_id, dst_id, edge_type, provenance_span_id)`** — not bespoke per-relation tables; multi-hop adds ON the same table with **zero migration** if the harness argues for it. **Every edge carries a provenance span** (the span that justifies it) — no unexplained edges.
  - **(b) Precedents ingest through the Phase-1 substrate NOW** (canonical text + span-IDs), so exposing precedent-search as a **6th tool** later is a *tool-registration* decision gated on **Phase-3 evidence** — not a re-ingestion project. Deferred, not dropped.

### Requirement index — applicability (the absence-of-evidence mechanism)
- **D-RB4:** **Applicability = classification-driven via the edge table, as the UNION of two edge types in the same generic table:**
  - **(a) Document-level:** families detected in the corpus resolve through **`family→requirement`** edges to what each *present* document must satisfy.
  - **(b) Submission-profile closure:** **`profile→family`** edges declare which families a **content-derived** submission profile requires to *exist at all* (e.g. any 3.2.P document present ⇒ drug-product profile ⇒ P.7 stability family applicable).
  - A required family with **zero classified documents fires as "entire section absent"** — the corpus-level absence a detected-families-only rule structurally *cannot* see (no stability doc ⇒ stability reqs never fire ⇒ the most-cited real deficiency class is invisible).
  - Deliberately **independent of whether the submission mentions the requirement's subject** — that independence is exactly what makes absence detectable. No new machinery; just `profile→family` edges alongside `family→requirement`. Curated eval-scoped. **The Phase-1 coverage manifest (INGEST-03; the substrate DETECT-05 later emits) is what makes the zero-document claim assertable** (uncapped, complete enumeration).

### Retrieval architecture — two indexes, opposite lifecycles
- **D-RB5:** **Submission corpus = LOCAL/ephemeral; rulebook + precedents = Databricks.** D-RB2's Databricks serving covers the **build-once/query-constantly** rulebook + precedents. The per-submission index `search_corpus` queries is the **opposite lifecycle** — built per review run, discarded after — and stays **local ephemeral hybrid: FAISS dense + BM25/exact lexical** over the Phase-1 substrate. Routing submissions through Databricks would add network latency+cost to every run and make SC4's measurement non-deterministic. **SC4's exact-identifier cases (batch numbers, table labels) are carried by the lexical leg.** Harness embedding path **pinned (local bge-m3)** for reproducibility.
- **D-RB6:** **Offline contract — tests + eval harness NEVER touch Databricks.** The deterministic build from the vendored snapshot is **also queryable locally** (same chunks, same span-IDs, FAISS/BM25). `read_guideline`, the requirement index, and the emit gate's rulebook store run against **that local build** in CI and the Phase-0 harness — zero Databricks dependency, same discipline as Phase 1's offline fixture. **Databricks is runtime serving behind a contract-identical interface; a config switch selects the backend, tool contracts never change.**

### Requirement index — authoring
- **D-RI1:** **LLM-drafted → human-reviewed → versioned data**, hardened so "human-reviewed" can't degrade into an agent rubber-stamping its own draft:
  - **(1) Loader gate, in code:** the registry loader VALIDATES every entry at load — the provenance span-ID must re-open **byte-exact via `open_span`**, the citation must resolve to a real rulebook chunk, and family/profile tags must exist in the **D-05 registry**. A mis-drafted entry **fails at LOAD**, not at review-time attention. (Gate is code; review sits on top — same shape as everything else.)
  - **(2) Ground-truth traceability test** (seed acceptance criterion): for **every Phase-0 eval deficiency in the absence family**, ≥1 index entry must **FIRE** for that submission's profile — proven by a **test**, not asserted. A known-real deficiency with no requirement to surface it means the seed set is *incomplete by measurement*. (The requirement-index equivalent of the **MS-04** lesson: the instrument must enumerate what the eval actually contains.)
  - **(3) Review = a diffable data artifact:** drafts land as **versioned YAML/JSON**; a senior-reviewer session verifies **entry-by-entry against the cited rule spans** before merge; **index version bumped on any change** (D-24 discipline). Reviewer of record: senior-reviewer session; user spot-checks.

### Requirement index — enumerate surface (rides on `read_guideline`; stays 5 tools)
- **D-RI2:** **Enumerate mode on `read_guideline`**, with four contract details:
  - **(1) One optional `citation` parameter** — omit → compact applicable-requirement index; provide → that rule's bounded full text. Same shape as Read-with/without-offset: one schema for weak models to learn, and the **Phase-3 Llama/Qwen go/no-go tests exactly this call pattern.**
  - **(2) Applicability resolved server-side** from the corpus manifest (detected families + profile closure, D-RB4). The agent **cannot pass free-text profiles or invent families**; an optional family filter validates against the D-05 registry **or the call is rejected** (typed self-correcting error, same shape as `emit_finding`). *The agent asks "what applies here?" — it never asserts what applies.*
  - **(3) Enumerate returns stable requirement IDs + citations directly usable in `emit_finding`'s rule-citation field** — zero translation across the enumerate→investigate→emit loop.
  - **(4) Both modes TOOLS-04-bounded** — enumerate returns compact `{requirement_id, citation, one-line trigger}` rows only (never rule text); citation mode returns bounded text + span-IDs, over-large **fails with a narrow-your-range error, never truncates.**

### emit_finding — the grounding gate
- **D-EF1:** **Dual byte-exact grounding.** (Core already locked upstream: submission quote re-opens byte-exact against **RAW** per D-22, unique resolution per D-19; rejections return **typed self-correcting errors**, not bare failures.)
  - **(1) Agent passes span-IDs on BOTH halves — never retypes text.** Finding = `{submission_span_id, rule_span_id, verdict…}`; the gate re-opens each via `open_span` and compares. **Selected-not-authored (TOOLS-02) applies to the rule half identically** — retyping is where weak models introduce drift, so the schema never asks for it.
  - **(2) Store-membership validated:** the rule span must resolve in the **RULEBOOK** store and the submission span in the **CORPUS** store — a submission span passed as a rule citation is a **typed rejection**, not a pass.
  - **(3) Repeat-read cost is already solved** by COST-04 read-dedup (built this phase): the second `read_guideline` of the same span is a **"still current" stub**; and the agent needs the rule text anyway for **DETECT-04's** compliance verdict, so the gate just makes *skipping* that read impossible.
  - **(4) Honest scope — the gate proves GROUNDING, not RELEVANCE.** Byte-exact rule quoting proves a real rule was retrieved+read this session; whether it's the **right** rule is the **Phase-5 verifier's** judgment, made sharper because it receives an *exact rule span to confirm/refute against*, not a bare citation number.
  - **(5) Finding schema — how D-RI2(3) and this lock compose (no contradiction):** the finding carries **BOTH** `rule_span_id` (the GROUNDING field — what the gate re-opens and validates, per (1)) **and** `requirement_id`/`citation` (METADATA linking the finding to the requirement it addresses — what D-RI2's enumerate returned). "Zero translation" means the flow `enumerate → citation → read_guideline(citation) → issued rule span-IDs → emit` needs no format conversion at any step — it does **not** mean a citation string substitutes for the span-ID. A finding missing `rule_span_id` is a typed rejection regardless of how valid its citation metadata is.

### Span granularity — selection from ISSUED IDs (agent never computes offsets)
- **D-GRAN:** Tools return text **ANNOTATED with per-sentence / per-row / per-cell span-IDs inline** — the Claude Code `cat -n` pattern: the model cites IDs it can **SEE**, never counts characters. `emit_finding` accepts **only IDs issued this session** (the **retrieval ledger**) — selection-not-authoring in its purest form, and **issued IDs are unique by construction**, which simplifies the gate's uniqueness check. Char-offset arithmetic by weak models is exactly where citation drift would re-enter; the schema never asks for it. Table cells already carry cell-level IDs (D-31); sentence-level annotation **extends the same pattern to prose**. **Granularity of ISSUANCE (sentence/row/cell) is the planner's tuning knob; the CONTRACT (agent selects issued IDs, never constructs ranges) is LOCKED.**

### SC4 — retrieval-recall acceptance bar
- **D-SC4:** **Measure → record → ratchet, plus one hard functional subset.** No invented threshold number before measurement (D-03's no-baked-cutoff discipline). Phase 2 measures recall@k over the Phase-0 answer spans, **RECORDS it as the committed retrieval baseline** (same shape as the `recall_by_family` baseline), and the gate is:
  - **(i)** the **exact-identifier subset passes HARD** — every eval-set batch number / table label retrieves its home document (functional correctness, not a statistic); **and**
  - **(ii)** the recorded recall@k becomes a **no-regress floor** for every later phase (ratchet). A phase that can't beat an unmeasured number is meaningless; one that regresses a measured one fails loudly.

### Precedent data — build-time task (recorded so it can't evaporate)
- **D-PREC:** **Audit `Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm` against the existing `defpredict.main.deficiency_kb` (~500 rows)** — schema, counts, overlap — and **set dedupe policy from what the data actually is.** Owner: senior reviewer.

### Claude's Discretion (within the locked contracts)
- TOOLS-04 size thresholds (persist-to-disk cutoff, preview shape); COST-04 read-dedup **hit-rate reporting** details.
- Hybrid-fusion mechanics for `search_corpus` (RRF vs weighted; dense/lexical weights) — bounded by D-RB5 (local FAISS + BM25/exact) and SC4's exact-identifier hard subset.
- **Issuance granularity** (sentence vs row vs cell) per D-GRAN — tune against emit precision + index cost.
- Corpus-index and edge-table on-disk formats — follow existing Delta/SQLite conventions where sensible (parallels Phase 1 D-15).
- Whether the reranker (`bge-reranker-v2-m3`) is added now or deferred — a precision lever, only if measured to help.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase governance
- `.planning/ROADMAP.md` — Phase 2 goal + Success Criteria 1–8 (the acceptance contract); the "code gate at the tool boundary" law; Phase-2 Research flag (rulebook-sourcing de-risking sub-track).
- `.planning/REQUIREMENTS.md` — **this phase:** TOOLS-01..04, RULES-01..05, COST-04. **Downstream consumers of these tools:** GROUND-01/03 + DETECT-04 (Phase 3), DETECT-05 (Phase 4), GROUND-02 (Phase 5). Anti-features (Out of Scope table).
- `.planning/PROJECT.md` — Key Decisions (guidelines-as-retrievable-reference-NOT-oracles; grounding-mandatory; content-driven, no-doc-cap; cost via caching/compaction/cheap-triage). **"Known debt to avoid inheriting":** README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE describe a REMOVED AutoGen design — do not trust their file refs.
- `.planning/phases/01-ingestion-foundation/01-CONTEXT.md` — Phase 1 decisions D-18..D-32 the substrate rests on (span-IDs, re-open primitive, normalizer version, table addressing, availability tiers, D-05 registry).

### The span-anchor substrate Phase 2 builds ON (Phase 1 deliverables)
- `src/ingest/anchors.py` — **`open_span(span, nt, doc_id) → (raw, canonical)` + `HashMismatch`**; `mint_span`; `short_hash`. THE re-open/verify primitive (D-21) that `emit_finding`, `get_section`, and the requirement-index loader gate (D-RI1) all call.
- `src/ingest/corpus.py` — `CorpusIndex` + `ingest_corpus()`; per-doc cache shape (`canonical`, `raw_serialized`, `offset_map`, `table_index`, `doc_entry`, outline) — what all rulebook/precedent corpora also route through (D-RB2).
- `src/ingest/normalize.py` — `canon_range_to_raw` offset map (D-23), normalizer version stamp (D-24).
- `src/ingest/tables.py` — `(table_id, row, col) → span-ID` table index (D-31) — cell-level IDs D-GRAN extends to prose.
- `src/ingest/manifest.py` — `CoverageManifest`, `DocEntry`, `OutlineEntry` — the coverage manifest the profile-closure absence claim (D-RB4) leans on.
- `src/ingest/store.py` — cache persistence (read-back for `get_section` / local rulebook build).
- `src/ingest/registry/` — the **D-05 data-driven CTD-family registry** (`{id, one-line trigger}`) the requirement index aligns with and the loader gate validates tags against (D-RI1).
- `src/ingest/classify.py` — document classification (families → the submission profile that drives applicability, D-RB4).
- `src/schemas/documents.py` — `NormalizedText`, `SpanID`.

### Existing retrieval + the Databricks serving seam
- `src/retrieval/vector_search.py` — `embed_texts` / `embed_query` (local **bge-m3** / `databricks-bge-large-en`, normalized) — the dense leg of local `search_corpus` (D-RB5); harness embedding pinned local (D-RB6).
- `src/retrieval/knowledge_base.py` — existing FAISS search over the 500-row deficiency KB; the precedent-retrieval seam + **D-PREC** audit target.
- `src/databricks/vector.py` — Databricks Vector Search client — runtime rulebook/precedent serving backend (D-RB2/D-RB5), behind the config switch (D-RB6).

### LLM plumbing
- `src/llm/structured.py` — hardened structured-output stack for the LLM requirement-index drafter (D-RI1) and typed tool-arg validation / self-correcting errors.
- `src/llm/client.py` — OpenAI-compatible client (Ollama/Databricks).

### Eval harness (SC4 baseline, traceability test, offline contract)
- `src/evals/run.py` — CI-style harness that imports the ingest library; home of the offline contract (D-RB6), the SC4 baseline recording (D-SC4), and the requirement-index traceability test (D-RI1).
- `src/evals/dataset/minispec.deficiencies.json` + `src/evals/dataset/documents.json` — labeled ground truth; the **MS-04** lesson (instrument must enumerate what the eval contains) is the model for D-RI1's traceability test.
- `.planning/phases/00-eval-harness/` — the `recall_by_family` baseline shape D-SC4 mirrors.

### Data sources (vendored snapshot — D-RB2)
- `Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm` — precedent source (**D-PREC** audit vs `defpredict.main.deficiency_kb`).
- **External, to vendor + version-pin:** eCFR Title 21 XML (public domain), ICH guideline PDFs (copyright-ack required), FDA guidance PDFs via regulations.gov. URLs + license notes live in project `CLAUDE.md` → "FDA / ICH Rules Sources" table.
- `CLAUDE.md` (project) — Technology Stack: source URLs/licenses; note the **LanceDB/reranker recommendations are superseded** for serving by the user's Databricks choice (D-RB2/D-RB5); reranker remains an optional measured precision lever.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`src/ingest/anchors.py` `open_span`** — reuse *verbatim* as the re-open/verify primitive under `get_section`, `emit_finding`, and the requirement-index loader gate. Do NOT reinvent span verification.
- **`src/ingest/registry/`** — the D-05 `{id, one-line trigger}` family registry; the requirement index is the same shape by design (build once, reuse). Loader-gate tag validation resolves against it.
- **`src/retrieval/vector_search.py`** — the embedding path (local bge-m3 / Databricks) already abstracts local-vs-serving; the dense leg of `search_corpus` and the rulebook dense index both build on it.
- **`src/retrieval/knowledge_base.py`** — existing FAISS/precedent retrieval; the precedent corpus unification (D-RB2) and D-PREC audit start here.
- **`src/llm/structured.py`** — the malformed-output fallback for the LLM requirement-index drafter and for typed self-correcting tool-arg errors.
- **`src/evals/run.py`** — the "import the library, record, never crash" harness; SC4 baseline + traceability test + offline contract all live here.

### Established Patterns
- **Content-addressed, version-stamped grounding** (span-ID = `{doc_id,start,end}`+hash, normalizer version) — the whole rulebook + precedent unification (D-RB2) rides on applying this to *rules*, not just submissions.
- **Deterministic-first, LLM-as-escalation** (oracles/checklists before specialists; classification tier ladder) — mirrored by the requirement-index **code loader gate first, LLM draft + human review on top** (D-RI1).
- **Declared availability contract, not runtime discovery** (D-30) — `follow_reference`'s typed `cross_document_resolution_pending_phase_4` (D-FR) and `read_guideline`'s typed rejections (D-RI2) follow the same "state the boundary, never fake it" ethos.
- **Offline fixture / no external dependency in CI** (Phase 1) — extended by D-RB6's "tests + harness never touch Databricks."

### Integration Points
- **Tools sit ON the substrate handoff surface** (canonical text + span-IDs from `src/ingest/`) — Phase 2 adds the navigation layer; it does NOT rewire `run_pipeline`/`upload.py` (still deferred per Phase-1 D-13; agent wiring is Phase 3).
- **Backend config switch** (D-RB6) — a single seam selects local-build vs Databricks serving for the rulebook/precedent store; tool contracts are backend-agnostic.
- **Generic edge table** (D-RB3) — new Delta relation layer keyed `(src_id, dst_id, edge_type, provenance_span_id)`; the requirement index's `family→requirement` + `profile→family` edges (D-RB4) live here.

</code_context>

<specifics>
## Specific Ideas

- **`cat -n` line-number analogy (D-GRAN):** the model cites span-IDs it can SEE inline, never computes char offsets — the single most-cited anti-citation-drift move.
- **Read-with/without-offset schema analogy (D-RI2):** one optional `citation` param gives enumerate-vs-fetch; deliberately the exact call pattern the Phase-3 Llama/Qwen go/no-go stresses.
- **MS-04 traceability analogy (D-RI1):** the requirement index is an *instrument*; a test proves it enumerates every absence-family deficiency the eval actually contains.
- **"Still current" stub reuse (D-EF1 ↔ COST-04):** the dual-grounding gate's repeat-read cost evaporates because read-dedup returns a stub on the second read of the same rule span.
- **Grounding ≠ relevance (D-EF1):** the emit gate's promise stays falsifiable — it proves a real rule was read this session; relevance is handed to the Phase-5 verifier, which now gets an exact span to refute against.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-hop GraphRAG traversal** (D-RB3) — built ONLY if the Phase-0 harness shows recall-by-family lift; otherwise the edge table stays thin. Same generic schema, zero-migration add.
- **Precedent-search as a 6th agent tool** (D-RB3) — deferred to Phase-3 evidence; precedents are ingested + retrievable now, so it's a later tool-registration, not re-ingestion.
- **Cross-document `follow_reference` traversal** (D-FR) — Phase 4 fills the same interface with the full reference graph.
- **Dynamic rulebook refresh** (D-RB2) — post-v1; build scripts are versioned one-time manual runs now.
- **Rule-citation RELEVANCE judgment** (D-EF1) — Phase 5 adversarial verifier.
- **Reranker (`bge-reranker-v2-m3`)** — optional precision lever, add only if measured to help (Claude's discretion).

None of the above are scope creep — each was raised, bounded, and consciously placed.

</deferred>

---

*Phase: 2-retrieval-navigation-tools-rulebook*
*Context gathered: 2026-07-31*
