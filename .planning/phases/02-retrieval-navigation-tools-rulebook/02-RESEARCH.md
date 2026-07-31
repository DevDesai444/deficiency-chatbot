# Phase 2: Retrieval, Navigation Tools & Rulebook - Research

**Researched:** 2026-07-31
**Domain:** Agent-facing navigation tools over a span-anchor substrate · hybrid (dense+lexical) retrieval · FDA/ICH rulebook sourcing & serving · requirement-index absence-of-evidence mechanism · grounding-gate tool-boundary validation
**Confidence:** HIGH (external sourcing mechanics, Databricks state, and codebase substrate all empirically verified live this session; MEDIUM on two named compliance gaps — see Assumptions Log)

## Summary

Phase 2 carries the roadmap's rulebook-sourcing research flag, and the flag was earned: this session live-tested every external dependency named in CONTEXT.md rather than trusting CLAUDE.md's prior research, and found the mechanics **mostly sound but with real, specific landmines**. The eCFR `versioner/v1` REST API is fully live and — critically — supports a `?part=` query parameter that scopes a fetch to exactly one CFR part (verified for all seven parts D-RB1 names: 210/211/314/320/600/601/11, totaling **~826 KB**, not the multi-megabyte whole-title pull CLAUDE.md implied). The GovInfo bulk-XML fallback CLAUDE.md documented is **stale** (`Bulkdata Service Error`) — the REST API is the sole verified path. ICH's exact copyright-acknowledgment paragraph was read **verbatim, directly from the source PDF** (not paraphrased) — and it does **not** appear in every ICH guideline: it is present in post-2015 "International Council for Harmonisation" era documents (E6(R2) Addendum, Q2(R2)) but **completely absent** from the four pre-2015 "ICH Harmonised Tripartite Guideline" era documents this eval set most needs (Q3A(R2), Q3B(R2), Q6A, Q1A(R2)) — confirmed by full-text scan, zero hits for "copyright" in any of them. regulations.gov API v4 is live, `api_key`-gated (confirmed 403 without one, confirmed a public `DEMO_KEY` works for spike-testing), and its documents→attachments→PDF-download flow was exercised end-to-end; the single most eval-relevant FDA guidance ("Analytical Procedures and Methods Validation for Drugs and Biologics") resolves to a stable, directly-fetchable `fda.gov/files/...pdf` URL that bypasses the API entirely.

Two things this session could **not** verify, and both matter: (1) the Databricks token configured in `.env` is fully live for SQL Statement Execution and Model Serving (embeddings **and** chat, including `databricks-meta-llama-3-3-70b-instruct` and both Qwen variants) but returns **403 "access token does not have required scopes: vector-search"** on the Vector Search Admin API — D-RB2's literal "Databricks Vector Search" serving layer cannot be provisioned with the current token; (2) ich.org's site-wide legal-mentions page is a JavaScript-rendered SPA this session's tools cannot execute, so the per-document notice text (which **was** verified) could not be cross-checked against a possible stricter site-wide term. Separately, and load-bearing for planning: **both `data/` and `Sample Data/` are blanket-`.gitignore`d** in this repo today — D-RB2's "committed, date-pinned raw sources" and "commit the xlsm precedent" requirements will silently no-op unless the plan adds a new tracked directory (recommended: `rulebook/`, not `data/`).

**Primary recommendation:** Build a new `src/tools/` package (the 5 tools + `emit_finding`) that calls Phase 1's `ingest.anchors.open_span` verbatim for every grounding check, and a new `src/rulebook/` package whose one-time build script pulls the vendored snapshot in `rulebook/` (new, git-tracked, NOT `data/`) through the *same* Phase-1 substrate (`serialize→normalize→anchor`) used for submissions, then populates **both** a local SQLite+FAISS+BM25 build (the D-RB6 offline/CI backend) **and** Databricks Delta tables (the runtime backend) from that one deterministic source. Treat literal Vector Search endpoint creation as blocked-pending-token-scope and ship the already-proven `_search_embeddings_table` client-side-cosine path (or a FAISS mirror of it) as the v1 Databricks-side retrieval leg, since D-RB6 already requires backend-agnostic tool contracts.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
Copied verbatim (condensed) from `02-CONTEXT.md`. These are settled — research is HOW, not WHETHER.

**follow_reference — Phase-2 contract**
- **D-FR:** `follow_reference` ships as a registered stub that RESOLVES same-document references (Phase 1's outline already supports this) and returns a typed `cross_document_resolution_pending_phase_4` for anything crossing a document boundary. Never a silent empty result, never a faked edge.

**Rulebook — breadth (text vs curation are decoupled axes)**
- **D-RB1:** Rule TEXT = CFR-complete; index TRIGGERS = eval-scoped. Ingest drug-relevant Title-21 parts **wholesale** (210/211 cGMP, 314 NDA/ANDA, 320 BA/BE, 600/601 biologics, 11 e-records). ICH guidelines + FDA guidances are **eval-scoped**. RULES-05's triggers stay eval-scoped and expand on demand. Nothing blocks citing a rule the index doesn't yet enumerate.

**Rulebook — sourcing & serving**
- **D-RB2:** Vendored snapshot = source of truth → manually-built Databricks KB = serving layer, built deterministically from the snapshot. Committed, date-pinned raw sources: eCFR Title-21 XML, ICH/FDA PDFs, `Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm` (LFS if large) — reproducible, offline evals, byte-stable citations. All three corpora (FDA rules, ICH rules, precedents incl. existing `defpredict.main.deficiency_kb` ~500 rows) **parse through Phase 1's ingestion substrate**, so every chunk carries canonical text + re-openable span-IDs, and a `read_guideline` citation passes the **same emit gate** as a submission quote. RULES-04 metadata `{source, citation, version/date, license, url}` + required ICH copyright notice stored per chunk. Serving = Databricks Delta + Vector Search (bge/gte endpoints, "already READY") for hybrid semantic+keyword, plus a Delta relation layer. Build scripts are versioned one-time manual runs; dynamic refresh is post-v1. Precedents = supporting evidence, never a finding source alone. *(Deliberately supersedes CLAUDE.md's LanceDB recommendation.)*

**Rulebook — Phase-2 relation/precedent boundary**
- **D-RB3:** Thin edges now, GraphRAG measured, precedents retrievable-not-a-tool. A **generic edge schema** `(src_id, dst_id, edge_type, provenance_span_id)` — not bespoke per-relation tables; every edge carries a provenance span. Precedents ingest through the Phase-1 substrate NOW; exposing precedent-search as a 6th tool is gated on Phase-3 evidence.

**Requirement index — applicability**
- **D-RB4:** Applicability = classification-driven via the edge table, as the UNION of two edge types: (a) **document-level** `family→requirement` edges; (b) **submission-profile closure** `profile→family` edges declaring which families a content-derived profile requires to exist AT ALL (e.g. any 3.2.P doc ⇒ drug-product profile ⇒ P.7 stability applicable). A required family with **zero classified documents fires as "entire section absent."** Independent of whether the submission mentions the requirement's subject. The Phase-1 coverage manifest is what makes the zero-document claim assertable.

**Retrieval architecture — two indexes, opposite lifecycles**
- **D-RB5:** Submission corpus = LOCAL/ephemeral; rulebook + precedents = Databricks. The per-submission `search_corpus` index is built per run, discarded after, and stays **local ephemeral hybrid: FAISS dense + BM25/exact lexical**. SC4's exact-identifier cases (batch numbers, table labels) are carried by the lexical leg. Harness embedding path **pinned (local bge-m3)** for reproducibility.
- **D-RB6:** Offline contract — tests + eval harness NEVER touch Databricks. The deterministic build from the vendored snapshot is **also queryable locally** (same chunks, same span-IDs, FAISS/BM25). `read_guideline`, the requirement index, and the emit gate's rulebook store run against **that local build** in CI/harness — zero Databricks dependency. Databricks is runtime serving behind a contract-identical interface; a config switch selects the backend, tool contracts never change.

**Requirement index — authoring**
- **D-RI1:** LLM-drafted → human-reviewed → versioned data. (1) **Loader gate in code**: validates every entry at load — provenance span-ID re-opens byte-exact via `open_span`, citation resolves to a real rulebook chunk, family/profile tags exist in the D-05 registry. A mis-drafted entry fails at LOAD. (2) **Ground-truth traceability test**: for every Phase-0 eval deficiency in the absence family, ≥1 index entry must FIRE for that submission's profile — proven by a test. (3) **Review = a diffable data artifact**: drafts land as versioned YAML/JSON; senior-reviewer session verifies entry-by-entry against cited rule spans before merge; index version bumped on any change.

**Requirement index — enumerate surface**
- **D-RI2:** Enumerate mode on `read_guideline`. (1) One optional `citation` parameter — omit → compact applicable-requirement index; provide → that rule's bounded full text. (2) Applicability resolved **server-side** from the corpus manifest; the agent cannot pass free-text profiles or invent families — an optional family filter validates against the D-05 registry or the call is rejected (typed error). (3) Enumerate returns stable requirement IDs + citations directly usable in `emit_finding`'s rule-citation field. (4) Both modes TOOLS-04-bounded — enumerate returns compact rows only; citation mode returns bounded text + span-IDs, over-large fails with a narrow-your-range error, never truncates.

**emit_finding — the grounding gate**
- **D-EF1:** Dual byte-exact grounding. (1) Agent passes span-IDs on BOTH halves — never retypes text. Finding = `{submission_span_id, rule_span_id, verdict…}`; the gate re-opens each via `open_span` and compares. Selected-not-authored (TOOLS-02) applies to the rule half identically. (2) **Store-membership validated**: rule span must resolve in the RULEBOOK store, submission span in the CORPUS store — a submission span passed as a rule citation is a typed rejection. (3) Repeat-read cost solved by COST-04 (built this phase). (4) The gate proves GROUNDING, not RELEVANCE — that's Phase 5. (5) Finding schema carries BOTH `rule_span_id` (grounding, gate-validated) AND `requirement_id`/`citation` (metadata linking to what enumerate returned) — a citation string never substitutes for the span-ID.

**Span granularity**
- **D-GRAN:** Tools return text ANNOTATED with per-sentence/per-row/per-cell span-IDs inline — the Claude Code `cat -n` pattern: the model cites IDs it can SEE, never counts characters. `emit_finding` accepts ONLY IDs issued this session (**the retrieval ledger**) — issued IDs are unique by construction. Table cells already carry cell-level IDs (D-31); sentence-level annotation extends the same pattern to prose. Granularity of issuance is the planner's tuning knob; the CONTRACT (select issued IDs, never construct ranges) is LOCKED.

**SC4 — retrieval-recall acceptance bar**
- **D-SC4:** Measure → record → ratchet, plus one hard functional subset. No invented threshold before measurement. Phase 2 measures recall@k over the Phase-0 answer spans, **RECORDS it as the committed retrieval baseline** (same shape as `recall_by_family`), and the gate is: (i) the exact-identifier subset passes HARD (every eval-set batch number/table label retrieves its home document); (ii) the recorded recall@k becomes a no-regress floor for every later phase.

**Precedent data — build-time task (recorded, not performed here)**
- **D-PREC:** Audit `Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm` (**4,040,565 bytes, ~4.04 MB** — measured this session) against `defpredict.main.deficiency_kb` (**confirmed exactly 500 rows this session**) — schema, counts, overlap — and set dedupe policy from what the data actually is. **Owner: senior reviewer. Explicitly NOT performed in this research per the task's hard constraint.**

