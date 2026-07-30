# Phase 1: Ingestion Foundation - Pattern Map

**Mapped:** 2026-07-30
**Files analyzed:** 28 (13 new `src/ingest/` modules · 2 registry data files · 1 schema extend · 3 migration-touch consumers · 1 eval-harness seam · 8 Wave-0 test artifacts)
**Analogs found:** 22 with a close analog / 28 total (6 genuinely-new flagged in "No Analog Found")

> **Authoritative file list** derived from RESEARCH §"Recommended Project Structure" (01-RESEARCH.md:216-234), §"Architectural Responsibility Map" (:100-113), §"Validation Architecture" Wave-0 gaps (:570-579), and §"Security Domain" planner action (:608). The task's starting map matched; two naming notes recorded below.
>
> **Naming/location notes for the planner:**
> - RESEARCH names the DOCX parser `src/ingest/docx_parse.py` (:104, :179, :223); the task prompt calls it `src/parse/docx.py`. Same role + same analog (`parse/pdf.py`) either way. Co-locating in `src/parse/docx.py` argues from symmetry with `parse/pdf.py`; RESEARCH's `ingest/` placement argues from the boundary law (parser emits raw text, geometry nulled). **Planner call** — this map treats them as one file, "the DOCX parser."
> - The task calls the registry `src/ingest/registry.*`. RESEARCH structures it as a `registry/` dir of two YAML data files (:229-231). A thin **`registry.py` loader** module is implied (nothing else loads the YAML + provides the D-05 `CTDSection` compat shim). This map lists loader + data separately.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/ingest/__main__.py` | CLI entry (controller) | request-response (argv→exit) | `src/evals/run.py` :213-247 | exact |
| `src/ingest/corpus.py` | orchestrator | batch (walk, per-file isolation) | `src/evals/run.py` :171-195 (`cmd_run`) | exact |
| `src/ingest/docx_parse.py` (aka `parse/docx.py`) | parser | file-I/O → transform | `src/parse/pdf.py` :197-258 (`extract_pdf`) | role-match |
| `src/ingest/serialize.py` | transform (utility) | transform (dict→text) | `src/parse/layout.py` :452-465 (`blocks_to_text`) | role-match |
| `src/ingest/normalize.py` | transform (utility) | transform (text→text+offset map) | **none** (offset map is new) | no-analog |
| `src/ingest/anchors.py` | primitive (utility) | request-response (span→raw+canonical / FAIL) | `src/schemas/llm.py` `ParseFailed` ethos + RESEARCH design | partial |
| `src/ingest/tables.py` | transform (utility) | transform (grid→`(id,r,c)` index) | `src/parse/pdf.py` :35-94 + `schemas/documents.py` :81-101 | partial |
| `src/ingest/classify.py` | classifier (service) | request-response + LLM escalation | `src/agents/detection/ctd.py` :12-31 + `llm/structured.py` :282-316 | role-match |
| `src/ingest/registry.py` | data loader (config) | CRUD-read (load registry) | `src/agents/detection/catalog.py` :11-63 | role-match |
| `src/ingest/store.py` | persistence (store) | CRUD / file-I/O (SQLite + cache) | `src/databricks/delta.py` :21-201 | role-match |
| `src/ingest/manifest.py` | model/schema | — (pydantic) | `src/schemas/documents.py` :41-119 + `schemas/llm.py` ParseFailed | role-match |
| `src/ingest/limits.py` | guard (middleware) | request-response (guard before parse) | **none** (only `ocr.py:88` timeout) | no-analog |
| `src/ingest/__init__.py` | package barrel | — (re-export) | any pkg `__init__` | trivial |
| `src/ingest/registry/ctd_families.yaml` | data | — | `catalog.py` `CANONICAL_DOMAINS` content | role-match |
| `src/ingest/registry/body_lexicon.yaml` | data | — | `checklists.py` `_VALIDATION_REQUIRED` :19-29 | role-match |
| `src/schemas/documents.py` (**extend**) | model/schema | — | self (extend in place) :55-113 | self |
| `src/agents/detection/checklists.py` (**touch**) | migration consumer | — | self :31-36, :183 (D-05 shim) | self |
| `src/agents/detection/pipeline.py` (**touch**) | migration consumer | — | self :16, :42 (D-05 shim) | self |
| `src/agents/detection/ctd.py` (**touch**) | migration consumer | — | self :12-31 (extend to doc-level) | self |
| `src/evals/run.py` (**touch**) | eval seam | — | self :174 (remove `format != "pdf"` skip) | self |
| `tests/ingest/conftest.py` | test fixtures | — | `tests/unit/test_section_splitter.py` :20-38 | role-match |
| `tests/ingest/test_normalize.py` | test (property) | — | **none** (property test is new) | no-analog |
| `tests/ingest/test_anchors.py` | test | — | `test_section_splitter.py` assertion style | partial |
| `tests/ingest/test_docx_parse.py` | test | — | `tests/unit/test_parse.py` :21-52 | role-match |
| `tests/ingest/test_tables.py` | test | — | `test_section_splitter.py` :33-38, :67-90 | role-match |
| `tests/ingest/test_corpus.py` | test | — | `tests/unit/test_parse.py` + `tmp_path` | partial |
| `tests/ingest/test_store.py` | test | — | **none** (sqlite roundtrip is new) | no-analog |
| merged-cell DOCX fixture (new asset) | test data | — | `src/evals/make_docx_fixture.py` :61-85 | exact |

---

## Pattern Assignments

Ordered by the RESEARCH-recommended build order (substrate spine first: normalize → anchors → serialize/tables → docx → classify → store → corpus/CLI). RISK-1 (`normalize.py` offset map) is built + property-tested **first** (RESEARCH:11, :572).

---

### `src/ingest/normalize.py` (transform, text→text+offset map) — **NO in-repo analog for the offset map**

**Analog:** none for the run-based offset map. NFC leg uses stdlib. Regex/const style mirrors `src/parse/layout.py`. Design reference = `tokenizers.NormalizedString` (installed transitively) per RESEARCH Pattern 4.

**Const/regex module style to mirror** (`src/parse/layout.py:33-61` — module-level named thresholds with a one-line rationale comment each):
```python
# --- running header/footer bands (share by both parse paths) -----------------
_HEADER_BAND = 0.12    # a block ending within the top this-fraction of the page is a header
```
Mirror this: put the ligature map, dehyphenation regex, and `NORMALIZER_VERSION` (D-24) as named module constants with rationale comments.

**Guarded dehyphenation (D-26)** — copy the verified ~15-line algorithm from RESEARCH:411-425 (`guarded_dehyphenate(text, is_plausible_word)`); it passes all four locked fixtures. The lexicon (`is_plausible_word`) unions a stdlib wordlist with `catalog.py`'s domain terms (RESEARCH:422-424).

**NFC + ligature finding the executor MUST encode** (RESEARCH Pitfall 1, :354-358): `unicodedata.normalize("NFC", s)` does **not** fold `ﬁ`; ligature fold is a **separate explicit op** `{ﬁ:fi, ﬂ:fl, ﬀ:ff, ﬃ:ffi, ﬄ:ffl}`. Never NFKC (corrupts `µ`/`²`). Op order: NFC → whitespace-collapse → guarded-dehyphenate → ligature map.

**Offset-map mechanism** — build the run-based map from RESEARCH:296-310 (`canon_range_to_raw`, `bisect` over run starts, O(log n)). Each run = `(canon_start, canon_len, raw_start, raw_len, kind)`.

**Signature to expose:** a `NormalizedText` value object carrying `canonical: str`, `raw_serialized: str`, `offset_map`, `normalizer_version: str`. Gate it with the round-trip property test (`test_normalize.py`) **before any consumer imports it** (RISK-1, RESEARCH:11).

---

### `src/ingest/anchors.py` (primitive, span→raw+canonical) — mostly new; partial analog for the failure ethos

**Analog (design):** RESEARCH:456-471 (`SpanID` frozen dataclass + `open_span`). **Analog (failure ethos):** `src/schemas/llm.py` `ParseFailed` — typed sentinel over silent corruption; here the parallel is a typed `HashMismatch` raise, never a silent wrong-substring return.

**Contract to implement verbatim (D-21):** given a span-ID return **BOTH** raw + canonical, or **FAIL** on hash mismatch:
```python
@dataclass(frozen=True)
class SpanID:
    doc_id: str; start: int; end: int; hash: str   # offsets over CANONICAL stream (D-19)

