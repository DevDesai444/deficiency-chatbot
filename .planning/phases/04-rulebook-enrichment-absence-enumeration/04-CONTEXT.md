# Phase 4: Rulebook Enrichment + Absence Enumeration (β) - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Two coupled deliverables that together close the `#1` recall gap (`absence_of_evidence = 0.000`):

1. **Rulebook enrichment (RULES-06)** — thicken the ICH/FDA rulebook and the requirement index from their thin Phase-2 baseline (rulebook `ich=4`/`fda=1` chunks; requirement index = **15 entries, almost all in one family `3.2.S.4.3`/ICH Q2**) to **per-requirement granularity**, so the index the enumerator walks is no longer sparse. Every new chunk keeps `{source, citation, version/date, license, url}` (RULES-04) + the ICH copyright acknowledgment.

2. **Absence enumeration (RECALL-01)** — build the **deterministic absence check** that walks `enumerate_requirements(manifest)` (Phase-2 applicability resolver), decides which applicable required items the submission **does not address**, and emits each as a **grounded absence candidate** dual-cited to the rule — recovering `absence_of_evidence` above the `0.000` floor, driven **only by the rulebook**, provably corpus-general.

**Grounding finding from the eval (drove the whole discussion):** every `absence_of_evidence` ground-truth item in the eval corpora is **requirement-LEVEL, present-but-unaddressed** — the document exists, the required item is triggered, but the supporting data/result is absent (e.g. mvr1381: "narrative claims accuracy established, no accuracy result table anywhere"; "no supporting data for LOD/LOQ"; "precision never demonstrated for Total Impurities"). **None** is a whole-section absence. The 15 Q2 index triggers are already shaped for exactly this pattern. So the eval floor is recovered by requirement-level "triggered-but-not-evidenced" detection — the zero-document mechanism is an additional, reviewer-general class (D-RB4) validated off-eval.

**Explicitly NOT in this phase:** rule-*relevance* judgment and adversarial verification (Phase 7 — the local-model verifier that PRUNES the candidates this phase over-emits); the other deterministic recall families — structural/cross-document (RECALL-02/03), precedent similarity (RECALL-04) (Phase 5); dynamic rulebook refresh (post-v1); re-coupling recall to the agent drive loop (Phase 3 NO-GO'd three times because the loop was the recall driver — absence enumeration is a deterministic pre-loop pass here).

**Carried forward — LOCKED in Phase 2, not re-opened:** D-RB4 (applicability via `family_requires_requirement` + `profile_requires_family` edges + coverage manifest); D-RI1 (LLM-draft → senior-review → versioned index, code loader gate, MS-04 traceability test); D-RI2 (enumerate-on-`read_guideline`, one optional `citation` param, applicability resolved server-side); D-EF1 dual byte-exact grounding through `emit_finding`; D-RB3 (generic edge schema `(src_id, dst_id, edge_type, provenance_span_id)` — **every edge carries a provenance span**); D-RB6 (offline contract — tests + harness never touch Databricks).

</domain>

<decisions>
## Implementation Decisions

### 'Does-not-address' test — the heart of RECALL-01
- **D-ABS1:** **Retrieval-threshold over-emit.** For each applicable requirement (from `enumerate_requirements`), query the ephemeral submission index (`src/retrieval/hybrid.py`) for evidence matching the requirement's trigger; a top-hit score **below a recorded threshold** → emit an absence **candidate**. Deterministic, recall-first, corpus-general (the query is the rulebook trigger, never a corpus constant). Chosen over structural-only (blind to "narrative claims X, no data" — the eval's dominant pattern) and over a structural+retrieval hybrid (avoids extra moving parts for the MVP).
- **D-ABS2:** **Over-emit; the verifier prunes.** Phase 4 optimizes **recall** — emit every plausibly-unaddressed applicable requirement. Precision is Phase 7's job (local-model verifier + `tp_required` semantics). Do **not** bake a precision cutoff into the recall layer (that is what re-suppresses the 0.000 floor).
- **D-ABS3:** **Deterministic pre-loop pure pass.** Absence enumeration is a pure function over `(coverage_manifest, requirement_index)` that emits candidates through the existing `emit_finding` grounding gate — **NOT** a tool the drive loop calls, **NOT** gated on the loop. β thesis: recall is deterministic; the loop only verifies.
- **D-ABS4:** **Absence grounding = rule span + manifest evidence (+ claim span when present).** Always cite the rule clause (`rule_span_id`) and the coverage-manifest evidence of what was searched/present-but-lacking; **additionally** cite the unsupported narrative-claim span when one exists (the MS-03/mvr case). Richest re-openable grounding for the Phase-7 verifier (SC4).
- **D-THR:** **Retrieval threshold is measured → recorded → ratcheted, never a baked constant** (D-03 / D-SC4 discipline). Tune and record the threshold against the **mvr1381** tuning corpus; commit it as a baseline; later phases may not regress it. (Generality is proven on a *different* corpus — see D-GEN1 — so tuning on mvr1381 is not circular for the *threshold*, only for *generality*.)