### Claude's Discretion (within the locked contracts)
- TOOLS-04 size thresholds (persist-to-disk cutoff, preview shape); COST-04 read-dedup hit-rate reporting details.
- Hybrid-fusion mechanics for `search_corpus` (RRF vs weighted; dense/lexical weights) — bounded by D-RB5 (local FAISS + BM25/exact) and SC4's exact-identifier hard subset.
- Issuance granularity (sentence vs row vs cell) per D-GRAN.
- Corpus-index and edge-table on-disk formats — follow existing Delta/SQLite conventions where sensible.
- Whether the reranker (`bge-reranker-v2-m3`) is added now or deferred — only if measured to help.

### Deferred Ideas (OUT OF SCOPE)
- Multi-hop GraphRAG traversal (D-RB3) — built only if the harness shows recall-by-family lift.
- Precedent-search as a 6th agent tool (D-RB3) — Phase-3-evidence-gated.
- Cross-document `follow_reference` traversal (D-FR) — Phase 4.
- Dynamic rulebook refresh (D-RB2) — post-v1.
- Rule-citation RELEVANCE judgment (D-EF1) — Phase 5 adversarial verifier.
- Reranker (`bge-reranker-v2-m3`) — optional precision lever, Claude's discretion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support (this doc) |
|----|-------------|------------------------------|
| **TOOLS-01** | 5 general tools returning identifiers/snippets, not whole documents | Cluster: Tools. `src/tools/` package sketch; existing `render.py`/`section_splitter.py` reused for section rendering; System Architecture Diagram shows the tool-call flow. |
| **TOOLS-02** | Tools return verbatim span-IDs; quote is selected, never authored | Cluster: Tools / Emit Gate. D-GRAN `cat -n` pattern; reuses `ingest.anchors.open_span`/`mint_span` verbatim (Phase 1, verified in-repo). |
| **TOOLS-03** | `emit_finding` re-resolves cited spans, rejects fabricated/non-unique/never-retrieved/rule-less quotes with a typed error | Cluster: Emit Gate. Mirrors existing `HashMismatch` (exception) + `ParseFailed` (sentinel) typed-error conventions, both read in full this session. Validation Architecture names the exact fabrication-rejection test. |
| **TOOLS-04** | Oversized results persist-to-disk + bounded preview + handle; over-large `get_section` fails narrow-your-range, never truncates | Cluster: Tools. Common Pitfalls #4 (never truncate — same discipline `structured.py`'s truncation-retry layer already models for LLM output). |
| **RULES-01** | eCFR Title 21 (public-domain XML) as the rulebook backbone | Cluster: Rulebook Sourcing. eCFR `versioner/v1` live-verified for all 7 parts, exact byte sizes, `?part=` scoping discovery, GovInfo-bulk-is-stale finding, 17 U.S.C. §105 public-domain citation (verified via Cornell LII). |
| **RULES-02** | ICH guidelines ingested, required copyright acknowledgment stored per chunk | Cluster: Rulebook Sourcing. Exact verbatim notice text (read directly from source PDF); the notice's ABSENCE from 4 of the 5 eval-scoped guidelines (verified via full-text scan) — the single most important landmine in this research. |
| **RULES-03** | FDA guidances (via regulations.gov) for eval-set topics | Cluster: Rulebook Sourcing. regulations.gov v4 mechanics live-verified (key requirement, DEMO_KEY, rate limit, attachment flow); the specific eval-relevant guidance resolved to a stable direct fda.gov URL. |
| **RULES-04** | Every rule chunk stores `{source, citation, version/date, license, url}` | Cluster: Rulebook Sourcing. Code Examples gives the metadata schema + the `rulebook/manifest.yaml` shape; Pitfall on eCFR's `_SUBSTITUTE_DATE_` placeholder trap. |
| **RULES-05** | Compact requirement index (citation + one-line trigger), separate from full rule text; enumerable | Cluster: Requirement Index. Existing `checklists.py::_VALIDATION_REQUIRED` (9 keys) and `catalog.py::CANONICAL_DOMAINS` identified as ready-made source material; D-05 registry loader pattern to mirror; D-RI1 traceability test design. |
| **COST-04** | Re-retrieving an unchanged span returns a "still current" stub | Cluster: Cost/Dedup. Retrieval-ledger design (shared with D-GRAN); Validation Architecture names the dedup test. |
</phase_requirements>

## Architectural Responsibility Map

This is a backend/agentic library, not a web app — "tiers" below are the system's internal layers (mirrors Phase 1's adaptation of this table). Mapping each capability to its owning layer prevents the two errors this phase is most exposed to: leaking rulebook-fetch logic into the tool layer, and leaking span-verification logic out of the one primitive that owns it.

| Capability | Primary Layer | Secondary Layer | Rationale |
|------------|---------------|------------------|-----------|
| 5 navigation tool signatures + arg validation | **Tool layer** (`src/tools/`, NEW) | — | TOOLS-01/02/04's home; pure Python callables Phase 3's loop binds — no HTTP surface this phase. |
| `emit_finding` grounding gate | **Tool layer** (`src/tools/emit_finding.py`, NEW) | Substrate (`ingest.anchors.open_span`) | TOOLS-03/D-EF1; the gate calls the Phase-1 primitive, never reimplements verification. |
| Retrieval ledger (issued span-IDs this session) + read-dedup | **Tool layer** (`src/tools/ledger.py`, NEW) | — | D-GRAN + COST-04; must be per-agent-run scoped (Security Domain V3 note). |
| Per-submission hybrid index (dense+lexical) | **Retrieval** (`src/retrieval/`, EXTEND) | Substrate (Phase-1 corpus cache) | D-RB5; local/ephemeral, built per run from the already-cached canonical text. |
| eCFR XML → unified document dict | **Rulebook parse adapter** (`src/rulebook/ecfr_parse.py`, NEW) | Substrate (`ingest.serialize`/`normalize`) | The ONE new parser this phase needs; converges on the SAME dict shape `extract_pdf`/`extract_docx` emit so it flows through the existing substrate unchanged. |
| ICH/FDA PDF → unified document dict | **Substrate** (`parse.pdf.extract_pdf`, existing, REUSED) | — | No new parser — these are ordinary PDFs. |
| Vendored raw-source storage | **Data** (`rulebook/`, NEW top-level, git-tracked) | — | D-RB2; must NOT be `data/` (gitignored) or unpatched `Sample Data/` (also gitignored) — see Common Pitfalls #1. |
| Rulebook build orchestration (one-time, versioned) | **Rulebook build** (`src/rulebook/build.py`, NEW) | Substrate + both serving backends | D-RB2's "manually-built... deterministically from the snapshot." |
| Local rulebook query backend (CI/harness) | **Persistence** (SQLite + FAISS/BM25, mirrors `ingest/store.py` conventions) | — | D-RB6's offline contract. |
| Databricks rulebook query backend (runtime) | **Databricks serving** (`src/databricks/`, EXTEND) | — | D-RB2; behind the SAME contract as the local backend (config switch, D-RB6). |
| Generic edge table (`family→requirement`, `profile→family`) | **Data** (SQLite, mirrors `databricks/delta.py` job-store convention) | — | D-RB3/D-RB4; one 4-column table, not a graph database. |
| Requirement-index entries (data) | **Data** (`src/rulebook/requirement_index.yaml`, NEW) | Registry (`ingest.registry`, D-05, REUSED pattern) | D-RI1; same `{id, one-line trigger}` shape by design. |
| Requirement-index loader gate (code) | **Rulebook** (`src/rulebook/requirement_index.py`, NEW) | Substrate (`open_span`) | D-RI1(1); a mis-drafted entry fails at LOAD, mirroring the registry's own load-time validation posture. |

**Boundary law:** the tool layer never calls an external network endpoint directly (not eCFR, not ICH, not regulations.gov, not Databricks admin APIs) — those calls belong ONLY inside `src/rulebook/build.py`'s one-time, versioned build step. At runtime, tools resolve exclusively against the already-built local-or-Databricks store behind the D-RB6 config switch. This is also the SSRF mitigation named in Security Domain below.

## Project Constraints (from CLAUDE.md)