def open_span(span: SpanID, doc) -> tuple[str, str]:
    canonical = doc.canonical_text[span.start:span.end]
    if short_hash(canonical, doc.normalizer_version) != span.hash:
        raise HashMismatch(span, expected=span.hash)      # FAIL (D-21) — tamper/version drift
    raw_s, raw_e = canon_range_to_raw(doc.offset_map, span.start, span.end)
    return doc.raw_serialized_text[raw_s:raw_e], canonical   # BOTH, never one (D-21)
```

**Convention to replicate:** hashing = stdlib `hashlib` (blake2b/sha256), hash over the **canonical** substring + `normalizer_version` (RESEARCH Open Question 1, :500-503; low-risk planner call under D-15). No in-repo content-hash analog exists — `databricks/delta.py` uses none. Geometry (`bbox`/`page`) must **never** enter `SpanID` (D-19 boundary law, RESEARCH:113).

---

### `src/ingest/serialize.py` (transform, document dict → raw serialized reading-order text)

**Analog:** `src/parse/layout.py:452-465` (`blocks_to_text`) — the canonical "flatten blocks + tables into reading-order text" function; and `src/agents/detection/checklists.py:48-63` (`_reading_order_text`) — the same join incl. table cells.

**Core pattern to mirror** (`layout.py:452-465`) — reading-order concatenation with table cells serialized in (this is exactly D-31's "cells serialized INTO the stream"):
```python
def blocks_to_text(blocks: list[LayoutBlock], tables: list[ExtractedTable]) -> str:
    parts: list[str] = [b.text for b in blocks if b.text]
    for t in tables:
        if t.title:
            parts.append(t.title)
        if t.kind == "key_value":
            parts.extend(f"{p.label}: {p.value}".strip(": ").strip() for p in t.pairs)
        else:
            if t.headers:
                parts.append("\t".join(t.headers).rstrip())
            for row in t.rows:
                parts.append("\t".join(row).rstrip())
    return "\n".join(p for p in parts if p)