### Rulebook + requirement-index enrichment (RULES-06)
- **D-ENR1:** **Stop rule = traceability floor + reviewer-general breadth.** MUST: every absence-family eval deficiency has ≥1 **firing** index entry for its submission's profile (D-RI1(2) hard gate, MS-04 lesson). SHOULD: decompose the guidelines those families live in to **per-requirement** granularity so it generalizes beyond the exact eval spans. Stop when the traceability test passes **and** each touched guideline is decomposed per-requirement.
- **D-ENR2:** **Target = decompose already-vendored Q3A/Q3B/Q6A first, then add Q1 stability.** Q3A/Q3B (impurities) + Q6A (specifications) PDFs are already vendored in `rulebook/ich/` but barely represented in the index — decompose them per-requirement first (highest coverage gain, no new sourcing). Then **vendor + add ICH Q1 (stability)** — the classic "stability data absent" reviewer case. The new Q1 PDF is a build-time vendoring task: date-pin, `sha256`, RULES-04 metadata, **ICH copyright notice stored per chunk**, routed through the Phase-1 ingestion substrate like every other chunk.
- **D-ENR3:** **Coverage bar = recorded metric, ratcheted (no invented target).** Record per-source chunk count + per-family requirement-entry count as a committed baseline (same shape as `recall_by_family` / SC4). SC1 passes when both **strictly exceed** the `ich=4`/`fda=1` & 15-entry baseline **and** the traceability test passes. No baked target number.
- **D-ENR4:** **Authoring = LLM-draft → code gate + traceability test → senior diff spot-check.** Batch LLM-draft per guideline; the **code loader gate** (provenance span re-opens byte-exact via `open_span` + family in the D-05 registry) and the **MS-04 traceability test** reject bad entries at LOAD/CI. The senior reviewer reviews the **versioned YAML diff** and spot-checks — not entry-by-entry. Gate is code; human review sits on top (D-RI1 shape). Index **version bumped on any change** (D-24 discipline).