Directives extracted from `./CLAUDE.md` that the planner must honor with the same authority as locked decisions, **reconciled against CONTEXT.md where they conflict** (CONTEXT.md wins per the task's explicit instruction):

- **Superseded by D-RB2 (not a contradiction — CONTEXT.md wins):** CLAUDE.md recommends LanceDB as the reference-corpus store. The user's Databricks Vector Search is already provisioned (SQL Statement API, Delta tables, and Model Serving all confirmed live this session) — do NOT introduce LanceDB. `rank-bm25` for the ephemeral per-submission lexical leg is still correctly recommended by CLAUDE.md and is NOT superseded — verified current at PyPI **0.2.2** this session, not yet a dependency.
- **Confirmed still accurate:** the "FDA / ICH Rules Sources" table's eCFR REST endpoint shapes are correct (`versioner/v1/full/{date}/title-21.xml`, `versioner/v1/structure/{date}/title-21.json`) — verified live. The GovInfo bulk-XML fallback path (`govinfo.gov/bulkdata/ECFR/title-21`) is **stale/broken** (returns a "Bulkdata Service Error" page) — do not rely on it; the REST API is sufficient and is the sole verified path.
- **Confirmed still accurate, refined:** regulations.gov API v4 requires a free `api.data.gov` key (confirmed: 403 `API_KEY_MISSING` without one); rate limit confirmed **1,000 requests/hour** (verified via the api.data.gov Developer Manual directly, not just CLAUDE.md's prior claim).
- **New finding CLAUDE.md did not have:** ICH's copyright-acknowledgment paragraph is **absent** from the pre-2015 "Tripartite Guideline" era PDFs (which is most of what this eval set needs — Q3A(R2)/Q3B(R2)/Q6A/Q1A(R2)). CLAUDE.md's "MEDIUM confidence, verify the notice text" flag was well-placed — the exact text is now VERIFIED (quoted below), but its per-document universality was wrong; treat the notice as a stored constant applied uniformly, not a per-PDF extraction target.
- **`openai` 1.40→2.x upgrade:** NOT this phase's action. Phase 2 builds pure-Python tool functions and schemas; it does not itself drive an `openai` tool-calling loop (that's Phase 3, AGENT-01). The installed venv already has `openai==2.43.0` (verified this session, PyPI latest is 2.51.0) — no version action needed here, but do not let the planner assign an unrelated SDK-bump task to this phase.
- **Grounding law, generality law, cost law (PROJECT.md):** unchanged, directly enforced by D-EF1/D-RB1/D-RB6 respectively.
- **Branch / stale-docs debt:** unchanged from Phase 1's note — build on the uncommitted `planning.py`/`summarise.py`/`sandwich.py`/`workers.py` redesign in `src/agents/detection/`, do not clobber it (Phase 2 does not touch these files — they are Phase 3's drive-loop surface). README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE still describe the removed AutoGen design.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `rank-bm25` | **0.2.2** `[VERIFIED: pypi.org/pypi/rank-bm25/json, this session]` | BM25 lexical leg of `search_corpus` (D-RB5) | Current, stable (only 4 releases ever — 0.1/0.2/0.2.1/0.2.2, first shipped 2017), single-purpose, exactly matches "BM25/exact lexical" locked in D-RB5. Not yet a dependency — grep of `pyproject.toml` confirms absence. |
| `pymupdf` | `>=1.24` installed, existing | Parse ICH/FDA rulebook PDFs | REUSE verbatim — `parse.pdf.extract_pdf` already emits the unified dict shape D-RB2 requires all rulebook corpora to converge on. No new PDF library needed. |
| stdlib `xml.etree.ElementTree` | Python 3.11+ stdlib | Parse eCFR Title-21 XML | `[VERIFIED: this session]` — fetched and parsed real eCFR XML (part 211, 96,680 bytes) with zero errors using plain `ElementTree`. The DIVn/HEAD/P/AUTH/SOURCE schema is simple and non-namespaced; **no new dependency (lxml) is justified** unless a later need (XPath, entity handling) proves otherwise. |
| `pyyaml` | `>=6.0` installed, existing | Requirement-index versioned data (D-RI1(3)) | REUSE — already the format `ingest/registry/ctd_families.yaml` uses; same `lru_cache`-over-`yaml.safe_load` loader pattern applies directly. |
| `httpx` | `>=0.27` installed, existing | eCFR / regulations.gov build-time API clients | REUSE — already the client used throughout `src/databricks/*.py`; mirror `llm/client.py`'s existing retry/backoff idiom for these new external calls. |
| `faiss-cpu` | `>=1.8` pinned, **1.14.3 installed** `[VERIFIED: python import, this session]` | Dense leg of the local ephemeral `search_corpus` index | Already present but **only in the `dev` dependency-group** (`pyproject.toml` comment: "local dev only -- vector search fallback"). D-RB5 makes this a PRODUCTION path (every `search_corpus` call), not a dev fallback — see Common Pitfalls #9 and Assumptions Log A5. |
| `sentence-transformers` | `>=3.0` pinned, **5.6.0 installed** | Local `bge-m3` embedding (harness-pinned per D-RB5/D-RB6) | REUSE verbatim — `retrieval/vector_search.py::embed_texts`/`embed_query` already implements local-vs-Databricks dispatch; no changes needed for Phase 2's dense leg. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `databricks-sdk` / `databricks-sql-connector` | `>=0.30` / `>=3.1`, existing | Databricks-side rulebook serving (D-RB2) | REUSE — `src/databricks/delta.py`'s `_run_sql`/`_table`/`_escape` helpers already implement the SQL Statement Execution API pattern; extend, don't replace. |
| `pydantic` | `>=2.7` pinned, **2.13.4 installed** (matches PyPI latest exactly) | Tool arg schemas + `emit_finding` input model + requirement-index entry model | REUSE — `llm/structured.py::schema_for_databricks` already sanitizes pydantic JSON schemas for Databricks-strict mode (flattens `anyOf`, strips `pattern`, forces `additionalProperties:false`); the SAME sanitizer applies to the 6 new tool-arg schemas Phase 3 will bind. |
| `git-lfs` | **3.7.1 installed locally** `[VERIFIED: this session]` | Large vendored-snapshot files (D-RB2 "LFS if large") | Available but **no `.gitattributes` exists yet**. Given the measured file sizes (below), LFS is optional for the eCFR/ICH/FDA XML/PDF set (all sub-1.5MB) but reasonable for the 4.04MB xlsm precedent file. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Databricks Vector Search (D-RB2, locked) | LanceDB | Explicitly superseded by CONTEXT.md — the user's Databricks infra is already provisioned and confirmed reachable (SQL API + embeddings both live this session). Do not revisit. |
| Databricks Vector Search Admin API (blocked — 403 scope) | Client-side cosine over a Delta embeddings table, exactly as `databricks/vector.py::_search_embeddings_table` already implements | The CURRENT token cannot create/query a literal Vector Search index (`vector-search` scope missing). The existing fallback path is proven working end-to-end (SQL read + local cosine) and satisfies D-RB6's backend-agnostic contract — use it as the v1 Databricks-side leg while the scope question is resolved (see Open Questions #1). |
| stdlib `ElementTree` for eCFR XML | `lxml` | Only worth adding if XPath queries or malformed-entity handling become necessary; not justified by anything observed in the live-fetched eCFR XML this session. |
| RRF fusion hand-written (~10 lines) | LanceDB's built-in RRF/cross-encoder rerank | N/A once LanceDB is superseded — the formula itself (`score = Σ 1/(k+rank_i)`, k=60) is public and trivial; no library needed for the ephemeral local index. |
| `bge-reranker-v2-m3` (Claude's discretion, deferred by default) | Skip reranking entirely for v1 | CONTEXT.md explicitly defers this to "only if measured to help" — do not build it speculatively; SC4's recall@k measurement is the trigger, not a design decision made now. |

**Installation:**
```bash
# New dependency (D-RB5 lexical leg) — not present in pyproject.toml today
uv add rank-bm25   # pins to >=0.2.2

# faiss-cpu promotion decision (Assumption A5) — confirm with the team whether
# search_corpus's runtime install path includes the `dev` dependency-group;
# if not, move faiss-cpu from [dependency-groups].dev to [project].dependencies.
```

**Version verification (this session, live):**
```
$ curl -s https://pypi.org/pypi/rank-bm25/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"
0.2.2
$ python3 -c "import openai, pydantic, faiss, sentence_transformers; print(openai.__version__, pydantic.VERSION, faiss.__version__, sentence_transformers.__version__)"
2.43.0 2.13.4 1.14.3 5.6.0
```

## Architecture Patterns

### System Architecture Diagram

Two flows: a **build-time** flow (this phase's rulebook ingestion, run once/versioned) and a **runtime** flow (the tool contracts this phase defines, called by Phase 3's loop — Phase 2 owns the contracts, not the caller).

```
BUILD-TIME (one-time, versioned manual run — D-RB2)
══════════════════════════════════════════════════

  eCFR versioner/v1 REST ──┐
  (?part= scoped fetch)    │
                            ├──▶ rulebook/ecfr/title-21/part-{n}.xml
  database.ich.org PDFs ───┤     rulebook/ich/{Q2-R2,Q3A-R2,...}.pdf      ──┐
  (eval-scoped, D-RB1)      │     rulebook/fda/{guidance}.pdf                │
                            │     rulebook/precedents/ANDA-TDDS-...xlsm       │
  regulations.gov v4 ──────┘     (D-PREC audit target)                       │
  (eval-scoped FDA guidances)                                                │
                                                                              ▼
                                                          src/rulebook/build.py
                                                                │
                                    ecfr_parse.py (NEW, XML→dict)  │  extract_pdf (existing, PDF→dict)
                                                                ▼
                                     src/ingest/ substrate (REUSED, unchanged):
                                     serialize_document → normalize → mint_span
                                     → build_table_index
                                                                │
                              canonical text + span-IDs + table index + metadata
                                                                │
                          ┌─────────────────────────────────────┴─────────────────────────────┐
                          ▼                                                                     ▼
              local SQLite + FAISS + BM25                                     Databricks Delta + (Vector
              (D-RB6 offline/CI backend —                                     Search OR client-side-cosine
              tests/harness ALWAYS use this)                                  fallback — D-RB2 runtime backend)
                          │                                                                     │
                          └─────────────────────────┬───────────────────────────────────────────┘
                                                      │  config switch (D-RB6): SAME chunks/span-IDs,
                                                      │  tool contract never changes
                                                      ▼
RUNTIME (Phase 3's agent loop calls these — Phase 2 owns the contract, not the caller)
════════════════════════════════════════════════════════════════════════════════════

  submission directory ──▶ ingest.ingest_corpus() [Phase 1] ──▶ per-submission CorpusIndex
                                                                        │
                                                                        ▼
                                                    src/tools/search_corpus.py
                                                    LOCAL ephemeral: FAISS dense + BM25 lexical (D-RB5)
                                                                        │
                                            results: {span_id, doc_id, snippet}, cat -n annotated (D-GRAN)
                                                                        │
                        ┌───────────────────────────────────────────────┼───────────────────────────────┐
                        ▼                                               ▼                                ▼
              open_doc / get_section                          follow_reference                 read_guideline(citation?)
              → open_span() [Phase 1,                          (same-doc only;                  omit → RULES-05 enumerate
                reused verbatim]                                typed pending-Phase-4            (server-resolved from
                                                                 stub cross-doc)                   corpus manifest, D-RI2)
                        │                                               │                          give → bounded rule text
                        └───────────────────────────────────────────────┴────────────┬─────────────┘
                                                                                       ▼
                                                          retrieval ledger (issued span-IDs, D-GRAN)
                                                          + COST-04 read-dedup ("still current" stub
                                                            on repeat read of the same span)
                                                                                       │
                                                                                       ▼
                                       emit_finding({submission_span_id, rule_span_id, verdict, requirement_id?})
                                                                                       │
                                            re-open BOTH via open_span() — submission_span_id against
                                            the CORPUS store, rule_span_id against the RULEBOOK store (D-EF1)
                                            byte-exact? unique? issued this session? correct store?
                                                          │                                │
                                                         YES                               NO
                                                          ▼                                ▼
                                              Fault created (schemas/faults.py)   typed self-correcting error
                                                                                  (never a bare failure — TOOLS-03)
```

### Recommended Project Structure

```
rulebook/                            # NEW top-level, GIT-TRACKED (must NOT be data/ or Sample Data/ — see Pitfall #1)
├── manifest.yaml                    # RULES-04: {source, citation, version/date, license, url, sha256} per file
├── ecfr/title-21/
│   ├── part-210.xml  part-211.xml  part-314.xml  part-320.xml
│   └── part-600.xml  part-601.xml  part-11.xml    # ~826 KB total, measured this session
├── ich/                              # eval-scoped (D-RB1) — see Rulebook Sourcing cluster below for the exact set
│   ├── Q2-R2_Guideline_2023-11-30.pdf
│   ├── Q3A-R2_Guideline_2006-10-25.pdf
│   ├── Q3B-R2_Guideline_2006-06-02.pdf
│   └── Q6A_Guideline_1999-10-06.pdf
├── fda/                              # eval-scoped (D-RB1)
│   └── analytical-procedures-and-methods-validation-for-drugs-and-biologics.pdf
└── precedents/
    └── ANDA-TDDS-Deficiency-Roadmap.xlsm   # 4.04 MB — D-PREC audit target, senior reviewer

src/tools/                           # NEW — Phase 2's agent-facing tool layer (D-21: tools built ON the substrate)
├── search_corpus.py                  # TOOLS-01/D-RB5 — hybrid FAISS+BM25 over the per-submission corpus
├── open_doc.py                       # TOOLS-01
├── get_section.py                    # TOOLS-01/TOOLS-04 — narrow-your-range on oversized
├── follow_reference.py               # TOOLS-01/D-FR — same-doc stub, typed cross_document_resolution_pending_phase_4
├── read_guideline.py                 # TOOLS-01/D-RI2 — citation param toggles enumerate|fetch
├── emit_finding.py                   # TOOLS-03/D-EF1 — the grounding gate
├── ledger.py                         # D-GRAN retrieval ledger (issued span-IDs) + COST-04 dedup
└── errors.py                         # typed self-correcting rejection sentinels (mirrors ParseFailed + HashMismatch)

src/rulebook/                        # NEW — rulebook build + serving (distinct from src/ingest's DOCUMENT substrate)
├── ecfr_parse.py                     # eCFR XML → the SAME {pages,blocks,tables} dict extract_pdf/extract_docx emit
├── build.py                          # one-time versioned build script (D-RB2)
├── edges.py                          # generic edge table (D-RB3): (src_id,dst_id,edge_type,provenance_span_id)
├── requirement_index.py              # RULES-05 schema + D-RI1 loader gate + LLM drafter (via llm.structured)
└── requirement_index.yaml            # versioned, human-reviewed data (D-RI1(3))

src/retrieval/                       # EXTEND existing
├── vector_search.py                   # existing, reused verbatim
├── knowledge_base.py                   # existing, precedent-retrieval seam / D-PREC audit start
├── lexical.py                          # NEW — rank-bm25 wrapper, the lexical leg
└── hybrid.py                           # NEW — RRF fusion (Claude's discretion, D-RB5-bounded)
```

### Pattern 1: Two-Backend Contract Behind One Interface (D-RB6)

**What:** The rulebook/precedent store has exactly one Python-level interface (`read_guideline`, the requirement-index enumerate call, the edge-table lookup); a config switch (mirrors `config.Settings.is_databricks`, already established) selects whether that interface resolves against the local SQLite+FAISS+BM25 build or Databricks Delta+Vector Search — the CALLER never branches.
**When to use:** Every rulebook-facing function in `src/tools/` and `src/rulebook/`.
**Example:**
```python
# Source: mirrors the EXISTING pattern in src/retrieval/vector_search.py::embed_texts
# and src/databricks/vector.py::search_similar — both already dispatch on s.is_databricks.
# The rulebook store extends the SAME established dispatch, not a new one.
def rulebook_search(query: str, top_k: int = 10) -> list[RuleChunk]:
    s = get_settings()
    if s.is_databricks:
        return _rulebook_search_databricks(query, top_k)   # Delta + (Vector Search | cosine fallback)
    return _rulebook_search_local(query, top_k)             # SQLite + FAISS + BM25 (D-RB6 — tests/harness land HERE)
```

### Pattern 2: Selection-Not-Authoring via the Retrieval Ledger (D-GRAN, TOOLS-02)

**What:** Every tool that returns text annotates it with inline span-IDs (the `cat -n` pattern) and records each issued ID in a per-run ledger; `emit_finding` (and any future tool consuming a span-ID) validates membership in that ledger before calling `open_span`, so an ID the model never actually saw this session is rejected before the byte-exactness check even runs.
**When to use:** Every tool result; the ledger is a single per-agent-run object threaded through all 6 tool calls.
**Example:**
```python
# Source: this session's synthesis of D-GRAN + the existing open_span/HashMismatch primitive
# (src/ingest/anchors.py, read in full this session).
def annotate_inline(canonical_text: str, spans: list[SpanID], ledger: RetrievalLedger) -> str:
    """Render text with inline span-ID markers the model can SEE and select — never compute."""
    out = []
    for i, span in enumerate(spans):
        ledger.record(span)  # issued THIS session -- the ledger IS the "selected, not authored" proof
        out.append(f"[{span.doc_id}:{span.start}:{span.end}] {canonical_text[span.start:span.end]}")
    return "\n".join(out)

class RetrievalLedger:
    """Per-agent-run scoped (Security Domain V3) -- issued span-IDs are unique by construction (D-GRAN)."""
    def __init__(self) -> None:
        self._issued: set[tuple[str, int, int]] = set()

    def record(self, span: SpanID) -> None:
        self._issued.add((span.doc_id, span.start, span.end))

    def was_issued(self, span: SpanID) -> bool:
        return (span.doc_id, span.start, span.end) in self._issued
```

### Pattern 3: Typed Self-Correcting Tool Rejection (mirrors `ParseFailed` + `HashMismatch`)

**What:** Two typed-error conventions already exist in this codebase (`schemas.llm.ParseFailed` — a pydantic sentinel returned alongside/instead of a result; `ingest.anchors.HashMismatch` — a raised exception carrying the expected/actual values). Phase 2's tool-boundary rejections (TOOLS-03, D-RI2(2), D-EF1) should pick ONE of these two shapes consistently, not invent a third.
**When to use:** Every tool-argument validation failure that must be self-correcting (i.e., the error message itself tells the calling model what to fix).
**Example:**
```python
# Source: mirrors schemas/llm.py::ParseFailed exactly (read this session) -- same sentinel shape,
# new domain. Chosen over the exception shape (HashMismatch) because tool-call rejections need to
# flow back to the CALLING MODEL as a message, not unwind a Python call stack.
class ToolRejected(BaseModel):
    tool: str                    # which tool rejected the call
    reason_code: str             # "not_byte_exact" | "not_unique" | "not_retrieved_this_session"
                                  # | "wrong_store" | "family_not_in_registry" | "range_too_large"
    reason: str                  # human-readable, self-correcting ("re-fetch via get_section, then retry")
    hint: str = ""                # what a correct retry looks like
```

### Anti-Patterns to Avoid

- **Truncating an oversized `get_section` result:** TOOLS-04 explicitly forbids this ("a truncated result costs ~25k tokens, an error costs ~100 bytes"). Return a narrow-your-range `ToolRejected`, never a silently-cut string.
- **Extracting the ICH copyright notice per-PDF at ingest time:** verified this session that 4 of the 5 eval-scoped ICH guidelines carry NO notice text at all — a per-document extraction approach will silently produce chunks with an empty `license` field for exactly the guidelines this eval set needs most. Store the notice as an applied constant (Code Examples below), not a scrape target.
- **Constructing a rulebook-source URL from runtime input:** D-RB2's sources are a fixed, reviewed, date-pinned manifest built ONCE. Never let `read_guideline`'s `citation` parameter (or any tool arg) reach an HTTP fetch — it only ever resolves against the already-built local/Databricks store (also the SSRF mitigation, Security Domain below).
- **Embedding a live corpus manifest, document count, or rule list inside a tool's JSON schema:** this doesn't visibly break anything THIS phase (COST-01's cache-stability invariant is Phase 6), but Phase 2 defines the tool schemas Phase 3+6 will bind — writing a schema whose `description` or `enum` embeds dynamic per-run content now creates a Phase 6 regression later. Keep all 6 tool-arg schemas static; dynamic content (which families are applicable, what's in the corpus) goes in tool RESULTS, never tool SCHEMAS.
- **Treating "didn't find a Vector Search endpoint" as "Databricks Vector Search doesn't work":** verified this session that Model Serving (chat + embeddings) and the SQL Statement API both work fully — only the Vector Search Admin API is scope-blocked. Don't over-conclude from one blocked surface.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| BM25 lexical scoring (Retrieval) | A custom TF-IDF/BM25 implementation | `rank-bm25` 0.2.2 `BM25Okapi` | Verified current, stable, single-purpose, exactly matches D-RB5's spec. |
| Span integrity re-verification (Tools / Emit Gate) | A new hash-check/reopen function for rulebook spans | `ingest.anchors.open_span` (Phase 1, REUSE verbatim) | D-RB2 requires rulebook chunks to "pass the same emit gate as a submission quote" — literally the same primitive, not a parallel one. |
| eCFR/ICH/FDA PDF parsing (Rulebook Sourcing) | A new PDF text extractor | `parse.pdf.extract_pdf` (existing, PyMuPDF) | ICH/FDA sources are ordinary PDFs; D-RB2 requires ALL rulebook corpora to parse through the Phase-1 substrate. |
| eCFR XML parsing (Rulebook Sourcing) | A hand-rolled regex XML scraper | stdlib `xml.etree.ElementTree` + a thin `ecfr_parse.py` adapter | Verified live this session — the DIVn/HEAD/P schema parses cleanly with zero errors; the ONLY new code is the adapter that reshapes it into the existing dict contract. |
| JSON-schema generation for 6 tool signatures (Tools) | Hand-written JSON Schema dicts | `model_json_schema()` + `llm.structured.schema_for_databricks` (existing) | Already hardened for Databricks-strict mode; reuse verbatim. |
| Typed tool-rejection errors (Emit Gate / Requirement Index) | A third, novel exception hierarchy | Mirror `ParseFailed` (sentinel) or `HashMismatch` (exception) — pick one shape, see Pattern 3 | Two established conventions already exist; a third fragments the codebase's "typed, self-correcting error" ethos. |
| Requirement-index storage (Requirement Index) | A new bespoke YAML loader | Mirror `ingest.registry`'s `lru_cache`-over-`yaml.safe_load` pattern | D-05's registry is explicitly the same `{id, one-line trigger}` shape by design — both docs say so. |
| Edge-table storage (Rulebook Sourcing / Requirement Index) | A graph database | SQLite, mirroring `ingest/store.py`'s `sqlite3.Row` + JSON-column convention | D-RB3 specs a generic 4-column table — one `CREATE TABLE` + parameterized inserts. |
| Retry/backoff for eCFR/regulations.gov calls (Rulebook Sourcing) | A new retry decorator/library | Mirror `llm/client.py`'s existing `_MAX_RETRIES`/exponential-backoff + `Retry-After`-header handling | Already hardened for exactly this class of external call. |
| Hybrid dense+lexical fusion (Retrieval) | A fusion micro-library | Reciprocal Rank Fusion, ~10 lines: `score = Σ 1/(k+rank_i)`, k=60 | RRF is public, well-known, parameter-light; a library is unjustified overhead once LanceDB is superseded. |
| USP `<1226>`/`<88>` full-text ingestion (Requirement Index) | Scraping or vendoring USP-NF chapter text | Citation-string-only references (no `read_guideline` full text) | USP-NF is **proprietary, subscription-gated content**, confirmed NOT public domain `[VERIFIED: usp.org/legal-notices, WebSearch]` — RULES-01..05 correctly names only eCFR/ICH/FDA as ingestible; USP stays a citation the requirement index/verdicts can NAME but not fetch. |

**Key insight:** every "don't hand-roll" in this phase resolves to "reuse a Phase-1 or `llm/` primitive that already exists and was already hardened for a slightly different input" — the only genuinely NEW code this phase needs is the eCFR-XML adapter, the 6 tool functions' own logic, the BM25/RRF glue, and the requirement-index loader gate. Everything else is composition.

## Common Pitfalls

> Organized by cluster: **Tools** · **Rulebook Sourcing** · **Retrieval** · **Requirement Index** · **Emit Gate** · **Cost/Dedup**.

### Pitfall 1 (Rulebook Sourcing): `data/` AND `Sample Data/` are both blanket-`.gitignore`d today
**What goes wrong:** D-RB2 requires the vendored snapshot (eCFR XML, ICH/FDA PDFs) and the precedent xlsm to be **committed**. `.gitignore:31-33` currently excludes `data/*` (except `data/README.md`) and the entire `Sample Data/` directory. A build script that writes into either location will produce files that `git status` never sees — the "reproducible, offline, byte-stable citations" promise silently fails with no error.
**Why it happens:** `data/` was deliberately gitignored in Phase 0/1 for corpus/build artifacts (`data/README.md`: "Intentionally empty in git"); `Sample Data/` was gitignored because it was originally just local sample input, not source-of-truth.
**How to avoid:** Use a NEW top-level directory (`rulebook/`, recommended above) that is NOT covered by either ignore rule. Copy (not move, to avoid disrupting whatever currently reads `Sample Data/`) the xlsm into `rulebook/precedents/`.
**Warning signs:** `git status` shows nothing after running the build script; `git log --follow rulebook/...` is empty after a commit that should have added files.

### Pitfall 2 (Rulebook Sourcing): GovInfo bulk-XML path is stale
**What goes wrong:** CLAUDE.md documents `govinfo.gov/bulkdata/ECFR/title-21` as a fallback bulk-download path. Live-fetched this session: HTTP 200 but the page body is titled **"Govinfo Bulkdata Service Error."**
**Why it happens:** GovInfo restructured or deprecated this exact bulk-data URL scheme since CLAUDE.md's research; the eCFR `versioner/v1` REST API has since become the maintained path.
**How to avoid:** Use ONLY the `versioner/v1` REST endpoints (`structure`, `full`) — both fully verified live this session, including the `?part=` scoping discovery below.
**Warning signs:** A build script that "succeeds" (200 status) but produces HTML instead of XML — always validate `Content-Type`/parse the response as XML before writing to disk.

### Pitfall 3 (Rulebook Sourcing): eCFR's `full` endpoint 404s on "today"
**What goes wrong:** `GET .../full/2026-07-30/title-21.xml` (today's date at research time) returned 404. `GET .../full/2026-07-29/title-21.xml` returned 200.
**Why it happens:** eCFR editions are published per amendment cycle; not every calendar date has a corresponding published edition. The correct date to use is `up_to_date_as_of` from `GET /api/versioner/v1/titles.json` (confirmed this session: Title 21's value was `2026-07-29`, one day behind wall-clock).
**How to avoid:** The build script must query `/titles.json`, extract `up_to_date_as_of` for title 21, and use THAT date in every subsequent `full`/`structure` call — never construct the date from `datetime.now()`.
**Warning signs:** Intermittent 404s that "used to work" — a strong sign wall-clock date is being used instead of the queried edition date.

### Pitfall 4 (Rulebook Sourcing): ICH's copyright notice is ABSENT from most of the eval-scoped guidelines
**What goes wrong:** A per-PDF text-extraction approach to satisfy RULES-02's "store the required copyright acknowledgment with each chunk" will find the notice in `Q2(R2)` (2023) and fail to find it in `Q3A(R2)` (2006), `Q3B(R2)` (2006), and `Q6A` (1999) — verified this session via full-text scan (zero matches for "copyright"/"legal notice"/"public license" in any of the three older PDFs).
**Why it happens:** ICH began embedding a standard "Legal notice" paragraph in documents from roughly the 2015 "ICH Harmonised Tripartite Guideline" → "International Council for Harmonisation" restructuring onward. Older Step-4 guidelines predate that convention.
**How to avoid:** Store the notice text as an applied constant (see Code Examples) attached to every ICH chunk regardless of source-PDF content, not as a per-document scrape result. This is the conservative/safe direction (over-attributing, never under-attributing).
**Warning signs:** A rulebook chunk with `source="ich"` and an empty/missing `license` field is a correctness bug, not a data gap — it means the per-PDF extraction silently found nothing.

### Pitfall 5 (Rulebook Sourcing): USP citations in the existing codebase are NOT ingestable
**What goes wrong:** `agents/detection/checklists.py` and `catalog.py` already reference USP `<88>`, `<87>`, `<661>`; the eval set's item A-09 cites USP `<1226>` directly. A well-intentioned implementer might try to vendor USP-NF chapter text alongside eCFR/ICH/FDA.
**Why it happens:** USP-NF "looks" like the same class of regulatory reference as eCFR/ICH, but is a **paid, copyrighted, subscription product** (`usp.org/legal-notices`: "not in the public domain... unauthorized websites... committing copyright violations") — confirmed via WebSearch this session.
**How to avoid:** RULES-01..05 correctly name only eCFR/ICH/FDA as ingestible sources. The requirement index and verdicts may CITE a USP chapter by name/number (a string), but `read_guideline` cannot fetch USP full text — document this scope boundary explicitly so it isn't rediscovered as a "missing feature" later.
**Warning signs:** A requirement-index entry whose `citation` field is a USP chapter number but whose `rule_span_id` resolves nowhere — this is EXPECTED (citation-only), not a bug, but must be distinguishable from a broken eCFR/ICH/FDA citation.

### Pitfall 6 (Retrieval): Databricks Vector Search Admin API is scope-blocked
**What goes wrong:** `GET /api/2.0/vector-search/endpoints` with the configured token returns **403 "Provided access token does not have required scopes: vector-search"** — verified this session. D-RB2's prose names "Databricks Vector Search" as the serving layer; literally provisioning that infra is currently blocked.
**Why it happens:** The token's scopes were granted for SQL Statement Execution + Model Serving (both confirmed fully working, including chat completions on `databricks-meta-llama-3-3-70b-instruct` and embeddings on `databricks-bge-large-en`), but not Vector Search administration.
**How to avoid:** Ship the ALREADY-WORKING `databricks/vector.py::_search_embeddings_table` client-side-cosine pattern (SQL read of a Delta embeddings table + local cosine) as the v1 Databricks-side rulebook query path — it is functionally the retrieval capability D-RB2 wants, even though it isn't the literal Vector Search product. Escalate the scope question as a separate, non-blocking track (Open Questions #1).
**Warning signs:** Any task that assumes `POST .../vector-search/indexes/{name}/query` will simply work — verify token scope FIRST (command in Environment Availability below) before committing to that code path in a plan.

### Pitfall 7 (Retrieval): `faiss-cpu` is a dev-only dependency but D-RB5 makes it a runtime one
**What goes wrong:** `pyproject.toml` lists `faiss-cpu>=1.8` only under `[dependency-groups].dev` with the comment "local dev only -- vector search fallback." D-RB5 makes FAISS the dense leg of `search_corpus` for EVERY run, including whatever eventually runs Phase 3's agent loop in a non-dev environment.
**Why it happens:** At the time that pin was added, FAISS genuinely was dev-only (a fallback for local testing of the deficiency_kb precedent search). D-RB5 changes its role without anyone having revisited the pin.
**How to avoid:** Flag for the planner: either promote `faiss-cpu` to `[project].dependencies`, or confirm (and document) that every environment that runs `search_corpus` always installs the `dev` group.
**Warning signs:** `ImportError: No module named 'faiss'` in any environment that installed only base dependencies.

### Pitfall 8 (Requirement Index): eCFR's `hierarchy_metadata` carries a literal unsubstituted placeholder
**What goes wrong:** Every `hierarchy_metadata` JSON blob in the fetched XML contains `"path":"/on/_SUBSTITUTE_DATE_/title-21/..."` — the literal string `_SUBSTITUTE_DATE_`, not a real date. Verified this session on live-fetched part 211 XML.
**Why it happens:** Appears to be an unsubstituted template variable in eCFR's own XML-generation pipeline (an upstream quirk, not something in this project's control).
**How to avoid:** Never parse a real date out of `hierarchy_metadata.path`. The `citation` field within the same blob IS correctly formed (e.g., `"21 CFR Part 211"`, `"21 CFR 211.1"`) — use that, plus the outer request date (from `/titles.json`'s `up_to_date_as_of`) for RULES-04's `version/date` metadata field.
**Warning signs:** A stored rule chunk with a `_SUBSTITUTE_DATE_` literal anywhere in its metadata is a sign the placeholder leaked through unvalidated.

### Pitfall 9 (Emit Gate / Cost-Dedup): the retrieval ledger must be per-run, not global
**What goes wrong:** If the ledger of "issued span-IDs this session" (D-GRAN) is implemented as module-level/global state rather than passed per agent-run, one run's issued IDs would validate against a DIFFERENT run's `emit_finding` call — defeating the "was never retrieved this session" check TOOLS-03 requires.
**Why it happens:** The simplest implementation of a cache/ledger is a global dict; this is fine for the D-05 registry (static, shared, read-only) but wrong for a session-scoped trust boundary.
**How to avoid:** Thread an explicit ledger instance through every tool call for one agent run (constructor-injected or passed as an argument), never a module-global. See Security Domain (V3) below.
**Warning signs:** A test that runs two "sessions" sequentially in the same process and finds cross-session span-ID leakage.

### Pitfall 10 (Tools): regulations.gov's `downloads.regulations.gov` attachment links can 403 outside the full API flow
**What goes wrong:** A directly-constructed `downloads.regulations.gov/{documentId}/attachment_N.pdf` URL, fetched standalone (no query params, no key), returned 403 this session even though the SAME id's `content.pdf` and the search→document→attachments flow worked when driven through the API with `api_key`.
**Why it happens:** Unclear from outside (possibly session/referer expectations, possibly the specific attachment had been superseded) — flagged honestly as unverified root cause, not asserted.
**How to avoid:** Prefer a direct `fda.gov/files/.../<name>.pdf` URL when the guidance has one (verified stable and reliable this session for the one eval-relevant guidance checked) over the regulations.gov attachment pipeline; reserve the regulations.gov flow for guidances that ONLY exist in docket/attachment form (no direct fda.gov publish URL).
**Warning signs:** A build script that treats a 403 on a `downloads.regulations.gov` URL as fatal — retry through the full documents→attachments API flow (with `api_key`) before concluding the source is unavailable.

## Code Examples

Verified patterns from this session's live investigation and the existing codebase:

### eCFR fetch — correct date + part-scoping (RULES-01)
```python
# Source: verified live this session (2026-07-31). The `?part=` query param scopes the fetch
# to ONE part -- part 211 alone is 96,680 bytes vs. the multi-MB whole-title pull CLAUDE.md implied.
import httpx

def fetch_ecfr_part(part: str, title: str = "21") -> tuple[str, str]:
    """Return (xml_text, edition_date). Uses the QUERIED up_to_date_as_of, never wall-clock (Pitfall 3)."""
    with httpx.Client(timeout=60.0) as client:
        titles = client.get("https://www.ecfr.gov/api/versioner/v1/titles.json").json()
        edition_date = next(t["up_to_date_as_of"] for t in titles["titles"] if t["number"] == int(title))
        resp = client.get(
            f"https://www.ecfr.gov/api/versioner/v1/full/{edition_date}/title-{title}.xml",
            params={"part": part},
        )
        resp.raise_for_status()
        return resp.text, edition_date

# Verified byte sizes this session, edition_date=2026-07-29, parts D-RB1 names:
#   210=11,723B  211=96,680B  314=446,325B  320=64,563B  600=85,630B  601=100,795B  11=20,474B
#   total ≈ 826,190 bytes (~0.8 MB) for the FULL D-RB1 "CFR-complete" set of drug-relevant parts.
```

### ICH copyright notice — applied constant, not per-PDF extraction (RULES-02, Pitfall 4)
```python
# Source: read VERBATIM from database.ich.org/sites/default/files/E6_R2_Addendum.pdf, page 2
# ("Legal notice" paragraph), and confirmed present (via pdftotext full-text scan) in
# ICH_Q2(R2)_Guideline_2023_1130.pdf. Confirmed ABSENT (zero "copyright" hits, full-text scan)
# in Q3A_R2__Guideline.pdf (2006), Q3B(R2) Guideline.pdf (2006), and Q6A Guideline.pdf (1999).
ICH_LEGAL_NOTICE = (
    "This document is protected by copyright and may be used, reproduced, incorporated "
    "into other works, adapted, modified, translated or distributed under a public license "
    "provided that ICH's copyright in the document is acknowledged at all times. In case of "
    "any adaption, modification or translation of the document, reasonable steps must be "
    "taken to clearly label, demarcate or otherwise identify that changes were made to or "
    "based on the original document. Any impression that the adaption, modification or "
    "translation of the original document is endorsed or sponsored by the ICH must be avoided. "
    "The document is provided \"as is\" without warranty of any kind. In no event shall the "
    "ICH or the authors of the original document be liable for any claim, damages or other "
    "liability arising from the use of the document. The above-mentioned permissions do not "
    "apply to content supplied by third parties. Therefore, for documents where the copyright "
    "vests in a third party, permission for reproduction must be obtained from this copyright holder."
)

def ich_chunk_metadata(citation: str, guideline_date: str, url: str) -> dict:
    """RULES-04 metadata shape, applied uniformly regardless of whether the SOURCE PDF embeds
    its own copy of this notice (most eval-scoped guidelines do not -- Pitfall 4)."""
    return {
        "source": "ich", "citation": citation, "version": guideline_date,
        "license": ICH_LEGAL_NOTICE, "url": url,
    }
```

### eCFR public-domain status — statutory citation (RULES-01)
```text
# Source: 17 U.S.C. § 105, verified live via Cornell Law LII this session:
# "Copyright protection under this title is not available for any work of the
#  United States Government..."
# eCFR/Title 21 text is authored by federal agencies (FDA/HHS) publishing under the
# Federal Register Act -- standard public-domain status for CFR text follows directly.
```

### regulations.gov v4 — search → document → attachment (RULES-03)
```python
# Source: verified live this session with the public DEMO_KEY (a real api.data.gov key
# is needed for the actual ingestion build -- DEMO_KEY's rate limit is far below 1,000/hr).
import httpx

def fetch_fda_guidance_attachment(document_id: str, api_key: str) -> list[dict]:
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"https://api.regulations.gov/v4/documents/{document_id}",
            params={"include": "attachments", "api_key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        # fileFormats[].fileUrl -> https://downloads.regulations.gov/{id}/content.pdf or attachment_N.pdf
        formats = data["data"]["attributes"].get("fileFormats") or []
        for inc in data.get("included", []):
            formats.extend(inc.get("attributes", {}).get("fileFormats") or [])
        return formats

# For a guidance with a stable direct fda.gov URL (verified this session for the single most
# eval-relevant guidance), PREFER that path over the API (Pitfall 10):
#   https://www.fda.gov/files/drugs/published/Analytical-Procedures-and-Methods-Validation-for-Drugs-and-Biologics.pdf
#   -> HTTP 200, 137,005 bytes, valid PDF v1.5.
```

### Requirement-index entry — mirrors the D-05 registry shape (RULES-05)
```python
# Source: mirrors ingest/registry/ctd_families.yaml's {id, label, applicability_trigger} shape
# exactly (both CONTEXT.md docs state this is deliberate). The 9 candidate v1 entries below are
# a DIRECT lift of agents/detection/checklists.py::_VALIDATION_REQUIRED's existing keys -- this
# hardcoded dict is the ready-made source material for RULES-05's "method-validation" family.
class RequirementEntry(BaseModel):
    id: str                      # e.g. "Q2-SPECIFICITY"
    family: str                  # must exist in ingest.registry.family_ids() (D-RI1 loader gate)
    citation: str                 # e.g. "ICH Q2(R2) 3.2" -- must resolve to a real rulebook chunk
    trigger: str                  # one-line applicability trigger (same shape as D-05)
    provenance_span_id: SpanID    # the rule span-ID that JUSTIFIES this entry (D-RI1 loader gate)

# Candidate v1 "method-validation" family entries (source: checklists.py _VALIDATION_REQUIRED,
# read this session) -- drafting + human review is a PLAN/BUILD-time task, not decided here:
#   specificity, linearity, limit of detection (LOD), limit of quantitation (LOQ), precision,
#   accuracy / recovery, robustness / ruggedness, system suitability, solution stability
```

### Requirement-index loader gate (D-RI1(1))
```python
# Source: this session's synthesis, mirroring ingest.registry's load-time validation posture
# and reusing open_span verbatim -- a mis-drafted entry fails at LOAD, not at review-time attention.
def load_requirement_index(path: str) -> list[RequirementEntry]:
    entries = [RequirementEntry.model_validate(e) for e in yaml.safe_load(open(path))]
    for e in entries:
        if e.family not in ingest.registry.family_ids():
            raise ValueError(f"{e.id}: family {e.family!r} not in D-05 registry")
        # provenance span-ID must re-open byte-exact against the RULEBOOK store (mirrors D-EF1(2))
        open_span(e.provenance_span_id, rulebook_nt_for(e.provenance_span_id.doc_id), e.provenance_span_id.doc_id)
    return entries
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---------------|-------------------|---------------|--------|
| Hardcoded keyword checklist (`checklists.py::_VALIDATION_REQUIRED`, string-search presence/absence) | Rulebook-grounded requirement index with real citations + span-IDs (RULES-05) | This phase | The existing checklist becomes the DRAFT source material for the new index, not dead code — a direct upgrade path, not a rewrite. |
| ICH Q2(R1) "Text and Methodology" | **ICH Q2(R2)**, merged with Q14, adopted at Step 4 **1 November 2023** `[CITED: WebSearch cross-referenced against ECA Academy + EMA mirror + fda.gov guidance page, MEDIUM-HIGH]` | November 2023 | The existing codebase's `catalog.py`/`checklists.py` reference "ICH Q2" generically (no revision number) — not a contradiction, but the plan should source the CURRENT Q2(R2) PDF, not an R1 copy, when building the rulebook. |
| Single hardcoded FAISS index over the 500-row `deficiency_kb` (the only retrieval path today) | Two-index architecture: ephemeral local per-submission index (`search_corpus`) + persistent rulebook/precedent index (`read_guideline`) | This phase | `retrieval/knowledge_base.py`'s existing precedent search becomes ONE of several retrieval surfaces, not the only one. |
| LanceDB recommended for the reference corpus (CLAUDE.md, prior research) | Databricks Delta + Vector Search (D-RB2, locked) | Discussion phase (2026-07-31) | Confirmed this session: the user's Databricks workspace already has the SQL/embedding infra live; only the Vector Search Admin API scope is blocked (Pitfall 6). |
| Whole-document / full-corpus context stuffing (explicit anti-feature, PROJECT.md) | Just-in-time retrieval via span-ID tools (Anthropic's documented "effective context engineering" pattern — already cited in CLAUDE.md's Sources) | Ongoing project design principle | This phase is the concrete implementation of that principle for the FDA/ICH rulebook specifically. |

**Deprecated/outdated:**
- GovInfo bulk-XML path (`govinfo.gov/bulkdata/ECFR/title-21`) — CLAUDE.md's documented fallback is stale; use the eCFR REST API exclusively.
- ICH Q2(R1) as "the" analytical-validation guideline — superseded by Q2(R2)/Q14 (Nov 2023); still worth knowing R1 existed since older submissions/literature may cite it, but new rulebook ingestion should target R2.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|-----------------|
| A1 | ich.org's site-wide `/page/legal-mentions` terms impose no ADDITIONAL restriction on the pre-2015 tripartite-era guidelines (Q3A(R2)/Q3B(R2)/Q6A/Q1A(R2)) beyond the standard ICH copyright-acknowledgment grant read verbatim from newer documents | Rulebook Sourcing (RULES-02) | If a stricter site-wide term exists, storing/redistributing those 4 guidelines' full text could exceed the license grant. LOW likelihood (ICH's mission is guideline dissemination) but genuinely UNVERIFIED — ich.org is a JS-rendered SPA this session's tools could not execute. |
| A2 | Applying the newer (post-2015) ICH "Legal notice" text uniformly to ALL vendored ICH chunks — including the 4 older, notice-less guidelines — is the correct/safe compliance posture | Rulebook Sourcing (RULES-02) | If wrong, this is over-inclusive attribution, not under-inclusive — the safer failure direction, but still an assumption pending A1's resolution. |
| A3 | FDA's own republication of an ICH-authored guideline (e.g. a `fda.gov/.../q2r2...` mirror) carries the same ICH-copyright obligation as the `database.ich.org` original | Rulebook Sourcing (RULES-02/03 overlap) | Minor compliance nuance either way — mitigated by the recommendation to always source ICH text from `database.ich.org` specifically, avoiding the FDA mirror for ICH-authored content. |
| A4 | The 1,000 requests/hour api.data.gov default applies to a newly-registered regulations.gov key without additional approval steps | Rulebook Sourcing (RULES-03) | If the real default is lower/tiered, the build script's pacing is too aggressive — LOW risk since D-RB1 scopes FDA sourcing to a handful of eval-relevant guidances (single-digit request counts). |
| A5 | `faiss-cpu`'s presence in the `dev` dependency-group is sufficient for it to be installed wherever `search_corpus`'s dense leg eventually runs (tests, harness, and Phase-3 runtime) | Retrieval (D-RB5) | If a non-dev install path is ever used, `search_corpus` breaks with `ImportError` at runtime — empirically true TODAY (confirmed installed in the active `.venv`), not proven for every future install path. |
| A6 | ICH Q2(R2)'s Step-4 adoption date is 1 November 2023 (the ICH Assembly action date), distinct from the `2023_1130` (30 November 2023) date embedded in its `database.ich.org` filename, which is likely a site-publish date rather than a second adoption event | State of the Art | If conflated, a build script might record the wrong "version/date" metadata field (RULES-04) — low practical impact (both dates are within the same month), but worth a single human confirmation glance at the PDF's own cover page before locking the metadata value. |

## Open Questions

1. **Can the Databricks token's scope be elevated to include `vector-search`, or should v1 ship on the client-side-cosine fallback?**
   - What we know: SQL Statement Execution API and Model Serving (chat + embeddings) are fully live with the current token; the Vector Search Admin API returns 403 for the SAME token.
   - What's unclear: whether a differently-scoped token is obtainable from whoever administers this Databricks workspace, or whether that's out of reach for this milestone.
   - Recommendation: plan the rulebook Delta tables + client-side-cosine query path as the v1 Wave-1 deliverable (already proven working); treat literal Vector Search endpoint creation as a follow-up task explicitly gated on confirming token scope BEFORE any plan commits engineering time to it.

2. **Where should the vendored snapshot live relative to `Sample Data/` and `data/`?**
   - What we know: both existing directories are blanket-gitignored; a new `rulebook/` directory sidesteps both ignore rules cleanly.
   - What's unclear: whether the team has a preference for negating the `Sample Data/` ignore rule for just the one xlsm file instead of duplicating it into `rulebook/precedents/`.
   - Recommendation: use the new `rulebook/` directory (cleaner, avoids negation-pattern fragility); copy (don't move) the xlsm so nothing that currently reads from `Sample Data/` breaks.

3. **What does ich.org's rendered legal-mentions page actually say?**
   - What we know: the PER-DOCUMENT notice text (verified verbatim, twice).
   - What's unclear: the site-wide terms (JS-rendered, unreachable by this session's tools).
   - Recommendation: a one-time human check (open the URL in an actual browser) before the ICH build script ships; record the confirmation as a line in `rulebook/manifest.yaml`.

4. **Exact requirement-index entry count/wording for v1?**
   - What we know: the source material is clearly identified — the existing 9-key `_VALIDATION_REQUIRED` checklist (method-validation family) plus a handful of Q3A/Q3B/Q6A impurity-specification-completeness entries and 2-3 21 CFR 211.194 documentation-completeness entries, all directly traceable to the 14 `absence_of_evidence` items in the Phase-0 eval set.
   - What's unclear: exact final wording/citations — D-RI1 explicitly requires human review before merge, so this is intentionally NOT settled at research time.
   - Recommendation: the plan should schedule LLM-drafting (via `llm.structured`) against this identified source material, followed by the senior-reviewer session D-RI1(3) requires.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|-----------|
| eCFR `versioner/v1` REST API | RULES-01 | ✓ | live, title-21 edition `2026-07-29` | GovInfo bulk XML (STALE — do not use, Pitfall 2) |
| `database.ich.org` (PDF hosting) | RULES-02 | ✓ | — | — |
| `ich.org` site-wide legal-mentions page | RULES-02 (compliance confirmation only) | ✗ (JS-rendered SPA, tool-inaccessible) | — | One-time manual browser check (Open Question #3) |
| regulations.gov API v4 | RULES-03 | ✓ (DEMO_KEY tested; real key needed for the build) | v4 | fda.gov direct guidance PDFs (preferred where available, Pitfall 10) |
| `api.data.gov` API key (real, non-DEMO) | RULES-03 build script | ✗ (not yet obtained — free signup) | — | `DEMO_KEY` (low rate limit, spike-testing only) |
| Databricks SQL Statement Execution API | D-RB2 (Delta tables) | ✓ | verified live this session | — |
| Databricks Model Serving — embeddings (`databricks-bge-large-en`) | D-RB5 Databricks-side dense leg | ✓ | verified live, 1024-dim, normalized | local `bge-m3` via sentence-transformers (already the D-RB6 default) |
| Databricks Model Serving — chat (`databricks-meta-llama-3-3-70b-instruct`, `databricks-qwen35-122b-a10b`, `databricks-qwen3-next-80b-a3b-instruct`) | D-RI1 LLM-drafting (via `llm.structured`) | ✓ | verified `READY` this session | — |
| Databricks Vector Search Admin API | D-RB2 literal serving layer | **✗ — 403, token lacks `vector-search` scope** | — | client-side cosine over a Delta embeddings table (`databricks/vector.py::_search_embeddings_table`, already implemented) |
| Unity Catalog Volume `defpredict.main.artifacts` | optional PDF mirror | ✓ (exists, currently empty) | — | not required — git (`rulebook/`) is the source of truth per D-RB2 |
| `git-lfs` | D-RB2 vendored-snapshot mechanics | ✓ | 3.7.1 | plain git (all vendored files are small enough that LFS is optional — see Standard Stack) |
| `rank-bm25` (PyPI) | D-RB5 lexical leg | ✗ (not yet installed) | latest `0.2.2` | none needed — trivial pure-Python install |
| `faiss-cpu` | D-RB5 dense leg (local) | ✓ (via `dev` group) | 1.14.3 | see Assumption A5 / Pitfall 7 |

**Missing dependencies with no fallback:**
- Databricks Vector Search Admin API scope — blocks literal endpoint/index creation. The SQL/embeddings-table fallback is a legitimate substitute under D-RB6's backend-agnostic contract, but is not what D-RB2's prose literally names — the planner must decide explicitly (see Open Question #1), not silently default.
- ich.org site-wide terms page — blocks independent verification of Assumptions A1/A2; does NOT block building the rulebook (the per-document notice text is sufficient to proceed), only blocks the last mile of compliance certainty.

**Missing dependencies with fallback:**
- regulations.gov real API key — `DEMO_KEY` unblocks a build-time spike/test today; a real key (free, ~5-minute signup at open.gsa.gov) should land before the actual ingestion build script runs at scale.
- `rank-bm25` — trivial to add, zero risk.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ with pytest-asyncio (`asyncio_mode=auto`) `[VERIFIED: pyproject.toml]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `pythonpath=["src"]`, `testpaths=["tests"]`) |
| Quick run command | `pytest tests/tools/ tests/rulebook/ -x -q` |
| Full suite command | `pytest` then `python -m evals.run gate` then `python -m evals.run retrieval-gate` (NEW subcommand, see Wave 0 Gaps) |
| Estimated runtime | quick: seconds (offline, no network/Databricks — mirrors Phase 1's `tests/ingest/conftest.py` offline-fixture discipline); full incl. SC4 recall@k over the ~35-item Phase-0 eval set: well under a minute (local FAISS/BM25 only, D-RB6) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|---------------|
| TOOLS-01 | 5 tools return identifiers/snippets; only `get_section` returns bounded full text | unit | `pytest tests/tools/test_contracts.py::test_tools_return_bounded_results -x` | ❌ Wave 0 |
| TOOLS-02 | Every result carries a span-ID; re-opening reproduces byte-for-byte | unit | `pytest tests/tools/test_span_selection.py::test_reopen_byte_exact -x` | ❌ Wave 0 |
| TOOLS-03 | **Fabrication-rejection test:** a deliberately fabricated/altered quote CANNOT be emitted | unit | `pytest tests/tools/test_emit_finding.py::test_fabricated_quote_cannot_be_emitted -x` | ❌ Wave 0 |
| TOOLS-03 | Non-unique quote, never-retrieved-this-session span, and rule-less finding are each independently rejected | unit | `pytest tests/tools/test_emit_finding.py::test_rejects_not_unique_and_not_in_ledger_and_no_rule_citation -x` | ❌ Wave 0 |
| TOOLS-04 | Over-large `get_section` fails narrow-your-range, never truncates; oversized results persist+preview+handle | unit | `pytest tests/tools/test_oversized_results.py::test_oversized_fails_not_truncates -x` | ❌ Wave 0 |
| RULES-01 | eCFR parts ingest through the Phase-1 substrate; span-IDs re-open byte-exact | unit | `pytest tests/rulebook/test_ecfr_parse.py::test_ecfr_part_ingests_and_reopens -x` | ❌ Wave 0 |
| RULES-02 | Every ICH chunk carries the exact copyright acknowledgment, INCLUDING chunks from notice-less source PDFs (Pitfall 4) | unit | `pytest tests/rulebook/test_ich_ingest.py::test_ich_chunk_carries_notice_even_when_source_pdf_lacks_it -x` | ❌ Wave 0 |
| RULES-03 | Eval-scoped FDA guidances ingest with metadata | unit | `pytest tests/rulebook/test_fda_ingest.py::test_fda_guidance_ingests -x` | ❌ Wave 0 |
| RULES-04 | Every rule chunk stores `{source, citation, version/date, license, url}`; `_SUBSTITUTE_DATE_` never leaks (Pitfall 8) | unit | `pytest tests/rulebook/test_metadata.py::test_every_chunk_has_required_metadata_and_no_placeholder_date -x` | ❌ Wave 0 |
| RULES-05 | Enumerate mode resolves applicability server-side from the corpus manifest; rejects free-text profiles/unregistered families | unit | `pytest tests/rulebook/test_requirement_index.py::test_enumerate_resolves_from_manifest_and_rejects_invalid_family -x` | ❌ Wave 0 |
| RULES-05 | **Ground-truth traceability test:** every Phase-0 `absence_of_evidence` deficiency's submission profile FIRES ≥1 requirement-index entry | eval | `pytest tests/rulebook/test_requirement_index.py::test_every_absence_family_deficiency_has_firing_entry -x` | ❌ Wave 0 |
| SC4 (D-SC4) | recall@k over the Phase-0 answer spans; exact-identifier subset (batch numbers, table labels) passes HARD | eval | `python -m evals.run retrieval-gate` (NEW subcommand) | ❌ Wave 0 |
| COST-04 | Re-retrieving an unchanged span returns a "still current" stub; hit rate reported | unit | `pytest tests/tools/test_read_dedup.py::test_repeat_read_returns_stub_and_reports_hit_rate -x` | ❌ Wave 0 |
| D-FR | `follow_reference` resolves same-doc refs; cross-doc returns the typed pending-Phase-4 stub, never silent/faked | unit | `pytest tests/tools/test_follow_reference.py::test_same_doc_resolves_cross_doc_typed_stub -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/tools/ tests/rulebook/ -x -q` (offline, no network/Databricks — D-RB6 extended to "no live internet either" for unit tests specifically)
- **Per wave merge:** `pytest` (full) + `python -m evals.run gate` + `python -m evals.run retrieval-gate`
- **Phase gate:** full suite green **and** the SC4 baseline is committed (`src/evals/baseline/retrieval_recall.json`, same shape as the existing `recall_by_family.json`) **and** the exact-identifier HARD subset passes 100% before `/gsd-verify-work`
- **Max feedback latency:** ~30 seconds (quick suite, entirely offline per D-RB6)

### SC4 Recall@k Measurement — design note
The Phase-0 eval set's 35 labeled deficiencies (28 `mvr1381` + 4 `minispec`, both non-held-out; 3 `spec32s41`, held out) each carry an `evidence_anchor` string — this is the natural "known answer span" SC4 measures recall against. Concretely: for each non-held-out deficiency, run `search_corpus` with a query derived from its `title`, and check whether a result within the top-k contains (or resolves to a span overlapping) the `evidence_anchor` text in the CORRECT `doc_id`. The **exact-identifier HARD subset** (D-SC4(i)) is the subset whose `evidence_anchor` is a bare identifier — e.g. `"11477"` (C-01, a table cell value), `"389"` (B-03), `"0.15"` (C-02) — these must retrieve their home document via the **lexical (BM25) leg**, not just the semantically-nearest chunk; a numeric-identifier query is exactly where dense embeddings are weakest and exact lexical matching is strongest, which is precisely why D-RB5 locks in a lexical leg at all.

### Emit-Gate Fabrication-Rejection Test — design note
Per TOOLS-03 and the ROADMAP's explicit SC5 language ("a test proves a deliberately fabricated quote CANNOT be emitted, rather than being emitted and caught later"): construct a `SpanID` whose `hash` field does not match `short_hash(canonical[start:end], normalizer_version)` for the actual stored canonical text (i.e., alter one character of a real retrieved quote before constructing the `emit_finding` call), and assert `open_span` raises `HashMismatch` (reused verbatim, Phase 1) and that `emit_finding` surfaces this as a typed `ToolRejected`, never a raw exception leak and never a silently-created `Fault`.

### Requirement-Index Ground-Truth Traceability Test — design note
Mirrors the MS-04 lesson (the instrument must enumerate what the eval actually contains): for each of the 14 `absence_of_evidence`-family items across the Phase-0 eval set (11 in `mvr1381`, 1 in `minispec`, 2 in the held-out `spec32s41`), derive that document's content-classified submission profile, call the requirement-index enumerate mode against it, and assert at least one returned entry's `trigger` text plausibly corresponds to what that specific deficiency is about (e.g. B-02's "no supporting data for LOD/LOQ" should fire the `Q2-LOD`/`Q2-LOQ` entries). A `mvr1381` item with zero firing entries means the v1 requirement-index draft is incomplete BY MEASUREMENT — exactly the failure mode D-RI1(2) exists to catch before it reaches production.

### Wave 0 Gaps
- [ ] `tests/tools/conftest.py` — shared fixtures: a fake `RetrievalLedger`, a synthetic `CorpusIndex` + rulebook-store double, mirrors `tests/ingest/conftest.py`'s offline/`no_llm` fixture pattern
- [ ] `tests/rulebook/conftest.py` — a tiny FIXTURE eCFR XML snippet + fixture ICH/FDA PDF stub, so unit tests never hit the network (D-RB6 extended: tests never touch the live internet either, not just Databricks)
- [ ] `src/evals/baseline/retrieval_recall.json` — the committed SC4 baseline artifact (same shape as `recall_by_family.json`)
- [ ] `evals/run.py retrieval-gate` subcommand (new; mirrors the existing `score`/`gate`/`run` subcommands' "record, never crash" pattern)
- [ ] `rank-bm25` added to `pyproject.toml` + lockfile
- [ ] `rulebook/` top-level directory created + `.gitignore` confirmed to NOT cover it (Pitfall 1)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|---------------------|
| V2 Authentication | No (this phase) | No new user-facing auth surface; Databricks token handling reuses the established `.env`/`config.Settings` pattern unchanged. |
| V3 Session Management | **Yes** | The retrieval ledger (D-GRAN's "issued this session") IS a session-scoped trust boundary — must be constructed per-agent-run and threaded explicitly through all 6 tool calls, never module-global state (Pitfall 9). |
| V4 Access Control | No (this phase) | Internal tool-calling only; no multi-tenant boundary introduced. |
| V5 Input Validation | **Yes** | pydantic v2 models for all 6 tool signatures + `emit_finding`; family/profile filters validated against D-05 registry membership (typed rejection on non-member, D-RI2(2)); every span-ID input is RE-VERIFIED via `open_span`/`HashMismatch`, never trusted as given by the calling model. |
| V6 Cryptography | Partial (unchanged scope) | Span-ID hash = blake2b, explicitly integrity-only per its own docstring ("a checksum for integrity/drift, not an authentication boundary") — correct scope for this use, no upgrade needed. Databricks token stays `.env`-only (gitignored), never logged in full (existing `structlog` convention already truncates error strings to ~200-300 chars — extend the same discipline to any new rulebook-build logging). |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Fabricated/hallucinated quote passed to `emit_finding` | Tampering / Spoofing | TOOLS-03's re-open-and-compare gate (D-EF1) — byte-exact re-open against the correct store, typed rejection on mismatch. |
| A rule span-ID passed where a submission span belongs, or vice versa | Tampering | D-EF1(2) store-membership validation — a rule span must resolve in the RULEBOOK store, a submission span in the CORPUS store; cross-store resolution is a typed rejection, not a pass. |
| Prompt injection via LLM-drafted requirement-index entries (D-RI1) | Tampering | The loader gate (D-RI1(1)) validates EVERY entry's provenance span-ID + citation + family/profile tags at LOAD time — a drafted entry citing a non-existent rulebook chunk or unregistered family fails to load regardless of how the drafting LLM was manipulated. |
| Path traversal / zip-slip when the rulebook build script writes vendored files by remote-derived names | Tampering / Elevation | Mirror Phase 1's `ingest/limits.py::safe_resolve` guard for the new `src/rulebook/build.py` — never derive a write path from unsanitized remote content (Content-Disposition filenames, URL segments); use the FIXED, reviewed `rulebook/manifest.yaml` paths instead. |
| SSRF via a dynamically-constructed rulebook source URL | Info Disclosure / Elevation | Not applicable by design, and must STAY that way (Anti-Patterns above): D-RB2's URLs are statically pinned in a build-time-only manifest; `read_guideline`'s `citation` parameter and every other runtime tool arg must NEVER reach an HTTP fetch — they only resolve against the already-built local/Databricks store. |
| Credential leakage (Databricks token) via error messages/build logs | Info Disclosure | Extend the existing truncate-and-never-echo `structlog` convention (`error=str(exc)[:200]`) to the new `src/rulebook/build.py` and `src/tools/` logging. |
| Over-broad `read_guideline` citation range triggering an oversized/costly result | DoS (cost) | TOOLS-04's narrow-your-range error (never truncate) — same discipline as `get_section`. |
| Unbounded regulations.gov/eCFR request volume during the build script | DoS (self-inflicted, cost) | Mirror `llm/client.py`'s existing retry/backoff idiom; the eval-scoped FDA/ICH set is small (single-digit to low-double-digit document count) so this is a low-probability concern, but pacing discipline should be reused, not re-invented. |

## Sources

### Primary (HIGH confidence — verified live this session)
- eCFR `versioner/v1` API — `titles.json`, `structure/{date}/title-21.json`, `full/{date}/title-21.xml?part={n}` for parts 210/211/314/320/600/601/11 — https://www.ecfr.gov/api/versioner/v1/
- 17 U.S.C. § 105 (Cornell LII) — https://www.law.cornell.edu/uscode/text/17/105
- ICH E6(R2) Addendum PDF — legal notice read verbatim from page 2 — https://database.ich.org/sites/default/files/E6_R2_Addendum.pdf
- ICH Q2(R2)/Q3A(R2)/Q3B(R2)/Q6A/Q1A(R2) PDFs — fetched + full-text scanned for notice presence/absence — https://database.ich.org/sites/default/files/ICH_Q2(R2)_Guideline_2023_1130.pdf , .../Q3A_R2__Guideline.pdf , .../Q3B(R2)%20Guideline.pdf , .../Q6A%20Guideline.pdf , .../Q1A(R2)%20Guideline.pdf
- regulations.gov API v4 — live `documents` search + detail + `include=attachments` — https://api.regulations.gov/v4/documents
- api.data.gov Developer Manual — rate limit "Hourly Limit: 1,000 requests per hour" — https://api.data.gov/docs/developer-manual/
- FDA direct guidance PDF — https://www.fda.gov/files/drugs/published/Analytical-Procedures-and-Methods-Validation-for-Drugs-and-Biologics.pdf
- FDA guidance index page (schema.org metadata) — https://www.fda.gov/regulatory-information/search-fda-guidance-documents/analytical-procedures-and-methods-validation-drugs-and-biologics
- Live Databricks workspace (SQL Statement API, Model Serving, UC Volumes, Vector Search Admin API) — `aip-amn-dev.cloud.databricks.com` (internal, this session)
- PyPI JSON API — `rank-bm25`, `openai`, `pydantic` — https://pypi.org/pypi/rank-bm25/json
- USP legal notice — https://www.usp.org/legal-notices/usp-on-unauthorized-websites
- Codebase (read in full this session): `src/ingest/{anchors,corpus,manifest,tables,normalize,classify,serialize,store,__init__}.py`, `src/ingest/registry/{__init__,ctd_families.yaml}`, `src/retrieval/{vector_search,knowledge_base}.py`, `src/databricks/{vector,delta,serving}.py`, `src/llm/{client,structured}.py`, `src/schemas/{documents,faults,llm}.py`, `src/agents/detection/{catalog,checklists,oracles,render,selection}.py`, `src/evals/{run,dataset/*}.py`, `pyproject.toml`, `.gitignore`, `.env`/`.env.example`, `01-CONTEXT.md`, `01-VALIDATION.md`

### Secondary (MEDIUM confidence — WebSearch verified with an official/authoritative source)
- ICH Q2(R2)/Q14 Step-4 adoption date (1 November 2023) — WebSearch cross-referencing ECA Academy + EMA/FDA mirror pages
- Docket `FDA-2015-N-0007` as the finalized "Analytical Procedures and Methods Validation for Drugs and Biologics" guidance's comment docket — WebSearch (Federal Register title match)

### Tertiary (LOW confidence — flagged, not otherwise used)
- None retained as load-bearing — every WebSearch-only finding in this research was either upgraded to Primary via direct fetch/read, or demoted to the Assumptions Log (A1-A6) with an explicit risk statement rather than presented as fact.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified live (PyPI for `rank-bm25`; installed-package introspection for `openai`/`pydantic`/`faiss`/`sentence-transformers`)
- Rulebook sourcing (eCFR): HIGH — every endpoint live-tested this session with real HTTP responses, byte counts, and a genuine bug found (GovInfo bulk path) and worked around
- Rulebook sourcing (ICH): HIGH on mechanics (URLs, PDF sizes, notice text read directly from source, notice absence confirmed via full-text scan) / MEDIUM on the site-wide-terms gap (Assumptions A1/A2)
- Rulebook sourcing (FDA/regulations.gov): HIGH — API mechanics, key requirement, rate limit, and the single most eval-relevant guidance all live-verified end-to-end
- Databricks serving: HIGH on what's confirmed working (SQL API, embeddings, chat, table schemas/row counts, UC Volumes) / confirmed BLOCKED (not "unknown") on Vector Search Admin API specifically
- Architecture/tooling patterns: HIGH — directly derived from CONTEXT.md's already-locked, highly specific contracts plus existing codebase conventions (`open_span`, `ParseFailed`, `structured.py`) read in full this session
- Pitfalls: HIGH — nearly all sourced from live verification (`.gitignore` conflicts, stale GovInfo path, ICH notice absence, Vector Search scope block) rather than speculation

**Research date:** 2026-07-31
**Valid until:** External API mechanics (eCFR/regulations.gov) — 30 days, stable government APIs. ICH/FDA specific guideline URLs — 90 days (guideline PDFs revise on a multi-year cadence; watch for another Q2-style revision). **Databricks token-scope finding — re-verify AT PLANNING TIME**, not treated as durable: re-run the Environment Availability verification commands (`GET /api/2.0/vector-search/endpoints`) before Wave 1 starts, since scope could change if the team requests elevation.

---

## RESEARCH COMPLETE

**Phase:** 2 - Retrieval, Navigation Tools & Rulebook
**Confidence:** HIGH

### Key Findings
- **eCFR is fully live and cheaper than assumed:** the `versioner/v1` API's `?part=` scoping fetches exactly the 7 drug-relevant parts D-RB1 names for ~826 KB total (not a multi-MB whole-title pull); the GovInfo bulk-XML fallback CLAUDE.md documented is stale ("Bulkdata Service Error") — use the REST API exclusively, and always source the edition date from `/titles.json`'s `up_to_date_as_of`, never wall-clock (it 404s on unpublished dates).
- **ICH's copyright notice is verified verbatim but NOT universal:** read directly from source PDFs, the exact acknowledgment text is present in post-2015 documents (Q2(R2)) but **completely absent** from the pre-2015 guidelines this eval set needs most (Q3A(R2), Q3B(R2), Q6A) — apply the notice as a stored constant to every ICH chunk, don't try to extract it per-PDF.
- **regulations.gov mechanics fully verified**, including the exact FDA guidance ("Analytical Procedures and Methods Validation for Drugs and Biologics") the eval set's method-validation-heavy content needs, which resolves to a stable direct `fda.gov/files/...pdf` URL bypassing the API entirely.
- **Databricks Vector Search Admin API is scope-blocked (403)** on the currently configured token, even though SQL Statement Execution and Model Serving (chat + embeddings, including Llama 3.3 70B and both Qwen variants) are fully live — plan the v1 rulebook query path on the already-proven client-side-cosine fallback, not a blocked API surface.
- **Both `data/` and `Sample Data/` are blanket-`.gitignore`d today** — D-RB2's "commit the vendored snapshot" and "commit the xlsm precedent" requirements need a NEW tracked directory (`rulebook/`, recommended) or they will silently no-op.
- **USP citations already in the codebase (`<88>`, `<1226>`) are NOT ingestable** — USP-NF is confirmed proprietary/subscription content, not public domain; the requirement index may cite USP by name but cannot fetch its text via `read_guideline`.

### File Created
`/Users/DEVDESAI1/dev/deficiency-chatbot/.planning/phases/02-retrieval-navigation-tools-rulebook/02-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Every version live-verified (PyPI + installed-package introspection) |
| Rulebook Sourcing (eCFR/ICH/FDA) | HIGH | Every URL/endpoint fetched live this session; exact byte sizes, notice text, and one stale-path bug all directly observed |
| Databricks Serving | HIGH (confirmed-working) / HIGH (confirmed-blocked) | Not a guess either way — SQL+Serving tested working, Vector Search tested blocked with an explicit 403 reason |
| Architecture/Tooling Patterns | HIGH | Derived from CONTEXT.md's locked contracts + full reads of the exact primitives (`open_span`, `ParseFailed`, `structured.py`) being reused |
| Pitfalls | HIGH | Nearly all empirically triggered this session, not speculated |

### Open Questions
1. Databricks Vector Search token-scope elevation — resolve or explicitly plan around the fallback (Open Questions #1 in the doc).
2. `rulebook/` vs. `Sample Data/`-negation for the vendored snapshot's exact placement (Open Questions #2).
3. ich.org's JS-rendered site-wide terms page — needs one human browser check (Open Questions #3).
4. Exact requirement-index entry wording — intentionally left to the D-RI1 human-review step, not research (Open Questions #4).

### Ready for Planning
Research complete. Planner can now create PLAN.md files for Phase 2, organized around the six requirement-clusters (tools / rulebook-sourcing / retrieval / requirement-index / emit-gate / cost) this document uses throughout.
