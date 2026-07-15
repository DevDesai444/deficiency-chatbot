# DefPredict Roadmap

Working document. Not a spec. Update as decisions land.

Line references below were verified against `main` @ `f0c285c` and may have shifted.

## Status — `main` @ `f3b9cf9`

| Branch | State |
|---|---|
| `fix/parse-repair-eventtype` | merged `f0c285c` |
| `fix/extraction-handoff-fidelity` | merged `1ebd05a` — **the gate is open** |
| `fix/json-extractor-consolidation` | merged `26ca4ab` |
| `fix/classifier-coverage-floor` | merged `ffff051` |
| `feat/coverage-and-commitments-specialist` | merged `f3b9cf9` |
| `fix/analysis-status-and-verdicts` | **unmerged** by choice — `27bb4e5`, tested, parked |
| Branches 4, 5, 6 below | not started — no longer gated |

Anchor digit guard landed separately at `846c81e`: fuzzy matching cannot adjudicate a
quantity, so a span carrying a number must match the source exactly. Without it a quote
reading `32.727` anchored against a source reading `22.727` — the anchor would have
passed a hallucinated D1, the deficiency it exists to catch.

Suite: 135 passing, 12 skipped (was 45 before this work).

### Known issues, none blocking

- `classifier.py:38` joins `SectionSummary.summary` into a prompt untruncated while every
  sibling field is capped. `summary` now carries model prose rather than a short heading —
  measured 8x growth on a 29-page document. Fits the current window; breaches around 200
  sections.
- `extraction/group.py` runs one `structured_call` per group in a serial loop. Five groups
  means five sequential round-trips. `asyncio.gather` is safe here — the loop body only
  appends, and the index map is group-local.
- Layer 2 does not anchor. `numeric_claims` / `guidance_refs` / `table_ref` come straight
  from the Layer 2 consensus with no source verification, so a fabricated numeric rides in
  unverified. Layer 1 anchors; Layer 2 does not.
- `filter_anchored` keeps findings with empty `evidence`, so a model that omits evidence
  bypasses anchoring entirely and the result is indistinguishable from an anchored finding.
  Dropping them would let code suppress an observation — surfacing them as `unverified` is
  the better shape.
- A per-group `structured_call` failure degrades that group to heading-only — the exact
  defect this work removed — and the run still reports success. `parse_repair` fires, but
  nothing reaches the final report.

---

---

## The primary defect

`src/agents/extraction/group.py:106-127` rebuilds every section as
`SectionSummary(section_id=..., summary=section.heading)`. `section.text` and
`section.tables` are read **nowhere** in that loop. `group.py:125` hardcodes
`findings=[]`. `key_values` (`src/schemas/documents.py:70`) has exactly one
repo-wide hit — its own declaration. No writer, no reader.

`src/agents/detection/group.py:166` — `report_text = json.dumps(intermediate_report.model_dump())`
— is the *sole* channel into the detection prompt at `:175`. Layer 2 receives a
heading list plus one prose blob (`consensus_notes`).

The extraction agents genuinely read the full text and table cells
(`extraction/agent.py:42-49` emits `section.text[:4000]` plus table rows). Their
output is then discarded 60 lines later.

**Verified by payload reconstruction** — substring probes against what Layer 2
actually receives:

| Probe | Present? |
|---|---|
| `22.727` / `8.72` | No |
| `Table 16` | No |
| `PDE` / `Class 3` | No |
| `2-Butanone` | No |

## Reference failure: Combipatch E&L report

29-page E&L report. Human analyst found 7 deficiencies. Pipeline ran healthy
(478s, no crash, `flaws_found=true`) and returned **1 generic uncited finding**.