### Whole-section (zero-document) absence
- **D-SEC1:** **In scope — expand `profile_requires_family` closure edges.** Grow the closure beyond the 2 current edges (`drug_substance→3.2.S.7`, `drug_product→3.2.P.7`) so a required family with **zero classified documents** fires "entire section absent." This falls out naturally from requirement-level enumeration (every requirement in a zero-doc family is unaddressed). Cheap (edges, no new machinery), reviewer-general (D-RB4's most-cited real class). Each new edge carries a **provenance span** (the rule text that says the profile requires the family) per D-RB3, validated by the same loader gate (D-RI1). **Because the main eval tests this class ~zero, it is validated by targeted OFF-eval composition tests:** a constructed corpus that omits a **required** family → absence fires; one that omits a **non-required** family → nothing fires.
- **D-SEC2:** **False-absence guard = profile-gated + over-emit candidate.** Fire whole-section absence ONLY for a family required by a profile the submission **actually exhibits** (content-derived closure); a family no active profile requires never fires. Mark it a candidate — Phase-7 verifier prunes. (Consistent with D-ABS2.)

### Corpus-generality guard (SC3)
- **D-GEN1:** **Generality witness = `heldout32s41` (spec32s41), NOT `mvr1381`, + constructed omission fixtures.** `mvr1381` is the corpus recall/threshold is tuned against (D-THR) — using it as the generality witness would be **circular**. Real generality must be proven on a corpus **never tuned on**: run the absence check against `heldout32s41` and confirm its absences arise from the same rulebook logic. Add the constructed omit-a-required-family / omit-a-non-required-family fixtures (D-SEC1) for the whole-section boundary.
- **D-GEN2:** **Three invariants.** (1) **No-constant:** the absence module references no corpus/doc/submission-ID literal. (2) **Rename-invariance:** reorganizing/renaming the held-out corpus directories yields the **identical** applicable-requirement set + identical absence-candidate IDs. (3) **Same-logic transfer:** the held-out corpus's absences come from the **same index entries firing**, not corpus-specific rules.
- **D-GEN3:** **Enforcement = automated CI test in the harness.** The guard is code (in `tests/` or `src/evals/`) that **fails the build** if the absence module embeds a corpus constant or if a folder rename changes applicability. Enforced every run (D-RB6 offline contract + the "green test on both sides of an untested boundary" lesson) — never a one-time audit.

### Emit-gate contract for absences (Phase-2 ↔ Phase-4 integration boundary)
- **D-GATE1:** **Absence-typed finding = byte-exact rule span + typed `CoverageAbsenceAnchor` (+ claim CORPUS span when present).** Extend `emit_finding` with an absence variant. The **RULE half stays byte-exact** (`rule_span_id` re-opens in the RULEBOOK store — D-EF1 unchanged). The **submission half becomes a typed `CoverageAbsenceAnchor`** — the families/sections enumerated + searched, with manifest span-IDs proving the search space — instead of a CORPUS text span. When a narrative claim exists, the claim's CORPUS span is **also** attached and validated. The gate validates every half that is present. Rejected alternatives: "require a submission anchor always" (structurally can't emit never-mentioned / whole-section absences — loses the D-SEC class); "null/sentinel submission span" (weakens the byte-exact invariant, re-opens citation drift).
- **D-GATE2:** **The absence side is re-derivable, not a frozen snapshot.** The `CoverageAbsenceAnchor` stores the exact enumerate inputs (profile, family, `requirement_id`) + the retrieval evidence (top-k hits that fell below the D-THR threshold) so the Phase-7 verifier deterministically **RE-RUNS** "was this searched and found lacking?" The rule span re-opens via `open_span`; **the negative is independently reproducible** (SC4 + composition-test-on-real-data discipline), not a recorded assertion the verifier must trust.

### Claude's Discretion (within the locked contracts)
- Exact threshold-tuning mechanic for D-THR (absolute score vs top-k gap vs relative-to-corpus) — bounded by "measured, recorded, ratcheted, no baked constant."
- `CoverageAbsenceAnchor` field layout and on-disk/serialized shape — follow existing span-ID + manifest conventions.
- LLM-drafting prompt design and batching for D-ENR4 — bounded by the loader gate + traceability test.
- Whether requirement-level and whole-section absences share one code path or two — bounded by D-ABS3 (single deterministic pass) and the D-GATE1 finding shape.
- Retrieval query construction from a requirement trigger (whole trigger vs extracted key terms) — bounded by D-GEN2's no-constant invariant.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase governance
- `.planning/ROADMAP.md` — Phase 4 goal + Success Criteria 1–4 (the acceptance contract): per-requirement enrichment, enumerate-applicable + flag-unaddressed, corpus-general guard, grounded/re-openable candidates + "no absences" positive reporting.
- `.planning/REQUIREMENTS.md` — **this phase:** RULES-06, RECALL-01. Downstream: RECALL-02/03/04/05 (Phase 5), VERIFY-01..04 (Phase 7 — the verifier that prunes these candidates). Note the β re-homing: AGENT-04's recall floor is subsumed by deterministic enumeration (RECALL-01).
- `.planning/PROJECT.md` — Key Decisions (rulebook-as-retrievable-reference-NOT-oracle; grounding-mandatory; content-driven applicability, no-doc-cap). "Known debt to avoid inheriting": README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE describe a REMOVED AutoGen design — do not trust their file refs.
- `.planning/phases/02-retrieval-navigation-tools-rulebook/02-CONTEXT.md` — **the direct upstream.** D-RB4 (applicability edges + manifest), D-RI1 (index authoring + loader gate + traceability test), D-RI2 (enumerate surface), D-EF1 (emit grounding gate), D-RB3 (generic edge schema + provenance-span rule), D-RB6 (offline contract).
- `.planning/phases/01-ingestion-foundation/01-CONTEXT.md` — substrate decisions (span-IDs, `open_span` re-open primitive, normalizer version, table addressing, D-05 registry, coverage manifest).

