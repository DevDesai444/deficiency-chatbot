# Phase 3: Drive-Loop Spike (GO/NO-GO) - Pattern Map

**Mapped:** 2026-08-01
**Repo HEAD:** `9b68856` (branch `CLI_for_folders`)
**Files analyzed:** 40 (8 new source, 13 modified source, 14 new test, 4 modified test, 1 optional CI)
**Analogs found:** 37 / 40 (exact 21, role-match 16, none 3)

**The one-sentence version:** the six Phase-2 tools in `src/tools/` are this phase's dominant
analog — every new file that touches the model boundary copies their shape (typed sentinel
returns, constructor-injected ledger, span-IDs rendered as `[doc:start:end]`, self-correcting
`hint`), and the three genuinely new things (a JSONL telemetry writer, a git-SHA provenance
capture, and a scripted-LLM test double) have **no analog in this repo at all** and are listed
explicitly in § No Analog Found so the planner does not go looking.

---

## File Classification

### New source files — `src/agents/review/` (the module path `.planning/research/ARCHITECTURE.md` already names)

| New file | Role | Data flow | Closest analog | Match |
|----------|------|-----------|----------------|-------|
| `src/agents/review/__init__.py` | barrel + public entry `run_review()` | request-response | `src/agents/detection/__init__.py` (barrel) + `src/agents/detection/pipeline.py::run_detection` (entry shape) | exact |
| `src/agents/review/loop.py` | orchestrator / turn loop | event-driven (turn loop) | `src/llm/client.py:96-128` (bounded loop, typed exits, never a partial-state return) + `pipeline.py:37-102` (timed entry → report) | role-match |
| `src/agents/review/budget.py` | service / per-run accumulator | event-driven accumulation | `src/tools/ledger.py::RetrievalLedger` | **exact** |
| `src/agents/review/registry.py` | registry / schema-derivation + dispatch | transform + request-response | `src/llm/structured.py:30-87` (derive) + `src/agents/detection/oracles.py:218-228` (battery + per-item guard) | role-match |
| `src/agents/review/spanref.py` | utility / parser | transform | `src/tools/get_section.py:26-48` (the exact inverse: mint→render) + `src/ingest/anchors.py:46-72` | **exact (inverse)** |
| `src/agents/review/telemetry.py` | service / writer | streaming file-I/O (append) | `src/ingest/store.py:46-57` (atomic write) + `src/evals/run.py:128-131` (summary JSON) | partial — **no JSONL writer exists in this repo** |
| `src/agents/review/oracles_tool.py` | **tool (the 7th)** | request-response | `src/tools/open_doc.py:14-36` (closest sibling shape) + `src/agents/detection/oracles.py:221-228` (the battery it wraps) | **exact** |
| `src/agents/review/prompts.py` | config / constants | n/a | `src/agents/detection/prompts.py` — **copy the module-constant shape, REJECT its `{}`/`.format()` templating** | exact w/ inversion |

### Modified source files

| File | Role | Change | Analog for the change | Match |
|------|------|--------|----------------------|-------|
| `src/tools/errors.py` | model (pydantic) | + `KNOWN_REASON_CODES`, + `half` field (D-TEL2/D-TEL3, additive only) | the file's own `preview`/`handle` additive precedent at `:23-28` | **exact (self)** |
| `src/tools/emit_finding.py` | tool / gate | + `half=` at all 7 rejection sites; + structured verdict/rule_span | its own 7 rejection sites `:52-92` | **exact (self)** |
| `src/tools/__init__.py` | barrel | export `run_oracles`-the-tool | the file itself `:9-12` | exact |
| `src/schemas/faults.py` | model | + `ComplianceVerdict` StrEnum, + `verdict`, + `rule_span_id`; + `stop_reason`/`budget_exhausted` on `FaultReport` | its own `EvidenceClass`/`Tier` StrEnums `:20-35`, all-defaulted field style `:41-62` | **exact (self)** |
| `src/schemas/events.py` | model | + `EventType` members, + `"review"` LayerName | the closed `Literal` at `:7-19` | exact (self) |
| `src/llm/client.py` | client / transport | + `ChatTurn`, + `chat_completion_tools()` **alongside** `chat_completion_full` | `chat_completion` / `chat_completion_full` sibling pair `:58-130` | **exact (self)** |
| `src/llm/structured.py` | service | + `_inline_refs`, + `tool_schema_for_databricks`, + `build_tool_schema` **beside** the existing three | `schema_for_databricks`/`_sanitize`/`build_response_format` `:30-87` | **exact (self)** |
| `src/evals/run.py` | CLI / harness | + `agent-run` subcommand | `cmd_run` `:240-302` + `build_parser` `:305-335` | **exact (self)** |
| `src/evals/__init__.py` | config | + `HARNESS_VERSION` / `MATCHER_VERSION` (**file is currently 0 bytes**) | `src/ingest/normalize.py:35-36`, `src/ingest/serialize.py:22`, `src/rulebook/requirement_index.py:42` | exact |
| `src/parse/pdf.py` | parser | P2 2-line fix + `PARSER_VERSION` | the sibling `else:` branch at `:234-237` is literally the code to copy | **exact (self)** |
| `src/ingest/store.py` | store | `cache_key()` folds `PARSER_VERSION` | `cache_key` `:35-39` already folds two versions | **exact (self)** |
| `src/config.py` | config | + `detection_mode: Literal["legacy","agent"]` | `Settings` field block `:43-51`; `DETECTOR_MODELS` allow-list `:93-105` | exact |
| `pyproject.toml` | config | remove `autogen-*` pins (hygiene) | n/a | n/a |

### New test files — `tests/agents/review/` (Wave 0)

| New test | Role | Data flow | Closest analog | Match |
|----------|------|-----------|----------------|-------|
| `tests/agents/review/__init__.py` | test scaffold | n/a | `tests/tools/__init__.py` (empty file) | exact |
| `tests/agents/review/conftest.py` | test fixtures | n/a | `tests/tools/conftest.py` (structure + `build_corpus_index` re-export) + `tests/ingest/conftest.py:35-59` (offline monkeypatch fixtures) | **exact** |
| `test_loop_basic.py` | unit | request-response | `tests/tools/test_contracts.py` | role-match |
| `test_tool_schemas.py` | unit | transform | `tests/unit/test_schemas.py` + `structured.py:43-73` behavior | role-match |
| `test_message_history.py` | unit | request-response | `tests/tools/test_contracts.py` | role-match |
| `test_loop_budget.py` | unit | event-driven | `tests/tools/test_read_dedup.py` (ledger-state assertions) | role-match |
| `test_runaway.py` | **integration (offline)** | event-driven | `tests/tools/test_enumerate_fetch_emit_e2e.py` (real primitives, no fakes) | **exact** |
| `test_continuation_floor.py` | unit | event-driven | `tests/tools/test_read_dedup.py` | role-match |
| `test_spanref_roundtrip.py` | **composition** | transform | `tests/tools/test_enumerate_fetch_emit_e2e.py` + `tests/tools/test_contracts.py:81-97` | **exact** |
| `test_prefix_stability.py` | unit (offline) | transform | none — hash-equality assertion is new | role-match |
| `test_verify_nondropping.py` | unit | batch | `tests/unit/test_detection.py` | role-match |
| `test_telemetry.py` | unit | file-I/O | `tests/ingest/test_store.py:16-39` (tmp_path write→read→assert) | **exact** |
| `test_repair_accounting.py` | unit | transform | `tests/tools/test_contracts.py` | role-match |
| `test_oracles_tool.py` | unit | request-response | `tests/tools/test_contracts.py:100-109` (ledger-issuance assertion) | **exact** |

### Modified test files

| File | Change | Analog inside the same file | Match |
|------|--------|----------------------------|-------|
| `tests/tools/test_emit_finding.py` | + `half` assertion at all 7 sites | `:52-83` and `:89-110` (one rejection, one honestly-named test) | **exact (self)** |
| `tests/tools/test_contracts.py` | + `KNOWN_REASON_CODES` coverage | `:51-62` reason-code assertions | **exact (self)** |
| `tests/unit/test_parse.py` | + P2 fallback-blocks test | **NOT this file's shape** — it is sample-PDF-gated (`:8-18`). Use `tests/ingest/conftest.py:122-144`'s `fitz`-built synthetic PDF instead | inverted |
| `tests/ingest/test_store.py` | + `PARSER_VERSION` in `cache_key` | `:16-39` `test_cache_resume_and_invalidate` — the bump→different-key→MISS assertion already exists for the normalizer | **exact (self)** |

---

## Pattern Assignments

### CLUSTER A — The 7th tool: `src/agents/review/oracles_tool.py` (tool, request-response)

**Analog: all six Phase-2 tools. `run_oracles` must be structurally indistinguishable from its siblings.**

The six share one shape. Copy all five properties:

**A1. Signature — corpus/manifest first, `ledger` always explicit, never a module global** (`src/tools/open_doc.py:14`, `get_section.py:51-55`, `search_corpus.py:39`, `read_guideline.py:33-40`, `follow_reference.py:21-23`, `emit_finding.py:40-51`):

```python
# src/tools/open_doc.py:14  — the closest sibling to run_oracles (metadata in, dict|rejection out)
def open_doc(corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger) -> dict | ToolRejected:
```
```python
# src/tools/get_section.py:51-55 — the optional-param convention (see Pitfall 6 in RESEARCH.md)
def get_section(
    corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger,
    start: int | None = None, end: int | None = None, heading: str | None = None,
    handle: str | None = None, max_chars: int = 8000,
) -> str | ToolRejected:
```