| ID | Deficiency |
|---|---|
| D1 | AET typo: p.7 says 22.727 µg/g, should be 8.72 (contradicts pp. 9/23/24/25) |
| D2 | USP <88> run for backing film + release liner but not pouch — no justification |
| D3 | Elemental E&L threshold should use SCT-derived AET, not PDE |
| D4 | ICH Q3D(R2) cutaneous route: only Class 1 + 2A required for transdermal |
| D5 | Table 16 typo: Class 3 row result cell says "Class 1 elements below PDE levels" |
| D6 | 2-Butanone/2-Pentanone in both DP and RLD per Annexure-4; conclusion needs clarification |
| D7 | No commitment to continue leachable monitoring through shelf life |

**D1–D6 die at `extraction/group.py:106-114`.** D7 survives (an *absence* claim —
a heading list suffices) and arrives degraded as `general_cmc` via the default at
`detection/group.py:97`. One generic uncited finding from a 29-page report is
precisely what this mechanism predicts.

## Unified causal model

| Deficiency | First death | Subsequent deaths | Fix |
|---|---|---|---|
| D1 | `extraction/group.py:106-114` | `classifier.py:35-40`; `prompts.py:88-108` (no numeric field); `prompts.py:64` | Branch 1 |
| D2 | `extraction/group.py:106-114` | `classifier.py:62` `[:4]` drops Container/Closure; `flaw_types.py:8-22` | Branch 1 |
| D3 | `extraction/group.py:106-114` | `classifier.py:62` drops Elemental Impurities; no rulebook | Branch 1, then 4 |
| D4 | **Partial** — `document_type` survives, "Class 3 tested" invisible | 8B lacks route logic — **binding even post-fix** | Branch 1 unblocks; **Branch 4 resolves** |
| D5 | `extraction/group.py:106-114` — **not the splitter** | `prompts.py:88-108` (no table-ref field) | Branch 1 |
| D6 | `extraction/group.py:106-114` | Container/Closure selection; no numeric field | Branch 1 |
| D7 | **Survives.** First death: `flaw_types.py:8-22` — no catalog entry framing absence as a hunt target | `prompts.py:88-108` → emerges as `general_cmc` | Branch 2 |

---

## Branch plan

### Ship now (exist, tested, unmerged)

Neither moves any of D1-D7 alone — `git diff main..<branch> -- src/agents/extraction/group.py`
is **empty for both**. They harden parsing of a payload that is already empty.
Merge anyway: both de-risk the branches that follow.

| Order | Branch | Commit | Why still merge |
|---|---|---|---|
| 0a | `fix/json-extractor-consolidation` | `9c3ea6a` | `rindex("]")` grabs prose brackets → `JSONDecodeError` → silent `[]`. **More important post-Branch-4**, which makes bracketed guidance citations routine. Merge before Branch 3 — same fallback line. |
| 0b | `fix/analysis-status-and-verdicts` | `27bb4e5` | Makes CLEAN distinguishable from PARSE_FAILED — the instrument that would have caught this on day one. Directly serves the zero-recs rule. Branch 6 extends its `loop.py` changes. |

### Branch 1 — `fix/extraction-handoff-fidelity` — THE GATE

- **Unblocks**: D1, D2, D3, D5, D6 fully; D4 partially — **6 of 7**
- **Depends on**: nothing. **Nothing else moves until this lands.**
- **What**: `summary` comes from the extraction agents' own output, not
  `section.heading`. Populate `key_values` with numerics/labels the agents
  surfaced. Carry `page_start`/`page_end` through `SectionSummary`. Stop
  hardcoding `findings=[]` (`group.py:125`) — land real `ExtractionFinding`
  objects (`documents.py:59-63`, defined but never constructed). Add
  `numeric_claims`, `guidance_refs`, `table_ref` to `FlawFinding`
  (`flaws.py:61-68`) and to `FINDING_EXTRACTOR` (`prompts.py:88-108`, currently
  five keys, none numeric or citational).
- **AI-native**: LLM decides what is salient — which numbers, which cells, which
  claims. No checklist of expected values, no per-section required fields, no
  thresholds. Code does exactly one deterministic thing: **substring-anchor
  verification** — every quoted span must appear verbatim in the originating
  `ParsedSection.text` or an `ExtractedTable.rows` cell. Unanchored spans are
  dropped and counted, never corrected.
