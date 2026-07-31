# Phase 2: Retrieval, Navigation Tools & Rulebook - Pattern Map

**Mapped:** 2026-07-31
**Files analyzed:** 38 (5 navigation tools + 3 grounding-gate support files + 6 rulebook-package files + 2 rulebook data files + 1 Databricks-serving extension + 2 retrieval extensions + 2 eval-harness modifications + 1 baseline artifact + 15 test files)
**Analogs found:** 35 / 38 direct or strong role-match; 3 explicit no-analog (genuinely new logic, noted below)

**Filename provenance note:** Most paths below are copied verbatim from RESEARCH.md's "Recommended Project Structure" (already very prescriptive — this session's job is to map patterns onto it, not invent a different layout). Two files are *inferred* from RESEARCH.md's "Architectural Responsibility Map" prose, which named the capability and its owning layer but not an exact filename: `src/rulebook/store.py` (local SQLite+FAISS+BM25 backend) and `src/databricks/rulebook.py` (Databricks-side serving extension). Both are flagged inline — confirm the exact name at plan time if it matters.

**Hard constraint honored:** `src/agents/detection/{challenge,pipeline,planning,prompts,sandwich,summarise,verify,workers}.py`, `src/llm/{client,structured}.py`, `src/schemas/faults.py`, `tests/agents/detection/test_planner_redesign.py`, `tests/unit/test_detection.py` appear **only** in the Analog / Closest-Analog columns below (read-only reuse-by-import), **never** in a New/Modified File column.

## File Classification

Grouped by RESEARCH.md's six requirement-clusters, since that is how the planner will likely organize plans.

### Cluster 1 — Navigation Tools (TOOLS-01/02/04, D-FR, D-RI2, D-GRAN)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `src/tools/__init__.py` | utility (barrel) | file-I/O | `src/ingest/__init__.py` (lazy PEP-562 barrel) | role-match |
| `src/tools/search_corpus.py` | service | request-response | `src/databricks/vector.py::search_similar`/`_search_embeddings_table` + `src/retrieval/vector_search.py::embed_query` | role-match (dispatch shape exact; BM25 leg is new) |
| `src/tools/open_doc.py` | service | request-response | `src/ingest/corpus.py::CorpusIndex.cached_entry` + `src/ingest/anchors.py::open_span` | exact |
| `src/tools/get_section.py` | service | request-response (bounded) | `src/ingest/anchors.py::open_span` + `src/ingest/limits.py::LimitExceeded` (reject-with-reason) | role-match |
| `src/tools/follow_reference.py` | service | request-response | `src/ingest/corpus.py::_build_outline` + `src/ingest/manifest.py::OutlineEntry` | role-match |
| `src/tools/read_guideline.py` | service | request-response (dual-mode) | `src/ingest/registry/__init__.py::load_families`/`family_ids` (enumerate) + `src/ingest/anchors.py::open_span` (fetch) | exact |

### Cluster 2 — Grounding Gate (TOOLS-03, D-EF1, D-GRAN, COST-04)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `src/tools/emit_finding.py` | service (gate) | request-response | `src/ingest/anchors.py::open_span`/`HashMismatch` (THE primitive, reused verbatim) + `src/schemas/faults.py::Fault` (artifact on success) | exact |
| `src/tools/ledger.py` | store (per-run, in-memory) | CRUD | `src/ingest/classify.py::EscalationStats` (per-run-scoped counter class) | partial (structurally similar: a small stateful class threaded through one run; different domain — counts vs. a set of issued IDs) |
| `src/tools/errors.py` | model (typed schema) | transform | `src/schemas/llm.py::ParseFailed` (chosen sentinel shape) vs. `src/ingest/anchors.py::HashMismatch` (rejected exception shape) — see RESEARCH.md Pattern 3 | exact (shape already decided by RESEARCH.md) |

### Cluster 3 — Rulebook Sourcing: parse + build (RULES-01/02/03/04, D-RB1, D-RB2)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `src/rulebook/__init__.py` | utility (barrel) | file-I/O | `src/ingest/__init__.py` (lazy PEP-562 barrel) | role-match |
| `src/rulebook/ecfr_parse.py` | utility (transform) | transform | **Output contract:** `src/parse/pdf.py::extract_pdf` (the dict shape to converge on) + `tests/ingest/conftest.py::make_doc_dict` (the shape spec, executable) | role-match on the OUTPUT side; **no analog** for the eCFR-XML-walking INPUT side (see No Analog Found) |
| `src/rulebook/build.py` | service (one-time batch orchestrator) | batch | `src/ingest/corpus.py::ingest_corpus` (never-abort walk→parse→persist loop) + `src/ingest/__main__.py` (thin CLI shell) + `src/llm/client.py::chat_completion_full` (retry/backoff idiom, READ-ONLY reuse) | exact (orchestration shape) |
| `rulebook/manifest.yaml` (data, git-tracked, NOT `data/`) | config | file-I/O | `src/ingest/registry/ctd_families.yaml` (data-file shape) + RESEARCH.md's RULES-04 metadata schema | role-match |

### Cluster 4 — Rulebook Storage: edges + requirement index + local backend (D-RB3, D-RB4, D-RI1, D-RB6)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `src/rulebook/edges.py` | store | CRUD | `src/ingest/store.py` (SQLite job-store: `_get_conn`/`_ensure_table`/`save_manifest`/`load_manifest`) | exact |
| `src/rulebook/requirement_index.py` | service (loader gate) + model (`RequirementEntry`) | CRUD (load+validate) | `src/ingest/registry/__init__.py` (`lru_cache`-over-`yaml.safe_load`) + `src/ingest/classify.py::_llm_tier` (structured-call LLM-tier pattern, READ-ONLY reuse of `llm.structured`) + `src/ingest/anchors.py::open_span` (loader-gate validation) | exact |
| `src/rulebook/requirement_index.yaml` (data) | config | file-I/O | `src/ingest/registry/ctd_families.yaml` (exact `{id, label/trigger, ...}` shape mirror, by design per both docs) | exact |
| `src/rulebook/store.py` *(inferred filename)* | store | CRUD | `src/ingest/store.py` (SQLite conventions) + `src/databricks/vector.py::_ensure_faiss`/`build_local_index`/`_search_faiss` (local FAISS build/persist/query) | exact |

### Cluster 5 — Databricks Serving + Retrieval Extension (D-RB2, D-RB5, D-RB6)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `src/databricks/rulebook.py` *(inferred filename)* | service | request-response | `src/databricks/vector.py` (`_search_databricks`/`_search_embeddings_table`/`_search_text_fallback` dispatch) + `src/databricks/delta.py` (`_run_sql`/`_table`/`_escape`) | exact — this is the single most important analog per the task brief |
| `src/retrieval/lexical.py` | service | request-response (+ transform sub-step: index build) | `src/databricks/vector.py::_ensure_faiss`/`build_local_index`/`_search_faiss` (same "build local index, persist, query" shape, applied to `rank-bm25` instead of FAISS) | role-match |
| `src/retrieval/hybrid.py` | utility | transform | **No analog** — RRF fusion is ~10 lines of public, well-known formula; RESEARCH.md explicitly says no library/precedent needed | no analog (see below) |