**A2. Typed sentinel return, never an exception** (`src/tools/errors.py:1-5` docstring is the rule; `open_doc.py:15-21` is the minimal instance):

```python
# src/tools/open_doc.py:15-21
entry = next((d for d in corpus.manifest.documents if d.doc_id == doc_id), None)
if entry is None:
    return ToolRejected(
        tool="open_doc", reason_code="not_found",
        reason=f"doc_id {doc_id!r} is not in this corpus's manifest",
        hint="call search_corpus first to discover valid doc_ids",
    )
```
Every rejection carries a **`hint` that names the next call to make**. That field is the whole
of D-LOOP5's self-correction affordance — `oracles_tool.py`'s rejections must carry one too.

**A3. Span issuance goes through `ledger.record_span`, and NOTHING else** (`open_doc.py:22-23`, `search_corpus.py:68-69`, `get_section.py:45-46`, `read_guideline.py:68-69`, `follow_reference.py:30-31`):

```python
# src/tools/open_doc.py:22-23 — outline spans become citable the moment they are rendered
for outline_entry in entry.outline:
    ledger.record_span(outline_entry.span)
```
**D-ORC2 inverts this for `run_oracles` only:** the oracle tool must **NOT** call
`record_span`. It is the one tool in the set whose results are *not* citable until the agent
re-opens them. Say so in the module docstring the way `follow_reference.py:36-38` documents its
own inversion, and assert it in `test_oracles_tool.py::test_no_prerecorded_spans`.

**A4. The `[doc_id:start:end]` render — the only span form the model ever sees** (identical in three tools, so it is a convention, not a coincidence):

```python
# src/tools/get_section.py:36-48
def _render_annotated(
    nt: NormalizedText, doc_id: str, start: int, end: int, ledger: RetrievalLedger,
) -> str:
    """Per-sentence cat -n annotation (D-GRAN) over nt.canonical[start:end] -- shared by the
    normal bounded-read path, the oversized-preview path, and the handle-continuation path so
    all three annotate identically and record spans into the SAME ledger."""
    out = []
    for s_off, e_off in split_sentences(nt.canonical[start:end]):
        s_abs, e_abs = start + s_off, start + e_off
        span = mint_span(nt.canonical, s_abs, e_abs, doc_id, nt.normalizer_version)
        ledger.record_span(span)
        out.append(f"[{doc_id}:{s_abs}:{e_abs}] {nt.canonical[s_abs:e_abs]}")
    return "\n".join(out)
```
Byte-identical twin at `src/tools/read_guideline.py:59-71` (rulebook store); same format string at
`src/tools/search_corpus.py:72` (`"snippet": f"[{doc_id}:{start}:{end}] {text}"`).

**A5. Declared boundary, never a fake result** — the pattern `run_oracles` needs for *absence* leads (RESEARCH.md Pitfall 9):

```python
# src/tools/follow_reference.py:36-39
# Cannot tell "genuinely cross-document" from "same-doc reference we failed to locate"
# without Phase 4's reference graph -- both are honestly reported the same way (D-30:
# declare the boundary, never fake resolution). Never a silent {} / None.
return {"doc_id": doc_id, "ref_text": ref_text, "status": _CROSS_DOC_PENDING}
```

**A6. The battery it wraps — per-check try/except so one bad check never sinks the set**:

```python
# src/agents/detection/oracles.py:218-228
ORACLES = [result_vs_limit, value_vs_inline_limit, cross_reference_consistency]


def run_oracles(doc: dict) -> list[Fault]:
    faults: list[Fault] = []
    for check in ORACLES:
        try:
            faults.extend(check(doc))
        except Exception:  # noqa: BLE001 - one bad check must not sink the battery
            continue
    return faults
```
**Impedance mismatch to bridge (RESEARCH.md D4/Pitfall 9):** this takes `doc: dict` (the
`extract_pdf` page/block shape), not a `CorpusIndex`. The S9 path lives in
`src/agents/detection/checklists.py:74-96`, and its "evidence" is *synthesized*, not a span:

```python
# src/agents/detection/checklists.py:80-95 — an ABSENCE finding has no source span to re-open
faults.append(
    Fault(
        title=f"Validation parameter not addressed: {element}",
        ...
        evidence_class=EvidenceClass.CHECKLIST,
        evidence=f"No mention of {element} (searched for: {', '.join(keys)}).",
        source="checklist:validation",
    )
)
```
`run_oracles`-the-tool must therefore return **two honestly-typed lead kinds** (positive leads
carrying a locating hint; absence leads carrying expected-element + scope-searched), never a
`Fault`, and never a pre-recorded span.

**Name collision warning:** `agents.detection.oracles.run_oracles` already exists and is imported
at `pipeline.py:17`. The new tool must not shadow it — keep the legacy import path intact
(D-LOOP1 requires the legacy arm runnable).

---

### CLUSTER B — `src/agents/review/budget.py` (service, event-driven accumulation)

**Analog: `src/tools/ledger.py` — exact. This is the repo's only per-run injected accumulator, and it is the documented precedent for the whole DI design (RESEARCH.md Pattern 1).**

**B1. The docstring states the injection contract — copy the sentence, not just the code** (`src/tools/ledger.py:1-9`):

```python
"""Per-agent-run retrieval ledger (D-GRAN issuance tracking + COST-04 read-dedup).

Constructor-injected, never a module global (Security Domain V3 -- Pitfall 9): one instance
per agent run, threaded explicitly through every tool call. ...
"""
```

**B2. Plain class, private sets, cheap counters, predicate + rate accessors** (`ledger.py:15-40`):

```python
class RetrievalLedger:
    def __init__(self) -> None:
        self._issued: set[tuple[str, int, int]] = set()
        self._served: set[tuple[str, int, int]] = set()
        self._dedup_checks = 0
        self._dedup_hits = 0

    def record_span(self, span: SpanID) -> None:
        self._issued.add((span.doc_id, span.start, span.end))

    def was_issued(self, span: SpanID) -> bool:
        return (span.doc_id, span.start, span.end) in self._issued

    def check_and_mark_served(self, doc_id: str, start: int, end: int) -> bool:
        """Returns True on a DEDUP HIT (caller must return the stub, not full text); False
        on first request (caller renders full text; this call already marks it served)."""
        self._dedup_checks += 1
        key = (doc_id, start, end)
        if key in self._served:
            self._dedup_hits += 1
            return True
        self._served.add(key)
        return False

    def dedup_hit_rate(self) -> float:
        return self._dedup_hits / self._dedup_checks if self._dedup_checks else 0.0
```

Three things to carry into `BudgetLedger`:
- **`check_and_mark_served` is a check-AND-mutate in one call** — the D-BUD2 productivity check
  and the D-BUD3 breaker key should be the same shape (`did_this_turn_produce(...) -> bool`),
  not a read followed by a separate write the loop can forget.
- **`dedup_hit_rate()` already exists — D-TEL1 reads it, never recomputes it** (RESEARCH.md
  Anti-Patterns). `BudgetLedger` should expose its own equivalents (`billed_tokens`,
  `continuations`) as accessors so telemetry never re-derives them either.
- **`_issued` is keyed `(doc_id, start, end)` — the hash is NOT part of the key** (`:17,23,26`).
  This is why a loop-side re-mint bug passes `was_issued` and fails at `open_span`
  (RESEARCH.md Pitfall 1). `budget.py`'s D-BUD2 "new unique span-IDs" counter must use the same
  3-tuple key or the two will disagree about what "new" means.

**B3. Bounded loop with typed exits and an explicit terminal return — the stop-reason shape** (`src/llm/client.py:96-130`): see Cluster C, excerpt C2. The `for attempt in range(_MAX_RETRIES)` / fall-through-`return` structure is exactly the loop skeleton `loop.py` needs, with `stop_reason` replacing `finish_reason="error"`.

---

### CLUSTER C — `src/llm/client.py` (+ `chat_completion_tools`) (client, request-response)

**Analog: the file itself. `chat_completion` → `chat_completion_full` is already a sibling-entry-point pair; add a third sibling, do not modify the second.**

**C1. Sibling entry points, thin wrapper on top** (`client.py:58-83`):

```python
def chat_completion(...) -> str:
    """Backwards-compatible entry point — returns raw text."""
    result = chat_completion_full(...)
    return result.content


def chat_completion_full(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> ChatResult:
    """Full-response variant — returns text + finish_reason so callers can detect truncation."""
```
`ChatTurn` follows `ChatResult`'s shape (`client.py:33-36`) — a plain `@dataclass`, not pydantic:
```python
@dataclass
class ChatResult:
    content: str
    finish_reason: str
```

**C2. The resilience layer to PRESERVE VERBATIM — copy this body, change only the `kwargs`** (`client.py:87-128`):

