# Phase 5: Deterministic Structural & Cross-Document Recall (β) - Research

**Researched:** 2026-08-06
**Domain:** Deterministic recall (structural comparisons, reference graph, precedent similarity, retrieval-surface fixes) — Python 3.11+, PyMuPDF + python-docx parse layer, pydantic v2, FAISS + bge-m3, on-prem Databricks only
**Confidence:** HIGH (all findings verified against live repo code, file:line cited)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Structural pillar (RECALL-02) — LOCKED:**
- D-STR1: Scope = summary-vs-detail value mismatch + result-exceeds-spec-limit + labeled-aggregate recompute over a general label vocabulary (Total/Sum/Maximum/Minimum/Average/Mean). Not two bespoke checks — one general family that captures Table 19 (total 0.14% < single-largest 0.15%) and Table 20 (Max cell 11477 vs true 12601).
- D-STR2: Det/interp litmus = pure-computation-only. Verdict is purely a computation over ≥2 re-openable values. Zero domain-semantic judgment. Any "is this the right statistic?" → Phase 7. A compared value MAY resolve from a rulebook rule span (e.g., spec limit), never an inline float constant.
- D-STR3: Grounding anchor = typed `StructuralAnchor` (sibling of `CoverageAbsenceAnchor`): one claim span + N basis span-IDs + relation enum {EQUALS, LEQ/ordering, SUM|MAX|MIN|MEAN} + expected-vs-actual. Re-derivable — verifier RE-RUNS the computation. Cells resolved via `tables.py (table_id,row,col)→SpanID`; over-emit with scoping-confidence flag when not cleanly addressable.
- D-STR4: Value normalization/tolerance = exact, unit-aware, abstain-on-doubt with PRECISION-DERIVED comparison (no epsilon constant). One general normalizer; compare at stated decimal precision of claim/limit operand; matches USP/ICH General-Notices rounding (0.104 vs NMT 0.10 → complies).
- D-STR5: Input surface = addressable table cells ONLY (`tables.py`). Table-tier-unavailable docs are SKIPPED but LOGGED and routed to Phase 7. Never silently dropped.

**Reference graph + contradictions (RECALL-03) — LOCKED:**
- D-REF1: Edge kinds = all three: hyperlinks (DOCX/PDF link metadata) + textual references ("see §X", "Table N", module citations) + numeric value cross-refs. General patterns over spans, no corpus anchors.
- D-REF2: Emit shape = one typed `ReferenceAnchor` + anomaly enum {UNRESOLVED_REF, ABSENT_TARGET, VALUE_CONTRADICTION} + src span + optional dst span(s).
- D-REF3: VALUE_CONTRADICTION is a full candidate only when an actual cross-reference edge connects the two values' locations. Also emit label/identifier-matched contradictions tagged low-confidence (D-ABS2 over-emit style).
- D-REF4: Contradiction comparison reuses the RECALL-02 comparison engine identically (same normalizer, same precision-derived tolerance).
- D-REF5: ABSENT_TARGET consults the coverage manifest first. Only emit as full candidate when target is ingested-and-present but referent genuinely missing; if target is table-tier-unavailable/unparsed, emit as declared-boundary low-confidence and route to Phase 7.
- Reuse `follow_reference` (fills the SAME interface — replaces `cross_document_resolution_pending_phase_4` stub) and `edges.py` provenance edge table.

**Precedent candidate mechanic (RECALL-04) — LOCKED:**
- D-PRC1: Match unit = section-level nearest-precedent. Embed each submission section, retrieve nearest past-deficiency chunks.
- D-PRC2: Typed `PrecedentAnchor` = re-openable submission span + precedent chunk id(s) + similarity score as attached supporting evidence. Grounding lives on the submission side.
- D-PRC3: No-leakage safeguard = exclude same-ANDA + pattern-match only (not verbatim submission text).
- D-PRC4: Threshold = absolute dense-cosine (0–1), general, single threshold.

**RECALL-05 — dynamic range + index persistence — LOCKED:**
- D-R5A: Replace RRF-fusion score ceiling (2/61 ≈ 0.0328 < 0.04 threshold) with an absolute dense-cosine similarity (0–1, real range) with a general threshold that actually separates addressed vs absent.
- D-R5B: Build the per-submission index ONCE at ingest (chunks + BM25 + dense embeddings), persist keyed by Phase-1 content hash; `search_corpus` LOADS the prebuilt index and embeds only the QUERY.

**Anti-overfitting guard fixture (RECALL-05 guard) — LOCKED:**
- D-GRD1: Committed fixture = tiny fully synthetic multi-doc corpus (no real FDA content). Four binding constraints: (1) deficiencies specified from rulebook/structural semantics blind to check code; (2) different surface forms than mvr1381; (3) realistic enough that bge-m3 cosine lands in real regime; (4) two-tier: synthetic every-build tripwire + real gitignored spec32s41 slow-lane witness.
- D-GRD2: All three transfer invariants (SAME-LOGIC, THRESHOLD-TRANSFER, RENAME-INVARIANCE) run in fast CI against the committed fixture — they actually EXECUTE, not pytest.skip.
- D-GRD3: Guard vocab discrimination = registered general-vocabulary allowlist. Aggregate lexicon (Total/Max/Mean) and ref cue-words ("see"/"Table") live in a declared reviewed registry; NO-CONSTANT scan flags any OTHER inline literal. Code gate, not reviewer sign-off.

**Shared candidate contract (all four legs) — LOCKED:**
- D-ENV1: One grounded-candidate envelope extending Phase 4's `Fault` + anchor pattern. Carries: typed anchor (union of CoverageAbsenceAnchor | StructuralAnchor | ReferenceAnchor | PrecedentAnchor), leg tag {ABSENCE, STRUCTURAL, REFERENCE, PRECEDENT}, confidence tier (full vs low), dedup key (docId, sectionId, ruleId?), grounding (submission span always present; rule span only when a rule applies).

**Precedent index build scope — LOCKED:**
- D-PIX1: Static global reference asset; built once at rulebook-build time (not per submission).
- D-PIX2: Per-chunk ANDA# metadata for query-time same-ANDA exclusion filter.
- D-PIX3: Local FAISS primary; Databricks mirror optional/serving-only. Guard fixture must run in stock CI without Databricks.

**On-premise/privacy constraint (HARD):**
- Self-hosted open-weights only (Llama 3.3 70B + Qwen MoE + Nemotron-Super-49B on Databricks). NO external LLM API (Claude/GPT) ever. Recall cannot be bought with a stronger hosted model.

**Anti-overfitting law (HARD):**
- No submission-specific constant (batch number, doc name, spec value, section path) in any check code. General by construction or it does not ship. The eval corpus (mvr1381) is a proxy, never a target.

**Iron guardrail:**
- Every finding = verbatim source quote + cited rule. Phase 0 recall-by-family gates every β phase with zero-true-positives-lost.

### Claude's Discretion
- Exact module/file layout for the new legs (sibling packages to Phase-4 absence), internal function decomposition, and test structure — planner/executor decide, following the Phase-4 pattern.
- Concrete reference-extraction regexes / hyperlink-metadata plumbing, provided they stay general (D-REF1) and register any cue-word vocabulary in the guard allowlist (D-GRD3).

### Deferred Ideas (OUT OF SCOPE)
- Semantic / interpretive cross-reference contradictions (X3/X5/X6) and any "is this the right statistic/method/interpretation?" judgment → Phase 7.
- Prose value-pairing (comparing values in narrative text) → Phase 7.
- Databricks mirror of the precedent index as query backend → optional/serving-only, not built in Phase 5.
- Cross-leg ranking beyond confidence-tier ordering → Phase 7 pruning.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECALL-02 | Deterministic intra-document structural inconsistencies over addressable table cells | `tables.py` build_table_index + `(table_id,row,col)→SpanID` index + cache entry already persists table_index. StructuralAnchor design verified against CoverageAbsenceAnchor analog. |
| RECALL-03 | Cross-document reference graph flagging unresolved refs, absent content, and value contradictions | `follow_reference.py` stub ready to fill; `edges.py` generic table zero-migration-ready for new edge types; parse layer has no hyperlink extraction yet (gap). |
| RECALL-04 | Precedent-similarity candidates over past-deficiency corpus | `precedents.py` ingests 385 deduplicated chunks with per-row anda_number in `precedent_provenance` SQLite table; `deficiency_kb.faiss` exists but maps to old row_ids (not RuleChunk doc_ids); need ANDA# filter bridging `precedent_provenance` ↔ FAISS vector index. |
| RECALL-05 | Anti-overfitting guard + dynamic-range threshold + per-submission index persistence | `hybrid.py` RRF ceiling confirmed 2/61 ≈ 0.0328; `search_corpus.py` re-embeds whole submission per query confirmed (lines 42–56); `ingest/store.py` content-hash-keyed cache already exists as persistence substrate. Threshold dead-branch in `absence.py:142` confirmed. |
</phase_requirements>

---

## Summary

Phase 5 owns the three remaining deterministic recall legs — structural/intra-document, reference-graph/cross-document, and precedent-similarity — plus two retrieval-surface fixes that make them viable at scale. Every decision is locked from a prior discuss session. The research task is understanding HOW to implement each leg against the real code the planner will direct an executor to modify.

The codebase is in excellent shape for this work. Phase 4 established the exact patterns Phase 5 must follow: the `CoverageAbsenceAnchor` + `emit_absence_finding` gate shows exactly how to design `StructuralAnchor`, `ReferenceAnchor`, and `PrecedentAnchor` as typed, re-derivable, byte-exact-grounded anchors. The `edges.py` generic edge table is already the right data structure for the reference graph and needs zero migration for new edge types. The `tables.py` `(table_id,row,col)→SpanID` index is built and persisted in every doc cache entry — the structural leg has its input surface. The `search_corpus.py` re-embed-per-query path is confirmed and well-understood; the index-persistence fix is a well-defined plumbing change over existing `ingest/store.py` infrastructure.

The precedent leg has a concrete integration gap: the existing `deficiency_kb.faiss` + `deficiency_kb_map.json` maps FAISS vector indices to SQLite `deficiency_kb` rowids (the old pre-Phase-2-substrate path), while the Phase-2-ingested RuleChunks in `rulebook/store.py` use `"precedent-"` prefixed doc_ids stored in `rulebook_map.json`. The ANDA# metadata for same-ANDA exclusion lives in `precedent_provenance` SQLite table keyed by `doc_id` (the RuleChunk doc_id). The planner must address which FAISS index the precedent tool queries (the rulebook store's `rulebook.faiss`/`rulebook_map.json` is the correct one — it is the Phase-2 substrate-ingested asset) and how the query-time ANDA# filter reads from `precedent_provenance`.

The anti-overfitting guard must be substantially strengthened: Phase 4's guard for `absence.py` (NO-CONSTANT structural scan) works well and is the exact pattern to extend to the three new modules. The two-tier fixture design (committed synthetic + gitignored real) is the right architecture; the key risk is fixture authoring quality (the four binding constraints in D-GRD1).