```

**Signature/convention the executor MUST add over the analog:** the analog throws the text away; `serialize.py` must instead emit `(raw_serialized_text, per_cell_char_ranges)` so `tables.py` can key `(table_id,row,col)` at the cell's serialized char-range (D-31). Serialization order MUST be **deterministic + version-stamped** (`SERIALIZER_VERSION`, D-31 / RESEARCH:387). For DOCX, order comes from `body.iterchildren()` (RESEARCH Pattern 2, :254-266), NOT `.paragraphs`/`.tables` (loses interleaving).

---

### `src/ingest/tables.py` (transform, grid → `(table_id,row,col)`→span-ID index) — partial analog

**Analog:** `src/parse/pdf.py:35-94` (`extract_tables` / `ExtractedTable` construction) and `src/schemas/documents.py:81-101` (`ExtractedTable`/`TablePair` field shape). Merged-cell dedup is new (python-docx `_tc` identity, RESEARCH Pattern 3).

**Merged-cell dedup (D-31, INGEST-05)** — copy RESEARCH:278-289 (`cell_spans` / `_tc`-origin). Every `(r,c)` a merge spans resolves to the **origin** cell's single span-ID:
```python
def cell_spans(table):
    origin, coord_to_origin = {}, {}
    for r, row in enumerate(table.rows):
        for c, cell in enumerate(row.cells):
            k = id(cell._tc)                     # merged cells share one _tc (H + V merges)
            if k not in origin:
                origin[k] = (r, c)               # first appearance = origin (row-major)
            coord_to_origin[(r, c)] = origin[k]
    return coord_to_origin