```python
    kwargs: dict = {
        "model": model or s.resolved_llm_model,
        "messages": messages,
        "temperature": temperature if temperature is not None else s.llm_temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            return ChatResult(
                content=choice.message.content or "",
                finish_reason=choice.finish_reason or "stop",
            )
        except BadRequestError as exc:
            # Server may reject response_format on some endpoint types.
            # Retry once without it so the pipeline degrades gracefully to prompt-only mode.
            if response_format is not None and "response_format" in kwargs:
                log.warning("response_format_rejected_falling_back", error=str(exc)[:200])
                kwargs.pop("response_format", None)
                response_format = None
                continue
            log.error("llm_bad_request", error=str(exc))
            raise
        except RateLimitError as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_rate_limited_giving_up", attempts=_MAX_RETRIES)
                raise
            retry_after = _retry_after_seconds(exc)
            delay = retry_after if retry_after else min(_RATE_LIMIT_BASE_DELAY * (2 ** attempt), _RATE_LIMIT_MAX_DELAY)
            log.warning("llm_rate_limited_backoff", attempt=attempt + 1, delay=round(delay, 1))
            time.sleep(delay)
        except _RETRYABLE as exc:
            if attempt == _MAX_RETRIES - 1:
                log.error("llm_call_failed", error=str(exc), attempts=_MAX_RETRIES)
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            log.warning("llm_call_retry", error=str(exc), attempt=attempt + 1, delay=delay)
            time.sleep(delay)

    return ChatResult(content="", finish_reason="error")
```
Supporting constants and the header reader that must come along (`client.py:15-30`):
```python
_RETRYABLE = (APIConnectionError, APITimeoutError)
_MAX_RETRIES = 5
_BASE_DELAY = 1.0
_RATE_LIMIT_BASE_DELAY = 8.0    # per-minute token limits need real waits, not 1-4s
_RATE_LIMIT_MAX_DELAY = 60.0


def _retry_after_seconds(exc) -> float | None:
    """Read a Retry-After header off a rate-limit error, if the server sent one."""
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None) or {}
    value = headers.get("retry-after") or headers.get("Retry-After")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
```

**C3. What the new entry point must read that the old one discards** — `client.py:99-103` reads
only `choice.message.content` and `choice.finish_reason`; `response.usage` and
`choice.message.tool_calls` are dropped on the floor. `ChatTurn` adds `tool_calls`,
`raw_message` (`message.model_dump()`, echoed back verbatim per RESEARCH.md Pitfall 10),
`prompt_tokens`, `completion_tokens`, `cached_tokens`, `usage_present`.

**C4. Anti-pattern, already proven by this code:** do **not** pass `tools=` and
`response_format=` together. The `BadRequestError` handler at `:104-113` only knows how to drop
`response_format`; with `response_format=None` it logs `llm_bad_request` and re-raises — so a
tools-related 400 would surface as an unrecoverable raise. Tool turns are `tools=`-only.

---

### CLUSTER D — `src/agents/review/registry.py` + `src/llm/structured.py` additions (registry, transform)

**Analog: `structured.py:30-87` — add three functions BESIDE the existing three, never modify them (`CLAUDE.md` "What NOT to Use": *"Replacing `structured.py` wholesale"*).**

**D1. The derivation pair to mirror** (`structured.py:30-40` and `:76-87`):

```python
def schema_for_databricks(model_cls: type[BaseModel]) -> dict:
    """Convert a Pydantic model's JSON schema to a Databricks-strict-compatible shape.

    Databricks strict mode (like OpenAI strict) requires:
      - additionalProperties: false on every object
      - No `pattern` on strings (some servers reject it)
      - anyOf[X, null] flattened to X (nullability handled via required)
      - $defs preserved
    """
    schema = model_cls.model_json_schema()
    return _sanitize(schema)


def build_response_format(model_cls: type[BaseModel], name: str | None = None) -> dict:
    """Build the OpenAI-compatible response_format param for Databricks."""
    s = get_settings()
    schema = schema_for_databricks(model_cls)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name or model_cls.__name__,
            "schema": schema,
            "strict": s.structured_output_strict,
        },
    }
```
`tool_schema_for_databricks()` / `build_tool_schema()` are the exact same two-function shape
(normalize → wrap) with a different wrapper (`{"type":"function","function":{...}}`).

**D2. THE LOAD-BEARING FINDING — the docstring at `:37` says `$defs preserved`, and Databricks prohibits `$ref`.** `_sanitize` never inlines a `$ref` (`structured.py:43-73`):

```python
def _sanitize(node):
    if isinstance(node, dict):
        node = dict(node)  # shallow copy

        # Flatten anyOf[X, {"type": "null"}] to X
        if "anyOf" in node:
            variants = node["anyOf"]
            non_null = [v for v in variants if not (isinstance(v, dict) and v.get("type") == "null")]
            if len(non_null) == 1:
                # Merge the non-null variant into the parent, drop anyOf
                inherited = _sanitize(non_null[0])
                for k, v in inherited.items():
                    if k not in node:
                        node[k] = v
                node.pop("anyOf", None)
            else:
                node["anyOf"] = [_sanitize(v) for v in variants]

        # Strip 'pattern' — some Databricks endpoints reject it
        node.pop("pattern", None)

        # Force additionalProperties: false on objects
        if node.get("type") == "object":
            node["additionalProperties"] = False

        for k, v in list(node.items()):
            node[k] = _sanitize(v)
        return node
    if isinstance(node, list):
        return [_sanitize(v) for v in node]
    return node
```
Consequence the planner must encode as an acceptance criterion: **span-IDs cross the model
boundary as flat `str`, never as a nested `SpanID` model.** A field typed `SpanID` emits
`{"$ref": "#/$defs/SpanID"}` + a `$defs` block that `_sanitize` deliberately keeps. Note the
two things `_sanitize` already gets right for tools — `pattern` stripping (`:62`) matches the
Databricks prohibition exactly, and `anyOf[X,null]` flattening (`:48-57`) handles the
`str | None` optional args the locked D-RI2 contract forces.

**D3. Tool arg models — copy `subagents.py`'s flat-pydantic shape, not a nested one** (`src/agents/detection/subagents.py:42-53`):

```python
class RawFinding(BaseModel):
    title: str = Field(description="One-line statement of the deficiency.")
    detail: str = Field(default="", description="What is wrong and why, argued from the evidence.")
    evidence: str = Field(default="", description="Verbatim value, cell, or sentence from the document.")
    section: str = Field(default="", description="Section heading or number the fault sits in.")
    page: int = 0
    table_ref: str = Field(default="", description="Table it concerns, e.g. 'Table 16'; empty if none.")
    severity: Severity = Severity.MEDIUM
```
Flat scalars + a `StrEnum` + per-field `description=` (the model reads those descriptions). This
is exactly the shape RESEARCH.md's `EmitFindingArgs` prescribes. `ComplianceVerdict` as a
`StrEnum` renders `{"type":"string","enum":[...]}` — no `anyOf`, no `$ref`.

**D4. The repair path the loop reuses for pre-dispatch arg coercion** (`structured.py:119-147`):

```python
def parse_structured(
    raw: str,
    model_cls: type[T],
) -> tuple[T | None, str | None]:
    """L3 + L4: extract, repair, validate.

    Returns (instance, None) on success or (None, error_message) on failure.
    """
    extracted = _extract_json_blob(raw)
    if not extracted:
        return None, "empty response after extraction"

    # First try clean parse
    try:
        obj = json.loads(extracted)
    except json.JSONDecodeError:
        # L3: deterministic repair (trailing commas, unclosed braces, unquoted keys)
        try:
            repaired = repair_json(extracted)
            obj = json.loads(repaired) if isinstance(repaired, str) else repaired
            log.info("json_repair_salvage", model=model_cls.__name__)
        except Exception as exc:
            return None, f"json_repair failed: {exc}"

    # L4: Pydantic validation — surface errors verbatim for caller re-prompt
    try:
        return model_cls.model_validate(obj), None
    except ValidationError as exc:
        return None, exc.json(indent=None)
```
The `(instance, error) | (None, error)` tuple return and the `log.info("json_repair_salvage", ...)`
structlog counter are the D-TEL4 pre-repair signal — **count that log event, do not build a
parallel counter.** `structured_call`'s layered-fallback structure (`:282-316`) is the model for
"try, then repair, then return a typed failure — never raise, never leak raw text."

---

### CLUSTER E — `src/agents/review/spanref.py` (utility, transform)

**Analog: the exact inverse already exists. `spanref.parse_span_ref` must undo `_render_annotated` byte-for-byte.**

**E1. The mint side (what the tools do — `get_section.py:45`, `read_guideline.py:68`, `search_corpus.py:68`)**, and the primitives it uses (`src/ingest/anchors.py:46-53`):

```python
def mint_span(canonical: str, start: int, end: int, doc_id: str, normalizer_version: str) -> SpanID:
    """Mint a content-addressed SpanID over canonical[start:end] (arbitrary ranges are valid)."""
    return SpanID(
        doc_id=doc_id,
        start=start,
        end=end,
        hash=short_hash(canonical[start:end], normalizer_version),
    )
```

**E2. The verification `emit_finding` runs — and the reason a wrong `normalizer_version` is fatal** (`src/ingest/anchors.py:56-72`):

```python
def open_span(span: SpanID, nt: NormalizedText, doc_id: str) -> tuple[str, str]:
    """Re-open a span-ID -> (raw_source_substring, canonical_substring) or raise HashMismatch (D-21).
    ...
    """
    if span.doc_id != doc_id:
        raise HashMismatch(span, span.doc_id, doc_id)
    from ingest.normalize import canon_range_to_raw  # local import: avoids an import cycle at load

    canonical = nt.canonical[span.start:span.end]
    actual = short_hash(canonical, nt.normalizer_version)
    if actual != span.hash:
        raise HashMismatch(span, span.hash, actual)
    raw_s, raw_e = canon_range_to_raw(nt.offset_map, span.start, span.end)
    return nt.raw_serialized[raw_s:raw_e], canonical
```