**Primary recommendation:** Follow the Phase-4 pattern rigorously for every new leg. Build StructuralAnchor, ReferenceAnchor, and PrecedentAnchor as strict siblings of CoverageAbsenceAnchor. Extend `emit_absence_finding` → `emit_structural_finding` / `emit_reference_finding` / `emit_precedent_finding` using the same gate mechanics. The shared envelope (D-ENV1) is an additive optional-field extension to `Fault`, the same pattern Phase 4 used. Index persistence (D-R5B) is the highest-impact change: it unblocks the "no-cap on document count" promise and must land early in wave planning.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Table-cell extraction + SpanID minting | Ingest layer (`tables.py`) | — | Already built; Phase 5 reads, never writes |
| Structural comparison engine (normalizer + precision-derived comparator) | Detection layer (`src/rulebook/structural.py` new) | Reuse for RECALL-03 cross-doc contradiction | Pure computation over ingest output |
| Reference extraction (hyperlinks, textual patterns) | Detection layer (`src/rulebook/references.py` new) | Parse layer (backfill DOCX rels if needed) | Graph-construction is a detection concern; parse layer currently does not extract refs |
| Reference graph (edge table backing) | Rulebook layer (`src/rulebook/edges.py`) | — | Already the generic edge store; zero migration needed |
| `follow_reference` tool (fills Phase-4 stub) | Tools layer (`src/tools/follow_reference.py` mod) | `edges.py` backing | Same interface contract; Phase 4 stub already documented this handoff |
| Precedent similarity retrieval | Rulebook layer (`src/rulebook/precedent_search.py` new) | Local FAISS (`data/rulebook.faiss`) | Queries the rulebook-substrate-ingested precedent chunks, not the old deficiency_kb.faiss |
| Per-submission index persistence | Ingest layer (`src/ingest/corpus.py`) + Tools layer (`src/tools/search_corpus.py` mod) | — | Ingest builds+saves; search_corpus loads+queries |
| Dense-cosine absolute score (replace RRF for absence threshold) | Retrieval layer (`src/retrieval/hybrid.py` mod or new function) | `search_corpus.py` call site | The score exposed by `search_corpus` must change type/range |
| Anti-overfitting guard | Test layer (`tests/evals/test_generality_guard.py` mod) | Guard vocab allowlist registry (new) | CI-enforced code gate; no human sign-off path |
| Shared candidate envelope | Schema layer (`src/schemas/faults.py` mod) | All emit functions | Additive optional-field extension following Phase-4 pattern |
| Eval harness family reporting | Evals layer (`src/evals/run.py` + `src/evals/schema.py`) | — | New leg-families plug into existing FailureFamily enum |

---

## Standard Stack

No new external dependencies required for this phase. All needed libraries are already installed.

### Core (verified present in repo)
| Library | Role | Verified Location |
|---------|------|-------------------|
| `faiss` (local FAISS) | Precedent FAISS index + rulebook FAISS | `src/rulebook/store.py:156`, `src/databricks/vector.py:19` — `[VERIFIED: repo code]` |
| `sentence-transformers` / `bge-m3` | Dense embeddings for cosine similarity | `src/retrieval/vector_search.py:13–16` — `[VERIFIED: repo code]` |
| `numpy` | Cosine similarity computation | `src/retrieval/vector_search.py:3` — `[VERIFIED: repo code]` |
| `python-docx` | DOCX hyperlink relationships (w:hyperlink + rels) | `src/parse/docx.py` — `[VERIFIED: repo code]` |
| `PyMuPDF` (fitz) | PDF link annotations | `src/parse/pdf.py` — `[VERIFIED: repo code]` |
| `pydantic v2` | Anchor models + gate contracts | `src/schemas/faults.py` — `[VERIFIED: repo code]` |
| `sqlite3` (stdlib) | `precedent_provenance` table, `edges` table, `rulebook_chunks` table | `src/rulebook/edges.py`, `src/rulebook/precedents.py` — `[VERIFIED: repo code]` |
| `re` (stdlib) | General textual reference pattern extraction | Used throughout — `[VERIFIED: repo code]` |
| `rank-bm25` / `BM25Index` | BM25 for per-submission index (already used in `search_corpus`) | `src/retrieval/lexical.py` — `[VERIFIED: repo code]` |

### No New Installs Required
`[VERIFIED: repo code]` — All of PyMuPDF, python-docx, bge-m3, FAISS, numpy, pydantic v2, sqlite3, rank-bm25 are already present and used.

---

## Architecture Patterns

### System Architecture Diagram

```
Submission documents (any directory, any nesting)
          |
          v
    [ingest_corpus]  ----builds----->  per-submission index (FAISS + BM25 + chunks)
          |                            persisted: data/ingest_cache/<content_hash>_index.*
          |                            (D-R5B -- ONE-TIME BUILD AT INGEST)
          v
    CoverageManifest
    + table_index (table_id,row,col → SpanID)
    + outline (section spans)
          |
    ------+---------------------------------------------------
    |              |                   |              |
    v              v                   v              v
[absence.py]  [structural.py]    [references.py] [precedent_search.py]
RECALL-01     RECALL-02          RECALL-03        RECALL-04
 (Phase 4)    (Phase 5 new)      (Phase 5 new)    (Phase 5 new)
    |              |                   |              |
    |         comparison engine        |              |
    |         (normalizer +       edges.py        rulebook FAISS
    |          comparator)        edge table      (rulebook.faiss/
    |              |              (Phase 2         rulebook_map.json)
    |              |               generic)            |
    |              |                   |           ANDA# filter via
    |              |                   |           precedent_provenance
    v              v                   v              v
emit_absence  emit_structural    emit_reference  emit_precedent
_finding      _finding            _finding         _finding
    |              |                   |              |
    +--------------+-------------------+--------------+
                        |
                        v
              Shared Fault envelope (D-ENV1)
              [leg_tag, anchor union, confidence_tier,
               dedup_key (docId,sectionId,ruleId?),
               submission_span (always), rule_span (if rule)]
                        |
                        v
                Phase 0 eval harness
                recall_by_family → gates on zero-TP-lost
                        |
                        v
                Phase 7 verifier (inherits pruning load)
```

```
RECALL-05: retrieval-surface fixes

  search_corpus.py (BEFORE):
    query → re-chunk corpus → rebuild BM25 → embed ALL chunks → RRF → RRF score (max 0.0328)
                     ↑ O(queries × corpus) — breaks no-cap promise

  search_corpus.py (AFTER):
    at ingest: build chunks + BM25 + dense embeddings → persist keyed by content_hash
    at query:  load persisted index → embed QUERY ONLY → cosine similarity (0–1 real range)
                     ↑ O(1) index load + O(1) query embed

  absence.py threshold comparison:
    BEFORE: top_score (RRF max 0.0328) >= 0.04 (threshold) → ALWAYS false → ALWAYS emit
    AFTER:  top_score (dense cosine 0–1) >= general_threshold → actually separates addressed vs absent
```

### Recommended Project Structure (New Files)

```
src/rulebook/
├── absence.py          # Phase 4 (existing, do not touch)
├── structural.py       # Phase 5 new — RECALL-02 structural leg
├── references.py       # Phase 5 new — RECALL-03 reference extraction + graph construction
├── precedent_search.py # Phase 5 new — RECALL-04 precedent similarity tool
└── edges.py            # Phase 2 (existing, reused with no migration)

src/schemas/
└── faults.py           # mod: add StructuralAnchor, ReferenceAnchor, PrecedentAnchor,
                        #      leg_tag field on Fault (D-ENV1 shared envelope)

src/tools/
├── emit_finding.py     # mod: add emit_structural_finding, emit_reference_finding,
│                       #      emit_precedent_finding following emit_absence_finding pattern
├── follow_reference.py # mod: fill the cross_document_resolution_pending_phase_4 stub
├── search_corpus.py    # mod: D-R5B — load prebuilt index instead of re-embed per query
└── errors.py           # mod: register new reason_codes for new leg rejections

src/retrieval/
└── vector_search.py    # read — embed_texts + embed_query already supports bge-m3

src/ingest/
└── corpus.py           # mod: D-R5B — persist per-submission index at end of ingest_corpus

tests/
├── rulebook/
│   ├── test_structural.py        # Phase 5 new
│   ├── test_references.py        # Phase 5 new
│   └── test_precedent_search.py  # Phase 5 new
├── tools/
│   ├── test_emit_structural_finding.py  # Phase 5 new
│   └── test_emit_reference_finding.py   # Phase 5 new
└── evals/
    └── test_generality_guard.py  # mod: extend to cover structural/reference/precedent modules

src/evals/
├── run.py                        # mod: register structural-gate / reference-gate commands
├── dataset/
│   └── synthetic_fixture/        # Phase 5 new — committed synthetic multi-doc corpus (D-GRD1)
└── baseline/
    ├── structural_threshold.json  # Phase 5 new — measured + recorded structural thresholds
    └── precedent_threshold.json   # Phase 5 new — measured + recorded precedent cosine threshold
```

---

## Research Domain 1: Structural Legs (RECALL-02)

### How table_index is read from the doc cache

**Verified:** `ingest/corpus.py:163` writes `"table_index": {k: v.model_dump() for k, v in table_index.items()}` to the per-doc JSON cache. `CorpusIndex.cached_entry(doc_id)` returns this dict including `table_index`. [VERIFIED: repo code, ingest/corpus.py:159–165]

```python
# Reading addressable cells from a cached doc:
cache = corpus.cached_entry(doc_id)
table_index_raw = cache["table_index"]  # {"{table_id},{row},{col}": SpanID dict}
```

**Sample keys from live cache:** `",0,0"`, `",0,1"` — table_id is the raw `table.get("table_id", f"t{ti}")` from `tables.py:37`. For DOCX tables without an explicit table_id, it defaults to `t0`, `t1`, etc. For PDFs the same. [VERIFIED: repo code + live cache inspection]

**Getting a SpanID for a cell:**
```python
from schemas.documents import SpanID
span_dict = table_index_raw.get(f"{table_id},{row},{col}")
if span_dict:
    span = SpanID.model_validate(span_dict)
```

**Merged cell resolution:** `tables.py:47–53` — a covered merged coordinate maps to the origin's span. So `table_index[f"{table_id},{r},{c}"]` is always the origin span if that cell is part of a merge. [VERIFIED: repo code, tables.py:47–53]

**Finding a labeled-aggregate cell:** The structural module must scan the `table_index` keys for a given doc to enumerate all `(table_id, row, col)` triples, then open each span and look for header-row or label cells matching the aggregate lexicon (Total/Sum/Maximum/Minimum/Average/Mean). The table structure (which cells are in the same row/column, what the header row contains) must be reconstructed from the key naming convention. Risk: the `table_index` dict only stores `(table_id,row,col)→SpanID` — it does NOT store the row/col count or the table's full structure separately. The structural module needs to group keys by `table_id`, infer max row/col from key ranges, and reconstruct the grid.

