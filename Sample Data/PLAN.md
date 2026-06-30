# AutoGen-DocIntel — Project Plan

> **Status:** Planning (no implementation yet).
> **Companion doc:** the architecture-vision markdown in this folder — treat its *figures* as
> aspirational; this PLAN.md is the ground-truth build plan.

---

## 1. What we are building

An **on-premise multi-agent tool** for pharmaceutical CMC regulatory review. An analyst uploads a
submission document (PDF / DOCX / eCTD / XML / CMC); the system:

1. Parses it into a canonical structured form.
2. Retrieves relevant historical deficiencies + guidance from a **Knowledge Graph (Neo4j) + vector
   index (FAISS)**.
3. Predicts likely **FDA CMC deficiencies**, each **tied to cited evidence**.
4. Scores risk and recommends remediation.
5. Routes the report to a **human analyst** who verifies / corrects / rejects it.
6. Writes **only human-confirmed facts** back into the KG, so the system's knowledge grows from
   verified production use.

### Core value (the one thing that must never fail)

> **Every predicted deficiency traces to cited evidence, and only human-confirmed facts enter the
> knowledge base.**

This is both the product's trust guarantee and (later) the research thesis. When any tradeoff arises,
this wins.

### End goal

**Working tool first, paper later.** Phases 1–5 deliver a deployable internal tool. The research
contribution (public FDA-483 proxy benchmark + faithfulness metrics) is a *separate later milestone*,
not a driver of the initial build.

---

## 2. Locked decisions

These are settled. Changing one requires explicit discussion.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Build for scale from day one.** Schema, ETL, and retrieval must handle large volumes; the shared `.xlsm` is a *development subset* of a much larger confidential corpus. | User: "lots and lots of data." No hard-coded product lists, no row-count assumptions, re-runnable ingestion. |
| D2 | **Use the real, rich taxonomy** — `CMC Section × Deficiency Type × Severity` — NOT the doc's 3 fixed dimensions (Stability/Impurity/Validation). | The richer taxonomy can always *roll up* to a 3-dimension summary view; the reverse loses data. |
| D3 | **HITL ingest = human-confirmed facts only.** The AI's original (possibly wrong) guess is never written to the KG. | Keeps the graph clean ground truth. |
| D4 | **Quarantine unverified/rejected docs.** They are stored for audit but NEVER used to ground future predictions. | Prevents the system from learning from its own unchecked output (feedback-loop drift). |
| D5 | **`verification_status` filter lives in every retrieval query.** All KG/FAISS reads filter to `confirmed` (+ `seed`). | Single structural guard that makes the self-enriching loop safe. |
| D6 | **Single user-facing input. No separate dataset-upload door.** Seed once; thereafter grow only via verified docs. | The doc's separate "training data" input is redundant. |
| D7 | **Format-aware parsing → one canonical `ParsedDocument` schema.** Agents downstream are format-agnostic. | eCTD/XML carry native CTD structure (exploit it); PDF/DOCX use extraction + OCR fallback. |
| D8 | **Private model serving only — no third-party API on the public internet.** Submission content must never leave the org's tenant/VPC. Bare on-prem GPUs OR a private, governed managed workspace both satisfy this; a public LLM API does not. | Confidentiality + 21 CFR Part 11. |
| D9 | **Provenance + idempotency on every KG write.** Each node records source-doc hash, who verified, when. Re-ingesting a doc must not duplicate nodes. | Auditability is the theme; duplicates corrupt retrieval. |
| D10 | **Databricks is the deployment substrate.** ETL → Jobs/Workflows. Vector index → Databricks Vector Search (Unity Catalog–governed) as the default, with FAISS retained as a portable fallback for local dev. Models → Model Serving (provisioned throughput) with MLflow lineage. Data → Unity Catalog with row-level access controls. Neo4j sits next to the workspace via private link or co-located VPC. | The workspace is already provisioned with governance, lineage, and IAM. Reusing it beats reinventing those. The private workspace preserves D8. |
| D11 | **Role-specialized adapters via LoRA on ONE shared base — not N independently fine-tuned full models.** Each agent role gets a lightweight adapter; the base is served once, adapters multiplex per request. Adapters are added **only when offline evals show prompting + RAG underperforms** — not by default. | Cuts serving cost ~30× vs full per-role models, keeps governance simple (one base lineage, N small adapters), and avoids the classic trap of fine-tuning where prompting already works. |

### Open items (resolve at the relevant phase, not now)

- **O1 — exact `.xlsm` schema:** real columns/values to be confirmed when Phase 1 starts (confidential).
  Working assumption from the dev subset: `ANDA # | Product | Dosage Form | CMC Section |
  Deficiency Type | Cohort Year | Severity/Category | Deficiency (text) | Deficiency Response`.