**E3. Where the `normalizer_version` comes from — the exact lookup, so the re-mint cannot drift** (`src/tools/get_section.py:26-33` + `:56,62`):

```python
def _nt_from_cache_entry(entry: dict) -> NormalizedText:
    return NormalizedText(
        canonical=entry["canonical"],
        raw_serialized=entry["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in entry["offset_map"]],
        normalizer_version=entry["normalizer_version"],
        serializer_version=entry["serializer_version"],
    )
```
```python
    cache = corpus.cached_entry(doc_id)   # get_section.py:56
    nt = _nt_from_cache_entry(cache)      # get_section.py:62
```
This helper is duplicated verbatim in **four** places — `get_section.py:26-33`,
`search_corpus.py:17-21`, `emit_finding.py:77-79`, `tests/tools/test_contracts.py:20-25`. That
duplication is the existing convention; `spanref.py` copying it a fifth time is consistent, but
consolidating it is also defensible. **Do not invent a new NormalizedText construction path.**

**E4. Rulebook-store resolution is a DIFFERENT lookup — store separation is a security control** (`emit_finding.py:66-75`):

```python
    corpus_cache = corpus.cached_entry(submission_span_id.doc_id)
    if corpus_cache is None:
        return ToolRejected(tool="emit_finding", reason_code="wrong_store",
                            reason=f"submission_span_id.doc_id={submission_span_id.doc_id!r} does not resolve in the CORPUS store",
                            hint="submission_span_id must come from get_section/search_corpus over THIS corpus")
    rule_nt = rulebook_nt_for(rule_span_id.doc_id, cache_dir=rulebook_cache_dir)
    if rule_nt is None:
        return ToolRejected(tool="emit_finding", reason_code="wrong_store",
                            reason=f"rule_span_id.doc_id={rule_span_id.doc_id!r} does not resolve in the RULEBOOK store",
                            hint="rule_span_id must come from read_guideline, not get_section")
```
`parse_span_ref` must be told **which store to resolve against**, never "whichever answers first."

**E5. A loop-side parse failure needs a DISTINCT reason code** (RESEARCH.md Pitfall 1). Follow
`errors.py:13-19`'s open-`str` design — add `span_ref_unparseable` / `span_ref_unknown_doc` to
`KNOWN_REASON_CODES`, never reuse `not_byte_exact`, because D-TEL3 pre-registers
`half=submission` + `not_byte_exact` as *model span invention* and a loop bug wearing that label
produces a wrong NO-GO.

---

### CLUSTER F — `src/agents/review/telemetry.py` (service, streaming file-I/O)

**Analog: PARTIAL. There is no JSONL writer anywhere in this repo** (`grep -rn "jsonl\|JSONL" src/ tests/ --include=*.py` → **no matches**). Two halves have analogs; the append-stream itself does not.

**F1. Atomic write — the durability convention for anything persisted** (`src/ingest/store.py:46-57`):

```python
def write_doc_cache(cache_dir, key: str, entry: dict) -> None:
    """Atomically persist a per-document cache entry (temp -> os.replace); no half entry on crash.
    ...
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    final = _cache_path(cache_dir, key)
    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry), encoding="utf-8")
    os.replace(tmp, final)   # atomic rename: a crash before this leaves only .tmp, never a half .json
```
Use this for the **summary JSON**. The per-turn JSONL is an append stream, so it cannot be
temp→rename; the closest defensible design is "append + flush per line," and a crashed run's
truncated last line must be tolerated by the reader (D-TEL1(i)'s aborted-vs-completed flag is in
the *summary*, which IS atomic).

**F2. Summary-file writer** (`src/evals/run.py:128-131`):

```python
def _write_metrics(metrics: dict, out_path: str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2, default=str))
```
`indent=2, default=str` is what makes the committed artifacts diffable across the 3 runs (D-TEL1(ii)).

**F3. Version-stamped provenance — the existing constants D-TEL1 must record** (four files, one convention):

```python
# src/ingest/normalize.py:35-36
LEXICON_VERSION = "1"
NORMALIZER_VERSION = f"nfc-wscollapse-gdehyph-lig/1-lex{LEXICON_VERSION}"

# src/ingest/serialize.py:22
SERIALIZER_VERSION = "reading-order-cells/1"

# src/rulebook/requirement_index.py:42
REQUIREMENT_INDEX_VERSION = "3"
```
`HARNESS_VERSION` / `MATCHER_VERSION` go in `src/evals/__init__.py` (**currently a 0-byte file**)
in exactly this shape. RESEARCH.md D7 verified there is no version constant anywhere in
`src/evals/*` today — this is a build, not a read.

**F4. Structured logging is already wired — reuse it, don't add a logger** (`client.py:6,11`, `structured.py:17,25`, `pipeline.py:12,26`):
```python
import structlog
log = structlog.get_logger()
```
Event-name convention is `snake_case` verbs/nouns: `llm_rate_limited_backoff`,
`json_repair_salvage`, `moderator_rescue_called`, `dropped_self_negating_findings`,
`detection_complete`. Follow it (`agent_turn`, `tool_dispatch`, `budget_ceiling_tripped`, …).

**F5. Rate accessors are READ, never recomputed** (`ledger.py:39-40`) — `dedup_hit_rate()` is a
D-TEL1 signal that already exists.

---

### CLUSTER G — `src/agents/review/loop.py` + `__init__.py` (orchestrator, event-driven)

**Analog: `src/agents/detection/pipeline.py::run_detection` for the entry-point shape; `client.py:96-128` for the loop skeleton (Cluster C, excerpt C2).**

**G1. Entry-point shape: timed, emits progress, never raises, always returns a report** (`pipeline.py:37-48` and `:93-102`):

```python
def run_detection(
    doc: dict, sections: list[dict], groups: list[dict], job_id: str = "", model: str | None = None
) -> FaultReport:
    start = time.time()
    detector_model = resolve_detector_model(model)
    ctd = detect_ctd_section(_leading_text(doc) or doc.get("filename", ""))
    doc_desc = describe_document(ctd)
    emit_sync(job_id, "detection", "layer_start", "Detection", f"Reviewing {doc_desc}")
    emit_sync(
        job_id, "detection", "agent_message", "Detection",
        f"Model: {DETECTOR_MODELS.get(detector_model, detector_model)}",
    )
```
```python
    log.info("detection_complete", faults=len(faults), workers=len(plan.workers), seconds=round(time.time() - start, 1))

    return FaultReport(
        job_id=job_id,
        faults=faults,
        faults_found=bool(faults),
        domains_checked=focused_headings,
        parse_failures=failures,
        analysis_seconds=round(time.time() - start, 1),
    )
```

**G2. THE SEAM D-ORC1/D-VER1 DISMANTLE — the exact two lines** (`pipeline.py:86-87`):

```python
    # Stage 4 — verify + tier + dedup, then the grounded challenge (scores, never vetoes).
    faults = verify_and_tier(oracle_faults + checklist_faults + agent_faults, doc)
    faults = challenge_faults(faults, sections, doc, model=detector_model)
```
**Do not edit these.** D-LOOP1 requires the legacy arm runnable and byte-identical; the agent
path is a *sibling* entry point (`run_review`), not a branch inside `run_detection`. The
signatures are incompatible anyway — `run_detection` is per-document (`:37-39`) and the harness
calls it in a per-document loop (`evals/run.py:259-281`), while D-BUD5 mandates a per-run budget
over a multi-document review.

**G3. Never-crash fan-out with per-item failure collection** (`src/agents/detection/workers.py:189-200`) — the shape for dispatching a turn's tool calls:

```python
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = [pool.submit(_run_specialist, w, sections, summaries, doc_desc, model) for w in plan.workers]
        futures += [pool.submit(_run_open_reviewer, c, sections, summaries, doc_desc, model) for c in chunks]
        for fut in concurrent.futures.as_completed(futures):
            try:
                fs, failure = fut.result()
                faults.extend(fs)
                if failure is not None:
                    failures.append(failure)
            except Exception as exc:  # noqa: BLE001 - one dead worker must not sink the fan-out
                log.warning("worker_failed", error=str(exc)[:200])
    return faults, failures
```
(Phase 3 dispatch is sequential — Databricks does not support parallel function calling — but the
`(results, failures)` tuple + `# noqa: BLE001` justification-comment convention carries over.)

**G4. Barrel** (`src/agents/detection/__init__.py`, all 3 lines):
```python
from agents.detection.pipeline import run_detection

__all__ = ["run_detection"]
```

---

### CLUSTER H — `src/agents/review/prompts.py` (config/constants) — **COPY THE SHAPE, INVERT THE TEMPLATING**

**Analog: `src/agents/detection/prompts.py` — module-level triple-quoted constants. But it uses `{}` placeholders filled by `.format()` at four call sites, and D-LOOP4 forbids exactly that for the system prompt.**

```python
# src/agents/detection/prompts.py:17-20 — the shape to copy STRUCTURALLY
SPECIALIST = """You are an FDA-style CMC reviewer whose sole focus is the "{domain}" domain:
{domain_desc}

You are reviewing {doc_desc}. Find EVERY deficiency in your domain that an FDA reviewer
...
```
Filled at `subagents.py:98`, `workers.py:145`, `workers.py:165`, `selection.py:64`
(`.format(...)`). **The review system prompt must have zero placeholders and zero `.format()`
call sites** — corpus manifest, document counts and families go in a separate `user` message
(RESEARCH.md § Code Examples). `test_prefix_stability.py` is the enforcement.

