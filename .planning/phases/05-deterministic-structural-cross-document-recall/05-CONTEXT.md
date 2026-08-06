# Phase 5: Deterministic Structural & Cross-Document Recall (β) - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Own the rest of recall in **general deterministic code** — three new recall legs plus the retrieval-surface fixes that make them viable and general:

1. **Intra-document structural inconsistencies** (RECALL-02) — summary-vs-detail value mismatch, reported-result-exceeds-spec-limit, and labeled-aggregate recompute — over re-openable table cells.
2. **Cross-document reference graph** (RECALL-03) — extract references, flag unresolved refs / absent referenced content-or-documents / cross-document value contradictions. Completes `follow_reference`'s reference-graph backing; subsumes the old X1/X2 checks.
3. **Precedent-similarity candidates** (RECALL-04) — surface candidates by similarity to the past-deficiency (ANDA) corpus, measured as its own recall family.
4. **Retrieval-surface fixes + anti-overfitting guard** (RECALL-05) — give the addressed/absent decision real dynamic range, persist the per-submission index at ingest, and enforce generality with a guard test that runs in stock CI.

Every check emits a **grounded candidate** dual-cited to source (and rule where one applies), stays **rulebook/structure/graph-general**, and passes the **anti-overfitting guard**. On the Phase 0 eval set, combined deterministic recall (absence + structural + cross-doc + precedent) must move recall-by-family above the 0.071 baseline with **zero true positives lost**.

**Iron guardrail (all legs):** no submission-specific constant — batch number, doc name, spec value, section path — in any check. General by construction or it does not ship. The eval corpus (mvr1381) is a proxy, never a target.

</domain>

<decisions>
## Implementation Decisions

> **Two provenance tiers below.** Decisions marked **[LOCKED — pre-reg 2026-08-06]** were settled in a prior senior-reviewer discuss session and are recorded in STATE.md § "Phase 5 Pre-Registered Decisions" — the authoritative source; do **not** re-litigate. Decisions marked **[DISCUSSED 2026-08-06]** were settled in this session.

### Structural pillar (RECALL-02) — [LOCKED — pre-reg 2026-08-06]
Fully decided. Summary (see STATE.md for the full text, which governs):
- **D-STR1 — Scope = "two + labeled-aggregate recompute".** SC1's two checks (summary-vs-detail mismatch; result-exceeds-spec-limit) PLUS one general family: a cell **labeled** as an aggregate (Total/Sum/Maximum/Minimum/Average/Mean) disagreeing with a deterministic recompute over its own tabulated rows. The aggregate lexicon is a **general label vocabulary** (like a stopword list), not a corpus constant.
- **D-STR2 — Det/interp litmus = "pure-computation-only".** A check is Phase-5 deterministic ONLY if its verdict is a pure computation (equality / ordering / arithmetic recompute) over ≥2 re-openable values with ZERO domain-semantic judgment. Any "is this the right statistic/method/interpretation?" question → Phase 7 interpretive tail. A compared value MAY resolve from a **rulebook rule span** (e.g. a spec limit), never an inline float constant.
- **D-STR3 — Grounding anchor = typed `StructuralAnchor`** (sibling of Phase-4 `CoverageAbsenceAnchor`): one claim span + N basis span-IDs + relation enum `{EQUALS, LEQ/ordering, SUM|MAX|MIN|MEAN}` + expected-vs-actual. **Re-derivable** — the verifier re-runs the computation, never trusts the snapshot. Cells resolved via `tables.py (table_id,row,col)→SpanID`; each basis span validated against its own store (CORPUS vs RULEBOOK). Over-emit with a scoping-confidence flag when a cell is not cleanly addressable; never silently drop.
- **D-STR4 — Value normalization/tolerance = "exact, unit-aware, abstain-on-doubt" with PRECISION-DERIVED comparison (no epsilon constant).** One general normalizer (strip %, canonicalize NMT/≤/≥ into comparator tags); abstain on unparseable/mismatched units. Compare at the **stated decimal precision** of the claim/limit operand (round finer operand, then exact-equal or strict-greater). Zero free parameters; matches the USP/ICH General-Notices rounding rule.
- **D-STR5 — Input surface = addressable table cells ONLY** (`tables.py`). Prose value-pairing requires reading meaning → Phase 7. A doc reporting table-tier unavailable is **skipped as a declared boundary** but LOGGED and routed to Phase 7, never silently dropped.