### Cluster 6 — Eval Harness Extension (D-SC4)

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `src/evals/run.py` **(MODIFY — add `retrieval-gate` subcommand)** | controller (CLI) | batch | **Itself** — `cmd_score`/`cmd_gate`/`cmd_run` in the same file (lines 125–241) | exact (extend the file's own established pattern) |
| `src/evals/metrics.py` **(MODIFY — upgrade `_retrieval_recall_at_k`)** | utility (metrics) | transform | **Itself** — the existing `_retrieval_recall_at_k` (lines 75–97) whose own docstring says *"Upgrades to true corpus recall@k once an explicit retrieval/navigation stage exists (Phase 2)"* + `src/evals/match.py::_anchor_tokens`/`matches` (verbatim substring-anchor matching against `evidence_anchor`) | exact — this is a load-bearing finding, not a guess |
| `src/evals/baseline/retrieval_recall.json` (data) | config | file-I/O | `src/evals/baseline/recall_by_family.json` (exact shape mirror) | exact |

### Cluster 7 — Tests (Wave 0 Gaps in RESEARCH.md's Validation Architecture)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|-----------------|----------------|
| `tests/tools/__init__.py`, `tests/rulebook/__init__.py` | test | file-I/O | `tests/ingest/__init__.py` | exact |
| `tests/tools/conftest.py` | test (fixtures) | request-response | `tests/ingest/conftest.py` (`offline`/`no_llm` fixtures + `make_doc_dict` factory) | exact |
| `tests/rulebook/conftest.py` | test (fixtures) | file-I/O | `tests/ingest/conftest.py` (same offline-fixture discipline; RESEARCH.md's own Wave-0-Gaps note says to mirror it) | exact |
| `tests/tools/test_contracts.py` | test | request-response | `tests/ingest/test_anchors.py` (contract-assertion style) | role-match |
| `tests/tools/test_span_selection.py` | test | request-response | `tests/ingest/test_anchors.py::test_reopen_and_hash_mismatch` (byte-exact reopen + tamper→exception) | exact |
| `tests/tools/test_emit_finding.py` | test | request-response | `tests/ingest/test_anchors.py` (tamper→`HashMismatch`) + `tests/evals/test_gate.py` (doctor-the-fixture-then-assert-rejection style, lines 44–81) | exact |
| `tests/tools/test_oversized_results.py` | test | request-response | `src/ingest/limits.py::LimitExceeded` usage style (`pytest.raises`-on-a-reason-carrying-exception) | role-match |
| `tests/tools/test_read_dedup.py` | test | CRUD | `tests/ingest/test_registry.py` (small, assertion-dense unit style) | partial |
| `tests/tools/test_follow_reference.py` | test | request-response | `tests/ingest/conftest.py::make_doc_dict` + `src/ingest/corpus.py::_build_outline` | role-match |
| `tests/rulebook/test_ecfr_parse.py` | test | transform | `tests/ingest/test_anchors.py` (reopen-byte-exact discipline, applied to the new parser's output) | role-match |
| `tests/rulebook/test_ich_ingest.py`, `test_fda_ingest.py` | test | transform | same as above | role-match |
| `tests/rulebook/test_metadata.py` | test | file-I/O | `tests/ingest/test_registry.py::test_each_entry_has_required_keys` (required-keys assertion, line 35–37) | exact |
| `tests/rulebook/test_requirement_index.py` | test | CRUD | `tests/evals/test_gate.py` (ground-truth-driven pass/fail testing) + `tests/ingest/test_registry.py` (loader validation style) | exact |

---

## Pattern Assignments

### Cluster 1 — Navigation Tools

#### `src/tools/search_corpus.py` (service, request-response)

**Analog:** `src/databricks/vector.py::search_similar` (dispatch) + `_search_embeddings_table` (client-side cosine — the proven-working pattern per the task brief) + `src/retrieval/vector_search.py::embed_query`.

**Dispatch pattern to copy** (`src/databricks/vector.py:63-71`):
```python
def search_similar(
    query_embedding: np.ndarray | None = None,
    query_text: str = "",
    top_k: int = 10,
) -> list[dict]:
    s = get_settings()
    if s.is_databricks:
        return _search_databricks(query_text, top_k)
    return _search_faiss(query_embedding, top_k)
```
`search_corpus` is D-RB5-locked to **always** the local/ephemeral leg (no Databricks branch at all — the per-submission index never goes to Databricks), so copy the *shape* (settings-driven, typed return), not the branch itself.

**Local FAISS build/query to copy** (`src/databricks/vector.py:26-60,74-105`):
```python
def _ensure_faiss():
    global _faiss_index, _faiss_id_map
    if _faiss_index is not None:
        return
    import faiss
    idx_path = Path(_FAISS_INDEX_PATH)
    map_path = Path(_FAISS_MAP_PATH)
    if idx_path.exists() and map_path.exists():
        _faiss_index = faiss.read_index(str(idx_path))
        _faiss_id_map = json.loads(map_path.read_text())
    else:
        _faiss_index = None
        _faiss_id_map = []

def build_local_index(embeddings: np.ndarray, row_ids: list[int]) -> None:
    import faiss
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    ...
```
Note this is a **process-lifetime cache** (module globals `_faiss_index`/`_faiss_id_map`) — for `search_corpus`'s **per-submission, per-run** index (D-RB5), thread the index through the caller (e.g. attach to `CorpusIndex` or pass explicitly), do **not** reuse a bare module-global — that is exactly Pitfall 9's ledger warning generalized to the FAISS index (one run's index must never leak into another run's query).

**Embedding leg** (`src/retrieval/vector_search.py:40-58`, reuse verbatim, unchanged):
```python
def embed_texts(texts: list[str], batch_size: int = 8) -> np.ndarray:
    s = get_settings()
    if s.is_databricks:
        return _embed_databricks(texts)
    model = _get_local_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=True, batch_size=batch_size)
```
D-RB6 pins the harness to **local bge-m3** always for `search_corpus` — call `embed_texts`/`embed_query` directly, do not add a Databricks branch inside `search_corpus` itself.

**Lexical leg:** new — see `src/retrieval/lexical.py` below; `search_corpus` composes `lexical.query(...)` + `embed_query`-driven FAISS search via `src/retrieval/hybrid.py`'s RRF.

**D-GRAN annotation requirement:** every result string must carry inline per-sentence/per-cell span-IDs, not a bare snippet — see the ledger/annotation pattern under Cluster 2 below; `search_corpus` is the first tool that needs it.

---

#### `src/tools/open_doc.py` / `src/tools/get_section.py` (service, request-response)

**Analog:** `src/ingest/corpus.py::CorpusIndex.cached_entry` (lines 52-58) + `src/ingest/anchors.py::open_span` (lines 56-72).

```python
# CorpusIndex.cached_entry — src/ingest/corpus.py:52-58
def cached_entry(self, doc_id: str) -> dict | None:
    """Fetch a document's persisted cache entry (full canonical text + offset map + index)."""
    for d in self.manifest.documents:
        if d.doc_id == doc_id:
            key = cache_key(d.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION)
            return read_doc_cache(self.cache_dir, key)
    return None
```
`open_doc`/`get_section` resolve `doc_id` → cached entry → `NormalizedText` → `open_span` for any requested range. This is the exact "the corpus cache already has everything, never re-parse" seam `src/ingest/store.py`'s docstring calls out ("Phase 2 `get_section` ... never re-parse the corpus").

**TOOLS-04 "never truncate" contrast — one analog to copy, one anti-pattern to avoid:**

Copy the *reject-with-reason* shape from `src/ingest/limits.py:25-33`:
```python
class LimitExceeded(Exception):
    """Raised when an untrusted file trips a size/entry/path/ratio guard.
    `.reason` is the human-readable string recorded on the D-16 manifest row."""
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
```
**Do NOT copy** `src/agents/detection/render.py::render_sections` (lines 61-74) — it is the closest **rendering** analog (markdown section→text, character-budget bounded) but its budget-exceeded behavior is a silent truncation:
```python
if used + len(piece) > char_budget and out:
    out.append("\n[... further sections omitted for length ...]")
    break
```
This is precisely the anti-pattern RESEARCH.md's Anti-Patterns section forbids for TOOLS-04 ("a truncated result costs ~25k tokens, an error costs ~100 bytes"). Reuse `render_section` (singular, lines 39-58 — one section → markdown, no truncation) for the text-shaping half; wrap the multi-section/oversized-range case in a `ToolRejected`-style narrow-your-range error instead of `render_sections`' loop.

---

#### `src/tools/follow_reference.py` (service, request-response)

**Analog:** `src/ingest/corpus.py::_build_outline` (lines 73-86) + `src/ingest/manifest.py::OutlineEntry` (lines 29-33).

```python
# src/ingest/corpus.py:73-86 — same-doc heading resolution, span-as-identity
def _build_outline(sections: list[dict], nt, doc_id: str) -> list[OutlineEntry]:
    outline: list[OutlineEntry] = []
    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading:
            continue
        probe = heading[:40]
        pos = nt.canonical.find(probe)
        if pos < 0:
            pos = 0
        span = mint_span(nt.canonical, pos, min(len(nt.canonical), pos + len(probe)), doc_id, nt.normalizer_version)
        outline.append(OutlineEntry(span=span, label=heading))
    return outline
```
```python
# src/ingest/manifest.py:29-33 — span IS identity, label is a human string only
class OutlineEntry(BaseModel):
    span: SpanID                 # section IDENTITY (content-addressed, D-18)
    label: str = ""              # human-readable heading text — a LABEL only (D-18)
    level: int = 0
```
Same-document reference resolution (D-FR) is a lookup against a document's own already-built `outline` (persisted on `DocEntry.outline`, `src/ingest/manifest.py:47`) — no new resolution machinery needed, just a search over spans already minted at ingest time. For cross-document references, return the typed `cross_document_resolution_pending_phase_4` sentinel — same *shape* as `ParseFailed` (Cluster 2's Pattern 3), never a bare `None`/`[]`.

---

#### `src/tools/read_guideline.py` (service, request-response, dual-mode)

**Analog:** `src/ingest/registry/__init__.py` (lines 26-49) — the enumerate-mode contract is almost a direct copy.

```python
# src/ingest/registry/__init__.py:26-49
@lru_cache(maxsize=1)
def load_families() -> list[dict]:
    """Return the CTD-family entries [{id, label, applicability_trigger}, ...] (cached)."""
    with open(_FAMILIES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []

def family_ids() -> set[str]:
    """The set of all registry family ids (== a subset of CTDSection values)."""
    return {e["id"] for e in load_families()}

def families_catalog_text() -> str:
    """Render the registry for an LLM prompt, mirroring catalog.py domain_catalog_text()."""
    return "\n".join(f"- {e['id']} ({e['label']}): {e['applicability_trigger']}" for e in load_families())
```
`read_guideline(citation=None)` (enumerate mode, D-RI2) is this same `{id, citation, one-line trigger}` row-listing shape, scoped server-side by the corpus manifest + optional family filter validated against `family_ids()`-equivalent (the requirement-index's own family membership check — see Cluster 4). `read_guideline(citation="21 CFR 211.166")` (fetch mode) is `open_span`-style bounded-text retrieval, TOOLS-04-bounded exactly like `get_section`.

---

### Cluster 2 — Grounding Gate

#### `src/tools/emit_finding.py` (service/gate, request-response)

**Analog:** `src/ingest/anchors.py::open_span`/`HashMismatch` — reused **verbatim**, not reimplemented (RESEARCH.md's "Don't Hand-Roll" table is explicit: "Span integrity re-verification... Use `ingest.anchors.open_span` verbatim").

```python
# src/ingest/anchors.py:56-72 — THE re-open/verify primitive both span halves call
def open_span(span: SpanID, nt: NormalizedText, doc_id: str) -> tuple[str, str]:
    if span.doc_id != doc_id:
        raise HashMismatch(span, span.doc_id, doc_id)
    from ingest.normalize import canon_range_to_raw
    canonical = nt.canonical[span.start:span.end]
    actual = short_hash(canonical, nt.normalizer_version)
    if actual != span.hash:
        raise HashMismatch(span, span.hash, actual)
    raw_s, raw_e = canon_range_to_raw(nt.offset_map, span.start, span.end)
    return nt.raw_serialized[raw_s:raw_e], canonical
```
Exact contract to replicate, proven by `tests/ingest/test_anchors.py:10-40`:
```python
# tamper within the span (same length, preserves offsets) -> HashMismatch
tampered = nt.model_copy(update={"canonical": ...})
with pytest.raises(HashMismatch):
    open_span(span, tampered, doc_id)
```
D-EF1(1) requires calling `open_span` **twice per finding** — once against the CORPUS store for `submission_span_id`, once against the RULEBOOK store for `rule_span_id` (D-EF1(2)'s store-membership check is just "which `NormalizedText`/store did you pass to `open_span`", not new logic). On success, construct `src/schemas/faults.py::Fault` (lines 38-62, READ-ONLY reuse — this schema is not in the off-limits list, only `src/agents/detection/*` consumers of it are):
```python
class Fault(BaseModel):
    evidence: str = Field(default="", description="Verbatim span or cell the finding rests on.")
    evidence_class: EvidenceClass = EvidenceClass.MODEL_JUDGMENT
    guidance_refs: list[str] = Field(default_factory=list)
    ...
```
`EvidenceClass.QUOTE_ANCHORED` (`src/schemas/faults.py:26`) is the existing enum value that already means "the cited evidence span exists verbatim in the doc" — exactly what `emit_finding`'s successful path proves; a rulebook-grounded finding is a natural fit for this value plus a populated `guidance_refs` from the requirement-index citation.

---

#### `src/tools/ledger.py` (store, per-run, CRUD)

**Analog:** `src/ingest/classify.py::EscalationStats` (lines 44-55) — a small, explicitly per-run-constructed stateful class threaded through one call chain, never a module global. Structurally the closest thing in the repo to "a set that accumulates during one run and is read back at the end."

```python
# src/ingest/classify.py:44-55
class EscalationStats:
    """Per-tier resolution counter -> escalation_rate (D-27), surfaced in the run summary."""
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def record(self, tier: str) -> None:
        self.counts[tier] = self.counts.get(tier, 0) + 1

    def escalation_rate(self) -> dict[str, float]:
        total = sum(self.counts.values()) or 1
        return {tier: c / total for tier, c in self.counts.items()}
```
And its call-site discipline (`src/ingest/corpus.py:103` — constructed once per `ingest_corpus()` call, passed down, never global):
```python
def ingest_corpus(root, cache_dir=DEFAULT_CACHE_DIR, model=None) -> CorpusIndex:
    ...
    stats = EscalationStats()
    ...
    classification = classify_document(nt, outline=outline, doc_id=doc_id, model=model, stats=stats)
```
`RetrievalLedger` should follow the identical discipline: constructed once per agent run, passed explicitly into every tool call (constructor-injected or threaded as an argument) — this is RESEARCH.md's Pitfall 9 (Security Domain V3): a global ledger would let one run's issued span-IDs validate against a different run's `emit_finding` call. Record `(doc_id, start, end)` tuples instead of tier-name strings; `record()`/`was_issued()` replace `record()`/`escalation_rate()`.

---

#### `src/tools/errors.py` (model, transform)

**Analog:** RESEARCH.md's own Pattern 3 already resolves the design choice between the two existing typed-error conventions — reproduce it here for the exact excerpts.

Convention A (rejected for this use — raises, unwinds the Python stack):
```python
# src/ingest/anchors.py:29-43
class HashMismatch(Exception):
    def __init__(self, span: SpanID, expected: str, actual: str):
        super().__init__(f"span {span.doc_id}[{span.start}:{span.end}] hash mismatch: "
                          f"expected {expected}, got {actual}")
        self.span = span
        self.expected = expected
        self.actual = actual
```
Convention B (**chosen** — a returned sentinel, flows back to the calling model as a message):
```python
# src/schemas/llm.py — whole file, 15 lines (READ-ONLY reuse of the SHAPE, not the class itself)
class ParseFailed(BaseModel):
    """Typed sentinel — the frontend renders this as a needs-human-review card
    instead of receiving a raw LLM dump."""
    layer: str
    reason: str
    raw_output: str
    validation_error: str = ""
    requires_human_review: bool = True
```
`src/tools/errors.py::ToolRejected` should mirror `ParseFailed`'s sentinel shape (a `BaseModel` a tool *returns*, not raises) — RESEARCH.md's own draft (Code Examples, RESEARCH.md lines 342-352) is:
```python
class ToolRejected(BaseModel):
    tool: str
    reason_code: str   # "not_byte_exact" | "not_unique" | "not_retrieved_this_session"
                        # | "wrong_store" | "family_not_in_registry" | "range_too_large"
    reason: str
    hint: str = ""
```
This is RESEARCH.md's proposed synthesis, not existing code — cited here as the concrete starting point, grounded in the real `ParseFailed` convention it mirrors.

---

### Cluster 3 — Rulebook Sourcing: parse + build

#### `src/rulebook/ecfr_parse.py` (utility, transform)

**Analog (output contract only):** `src/parse/pdf.py::extract_pdf` docstring (lines 197-206) — the dict shape every rulebook source must converge on:
```python
def extract_pdf(path: str | Path) -> dict:
    """Returns a plain dict (no custom datatypes):
        {filename, page_count, toc:[{level,title,page}],
         pages:[{page_number, page_label, width, height, rotation, source, is_scanned,
                 blocks:[...], tables:[...], figures:[...]}]}
    """
```
And the exact, executable version of that shape from `tests/ingest/conftest.py::make_doc_dict` (lines 92-118) — use this as the literal target `ecfr_parse.py` must produce (a `pages[0].blocks[]` list of `{text, page, reading_order}` dicts is sufficient; no tables/figures needed for CFR prose):
```python
def make_doc_dict(blocks, tables, filename="doc.pdf", page_count=1, toc=None):
    return {
        "filename": filename, "page_count": page_count, "toc": list(toc or []),
        "pages": [{
            "page_number": 1, "page_label": "", "width": 612.0, "height": 792.0,
            "rotation": 0, "source": "pymupdf", "is_scanned": False,
            "blocks": list(blocks), "tables": list(tables), "figures": [],
        }],
    }
```
Once `ecfr_parse.py` emits this shape, it flows through `src/ingest/serialize.py::serialize_document` → `src/ingest/normalize.py::normalize` → `src/ingest/tables.py::build_table_index` **completely unchanged** — the whole point of converging on the contract. **The XML-walking logic itself (DIVn/HEAD/P/AUTH/SOURCE tags) has no in-repo analog** — see No Analog Found.

---

#### `src/rulebook/build.py` (service, batch)

**Analog:** `src/ingest/corpus.py::ingest_corpus` (lines 99-177) — the never-abort batch-orchestration shape.

```python
# src/ingest/corpus.py:132-135 — one bad item becomes a manifest row, never crashes the batch (D-16)
except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run (D-16)
    entries.append(DocEntry(doc_id=..., filename=path.name,
                            content_hash="", status="parse_failed", reason=str(exc)[:300]))
    continue
```
```python
# src/ingest/corpus.py:172-175 — persistence failure must not lose the in-memory result either
try:
    save_manifest(manifest, corpus_id=str(root))
except Exception as exc:  # noqa: BLE001
    log.warning("manifest_persist_failed", error=str(exc)[:200])
```
`build.py` should apply the identical discipline per-source (one bad eCFR part / ICH PDF / FDA guidance becomes a `manifest.yaml` row noting the failure, never aborts the whole vendored-snapshot build).

**CLI shell to copy** — `src/ingest/__main__.py`, whole file (38 lines): a thin `argparse` wrapper that only parses argv, calls the library function, and prints a summary; "Evals and later phases import the library, not the CLI" (line 8) — apply the same discipline: `src/rulebook/build.py` should expose a plain function other code can import, with a `python -m rulebook.build` shell being ergonomic sugar only.

**HTTP client shape (read-only reuse of the retry/backoff idiom, `src/llm/client.py:76-130`):**
```python
for attempt in range(_MAX_RETRIES):
    try:
        response = client.chat.completions.create(**kwargs)
        ...
    except RateLimitError as exc:
        if attempt == _MAX_RETRIES - 1:
            raise
        retry_after = _retry_after_seconds(exc)
        delay = retry_after if retry_after else min(_RATE_LIMIT_BASE_DELAY * (2 ** attempt), _RATE_LIMIT_MAX_DELAY)
        time.sleep(delay)
```
The *shape* (numbered attempts, `Retry-After` header parsing, exponential backoff, give up after N) is the pattern to copy for eCFR/regulations.gov calls — the *client* itself should mirror `src/databricks/delta.py::_sql_client`'s plain `httpx.Client` context-manager usage (lines 31-37), not the OpenAI SDK wrapper (no LLM involved in fetching rule text):
```python
def _sql_client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(base_url=s.databricks_host, headers={...}, timeout=50.0)
```

---

### Cluster 4 — Rulebook Storage: edges + requirement index + local backend

#### `src/rulebook/edges.py` (store, CRUD)

**Analog:** `src/ingest/store.py` (lines 68-106) — the SQLite job-store convention, `sqlite3.Row` + JSON columns.

```python
# src/ingest/store.py:75-92 — CREATE TABLE IF NOT EXISTS + upsert-by-primary-key
def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS corpus_manifest "
        "(corpus_id TEXT PRIMARY KEY, manifest_json TEXT, created_at TEXT)"
    )

def save_manifest(manifest: CoverageManifest, corpus_id: str = "default", db_path: str = DEFAULT_DB_PATH) -> None:
    conn = _get_conn(db_path)
    _ensure_table(conn)
    conn.execute(
        "INSERT INTO corpus_manifest (corpus_id, manifest_json, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(corpus_id) DO UPDATE SET manifest_json=excluded.manifest_json, created_at=excluded.created_at",
        (corpus_id, json.dumps(manifest.model_dump()), manifest.created_at),
    )
```
D-RB3's generic edge schema `(src_id, dst_id, edge_type, provenance_span_id)` is a direct fit for one `CREATE TABLE edges (src_id TEXT, dst_id TEXT, edge_type TEXT, provenance_span_id TEXT, PRIMARY KEY (src_id, dst_id, edge_type))` plus parameterized inserts — same file, same conventions, new table.

---

#### `src/rulebook/requirement_index.py` (service + model, CRUD/validate)

**Analog (loader, cached):** `src/ingest/registry/__init__.py:26-30` (`lru_cache`-over-`yaml.safe_load`) — copy directly:
```python
@lru_cache(maxsize=1)
def load_families() -> list[dict]:
    with open(_FAMILIES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []
```

**Analog (LLM drafter, read-only reuse of `llm.structured`):** `src/ingest/classify.py::_llm_tier` (lines 116-135) — the no-creds-skip + `structured_call` pattern:
```python
def _llm_tier(nt, doc_id, model=None) -> DocClassification | None:
    s = get_settings()
    if not (s.databricks_host and s.databricks_token):
        return None  # no creds -> skip; caller keeps the deterministic result
    ...
    instance, failure = structured_call(messages, ClassifyResult, model=model)
    if instance is None:
        return None  # ParseFailed -> caller never leaks a raw dump
    return DocClassification(...)
```
The requirement-index LLM drafter is a build-time/authoring-time tool (D-RI1's step before human review), so it should call `structured_call` the same way — never raise, always degrade to "nothing drafted" on failure, never leak `ParseFailed`'s raw text into the committed YAML.

**Analog (loader-gate validation, RESEARCH.md's own synthesis, grounded in real primitives):**
```python
# RESEARCH.md Code Examples — mirrors ingest.registry's load-time validation posture
def load_requirement_index(path: str) -> list[RequirementEntry]:
    entries = [RequirementEntry.model_validate(e) for e in yaml.safe_load(open(path))]
    for e in entries:
        if e.family not in ingest.registry.family_ids():
            raise ValueError(f"{e.id}: family {e.family!r} not in D-05 registry")
        open_span(e.provenance_span_id, rulebook_nt_for(e.provenance_span_id.doc_id), e.provenance_span_id.doc_id)
    return entries
```
This composes three already-read primitives verbatim: `ingest.registry.family_ids()` (membership check), `ingest.anchors.open_span` (provenance re-open), and pydantic `model_validate` (shape check) — no new validation machinery.

**Test analog for the loader gate** — `tests/ingest/test_registry.py:35-37` (required-keys assertion style, directly portable):
```python
def test_each_entry_has_required_keys():
    for entry in load_families():
        assert {"id", "label", "applicability_trigger"} <= set(entry), entry
```

**Draft source material already in the repo** (RESEARCH.md's own finding — not a code pattern, but the concrete v1 content the drafter/human-reviewer should start from):
- `src/agents/detection/checklists.py:19-29` — `_VALIDATION_REQUIRED` (9-key method-validation checklist, direct lift candidate for `Q2-*` requirement-index entries)
- `src/agents/detection/catalog.py:11-27` — `CANONICAL_DOMAINS` (impurities/stability/container-closure descriptions, candidate trigger-text source)

---

#### `src/rulebook/requirement_index.yaml` (data)

**Analog:** `src/ingest/registry/ctd_families.yaml` (whole file, 83 lines) — mirror this exact per-entry shape:
```yaml
- id: "3.2.S.4.3"
  label: "Drug Substance Validation of Analytical Procedures"
  applicability_trigger: "Validation of drug-substance analytical procedures (ICH Q2 parameters)."
```
The requirement index adds `family` (must be a value from this same file's `id` column, cross-validated by the loader gate), `citation`, and `provenance_span_id`, but the base `{id, label/trigger}` row shape is a deliberate, stated mirror (both `ctd_families.yaml`'s header comment and RESEARCH.md say so explicitly).

---

#### `src/rulebook/store.py` *(inferred filename — local SQLite+FAISS+BM25 backend, D-RB6)*

**Analog:** `src/ingest/store.py` (SQLite conventions, `_get_conn`/atomic JSON writes) + `src/databricks/vector.py:26-60` (`_ensure_faiss`/`build_local_index` — local FAISS build/persist/load).

```python
# src/ingest/store.py:46-57 — atomic write: temp -> os.replace, no half-written file on crash
def write_doc_cache(cache_dir, key: str, entry: dict) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    final = _cache_path(cache_dir, key)
    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry), encoding="utf-8")
    os.replace(tmp, final)
```
This is the pattern for persisting the rulebook's local chunk store deterministically from the vendored snapshot (D-RB2's "manually-built... deterministically" build output) — same atomic-write discipline the ingest cache already uses.

---

### Cluster 5 — Databricks Serving + Retrieval Extension

#### `src/databricks/rulebook.py` *(inferred filename — the single most important analog per the task brief)*

**Analog:** `src/databricks/vector.py::_search_embeddings_table` (lines 115-162) — the proven-working client-side-cosine fallback, since the Vector Search Admin API is 403 scope-blocked (RESEARCH.md Pitfall 6).

```python
# src/databricks/vector.py:115-162
def _search_embeddings_table(query_text: str, top_k: int) -> list[dict]:
    """Cosine similarity search using pre-computed embeddings stored on Databricks."""
    from retrieval.vector_search import embed_query as _embed
    query_emb = _embed(query_text)

    emb_table = _table("deficiency_embeddings")
    kb_table = _table("deficiency_kb")
    emb_data = _run_sql(f"SELECT record_id, embedding FROM {emb_table}")
    emb_rows = _rows_from_result(emb_data)
    if not emb_rows:
        return _search_text_fallback(query_text, top_k)

    ids, embeddings = [], []
    for r in emb_rows:
        ids.append(int(r["record_id"]))
        embeddings.append(json.loads(r["embedding"]))

    emb_matrix = np.array(embeddings, dtype=np.float32)
    q = query_emb.reshape(1, -1).astype(np.float32)
    q_norm = q / (np.linalg.norm(q) + 1e-9)
    e_norm = emb_matrix / (np.linalg.norm(emb_matrix, axis=1, keepdims=True) + 1e-9)
    scores = (e_norm @ q_norm.T).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]
    ...
```
`src/databricks/rulebook.py` should reproduce this exact structure against new tables (e.g. `rulebook_chunks`, `rulebook_embeddings`) instead of `deficiency_kb`/`deficiency_embeddings`. Reuse `_run_sql`/`_table`/`_escape`/`_rows_from_result` from `src/databricks/delta.py` (lines 40-97) unchanged — including the **chunk-pagination discipline** (`_rows_from_result`, lines 80-97) whose docstring explicitly warns: *"Reading `data_array` alone silently truncates the result (e.g. 261 of 500 rows...)"* — a real, previously-hit bug in this exact codebase, directly relevant to pulling potentially-large rulebook tables.

**Two-backend dispatch (D-RB6's config switch) — the general pattern, already established twice in this repo** (`src/retrieval/vector_search.py:40-44` and `src/databricks/delta.py:104-107`):
```python
def embed_texts(texts, batch_size=8):
    s = get_settings()
    if s.is_databricks:
        return _embed_databricks(texts)
    ...

def create_job(job_id, document_name):
    s = get_settings()
    if s.is_databricks:
        _create_job_databricks(job_id, document_name)
        return
    ...
```
The rulebook-store interface (`read_guideline`, requirement-index enumerate, edge-table lookup) should dispatch on `get_settings().is_databricks` identically — the caller never branches, only the one dispatch function does.

---

#### `src/retrieval/lexical.py` (service, request-response)

**Analog:** `src/databricks/vector.py:26-60` (`_ensure_faiss`/`build_local_index`) — same "build a local index once, persist to disk, load lazily, query" shape, applied to `rank-bm25`'s `BM25Okapi` instead of FAISS. `rank-bm25` is not yet a dependency (`pyproject.toml:6-36` has no lexical-search entry) — add it per RESEARCH.md's Standard Stack (`uv add rank-bm25`, pins `>=0.2.2`).

#### `src/retrieval/hybrid.py` (utility, transform)

No analog — see No Analog Found. RESEARCH.md hands the complete formula: `score = Σ 1/(k+rank_i)`, k=60 (Reciprocal Rank Fusion), ~10 lines, no library.

---

### Cluster 6 — Eval Harness Extension

#### `src/evals/run.py` **(MODIFY)** — add `retrieval-gate` subcommand

**Analog:** the file's own existing subcommands (`src/evals/run.py:125-241`) — extend, don't invent a new CLI shape.

```python
# src/evals/run.py:137-149 — the "record, never crash" gate pattern to mirror
def cmd_gate(args: argparse.Namespace) -> int:
    eval_set = load_eval_set()
    report = load_captured(args.captured) if args.captured else golden_report(args.doc_id)
    baseline = json.loads(Path(args.baseline).read_text())
    baseline_ids = baseline_found_ids(eval_set, extra=set(baseline.get("found_set", [])))
    result = check_gate(report, eval_set, args.doc_id, baseline_ids)
    if result.ok:
        print("GATE OK")
        return 0
    print(f"GATE FAILED: lost {sorted(result.lost)}")
    return 1
```
```python
# src/evals/run.py:229-233 — subcommand registration to copy for `retrieval-gate`
gate_p = subparsers.add_parser("gate", help="Zero-true-positives-lost CI gate (LLM-free).")
gate_p.add_argument("--captured", default=None, help="Path to a captured FaultReport JSON.")
gate_p.add_argument("--doc-id", dest="doc_id", default=DEFAULT_DOC_ID)
gate_p.add_argument("--baseline", default=str(BASELINE_PATH))
gate_p.set_defaults(func=cmd_gate)
```
A new `retrieval_gate_p = subparsers.add_parser("retrieval-gate", ...)` with a `cmd_retrieval_gate` following the identical shape (load eval set → run `search_corpus` per non-held-out deficiency → compare against `src/evals/baseline/retrieval_recall.json` → exit 0/1) is a same-file, same-pattern addition.

---

#### `src/evals/metrics.py` **(MODIFY)** — upgrade `_retrieval_recall_at_k`

**This is the load-bearing finding of this cluster:** the function this task targets **already exists** and is **explicitly self-documented as a placeholder for this exact phase**:

```python
# src/evals/metrics.py:75-97 — read in full; the docstring is the instruction
def _retrieval_recall_at_k(report: FaultReport, eval_set: EvalSet, doc_id: str):
    """Phase-0 proxy for retrieval-stage coverage.

    The current detector sees the whole document in one shot -- there is no explicit top-k
    retrieval stage to measure yet, so this reports section/table-number OVERLAP between each
    GT deficiency's `section_hint` and everything the run cited (`table_ref`, `cited_section_
    indices`, `domains_checked`) as a coarse "was this part of the document surfaced at all"
    signal, independent of whether the exact finding was made. Upgrades to true corpus recall@k
    once an explicit retrieval/navigation stage exists (Phase 2).
    """
    doc_gts = [gt for gt in eval_set.deficiencies if gt.doc_id == doc_id and gt.section_hint.strip()]
    if not doc_gts:
        return "n/a_phase0"
    ...
```
Phase 2 should **replace this proxy's body** (keep the function name/call site in `compute_metrics`, or add a sibling `_search_corpus_recall_at_k`) with a real `search_corpus`-driven measurement, per RESEARCH.md's own SC4 design note: for each non-held-out `GroundTruthDeficiency`, run `search_corpus` with a query derived from `title`, check whether a top-k result's span overlaps `evidence_anchor` in the correct `doc_id`.

**Analog for the anchor-matching mechanics** — `src/evals/match.py:36-53,66-92` (verbatim substring-anchor matching, already does almost exactly this against `Fault.evidence` instead of a retrieval result):
```python
_TOKEN_RE = re.compile(r"[0-9][0-9.\/]{3,}")
_WORD_RE = re.compile(r"[a-z]{6,}")

def matches(fault: dict, gt: GroundTruthDeficiency) -> bool:
    """True iff every distinctive anchor token of `gt` appears verbatim in `fault["evidence"]`."""
    tokens = _anchor_tokens(gt.evidence_anchor)
    if not tokens:
        return False
    evidence_text = _norm(fault.get("evidence", ""))
    return all(tok in evidence_text for tok in tokens)
```
The exact-identifier HARD subset (D-SC4(i)) is naturally the same `_TOKEN_RE` (`[0-9][0-9.\/]{3,}`) already used to detect "distinctive numeric anchors" — reuse it to classify which `GroundTruthDeficiency` rows belong in the hard subset, rather than inventing a second numeric-token regex.

**Sentinel discipline to copy** — `src/evals/metrics.py:104-114` (`_anchor_rate`'s real-number-or-explicit-sentinel rule, never a silent zero):
```python
def _anchor_rate(report: FaultReport, source_text: str):
    """W1: this MUST be a real computed number whenever `source_text` is non-empty --
    never a permanent sentinel. Only falls back to `"n/a_no_source"` when the caller
    genuinely has nothing to check against."""
    if not source_text.strip():
        return "n/a_no_source"
```
Apply the same discipline to the new recall@k: a real fraction when the corpus/eval set support it, an explicit named sentinel (not a bare `0.0`) when they don't.

---

#### `src/evals/baseline/retrieval_recall.json` (data)

**Analog:** `src/evals/baseline/recall_by_family.json` (whole file, 18 lines) — mirror exactly:
```json
{
  "generated_from": "golden:mvr1381_run3",
  "overall": {"recall": 0.071, "precision": 0.074, "tp": 2, "fp": 25, "fn": 26},
  "recall_by_family": {"absence_of_evidence": 0.0, ...},
  "anchor_rate": 0.581,
  "found_set": ["C-01", "C-02"]
}
```
This is the shape D-SC4 explicitly says to copy ("RECORDS it as the committed retrieval baseline, same shape as `recall_by_family`"). Consumed the same way `src/evals/gate.py::baseline_found_ids` (lines 21-33) consumes the existing baseline — load, union into a protected set, never let a later run silently shrink it.

---

### Cluster 7 — Tests

**Analog for every `conftest.py`:** `tests/ingest/conftest.py` (167 lines, read in full) — the offline/no-network fixture discipline this whole suite is built on:
```python
# tests/ingest/conftest.py:35-44 — the "no Databricks/LLM creds reachable in CI" fixture
@pytest.fixture
def offline(monkeypatch):
    """Force the no-Databricks OCR fallback so tests are fast and deterministic."""
    from config import Settings
    import parse.ocr as ocrmod
    monkeypatch.setattr(ocrmod, "get_settings", lambda: Settings(databricks_host="", databricks_token=""))
```
`tests/tools/conftest.py` needs the equivalent for `src/tools/*` (a fake `RetrievalLedger`, a synthetic `CorpusIndex` + rulebook-store double — exactly what RESEARCH.md's Wave 0 Gaps names). `tests/rulebook/conftest.py` needs a tiny fixture eCFR XML snippet + fixture ICH/FDA PDF stub so `test_ecfr_parse.py`/`test_ich_ingest.py`/`test_fda_ingest.py` never touch the live internet (D-RB6 extended, per RESEARCH.md, to "tests never touch the live internet either, not just Databricks").

**Analog for the emit-gate fabrication-rejection test** — `tests/ingest/test_anchors.py` (whole file, 46 lines) is the exact test-writing pattern (mint → tamper → assert raises) `tests/tools/test_emit_finding.py` should follow, but returning a `ToolRejected` sentinel instead of raising:
```python
# tests/ingest/test_anchors.py:28-31
tampered = nt.model_copy(update={"canonical": nt.canonical[:start] + "X" * (end - start) + nt.canonical[end:]})
with pytest.raises(HashMismatch):
    open_span(span, tampered, doc_id)
```

**Analog for ground-truth-driven pass/fail tests** — `tests/evals/test_gate.py:44-58` (doctor a real fixture, strip the evidence that proves one deficiency, assert the specific loss is named):
```python
def test_doctored_report_missing_table20_evidence_loses_c01(self):
    original = golden_report()
    doctored_faults = [f for f in original.faults if "11477" not in f.evidence]
    doctored = original.model_copy(update={"faults": doctored_faults})
    g = check_gate(doctored, load_eval_set(), DOC_ID, BASELINE)
    assert g.ok is False
    assert g.lost == {"C-01"}
```
`tests/rulebook/test_requirement_index.py`'s ground-truth traceability test (D-RI1(2)) is the same shape inverted: for each of the 14 `absence_of_evidence` eval items, derive the submission profile, call enumerate mode, assert `>=1` entry fires — a `mvr1381` item with zero firing entries is the "loss" this test must name, mirroring how `check_gate` names exactly which id disappeared.

**Analog for required-keys assertions** — `tests/ingest/test_registry.py:35-37,49-52` (whole file is a good short template):
```python
def test_each_entry_has_required_keys():
    for entry in load_families():
        assert {"id", "label", "applicability_trigger"} <= set(entry), entry
```

---

## Shared Patterns

### 1. Span re-open/verify — `open_span` + `HashMismatch`
**Source:** `src/ingest/anchors.py:56-72` (function), `:29-43` (exception)
**Apply to:** `emit_finding.py` (both span halves), `get_section.py`, `open_doc.py`, `requirement_index.py`'s loader gate (provenance-span check), `src/rulebook/ecfr_parse.py`'s downstream flow (once serialized, spans are minted/opened identically to submission docs — RULES-01/02/03's core promise).
```python
def open_span(span: SpanID, nt: NormalizedText, doc_id: str) -> tuple[str, str]:
    if span.doc_id != doc_id:
        raise HashMismatch(span, span.doc_id, doc_id)
    canonical = nt.canonical[span.start:span.end]
    actual = short_hash(canonical, nt.normalizer_version)
    if actual != span.hash:
        raise HashMismatch(span, span.hash, actual)
    raw_s, raw_e = canon_range_to_raw(nt.offset_map, span.start, span.end)
    return nt.raw_serialized[raw_s:raw_e], canonical
```
**Never reimplement this.** Every "verify a quote is real" need in Phase 2 routes through it.

### 2. Two-backend dispatch on `Settings.is_databricks`
**Source:** `src/config.py:53-55` (the property) + `src/retrieval/vector_search.py:40-44` + `src/databricks/delta.py:104-107` (two independent existing call sites using the identical shape)
**Apply to:** `src/databricks/rulebook.py` / `src/rulebook/store.py`'s shared interface (D-RB6's config switch); NOT `search_corpus` (D-RB5 pins it local-always, no branch).
```python
@property
def is_databricks(self) -> bool:
    return self.environment == "databricks"
```
```python
def create_job(job_id: str, document_name: str) -> None:
    s = get_settings()
    if s.is_databricks:
        _create_job_databricks(job_id, document_name)
        return
    # ... local SQLite path
```

### 3. Typed self-correcting rejection — sentinel over exception
**Source:** `src/schemas/llm.py` (whole file, `ParseFailed`) — the chosen shape per RESEARCH.md's Pattern 3
**Apply to:** `src/tools/errors.py::ToolRejected`, `read_guideline`'s D-RI2(2) family-filter rejection, `follow_reference`'s cross-doc stub.
```python
class ParseFailed(BaseModel):
    layer: str
    reason: str
    raw_output: str
    validation_error: str = ""
    requires_human_review: bool = True
```

### 4. Never-abort batch loop — one bad item becomes a row, not a crash
**Source:** `src/ingest/corpus.py:132-135,172-175` (D-16)
**Apply to:** `src/rulebook/build.py` (one bad eCFR part/ICH PDF/FDA guidance never aborts the vendored-snapshot build); `src/evals/run.py::cmd_run`'s existing `parse_failures` dict (lines 186-187) is the same discipline already in the file the `retrieval-gate` subcommand extends.
```python
except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run (D-16)
    entries.append(DocEntry(doc_id=..., status="parse_failed", reason=str(exc)[:300]))
    continue
```

### 5. Atomic write — temp file + `os.replace`
**Source:** `src/ingest/store.py:46-57`
**Apply to:** `src/rulebook/store.py`'s local chunk persistence, `src/rulebook/build.py`'s manifest write.
```python
tmp = final.with_suffix(".tmp")
tmp.write_text(json.dumps(entry), encoding="utf-8")
os.replace(tmp, final)   # atomic rename: a crash before this leaves only .tmp, never a half .json
```

### 6. `lru_cache`-over-`yaml.safe_load` registry loader
**Source:** `src/ingest/registry/__init__.py:26-37`
**Apply to:** `src/rulebook/requirement_index.py`'s `requirement_index.yaml` loader; `rulebook/manifest.yaml`'s loader in `build.py`/`store.py`.
```python
@lru_cache(maxsize=1)
def load_families() -> list[dict]:
    with open(_FAMILIES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []
```

### 7. Offline/no-network test fixtures
**Source:** `tests/ingest/conftest.py:35-59`
**Apply to:** `tests/tools/conftest.py`, `tests/rulebook/conftest.py` — RESEARCH.md's own Wave 0 Gaps names this mirror explicitly.

### 8. Lazy PEP-562 package barrel (only if a real import cycle appears)
**Source:** `src/ingest/__init__.py` (whole file, 27 lines)
**Apply to:** `src/tools/__init__.py`, `src/rulebook/__init__.py` — watch for the same class of cycle that forced this in `ingest` (`src/tools/emit_finding.py` importing `ingest.anchors`, `src/rulebook/requirement_index.py` importing `ingest.registry` — if any of these end up imported FROM inside `ingest`/`agents.detection` transitively, use this lazy-`__getattr__` shape rather than a naive eager barrel).
```python
def __getattr__(name: str):
    if name in ("ingest_corpus", "CorpusIndex"):
        from ingest import corpus
        return getattr(corpus, name)
    raise AttributeError(f"module 'ingest' has no attribute {name!r}")
```

---

## No Analog Found

Files/logic with no close match in the codebase (planner should lean on RESEARCH.md's Code Examples instead):

| File / Logic | Role | Data Flow | Reason |
|---|---|---|---|
| `src/retrieval/hybrid.py` (RRF fusion) | utility | transform | No fusion logic exists anywhere in the repo today (only one retrieval path — FAISS-or-SQL-LIKE — existed pre-Phase-2). RESEARCH.md hands the complete formula (`score = Σ 1/(k+rank_i)`, k=60, ~10 lines) — implement directly from that, no library. |
| eCFR DIVn/HEAD/P XML-walking logic (inside `src/rulebook/ecfr_parse.py`) | utility | transform | The repo has zero XML parsing today (`ElementTree` is not currently imported anywhere in `src/`). The **output contract** has a strong analog (`extract_pdf`'s dict shape); the **input-side** tag-walking does not — RESEARCH.md's Code Examples (`fetch_ecfr_part`) covers the HTTP-fetch half only, not the tag-to-block mapping. |
| ICH copyright-notice-as-applied-constant (inside `build.py`'s ICH ingest path) | utility | transform | Novel domain concern (per-source-type constant metadata, deliberately NOT extracted from the PDF — Pitfall 4). No existing code attaches a fixed license string to a chunk; RESEARCH.md's Code Examples section already hands the complete `ICH_LEGAL_NOTICE` constant + `ich_chunk_metadata()` function verbatim — copy those directly rather than searching for an in-repo pattern. |

## Metadata

**Analog search scope:** `src/ingest/` (all 10 modules + registry), `src/retrieval/` (both existing files), `src/databricks/` (all 3 modules), `src/llm/` (both modules, read-only), `src/schemas/` (documents, llm, faults, flaws), `src/evals/` (run, metrics, match, gate, schema, capture, baseline data), `src/agents/detection/` (checklists, catalog, ctd, render — draft-material and rendering analogs only, never the off-limits redesign files), `tests/ingest/` (conftest + 3 representative test files), `tests/evals/test_gate.py`, `pyproject.toml`, `.gitignore`, `src/config.py`, `src/parse/pdf.py` (signature only).

**Files scanned (read in full or targeted-range):** 33 source files, 2 YAML data files, 2 JSON data files, 1 pyproject.toml, 1 .gitignore.

**Pattern extraction date:** 2026-07-31

---

## PATTERN MAPPING COMPLETE

**Phase:** 2 - retrieval-navigation-tools-rulebook
**Files classified:** 38

### Coverage
- Files with exact analog: 20
- Files with role-match / partial analog: 15
- Files with no analog: 3 (see No Analog Found — each has a RESEARCH.md-provided starting point instead)

### Key Patterns Identified
- Every grounding check in Phase 2 (emit_finding's both halves, get_section, requirement-index loader gate) routes through `src/ingest/anchors.py::open_span`/`HashMismatch` verbatim — never reimplemented.
- The Databricks-vs-local split is not new: `Settings.is_databricks` dispatch already exists at two independent call sites (`retrieval/vector_search.py`, `databricks/delta.py`); the rulebook store extends the same seam, and `databricks/vector.py::_search_embeddings_table` is a proven-working template for the rulebook's Databricks-side query path (Vector Search Admin API is 403-blocked).
- Two of this phase's most important pieces are **modifications to already-self-documenting placeholders**, not new files: `src/evals/metrics.py::_retrieval_recall_at_k`'s own docstring says "Upgrades to true corpus recall@k once an explicit retrieval/navigation stage exists (Phase 2)", and `src/evals/run.py` already has the exact `score`/`gate`/`run` subcommand shape a `retrieval-gate` subcommand should copy.
- The typed-rejection design choice is pre-resolved by RESEARCH.md: pick the `ParseFailed` sentinel shape (returned, not raised) over `HashMismatch`'s exception shape, because tool rejections must flow back to the calling model as a message.
- One explicit anti-pattern to avoid: `src/agents/detection/render.py::render_sections`'s char-budget behavior silently truncates with an "omitted for length" marker — TOOLS-04 forbids exactly this; reuse only its singular `render_section` (no truncation loop).

### File Created
`/Users/DEVDESAI1/dev/deficiency-chatbot/.planning/phases/02-retrieval-navigation-tools-rulebook/02-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files, organized by the same six requirement-clusters RESEARCH.md and this document both use.