- **O2 — base LLM choice:** the architecture-vision doc names Mistral-7B as a candidate; revisit
  against current (2026) open-weight options at Phase 3, and confirm against what Model Serving
  supports for provisioned throughput. Not a blocker now.
- **O3 — research/benchmark:** deferred to a post-tool milestone (does a public FDA-483 benchmark
  already exist? check then).
- **O4 — fine-tuning need per role:** Parser is structural — likely rules + small extraction model,
  no FT. Retrieval is embedding-based — fine-tune the *embedding model* (contrastive on
  deficiency↔guidance pairs), not the LLM, if anything. Risk Assessor and Recommender are the only
  realistic LLM-FT candidates, and only after Phase 3's eval shows them underperforming a strong
  prompted baseline. Resolve at Phase 4.5.

---

## 3. Architecture (concrete, corrected against reality)

```
        ┌──────────── SINGLE USER-FACING INPUT (no separate dataset door — D6) ────────────┐
        │   Upload: PDF │ DOCX │ eCTD │ XML │ CMC                                            │
        └───────────────────────────────┬──────────────────────────────────────────────────┘
                                        ▼
   FORMAT-AWARE PARSER AGENTS (D7) ──► canonical ParsedDocument schema
                                        │
                                        ▼
   KNOWLEDGE LAYER (read, status-gated — D5)            AGENT ORCHESTRATION (AutoGen)
   ┌───────────────────────────────┐                   ┌──────────────────────────────────┐
   │ Neo4j KG  (Product/Deficiency/ │  ◄── retrieval ───│ Supervisor → Parser → Retrieval  │
   │   Section/Resolution/Guidance) │                   │   → Risk Assessor → Recommender  │
   │ Vector index — Vector Search  │                   │ every claim cites its evidence   │
   │   (UC) or FAISS (D10)         │                   └───────────────┬──────────────────┘
   │ status ∈ {seed, confirmed,     │                                   │
   │           quarantined}         │                                   │   role-routed
   └───────────────▲───────────────┘                                   ▼  per request
                   │                              ┌──────────────────────────────────┐
                   │                              │ Model Serving (D10)              │
                   │                              │  one base LLM + LoRA adapters    │
                   │                              │  per role (D11), routed by       │
                   │                              │  the supervisor                  │
                   │                              └───────────────┬──────────────────┘
                   │                                              ▼
                   │                              RISK REPORT (per-claim + evidence)
                   │                                                   │
                   │  confirmed-only, idempotent,                      ▼
                   │  provenance-stamped write (D3,D9)     ┌──────────────────────────────┐
                   │                                       │ HUMAN-IN-THE-LOOP            │
                   └───────────────────────────────────────│  verify / correct / reject  │
                                                           └──────────────┬───────────────┘
                          status=quarantined (D4)  ◄────────── reject/unverified
                          corrections log (κ signal) ◄───────── every correction diff
```

---

## 4. Phased roadmap

Sequential. Each phase ends with something demonstrable.

### Phase 1 — Data + KG foundation  *(START HERE)*
**Goal:** A real, scalable Neo4j KG + FAISS index built from the deficiency data, with status &
provenance on every node.
- Re-runnable ETL: `.xlsm` → normalized records → graph + vector index.
- Node/edge schema on the **real taxonomy** (D2), designed for volume (D1).
- `verification_status` and `provenance` on every node; `seed` for the initial load.
- FAISS index over deficiency text + guidance, sized for large corpora.
**Done when:** the dev-subset loads end-to-end; a Cypher query returns deficiencies filtered by
`verification_status`; re-running ETL is idempotent (no dupes — D9).
**Highest-leverage phase** — a wrong schema here poisons everything downstream.

### Phase 2 — Multi-format ingestion
**Goal:** Any supported format → one canonical `ParsedDocument`.
- Format-aware parsers; eCTD/XML use native CTD structure; PDF/DOCX extraction + OCR fallback.
- Thin end-to-end slice: upload → parse → structured echo (no assessment yet).
**Done when:** all target formats produce the same canonical schema; CTD sections identified.

### Phase 3 — Retrieval + cited risk assessment
**Goal:** Status-gated retrieval + per-claim, evidence-cited risk assessment.
- KG + FAISS fused retrieval, **always** filtered to `confirmed`/`seed` (D5).
- Risk Assessor emits Pydantic-structured claims; **each claim names its evidence** (KG path /
  passage). Ungrounded claims are suppressed, not surfaced.
- Risk scoring over the real taxonomy.
**Done when:** a doc produces a structured report where every claim has a traceable citation.