- **Zero-recs**: Anchoring only *removes* fabricated content. An agent emitting
  nothing yields `key_values={}` and zero findings; `flaws_found=len(findings) > 0`
  (`detection/group.py:216`) stays false. Nothing here manufactures a finding.
- **Files**: `src/agents/extraction/group.py`, `src/agents/extraction/agent.py`,
  `src/schemas/documents.py`, `src/schemas/flaws.py`, `src/llm/prompts.py`, new
  `src/agents/extraction/anchor.py`
- **Effort**: ~10 agent-hours; 2 human review days
- **Test**: Run Combipatch. Dump the `IntermediateReport` handed to Layer 2 and
  grep it. **Expected: `22.727` and `8.72` both present with page anchors;
  `Table 16` and `PDE` present.** Today all four are absent — binary observable,
  independent of whether detection improves.
- **Does NOT fix**: Doesn't guarantee detection *acts* on the data. D4 stays
  blocked (needs Branch 4). D7 unaffected.

### Branch 2 — `feat/coverage-and-commitments-specialist`

- **Unblocks**: D7; reinforces D2
- **Depends on**: nothing — **ships today, parallel with Branch 1**
- **What**: `FLAW_TYPE_DEFINITIONS` (`flaw_types.py:8-22`) has 13 entries, all
  framed as defects in *present* content. None frame *absence* as a hunt target.
  Add catalog entries for negative-space reasoning plus a specialist prompt.
- **AI-native**: The catalog is vocabulary, not routing — as `flaw_types.py:1-4`
  already states. One-line natural-language descriptions the LLM interprets. No
  "shelf-life commitment required for E&L" rule.
- **Zero-recs**: Inherits `prompts.py:47` — *explicitly state "No {flaw_type}
  deficiencies identified" — do NOT force findings*.
- **Files**: `src/agents/detection/flaw_types.py`, `src/llm/prompts.py`
- **Effort**: ~4 agent-hours; 1 human review day
- **Test**: Combipatch → finding naming the absent shelf-life monitoring
  commitment (D7), categorized as something other than `general_cmc`. Plus a
  known-clean document → zero findings.

### Branch 3 — `fix/classifier-coverage-floor`

- **Unblocks**: insurance across D2, D3, D4, D6
- **Depends on**: nothing (~2 hrs)
- **What**: `classifier.py:62` returns `list(FLAW_TYPE_DEFINITIONS.keys())[:4]` on
  parse failure — Specification/CoA, Method/Validation, Impurities, Stability.
  For an **E&L report** this excludes Container/Closure (`flaw_types.py:14`) and
  Elemental Impurities (`:21`) — the only two that matter. Dict-insertion-order
  arbitrary, not curated. Also `classifier.py:56` lets `[]` pass validation
  (`all()` vacuously true over empty) → zero specialists spawned.
- **AI-native**: *Removes* an accidental hard-coded rule rather than adding one.
  No doc-type→category mapping. LLM still selects freely at `classifier.py:44-57`.
- **Before scoping**: read the Combipatch event log — `detection/group.py:132-135`
  emits the selected categories. If it names exactly those 4, the fallback fired
  live and this is urgent, not insurance.

### Branch 4 — `feat/guidance-corpus-and-framework-retrieval`

- **Unblocks**: D3, D4
- **Depends on**: **Branch 1** — retrieval keyed on content that doesn't exist
  retrieves nothing; citations need `guidance_refs` to land in
- **What**: Retrieval over a corpus of actual guidance documents (ICH Q3D(R2),
  PQRI). Passages retrieved by semantic similarity, injected as context. The
  agent reasons from the *text of the guidance*, as a human analyst reads source.
- **AI-native**: The corpus is *source text*, not encoded rules. No
  `if route == "transdermal": require Class 1, 2A` anywhere. Deterministic part:
  the cited passage must exist verbatim in the corpus — same anchoring primitive
  as Branch 1.
