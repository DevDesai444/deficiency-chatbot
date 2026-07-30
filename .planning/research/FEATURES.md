# Feature Research

**Domain:** Agentic FDA/ICH regulatory-compliance reviewer over arbitrary PDF+DOCX submission corpora (CMC / CTD Module 3 emphasis)
**Researched:** 2026-07-30
**Confidence:** MEDIUM-HIGH
_(Deficiency taxonomy: HIGH — grounded in ICH guideline structure + FDA deficiency literature. Feature landscape: MEDIUM — the "agentic **reviewer/critic**" niche is nascent; most shipping pharma-AI tools are **authoring** tools, so the reviewer feature set is triangulated from adjacent legal-AI review products + emerging pharma agentic tools.)_

---

## Executive Framing (read this first)

The market whitespace is real and it shapes every category below. Almost every AI tool in this space today is an **author** — it helps write the dossier faster (Celegence, Narrativa, Weave Bio, Veeva-adjacent authoring). Only a thin slice acts as a **reviewer/critic** that finds where a submission *fails*, and even those (Peer AI's "virtual content challenger") frame it as an internal QC aid, not a grounded deficiency-finder over an arbitrary corpus.

DefPredict's product identity is therefore: **a grounded adversarial reviewer, not an author.** That single decision is the source of most of the anti-features. Every table-stakes item is "what any credible reviewer must do"; every differentiator is "what makes findings trustworthy enough that a regulatory analyst acts on them instead of re-reviewing from scratch." The precision bar is unusually high because the closest analog — legal AI — is actively being sanctioned for hallucinated citations (1,153 documented fake-citation cases as of Jan 2026). In regulatory review, a hallucinated deficiency wastes an expert's afternoon and destroys trust; grounding is not a feature, it is the license to operate.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Missing any of these and a regulatory analyst does not consider it a serious review tool.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Corpus ingestion — multi-format, nested, uncapped** | Real submissions are deep folder trees of hundreds of PDF+DOCX files | MEDIUM | PDF path exists; DOCX path is net-new. Must handle digital + scanned (OCR). No doc/depth cap is a hard requirement, not a nicety. |
| **Content-based document classification** | Folder/file names are unreliable; a reviewer knows "this is a stability report" from content | MEDIUM | Classify by content into CTD-ish roles (3.2.S.4 spec, 3.2.P.8 stability, QOS 2.3…) without hardcoding module paths. |
| **Evidence-cited findings (verbatim quote + locator)** | An uncited compliance claim is unactionable — the analyst must be able to open the exact passage | MEDIUM | doc → section → span anchor, re-openable. This is the core precision guarantee. Already an invariant in the existing `FaultReport` schema. |
| **Rule-linked verdict per finding** | A deficiency is meaningless without *which* FDA/ICH requirement it violates | MEDIUM-HIGH | Dual citation: submission passage **and** the guideline clause. Requires FDA/ICH corpus as retrievable reference. |
| **Compliance verdict + severity/tier** | Analysts triage; not all findings are equal (CRL-grade vs advisory) | LOW-MEDIUM | Reuse existing tier model (verified/corroborated/advisory). Map to regulatory severity (major/minor deficiency). |
| **Cross-document consistency checking** | The single most common real CMC deficiency class is spec/value mismatch across docs (e.g. QOS 2.3 vs 3.2 body) | HIGH | Table stakes *because* reviewers do it, but genuinely hard — see taxonomy §Cross-cutting. |
| **Corpus search / retrieval** | Can't reason over a 500-doc corpus by loading it all; reviewer must fetch on demand | MEDIUM | `search_corpus` / `get_section` tools. Retrieval infra (FAISS/Databricks) already exists. |
| **Structured, exportable review report** | Output must land in an analyst's workflow (triage queue, review doc), not a chat log | LOW-MEDIUM | Grouped by document/theme/severity; each row drillable to evidence. Human-in-the-loop is mandatory. |
| **Coverage / "what was reviewed" manifest** | Reviewers must know what the tool *looked at* to trust the absence of findings | MEDIUM | Borderline table-stakes now: without it, "no deficiencies found" is worthless. Enumerate docs/sections examined. |

### Differentiators (Competitive Advantage)

Where DefPredict competes. These align directly with the PROJECT Core Value (recall **and** precision, "no blabber").

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Grounded adversarial verification (refute-or-confirm)** | Every candidate deficiency must survive a verifier that re-reads source and tries to *kill* it — kills the hallucinated-finding failure mode | HIGH | The headline differentiator. Adversarial sub-agent returns an evidence-forced verdict; unsupported findings are dropped. Directly answers the legal-AI hallucination crisis. |
| **Dual-grounded, guideline-linked findings** | Analyst sees *both* the offending submission text and the exact rule clause side-by-side — auditable in seconds | HIGH | Requires the FDA/ICH corpus ingested as *reference* (consulted), never as answer-key oracle. |
| **Precedent retrieval (historical deficiency KB)** | "This looks like the CRL pattern from prior ANDAs" — grounds findings in what FDA has actually cited | MEDIUM | 500-row deficiency KB + vector search already exist. Reframe from single-doc to corpus reviewer. Raises credibility of judgment-class findings. |
| **Coverage tracking as a recall guarantee** | Turns "no-cap corpus" from a liability into a claim: shows sections reviewed, references followed, gaps not yet examined | MEDIUM-HIGH | Beyond table-stakes manifest: track *which review themes* were applied to *which* content, surface un-reviewed regions. Underpins recall claims in the eval harness. |
| **Agentic reference-following navigation** | Follows "see Section 3.2.S.4.2", hyperlinks, and value cross-refs like a human reviewer chasing a thread | HIGH | `follow_reference` + drive-loop. This is what makes it generalize to arbitrary corpora vs. one-shot slicing. |
| **Reference-graph cross-document contradiction detection** | Catches contradictions a linear reader misses (spec limit in three places, two agree) | HIGH | Build a value/reference graph across the corpus, then reason over inconsistencies. High-value, high-effort. |
| **Deterministic-first oracle layer for stable facts** | Numeric/structural checks (thresholds, presence, value equality) run cheaply and *never hallucinate* | MEDIUM | Keep deterministic checks ONLY for stable structural/consistency facts (per PROJECT), feeding the agent — not as the source of intelligence. High precision floor at low cost. |
| **Cost-managed corpus-scale reasoning** | Makes the agentic loop economically viable at 100s of docs (caching, compaction, cheap-triage, budgets) | HIGH | Not user-visible but the enabling differentiator — without it, corpus-scale agentic review is unaffordable. |
| **Calibrated confidence tied to evidence class** | Findings labeled by *how* they were established (code-verified vs quote-anchored vs model-judgment) | LOW-MEDIUM | Existing evidence-class model. Lets analysts trust deterministic findings instantly and scrutinize judgment ones. |

### Anti-Features (Commonly Requested, Often Problematic)

Documented to prevent scope creep. Most follow from "reviewer, not author / not decision-maker."

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-filing / submitting to FDA** | "Close the loop, save a step" | Regulatory submission is a legal act; a hallucinated or wrong filing is catastrophic and irreversible | Human stays in the loop; tool outputs a review, an analyst files. (Already Out of Scope in PROJECT.) |
| **Final regulatory determination ("approvable / not")** | People want a yes/no verdict | The tool surfaces cited *issues*; declaring compliance is an expert legal judgment it cannot own | Report deficiencies + severity; expert decides. Frame verdicts as "candidate deficiency," never "approval status." |
| **Unbounded autonomy without grounding** | "Let the agent just go" | Ungrounded autonomy is exactly the hallucination-generator that sinks legal-AI tools | Bounded loop: every claim pinned to retrieved verbatim evidence + verifier gate + budget ceiling. |
| **Answer-key oracles as primary intelligence** | Deterministic checks feel "safe" and precise | Hardcoded per-submission oracles don't generalize to new corpora — brittle, high-maintenance | Deterministic checks for *stable structural/consistency facts only*; intelligence comes from agent + retrievable rulebook. (PROJECT decision.) |
| **Hardcoded module/folder layout ("M3", "3.2.S.4.1")** | Submissions "usually" follow eCTD structure | Real corpora are misnamed, flattened, or idiosyncratic; hardcoding = silent misses | Infer structure from content; treat CTD roles as a semantic hypothesis, not a path lookup. |
| **Auto-drafting the deficiency response / remediating the dossier** | "Also write the fix" | Turns a reviewer into an author — different product, dilutes the trust/precision focus, and the fix needs the very expert the tool serves | Stay a critic. Optionally *suggest* what evidence would resolve a finding, but never author submission content. |
| **Continuous/real-time submission monitoring** | "Watch our RIM system live" | Massive infra scope creep orthogonal to the core review problem; corpora are reviewed in batches | Batch review of a directory on demand; defer streaming/monitoring to v2+ if ever. |
| **Uncalibrated numeric risk scores** | Dashboards love a "92% compliant" gauge | A precise-looking score with no evidence lineage invites false confidence — the opposite of the trust goal | Evidence-class labels + severity tiers grounded in citations; no fabricated aggregate score. |
| **Full-corpus context stuffing** | "Just load everything, models have big context now" | Defeats generality (no cap), explodes cost, and buries signal; degrades recall on large corpora | Retrieval + compaction; never load the whole directory. (PROJECT constraint.) |

---

## FDA/ICH Deficiency Taxonomy (Detection Target)

This is the *what-to-detect* catalog, organized by CTD Module 3 structure plus cross-cutting themes. **Detection difficulty** is the key column for architecture: it says whether a finding is a cheap deterministic oracle, a hybrid (deterministic flag → LLM adjudication), or pure judgment.

**Legend — Detection difficulty:**
- **DET** = deterministically checkable (presence/absence, numeric compare, threshold arithmetic) → oracle/checklist layer.
- **HYB** = deterministic *trigger* then judgment *adjudication* (e.g. detect a mismatch numerically, judge if it's a real deficiency; or a Q6A decision-tree gate: is this test even required for this product?).
- **JUD** = judgment/semantic — requires reading and reasoning (adequacy, sufficiency, scientific justification). This is where the agent + verifier earn their keep.

Grounding note: the *substance* below is HIGH-confidence (ICH guideline text + FDA OGD "Common Deficiencies in ANDAs" literature). Which are DET vs JUD is an engineering judgment (MEDIUM) — validate against the eval harness.

### A. Drug Substance — CTD 3.2.S

| # | Deficiency class | Governing guideline | What's wrong | Detection | Complexity |
|---|------------------|---------------------|--------------|-----------|------------|
| S1 | **Missing/incomplete required subsection** (nomenclature, structure elucidation, manufacturer, control, stability) | CTD/eCTD granularity; Q11 | A required 3.2.S.x block is absent or a stub | DET | LOW — structural presence check once content-classified |
| S2 | **Impurity above ICH threshold not identified/qualified** | Q3A(R2) | An impurity reported above the identification/qualification threshold with no structure/qualification | HYB | HIGH — needs max-daily-dose + threshold table + reading batch data; arithmetic is DET, "is qualification argument adequate" is JUD |
| S3 | **Genotoxic/mutagenic & nitrosamine impurity control gap** | ICH M7(R2); FDA nitrosamine guidance | No control strategy / AI (acceptable intake) limit for DNA-reactive or nitrosamine impurities | HYB | HIGH — presence of a control statement is DET-ish; adequacy vs. current recommended limits is JUD; **highest-salience current FDA driver** |
| S4 | **Residual solvent exceeds / not controlled to Q3C limit** | Q3C(R9) | Class 1 solvent used, or Class 2 above PDE, without justification | HYB | MEDIUM — class lookup + PDE compare is DET; solvent-in-process inference is JUD |
| S5 | **Elemental impurity risk assessment / PDE gap** | Q3D(R2) | No elemental-impurity risk assessment, or element above route-specific PDE | HYB | MEDIUM-HIGH — PDE table by route is DET; whether the risk assessment is complete is JUD |
| S6 | **Chiral / stereoisomer control missing** | Q6A (decision trees); FDA OGD | Chiral drug substance lacks chiral identity and/or chiral impurity control | HYB | MEDIUM — "is it chiral?" gate (JUD/DET from structure) then presence-of-test check (DET); a *cited common ANDA deficiency* |
| S7 | **Specification acceptance criteria unjustified / not stability-supported** | Q6A; Q1E | Limits set with no batch-data or stability justification | JUD | HIGH — reasoning over batch analyses + stability trend |
| S8 | **Analytical method not validated for its purpose / missing validation characteristics** | Q2(R2) | Method lacks required characteristics (specificity, accuracy, precision, LOD/LOQ, linearity, range) for its use category | HYB | MEDIUM-HIGH — checklist of expected characteristics vs. method type is DET; "is it *stability-indicating*/fit-for-purpose" is JUD |
| S9 | **LOD/LOQ not provided for impurity/residual-solvent methods** | Q2(R2); FDA OGD | Impurity/RS methods reported without detection/quantitation limits | DET | LOW — explicitly cited FDA common deficiency; presence check |
| S10 | **Reference standard source/lot/purity not stated** | Q6A 3.2.S.5; FDA OGD | Impurity or working standard lacks source, lot, purity | DET | LOW — explicitly cited FDA common deficiency |
| S11 | **Structure elucidation insufficient** | Q6A/Q11 3.2.S.3 | Characterization data don't support the claimed structure | JUD | HIGH — scientific adequacy |
| S12 | **Drug-substance stability data / retest period unsupported** | Q1A(R2), Q1E | Insufficient long-term/accelerated data or unsupported retest-period extrapolation | HYB | HIGH — duration/condition checks are DET; extrapolation adequacy (Q1E) is JUD |

### B. Drug Product — CTD 3.2.P

| # | Deficiency class | Governing guideline | What's wrong | Detection | Complexity |
|---|------------------|---------------------|--------------|-----------|------------|
| P1 | **Composition / description inconsistency** | Q6A 3.2.P.1 | Formulation table disagrees between P.1, batch records, and QOS | HYB | MEDIUM — numeric/component compare is DET; intent vs. typo is JUD |
| P2 | **Pharmaceutical development / CQA rationale gaps** | Q8(R2) | Critical quality attributes or control strategy not justified | JUD | HIGH — QbD reasoning |
| P3 | **Degradation-product impurity above Q3B threshold not addressed** | Q3B(R2) | Degradant above identification/qualification threshold not identified/qualified | HYB | HIGH — dose-keyed threshold arithmetic (DET) + qualification adequacy (JUD) |
| P4 | **Dissolution method/acceptance criteria inadequate** | Q6A; FDA product-specific guidance | Missing/weak dissolution test or unjustified criteria for solid oral | HYB | MEDIUM-HIGH — "is dissolution required?" gate (DET) + criteria adequacy (JUD) |
| P5 | **Drug-product spec not validated / method validation gap** | Q2(R2) | Same as S8 but for finished product | HYB | MEDIUM-HIGH |
| P6 | **Spec ↔ stability mismatch (limits not supported through shelf life)** | Q6A, Q1E | Release limits/end-of-shelf-life limits not supported by stability data | JUD | HIGH |
| P7 | **Container-closure suitability not demonstrated** | 3.2.P.7; FDA CCS guidance | Protection/compatibility/safety of CCS not shown for dosage form & route | JUD | MEDIUM-HIGH — a cited CRL area |
| P8 | **Extractables & leachables study missing/inadequate** | FDA CCS guidance; USP <661>/<1663>/<1664> | No E&L assessment, or leachables not tracked on stability (esp. parenteral/inhalation) | HYB | HIGH — presence of study is DET-ish; toxicological adequacy is JUD; a recurring ANDA deficiency |
| P9 | **Stability protocol/data insufficient for proposed shelf life** | Q1A(R2), Q1B, Q1C, Q1D, Q1E | <12mo long-term or <6mo accelerated at submission; wrong storage conditions; unsupported extrapolation; no photostability; missing bracketing/matrixing justification | HYB | HIGH — durations/conditions/**"significant change"** breaches are DET; shelf-life extrapolation (Q1E) is JUD |
| P10 | **Post-approval stability commitment absent** | Q1A(R2) | No commitment to continue stability on production batches | DET | LOW — presence check |
| P11 | **Excipient control inadequate** | 3.2.P.4; Q3D | Novel/critical excipient not controlled; elemental-impurity contribution ignored | JUD | MEDIUM |

### C. Cross-Cutting / Corpus-Level (the differentiator territory)

These are the **cross-document** deficiencies that a one-shot single-document detector *cannot* find — the reason the agentic corpus redesign exists.

| # | Deficiency class | Governing basis | What's wrong | Detection | Complexity |
|---|------------------|-----------------|--------------|-----------|------------|
| X1 | **Specification mismatch: QOS (2.3) vs body of data (3.2)** | CTD consistency; FDA OGD | Release/shelf-life limits differ between the module-2 summary and module-3 detail | HYB | HIGH — *the* classic cited CMC deficiency; numeric compare is DET *once the same spec is located in two docs*, which is the hard retrieval/alignment problem |
| X2 | **Value contradiction across documents** (batch #, lot, assay, limit, method params) | Data integrity | Same quantity stated differently in two+ places | HYB | HIGH — build value/reference graph, compare; adjudicate real vs. benign |
| X3 | **Method described inconsistently across docs** | Q2(R2) consistency | Analytical method parameters differ between validation report, spec, and stability protocol | JUD | HIGH — semantic method comparison |
| X4 | **Broken / unsatisfied cross-reference** | eCTD navigation | "See Section X" points to missing/irrelevant content, or a referenced study is absent | DET/HYB | MEDIUM — reference resolution is DET; "does target actually support the claim" is JUD |
| X5 | **Coverage gap — required content class absent corpus-wide** | CTD completeness | An expected review theme (e.g. elemental-impurity assessment) is absent from the *entire* corpus | HYB | MEDIUM-HIGH — depends on coverage tracking; "was this ever addressed anywhere?" |
| X6 | **Data-integrity / traceability break** | ALCOA+, 21 CFR 211 | Batch data can't be traced to the batches underpinning specs/stability | JUD | HIGH — reasoning across manufacturing, batch, stability docs |

**Taxonomy dependency note:** many threshold checks (S2, S3, S4, S5, P3) are only computable once the agent has extracted a *governing parameter* — maximum daily dose, route of administration, dosage form. Those parameters are themselves often stated in one document and needed in another → they depend on X-class cross-document retrieval. **This means the cross-cutting corpus layer is a prerequisite for correct thresholding, not an add-on.**

---

## Feature Dependencies

```
Corpus ingestion (PDF+DOCX, nested, uncapped)
    └──requires──> DOCX parse path (converge on existing structured model)
    └──requires──> Content-based classification
                        └──enables──> Deterministic oracle layer (structural presence)

Corpus search / retrieval  ──requires──> Content classification + chunk index
    └──enables──> Agentic reference-following navigation
                        └──enables──> Reference-graph cross-document contradiction (X1, X2, X4)
                                            └──enables──> Correct dose/route-keyed thresholds (S2–S5, P3)

FDA/ICH corpus as retrievable reference
    └──requires──> Rulebook ingestion (open-source FDA guidances + ICH guidelines)
    └──enables──> Rule-linked verdicts (table stakes)
    └──enables──> Dual-grounded guideline-linked findings (differentiator)

Grounded evidence anchors (verbatim quote + locator)
    └──requires──> Agentic navigation (agent must have *retrieved* what it cites)
    └──enables──> Adversarial verifier (refute-or-confirm re-reads the anchor)
                        └──gates──> Every JUD-class finding before it survives

Coverage tracking ──enhances──> Recall claims + Eval harness (precision/recall gate)

Cost controls (caching / compaction / cheap-triage / budgets)
    └──enables──> Corpus-scale operation of ALL of the above (no cap)

Deterministic oracle layer  ──conflicts──>  Answer-key oracles as primary intelligence
    (keep the former for stable facts ONLY; the latter is an anti-feature)
```

### Dependency Notes

- **Thresholding depends on cross-document retrieval:** S2–S5/P3 threshold math needs max-daily-dose/route/dosage-form that often live in a *different* document than the impurity table. The corpus/reference-graph layer is therefore a hard prerequisite for the "easy-looking" arithmetic checks — do not schedule threshold oracles before cross-doc retrieval exists.
- **Adversarial verifier depends on true grounding:** the verifier can only refute-or-confirm if the candidate finding carries a re-openable anchor. Grounding discipline must land *before* (or with) the verifier, not after.
- **Rule-linked verdicts depend on the rulebook corpus:** you cannot cite "violates Q3C Class-2 PDE" without the ICH text ingested as reference. Rulebook ingestion gates the entire "guideline-linked" value prop.
- **Everything at scale depends on cost controls:** caching/compaction/budgets aren't a feature phase — they're the substrate that lets the uncapped-corpus promise be real. Under-investing here caps corpus size in practice, silently violating the core generality constraint.
- **Deterministic layer conflicts with oracle-as-intelligence:** keep the deterministic checks narrow (presence, equality, threshold arithmetic). The moment they become the *source* of findings you've rebuilt the brittle answer-key the redesign exists to escape.

---

## MVP Definition

### Launch With (v1) — prove "grounded corpus reviewer that generalizes"

- [ ] **Corpus ingestion (PDF+DOCX, nested, uncapped) + content classification** — without it there is no corpus reviewer.
- [ ] **Agentic loop + core navigation tools** (`search_corpus`, `open_doc`, `get_section`, `follow_reference`, `read_guideline`) — the mechanism that generalizes.
- [ ] **FDA/ICH rulebook ingested as retrievable reference** — required for any rule-linked verdict.
- [ ] **Grounded, dual-cited findings** (submission span + rule clause) — the precision guarantee / "no blabber."
- [ ] **Adversarial verifier gate** — the differentiator that makes findings trustworthy; refute-or-confirm before survival.
- [ ] **Deterministic oracle layer for the DET-class deficiencies** (S1, S9, S10, P10, X4-presence) — cheap, hallucination-proof precision floor + high-value quick wins that are *cited FDA common deficiencies*.
- [ ] **A first slice of cross-document consistency (X1 spec mismatch, X2 value contradiction)** — this is the reason the redesign exists; ship at least the flagship cross-doc check.
- [ ] **Structured, drillable report + coverage manifest** — output an analyst can act on and trust.
- [ ] **Eval harness (precision/recall vs. ANDA ground truth)** — "reliable" must be measured, not asserted; gates everything.

### Add After Validation (v1.x) — deepen the taxonomy once the loop is trustworthy

- [ ] **Threshold-arithmetic deficiencies** (S2/S3 nitrosamine-M7/S4/S5, P3) — trigger: cross-doc retrieval of dose/route/dosage-form is solid enough to key thresholds correctly.
- [ ] **Stability adequacy suite** (S12, P6, P9, P10) — trigger: stability docs classify reliably; add Q1A/Q1E duration+condition+"significant change" checks then extrapolation judgment.
- [ ] **Method-validation completeness (S8/P5) against Q2(R2) characteristic checklist** — trigger: method reports classify reliably.
- [ ] **Precedent-retrieval overlay on judgment findings** — trigger: base findings are precise; use the 500-row KB to raise credibility, not to generate.
- [ ] **Reference-graph contradiction detection (X3, X5, X6)** — trigger: X1/X2 validated; generalize to semantic method/coverage/traceability contradictions.

### Future Consideration (v2+)

- [ ] **Biologics / Module 3 biotech track** (Q6B, Q5C) — defer: chemical/small-molecule CMC is the seeded ground-truth domain.
- [ ] **Modules 4–5 (nonclinical/clinical) review** — defer: CMC Module 3 is where the ground truth and value density are; prove there first.
- [ ] **Suggested-resolution hints** ("what evidence would clear this") — defer: stays reviewer-side, but only after precision is proven; must never drift into auto-authoring.
- [ ] **Multi-region divergence** (FDA vs EMA vs PMDA expectation deltas) — defer: single-authority (FDA/ICH) first.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Corpus ingestion (PDF+DOCX, nested, uncapped) | HIGH | MEDIUM | P1 |
| Content-based classification | HIGH | MEDIUM | P1 |
| Agentic loop + navigation tools | HIGH | HIGH | P1 |
| Grounded dual-cited findings | HIGH | MEDIUM | P1 |
| Adversarial verifier gate | HIGH | HIGH | P1 |
| FDA/ICH rulebook as reference | HIGH | MEDIUM | P1 |
| Deterministic oracle layer (DET deficiencies) | HIGH | LOW-MEDIUM | P1 |
| Cross-doc spec/value consistency (X1, X2) | HIGH | HIGH | P1 |
| Structured report + coverage manifest | HIGH | LOW-MEDIUM | P1 |
| Eval harness (precision/recall) | HIGH | MEDIUM | P1 |
| Cost controls (caching/compaction/budgets) | MEDIUM (enabling) | HIGH | P1 (enabling) |
| Threshold-arithmetic deficiencies (S2–S5, P3) | HIGH | HIGH | P2 |
| Stability adequacy suite (Q1/Q1E) | HIGH | HIGH | P2 |
| Method-validation completeness (Q2R2) | MEDIUM-HIGH | MEDIUM | P2 |
| Precedent retrieval overlay | MEDIUM | LOW (exists) | P2 |
| Reference-graph contradiction (X3, X5, X6) | HIGH | HIGH | P2/P3 |
| Biologics / Modules 4–5 | MEDIUM | HIGH | P3 |
| Suggested-resolution hints | LOW-MEDIUM | MEDIUM | P3 |

**Priority key:** P1 = must have for launch · P2 = should have, add when possible · P3 = nice to have, future.

---

## Competitor Feature Analysis

The critical insight: **the field is dominated by authoring tools; the grounded-reviewer niche is nearly empty.**

| Capability | Authoring tools (Celegence, Narrativa, Weave Bio) | "Content challenger" (Peer AI) | Legal-AI review (Harvey, GC AI) | DefPredict approach |
|------------|---------------------------------------------------|--------------------------------|----------------------------------|---------------------|
| Primary mode | **Generate** dossier content | Challenge draft during internal QC | Review/redline contracts | **Find cited deficiencies** in a submitted corpus |
| Corpus scope | Document being authored | Documents under review | Contract(s) provided | Arbitrary nested PDF+DOCX directory, uncapped |
| Grounding | Varies; generation-oriented | Human-in-loop QC | Every clause → source paragraph (maturing hard) | Mandatory verbatim anchor + rule clause; verifier-gated |
| Adversarial verification | No | Partial (challenger framing) | Emerging (citation-grounding research) | **Core** refute-or-confirm gate |
| Cross-document consistency | Limited | Limited | Limited (per-contract) | **Core** reference-graph across corpus |
| Rule linkage | Templates/style | SME review | Playbook/precedent | Retrievable FDA/ICH rulebook, dual-cited |
| Regulatory determination | No | No | No | **Deliberately No** (anti-feature) |

**Whitespace:** an agentic reviewer that (a) ingests an arbitrary corpus, (b) grounds every finding in verbatim source + rule, (c) verifies adversarially, and (d) catches cross-document contradictions — is not something the current pharma-AI authoring market offers. The nearest patterns worth borrowing are from **legal AI** (citation grounding as the trust mechanism) and its cautionary tale (hallucinated citations → sanctions → grounding is existential).

---

## Sources

**ICH / regulatory guideline structure (HIGH confidence):**
- [ICH Q2(R2) Validation of Analytical Procedures — Step 4, 2023-11-30](https://database.ich.org/sites/default/files/ICH_Q2(R2)_Guideline_2023_1130.pdf) — adopted 1 Nov 2023, effective mid-2024; adds biologics, multivariate/spectroscopic; paired with Q14.
- [ISPE — Streamlining Analytical Procedure Development: ICH Q2(R2) and Q14](https://ispe.org/pharmaceutical-engineering/ispeak/streamlining-analytical-procedure-development-validation-and)
- [ICH Q3A(R2) Impurities in New Drug Substances](https://database.ich.org/sites/default/files/Q3A(R2)%20Guideline.pdf) — reporting/identification/qualification thresholds keyed to max daily dose.
- [EMA — ICH Q3C(R9) Residual Solvents](https://www.ema.europa.eu/en/ich-q3c-r9-residual-solvents-scientific-guideline) — R9 Step 4 Jan 2024, Step 5 effective 29 Apr 2024; Class 1/2/3 + PDE.
- [ICH Q3D(R2) Elemental Impurities — Step 4, 2022](https://database.ich.org/sites/default/files/Q3D-R2_Guideline_Step4_2022_0308.pdf) — adopted Apr 2022; route-specific PDEs.
- [ICH Q1A(R2) Stability Testing of New Drug Substances and Products](https://database.ich.org/sites/default/files/Q1A(R2)%20Guideline.pdf) — long-term/intermediate/accelerated conditions, significant-change; with Q1B–E.
- [ICH Q6A Specifications — decision trees #1–8 (ECA Academy)](https://www.gmp-compliance.org/guidelines/gmp-guideline/ich-q6a-attachments-decision-trees-1-through-8) — universal + specific tests, acceptance-criteria decision trees.

**FDA CMC deficiency literature (HIGH/MEDIUM — real-world deficiency patterns):**
- [FDA Perspectives: Common Deficiencies in ANDAs — Part 1: Drug Substance (Pharmaceutical Technology)](https://www.pharmtech.com/view/fda-perspectives-common-deficiencies-abbreviated-new-drug-applications-part-1-drug-substance) — impurity reference-standard source/lot/purity, chiral controls, LOD/LOQ, USP identity tests.
- [Part 2: Description, Composition, Excipients](https://www.pharmtech.com/view/fda-perspectives-common-deficiencies-abbreviated-new-drug-applications-part-2-description-compositio)
- [Part 3: Control of the Drug Product and Stability](https://www.pharmtech.com/view/fda-perspectives-common-deficiencies-abbreviated-new-drug-applications-part-3-control-drug-product-a) (HTTP 403 on fetch; corroborated via search excerpts)
- [CMC Deficiency Patterns in ANDA Review — systematic review (IJPS)](https://www.ijpsjournal.com/article/CMC+Deficiency+Patterns+in+ANDA+Review:+A+Systematic+Review+of+Regulatory+Expectations+in+Healthcare+) — chemistry ≈34% of ANDA deficiencies; 74% of 2020–2024 CRLs cited quality/manufacturing; QOS 2.3 vs 3.2 spec mismatch.
- [Extractables & Leachables overview (Pharmaceutical Technology / NCBI)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12846058/) — CCS suitability + leachables-on-stability as recurring ANDA deficiencies.

**Agentic / document-review feature landscape (MEDIUM — nascent niche, triangulated):**
- [Peer AI vs Weave Bio — Regulatory AI Tools Analysis (IntuitionLabs)](https://intuitionlabs.ai/articles/peer-ai-weave-bio-regulatory-tools-analysis) — Peer AI "agentic virtual content challenger," human-in-the-loop.
- [Narrativa — Agentic AI for Regulatory Life Sciences](https://www.narrativa.com/ai-agents-regulatory-life-sciences/) — cross-referencing, version control (authoring-oriented).
- [Celegence — AI-Powered CMC Regulatory Writing](https://www.celegence.com/ai-powered-cmc-regulatory-writing-pharma-structured-automation-authoring/) — authoring, not review.
- [Harvey — How AI Is Transforming Contract Review](https://www.harvey.ai/blog/how-ai-is-transforming-contract-review-software) — "audit, don't trust": every extraction links to source paragraph.
- [GC AI — Legal Document Review 2026](https://gc.ai/blog/legal-document-review)
- [Who Checks the Citations? Benchmarking Legal Hallucination Detection (arXiv)](https://arxiv.org/pdf/2606.21155) — fabricated citations in 17–33% of legal-AI responses; grounding as existential.
- [AI Hallucinations in Legal Work (2026)](https://thelegalprompts.com/blog/ai-hallucinations-legal-work-avoid-sanctions-2026) — 1,153 documented fake-citation cases (Jan 2026), accelerating.

---
*Feature research for: agentic FDA/ICH regulatory-compliance reviewer (CMC / Module 3)*
*Researched: 2026-07-30*