```

**PDF-path caveat the executor MUST honor** (RESEARCH Pitfall 4, :372-376): PyMuPDF `find_tables().extract()` fills spanned cells with `""` and gives **no merge metadata** — mark PDF merged-cell resolution **best-effort/unverified** in the manifest (D-30 table tier); do not claim addressability you can't back. DOCX complex-merge → wrap in try/except → typed `ParseFailed` + `parsed_partial` (RESEARCH Pitfall 5, :378-381).

---

### `src/ingest/docx_parse.py` / `src/parse/docx.py` (parser, DOCX → same document dict)

**Analog:** `src/parse/pdf.py:197-258` (`extract_pdf`) — **the exact dict shape to converge on**; `src/evals/make_docx_fixture.py:61-85` shows the python-docx write-side API (`Document()`, `add_table`, `table.rows[r].cells`, `cell.text`).

**Return shape to match byte-for-byte** (`pdf.py:238-258`) — same keys, geometry nulled per D-20:
```python
return {"filename": path.name, "page_count": page_count, "toc": toc, "pages": pages}
# each page: {page_number, page_label, width, height, rotation, source, is_scanned,
#             blocks:[LayoutBlock.model_dump()], tables:[ExtractedTable.model_dump()], figures:[...]}
```
DOCX fills `page_number=None`, `bbox=None`, `page=None` (D-20 — **never synthetic**). Copy the `extract_docx` skeleton + `iter_block_items` from RESEARCH:428-451 and :254-266.

**Convergence guarantee:** `section_splitter.split_document` (`section_splitter.py:196-251`) must consume the DOCX dict **unchanged**. Its sort key `body_blocks.sort(key=lambda b: (b["page"], b["reading_order"]))` (:206) breaks on `page=None` — the executor adds a one-line guard to sort by `reading_order` alone when `page` is `None` (RESEARCH:450). This is the concrete INGEST-02 / SC2 "identical model" deliverable.

**python-docx write API to reuse in fixtures** (`make_docx_fixture.py:68-78`):
```python
table = document.add_table(rows=1, cols=len(_TABLE_HEADER))
for label, result, limit in _TABLE_ROWS:
    row_cells = table.add_row().cells
    for cell, value in zip(row_cells, (label, result, limit)):
        cell.text = value
```

---

### `src/ingest/classify.py` (classifier, deterministic-first + LLM escalation)

**Analog:** `src/agents/detection/ctd.py:12-31` (`detect_ctd_section`) — the deterministic regex seam to extend from section-level to document-level; `src/llm/structured.py:282-316` (`structured_call`) — the escalation call, reused **verbatim** (D-07, RESEARCH "Don't Hand-Roll" :330); `src/agents/detection/catalog.py:11-63` — the registry + `domain_catalog_text()` "feed the catalog into the LLM prompt" pattern; `src/agents/detection/pipeline.py:29-34` (`_leading_text`) — the first-N-lines signal for D-28.

**Deterministic tier to extend** (`ctd.py:12-31`) — the regex-list → first-match shape, generalized to read the registry lexicon instead of a hardcoded enum:
```python
_CTD_PATTERNS: list[tuple[re.Pattern, CTDSection]] = [
    (re.compile(r"3\.2\.\s*S\.4\.1\b", re.IGNORECASE), CTDSection.S_4_1_SPECIFICATION), ...]
def detect_ctd_section(text: str) -> CTDSection:
    for pattern, section in _CTD_PATTERNS:
        if pattern.search(text):
            return section
    return CTDSection.UNKNOWN