**Pattern for reconstructing a table grid from table_index:**
```python
from collections import defaultdict
by_table: dict[str, dict[tuple[int,int], SpanID]] = defaultdict(dict)
for key, span_dict in table_index_raw.items():
    parts = key.split(",")
    if len(parts) == 3:
        table_id, row, col = parts[0] or "t0", int(parts[1]), int(parts[2])
        by_table[table_id][(row, col)] = SpanID.model_validate(span_dict)
```

**PDF merged-cell caveat (D-STR5):** `tables.py docstring` and `ingest/corpus.py:150` — PDF tables set `tables_tier = "unavailable"` when `has_lost_table` is True (any `_parse_failed` marker). `DocEntry.tables` field is `"addressable"` or `"unavailable"`. The structural module MUST check `doc_entry.tables == "addressable"` before attempting cell-level comparison; if unavailable → log + route to Phase 7. [VERIFIED: repo code, ingest/corpus.py:149–150]

### StructuralAnchor design

Closest analog: `CoverageAbsenceAnchor` in `src/schemas/faults.py:68–84`. [VERIFIED: repo code]

```python
class StructuralAnchor(BaseModel):
    """D-STR3: Re-derivable structural inconsistency anchor.
    The verifier RE-RUNS the comparison; never trusts the stored snapshot."""
    claim_span_id: SpanID = Field(description="The cell/span asserting the claim value (e.g. the 'Total' cell).")
    basis_span_ids: list[SpanID] = Field(description="The N basis cells the claim was computed from.")
    relation: Literal["EQUALS", "LEQ", "GEQ", "SUM", "MAX", "MIN", "MEAN"] = Field(...)
    expected_value: str = Field(description="Re-derived expected value as a string (raw text from basis cells).")
    actual_value: str = Field(description="Value in the claim span (verbatim).")
    comparison_store: Literal["CORPUS", "RULEBOOK"] = Field(
        default="CORPUS",
        description="Where each basis span resolves: CORPUS for table cells, RULEBOOK for spec limits."
    )
    scoping_confidence: Literal["full", "low"] = Field(
        default="full",
        description="D-ABS2: 'low' when a contributing cell was not cleanly addressable."
    )
```

**Place in `src/schemas/faults.py`** as a sibling of `CoverageAbsenceAnchor`. Add `structural_anchor: StructuralAnchor | None = None` as optional field on `Fault`. [Pattern: faults.py:101 existing `absence_anchor` field]

### Value normalization and precision-derived comparator (D-STR4)

**Algorithm (no epsilon, no free parameter):**