- **Files**: new `src/knowledge/corpus/`, `src/knowledge/retrieval.py`,
  `src/agents/detection/group.py` (`_build_context_for_flaw_type` at `:170` is
  the existing hook)
- **Effort**: ~14 agent-hours; 3 human review days

### Branch 5 — `feat/consistency-and-contradiction-agent`

- **Unblocks**: D1; surfaces D6
- **Depends on**: **Branch 1** — comparing numerics across pages is a no-op
  against a heading list
- **What**: A specialist comparing `numeric_claims` across sections/pages.
- **AI-native**: LLM decides which claims are comparable and whether a delta is a
  contradiction or a legitimate difference. Code confirms only that both values
  were anchored to real page text. No tolerance thresholds, no expected-value table.
- **Effort**: ~8 agent-hours; 2 human review days

### Branch 6 — `fix/evaluator-oracle-and-escalation`

- **Unblocks**: **zero of 7** — buys detection of the *next* silent collapse
- **Depends on**: Branch 1
- **What**: `loop.py:70` passes `evaluate_corrections(corrections, flaw_report.consensus_summary)`
  — prose only. `flaw_report.findings` is never passed; the signature
  (`evaluator.py:11-14`) can't accept it. Pass structured findings.
- **AI-native**: Evaluator remains an LLM judge. **No arithmetic gate forcing
  `len(corrections) >= len(findings)`** — that would violate the zero-recs rule.
- **Zero-recs**: **Load-bearing.** A report with zero findings must still yield
  zero recommendations and PASS. Coverage judgment must be vacuously satisfied at
  zero, never "you missed some."
- **Test**: Inject a `FlawReport` with 7 findings, stub the suggestor to 1
  correction. **Expected: verdict ≠ PASS.** Today it PASSes.

---

## Ship sequence

| # | Branch | Observable after merge |
|---|---|---|
| 0a | `fix/json-extractor-consolidation` | No behavior change on Combipatch. Prose-bracket regression test passes. |
| 0b | `fix/analysis-status-and-verdicts` | Run reports a *status*, not just `flaws_found=true`. Instrumentation before surgery. |
| **1** | **`fix/extraction-handoff-fidelity`** | **`22.727`, `8.72`, `Table 16`, `PDE` appear in the Layer-2 payload. Finding count rises from 1. D5 and D6 plausibly land immediately.** |
| 2 | `feat/coverage-and-commitments-specialist` | D7 named specifically, correctly categorized. *Parallel with 1.* |
| 3 | `fix/classifier-coverage-floor` | Container/Closure + Elemental Impurities named in the `agent_spawned` event. |
| 4 | `feat/guidance-corpus-and-framework-retrieval` | D3 and D4 land with anchored citations. |
| 5 | `feat/consistency-and-contradiction-agent` | D1 lands with both values and both page numbers. |
| 6 | `fix/evaluator-oracle-and-escalation` | Injected 7-findings/1-correction test no longer PASSes. |

Branches 1 and 2 run concurrently. Branch 3 is hours with no dependency.

---

## Dropped / rescoped

| Item | Verdict | Reason |
|---|---|---|
| `feat/structured-tables-and-numeric-claims` (prior plan) | **DROP — ~70% dead work** | The table half **already ships**: `ExtractedTable` (`documents.py:38-42`) preserves `headers`/`rows`/`page` verbatim; `section_splitter.py:144-185` sets `page_start`/`page_end`. Do not build `TableArtifact`. The `numeric_claims` half folds into Branch 1. |
| Prior "Mode D — section splitter paraphrases tables" | **FALSE** | The splitter preserves rows. The fidelity Mode D wanted to build exists and is thrown away at `group.py:106`. |
| RC-3 — CorrectionList truncation | **Separate ticket, 0 of 7** | Real latent bug: `_extract_json_blob`'s `rfind("}")` chops at the last complete element, `json_repair` closes the array, Pydantic validates a shorter list with no error/no ParseFailed/no log (empirically 3 intended → 2 returned). But corrections are downstream of findings, and 7 verbose corrections ≈2374 tokens never reach the 4096 ceiling. Fires only past ~25 corrections. |
| RC-5 — evaluator blindness | **Reclassified: missing control, not cause** | A perfect evaluator handed a faithful 1-of-1 still returns PASS. Explains why nobody *noticed*. → Branch 6. |