### Reference graph + contradictions (RECALL-03) — [DISCUSSED 2026-08-06]
- **D-REF1 — Edge kinds = all three.** Extract hyperlinks (DOCX/PDF link metadata) + textual references ("see §X", "Table 19", module citations like "Module 3.2.P.5") + numeric value cross-refs. Each extractor is a **general pattern** over spans, no corpus anchors.
- **D-REF2 — Emit shape = one `ReferenceAnchor` + anomaly enum.** A single typed anchor (sibling of `StructuralAnchor` / `CoverageAbsenceAnchor`) carrying anomaly enum `{UNRESOLVED_REF, ABSENT_TARGET, VALUE_CONTRADICTION}` + src span + optional dst span(s). One re-derivation path, one verifier branch.
- **D-REF3 — Value-contradiction matching = edge-required (full), label-match (low-confidence).** Emit a VALUE_CONTRADICTION as a **full candidate** only when an actual cross-reference edge connects the two values' locations (catches X1: QOS 2.3 → Module 3.2.P.5). Also emit label/identifier-matched contradictions but tagged **low scoping-confidence** (D-ABS2 over-emit style) for the verifier to prune (catches unlinked X2). Recall-safe without hard false positives.
- **D-REF4 — Contradiction comparison reuses the RECALL-02 engine identically.** Same normalizer, same precision-derived tolerance (no epsilon), same abstain-on-unit-mismatch. One comparison semantics across structural + cross-doc; guard-clean by construction.
- **D-REF5 — ABSENT_TARGET consults the coverage manifest first.** Emit ABSENT_TARGET as a full candidate only when the target doc/section is **ingested-and-present** but the referent is genuinely missing. If the target is table-tier-unavailable / unparsed, emit as declared-boundary low-confidence and route to Phase 7 — honours the Phase-1 availability contract, avoids FP from ingestion gaps.
- Reuse `follow_reference` (fills the SAME interface — replaces the `cross_document_resolution_pending_phase_4` stub) and the `edges.py` provenance-carrying edge table (D-RB3: every edge carries a provenance span).

### Precedent candidate mechanic (RECALL-04) — [DISCUSSED 2026-08-06]
- **D-PRC1 — Match unit = section-level nearest-precedent.** Embed each submission section, retrieve nearest past-deficiency chunks; an above-threshold match emits a candidate anchored to that section. General, per-section, mirrors the retrieval substrate.
- **D-PRC2 — Anchor = submission span anchors; precedent attached (D-RB2(5)).** Typed `PrecedentAnchor` = the re-openable **submission** span (the grounded claim) + precedent chunk id(s) + similarity score as **attached supporting evidence**. Grounding lives on the submission side; precedent text is never a finding source.
- **D-PRC3 — No-leakage safeguard = exclude same-ANDA + pattern-match only.** Filter out precedent rows whose ANDA# matches the submission under review, and match on deficiency-**pattern** similarity, not verbatim submission text. Guard test asserts the held-out corpus still produces precedent candidates from the same logic (no self-recognition of seeded items).
- **D-PRC4 — Threshold = absolute dense-cosine, general.** An absolute cosine similarity (0–1, real range) with a single general threshold, no corpus-tuned constant. Consistent with the RECALL-05 dynamic-range approach and the other legs.

### RECALL-05 — dynamic range + index persistence — [LOCKED — pre-reg 2026-08-06]
Two jobs on the same retrieval surface (`retrieval/hybrid.py`, `tools/search_corpus.py`, `ingest/corpus.py`):
- **D-R5A — Dynamic range.** The RRF-fusion score ceiling `2/61 ≈ 0.0328` sits below the `0.04` absence threshold, so `absence.py:142`'s "found → not absent" branch is **dead** → emit-everything. Replace the RRF-rank artifact with an **absolute dense-cosine similarity** (0–1, real range) with a general threshold that actually separates addressed vs absent requirements.
- **D-R5B — Persist the per-submission index (feasibility prerequisite, NOT a Phase-8 optimization).** Today `search_corpus` re-chunks, rebuilds BM25, and **re-embeds the entire submission on every query** — O(queries·corpus), which breaks the "no cap on document count" promise once Phase 5 multiplies query count. Build the index **once at ingest** (chunks + BM25 + dense embeddings), persist next to the Phase-1 doc cache **keyed by the same content hash** that makes ingest resumable; `search_corpus` loads the prebuilt index and embeds only the **query**.