### Phase 4 — HITL verification loop
**Goal:** Human verify/correct/reject → confirmed-only self-enriching KG.
- Analyst UI: per-claim confirm / correct / reject.
- Confirmed → idempotent, provenance-stamped KG write (D3, D9).
- Rejected/unverified → quarantine (D4); corrections logged separately (κ signal for later).
**Done when:** confirming a doc visibly enriches retrieval for the *next* doc; quarantined data is
provably excluded from grounding.

### Phase 4.5 — Role-specialized adapters  *(conditional, eval-gated)*
**Goal:** LoRA adapters per agent role where evals justify them — not by default.
- Build per-role eval sets from the Phase 4 confirmed corpus + the κ correction log.
- Run prompted baseline vs LoRA-adapted variant on Risk Assessor first, Recommender second. Ship
  the adapter only when its win is statistically meaningful **and** the D5 citation-faithfulness
  invariant doesn't regress (no extra hallucinated grounding).
- Embedding model: contrastive fine-tune on deficiency↔guidance pairs from the same confirmed
  corpus. Cheap; biggest retrieval lift usually lives here.
- Training on Mosaic AI Model Training (LoRA-SFT); every run tracked in MLflow; winning adapters
  registered in Unity Catalog with the dataset version they were trained on.
- Serving: one base LLM endpoint on Model Serving, adapters loaded per request, routed by the
  supervisor agent (`role → adapter_id`). Rollback to prompted base = one config flip.
**Done when:** at least one role has a measurably better adapter in production, citations still
ground, and the adapter pipeline is reproducible from Unity Catalog dataset → MLflow run → registered
adapter → serving endpoint.
**Skip-if:** Phase 4 evals show prompted base is already at the citation-faithfulness ceiling.
Don't fine-tune to fine-tune.

### Phase 5 — Hardening + deployment on Databricks
**Goal:** Production-ready inside the existing workspace (D10).
- Unity Catalog tables for `ParsedDocument`, deficiency records, corrections log; row/column-level
  access for analyst PII.
- Jobs/Workflows running ETL on schedule + on-demand for HITL writes; alerting on idempotency or
  status-filter violations (D5, D9 are tested invariants).
- Model Serving endpoints (provisioned throughput) for the base LLM + adapters; separate embedding
  endpoint for retrieval.
- Vector Search index for regulatory text under Unity Catalog; Neo4j via private link / co-located
  VPC.
- Corporate SSO via the workspace's existing IdP; audit via system tables.
- Latency budgets per agent hop, packaging, on-call runbook.
**Done when:** end-to-end inside the workspace via VPN/private endpoint, auth + audit trail, SLOs
hit, rollback paths rehearsed.

### Later milestone — Research extraction *(deferred)*
Public FDA Warning Letter / Form 483 proxy benchmark; citation precision/recall + calibration +
human-κ; code release. Out of scope for the tool build.

---

## 5. Cross-cutting requirements

- **Scale (D1):** streaming/batched ETL, indexed Cypher, vector index type chosen for corpus size,
  no in-memory full-corpus assumptions.
- **Auditability (D9):** every KG write traceable to a source doc + human + timestamp.
- **Safety (D4, D5):** quarantine + status-filter are tested invariants, not conventions.
- **Confidentiality (D8):** nothing leaves the tenant; private serving only.
- **Reproducibility (D10, D11):** every model artifact in MLflow, every dataset version in Unity
  Catalog, every retrieval index hash-pinned to a corpus snapshot. Re-deriving any agent's output
  from `(doc, dataset_version, model_version, adapter_version, prompt_version)` must be possible.

---

## 6. What's explicitly OUT of scope (and why)

- Separate training-data input door — redundant (D6).
- Learning from unverified / own output — drift risk (D4).
- Third-party LLM APIs **outside** the tenant for submission content — confidentiality / 21 CFR
  Part 11 (D8). Note: Model Serving *inside* the private workspace is not "cloud API" in this
  sense — content never leaves the tenant.
- Per-role fine-tuning by default — gated on evals (D11). Fine-tuning the Parser or Supervisor is
  out of scope until somebody shows me an eval where prompting actually fails.
- The architecture-vision doc's figures (~2,800 records / 340 products / 3 fixed dimensions) —
  build on the **real** data + taxonomy instead (D2); those numbers are aspirational.
- Paper / benchmark work — deferred to a later milestone (tool first).

---

## 7. Immediate next step

Detail **Phase 1** to implementation-readiness: exact Neo4j node/edge schema (on the real taxonomy),
Vector Search / FAISS index design, and the re-runnable ETL approach for the `.xlsm` → graph +
index, expressed as Databricks Jobs / Unity Catalog tables from day one (D10). Requires confirming
the real `.xlsm` columns (O1) when you're ready to start Phase 1.

*Last updated: 2026-06-30 — added Databricks deployment substrate (D10), role-specialized adapter
strategy (D11), Phase 4.5 eval-gated fine-tuning.*