### The Phase-2 mechanism Phase 4 completes
- `src/rulebook/requirement_index.py` — `load_requirement_index` (D-RI1 loader gate), `enumerate_requirements(manifest, family)` (D-RI2 applicability resolver), `submission_profile(manifest)` (content-derived profile), `build_requirement_edges` (`family_requires_requirement` + the 2 `profile_requires_family` closure edges D-SEC1 expands). **The absence check is the missing consumer of `enumerate_requirements`.**
- `src/rulebook/requirement_index.yaml` — the versioned index (currently 15 entries, ~all family `3.2.S.4.3`); D-ENR2 decomposes Q3A/Q3B/Q6A + adds Q1 here; D-ENR4 governs how.
- `src/rulebook/store.py` — rulebook store (RULEBOOK-store membership check in the emit gate, D-GATE1).
- `src/tools/read_guideline.py` — enumerate/citation surface (D-RI2); the absence check consumes `enumerate_requirements` directly, not necessarily via the tool.
- `src/ingest/manifest.py` — `CoverageManifest`, `DocEntry` — the uncapped coverage enumeration the zero-document claim (D-SEC1) and the `CoverageAbsenceAnchor` (D-GATE1/2) lean on.
- `src/ingest/anchors.py` — `open_span` / `HashMismatch` / `mint_span` — the byte-exact re-open primitive the emit gate and loader gate call.
- `src/ingest/classify.py` + `src/ingest/registry/` — document classification → family_guess → submission profile (D-RB4); D-05 family registry the loader gate validates tags against.

### Retrieval, emit gate, LLM plumbing
- `src/retrieval/hybrid.py` — the ephemeral submission index the D-ABS1 retrieval-threshold check queries (dense + lexical).
- `src/retrieval/vector_search.py` — `embed_query` (local bge-m3, pinned for reproducibility per D-RB6).
- `src/tools/errors.py` — typed self-correcting `ToolRejected` errors — the shape absence-gate rejections follow.
- `src/schemas/faults.py` — finding/fault schema; D-GATE1 adds the absence-typed variant + `CoverageAbsenceAnchor` here.
- `src/llm/structured.py` — hardened structured-output stack for the D-ENR4 LLM index drafter.

### Eval harness (SC1 coverage baseline, traceability test, generality guard)
- `src/evals/run.py` — CI-style harness (imports the library, records, never crashes); home of the D-ENR3 coverage baseline, the D-RI1(2) traceability test, and the D-GEN3 generality CI test.
- `src/evals/dataset/mvr1381.deficiencies.json` — **tuning corpus** (D-THR threshold tuning; 11 requirement-level absences). NOT the generality witness.
- `src/evals/dataset/heldout32s41.deficiencies.json` — **generality witness** (D-GEN1; never tuned on).
- `src/evals/dataset/minispec.deficiencies.json` — MS-03 (the canonical "claim without data" absence).
- `src/evals/schema.py` — `ABSENCE_OF_EVIDENCE` failure family + `tp_required` semantics.

### Rulebook snapshot (D-ENR2 targets)
- `rulebook/manifest.yaml` — vendored-snapshot manifest (date-pins, sha256, RULES-04 metadata); new Q1 entry added here.
- `rulebook/ich/` — Q2, Q3A-R2, Q3B-R2, Q6A vendored PDFs (Q3A/Q3B/Q6A = decompose targets; Q1 = new vendor).
- `docs/databricks-rulebook-kb-representation.md` — the live Databricks rulebook KB shape (`defpredict.main.rulebook_chunks/_embeddings`); serving layer behind the D-RB6 config switch.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`src/rulebook/requirement_index.py::enumerate_requirements`** — already resolves "what must THIS submission contain" from the manifest profile. Phase 4 adds the **consumer** that turns applicable→unaddressed→candidate. Do NOT reinvent applicability.
- **`src/retrieval/hybrid.py`** — the ephemeral submission index; D-ABS1 queries it per applicable-requirement trigger. Reuse verbatim.
- **`src/ingest/anchors.py::open_span`** — the byte-exact re-open primitive for the rule half of the absence gate (D-GATE1) and the loader gate (D-ENR4).
- **`src/ingest/manifest.py::CoverageManifest`** — the uncapped coverage enumeration behind the zero-document claim and the re-derivable `CoverageAbsenceAnchor`.
- **`src/evals/run.py`** — "import the library, record, never crash" harness; coverage baseline + traceability test + generality CI test all live here.