## Lower-priority (from earlier code review)

| Branch | Fixes |
|---|---|
| `fix/loop-and-extractor-hardening` | Terminal fallthrough emits ISSUES_FOUND with 0 recs; `_find_balanced_array` picks first span not longest |
| `fix/faiss-globals-lock` | `_faiss_index`/`_faiss_id_map` mutated without lock; concurrent search reads partial state |
| `fix/health-check-import` | Health check imports private `_run_sql`; brittle on refactor |
| `fix/section-page-metadata` | All sections claim `page_start`=first, `page_end`=last — provenance broken |
| `refactor/dedupe-model-client` | `_make_model_client` duplicated across extraction and detection |

---

## Honest capability ceiling

After all six ship: **5 of 7 reliably, 6 on a good run, 7 rarely.**

**D4 is weakest.** Even with Q3D(R2) retrieved, the reasoning is: transdermal ⇒
cutaneous route ⇒ only Class 1 + 2A required ⇒ Class 3 tested but not required ⇒
*therefore scope wasn't route-scoped*. Three hops over retrieved text, executed by
**Llama 3.1 8B** (`detection/group.py:128` uses the agent client; only the
moderator gets 70B). **The corpus makes D4 possible, not likely.** If D4 must be
reliable, the honest fix is a model upgrade for that specialist — not another feature.

**D1 is fragile differently.** Cross-page numeric reconciliation requires the
consistency agent to recognize `22.727` and `8.72` are the same quantity — AET for
the same product — rather than two unrelated numbers. Nothing deterministic can
establish that; it's a semantic judgment. An 8B will produce false positives
alongside true ones. Expect noise.

**Structural ceiling nothing here touches:** `prompts.py:64` — *"A finding needs at
least one corroboration from another agent to survive"* — contradicts
`prompts.py:54` — *"Only report and discuss findings in YOUR specific domain."*
Line 64 demands corroboration from agents line 54 forbids from speaking. **Every
one of D1-D7 is a single-domain finding.** The gate is prompt-only, never enforced
in code (`_extract_structured_findings` has no corroboration filter), and
self-neutralizes at `prompts.py:65,69` (DROPPED requires a *successful* challenge;
silence is abstention). An uncorroborated-unchallenged finding has **no defined
disposition** — the outcome is stochastic. Latent recall hazard across all seven.
Fix is a prompt rewrite whose effect is unmeasurable until Branch 1 lands.
**Revisit after Branch 1 with real data.**

**PyMuPDF cannot read what isn't text.** Deficiencies in scanned pages or
image-embedded tables are invisible at Layer 1 regardless of everything downstream.

**None of this is validated on n=1.** Combipatch is one document with one
analyst's ground truth. The plan is engineered to a signature that matches one
run's prediction exactly — strong evidence, but "6 of 7 on Combipatch" is a
test-set score on the set we fit to. Before trusting these numbers, run the
post-Branch-1 pipeline against at least two more documents with known analyst
findings, **including one genuinely clean one to confirm the zero-recs rule holds.**

---

## Hard rules

- **No hard-coded regulatory rules, checklists, or thresholds.** LLM decides what
  is a finding; code only verifies claims are anchored in source text.
- **Zero recommendations must remain a legitimate outcome.** A clean document
  returns `analysis_status="clean"` with 0 recs. That is success.
- **No AI-tool metadata** in commits or files.
- **Never touch the `amn_dev_databricks` catalog.** Use `defpredict` only.
- Adversarially verify each substantive change with ≥3 lenses before merging.
