# AutoGen-DocIntel — Project Plan

> **Status:** Planning (no implementation yet).
> **Companion doc:** `Amneal_Exp.md` (architecture vision — treat its *figures* as aspirational;
> this PLAN.md is the ground-truth build plan).
> **Author context:** Dev Desai, Amneal Pharmaceuticals, Regulatory Affairs (AI Eng. Intern).

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
| D8 | **On-prem, local LLM only.** No cloud APIs for submission content. | Confidentiality + 21 CFR Part 11. Confirmed by the data being confidential. |
| D9 | **Provenance + idempotency on every KG write.** Each node records source-doc hash, who verified, when. Re-ingesting a doc must not duplicate nodes. | Auditability is the theme; duplicates corrupt retrieval. |

### Open items (resolve at the relevant phase, not now)

- **O1 — exact `.xlsm` schema:** real columns/values to be confirmed when Phase 1 starts (confidential).
  Working assumption from the dev subset: `ANDA # | Product | Dosage Form | CMC Section |
  Deficiency Type | Cohort Year | Severity/Category | Deficiency (text) | Deficiency Response`.
- **O2 — local LLM choice:** `Amneal_Exp.md` names Mistral-7B; revisit against current (2026) local
  models at Phase 3. Not a blocker now.
- **O3 — research/benchmark:** deferred to a post-tool milestone (does a public FDA-483 benchmark
  already exist? check then).

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
   │ FAISS    (regulatory text)     │                   │ every claim cites its evidence   │
   │ status ∈ {seed, confirmed,     │                   └───────────────┬──────────────────┘
   │           quarantined}         │                                   ▼
   └───────────────▲───────────────┘                   RISK REPORT (per-claim + evidence)
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

### Phase 5 — Hardening + deployment
**Goal:** Production-ready on Amneal's on-prem infra.
- Corporate SSO auth, audit logging, encrypted doc storage + retention.
- Real local-LLM serving (resolve O2); latency targets; packaging.
**Done when:** runs on the target server, accessed via VPN, with auth + audit trail.

### Later milestone — Research extraction *(deferred)*
Public FDA Warning Letter / Form 483 proxy benchmark; citation precision/recall + calibration +
human-κ; code release. Out of scope for the tool build.

---

## 5. Cross-cutting requirements

- **Scale (D1):** streaming/batched ETL, indexed Cypher, FAISS index type chosen for corpus size,
  no in-memory full-corpus assumptions.
- **Auditability (D9):** every KG write traceable to a source doc + human + timestamp.
- **Safety (D4, D5):** quarantine + status-filter are tested invariants, not conventions.
- **Confidentiality (D8):** nothing leaves the on-prem network; local models only.

---

## 6. What's explicitly OUT of scope (and why)

- Separate training-data input door — redundant (D6).
- Learning from unverified / own output — drift risk (D4).
- Cloud LLM APIs for submission content — confidentiality / 21 CFR Part 11 (D8).
- The `Amneal_Exp.md` figures (2,800 records / 340 products / 3 fixed dimensions) — build on the
  **real** data + taxonomy instead (D2); those numbers are aspirational.
- Paper / benchmark work — deferred to a later milestone (tool first).

---

## 7. Immediate next step

Detail **Phase 1** to implementation-readiness: exact Neo4j node/edge schema (on the real taxonomy),
FAISS index design, and the re-runnable ETL approach for the `.xlsm` → graph + index. Requires
confirming the real `.xlsm` columns (O1) when you're ready to start Phase 1.

*Last updated: 2026-06-18 — initial plan.*