### Established Patterns
- **Deterministic-first, LLM-as-escalation** — the absence check is deterministic (D-ABS3); the LLM only *drafts* index entries (D-ENR4) and *verifies* candidates downstream (Phase 7). Recall never runs through the model loop.
- **Over-emit → gate/verify** — the emit gate proves GROUNDING not RELEVANCE (D-EF1); the Phase-7 verifier proves relevance. D-ABS2 leans on this split.
- **Code gate first, human review on top** (D-RI1) — D-ENR4 scales this to 10x entries: loader gate + traceability test in code; senior reviews the diff.
- **Every edge carries a provenance span** (D-RB3) — the new `profile_requires_family` closure edges (D-SEC1) are not exempt.
- **No baked cutoff before measurement** (D-03/D-SC4) — applied to both the retrieval threshold (D-THR) and the coverage bar (D-ENR3).
- **Offline contract / green-test-both-sides-of-a-boundary** — the generality guard (D-GEN3) and off-eval composition tests (D-SEC1) are CI-enforced, never one-time audits.

### Integration Points
- **`emit_finding` absence variant** (D-GATE1) — the single Phase-2↔Phase-4 seam; the RULEBOOK/CORPUS store-membership checks extend to accept a `CoverageAbsenceAnchor` on the submission half.
- **`profile_requires_family` closure** (`build_requirement_edges`) — D-SEC1 grows this edge set on the same generic edge table (zero migration, D-RB3).
- **Coverage manifest → profile → applicability** — the content-derived chain that keeps everything corpus-general (D-GEN2 no-constant).

</code_context>

<specifics>
## Specific Ideas

- **The eval's absences are ALL requirement-level "claim/requirement present, data absent"** (mvr1381 ×11, MS-03) — this drove D-ABS1 (retrieval over structural) and the whole absence-signal design.
- **mvr1381 = tune, heldout32s41 = prove** (D-THR + D-GEN1) — the anti-circularity split the senior reviewer insisted on: never witness generality on the corpus you tuned against.
- **Off-eval composition tests for whole-section absence** (D-SEC1) — omit-a-required-family → fires; omit-a-non-required-family → silent. The main eval structurally can't measure this class, so a constructed boundary test carries it.
- **The negative must be re-derivable, not asserted** (D-GATE2) — the `CoverageAbsenceAnchor` stores enumerate inputs + sub-threshold retrieval hits so a verifier re-runs the search rather than trusting a snapshot.
- **Absence enumeration is a pre-loop pure pass** (D-ABS3) — the deliberate structural answer to three consecutive Phase-3 drive-loop NO-GOs: recall is no longer the loop's job.

</specifics>

<deferred>
## Deferred Ideas

- **Rule-relevance judgment + adversarial verification of absence candidates** — Phase 7 (VERIFY-01..04). This phase over-emits; Phase 7 prunes. The `CoverageAbsenceAnchor` (D-GATE2) is built re-derivable specifically so that verifier can re-run the negative.
- **Structural/cross-document recall (intra-doc mismatch, reference graph)** — RECALL-02/03, Phase 5. Some mvr1381 items (e.g. "conclusion asserts room-temperature storage, documented nowhere") straddle absence and structural integrity; treat the rulebook-triggered angle here, the structural angle in Phase 5.
- **Precedent-similarity recall** — RECALL-04, Phase 5.
- **Broad reviewer-general enrichment beyond Q1/Q3/Q6** (Q8–Q12, full CFR cGMP per-requirement) — deferred; D-ENR1 stops at traceability-floor + the guidelines the eval families live in.
- **Dynamic rulebook refresh** — post-v1; enrichment is a versioned one-time manual build (D-RB2).
- **Structural+retrieval hybrid absence signal** — considered in D-ABS1, deferred as a precision lever only if measured to help.

None of the above are scope creep — each was raised, bounded, and consciously placed.

</deferred>

---

*Phase: 04-rulebook-enrichment-absence-enumeration*
*Context gathered: 2026-08-05*