### Anti-overfitting guard fixture (RECALL-05 guard) — [DISCUSSED 2026-08-06]
- **D-GRD1 — Committed fixture = synthetic planted-deficiency corpus.** A tiny, fully synthetic multi-doc corpus (no real/confidential FDA content) with planted structural + cross-ref + precedent-style deficiencies. Safe to commit, license-clean, deterministic. **Four binding constraints on the fixture** (guards this codebase's signature bug — a green test on both sides of an untested boundary):
  1. Planted deficiencies are specified from **rulebook/structural semantics** — what a real reviewer would flag — **independently of (ideally blind to) the check implementation**. Not reverse-engineered from what the code happens to detect.
  2. **Different surface forms than mvr1381** — different doc names, section paths, values, table layouts — so RENAME and THRESHOLD-TRANSFER exercise transfer, not recognition.
  3. **Realistic enough prose/tables that bge-m3 cosine lands in the same regime as real docs** — otherwise THRESHOLD-TRANSFER on a toy fixture is meaningless (degenerate text won't exercise the dense-cosine thresholds).
  4. **Two-tier, not a replacement:** the synthetic fixture is the every-build tripwire ("runs green every build"); keep the real gitignored **spec32s41** corpus as the slow-lane stronger witness ("generalizes to real content").
- **D-GRD2 — All three transfer invariants run in fast CI** against the committed fixture: SAME-LOGIC, THRESHOLD-TRANSFER, RENAME-INVARIANCE. They must actually **execute**, not `pytest.skip`. Keep the corpus-gated slow lane for the larger real corpus.
- **D-GRD3 — Guard vocab discrimination = registered general-vocabulary allowlist.** General label vocabularies (aggregate lexicon Total/Max/Mean; reference cue-words "see"/"Table") live in a declared, reviewed registry; the NO-CONSTANT scan treats registry members as allowed and **flags any OTHER inline literal** (numeric spec values, CTD section paths, doc names, batch IDs). Each vocab entry is asserted to contain no corpus-specific token. This is a **code gate**, not reviewer sign-off (three-laws principle).

### Shared candidate contract (all four legs) — [DISCUSSED 2026-08-06]
- **D-ENV1 — One grounded-candidate envelope** extending Phase 4's existing `Fault` + anchor pattern (not per-leg shapes). The envelope carries:
  - a typed **anchor** (union of `CoverageAbsenceAnchor | StructuralAnchor | ReferenceAnchor | PrecedentAnchor`),
  - a **leg tag** `{ABSENCE, STRUCTURAL, REFERENCE, PRECEDENT}`,
  - a **confidence tier** (full vs low-confidence — the single field that scoping-confidence flags, label-match low-confidence, and precedent soft-leads all write into),
  - a **dedup key** `(docId, sectionId, ruleId?)` — `ruleId` **nullable** (precedent and rule-less structural findings have none),
  - **grounding:** submission span always present; rule span attached only when a rule applies.
- Uniform envelope ⇒ uniform Phase 7 verification + uniform coverage reporting. Natural continuation of the contract, not a new abstraction.

### Precedent index build scope — [DISCUSSED 2026-08-06]
- **D-PIX1 — Static global reference asset.** The precedent (`deficiency_kb`) index is built **once at reference/rulebook-build time** (like the rulebook KB), distinct from the per-submission index — different lifecycle (rebuilt only when the ANDA deficiency corpus changes, **never** per submission).
- **D-PIX2 — Per-chunk ANDA# metadata** so same-ANDA exclusion (D-PRC3) is a **query-time metadata filter**, not a rebuild.
- **D-PIX3 — Local FAISS primary.** Precedents are a global reference asset (not submission content), so a Databricks mirror is permissible — but the guard's held-out fixture must run in stock CI **without Databricks**, and local determinism + cost favor querying the local `deficiency_kb.faiss` (mirrors `search_corpus` being local). Databricks mirror stays optional / serving-only.

### Candidate consolidation & index-persistence interaction — resolved
- **D-CON1 — Consolidation via the shared envelope.** Dedup across legs by the envelope's `dedup_key`; ordering leans on the `confidence_tier`; Phase 7 inherits the remaining pruning load (per Phase-4 handoff). No separate consolidation abstraction needed.
- **D-CON2 — Index persistence keys on the Phase-1 content hash** (per D-R5B) — same hash that makes ingest resumable; a changed document invalidates and rebuilds its index entry. No new invalidation scheme.

### Claude's Discretion
- Exact module/file layout for the new legs (sibling packages to Phase-4 absence), internal function decomposition, and test structure — planner/executor decide, following the Phase-4 pattern.
- Concrete reference-extraction regexes / hyperlink-metadata plumbing, provided they stay general (D-REF1) and register any cue-word vocabulary in the guard allowlist (D-GRD3).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked prior decisions (authoritative — read FIRST)
- `.planning/STATE.md` § "Phase 5 Pre-Registered Decisions (discuss 2026-08-06)" — the LOCKED structural pillar (RECALL-02) + RECALL-05 dynamic-range/index-persistence decisions. **Governs; do not re-litigate.**
- `.planning/ROADMAP.md` § "Phase 5: Deterministic Structural & Cross-Document Recall (β)" (Goal, Depends-on, 5 Success Criteria) — the fixed phase boundary.
- `.planning/REQUIREMENTS.md` — RECALL-02, RECALL-03 (subsumes DETECT-01/02), RECALL-04, RECALL-05.

### Phase-4 handoff & known limitation
- `.planning/phases/04-rulebook-enrichment-absence-enumeration/04-VERIFICATION.md` § "Phase-5 Handoff / Known Limitation" — the absence threshold `0.04` vs RRF ceiling `~0.0328` non-discriminative retrieval leg (the RECALL-05 dynamic-range motivation).
- `.planning/phases/04-rulebook-enrichment-absence-enumeration/04-CONTEXT.md` — Phase-4 decisions the envelope/anchor pattern extends (CoverageAbsenceAnchor, emit_absence_finding, D-ABS2 over-emit, D-GEN3 generality guard).
- `.planning/phases/04-rulebook-enrichment-absence-enumeration/04-PATTERNS.md` — Phase-4 pattern map (closest analogs for the new legs).

### Precedent & rulebook substrate
- `.planning/phases/02-retrieval-navigation-tools-rulebook/02-PRECEDENT-AUDIT.md` — D-PREC dedupe/forward-fill/row-identity policy the precedent ingestion implements; source of ANDA# metadata for D-PIX2/D-PRC3.
- `.planning/phases/02-retrieval-navigation-tools-rulebook/02-CONTEXT.md` — D-RB3 (generic edge table + provenance span), D-RB2(5) (precedent = evidence, never a finding source), D-FR (`follow_reference` contract).
- `docs/databricks-rulebook-kb-representation.md` — KB representation across local FAISS / Databricks backends (informs D-PIX3 local-primary vs Databricks-mirror).

### CTD/family generality reference
- Anti-overfitting guard (RECALL-05 guard) must reject CTD-family section paths (`3.2.[SP].`) and inline threshold floats per the Phase-4-hardened NO-CONSTANT structural check — see `.planning/phases/04-rulebook-enrichment-absence-enumeration/` guard artifacts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/tools/follow_reference.py` — currently returns the typed `cross_document_resolution_pending_phase_4` sentinel; Phase 5 fills the **same interface** with the real reference graph (contract unchanged, per its docstring).
- `src/rulebook/edges.py` — generic edge table `(src_id, dst_id, edge_type, provenance_span_id)`; `add_edge` rejects empty provenance (D-RB3). Backs the RECALL-03 reference graph with zero migration for new edge types.
- `src/rulebook/precedents.py` — ingests the vendored ANDA deficiency xlsm through the Phase-1 substrate; carries the 9-column schema incl. `anda_number` (needed for D-PIX2/D-PRC3 same-ANDA exclusion). **No candidate-surfacing tool registered yet** — RECALL-04 adds it.
- `data/deficiency_kb.faiss` + `data/deficiency_kb_map.json` — existing precedent similarity index (wired in `src/config.py`, `src/databricks/vector.py`, `src/databricks/delta.py`, `src/rulebook/build.py`); the static global asset of D-PIX1.
- `src/ingest/tables.py` — `(table_id,row,col)→SpanID` cell addressing; the ONLY input surface for structural checks (D-STR5).
- Phase-4 `CoverageAbsenceAnchor` + `emit_absence_finding` — the anchor/emit pattern `StructuralAnchor`, `ReferenceAnchor`, `PrecedentAnchor`, and the shared envelope (D-ENV1) extend.

### Established Patterns
- **Grounded-candidate / emit-gate contract** (Phase 2 `emit_finding`, Phase 4 `emit_absence_finding`): every candidate is a re-openable verbatim span + optional rule span, re-derivable at verify time. All four Phase-5 legs conform (D-ENV1).
- **D-ABS2 over-emit with scoping-confidence:** when a contributing value is not cleanly addressable, over-emit low-confidence rather than drop; Phase 7 prunes. Reused for D-STR3, D-REF3, and precedent soft-leads.
- **Anti-overfitting guard is CI-enforced but partly corpus-gated:** NO-CONSTANT is structural; `test.yml` runs coverage-gate + absence-gate every build + a `pytest-slow` job. RECALL-05 guard must move SAME-LOGIC/THRESHOLD-TRANSFER/RENAME into fast CI via the committed synthetic fixture (D-GRD1/2).

### Integration Points
- `src/retrieval/hybrid.py` — RRF fusion (score ceiling `2/61`); RECALL-05 job 1 replaces the rank artifact with absolute dense-cosine (D-R5A).
- `src/tools/search_corpus.py` (lines ~42/48/53) — re-embeds the whole submission per query; RECALL-05 job 2 loads a prebuilt persisted index and embeds query-only (D-R5B).
- `src/ingest/corpus.py` — corpus index + resumable content-hash store; the persisted per-submission index keys here (D-CON2).
- Candidate output → Phase 7 verifier: the shared envelope (D-ENV1) is the hand-off surface; consolidation/dedup by `dedup_key`, pruning inherited by Phase 7 (D-CON1).

</code_context>

<specifics>
## Specific Ideas

- **X1 / X2 must pass end-to-end** on the Phase 0 eval set: X1 (QOS 2.3 vs Module 3.2 body cross-document spec mismatch) via an edge-linked VALUE_CONTRADICTION; X2 (cross-document value contradiction) at least as a label-matched low-confidence candidate.
- **Table 19 / Table 20 as ONE general rule:** the labeled-aggregate recompute (D-STR1) must capture Table 19 (total 0.14% < single-largest 0.15%) and Table 20 (Max cell 11477 vs true 12601) as one general family, not two bespoke checks.
- **Regulatory rounding correctness:** limit-exceedance uses precision-derived comparison so `0.104` vs `NMT 0.10` **complies** (USP/ICH General-Notices rounding), not a naive exact-ordering false positive (D-STR4).

</specifics>

<deferred>
## Deferred Ideas

- **Semantic / interpretive cross-reference contradictions (X3/X5/X6)** and any "is this the right statistic/method/interpretation?" judgment (r² mislabel, retained outlier, absorptivity spread, linearity) → **Phase 7 interpretive tail** (fails the pure-computation litmus D-STR2). Already in the v2+ deferred list.
- **Prose value-pairing** (comparing values stated in narrative text rather than addressable table cells) → Phase 7 (requires reading meaning; D-STR5 restricts Phase 5 to table cells).
- **Databricks mirror of the precedent index as a query backend** → optional / serving-only; not built in Phase 5 (D-PIX3 keeps local FAISS primary so CI runs without Databricks).
- **Cross-leg ranking beyond confidence-tier ordering** → left to Phase 7 pruning; no bespoke scorer in Phase 5 (D-CON1).

</deferred>

---

*Phase: 5-Deterministic Structural & Cross-Document Recall (β)*
*Context gathered: 2026-08-06*