```

**LLM escalation to call (do NOT reinvent)** — `structured.py:282-316`. Define a pydantic result model (`{label, family, confidence}`), then:
```python
instance, failure = structured_call(messages, ClassifyResult, model=cheap_model)
# instance XOR failure — never a raw text leak (structured.py:292)
```

**First-N-lines signal for D-28** (`pipeline.py:29-34`) — mirror `_leading_text(doc, pages=3)`; RESEARCH:505-508 recommends first ~15 non-empty serialized lines or ~1000 chars.

**Signatures/conventions the executor MUST add (D-27/D-29):** emit per document `{label, family_guess, confidence, tier ∈ {regex,lexicon,llm}, triggering_span_id}`. The **tier** and **triggering span-ID** are load-bearing (three incomparable confidence scales); the run summary reports the escalation rate per tier via `structlog` (D-27, RESEARCH:144). LLM tier degrades to deterministic-only when no Databricks creds (mirror `ocr.py:78` no-creds skip).

---

### `src/ingest/registry.py` + `registry/*.yaml` (data loader + data, D-05/D-06)

**Analog:** `src/agents/detection/catalog.py:11-63` — the `dict`-of-`{id: description}` registry + a `normalize_type` alias map + a `domain_catalog_text()` renderer is the **exact target shape** (RESEARCH Runtime State :348 "already registry-shaped — align, don't duplicate"). `src/schemas/documents.py:8-35` `CTDSection` is the enum being migrated **out**.

**Registry entry shape (D-05, RULES-05-aligned):** `{id, label, applicability_trigger}` + per-family keyword lexicon (D-06). The `catalog.py` `CANONICAL_DOMAINS` descriptions are the model for the one-line `applicability_trigger`:
```python
CANONICAL_DOMAINS: dict[str, str] = {
    "specification": "Incomplete specifications, missing acceptance criteria, CoA discrepancies, ...",
    "method-validation": "Analytical method not validated; missing ICH Q2 parameters ...", ...}
def domain_catalog_text() -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in CANONICAL_DOMAINS.items())
```

**Migration-safety convention the executor MUST replicate** (RESEARCH:340-350): keep the registry `id`s equal to the existing `CTDSection` **values** (`"3.2.S.4.1"`, StrEnum) so downstream set-membership keeps matching. `body_lexicon.yaml` mirrors the `checklists.py:19-29` `_VALIDATION_REQUIRED` keyword-list shape.

---

### `src/ingest/store.py` (persistence, content-hash cache + SQLite index + manifest)

**Analog:** `src/databricks/delta.py:21-201` — SQLite connection + row factory + the SQLite/Databricks auto-dispatch + JSON-column serialization. Content-hash keying + atomic write are new (RESEARCH Pitfall 6).

**SQLite conn + JSON-column pattern to mirror** (`delta.py:21-25`, `:133-141`, `:155-157`):
```python
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH); conn.row_factory = sqlite3.Row
    return conn
# write JSON columns:
vals.append(json.dumps(extra[key]) if extra[key] is not None else None)
# read them back:
for json_col in ("intermediate_report", "flaw_report", "recommendations"):
    if result.get(json_col): result[json_col] = json.loads(result[json_col])
```

**Signatures/conventions the executor MUST add (D-14/D-24/D-32, RESEARCH Pitfall 6 :384-388):**
- Cache key = `content_hash(file_bytes)` **+ `normalizer_version` + `serializer_version`** — a version bump invalidates cleanly (the D-24 migration path).
- Store the **FULL canonical text** on disk (D-32), not just outline+metadata.
- Atomic write (temp file → rename) so a mid-write crash leaves no half-entry; on resume, skip files whose (hash, versions) tuple is present. Follow `delta.py` SQLite conventions for the index metadata (D-15, RESEARCH:154).

---

### `src/ingest/manifest.py` (model/schema, coverage manifest — INGEST-03/D-30)

**Analog:** `src/schemas/documents.py:41-119` pydantic-v2 model style (`BaseModel` + `Field(default_factory=...)` + docstring-per-model); `src/schemas/llm.py` `ParseFailed` — the typed-status-with-reason sentinel that `parsed_partial` mirrors (D-17 "isPartialView").

**Model style to mirror** (`documents.py:87-101` — defaults + `Field(default_factory=list)` + inline field comments):
```python
class ExtractedTable(BaseModel):
    title: str = ""
    headers: list[str] = Field(default_factory=list)
    kind: str = "grid"                                    # "grid" | "key_value"
    ...
```

**New vocabulary the executor defines (D-16/D-30):** status ∈ `{parsed, parsed_partial, parse_failed, unsupported}` each with a `reason`; availability tiers declared up front: `structure ∈ {outlined, flat}`, `tables ∈ {addressable, unavailable}`. `parsed_partial` records **what degraded** (mirror `ParseFailed`'s `reason`/`validation_error` split). Downstream reads capability **from the manifest**, never at runtime (D-30).

---

### `src/ingest/corpus.py` (orchestrator, walk + dispatch + never-crash batch)

**Analog:** `src/evals/run.py:171-195` (`cmd_run`) — **the exact "record parse_failure, skip, never crash" loop D-16 mandates**; `src/agents/orchestrator.py:17-47` (`run_pipeline`) — the parse→process sequence shape to **parallel but leave untouched** (D-13).

**Never-crash batch pattern to copy verbatim** (`run.py:171-195`):
```python
parse_failures: dict[str, str] = {}
for doc in eval_set.documents:
    if doc.format != "pdf":
        parse_failures[doc.doc_id] = f"no parse path for format={doc.format!r} ..."
        continue
    try:
        parsed = extract_pdf(doc.path)
        ...
    except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run
        parse_failures[doc.doc_id] = str(exc)
        continue
```
Adapt: iterate `os.walk`/`Path.rglob` (uncapped depth), dispatch `.pdf`→`extract_pdf` / `.docx`→docx parser, content-hash each file, unsupported ext → `unsupported` manifest row (not crash). Call `limits.py` guards **before** the heavy parse (RESEARCH:608).

**Convention the executor MUST honor (D-09):** filename/folder path is **excluded** from classification — enforced by construction (never pass the path to `classify.py`). This is what the SC1 rename-folders test verifies.

---

### `src/ingest/__main__.py` (CLI shell, `python -m ingest <dir>`)

**Analog:** `src/evals/run.py:213-247` — **exact** argparse-shell pattern (`build_parser` → `main(argv)` → `raise SystemExit(main())`).

**Skeleton to copy** (`run.py:213-247`):
```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ingest", description="...")
    ...
    return parser
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
if __name__ == "__main__":
    raise SystemExit(main())
```
**Convention (D-11):** the CLI is a **thin shell** — it only parses argv and calls the pure `ingest_corpus(root) -> CorpusIndex` library (exported from `__init__.py`). All logic lives in the library; evals/Phase-2 import it, not the CLI.

---

### `src/schemas/documents.py` (**EXTEND** — add canonical-text/offset/span layer)

**Analog:** self — extend the existing pydantic models in place (:41-113). Do **not** rewrite.

**Changes the executor makes (D-19/D-20/D-05):**
- Add canonical-text/offset/span fields (new models: `SpanID`, `NormalizedText`/canonical-text carrier, per-doc `offset_map` + `normalizer_version`/`serializer_version` stamps).
- Make geometry **optional** per D-20: `bbox`/`page` currently default to non-null tuples/ints (`LayoutBlock.bbox: Bbox = (0.0,0.0,0.0,0.0)`, `page: int = 0`, :64-65) — DOCX needs these `None`, so widen to `Bbox | None` / `int | None` (RESEARCH Discretion :94: offsets are identity, geometry optional provenance).
- `CTDSection` (:8-35) becomes registry-backed but **keep the StrEnum values as registry ids** (migration shim, D-05).

---

### D-05 migration-touch consumers (read-compat, do not renumber)

**`src/agents/detection/checklists.py`** — `_VALIDATION_SECTIONS` set + `run_checklists(doc, ctd)` (:31-36, :181-188) does `ctd in _VALIDATION_SECTIONS`. Keep working by reusing the CTD citation strings as registry ids.
**`src/agents/detection/pipeline.py`** — imports + calls `detect_ctd_section` / `describe_document` (:16, :42). Point at the registry-backed classifier; signature unchanged.
**`src/agents/detection/ctd.py`** — the seam being extended to doc-level (D-07). Keep `detect_ctd_section(text) -> CTDSection` callable for the shim; add the doc-level entry beside it.
**Convention (RESEARCH:350):** "This is a code edit, not a data migration (no stored enum values on disk yet). Do not renumber."

---

### `src/evals/run.py` (**touch** — remove the DOCX skip)

**Analog:** self :174. Wave-0 gap (RESEARCH:579): remove/replace the `if doc.format != "pdf": ... continue` skip so `mini_spec.docx` gets a live parse path via the new DOCX parser; SC4 gate then shows it no longer a `parse_failure`. This is eval-harness wiring, **not** the `upload.py`/`orchestrator.py` rewire that D-13 forbids.

---

### Wave-0 tests (`tests/ingest/`)

**`conftest.py`** — Analog: `tests/unit/test_section_splitter.py:20-38`. Copy the `offline` OCR monkeypatch and the inline `_block()`/`_grid()` builders; add a merged-cell DOCX builder (extend `make_docx_fixture.py` style) + a synthetic document-dict factory. **No `conftest.py` exists yet** (RESEARCH:544).
```python
@pytest.fixture
def offline(monkeypatch):
    from config import Settings
    import parse.ocr as ocrmod
    monkeypatch.setattr(ocrmod, "get_settings",
                        lambda: Settings(databricks_host="", databricks_token=""))
def _grid(page, y0, y1, headers, rows, title=""):
    return {"kind": "grid", "title": title, "headers": headers, "rows": rows, "pairs": [], ...}
```

**`test_docx_parse.py`** — Analog: `tests/unit/test_parse.py:21-52` (`TestSpecPDF` key/shape assertions), but use the **committed** `mini_spec.docx` + merged-cell fixture (endpoint-free), NOT `skip_if_no_samples`. Assert the dict keys match `pdf.py`'s and the 5×3 impurities table reconstructs.

**`test_tables.py`** — Analog: `test_section_splitter.py:33-38, :67-90` `_grid` builders + resolution assertions. Assert every merged `(r,c)`→one span-ID (D-31) and same-doc-twice→identical `(id,r,c)→span` map (determinism).

**`test_normalize.py`** — **No analog** (new): offset round-trip **property** test (RISK-1 gate, write FIRST) + the four locked dehyphenation fixtures + NFC/ligature/unit invariants.

**`test_anchors.py`** — partial analog (assertion style): re-open byte-exactness + tampered-stream/wrong-version → `HashMismatch`.

**`test_corpus.py`** — partial analog (`test_parse.py` + `tmp_path`): rename-folders invariant (SC1), uncapped walk + unsupported row, one-bad-file-never-aborts (D-16).

**`test_store.py`** — **No analog** (new): manifest availability tiers (D-30), cache resume + normalizer-version invalidation (D-14/D-24).

---

## Shared Patterns

### Never-crash batch (D-16)
**Source:** `src/evals/run.py:171-195` (`cmd_run` per-item `try/except` + `parse_failures: dict`)
**Apply to:** `corpus.py` (top-level loop), and every per-file/per-table sub-step that can raise.
```python
try:
    parsed = extract_pdf(doc.path); ...
except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run
    parse_failures[doc.doc_id] = str(exc); continue
```

### Typed sentinel over silent corruption (D-17 / "isPartialView")
**Source:** `src/schemas/llm.py` `ParseFailed` (`layer/reason/raw_output/validation_error/requires_human_review`) + `structured.py:315` "sentinel — bubble up structured failure, never raw text"
**Apply to:** `manifest.py` statuses (`parsed_partial` records **what** degraded), `tables.py`/`docx_parse.py` complex-merge → typed `ParseFailed` not a corrupt table.

### Structured LLM output (do NOT reinvent — D-07)
**Source:** `src/llm/structured.py:282-316` (`structured_call`) → returns `instance XOR ParseFailed`
**Apply to:** `classify.py` escalation tier only. Reuse verbatim.
```python
instance, failure = structured_call(messages, ClassifyResult, model=cheap_model)
```

### SQLite auto-dispatch store
**Source:** `src/databricks/delta.py:21-25` (conn+`row_factory`), `:133-141`/`:155-157` (JSON columns), `:104-108` (`if s.is_databricks:` dispatch)
**Apply to:** `store.py` corpus index + manifest rows.

### Reading-order text join (incl. table cells)
**Source:** `src/parse/layout.py:452-465` (`blocks_to_text`) + `src/agents/detection/checklists.py:48-63` (`_reading_order_text`)
**Apply to:** `serialize.py` (D-31 cells-serialized-in) — but retain per-cell char ranges the analogs discard.

### No-creds / offline degradation
**Source:** `src/parse/ocr.py:71-79` (empty `databricks_host`/`token` → skip, return `None`); `src/config.py:6-16,86-88` (`Settings` + `get_settings` `lru_cache`); test hook `test_section_splitter.py:20-27`
**Apply to:** `classify.py` (LLM tier → deterministic-only when no creds), all `tests/ingest/` (reuse the `offline` fixture).

### Deterministic-first, LLM-as-escalation (project-wide ethos)
**Source:** `src/agents/detection/pipeline.py:50-83` (oracles/checklists before specialists); `ctd.py`→`structured.py`
**Apply to:** `classify.py` (regex→lexicon→LLM), and the D-27 per-tier escalation-rate metric via `structlog`.

---

## No Analog Found

Files with no close in-repo match — planner/executor should use RESEARCH patterns (cited) instead of hunting for a codebase analog.

| File | Role | Data Flow | Reason / Use Instead |
|------|------|-----------|----------------------|
| `src/ingest/normalize.py` (offset map) | transform | text→text+map | No offset-tracking code exists in `src/`. Use RESEARCH Pattern 4 run-based map (:291-310) + `tokenizers.NormalizedString` (installed) as the reference for the NFC leg. NFC leg = stdlib `unicodedata`. |
| `src/ingest/anchors.py` (content-hash + re-open) | primitive | request-response | No content-hash / re-open primitive in repo (`delta.py` uses no hashing). Use RESEARCH:456-471 design + stdlib `hashlib`. Failure ethos borrows `schemas/llm.py` ParseFailed only. |
| `src/ingest/limits.py` (byte/page/entry/time caps) | guard | request-response | **No size/cap/zip-bomb/timeout guard anywhere in `src/parse/`** (only `ocr.py:88 timeout=60.0`). Genuinely new security module — build from RESEARCH §"Security Domain" (:581-608): zip-bomb guard via `zipfile`, per-file byte ceiling, page/entry caps, path-traversal-safe walk. |
| `src/ingest/tables.py` (`(id,r,c)` index) | transform | transform | Cell **addressing** is new; only the `ExtractedTable` *shape* (`pdf.py`/`schemas`) is analogous. Merged-cell dedup = RESEARCH Pattern 3 `_tc` identity. |
| `tests/ingest/test_normalize.py` (property test) | test | — | No property-based test exists in the suite. New: offset round-trip property test (RISK-1). |
| `tests/ingest/test_store.py` (sqlite roundtrip) | test | — | No store-layer unit test exists (`delta.py` untested in `tests/`). New: cache resume/invalidate + manifest tiers. |

---

## Metadata

**Analog search scope:** `src/parse/` (pdf, layout, ocr, section_splitter), `src/schemas/` (documents, llm), `src/evals/` (run, make_docx_fixture), `src/agents/` (orchestrator, detection/{ctd,catalog,checklists,pipeline}), `src/llm/` (structured, client), `src/databricks/delta.py`, `src/config.py`, `tests/unit/` (test_parse, test_section_splitter).
**Files scanned:** 18 source + 2 test analogs read in full (all ≤ 465 lines, single-pass each); greenfield status of `src/ingest/` and absence of substrate symbols verified by grep.
**Project skills:** none found (`.claude/skills/`, `.agents/skills/` absent).
**Pattern extraction date:** 2026-07-30