1. Strip trailing `%` → parse as float; if units differ, abstain (return None, never emit).
2. Canonicalize comparator tags: `NMT` / `≤` / `not more than` → `LEQ`; `NLT` / `≥` / `not less than` → `GEQ`; no tag → `EQUALS` for aggregate checks.
3. Parse stated precision: count decimal digits in the raw text. E.g., `"0.10"` → precision 2; `"11477"` → precision 0; `"0.14"` → precision 2.
4. If claim operand has MORE decimal places than limit/reference operand: round claim to reference precision. If reference is finer than claim: round reference to claim precision. (Always round the finer operand to the coarser's precision.)
5. Comparison: `EQUALS` → `round(claim_val, precision) == round(ref_val, precision)`; `LEQ` → `round(claim_val, precision) > round(ref_val, precision)` is a violation; `GEQ` → `round(claim_val, precision) < round(ref_val, precision)` is a violation; `SUM`/`MAX`/`MIN`/`MEAN` → recompute over basis cells, compare at precision of claim cell.

**Rounding correctness example:**
- Claim: `"0.104"` (3 decimal places). Limit: `"NMT 0.10"` (2 decimal places). Limit precision = 2. Round claim to 2 places: `round(0.104, 2) = 0.10`. Comparison: `0.10 > 0.10` → False → COMPLIES. No violation emitted. [ASSUMED: Python `round(0.104, 2) = 0.1` — confirmed per Python banker's rounding; verified the intent matches USP/ICH per CONTEXT.md D-STR4]
- Claim: `"0.15"`. Limit: `"NMT 0.10"`. Both precision 2. `round(0.15, 2) > round(0.10, 2)` → `0.15 > 0.10` → True → VIOLATION. Emit C-02 / MS-04 class.

**Where C-01/C-04/MS-01/MS-02/MS-04 map:**
- C-01: Table 20 `Maximum` cell (11477) vs recomputed max of column basis cells (true 12601). Relation: `MAX`. `max(basis) = 12601 ≠ 11477` → VIOLATION.
- C-04: Table 19 `Total` cell (0.14%) vs max of row basis cells (0.15%). Relation: `SUM` or aggregate check. `total < max_single` → VIOLATION.
- C-02: Unspecified impurity (0.15%) reported as meeting NMT 0.10% limit. Relation: `LEQ`. `round(0.15,2) > round(0.10,2)` → VIOLATION. Rule span from rulebook (spec limit ICH Q3A or labeling).
- MS-01, MS-04: Same pattern as C-04, C-02. [VERIFIED: eval dataset inspection]

**Abstain conditions (never emit, never raise):**
- Unparseable numeric text (text, non-numeric in cell)
- Mismatched units that can't be normalized (e.g., mg vs %)
- Merged cells with no clean origin span
- Table-tier-unavailable document

**General aggregate lexicon (D-GRD3 allowlist):** `{"total", "sum", "maximum", "max", "minimum", "min", "average", "mean"}` — case-insensitive match against cell text or adjacent header/label cell text. Must be registered in the guard allowlist, not hardcoded inline.

### How a compared value resolves from a RULEBOOK rule span (D-STR2)

For `result-exceeds-spec-limit`: the spec limit lives in the submission doc itself (the spec table). But it MAY also be sourced from a rulebook rule span (e.g., ICH Q3A 0.10% threshold for unspecified impurities). When sourced from the rulebook: the basis span has `comparison_store="RULEBOOK"`. The emit gate must validate this span against the rulebook store (same `rulebook_nt_for` path as `emit_finding`). When sourced from a submission cell: `comparison_store="CORPUS"`, validated against `corpus.cached_entry`.

The emit gate pattern for `StructuralAnchor`:
```python
for span_id, store in zip(anchor.basis_span_ids, basis_stores):
    if store == "RULEBOOK":
        nt = rulebook_nt_for(span_id.doc_id, cache_dir=rulebook_cache_dir)
        # validate with open_span
    else:
        nt = corpus.cached_entry(span_id.doc_id)  # then construct NormalizedText
        # validate with open_span
```

---

## Research Domain 2: Reference Graph (RECALL-03)

### Reference extraction — the three edge kinds

**Kind 1: DOCX hyperlinks.** python-docx does not expose `w:hyperlink` elements directly from its high-level API, but they exist in the XML. The DOCX `word/_rels/document.xml.rels` file maps `rId` to target URI/anchor. Extraction approach:

```python
# Inside extract_docx or a reference extractor consuming the parsed dict:
from docx import Document
from docx.oxml.ns import qn
import zipfile, xml.etree.ElementTree as ET

# The relationship file:
with zipfile.ZipFile(docx_path) as z:
    rels_xml = z.read("word/_rels/document.xml.rels")
rels_tree = ET.fromstring(rels_xml)
# Each <Relationship Type="hyperlink" Target="..."/> is a hyperlink
```

However, `src/parse/docx.py` currently does NOT extract hyperlinks. It only extracts paragraph text and table cells. The reference extractor must either extend `parse/docx.py` to also emit hyperlink spans, or open the DOCX zip itself from the cached canonical text + doc_id path.

**Risk:** The reference extractor cannot open the original .docx file from the corpus cache (only canonical text + offset map is persisted, not the raw .docx bytes). The original file path is available from `DocEntry.filename` but the full path is not stored (only `doc_id = content_hash`). **Mitigation:** Either (a) add hyperlink extraction to `extract_docx` so it emits them in the parsed dict (stored in cache), or (b) re-read from the corpus root path via `CorpusIndex.root + DocEntry.filename`. Option (a) is cleaner and preserves the offline guarantee. [VERIFIED: ingest/corpus.py:105–106 — corpus root is stored in CorpusIndex.root; filename in DocEntry.filename]

**Kind 2: PDF link annotations.** PyMuPDF (`fitz`) exposes link annotations on each page:
```python
import fitz
doc = fitz.open(pdf_path)
for page in doc:
    for link in page.get_links():
        # link["kind"] == fitz.LINK_URI (external) or fitz.LINK_GOTO (internal page jump)
        # link["uri"] / link["page"] / link["from"] (Rect in page coords)
```
Currently `src/parse/pdf.py` does NOT extract link annotations. Same gap as DOCX. Extension needed. [VERIFIED: parse/pdf.py inspection — no `get_links` call]

**Kind 3: Textual reference patterns (general regex).** General patterns that work across any doc:
- `"see §X"`, `"see Section X.X"`, `"refer to §X.X"` → pattern: `r"(?:see|refer to|as (?:described|stated) in|per)\s+§?\s*([\d\.]+[A-Za-z\.]*)"`
- `"Table N"`, `"Table X-Y"` → pattern: `r"\b[Tt]able\s+(\d+[\w\-]*)"`
- CTD module references: `"Module 3.2.P.5"`, `"Section 3.2.S.4.1"` → pattern: `r"(?:Module|Section)\s+(3\.2\.[SP]\.[\d\.]+)"`
- Same-doc `"(see above)"`, `"Table above"` → resolvable within doc via outline; cross-doc if not found

All patterns must be **registered in the D-GRD3 general-vocabulary allowlist** (the cue-words "see", "refer", "Table", "Module" etc. are allowed vocabulary; the CTD section patterns in the EXTRACTOR code are not inline literals — they are general patterns that match any section path, not a specific one). The guard must distinguish "general regex pattern that matches any CTD path" from "hardcoded literal `3.2.S.4.1`". The rule: the regex pattern `r"(?:Module|Section)\s+(3\.2\.[SP]\.[\d\.]+)"` is in the allowed allowlist as a general pattern; if a developer writes `if section_id == "3.2.S.4.1"` that is a corpus constant and must fail the guard.

### ReferenceAnchor design

```python
class ReferenceAnchor(BaseModel):
    """D-REF2: One cross-reference edge with anomaly classification."""
    src_span_id: SpanID = Field(description="The span containing the reference text in the source doc.")
    dst_span_id: SpanID | None = Field(default=None, description="The target span if resolved; None if unresolved.")
    edge_type: Literal["hyperlink", "textual_ref", "value_crossref"] = Field(...)
    anomaly: Literal["UNRESOLVED_REF", "ABSENT_TARGET", "VALUE_CONTRADICTION"] = Field(...)
    scoping_confidence: Literal["full", "low"] = Field(
        default="full",
        description="D-REF3: 'low' for label-match-only contradictions (no direct edge)."
    )
```

### edges.py integration (D-REF — reuse the existing generic edge table)

`src/rulebook/edges.py` is the correct backing store. [VERIFIED: repo code, edges.py:1–70]

New edge_type values to add:
- `"hyperlink"` — DOCX/PDF link annotation
- `"textual_ref"` — regex-matched cross-reference
- `"value_crossref"` — numeric value present in two locations linked by a reference

`add_edge(src_id=span_id.doc_id+":"+str(span_id.start), dst_id=..., edge_type="textual_ref", provenance_span_id=span_json)` — no schema migration needed. `edges.py:30–33` rejects empty provenance, so the reference extractor must always attach the src span as provenance. [VERIFIED: edges.py:33]

### follow_reference.py — filling the Phase-4 stub

`src/tools/follow_reference.py:18` — `_CROSS_DOC_PENDING = "cross_document_resolution_pending_phase_4"` is the sentinel. Phase 5 replaces the fallback return with real reference-graph lookup:

```python
# NEW logic in follow_reference (replacing line 26 and lines 30–39 cross-doc return):
# 1. Check edges table: get_edges(src_id=<doc_id>:<ref_text_span>, edge_type=<any ref type>)
# 2. If an edge exists → resolve dst to a span → return {"doc_id": dst_doc_id, "span_id": ..., "resolved": True}
# 3. If no edge but could be same-doc → existing outline search (lines 28–36 unchanged)
# 4. If no edge, cross-doc, absent → return ABSENT_TARGET or UNRESOLVED_REF
```

The new `follow_reference` returns SAME interface shape as the old one, plus additional keys for the anomaly type. [VERIFIED: follow_reference.py docstring says "Phase 4's full reference graph fills the SAME interface without changing this contract"]

### Coverage manifest for ABSENT_TARGET (D-REF5)

`CoverageManifest.documents` contains a `DocEntry` per doc with `tables: "addressable" | "unavailable"` and `status: "parsed" | "parsed_partial" | "parse_failed" | "unsupported"`. Before emitting `ABSENT_TARGET`:

```python
target_entry = next((d for d in manifest.documents if d.doc_id == target_doc_id), None)
if target_entry is None:
    # Document genuinely absent from the submission corpus → full ABSENT_TARGET candidate
    emit_reference_finding(..., anomaly="ABSENT_TARGET", scoping_confidence="full")
elif target_entry.tables == "unavailable" and target_is_table_ref:
    # Table reference but table-tier unavailable → declared boundary, low confidence, Phase 7
    emit_reference_finding(..., anomaly="ABSENT_TARGET", scoping_confidence="low")
elif target_entry.status in ("parse_failed", "unsupported"):
    # Parse failed → declared boundary, low confidence
    emit_reference_finding(..., anomaly="ABSENT_TARGET", scoping_confidence="low")
```

[VERIFIED: ingest/corpus.py:148–155, manifest.py DocEntry fields]

---

## Research Domain 3: Precedent Leg (RECALL-04)

### Current state of the precedent index — two separate FAISS indexes exist

**Critical finding (two indexes, different purposes):**

1. **`data/deficiency_kb.faiss` + `data/deficiency_kb_map.json`** — OLD pre-Phase-2 index. Maps FAISS vector index positions → SQLite `deficiency_kb` rowids. Used by `src/databricks/vector.py:74–105` via `_search_faiss`. The map is a list of integers (SQLite rowids): `[1, 2, 3, ..., 500]`. This index was built from the raw spreadsheet content BEFORE the Phase-2 substrate ingestion. It does NOT use RuleChunk doc_ids and does NOT benefit from the Phase-2 `precedent_provenance` ANDA# metadata. [VERIFIED: vector.py:19–20, deficiency_kb_map.json inspection]

2. **`data/rulebook.faiss` + `data/rulebook_map.json`** — the Phase-2 rulebook store FAISS index. Maps FAISS vector index positions → RuleChunk doc_ids (strings). Includes precedent chunks alongside eCFR/ICH/FDA chunks. Rebuilt by `store.py:rebuild_local_index()`. This index IS the Phase-2-substrate-ingested precedent asset. [VERIFIED: store.py:154–155, 200–206]

**For RECALL-04, the correct index is #2 (`data/rulebook.faiss`).**

The `precedent_provenance` SQLite table (keyed by `doc_id = "precedent-" + sha256(deficiency_text)[:16]`) holds `anda_number` per chunk. [VERIFIED: precedents.py:87–114]

**The ANDA# filter (D-PRC3) works as follows:**
```python
# Get all doc_ids for chunks belonging to the submission's ANDA#
from rulebook.precedents import get_provenance
# query: embed submission section → FAISS top-k from rulebook.faiss
# filter: for each returned doc_id, call get_provenance(doc_id) and check anda_number
# if provenance[0]["anda_number"] == submission_anda_number → skip (same-ANDA exclusion)
```

**Gap: No built-in metadata filter in the current FAISS-based store.** The local FAISS index (`IndexFlatIP`) does not support metadata filtering at query time — filtering must be done post-hoc on the returned doc_ids. For 385 chunks this is fast. [VERIFIED: store.py:174–207]

**ANDA# of the submission under review:** Not currently tracked in `CorpusIndex` or `CoverageManifest`. The structural ANDA# would come from document content (e.g., the cover page or submission metadata). For Phase 5, either: (a) the precedent leg accepts an optional `submission_anda_number: str | None` parameter (None → no same-ANDA exclusion), or (b) the phase detects it from the manifest classification. Option (a) is simpler and avoids requiring content-based ANDA# detection. [ASSUMED: content-based ANDA# detection is out of scope for Phase 5; the parameter default is None]

### PrecedentAnchor design

```python
class PrecedentAnchor(BaseModel):
    """D-PRC2: Section-level precedent similarity evidence (not a finding source itself)."""
    submission_span_id: SpanID = Field(description="The submission section span that triggered this candidate.")
    precedent_doc_ids: list[str] = Field(description="doc_ids of matching precedent chunks (supporting evidence only).")
    similarity_scores: list[float] = Field(description="Dense cosine scores corresponding to precedent_doc_ids.")
    threshold: float = Field(description="The general threshold this run used.")
    anda_excluded: list[str] = Field(default_factory=list, description="D-PRC3: ANDA numbers excluded from results (same-ANDA filter).")
```

### Precedent index build scope (D-PIX1/D-PIX2/D-PIX3)

The precedent chunks are ALREADY ingested into `data/rulebook.faiss` via `src/rulebook/precedents.py` + `src/rulebook/build.py:vendor_precedent()`. [VERIFIED: build.py:266–281, test_precedents.py confirms 385 chunks ingested]

**What Phase 5 adds at build time:** Ensure each precedent chunk's `doc_id` maps cleanly through `precedent_provenance` to get `anda_number`. This mapping already exists from Phase 2. No rebuild needed unless the xlsm changes.

**What Phase 5 adds at query time:** A `search_precedents(submission_span, corpus, top_k, submission_anda_number)` function that:
1. Embeds the submission section text (using `embed_query`)
2. Queries `rulebook_search_local()` dense leg (or directly queries `rulebook.faiss`) for `source="precedent"` chunks only
3. Post-hoc filters by `anda_number != submission_anda_number` via `get_provenance(doc_id)`
4. Returns above-threshold matches as `PrecedentAnchor`

**Filtering by source="precedent" in the rulebook FAISS:** The current `_rulebook_search_local` in `store.py:209–244` does not filter by source. Phase 5 must either add a source filter or track which FAISS indices belong to precedent chunks (via `_faiss_doc_ids` and matching against "precedent-" prefix). The "precedent-" prefix approach is simplest: `all_precedent_doc_ids = [d for d in _faiss_doc_ids if d.startswith("precedent-")]`. [VERIFIED: precedents.py:155 — precedent doc_ids are `"precedent-" + sha256(text)[:16]`]

### What gets embedded on the submission side vs precedent side

- **Submission side:** Each section's canonical text is embedded at query time using `embed_query()` (single text → single embedding). Section boundaries come from `DocEntry.outline` span list. [VERIFIED: ingest/corpus.py:142, manifest.py:OutlineEntry]
- **Precedent side:** Each chunk's canonical text is pre-embedded at build time in `rulebook.faiss`. The chunk text is the deficiency text verbatim (via `serialize_document` path in `precedents.py:130`). [VERIFIED: precedents.py:126–137]

"Pattern-match, not verbatim" (D-PRC3): embedding the SUBMISSION SECTION text (regulatory narrative) against the PRECEDENT DEFICIENCY text (reviewer's deficiency description) means the match is inherently semantic pattern-similarity, not verbatim text matching. The submission section says "we established accuracy..." while the precedent says "accuracy result table is absent" — the embedding captures the shared concept of accuracy without recognizing the exact same words. [ASSUMED: this is the intended semantic, not verified empirically in this session]

---

## Research Domain 4: Retrieval-Surface Fixes (RECALL-05)

### Confirmed RRF ceiling dead-branch

`src/retrieval/hybrid.py:5,9` — `k=60` is the default. With two rankings: max score = `1/(60+1) + 1/(60+1) = 2/61 ≈ 0.03279`. [VERIFIED: hybrid.py:9]

`src/rulebook/absence.py:142` — `if top_score >= threshold:` with `threshold=0.04` from the committed baseline. `0.03279 < 0.04` → this branch is ALWAYS false → EVERY applicable requirement is over-emitted regardless of retrieval strength. [VERIFIED: absence.py:141–143 + hybrid.py]

`src/evals/baseline/absence_threshold.json` stores `"threshold": 0.04`. [VERIFIED: 04-VERIFICATION.md + absence.py:20 docstring]

### D-R5A — Dense cosine absolute score

**Current path:** `search_corpus.py:59–63` — computes `scores = (e_norm @ q_norm.T).flatten()` (this IS already cosine similarity in [0,1] because both are L2-normalized). But then the DENSE scores are fed into `reciprocal_rank_fusion` which CONVERTS them to rank-based scores (losing the 0–1 range). The fix is to RETURN the actual dense cosine similarity alongside or instead of the RRF-fused score. [VERIFIED: search_corpus.py:53–63]

**Implementation approach for D-R5A:**
Option A: Return both the RRF-fused score (for BM25 rank) and the dense cosine score (for addressed/absent decision). The `score` field in the returned dict switches to dense cosine; RRF is used only for ordering, not for thresholding.

Option B: Replace the RRF fusion score with a new hybrid signal that keeps the 0–1 range. E.g., `combined_score = 0.5 * dense_cosine + 0.5 * (lexical_rank_based_score)`.

Option A is simpler and preserves the BM25 rank ordering for result order while giving the absence threshold a meaningful signal. [ASSUMED: Option A — verify with planner]

**Concrete change in `search_corpus.py`:**
```python
# After line 60 (dense_order computed):
dense_scores = {chunk_ids[i]: float(scores[i]) for i in dense_order[:top_k*2]}

# After fused (line 63):
fused = reciprocal_rank_fusion([lexical_ranked, dense_ranked])[:top_k]

# When building out dict (line 66–79), add dense_cosine_score:
for cid, _rrf_score in fused:
    out.append({
        "doc_id": ..., "span_id": ...,
        "score": dense_scores.get(cid, 0.0),  # CHANGED: dense cosine (0–1)
        "rrf_score": _rrf_score,               # preserved for ordering reference
        "snippet": ...,
    })
```

**Absolute threshold range in practice:** Dense cosine similarity from bge-m3 for a relevant requirement trigger vs. its source text typically lands 0.7–0.9 for good matches, 0.4–0.6 for loose matches, and 0.2–0.4 for unrelated content. A threshold around 0.5–0.6 should give genuine separation. The exact threshold MUST be measured on mvr1381, recorded in `absence_threshold.json`, and NOT hardcoded. [ASSUMED: typical bge-m3 cosine range — this must be verified empirically on mvr1381]

### D-R5B — Per-submission index persistence

**What to persist (per document, keyed by content_hash):**
```
data/ingest_cache/{content_hash}__{nv}__{sv}__{pv}.json  # already exists (canonical text + table_index)
data/ingest_cache/{content_hash}__{nv}__{sv}__{pv}_bm25.pkl  # NEW: BM25 index
data/ingest_cache/{content_hash}__{nv}__{sv}__{pv}_vectors.npy  # NEW: chunk embeddings (n_chunks × dim)
data/ingest_cache/{content_hash}__{nv}__{sv}__{pv}_chunks.json  # NEW: chunk metadata (doc_id, start, end, nv)
```

Or alternatively, store all three in the existing JSON cache dict (adding `"bm25_index"`, `"chunk_embeddings"`, `"chunk_metadata"` keys). However, numpy arrays serialize poorly to JSON; a sidecar `.npy` file is more efficient.

**Where to build:** At the end of `ingest_corpus.py:ingest_corpus()`, AFTER all documents are parsed. Or per-document in the existing loop (each doc's chunks built and persisted individually). The per-document approach is better because a submission with N=100 documents builds N separate indexes that can be loaded/queried independently without loading the whole corpus into memory.

**Where to load in search_corpus.py:** Replace `_build_chunks()` + `BM25Index([...])` + `embed_texts([...])` with loading the prebuilt persisted artifacts:
```python
def search_corpus(corpus, query, ledger, top_k=10):
    # Try to load persisted index
    if _has_persisted_index(corpus):
        return _search_with_persisted_index(corpus, query, ledger, top_k)
    # Fall back to legacy re-embed path for backward compatibility
    return _search_legacy(corpus, query, ledger, top_k)
```

**Invalidation:** The existing `cache_key(content_hash, nv, sv, pv)` already handles invalidation — a changed document gets a new content_hash → new index key → rebuilds automatically. [VERIFIED: ingest/store.py:36–49]

**BM25 index serialization:** `rank_bm25` BM25Index does not have a built-in serialize method. Options: (a) `pickle.dump` the `BM25Okapi` object, or (b) persist the tokenized corpus as JSON and rebuild the index at load. Option (b) is safer (no pickle security concerns). The tokenized corpus is small (list of word lists per chunk). [VERIFIED: retrieval/lexical.py:1–24 — uses rank_bm25 BM25Okapi]

**Interaction with two backends (local FAISS vs Databricks Vector):** `search_corpus.py` has a docstring stating it is "LOCAL AND EPHEMERAL ONLY -- no Databricks branch exists in this file by design". [VERIFIED: search_corpus.py:1–4] The D-R5B persistence is also local only. Databricks serving for the submission index remains out of scope (per-submission content is not routed to Databricks by design).

---

## Research Domain 5: Anti-Overfitting Guard + Synthetic Fixture

### Current guard state (Phase 4 handoff)

The existing guard (`tests/evals/test_generality_guard.py`) covers `absence.py` only. [VERIFIED: test_generality_guard.py:1]

**What currently runs in fast CI (every build):**
- `test_absence_module_embeds_no_corpus_constant` — structural scan of `src/rulebook/absence.py` for: (a) CTD-family literals matching `r"3\.2\.[SP]\."`, (b) float literals not in `{0.0, 1.0}`, (c) dataset id denylist `{mvr1381, spec32s41, heldout32s41, minispec}` [VERIFIED: test_generality_guard.py:95–135]
- `python -m evals.run coverage-gate` [VERIFIED: .github/workflows/test.yml]
- `python -m evals.run absence-gate` (corpus-gated, skips when data/ absent) [VERIFIED: .github/workflows/test.yml]

**What currently corpus-gates (pytest.skip without held-out PDF):**
- `test_rename_invariance_of_applicable_requirements` — pytest.skip if `data/32s41-Specification.pdf` absent [VERIFIED: test_generality_guard.py:84–87]
- `test_threshold_transfer_and_same_logic_on_heldout` — slow-deselected (`@pytest.mark.slow`) [VERIFIED: test_generality_guard.py:160]

### Guard extension for Phase 5 (D-GRD1/D-GRD2)

**The synthetic fixture approach (D-GRD1):** A committed tiny multi-doc test corpus that is:
1. License-clean (no real FDA content, entirely synthetic)
2. Contains planted structural deficiencies (aggregate cell wrong, result exceeds limit)
3. Contains planted cross-reference deficiencies (reference to a table that differs in another doc)
4. Contains planted precedent-matchable content (narrative that paraphrases a known deficiency type)
5. Uses different doc names, table layouts, and values than mvr1381
6. Written with realistic enough regulatory prose that bge-m3 embeddings land in 0.5–0.8 cosine similarity range against relevant precedent chunks

**Recommended fixture structure:**
```
tests/fixtures/synthetic_submission/
├── doc_a.pdf   (synthetic "Quality Overall Summary 2.3" equivalent — has a cross-ref to doc_b)
├── doc_b.docx  (synthetic "Module 3.2.P.5" equivalent — has the spec table that doc_a cross-refs)
└── doc_c.pdf   (synthetic "Specification" document — has aggregate table error + limit exceedance)
```

**The three invariants that must ACTUALLY RUN in fast CI (D-GRD2):**
- `SAME-LOGIC`: Run structural/reference/precedent checks on the synthetic fixture → verify the planted deficiencies are found → verify their origin code paths match general rules (not corpus-specific).
- `THRESHOLD-TRANSFER`: With threshold frozen from synthetic fixture measurement, run on a second synthetic fixture with different values → verify the same threshold fires.
- `RENAME-INVARIANCE`: Rename synthetic fixture directory → verify same candidates found.

**These can execute without the gitignored spec32s41 corpus** because the synthetic fixture is committed. This is the key improvement over Phase 4's guard.

### Guard vocab allowlist registry (D-GRD3)

New file (suggested): `src/rulebook/guard_vocab.py`

```python
# REGISTERED general-vocabulary allowlists — NOT corpus constants.
# Every entry asserted to contain no corpus-specific token.
# Adding a vocabulary set here means the NO-CONSTANT scan treats it as allowed.

AGGREGATE_LEXICON = frozenset({
    "total", "sum", "maximum", "max", "minimum", "min", "average", "mean"
})

REFERENCE_CUE_WORDS = frozenset({
    "see", "refer", "table", "section", "module", "figure", "appendix",
    "as described in", "as stated in", "per", "referenced in"
})

# Assertion: no entry in any set is a corpus-specific token (doc name, ANDA#, specific value)
# Enforced by test (guard must scan each vocabulary entry against corpus-specific patterns)
```

**Guard scan extension for structural.py, references.py, precedent_search.py:**
The NO-CONSTANT scan currently checks only `absence.py`. Phase 5 must extend it to also scan `structural.py`, `references.py`, and `precedent_search.py` for the same patterns (CTD-family literals, hardcoded float thresholds, dataset id denylist). The allowlist means: words in `AGGREGATE_LEXICON` and `REFERENCE_CUE_WORDS` are permitted; any OTHER inline string literal matching document-specific patterns is flagged.

---

## Research Domain 6: Shared Envelope + Eval Wiring

### D-ENV1 shared envelope — extension to Fault

`src/schemas/faults.py:87–116` is the existing `Fault` model. The additive extension pattern from Phase 4 (adding `absence_anchor: CoverageAbsenceAnchor | None = None`) is the exact template. [VERIFIED: faults.py:101]

**New fields to add to `Fault`:**
```python
# Following Phase-4 pattern exactly:
structural_anchor: StructuralAnchor | None = Field(default=None, ...)
reference_anchor: ReferenceAnchor | None = Field(default=None, ...)
precedent_anchor: PrecedentAnchor | None = Field(default=None, ...)
leg_tag: Literal["ABSENCE", "STRUCTURAL", "REFERENCE", "PRECEDENT"] | None = Field(default=None, ...)
```

Alternatively, a `Union[CoverageAbsenceAnchor, StructuralAnchor, ReferenceAnchor, PrecedentAnchor] | None` typed `anchor` field with the discriminator on `leg_tag`. The discriminated union approach is cleaner but requires pydantic discriminated union syntax. The additive-field approach is simpler and more consistent with Phase 4. [ASSUMED: additive-field approach preferred for consistency with Phase 4]

**Dedup key:** `(docId, sectionId, ruleId?)` where `sectionId` is derived from the span's offset range and `ruleId` is nullable. Since span-IDs carry `(doc_id, start, end)`, a dedup key can be `(span_id.doc_id, span_id.start // SECTION_GRANULARITY, rule_span_id.doc_id if rule_span_id else None)`. SECTION_GRANULARITY ~4096 chars (typical section size).

### How Phase 0 harness reports recall-by-family

`src/evals/metrics.py:57–72` — `_end_to_end_by_family` scores faults against `FailureFamily` enum. Currently four families: `absence_of_evidence`, `derivation_plausibility`, `cross_reference_integrity`, `regulatory_framing`. [VERIFIED: schema.py:21–31]

**What Phase 5 adds to eval wiring:**
- `cross_reference_integrity` ← covers X1/X2 (C-01, C-02, C-04, MS-01, MS-02, MS-04 in the eval set) [VERIFIED: eval dataset inspection]
- `derivation_plausibility` ← structural leg may contribute to this family (C-01's Table 20 recompute is in `cross_reference_integrity` family; C-02's limit exceedance is also `cross_reference_integrity`)
- Precedent matches don't have a dedicated FailureFamily yet — they map to the family of the matched precedent (whichever family the precedent deficiency belonged to)

**X1/X2 ground truth location:** The eval dataset does NOT use the labels "X1" and "X2" explicitly. They refer to conceptual deficiency types:
- X1 (QOS 2.3 vs Module 3.2 body cross-document spec mismatch) → `cross_reference_integrity` family (likely C-03: "The two methods are not 'comparable' for the single largest unspecified impurity") [ASSUMED: needs confirmation — the QOS-vs-Module reference isn't directly in the mvr1381 dataset as a single doc; it's a cross-document check for a multi-doc submission]
- X2 (cross-document value contradiction) → C-01 (Table 20 Max), C-02 (limit exceedance), C-04 (Table 19 total), MS-01, MS-02, MS-04 are all `cross_reference_integrity` family items [VERIFIED: eval dataset inspection]

**Note:** The current mvr1381.deficiencies.json has only ONE document (`doc_id` appears to be for a single PDF — the estradiol method validation report). True cross-document checks (QOS vs Module 3.2.P.5) would require a multi-doc submission corpus. The minispec fixture (mini_spec.docx) has MS-01/MS-02/MS-04 which are intra-document structural checks. Phase 5 Success Criterion 2 ("catching at least one X1") may require adding a multi-doc eval fixture or clarifying that the minispec's intra-doc checks count as the testable X2. [VERIFIED: eval dataset inspection + minispec.deficiencies.json]

**The CRITICAL insight:** For Phase 5 SC2, the eval success must be measurable on the existing eval corpus. The minispec document already has two `cross_reference_integrity` items (MS-01: total < single component; MS-02: stated Max doesn't match true max) that are intra-document structural checks perfectly suited to RECALL-02. These are the testable targets for the structural leg. True X1 (QOS vs Module cross-doc) requires a multi-doc submission that may not exist in the current eval corpus.

### Extending evals/run.py with structural/reference gates

Pattern from Phase 4: `cmd_coverage_gate`, `cmd_absence_gate` added to `build_parser()` in `run.py`. [VERIFIED: run.py:701, 708]

Phase 5 adds:
- `structural-gate`: runs `detect_structural_inconsistencies` on eval docs, checks recall on `cross_reference_integrity` family (or `derivation_plausibility` where applicable), ratchets against a committed baseline.
- `reference-gate`: same for reference graph checks.

Or: a single `deterministic-recall-gate` that runs all three new legs and reports family-level recall.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Byte-exact span re-open | Custom span verification | `ingest.anchors.open_span` | Already tested, hash-verified |
| Grounding gate | Custom emission path | `emit_finding` / `emit_absence_finding` pattern | Phase 7 verifier depends on this exact contract |
| Edge persistence | Custom graph DB | `rulebook.edges` SQLite generic table | Zero migration, provenance-enforced, already used |
| Precedent FAISS queries | New vector search library | `rulebook.store._rulebook_search_local` + FAISS | Already integrated, bge-m3 aligned |
| ANDA# lookup | Custom provenance table | `rulebook.precedents.get_provenance(doc_id)` | Already built in Phase 2 |
| BM25 | Implement BM25 from scratch | `retrieval.lexical.BM25Index` wrapping `rank_bm25` | Already built |
| Anti-overfitting scan | Ad-hoc grep | Extend `test_generality_guard.py::test_absence_module_embeds_no_corpus_constant` pattern | Pattern already proven, just generalize to new module paths |
| Content-hash cache key | New hashing scheme | `ingest.store.cache_key(content_hash, nv, sv, pv)` | Already invalidation-correct |

---

## Common Pitfalls

### Pitfall 1: table_index key format — empty table_id
**What goes wrong:** When `tables.py:37` cannot find a `table_id` in the parsed table dict, it defaults to `f"t{ti}"` where `ti` is the positional index. However, looking at the live cache sample: keys are `",0,0"` with an EMPTY string table_id (not `"t0,0,0"`). This happens when the serializer and table dict don't assign a table_id.
**Root cause:** The live cache shows table_id is empty string `""` for the sample doc. The structural module's key construction `f"{table_id},{row},{col}"` must handle `table_id=""` producing keys like `",0,0"`.
**How to avoid:** When grouping by table_id from the `table_index` dict, split on commas correctly: `parts = key.split(",", 2)` → `table_id, row, col = parts`. If `table_id == ""`, treat as `"default"` internally.
**Warning signs:** `table_index` keys that start with `","` — these are valid keys, not corrupt data.
[VERIFIED: live cache inspection showed keys `",0,0"`, `",0,1"`]

### Pitfall 2: Merged cells resolving to the same SpanID
**What goes wrong:** Two cells that are part of a merge resolve to the SAME SpanID. A structural check treating them as two independent values will compute `expected == actual` trivially.
**Root cause:** `tables.py:47–53` — merged cells share the origin's SpanID by design.
**How to avoid:** Before adding a span to the basis list, deduplicate by `(doc_id, start, end)`. If all basis spans resolve to the same span, abstain (cannot recompute — no independent values).
**Warning signs:** `basis_span_ids` contains duplicate entries.

### Pitfall 3: bge-m3 cosine similarity range on short text
**What goes wrong:** Very short section texts (one sentence) produce unstable cosine similarities — too close to zero for anything, too high for unrelated content. The absolute threshold set on longer text may fail on short sections.
**Root cause:** bge-m3's contextualized embeddings work best on paragraph-length text (50–500 tokens). Sub-sentence fragments give degenerate representations.
**How to avoid:** When embedding submission sections, use a minimum character length (e.g., skip sections with `len(canonical_text) < 100`). Log skips. For precedent candidates, only emit above the threshold — never for very short sections.
**Warning signs:** Precedent similarity scores uniformly near 0 for short sections.

### Pitfall 4: Precedent vs rulebook FAISS confusion
**What goes wrong:** Code accidentally queries `deficiency_kb.faiss` (old, maps to SQLite rowids) instead of `rulebook.faiss` (new, maps to RuleChunk doc_ids with Phase-2 substrate ingestion).
**Root cause:** Two FAISS indexes exist with similar names and purposes.
**How to avoid:** ALWAYS use `rulebook.store._rulebook_search_local()` (which loads `data/rulebook.faiss` / `data/rulebook_map.json`) for Phase 5 precedent queries. Never call `databricks.vector._search_faiss()` for precedent (it uses the old index). Filter by `doc_id.startswith("precedent-")`.
**Warning signs:** ANDA# filter not working because `get_provenance(doc_id)` returns nothing (doc_id is an integer rowid, not a `"precedent-"` prefixed string).

### Pitfall 5: Rule span for structural findings when no rulebook rule applies
**What goes wrong:** A labeled-aggregate recompute (Table 19 total < single component) has no applicable rulebook rule span — it's purely arithmetic. The emit gate requires `rule_span_id` to be non-None for a non-absence finding.
**Root cause:** `emit_finding` and `emit_absence_finding` both require a rule half. But `SUM/MAX` aggregate recomputes may not have a specific rule clause.
**How to avoid:** For purely arithmetic structural checks (labeled-aggregate recompute), the rule span CAN be the general ICH Q2/Q6A requirement for "internally consistent results" if one exists in the rulebook. OR: the emit gate for structural findings accepts `rule_span_id=None` for STRUCTURAL findings where the verdict is derived purely from arithmetic (the submission contradicts itself, not a specific rule). This requires a small gate modification. [ASSUMED: the emit gate will need to allow `rule_span_id=None` for STRUCTURAL leg where no specific rule applies — this is a design decision the planner must make]

### Pitfall 6: Reference cue-word patterns flagged by guard as corpus constants
**What goes wrong:** A regex like `r"Module 3\.2\.[SP]\."` in `references.py` is flagged by the NO-CONSTANT CTD-family scan because it contains `3.2.S.`.
**Root cause:** The existing NO-CONSTANT scan uses `r"3\.2\.[SP]\."` to reject CTD section paths. But a reference EXTRACTOR legitimately uses this pattern as a general regex to DETECT such paths.
**How to avoid:** Register general regexes in the `REFERENCE_CUE_WORDS` allowlist in `guard_vocab.py`. The guard must distinguish "inline string literal `3.2.S.4.1`" from "general regex pattern `r\"3\\.2\\.[SP]\\.\"` used to extract any CTD path". The scan can check: if the pattern match occurs inside a `re.compile(...)` call or `r"..."` string (regex context), it is a general pattern (allowed); if it occurs as a bare string comparison, it is a literal (flagged).
**Warning signs:** NO-CONSTANT test fails on `references.py` due to the general CTD-extraction regex.

### Pitfall 7: Per-submission index persistence — race condition or stale load
**What goes wrong:** Two concurrent ingestion runs for the same submission write the index simultaneously. Or a run loads an index built with an old normalizer version.
**Root cause:** The cache key folds in normalizer/serializer/parser versions, so stale loads are prevented. But concurrent writes to `.npy` files (non-atomic) can corrupt.
**How to avoid:** Use atomic write-then-rename (`tmp → os.replace`) the same way `ingest.store.write_doc_cache` does for the JSON cache. The content hash + version key makes the final path deterministic; no lock is needed if writes are atomic. [VERIFIED: ingest/store.py:56–67 pattern]

### Pitfall 8: Fixture bge-m3 cosine regime — degenerate fixture text
**What goes wrong:** The synthetic fixture uses boilerplate placeholder text ("Lorem ipsum" style) that produces near-zero dense cosine similarity against real precedent chunks. The THRESHOLD-TRANSFER invariant becomes meaningless.
**Root cause:** D-GRD1 constraint 3: the fixture must have realistic regulatory prose.
**How to avoid:** Write fixture text as actual regulatory-domain sentences (method validation, stability data, impurity results, etc.) even if the values are entirely made up. The vocabulary must match the domain so bge-m3 places the embeddings in the right part of the semantic space.
**Warning signs:** Dense cosine scores for fixture content against precedent chunks all below 0.3 — indicates degenerate fixture text.

---

## Code Examples

### Reading addressable table cells (D-STR5)
```python
# Source: verified against src/ingest/corpus.py:159–165 + live cache inspection
from schemas.documents import SpanID
from ingest.corpus import CorpusIndex

def get_table_cells(corpus: CorpusIndex, doc_id: str) -> dict[tuple, SpanID]:
    """Returns {(table_id, row, col): SpanID} for all addressable cells in doc_id."""
    cache = corpus.cached_entry(doc_id)
    if cache is None:
        return {}
    table_index_raw = cache.get("table_index", {})
    result = {}
    for key, span_dict in table_index_raw.items():
        parts = key.split(",", 2)
        if len(parts) == 3:
            table_id, row, col = parts[0], int(parts[1]), int(parts[2])
            result[(table_id, row, col)] = SpanID.model_validate(span_dict)
    return result
```

### Precision-derived comparison (D-STR4)
```python
# Source: derived from CONTEXT.md D-STR4 + USP/ICH General-Notices rounding rule
import re
from decimal import Decimal

def _stated_precision(text: str) -> int:
    """Count decimal digits in the first numeric value in text."""
    m = re.search(r'(\d+)\.(\d+)', text)
    if m:
        return len(m.group(2))
    return 0

def compare_values(claim_text: str, ref_text: str, comparator: str) -> bool | None:
    """Returns True = violation, False = complies, None = abstain."""
    try:
        claim_num = float(re.search(r'[\d.]+', claim_text).group())
        ref_num = float(re.search(r'[\d.]+', ref_text).group())
    except (AttributeError, ValueError):
        return None  # abstain on unparseable
    claim_prec = _stated_precision(claim_text)
    ref_prec = _stated_precision(ref_text)
    # Round finer operand to coarser's precision
    prec = min(claim_prec, ref_prec)
    rounded_claim = round(claim_num, prec)
    rounded_ref = round(ref_num, prec)
    if comparator in ("LEQ", "NMT"):
        return rounded_claim > rounded_ref
    elif comparator in ("GEQ", "NLT"):
        return rounded_claim < rounded_ref
    elif comparator == "EQUALS":
        return rounded_claim != rounded_ref
    return None  # unknown comparator → abstain
```

### Adding an edge to the reference graph (D-REF, D-RB3)
```python
# Source: verified against src/rulebook/edges.py:30–46
from rulebook.edges import add_edge
from schemas.documents import SpanID
import json

def register_reference_edge(
    src_span: SpanID,
    dst_span: SpanID | None,
    edge_type: str,
    db_path: str,
) -> None:
    """Register a reference edge with the src span as provenance (D-RB3)."""
    # provenance_span_id = the src span that CONTAINS the reference text
    prov = json.dumps(src_span.model_dump())
    src_id = f"{src_span.doc_id}:{src_span.start}"
    dst_id = f"{dst_span.doc_id}:{dst_span.start}" if dst_span else "unresolved"
    add_edge(src_id, dst_id, edge_type, prov, db_path=db_path)
    # add_edge rejects empty prov (edges.py:33) — prov is always the src span JSON
```

### Query precedent index with ANDA# exclusion (D-PRC3)
```python
# Source: derived from verified src/rulebook/store.py:209–244 + src/rulebook/precedents.py:117–123
from rulebook.store import _rulebook_search_local, _faiss_doc_ids
from rulebook.precedents import get_provenance
from retrieval.vector_search import embed_query
import numpy as np

def search_precedents(
    section_text: str,
    top_k: int = 5,
    threshold: float = 0.6,
    submission_anda_number: str | None = None,
) -> list[tuple[str, float]]:
    """Returns [(precedent_doc_id, cosine_score)] above threshold, same-ANDA excluded."""
    results = _rulebook_search_local(section_text, top_k * 3)
    # Filter to precedent chunks only
    precedent_results = [c for c in results if c.doc_id.startswith("precedent-")]
    # Apply ANDA# exclusion
    filtered = []
    for chunk in precedent_results:
        if submission_anda_number:
            provenance = get_provenance(chunk.doc_id)
            if any(str(p.get("anda_number")) == submission_anda_number for p in provenance):
                continue  # same-ANDA exclusion
        # Compute dense cosine for threshold check
        # (store.py returns chunks; need actual cosine score)
        filtered.append(chunk)
    return filtered[:top_k]
```

### Emit structural finding following Phase-4 gate pattern
```python
# Source: pattern from src/tools/emit_finding.py:137–230 (emit_absence_finding)
def emit_structural_finding(
    corpus: CorpusIndex,
    rule_span_id: SpanID | None,
    structural_anchor: StructuralAnchor,
    ledger: RetrievalLedger,
    ...
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
) -> Fault | ToolRejected:
    # 1. Rule half: byte-exact (same as emit_absence_finding lines 163–189)
    #    May be None for pure-arithmetic checks (labeled-aggregate with no rule)
    if rule_span_id is not None:
        if not ledger.was_issued(rule_span_id): return ToolRejected(...)
        rule_nt = rulebook_nt_for(rule_span_id.doc_id, ...)
        try: open_span(rule_span_id, rule_nt, rule_span_id.doc_id)
        except HashMismatch: return ToolRejected(...)

    # 2. Submission half: validate ALL basis span-IDs
    for span_id in [structural_anchor.claim_span_id] + structural_anchor.basis_span_ids:
        if not ledger.was_issued(span_id): return ToolRejected(...)
        if structural_anchor.comparison_store == "CORPUS":
            cache = corpus.cached_entry(span_id.doc_id)
            # validate open_span
        else:
            rule_nt = rulebook_nt_for(span_id.doc_id, ...)
            # validate open_span

    # 3. Re-derivability check: enough basis spans for re-computation
    if len(structural_anchor.basis_span_ids) < 1:
        return ToolRejected(..., reason_code="unanchored_structural", ...)

    return Fault(
        ..., leg_tag="STRUCTURAL", structural_anchor=structural_anchor,
        verdict=ComplianceVerdict.VIOLATION, evidence_class=EvidenceClass.CODE_VERIFIED,
        tier=Tier.VERIFIED,  # code-verified structural computation → VERIFIED tier
    )
```

---

## State of the Art

| Old Approach | Current Approach | Status |
|--------------|------------------|--------|
| search_corpus re-embeds whole submission per query | D-R5B: build once at ingest, load at query | Phase 5 implements |
| RRF-score (max 0.0328) vs 0.04 threshold → dead branch | Dense cosine (0–1) vs general threshold | Phase 5 implements |
| follow_reference returns `cross_document_resolution_pending_phase_4` sentinel | Real reference-graph lookup via edges.py | Phase 5 fills |
| Precedent FAISS (old deficiency_kb.faiss) → SQLite rowids, no ANDA# filter | Rulebook FAISS (rulebook.faiss) → RuleChunk doc_ids → precedent_provenance ANDA# | Phase 5 registers the query tool |
| Anti-overfitting guard corpus-gated (pytest.skip without held-out PDF) | D-GRD1/D-GRD2: committed synthetic fixture → all 3 invariants execute in fast CI | Phase 5 provisions |

---

## Runtime State Inventory

Phase 5 is NOT a rename/refactor phase. Standard greenfield additions. No runtime state migration required.

However, note:
- `data/deficiency_kb.faiss` + `data/deficiency_kb_map.json` are the OLD pre-Phase-2 index and should NOT be used by Phase 5 code. They may continue to exist but Phase 5 must not query them. No deletion action needed (they back the legacy `databricks/vector.py` path).
- `data/rulebook.faiss` + `data/rulebook_map.json` are the Phase-2 substrate index, already present and correct.
- The per-submission index persistence (D-R5B) adds new sidecar files to `data/ingest_cache/` alongside existing JSON cache files. These are additive; no existing state is invalidated.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `faiss` | Precedent FAISS + rulebook FAISS queries | ✓ | present | — |
| `sentence-transformers` / bge-m3 | Dense embeddings | ✓ | present | — |
| `numpy` | Cosine similarity | ✓ | present | — |
| `python-docx` | DOCX hyperlink extraction | ✓ | present | — |
| `PyMuPDF` (fitz) | PDF link annotation extraction | ✓ | present | — |
| `rank-bm25` | BM25 for per-submission index | ✓ | present | — |
| `pydantic v2` | Anchor + Fault models | ✓ | present | — |
| `sqlite3` | edges, precedent_provenance tables | ✓ | stdlib | — |
| Databricks serving | (optional) embedding backend | conditional | — | Local bge-m3 via sentence-transformers |

No missing dependencies. [VERIFIED: all imported in existing src/ files]

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already configured, `asyncio_mode=auto` in pyproject.toml) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `PYTHONPATH=src uv run pytest -m "not slow" -q tests/rulebook/ tests/tools/ tests/evals/` |
| Full suite command | `PYTHONPATH=src uv run pytest -q` |
| Guard gate | `PYTHONPATH=src uv run python -m evals.run structural-gate` (new, Phase 5) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RECALL-02 | Structural inconsistency detection on table cells | unit | `pytest tests/rulebook/test_structural.py -x` | ❌ Wave 0 |
| RECALL-02 | Emit gate rejects unanchored structural finding | unit | `pytest tests/tools/test_emit_structural_finding.py -x` | ❌ Wave 0 |
| RECALL-02 | MS-01/MS-04 recovered end-to-end | integration | `PYTHONPATH=src python -m evals.run structural-gate` | ❌ Wave 0 |
| RECALL-03 | Reference extraction finds DOCX hyperlinks | unit | `pytest tests/rulebook/test_references.py::test_docx_hyperlink_extraction -x` | ❌ Wave 0 |
| RECALL-03 | ABSENT_TARGET consults manifest first | unit | `pytest tests/rulebook/test_references.py::test_absent_target_manifest_check -x` | ❌ Wave 0 |
| RECALL-03 | VALUE_CONTRADICTION uses RECALL-02 comparator | unit | `pytest tests/rulebook/test_references.py::test_value_contradiction_reuses_comparator -x` | ❌ Wave 0 |
| RECALL-04 | Precedent query excludes same-ANDA chunks | unit | `pytest tests/rulebook/test_precedent_search.py::test_same_anda_exclusion -x` | ❌ Wave 0 |
| RECALL-04 | PrecedentAnchor emission follows emit-gate contract | unit | `pytest tests/rulebook/test_precedent_search.py::test_emit_precedent_gate -x` | ❌ Wave 0 |
| RECALL-05 | RRF score ceiling ≤ 0.04 (confirming dead branch) | regression | `pytest tests/retrieval/test_hybrid.py::test_rrf_ceiling -x` | ❌ Wave 0 |
| RECALL-05 | Dense cosine range 0–1 after D-R5A change | unit | `pytest tests/tools/test_search_corpus.py::test_dense_cosine_range -x` | ❌ Wave 0 |
| RECALL-05 | Per-submission index built at ingest + loaded at query | integration | `pytest tests/ingest/test_corpus_index_persistence.py -x` | ❌ Wave 0 |
| RECALL-05 (guard) | SAME-LOGIC invariant executes in fast CI on synthetic fixture | unit | `pytest tests/evals/test_generality_guard.py::test_structural_no_corpus_constant -x` | ❌ Wave 0 |
| RECALL-05 (guard) | THRESHOLD-TRANSFER with frozen threshold on synthetic fixture 2 | unit | `pytest tests/evals/test_generality_guard.py::test_threshold_transfer_synthetic -x` | ❌ Wave 0 |
| RECALL-05 (guard) | RENAME-INVARIANCE on synthetic fixture | unit | `pytest tests/evals/test_generality_guard.py::test_rename_invariance_synthetic -x` | ❌ Wave 0 |
| All | Zero true-positives lost (C-01, C-02 remain found) | gate | `PYTHONPATH=src python -m evals.run absence-gate` (existing) | ✅ |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src uv run pytest -m "not slow" -q tests/rulebook/ tests/tools/`
- **Per wave merge:** `PYTHONPATH=src uv run pytest -m "not slow" -q` + all eval gates
- **Phase gate:** Full suite green + all gates (`coverage-gate`, `absence-gate`, `structural-gate`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/rulebook/test_structural.py` — covers RECALL-02 structural detection
- [ ] `tests/tools/test_emit_structural_finding.py` — covers RECALL-02 gate
- [ ] `tests/rulebook/test_references.py` — covers RECALL-03 reference extraction
- [ ] `tests/tools/test_emit_reference_finding.py` — covers RECALL-03 gate
- [ ] `tests/rulebook/test_precedent_search.py` — covers RECALL-04 precedent tool
- [ ] `tests/ingest/test_corpus_index_persistence.py` — covers RECALL-05 D-R5B
- [ ] `tests/fixtures/synthetic_submission/` — committed synthetic corpus (D-GRD1)
- [ ] `src/rulebook/guard_vocab.py` — registered general-vocabulary allowlist (D-GRD3)
- [ ] Guard extension in `tests/evals/test_generality_guard.py` — new invariants for structural/reference/precedent modules

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | all inputs through pydantic v2 models; `open_span` HashMismatch rejects tampered spans |
| V5 Path traversal | yes | `ingest.limits.safe_resolve` already guards corpus root; sidecar index files use content-hash-keyed paths (no user-controlled filenames) |
| V6 Cryptography | no | hash is for integrity verification (Blake2b in `content_hash`), not encryption |
| V2 Authentication | no | no new auth surface |

No new security surface beyond existing ingest/store patterns. The per-submission index persistence uses the same atomic write + content-hash key pattern as `write_doc_cache` — not susceptible to path traversal because the key is `content_hash` (hex characters only, safe for filesystem). [VERIFIED: ingest/store.py:28 `_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")` sanitizes keys]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The correct FAISS index for RECALL-04 precedent queries is `data/rulebook.faiss` (not `data/deficiency_kb.faiss`) | Research Domain 3 | If wrong: ANDA# filter won't work (deficiency_kb.faiss has no doc_id → precedent_provenance path); planner would direct executor to wrong asset |
| A2 | `submission_anda_number` parameter defaults to None (Phase 5 does not detect ANDA# from doc content) | Research Domain 3 | If wrong: same-ANDA exclusion may silently not fire; acceptable risk — Phase 5 is recall-biased; same-ANDA inclusions are later pruned by Phase 7 verifier |
| A3 | `emit_structural_finding` will be allowed to accept `rule_span_id=None` for labeled-aggregate checks with no specific rule clause | Research Domain 2 + Code Examples | If wrong: every aggregate check must find a rulebook rule span (may be possible — ICH Q2 "consistency" requirement); planner must decide |
| A4 | `rule_span_id=None` for STRUCTURAL leg is acceptable for labeled-aggregate checks (pure arithmetic verdict) | Research Domain 6 (Shared envelope) | If wrong: need to add a "generic structural integrity" rulebook entry to provide a rule span for all checks |
| A5 | Option A for D-R5A (return dense cosine as primary `score`, keep RRF in `rrf_score`) is the preferred approach | Research Domain 4 | If wrong: search result ordering may degrade for BM25-strong exact-id queries; should preserve BM25 as tiebreaker |
| A6 | Dense bge-m3 cosine general threshold will land around 0.5–0.6 for addressed requirements; must be measured empirically | Research Domain 4 | If wrong: wrong threshold direction (too high → over-emit; too low → under-emit); measured and recorded per D-THR pattern, so adjustable |
| A7 | The minispec MS-01/MS-02/MS-04 items are the testable targets for Phase 5 SC2 (the "X1/X2 catches" in the ROADMAP) given the current single-doc eval corpus | Research Domain 6 | If wrong and SC2 requires a true multi-doc X1 cross-document check: would need a new multi-doc eval fixture; raise with senior reviewer before locking the success-criteria interpretation |
| A8 | bge-m3 cosine for realistic regulatory fixture text vs precedent deficiency descriptions lands in 0.5–0.8 range | Research Domain 5 (Pitfall 8) | If wrong (too low): THRESHOLD-TRANSFER invariant in fast CI is vacuous; must write fixture text more carefully |
| A9 | Python `round(0.104, 2) == 0.1` (banker's rounding) — the precision-derived comparator must use Python's built-in `round()` | Research Domain 2 | If wrong (Python rounds differently): limit exceedance comparisons may be off by 1 ULP; safe bet since Python `round()` follows IEEE 754 banker's rounding |

---

## Open Questions (RESOLVED)

1. **Should rule_span_id be required for STRUCTURAL findings, and if so, which rule?**
   - What we know: `emit_finding` requires `rule_span_id`. Pure aggregate arithmetic (Table 19 total < single component) has no specific single FDA/ICH rule — it's internal consistency.
   - What's unclear: Does the ICH Q2(R2) or Q6A general "results must be internally consistent" requirement suffice as the rule span? Or should the emit gate be relaxed for STRUCTURAL leg?
   - Recommendation: Add a general "data consistency" rule entry to the requirement index (e.g., ICH Q2 "reportable value" clause) that can serve as the rule span for aggregate checks. Alternatively, relax the gate for STRUCTURAL: `rule_span_id` optional (consistent with absence finding's different submission half). Raise with senior reviewer.
   - **RESOLVED (D-STR6):** rule_span_id is nullable for the STRUCTURAL leg. Pure internal-consistency findings (aggregate recompute, summary-vs-detail mismatch) emit with no rule span (rule_span_id=None); only result-exceeds-spec-limit cites the rulebook limit span when available. Do NOT invent a general data-consistency rule — the emit gate is relaxed to permit null ruleId for STRUCTURAL findings per D-ENV1 ("rule span attached only when a rule applies"). Decided in CONTEXT.md D-STR6.

2. **Multi-doc submission fixture for true X1 test (QOS vs Module cross-reference)**
   - What we know: Current mvr1381/minispec eval corpora are single-document. True X1 (QOS 2.3 vs Module 3.2.P.5 cross-doc mismatch) requires two documents.
   - What's unclear: Does Phase 5 SC2 ("catching at least one X1") require adding a multi-doc eval fixture, or is the minispec's intra-document MS-01/MS-02 sufficient proxy?
   - Recommendation: The synthetic fixture (D-GRD1) should be a multi-doc submission (doc_a = QOS analog, doc_b = Module analog) and serve double duty: (a) anti-overfitting guard corpus, (b) provides the cross-document X1/X2 testable scenario. Raise with senior reviewer before authoring the fixture.
   - **RESOLVED (D-GRD4):** The committed synthetic fixture is multi-document — doc_a (QOS analog, PDF) and doc_b (Module 3.2 analog, DOCX) — with planted X1 (value in doc_a cross-referenced to doc_b with a contradiction) and X2 (cross-doc value inconsistency). It serves double duty: (a) anti-overfitting guard corpus for SAME-LOGIC/THRESHOLD-TRANSFER/RENAME invariants, and (b) the cross-document end-to-end catch for SC2. A separate fixture_b (distinct surface forms) is also committed for the THRESHOLD-TRANSFER invariant proper. Decided in CONTEXT.md D-GRD4.

3. **DOCX hyperlink extraction — extend parse layer vs. re-open DOCX from root path?**
   - What we know: `parse/docx.py` currently extracts paragraph text and tables but NOT hyperlinks. The corpus cache stores canonical text but not the raw DOCX bytes.
   - What's unclear: Is it acceptable to extend `extract_docx()` to also emit a `hyperlinks: list[dict]` field in the parsed dict, or should the reference extractor re-open the DOCX from `CorpusIndex.root / DocEntry.filename`?
   - Recommendation: Extend `extract_docx()` to emit hyperlinks in the parsed dict (stored in cache under `"hyperlinks"` key). This preserves the offline guarantee (no re-parsing at query time) and keeps all extraction at ingest time. The planner should allocate a Wave 0 task to add this to `parse/docx.py`.
   - **RESOLVED:** extend `extract_docx()` at ingest to emit a `hyperlinks` field in the parsed dict (list of {rId, target, paragraph_index}), keeping all extraction at ingest time and preserving the offline cache guarantee. This is implemented in Plan 01 Wave-0 Task 1a (parse-layer backfill). Decided by planner following the recommendation.

---

## Sources

### Primary (HIGH confidence)
- `src/retrieval/hybrid.py` — RRF formula + k=60 confirmed, 2/61 ceiling computed [VERIFIED: repo code]
- `src/tools/search_corpus.py` — re-embed-per-query path confirmed at lines 42–56 [VERIFIED: repo code]
- `src/ingest/corpus.py` — table_index persistence in cache at line 163 [VERIFIED: repo code]
- `src/ingest/tables.py` — `(table_id,row,col)→SpanID` build logic [VERIFIED: repo code]
- `src/rulebook/absence.py` — RECALL-01 pattern, dead-branch at line 142 [VERIFIED: repo code]
- `src/schemas/faults.py` — CoverageAbsenceAnchor + Fault model, additive-field pattern [VERIFIED: repo code]
- `src/tools/emit_finding.py` — dual-gate pattern for emit_absence_finding [VERIFIED: repo code]
- `src/tools/follow_reference.py` — Phase-4 stub + contract [VERIFIED: repo code]
- `src/rulebook/edges.py` — generic edge table, provenance enforcement [VERIFIED: repo code]
- `src/rulebook/precedents.py` — ANDA# in `precedent_provenance`, doc_id prefix, 385 chunks [VERIFIED: repo code]
- `src/rulebook/store.py` — rulebook.faiss + rulebook_map.json, `rebuild_local_index`, precedent filtering by doc_id prefix [VERIFIED: repo code]
- `src/databricks/vector.py` — deficiency_kb.faiss path + map format (list of rowids) [VERIFIED: repo code + data/deficiency_kb_map.json inspection]
- `tests/evals/test_generality_guard.py` — Phase-4 guard structure, CTD-family scan regex, float sentinel whitelist [VERIFIED: repo code]
- `.github/workflows/test.yml` — what actually runs in CI [VERIFIED: repo config]
- `src/evals/dataset/mvr1381.deficiencies.json` + `minispec.deficiencies.json` + `heldout32s41.deficiencies.json` — eval dataset structure, X1/X2 ground truth families [VERIFIED: repo data]
- `data/ingest_cache/` — live cache inspection showing table_index key format `",0,0"` [VERIFIED: live data]
- `.planning/phases/05-deterministic-structural-cross-document-recall/05-CONTEXT.md` — all locked decisions [VERIFIED: planning doc]
- `.planning/phases/04-rulebook-enrichment-absence-enumeration/04-PATTERNS.md` — Phase-4 analog map [VERIFIED: planning doc]

### Secondary (MEDIUM confidence)
- `.planning/phases/04-rulebook-enrichment-absence-enumeration/04-VERIFICATION.md` — Phase-5 handoff / known limitation + guard enforcement state [CITED: planning doc]
- `.planning/phases/02-retrieval-navigation-tools-rulebook/02-PRECEDENT-AUDIT.md` — D-PREC dedupe policy, ANDA# source [CITED: planning doc]
- `docs/databricks-rulebook-kb-representation.md` — Databricks KB shape, local vs Databricks dispatch [CITED: repo doc]

### Tertiary (LOW confidence)
- A5 (dense cosine threshold range ~0.5–0.6) — based on typical bge-m3 behavior in regulatory domain; must be measured empirically [ASSUMED]
- A8 (fixture cosine range) — based on typical sentence-transformers behavior; must be validated when fixture is authored [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified present in repo
- Architecture patterns: HIGH — all based on verified repo code with exact file:line citations
- Structural leg (RECALL-02): HIGH — table_index format verified in live cache; comparison algorithm derived from locked decisions
- Reference graph (RECALL-03): MEDIUM-HIGH — edges.py verified; parse layer gap confirmed; extraction algorithm is new
- Precedent leg (RECALL-04): HIGH on data structure (two-FAISS finding critical); MEDIUM on query implementation (untested in new form)
- Retrieval fixes (RECALL-05): HIGH — RRF ceiling confirmed; exact change points identified
- Guard (RECALL-05 guard): HIGH — existing guard code verified; synthetic fixture constraints are locked decisions
- Pitfalls: HIGH — all derived from actual code inspection

**Research date:** 2026-08-06
**Valid until:** 2026-09-05 (30 days — stable Python/FAISS/pydantic codebase; internal code patterns are durable)