Content worth carrying forward from `prompts.py:29-38` (already-tuned reviewer rules that match
this project's precision goal):
```
- Each finding must cite specific evidence: a verbatim value, table cell, or sentence from
  the document, with the section or page. Never invent a value or a citation.
- Report an absence (something required that is missing) plainly — you cannot quote what is
  absent, so describe what you expected and where you looked.
- "N/A", "ND", and "Not Applicable" cells are usually intentional — do NOT report them as
  missing unless a genuinely required value is blank.
- If your domain is clean, return an empty findings list. Do NOT force findings.
```

---

### CLUSTER I — `src/tools/errors.py` + `src/tools/emit_finding.py` (models/tool — ADDITIVE ONLY)

**Analog: each file's own existing additive precedent.**

**I1. `errors.py` — the whole file is 28 lines; the additive precedent is in it** (`errors.py:11-28`):

```python
class ToolRejected(BaseModel):
    tool: str
    # Known reason codes (plain str, NOT a closed Literal -- later plans add codes without
    # editing this file): not_found | range_too_large | not_byte_exact |
    # not_retrieved_this_session | wrong_store | family_not_in_registry | no_rule_citation
    # NOTE: not_unique is deliberately excluded from this list. ...
    reason_code: str
    reason: str
    hint: str = ""
    # TOOLS-04 persist+preview+handle (plan-checker Blocker 2): populated on an oversized-range
    # rejection (reason_code="range_too_large") -- `preview` is a bounded, span-ID-annotated
    # string; `handle` is the re-openable key for a follow-up page-forward call. Both default to
    # "" for every OTHER rejection reason, where they don't apply.
    preview: str = ""
    handle: str = ""
```
`half: str = ""` copies `preview`/`handle` exactly: **defaulted, documented with the decision ID
that added it, and explicitly noted as `""` for every tool where it does not apply.**
`KNOWN_REASON_CODES` promotes the `:13-19` comment into a dict without closing the `str` type —
the comment already says why it must stay open.

**I2. `emit_finding.py` — the 7 sites, in file order, with their D-TEL3 `half` value** (verified against `emit_finding.py:52-92`):

| Line | Code | `half` | Excerpt |
|------|------|--------|---------|
| `:53` | `no_rule_citation` | `rule` | `if rule_span_id is None:` |
| `:58` | `not_retrieved_this_session` | `submission` | `if not ledger.was_issued(submission_span_id):` |
| `:62` | `not_retrieved_this_session` | `rule` | `if not ledger.was_issued(rule_span_id):` |
| `:68` | `wrong_store` | `submission` | `if corpus_cache is None:` |
| `:73` | `wrong_store` | `rule` | `if rule_nt is None:` |
| `:84` | `not_byte_exact` | `submission` | `except HashMismatch:` (submission `open_span`) |
| `:90` | `not_byte_exact` | `rule` | `except HashMismatch:` (rule `open_span`) |

```python
# src/tools/emit_finding.py:57-64 — the two-line pair that must NOT collapse into one count
    if not ledger.was_issued(submission_span_id):
        return ToolRejected(tool="emit_finding", reason_code="not_retrieved_this_session",
                            reason="submission_span_id was never actually retrieved this session",
                            hint="re-fetch via get_section/search_corpus, then cite the span-ID it returns")
    if not ledger.was_issued(rule_span_id):
        return ToolRejected(tool="emit_finding", reason_code="not_retrieved_this_session",
                            reason="rule_span_id was never actually retrieved this session",
                            hint="re-fetch via read_guideline, then cite the span-ID it returns")
```
Same `reason_code`, opposite diagnoses — this pair is *why* D-TEL3 exists.

**I3. The two documented Phase-2 boundaries Phase 3 closes** (`emit_finding.py:94-98` and `:100-117`):

```python
    # Phase 2 has no compliance-verdict CLASSIFICATION logic yet (DETECT-04 lands in Phase 3) --
    # `verdict` is accepted per D-EF1's finding schema {submission_span_id, rule_span_id, verdict...}
    # and threaded into `detail` for now rather than a dedicated Fault field (none exists on the
    # unmodified schemas.faults.Fault); Phase 3 owns any future verdict-specific field/logic.
    detail_with_verdict = f"{detail} [verdict: {verdict}]".strip() if verdict else detail
```
```python
    return Fault(
        title=title or "Deficiency", detail=detail_with_verdict,
        tier=Tier.CORROBORATED, evidence_class=EvidenceClass.QUOTE_ANCHORED, confidence=0.7,
        evidence=submission_raw, source="tool:emit_finding",
        guidance_refs=[rule_citation or rule_span_id.doc_id] + ([requirement_id] if requirement_id else []),
    )
```
The `:100-111` comment names its own successor: *"If a later phase (Phase 5's verifier) needs to
re-open the EXACT rule span a Fault cites, that requires either a Fault schema change
(schemas/faults.py, currently off-limits)…"* — **Phase 3 is the phase that makes it not
off-limits.** Note also `title or "Deficiency"`: harmless for scoring (the matcher reads
`evidence` only, `match.py:91`) but catastrophic under `verify.py`'s title-keyed dedup — which is
D-VER1's empirical justification.

---

### CLUSTER J — `src/schemas/faults.py` (model, additive)

**Analog: the file's own StrEnum + all-defaulted-field style.**

```python
# src/schemas/faults.py:20-35 — the StrEnum shape ComplianceVerdict copies, docstring included
class EvidenceClass(StrEnum):
    """What kind of check stands behind the finding — surfaced so the analyst never
    mistakes a model opinion for a code-verified fact."""

    CODE_VERIFIED = "code_verified"      # an oracle recomputed / compared cells
    CHECKLIST = "checklist"              # a required element was searched for and is absent
    QUOTE_ANCHORED = "quote_anchored"    # the cited evidence span exists verbatim in the doc
    MODEL_JUDGMENT = "model_judgment"    # LLM reasoning only, no oracle or anchor


class Tier(StrEnum):
    """Confidence tier. Recall lives in ADVISORY — nothing is hidden, only ranked."""

    VERIFIED = "verified"          # T1 — oracle-confirmed, or strong precedent + self-consistency
    CORROBORATED = "corroborated"  # T2 — >=1 real precedent, no hard oracle
    ADVISORY = "advisory"          # T3 — model judgment, incl. novel / out-of-distribution
```
Per-member trailing comment explaining the semantics — copy that for
`violation`/`gap`/`ambiguous`.

**Every new field must default**, so the committed golden fixtures
(`src/evals/dataset/golden/mvr1381_run3.json`) and every existing construction site keep
validating (`faults.py:41-62` — 15 of 17 fields are defaulted; `FaultReport` at `:65-73` is
100% defaulted):

```python
    evidence: str = Field(default="", description="Verbatim span or cell the finding rests on.")
    guidance_refs: list[str] = Field(default_factory=list)
```

---

### CLUSTER K — `src/evals/run.py` `agent-run` subcommand (CLI, batch)

**Analog: `cmd_run` + `build_parser` in the same file — exact.**

**K1. The "import the library, record, never crash" shape CONTEXT.md names as the model for the spike harness** (`evals/run.py:240-287`):

```python
def cmd_run(args: argparse.Namespace) -> int:
    """`run`: LIVE parse -> detect over every non-held-out eval-set document.
    ...
    A document whose format has no parse path yet (DOCX at Phase 0) or that raises anywhere in
    parse/detect is recorded as a `parse_failure` and skipped -- one bad document never crashes
    the whole run.
    """
    from agents.detection.pipeline import run_detection      # LAZY import — keeps `--help` light
    from parse.pdf import extract_pdf
    from parse.section_splitter import group_sections, split_document

    eval_set = load_eval_set()
    reports: dict[str, FaultReport] = {}
    per_doc_metrics: dict[str, dict] = {}
    parse_failures: dict[str, str] = {}

    for doc in eval_set.documents:
        if doc.held_out:
            continue
        try:
            ...
            report = run_detection(parsed, sections, groups, job_id="", model=args.model)
        except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run
            parse_failures[doc.doc_id] = str(exc)
            continue

        reports[doc.doc_id] = report
        source_text = _join_source_text(parsed)
        metrics = compute_metrics(report, eval_set, doc.doc_id, source_text=source_text)
        per_doc_metrics[doc.doc_id] = metrics
        print(f"=== {doc.doc_id} ===")
        print(format_table(metrics))

    if parse_failures:
        print(f"parse_failures: {parse_failures}")
    _write_metrics({"per_document": per_doc_metrics, "parse_failures": parse_failures}, args.out)
```
Three properties to copy exactly: **`if doc.held_out: continue`** (`:260-261` — the reason
`spec32s41` is available as D-BUD1's calibration corpus), **the lazy in-function import** of the
heavy stack (`:250-252`, justified in the module docstring at `run.py:23-30`), and **the
per-document `except Exception` that records and continues**.

**K2. Subcommand registration** (`run.py:323-327`):

```python
    run_p = subparsers.add_parser("run", help="LIVE: parse+detect every non-held-out document.")
    run_p.add_argument("--model", default=None, help="Detector model id (validated by resolve_detector_model).")
    run_p.add_argument("--gate", action="store_true", help="Also apply the zero-TP-lost gate.")
    run_p.add_argument("--out", default=DEFAULT_RUN_OUT)
    run_p.set_defaults(func=cmd_run)
```
`agent-run` is one more `subparsers.add_parser(...)` + `set_defaults(func=cmd_agent_run)`.
**Model arg must route through `resolve_detector_model`** (`config.py:100-105`) — the allow-list
is what keeps D-GO3's baseline-matched-model claim enforceable in code:
```python
def resolve_detector_model(model: str | None) -> str:
    """A requested model is used only if it is in the allow-list; otherwise fall back
    to the configured default. Never lets an arbitrary client string reach the LLM call."""
    if model and model in DETECTOR_MODELS:
        return model
    return get_settings().detector_model
```

**K3. Re-scoring a committed run without an LLM — makes D-TEL1(ii) nearly free** (`src/evals/capture.py:16-18`):

```python
def load_captured(path: str | Path) -> FaultReport:
    """Load and validate a captured `FaultReport` JSON file from `path`."""
    return FaultReport.model_validate_json(Path(path).read_text())
```
Commit `run{1,2,3}.json` as serialized `FaultReport`s and the verdict is re-derivable via
`python -m evals.run score --captured <path>` by someone who did not watch the runs.

---

### CLUSTER L — P2: `src/parse/pdf.py` + `src/ingest/store.py` (parser + store)

**L1. The fix is a copy of the sibling branch two lines below it** (`pdf.py:221-237`):

```python
        if scanned:
            source = "rapidocr"
            ocr_result = ocr_page(page)
            if ocr_result is not None:
                text, ocr_tables, blocks, figures, ocr_source = ocr_result
                source = ocr_source  # "rapidocr" (boxed/blank) or "rapidocr-flat-text" (degraded, text kept)
                # find_tables() finds nothing on a scan (grid lines are pixels, not
                # vectors), so these reconstructed tables are all this page has.
                tables = tables + ocr_tables
                ocr_count += 1
            else:
                source = "rapidocr-fallback"
                text = page.get_text("text")          # ← computed, then discarded
        else:
            text = page.get_text("text")
            blocks = _digital_blocks(page, tables)    # ← THE TWO LINES TO COPY UP
            figures = _digital_figures(page, blocks)  # ←
```
`blocks`/`figures` are initialized empty at `:217-218` and stay empty on the fallback branch; the
appended page dict at `:239-252` has **no `text` key**, so `text` is used only by
`_detect_page_label(text)` at `:242`. Every downstream consumer reads `blocks`
(`ingest/serialize.py:55-57`, `checklists.py:51-56`, `verify.py:97-98`).

The branch is reached when `ocr_page` returns `None` (`ocr.py:80-82`: *"no OCR API available
(e.g. local dev without creds) -> skip"*) on a page `is_scanned_page` flagged
(`ocr.py:59-71`: image coverage over threshold **or** a glyphless font — i.e. a scan carrying an
invisible OCR text layer).

**L2. `PARSER_VERSION` — same shape as the other three version constants** (Cluster F, excerpt F3), folded into the key that already folds two:

```python
# src/ingest/store.py:35-39
def cache_key(content_hash: str, normalizer_version: str, serializer_version: str) -> str:
    """A filesystem-safe key folding in both versions; a version bump invalidates (D-24, Pitfall 6)."""
    nv = _UNSAFE.sub("_", normalizer_version)
    sv = _UNSAFE.sub("_", serializer_version)
    return f"{content_hash}__{nv}__{sv}"
```
Note `content_hash` is over **file bytes** (`ingest/corpus.py:119`), so a parser change alone
never invalidates the key today — RESEARCH.md's silent-corruption seam. The call site to update
is `CorpusIndex.cached_entry` (`ingest/corpus.py:52-58`):
```python
    def cached_entry(self, doc_id: str) -> dict | None:
        """Fetch a document's persisted cache entry (full canonical text + offset map + index)."""
        for d in self.manifest.documents:
            if d.doc_id == doc_id:
                key = cache_key(d.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION)
                return read_doc_cache(self.cache_dir, key)
        return None
```
…plus `tests/tools/conftest.py:75` and `tests/ingest/test_store.py:20`, which both call
`cache_key` positionally. **Signature change ⇒ 4+ call sites.** A keyword-defaulted
`parser_version: str = PARSER_VERSION` keeps the existing calls compiling while still changing
the emitted key.

**L3. The existing invalidation test to extend** (`tests/ingest/test_store.py:31-34`):

```python
    # normalizer-version bump -> different key -> MISS (invalidation, D-24)
    key_bumped = cache_key(h, "nfc-.../2-lex1", sv)
    assert key_bumped != key
    assert read_doc_cache(cache_dir, key_bumped) is None
```
The `PARSER_VERSION` test is this, one argument over.

---

### CLUSTER M — `tests/agents/review/conftest.py` and the four load-bearing tests

**M1. `tests/tools/conftest.py` is the canonical corpus fixture — every new offline test builds corpora through it.** Full text (`tests/tools/conftest.py:37-84`):

```python
def build_corpus_index(
    tmp_path, doc_id: str, blocks, tables=None, outline_headings=None,
    filename: str = "doc.pdf", title: str = "Test Document",
) -> CorpusIndex:
    """Build + persist a real single-document `CorpusIndex` fixture.

    `blocks`/`tables` feed `make_doc_dict` (the exact `extract_pdf`-shaped dict); the resulting
    doc is run through the real `serialize_document` -> `normalize` -> `build_table_index`
    pipeline `ingest_corpus()` itself uses, then cached exactly as `write_doc_cache` expects, so
    `CorpusIndex.cached_entry(doc_id)` returns a genuine cache entry, never a stand-in shape.

    `outline_headings` (optional) is an ordered list of heading strings that must appear
    verbatim in the rendered canonical text (put them inside a block's text); each becomes an
    `OutlineEntry` spanning its first occurrence, mirroring `ingest.corpus._build_outline`'s own
    best-effort match. Classification is left `None` -- Phase 2's tools never need it.
    """
    tables = tables or []
    doc = make_doc_dict(blocks, tables, filename=filename)
    raw, cell_ranges = serialize_document(doc)
    nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
    table_index = build_table_index(nt, tables, cell_ranges, doc_id)

    outline: list[OutlineEntry] = []
    for heading in outline_headings or []:
        pos = nt.canonical.find(heading)
        pos = max(pos, 0)
        span = mint_span(nt.canonical, pos, pos + len(heading), doc_id, nt.normalizer_version)
        outline.append(OutlineEntry(span=span, label=heading))

    entry = DocEntry(
        doc_id=doc_id, filename=filename, content_hash=f"testhash-{doc_id}",
        status="parsed", structure="outlined" if outline else "flat",
        tables="addressable" if table_index else "unavailable",
        classification=None, title=title, outline=outline,
        normalizer_version=nt.normalizer_version, serializer_version=nt.serializer_version,
    )

    cache_dir = str(tmp_path / "cache")
    key = cache_key(entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION)
    write_doc_cache(cache_dir, key, {
        "canonical": nt.canonical, "raw_serialized": nt.raw_serialized,
        "offset_map": [r.model_dump() for r in nt.offset_map],
        "normalizer_version": nt.normalizer_version, "serializer_version": nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in table_index.items()},
        "doc_entry": entry.model_dump(),
    })
    manifest = CoverageManifest(documents=[entry])
    return CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)
```
Plus the per-test ledger fixture (`:32-34`):
```python
@pytest.fixture
def fresh_ledger() -> RetrievalLedger:
    return RetrievalLedger()
```
**RESEARCH.md's Wave-0 list asks for a multi-document extension.** Extend by taking a list of
`(doc_id, blocks, outline_headings)` and returning ONE `CorpusIndex` with N `DocEntry`s sharing a
single `cache_dir` — the `manifest = CoverageManifest(documents=[entry])` line at `:83` is the
only structural change. **Do not hand-roll a cache dict** (the docstring at `:41-46` says why:
`cached_entry()` must be byte-identical to a real ingest).

The `conftest.py` docstring convention itself (`tests/tools/conftest.py:1-14`,
`tests/ingest/conftest.py:1-23`) is a bulleted inventory of what the module provides — copy it.

**M2. Offline-forcing fixtures** (`tests/ingest/conftest.py:35-59`) — the D-RB6 mechanism:

```python
@pytest.fixture
def offline(monkeypatch):
    """Force the no-Databricks OCR fallback so tests are fast and deterministic."""
    from config import Settings
    import parse.ocr as ocrmod

    monkeypatch.setattr(
        ocrmod, "get_settings", lambda: Settings(databricks_host="", databricks_token="")
    )


@pytest.fixture
def no_llm(monkeypatch):
    """`offline` + no-creds llm.client, so the classifier LLM tier degrades to deterministic."""
    from config import Settings

    empty = lambda: Settings(databricks_host="", databricks_token="")  # noqa: E731
    import parse.ocr as ocrmod

    monkeypatch.setattr(ocrmod, "get_settings", empty)
    # llm.client binds `get_settings` into its own namespace (from config import get_settings);
    # patch it there. raising=False keeps this robust if the classifier lands elsewhere later.
    import llm.client as clientmod

    monkeypatch.setattr(clientmod, "get_settings", empty, raising=False)
```
**Note for the loop:** dependency injection makes this monkeypatching unnecessary for
`ScriptedChatClient` (RESEARCH.md Pattern 1) — which is the point. `offline`/`no_llm` are still
needed for the P2 parse test and any test that touches `parse.ocr`.

**M3. THE COMPOSITION TEST SHAPE — `tests/tools/test_enumerate_fetch_emit_e2e.py`.** GROUND-01's
span-ID round-trip is the same shape aimed at a different boundary. Copy four things:

*(a) The docstring that names the failure class* (`:1-14`):
```python
"""Boundary-crossing composition test -- Phase-2 verification-queue item 5 (MATERIAL).

Every other test in this suite proves ONE tool's own contract in isolation (green unit tests on
each side of `read_guideline`/`emit_finding`). That is exactly the class of test whose absence
let the real citation<->store granularity mismatch ship undetected in 02-09: `read_guideline`'s
fetch mode was proven correct against a CONTROLLED entry, and `enumerate_requirements` was proven
correct against the real index -- but nothing drove the REAL, committed
`rulebook/requirement_index.yaml`'s 15 entries all the way through
`enumerate_requirements -> read_guideline(rule_doc_id) -> emit_finding` in one composed test.
...
"""
```

*(b) Parse exactly what the model sees, from the rendered string* (`:32` and `:140-143`):
```python
_SPAN_RE = re.compile(r"^\[([^:\]]+):(\d+):(\d+)\]")
```
```python
            m = _SPAN_RE.search(fetch_result)
            assert m, f"{rule_doc_id}: no annotated [doc_id:start:end] span found in fetch result"
            span_doc_id, span_start, span_end = m.group(1), int(m.group(2)), int(m.group(3))
```

*(c) Re-mint from the store's own `normalizer_version`, then assert BOTH gates* (`:145-153`):
```python
        nt = rulebook_nt_for(span_doc_id)
        assert nt is not None, f"{rule_doc_id}: rulebook_nt_for({span_doc_id!r}) unexpectedly None"
        rule_span = mint_span(nt.canonical, span_start, span_end, span_doc_id, nt.normalizer_version)
        assert ledger.was_issued(rule_span), f"{rule_doc_id}: span not recorded in the ledger by read_guideline"

        result = emit_finding(
            corpus=corpus, submission_span_id=submission_span, rule_span_id=rule_span,
            ledger=ledger, verdict="fails",
            requirement_id=requirement_id, rule_citation=row["citation"],
        )
```

*(d) Collect failures, assert the whole set at the end — never `assert` inside the loop on the thing under test* (`:115-116` and `:160-162`):
```python
    resolved: list[str] = []
    rejected: list[tuple[str, str, str]] = []
```
```python
    assert not rejected, f"expected 15/15 to resolve end-to-end, but these did not: {rejected}"
    assert len(resolved) == 15
    assert set(resolved) == {row["requirement_id"] for row in rows}
```
The failure message names *which* items failed and why — a per-iteration `assert` would report
only the first.

*(e) The COST-04 subtlety the round-trip test will hit too* (`:117-124`): a second whole-document
fetch legitimately returns a `[STILL_CURRENT]` stub rather than re-rendering, and the test
carries a `span_by_doc_id` cache to handle it. `get_section`'s dedup (`get_section.py:132-136`)
behaves identically, so the span-ref round-trip test over five rendering tools must expect
`[STILL_CURRENT]` on any repeated `(doc_id, start, end)`.

**M4. Byte-exact re-open assertion, minimal form** (`tests/tools/test_contracts.py:81-97`):

```python
def test_get_section_span_ids_reopen_byte_exact(tmp_path, fresh_ledger):
    body = "Only one sentence here."
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])
    cache = corpus.cached_entry("d1")
    nt = _nt_from_cache(cache)

    section = get_section(corpus, "d1", fresh_ledger, start=0, end=len(nt.canonical))
    assert isinstance(section, str)

    m = _SPAN_MARKER.match(section)
    assert m is not None
    start, end, printed_text = int(m.group(1)), int(m.group(2)), m.group(3)

    span = mint_span(nt.canonical, start, end, "d1", nt.normalizer_version)
    _raw, reopened_canonical = open_span(span, nt, "d1")
    assert reopened_canonical == printed_text
    assert reopened_canonical == nt.canonical[start:end]
```
`assert reopened_canonical == printed_text` — the text the model saw equals the text the gate
re-opens. That is the round-trip assertion, already written, for one tool.

**M5. Ledger-issuance assertion for `test_oracles_tool.py::test_no_prerecorded_spans`** — the positive form to invert (`tests/tools/test_contracts.py:100-109`):

```python
def test_open_doc_outline_spans_are_issued_in_ledger(tmp_path, fresh_ledger):
    body = "Heading One text. Some content follows after the heading."
    corpus = build_corpus_index(
        tmp_path, "d1", [_block(body)], outline_headings=["Heading One text."],
    )
    doc = open_doc(corpus, "d1", fresh_ledger)
    assert isinstance(doc, dict)
    assert len(doc["outline"]) == 1
    span = SpanID.model_validate(doc["outline"][0]["span_id"])
    assert fresh_ledger.was_issued(span) is True
```
D-ORC2's test is this with `is False`, plus an assertion that the ledger is *entirely* untouched.

**M6. Rejection-type assertion, and the "one behavior, one honestly-named test" rule** (`tests/tools/test_emit_finding.py:6-9` docstring, `:79-83`):

```python
    # Proof of REJECTION, not "emitted then caught": assert the return TYPE, not a
    # side-channel flag -- no Fault object is ever constructed on this path.
    assert isinstance(result, ToolRejected)
    assert result.reason_code == "not_byte_exact"
    assert not isinstance(result, Fault)
```
The `half` assertions are one more line each, at all 7 sites. The file's own docstring records
that it *replaced* a combined test with distinctly-named ones — do not regress that.

**M7. `test_verify_nondropping.py`'s target** (`src/agents/detection/verify.py:107-108`, `:117-122`, `:136-144`):

```python
def _dedup_key(f: Fault) -> tuple[str, str, str]:
    return (_norm(f.title)[:60], _norm(f.section), _norm(f.table_ref))
```
```python
    for f in faults:
        if f.evidence_class not in (EvidenceClass.CODE_VERIFIED, EvidenceClass.CHECKLIST):
            # A soft finding that concedes compliance in its own words is not a deficiency. ...
            if _concedes_compliance(f):
                dropped_self_negating += 1
                continue
```
```python
        key = _dedup_key(f)
        existing = kept.get(key)
        if existing is None:
            kept[key] = f
        elif _AUTHORITY[f.evidence_class] > _AUTHORITY[existing.evidence_class]:
```
`emit_finding` produces `QUOTE_ANCHORED` (`emit_finding.py:114`) → **not exempt** at `:117`; and
`title or "Deficiency"` + empty `section`/`table_ref` → every untitled agent finding collapses to
**one** `_dedup_key`. The test asserts `len(verify_and_tier(faults, doc)) < len(faults)` — i.e. it
documents that the legacy pass IS dropping, which is why the agent path bypasses it.

**M8. P2's parse test needs a synthetic PDF — `tests/unit/test_parse.py` is the WRONG shape to copy** (`tests/unit/test_parse.py:8-18`):

```python
SAMPLE_DIR = os.environ.get(
    "SAMPLE_DATA_DIR",
    "/Users/DEVDESAI1/Desktop/University_at_Buffalo/Projects/deficiency-chatbot/Sample Data",
)
...
skip_if_no_samples = pytest.mark.skipif(
    not os.path.exists(SPEC_PDF), reason="Sample PDFs not available"
)
```
Every test in that file is gated on a hard-coded absolute path. A P2 test written this way is
silently skipped in CI and proves nothing. Use the `fitz` builder instead
(`tests/ingest/conftest.py:122-144`):

```python
def _make_doc_bytes(content: str, ext: str) -> bytes:
    """Generate a real, parseable one-page PDF or DOCX whose body contains `content`.
    ...
    """
    if ext == ".pdf":
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), content)
        data = doc.tobytes()
        doc.close()
        return data
```
The P2 fixture must additionally make `is_scanned_page` return `True` — per `ocr.py:59-71` that
means a full-page image **or** a glyphless font — while still carrying an embedded text layer
`_digital_blocks` can read via `page.get_text("dict")` (`pdf.py:123`). `write_corpus_tree`
(`tests/ingest/conftest.py:147-167`) is the multi-file extension of the same builder if the
calibration corpus is synthesized (RESEARCH.md's option (b)).

---

## Shared Patterns

### S1 — Typed sentinel returns, never exceptions, at the model boundary
**Source:** `src/tools/errors.py:1-5` (the rule), `src/schemas/llm.py::ParseFailed` (the older twin)
**Apply to:** `oracles_tool.py`, `spanref.py`, `registry.py` dispatch, every loop-side validation

```python
"""ToolRejected -- the typed, self-correcting rejection sentinel every tool in src/tools/
RETURNS (never raises) on a bad call. Mirrors schemas.llm.ParseFailed's sentinel shape, chosen
over ingest.anchors.HashMismatch's exception shape because a tool rejection must flow back to
the CALLING MODEL as a message, not unwind a Python call stack (RESEARCH.md Pattern 3).
"""
```
The exception shape (`HashMismatch`, `anchors.py:29-43`) is reserved for the *substrate* layer,
where nothing model-facing can catch it. D-LOOP5 extends the sentinel rule up into the loop:
a rejection is a message the model reads, and it consumes a turn.

### S2 — Constructor/parameter injection, one instance per run, never a module global
**Source:** `src/tools/ledger.py:3-5`
**Apply to:** `BudgetLedger`, `TurnLog`, the `complete` callable, `ToolRegistry`

> *"Constructor-injected, never a module global (Security Domain V3 -- Pitfall 9): one instance
> per agent run, threaded explicitly through every tool call."*

Counter-example in the same codebase, and the reason the rule is written down: `llm/client.py:13`
holds `_client: OpenAI | None = None` as a module singleton, and `tests/ingest/conftest.py:57-59`
has to monkeypatch `llm.client.get_settings` to work around it. The rulebook store has the same
problem, which is why `emit_finding` threads `rulebook_cache_dir` explicitly (`emit_finding.py:20-27`).
**Every Phase-3 object the tests need to control must be a parameter.**

### S3 — Code gate first, model on top; the gate teaches via `hint`
**Source:** `src/tools/emit_finding.py:1-7`, every `ToolRejected(... hint=...)` construction
**Apply to:** budgets, breaker, DR, the AGENT-04 floor — all code, never prompt text

```python
"""The grounding gate (TOOLS-03, D-EF1) -- the ONLY path by which a Fault can exist.

Re-opens BOTH the submission quote and the cited rule clause via ingest.anchors.open_span
(never reimplemented), validates both span-IDs were actually issued THIS session (the
ledger -- D-GRAN selection-not-authoring), validates store membership ... and ONLY THEN
constructs a Fault. Every failure is a typed ToolRejected, never a raised exception.
"""
```
Every `hint` in `src/tools/` names the **next call to make**, e.g.
`hint="call open_doc first"` (`get_section.py:60`),
`hint="re-fetch via read_guideline, then cite the span-ID it returns"` (`emit_finding.py:64`).
D-LOOP5's `render_rejection` must surface `hint` (and `preview`/`handle`) or the gate becomes a
wall instead of a teacher.

### S4 — Decision-ID-annotated comments at every non-obvious line
**Source:** pervasive — `get_section.py:66-67` (`# TOOLS-04 persist+preview+handle (plan-checker Blocker 2)`), `emit_finding.py:94-97` (`# Phase 2 has no compliance-verdict CLASSIFICATION logic yet (DETECT-04 lands in Phase 3)`), `follow_reference.py:36-38` (`# ... (D-30: declare the boundary, never fake resolution)`), `ledger.py:3` (`# Security Domain V3 -- Pitfall 9`)
**Apply to:** every new file. This codebase's comments carry the *decision that forced the code*,
not a restatement of the code. Phase 3's `D-BUD*`/`D-TEL*`/`D-LOOP*`/`D-ORC*` IDs go in the same
position. The planner should make this an acceptance criterion — it is how the repo stays
auditable across phases.

### S5 — Version-stamped, content-addressed identity
**Source:** `anchors.py:17-26` (`short_hash(canonical_substr, normalizer_version)`), `store.py:35-39`, `normalize.py:35-36`, `serialize.py:22`
**Apply to:** `PARSER_VERSION`, `HARNESS_VERSION`, `MATCHER_VERSION`, the corpus content-hash in the D-TEL1 provenance block

```python
def short_hash(canonical_substr: str, normalizer_version: str) -> str:
    """Short content-hash of a canonical substring bound to the normalizer version (D-19/D-24).
    ... a normalization change shifts the substring and the hash fails loudly on re-open, while
    the version stamp distinguishes an intentional change from tampering.
    """
    payload = (normalizer_version + "\x00" + canonical_substr).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=8).hexdigest()
```

### S6 — Offline / no-external-dependency test design (D-RB6)
**Source:** `tests/tools/conftest.py:1-14`, `tests/ingest/conftest.py:1-23`, `tests/tools/test_enumerate_fetch_emit_e2e.py:11-13`, `tests/tools/test_emit_finding.py:36-46` (tmp_path-scoped rulebook store)
**Apply to:** every Wave-0 test. Real primitives + `tmp_path` isolation, never a mock of the thing
under test. Note the guard convention in `test_enumerate_fetch_emit_e2e.py:38-41`:
`update_manifest=False` on every rulebook build — *"this fixture must NEVER rewrite the committed
`rulebook/manifest.yaml`."* Phase-3 tests that touch `data/ingest_cache/` need the same
discipline. **There is no CI workflow** (`.github/workflows/` does not exist), so this is
currently enforced by test design alone.

### S7 — UI progress events (additive, closed Literal)
**Source:** `src/schemas/events.py:7-19`, `src/agents/event_bus.py:37-43`, call sites `pipeline.py:44-92`
```python
def emit_sync(job_id: str, layer: str, event_type: str, agent_name: str = "", message: str = "") -> None:
    event = AgentEvent(job_id=job_id, layer=layer, event_type=event_type, agent_name=agent_name, message=message)
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(emit, event)
    except RuntimeError:
        emit(event)
```
`emit_sync` tolerates both running-loop and no-loop contexts and `job_id=""` (the harness passes
`""` — `evals/run.py:245`). `EventType` is a **closed `Literal` with 9 members** and `LayerName`
is `Literal["parse","detection"]` — agent-step events must **add** members. `AgentEvent.metadata:
dict` (`events.py:29`) is the right carrier for per-turn numbers so `message` stays human-readable.
Note `emit_sync`'s signature has no `metadata` parameter — adding one is a further additive change.

---

## No Analog Found

Files/mechanisms with no close match in the codebase. The planner should use RESEARCH.md's
prescribed shapes and budget extra review for these three.

| Item | Role | Data flow | Why there is no analog |
|------|------|-----------|------------------------|
| **JSONL append-stream writer** (inside `src/agents/review/telemetry.py`) | service | streaming file-I/O | `grep -rn "jsonl\|JSONL" src/ tests/ --include=*.py` returns **nothing**. All existing persistence is whole-file (`store.write_doc_cache`, `run._write_metrics`) or SQLite (`store.save_manifest`). The atomic temp→rename convention (S5/F1) **cannot** apply to an append stream — this is a genuinely new durability shape, and its failure mode (a truncated final line on an aborted run) must be handled by the reader. |
| **Git-SHA / provenance capture** (D-TEL1(i): the pre-registration file's commit SHA) | utility | transform | `grep -rn "subprocess\|git rev-parse\|GIT_SHA" src/ --include=*.py` returns **nothing** — no module in `src/` shells out or reads git state. A new helper is required, and it must degrade gracefully (a missing SHA is a *recorded* `""`, not a crash — same discipline as `run.py`'s `_load_source_text` degrading to `""`). |
| **`ScriptedChatClient` / `ForcedRunaway` LLM test doubles** | test fixture | request-response | No test in the repo drives an LLM-calling code path with a scripted stand-in. The 3 existing patterns are (a) monkeypatch `get_settings` to no-creds so the call **degrades** (`tests/ingest/conftest.py:46-59`), (b) skip the test entirely, (c) replay a captured `FaultReport` (`evals/capture.py:16-18`) — none of which exercises a multi-turn loop. RESEARCH.md § Validation Architecture supplies the shape; DI (Pattern 1) is what makes it possible without monkeypatching. |

**Partial-analog warnings (analog exists but must be inverted, not copied):**

| Item | Analog | The inversion |
|------|--------|---------------|
| `src/agents/review/prompts.py` | `src/agents/detection/prompts.py` | Copy the module-constant shape; **reject** the `{}` + `.format()` templating (4 call sites) — D-LOOP4 requires a placeholder-free system prompt. |
| `run_oracles`-the-tool's ledger behavior | all six Phase-2 tools call `ledger.record_span` | D-ORC2 forbids it. This is the **only** tool that must not issue spans. |
| P2's parse test | `tests/unit/test_parse.py` | That file is gated on a hard-coded absolute `SAMPLE_DATA_DIR` path (`:8-18`) — every test in it skips in CI. Build a synthetic PDF with `fitz` instead (`tests/ingest/conftest.py:122-144`). |
| `_write_metrics` for run summaries | `src/evals/run.py:128-131` | It is not atomic (`out.write_text` directly). Use `store.write_doc_cache`'s temp→`os.replace` for the committed summaries, since a half-written summary is indistinguishable from an aborted run — the exact ambiguity D-TEL1(i) exists to prevent. |

---

## Metadata

**Analog search scope:** `src/tools/`, `src/llm/`, `src/agents/`, `src/agents/detection/`,
`src/schemas/`, `src/evals/`, `src/ingest/`, `src/parse/`, `src/config.py`, `tests/tools/`,
`tests/ingest/`, `tests/unit/`, `tests/agents/`
**Files scanned:** 61 source (7,430 lines) + 56 test (5,798 lines) enumerated; 27 read in full or
in targeted ranges
**Verification commands run this session:**
- `grep -rn "jsonl\|JSONL" src/ tests/ --include=*.py` → no matches
- `grep -rn "subprocess\|git rev-parse\|GIT_SHA" src/ --include=*.py` → no matches
- `grep -rn "_VERSION = " src/` → 4 matches (`normalize.py:35,36`, `serialize.py:22`, `requirement_index.py:42`) — none in `src/evals/`
- `wc -c src/evals/__init__.py` → **0 bytes**
- `ls tests/agents/` → `__init__.py`, `detection/` only — `tests/agents/review/` does not exist

**Pattern extraction date:** 2026-08-01
**Consistent with:** `03-CONTEXT.md` (23 locked decisions), `03-RESEARCH.md` (§Code Reconnaissance
D1–D10, §Validation Architecture, §Common Pitfalls 1–10). Where this document and RESEARCH.md
overlap, the `file:line` citations here were re-verified against the working tree at `9b68856`
this session.
