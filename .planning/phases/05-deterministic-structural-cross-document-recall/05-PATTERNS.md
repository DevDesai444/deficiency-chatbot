# Phase 5: Deterministic Structural & Cross-Document Recall (β) - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 17 new/modified files
**Analogs found:** 17 / 17

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/schemas/faults.py` | model | transform | `src/schemas/faults.py` (self — additive extension) | exact |
| `src/rulebook/structural.py` | service | CRUD/transform | `src/rulebook/absence.py` | exact (same role: pure-function deterministic pass) |
| `src/rulebook/references.py` | service | event-driven/graph | `src/rulebook/absence.py` + `src/rulebook/edges.py` | role-match |
| `src/rulebook/precedent_search.py` | service | CRUD/similarity | `src/rulebook/absence.py` + `src/rulebook/store.py` | role-match |
| `src/rulebook/guard_vocab.py` | config/utility | transform | `tests/evals/test_generality_guard.py` (denylist constants) | partial |
| `src/tools/emit_finding.py` | service/gate | request-response | `src/tools/emit_finding.py` (self — additive `emit_structural_finding` / `emit_reference_finding` / `emit_precedent_finding`) | exact |
| `src/tools/follow_reference.py` | service | request-response | `src/tools/follow_reference.py` (self — fill Phase-4 stub) | exact |
| `src/tools/search_corpus.py` | service | CRUD/retrieval | `src/tools/search_corpus.py` (self — D-R5B persist path) | exact |
| `src/tools/errors.py` | utility | transform | `src/tools/errors.py` (self — additive reason codes) | exact |
| `src/ingest/corpus.py` | service | file-I/O | `src/ingest/corpus.py` (self — D-R5B persist at ingest) | exact |
| `src/retrieval/hybrid.py` | utility | transform | `src/retrieval/hybrid.py` (self — D-R5A cosine score) | exact |
| `tests/rulebook/test_structural.py` | test | CRUD | `tests/rulebook/test_absence.py` | exact |
| `tests/rulebook/test_references.py` | test | event-driven | `tests/rulebook/test_absence.py` + `tests/rulebook/test_edges.py` | role-match |
| `tests/rulebook/test_precedent_search.py` | test | CRUD | `tests/rulebook/test_absence.py` + `tests/rulebook/conftest.py` | role-match |
| `tests/tools/test_emit_structural_finding.py` | test | request-response | `tests/tools/test_emit_absence_finding.py` | exact |
| `tests/tools/test_emit_reference_finding.py` | test | request-response | `tests/tools/test_emit_absence_finding.py` | exact |
| `tests/evals/test_generality_guard.py` | test | transform | `tests/evals/test_generality_guard.py` (self — extend) | exact |
| `tests/ingest/test_corpus_index_persistence.py` | test | file-I/O | `tests/ingest/test_corpus.py` | role-match |
| `src/evals/dataset/synthetic_fixture/` | config/data | batch | `tests/ingest/fixtures/` | partial |
| `src/evals/baseline/structural_threshold.json` | config | — | `src/evals/baseline/absence_threshold.json` | exact |
| `src/evals/baseline/precedent_threshold.json` | config | — | `src/evals/baseline/absence_threshold.json` | exact |
| `src/evals/run.py` | utility/CLI | batch | `src/evals/run.py` (self — add structural-gate subcommand) | exact |

---

## Pattern Assignments

### `src/schemas/faults.py` (model, transform) — additive extension

**Analog:** `src/schemas/faults.py` (self)

**Imports pattern** (lines 1-18):
```python
from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, Field
from schemas.documents import SpanID
from schemas.flaws import FlawCategory, Severity, SimilarDeficiency
from schemas.llm import ParseFailed
```

**Existing anchor pattern** (lines 68-101) — copy this shape for all three new anchors:
```python
class CoverageAbsenceAnchor(BaseModel):
    """...typed anchor: enumerate inputs + sub-threshold retrieval evidence + manifest span-IDs..."""
    profile: list[str] = Field(default_factory=list, ...)
    family: str = Field(default="", ...)
    requirement_id: str = Field(default="", ...)
    threshold: float = Field(default=0.0, ...)
    sub_threshold_hits: list[RetrievalHit] = Field(default_factory=list, ...)
    manifest_span_ids: list[SpanID] = Field(default_factory=list, ...)
    claim_span_id: SpanID | None = Field(default=None, ...)
```

**New anchors to add — follow this exact pattern with sibling class definitions:**
```python
class StructuralAnchor(BaseModel):
    """D-STR3: Re-derivable structural inconsistency anchor.
    The verifier RE-RUNS the comparison; never trusts the stored snapshot."""
    claim_span_id: SpanID = Field(description="The cell/span asserting the claim value.")
    basis_span_ids: list[SpanID] = Field(description="The N basis cells the claim was computed from.")
    relation: Literal["EQUALS", "LEQ", "GEQ", "SUM", "MAX", "MIN", "MEAN"] = Field(...)
    expected_value: str = Field(description="Re-derived expected value as a string (raw text from basis cells).")
    actual_value: str = Field(description="Value in the claim span (verbatim).")
    comparison_store: Literal["CORPUS", "RULEBOOK"] = Field(default="CORPUS", ...)
    scoping_confidence: Literal["full", "low"] = Field(default="full",
        description="D-ABS2: 'low' when a contributing cell was not cleanly addressable.")

class ReferenceAnchor(BaseModel):
    """D-REF2: One cross-reference edge with anomaly classification."""
    src_span_id: SpanID = Field(description="The span containing the reference text in the source doc.")
    dst_span_id: SpanID | None = Field(default=None, description="The target span if resolved; None if unresolved.")
    edge_type: Literal["hyperlink", "textual_ref", "value_crossref"] = Field(...)
    anomaly: Literal["UNRESOLVED_REF", "ABSENT_TARGET", "VALUE_CONTRADICTION"] = Field(...)
    scoping_confidence: Literal["full", "low"] = Field(default="full",
        description="D-REF3: 'low' for label-match-only contradictions (no direct edge).")

class PrecedentAnchor(BaseModel):
    """D-PRC2: Section-level precedent similarity evidence (not a finding source itself)."""
    submission_span_id: SpanID = Field(description="The submission section span that triggered this candidate.")
    precedent_doc_ids: list[str] = Field(description="doc_ids of matching precedent chunks (supporting evidence only).")
    similarity_scores: list[float] = Field(description="Dense cosine scores corresponding to precedent_doc_ids.")
    threshold: float = Field(description="The general threshold this run used.")
    anda_excluded: list[str] = Field(default_factory=list,
        description="D-PRC3: ANDA numbers excluded from results (same-ANDA filter).")
```

**Additive Fault fields** (follow line 101 `absence_anchor: CoverageAbsenceAnchor | None = Field(default=None, ...)`):
```python
# Add as siblings of absence_anchor at line ~101–103 (additive, no existing field changes):
structural_anchor: StructuralAnchor | None = Field(default=None,
    description="D-STR3: re-derivable structural inconsistency anchor; mutually exclusive with absence_anchor.")
reference_anchor: ReferenceAnchor | None = Field(default=None,
    description="D-REF2: cross-reference edge + anomaly; mutually exclusive with other anchors.")
precedent_anchor: PrecedentAnchor | None = Field(default=None,
    description="D-PRC2: precedent similarity evidence; mutually exclusive with other anchors.")
leg_tag: Literal["ABSENCE", "STRUCTURAL", "REFERENCE", "PRECEDENT"] | None = Field(default=None,
    description="D-ENV1: which recall leg produced this Fault.")
```

---

### `src/rulebook/structural.py` (service, transform) — new file, RECALL-02

**Analog:** `src/rulebook/absence.py`

**Imports pattern** (copy from `absence.py` lines 22-40, adapt for structural):
```python
from __future__ import annotations
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from rulebook.guard_vocab import AGGREGATE_LEXICON  # D-GRD3 registry
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.documents import SpanID
from schemas.faults import StructuralAnchor, Fault
from tools.emit_finding import emit_structural_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
```

**Module docstring pattern** (copy from `absence.py` lines 1-21, adapt):
```python
"""The deterministic structural inconsistency pass (RECALL-02, D-STR1–D-STR6).

`detect_structural_inconsistencies` is a PURE FUNCTION over `(corpus, manifest, ledger)`.
NOT a drive-cycle tool. It composes:

    get_table_cells (table_index from corpus cache, D-STR5)
        -> _scan_table_for_aggregates (AGGREGATE_LEXICON from guard_vocab.py, D-GRD3)
        -> emit_structural_finding (the byte-exact grounding gate)

No submission-specific constant -- batch number, doc name, spec value, section path -- ever
appears here (D-GEN2 anti-overfitting law). The AGGREGATE_LEXICON is a general label vocabulary
registered in guard_vocab.py, not an inline constant (D-GRD3).
"""
```

**Core detection pattern** (model on `absence.py:90-172`, adapt for structural):
```python
def detect_structural_inconsistencies(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
) -> list[Fault]:
    """Pure deterministic structural pass: table-cell aggregate recompute + limit exceedance.
    Returns every grounded structural Fault (verdict VIOLATION). Over-emits low-confidence
    findings (D-ABS2 over-emit style) rather than dropping when a cell is not cleanly addressable.
    """
    faults: list[Fault] = []
    for doc_entry in manifest.documents:
        if doc_entry.tables != "addressable":
            # D-STR5: table-tier-unavailable -> log + route to Phase 7, never drop silently.
            log.info("structural_skip_unavailable_tables", doc_id=doc_entry.doc_id,
                     tables=doc_entry.tables, routed_to="phase_7")
            continue
        cache = corpus.cached_entry(doc_entry.doc_id)
        if cache is None:
            continue
        table_cells = _get_table_cells(cache)
        by_table = _group_by_table(table_cells)
        for table_id, cells in by_table.items():
            faults.extend(_scan_aggregate_consistency(cells, doc_entry, corpus, ledger, rulebook_cache_dir))
    return faults
```

**Table grid reconstruction pattern** (derived from `tables.py:37-53` key convention):
```python
def _get_table_cells(cache: dict) -> dict[tuple, SpanID]:
    """Returns {(table_id, row, col): SpanID} for all addressable cells (D-STR5)."""
    from schemas.documents import SpanID
    table_index_raw = cache.get("table_index", {})
    result = {}
    for key, span_dict in table_index_raw.items():
        parts = key.split(",", 2)          # Pitfall 1: table_id may be "" -> key starts with ","
        if len(parts) == 3:
            table_id, row, col = parts[0], int(parts[1]), int(parts[2])
            result[(table_id, row, col)] = SpanID.model_validate(span_dict)
    return result

def _group_by_table(cells: dict) -> dict[str, dict[tuple, SpanID]]:
    from collections import defaultdict
    by_table: dict[str, dict[tuple[int,int], SpanID]] = defaultdict(dict)
    for (table_id, row, col), span in cells.items():
        by_table[table_id][(row, col)] = span
    return by_table
```

**Value normalization pattern** (D-STR4 — no epsilon, no free parameter):
```python
import re

def _stated_precision(text: str) -> int:
    """Count decimal digits in the first numeric value in text."""
    m = re.search(r'(\d+)\.(\d+)', text)
    return len(m.group(2)) if m else 0

def compare_values(claim_text: str, ref_text: str, comparator: str) -> bool | None:
    """Returns True=violation, False=complies, None=abstain (D-STR4).
    Precision-derived, unit-aware, no epsilon constant."""
    try:
        claim_num = float(re.search(r'[\d.]+', claim_text).group())
        ref_num = float(re.search(r'[\d.]+', ref_text).group())
    except (AttributeError, ValueError):
        return None  # abstain on unparseable
    prec = min(_stated_precision(claim_text), _stated_precision(ref_text))
    rounded_claim = round(claim_num, prec)
    rounded_ref = round(ref_num, prec)
    if comparator in ("LEQ", "NMT"):
        return rounded_claim > rounded_ref
    elif comparator in ("GEQ", "NLT"):
        return rounded_claim < rounded_ref
    elif comparator == "EQUALS":
        return rounded_claim != rounded_ref
    return None
```

**Merged-cell deduplication** (Pitfall 2 — deduplicate basis spans before recompute):
```python
def _deduplicate_basis(basis: list[SpanID]) -> list[SpanID]:
    """Pitfall 2: merged cells share one SpanID. Deduplicate by (doc_id,start,end)."""
    seen = set()
    unique = []
    for s in basis:
        key = (s.doc_id, s.start, s.end)
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique
```

**NO-CONSTANT constraint:** this module must import thresholds only from config/JSON, never inline floats (except 0.0/1.0 sentinels). The `AGGREGATE_LEXICON` must be imported from `guard_vocab.py`, never defined inline.

---

### `src/rulebook/references.py` (service, graph) — new file, RECALL-03

**Analog:** `src/rulebook/absence.py` (detection-pass structure) + `src/rulebook/edges.py` (graph backing)

**Imports pattern:**
```python
from __future__ import annotations
import re
import zipfile
import xml.etree.ElementTree as ET
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest, DocEntry
from rulebook.edges import add_edge, get_edges
from rulebook.guard_vocab import REFERENCE_CUE_WORDS   # D-GRD3 registry
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.documents import SpanID
from schemas.faults import ReferenceAnchor, Fault
from tools.emit_finding import emit_reference_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
```

**Edge registration pattern** (from `edges.py:30-46` — provenance always required):
```python
def _register_edge(src_span: SpanID, dst_span: SpanID | None, edge_type: str, db_path: str) -> None:
    """D-RB3: every edge carries a provenance span-ID. add_edge rejects empty provenance."""
    import json
    prov = json.dumps(src_span.model_dump())
    src_id = f"{src_span.doc_id}:{src_span.start}"
    dst_id = f"{dst_span.doc_id}:{dst_span.start}" if dst_span else "unresolved"
    add_edge(src_id, dst_id, edge_type, prov, db_path=db_path)
```

**ABSENT_TARGET manifest check pattern** (D-REF5 — consult coverage manifest first):
```python
def _assess_absent_target(target_doc_id: str, manifest: CoverageManifest,
                           is_table_ref: bool) -> tuple[str, str]:
    """Returns (anomaly, scoping_confidence) for a missing target. D-REF5."""
    target_entry = next((d for d in manifest.documents if d.doc_id == target_doc_id), None)
    if target_entry is None:
        return "ABSENT_TARGET", "full"   # genuinely not in submission
    if target_entry.status in ("parse_failed", "unsupported"):
        return "ABSENT_TARGET", "low"    # declared boundary -> Phase 7
    if is_table_ref and target_entry.tables == "unavailable":
        return "ABSENT_TARGET", "low"    # table-tier-unavailable -> Phase 7
    return "ABSENT_TARGET", "low"        # present but referent genuinely missing
```

**General textual reference patterns** (D-REF1 — must be registered in guard_vocab allowlist, NOT inline corpus literals):
```python
# These patterns are GENERAL (match any CTD path, not a specific one).
# Registered in guard_vocab.REFERENCE_CUE_WORDS to satisfy D-GRD3.
_REF_PATTERNS = [
    re.compile(r"(?:see|refer to|as (?:described|stated) in|per)\s+§?\s*([\d\.]+[A-Za-z\.]*)"),
    re.compile(r"\b[Tt]able\s+(\d+[\w\-]*)"),
    re.compile(r"(?:Module|Section)\s+(3\.2\.[SP]\.[\d\.]+)"),  # D-GRD3: general CTD pattern, not a literal
]
# NOTE: Pitfall 6 — the CTD pattern above is a general EXTRACTOR regex (allowed by guard_vocab)
# NOT a corpus literal like "3.2.S.4.1". The NO-CONSTANT scan must treat re.compile(r"...") in
# extractor context as allowlisted. See guard_vocab.py for registration.
```

**fill follow_reference stub** (lines 18-39 of `follow_reference.py`):
```python
# NEW: after same-doc outline search succeeds, fallback replaces the _CROSS_DOC_PENDING sentinel:
edges = get_edges(src_id=f"{doc_id}:{ref_span_start}", db_path=db_path)
if edges:
    dst_doc_id, dst_start = edges[0][1].split(":")
    # resolve dst span and return:
    return {"doc_id": dst_doc_id, "resolved": True, "span_id": ..., "status": "resolved_cross_doc"}
# No edge -> honest boundary:
anomaly = "UNRESOLVED_REF"
return {"doc_id": doc_id, "ref_text": ref_text, "status": anomaly}
```

---

### `src/rulebook/precedent_search.py` (service, similarity) — new file, RECALL-04

**Analog:** `src/rulebook/absence.py` (pure-function detection pass structure) + `src/rulebook/store.py` (FAISS query path)

**Imports pattern:**
```python
from __future__ import annotations
import numpy as np
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from rulebook.precedents import get_provenance
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR, _rulebook_search_local, _faiss_doc_ids, _ensure_faiss
from retrieval.vector_search import embed_query
from schemas.documents import SpanID
from schemas.faults import PrecedentAnchor, Fault
from tools.emit_finding import emit_precedent_finding
from tools.ledger import RetrievalLedger
```

**FAISS precedent filter pattern** (from `store.py:209-244` + `precedents.py:155` doc_id prefix):
```python
def _filter_precedent_chunks(raw_results, submission_anda_number: str | None,
                              threshold: float) -> list[tuple[str, float]]:
    """Filter rulebook FAISS results to precedent-only, above-threshold, ANDA-excluded (D-PRC3).

    CRITICAL: use data/rulebook.faiss (Phase-2 substrate) NOT data/deficiency_kb.faiss (old index).
    Pitfall 4: deficiency_kb.faiss maps to SQLite rowids; rulebook.faiss maps to RuleChunk doc_ids.
    """
    _ensure_faiss()
    # Filter by "precedent-" prefix (src/rulebook/precedents.py:155 -- precedent doc_ids start with this)
    precedent_results = [c for c in raw_results if c.doc_id.startswith("precedent-")]
    filtered = []
    for chunk in precedent_results:
        if submission_anda_number:
            provenance = get_provenance(chunk.doc_id)
            if any(str(p.get("anda_number")) == submission_anda_number for p in provenance):
                continue  # D-PRC3 same-ANDA exclusion
        filtered.append(chunk)
    return filtered
```

**Dense cosine similarity** (needed for threshold comparison — `_rulebook_search_local` does not return scores):
```python
def _cosine_score(query_embedding: np.ndarray, chunk_doc_id: str) -> float:
    """Compute actual dense cosine for threshold gating (D-PRC4 absolute threshold)."""
    import faiss
    _ensure_faiss()
    if _faiss_index is None:
        return 0.0
    # Re-query with top-1 to get score for specific chunk — or cache the scores from the FAISS search
    # Preferred: extract scores during the initial FAISS search (indices + distances from IndexFlatIP)
    # IndexFlatIP returns inner products; with L2-normalized vectors, IP == cosine similarity
    ...
```

**Section embedding pattern** (D-PRC1 — embed submission section text, not the doc):
```python
def search_precedents(
    section_text: str,
    top_k: int = 5,
    threshold: float = 0.6,           # D-PRC4: general, not corpus-tuned; read from JSON baseline
    submission_anda_number: str | None = None,  # D-PRC3: None -> no same-ANDA exclusion
    db_path: str = "data/defpredict.db",
) -> list[tuple[str, float]]:
    """Returns [(precedent_doc_id, cosine_score)] above threshold, same-ANDA excluded.
    Pitfall 3: skip sections with len(section_text) < 100 (degenerate bge-m3 embeddings)."""
    if len(section_text) < 100:
        return []  # Pitfall 3: too short for stable bge-m3 cosine
    results = _rulebook_search_local(section_text, top_k * 3)
    return _filter_precedent_chunks(results, submission_anda_number, threshold)
```

**NO-CONSTANT constraint:** The `threshold` parameter must be read from `src/evals/baseline/precedent_threshold.json` at call site (same pattern as `absence.py` reading `absence_threshold.json`). Never inline the float in this module.

---

### `src/rulebook/guard_vocab.py` (config, utility) — new file, D-GRD3

**Analog:** `tests/evals/test_generality_guard.py` (lines 48-63 — existing denylist constants structure)

**Core pattern** (D-GRD3 — registry, not inline constants):
```python
"""Registered general-vocabulary allowlists (D-GRD3).

Every entry asserted to contain no corpus-specific token (doc name, ANDA#, specific value,
specific CTD section path). These vocabularies are ALLOWED by the NO-CONSTANT guard scan;
any OTHER inline string literal matching corpus-specific patterns is flagged.

Adding a vocabulary set here is REQUIRED before using it in structural.py / references.py;
adding without review is blocked by the test that asserts each entry contains no corpus token.
"""
from __future__ import annotations

# General aggregate label vocabulary (D-STR1/D-GRD3). Case-insensitive match in structural.py.
AGGREGATE_LEXICON: frozenset[str] = frozenset({
    "total", "sum", "maximum", "max", "minimum", "min", "average", "mean"
})

# General reference cue-word vocabulary (D-REF1/D-GRD3). Allowlists general regex patterns
# in references.py that EXTRACT any CTD path -- not literals matching a specific path.
REFERENCE_CUE_WORDS: frozenset[str] = frozenset({
    "see", "refer", "table", "section", "module", "figure", "appendix",
    "as described in", "as stated in", "per", "referenced in"
})
# Assertion enforced by test: no entry is a corpus-specific token.
```

---

### `src/tools/emit_finding.py` (gate/service) — additive extension

**Analog:** `src/tools/emit_finding.py` self — `emit_absence_finding` (lines 137-230)

**Imports addition:**
```python
# Add to existing imports (line 35):
from schemas.faults import ComplianceVerdict, CoverageAbsenceAnchor, StructuralAnchor, \
    ReferenceAnchor, PrecedentAnchor, EvidenceClass, Fault, Tier
```

**New function `emit_structural_finding`** — copy the `emit_absence_finding` gate skeleton (lines 137-230), adapt:
```python
def emit_structural_finding(
    corpus: CorpusIndex,
    rule_span_id: SpanID | None,          # D-STR6: nullable for pure arithmetic checks
    structural_anchor: StructuralAnchor,
    ledger: RetrievalLedger,
    title: str = "",
    detail: str = "",
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
) -> Fault | ToolRejected:
    # 1. RULE half (D-STR6: nullable for labeled-aggregate checks with no specific rule):
    if rule_span_id is not None:
        if not ledger.was_issued(rule_span_id):
            return ToolRejected(tool="emit_structural_finding",
                                reason_code="not_retrieved_this_session", half="rule", ...)
        rule_nt = rulebook_nt_for(rule_span_id.doc_id, cache_dir=rulebook_cache_dir)
        if rule_nt is None:
            return ToolRejected(tool="emit_structural_finding",
                                reason_code="wrong_store", half="rule", ...)
        try:
            open_span(rule_span_id, rule_nt, rule_span_id.doc_id)
        except HashMismatch:
            return ToolRejected(tool="emit_structural_finding",
                                reason_code="not_byte_exact", half="rule", ...)

    # 2. Claim span (always required for STRUCTURAL — it is the submission span):
    claim = structural_anchor.claim_span_id
    if not ledger.was_issued(claim):
        return ToolRejected(tool="emit_structural_finding",
                            reason_code="not_retrieved_this_session", half="submission", ...)
    corpus_cache = corpus.cached_entry(claim.doc_id)
    if corpus_cache is None:
        return ToolRejected(tool="emit_structural_finding",
                            reason_code="wrong_store", half="submission", ...)
    claim_nt = NormalizedText(canonical=corpus_cache["canonical"], ...)
    try:
        open_span(claim, claim_nt, claim.doc_id)
    except HashMismatch:
        return ToolRejected(tool="emit_structural_finding",
                            reason_code="not_byte_exact", half="submission", ...)

    # 3. Re-derivability check (D-GATE2 equivalent for structural):
    deduped = _deduplicate_basis(structural_anchor.basis_span_ids)  # Pitfall 2
    if not deduped:
        return ToolRejected(tool="emit_structural_finding",
                            reason_code="unanchored_structural", half="submission",
                            reason="structural anchor has no independent basis spans to recompute from", ...)

    return Fault(
        title=title or "Structural inconsistency",
        detail=detail,
        tier=Tier.VERIFIED,              # code-verified arithmetic computation
        evidence_class=EvidenceClass.CODE_VERIFIED,
        confidence=0.9,
        verdict=ComplianceVerdict.VIOLATION,
        rule_span_id=rule_span_id,        # may be None for pure arithmetic (D-STR6)
        submission_span_id=structural_anchor.claim_span_id,
        structural_anchor=structural_anchor,
        leg_tag="STRUCTURAL",
        source="tool:emit_structural_finding",
    )
```

**New reason codes to add to `src/tools/errors.py`** (additive, follow `KNOWN_REASON_CODES` at line 47):
```python
"unanchored_structural": "emit_structural_finding's StructuralAnchor has no independent basis spans (Pitfall 2: all basis spans deduplicate to the same merged cell).",
"unanchored_reference": "emit_reference_finding's ReferenceAnchor is missing a source span.",
"no_comparison_basis": "Structural comparison has fewer than 2 independent basis cells; abstaining (D-STR3).",
```

---

### `src/tools/follow_reference.py` (service) — fill Phase-4 stub

**Analog:** `src/tools/follow_reference.py` self (lines 1-39)

**Pattern:** Keep same-doc outline search (lines 28-36) unchanged. Replace the cross-doc `_CROSS_DOC_PENDING` fallback (line 38) with real graph lookup:
```python
from rulebook.edges import get_edges   # add to imports

# After same-doc outline search fails (replacing line 37-39):
# Check the reference graph for a cross-document edge:
# src_id format: "{doc_id}:{ref_span_start}" — same format add_edge uses in references.py
src_key = f"{doc_id}:0"  # simplified; real impl uses the matched span's start offset
edges = get_edges(src_id=src_key, db_path=db_path)
if edges:
    _src, dst_id, edge_type, prov_json = edges[0]
    # dst_id format: "{dst_doc_id}:{dst_start}" (set by references.py's _register_edge)
    dst_parts = dst_id.split(":", 1)
    if len(dst_parts) == 2 and dst_parts[1].isdigit():
        dst_doc_id, dst_start = dst_parts[0], int(dst_parts[1])
        # Mint or fetch the dst span and record it in the ledger:
        cache = corpus.cached_entry(dst_doc_id)
        if cache:
            span = SpanID(doc_id=dst_doc_id, start=dst_start, end=dst_start + 1, hash="")  # refetch
            ledger.record_span(span)
            return {"doc_id": dst_doc_id, "resolved": True, "span_id": span.model_dump(),
                    "edge_type": edge_type, "label": ref_text}

# Still unresolved — honest boundary (same shape as before, but rename sentinel):
return {"doc_id": doc_id, "ref_text": ref_text, "status": "UNRESOLVED_REF"}
```

---

### `src/tools/search_corpus.py` (service, retrieval) — D-R5A + D-R5B

**Analog:** `src/tools/search_corpus.py` self (lines 1-80)

**D-R5A — return dense cosine instead of RRF score** (lines 63-79):
```python
# CURRENT (line 63-66):
fused = reciprocal_rank_fusion([lexical_ranked, dense_ranked])[:top_k]
for cid, score in fused:  # score here is RRF score (max 0.0328 < 0.04 threshold -> dead branch)

# AFTER D-R5A change:
# Preserve dense cosine scores from before RRF:
dense_scores = {chunk_ids[i]: float(scores[i]) for i in dense_order}  # 0-1 range cosine

fused = reciprocal_rank_fusion([lexical_ranked, dense_ranked])[:top_k]
for cid, rrf_score in fused:
    doc_id, start, end, text, nv = by_chunk_id[cid]
    ...
    out.append({
        "doc_id": doc_id, "span_id": span.model_dump(),
        "score": dense_scores.get(cid, 0.0),   # CHANGED: dense cosine (0-1 real range)
        "rrf_score": rrf_score,                  # preserved for ordering reference
        "snippet": f"[{doc_id}:{start}:{end}] {text}",
    })
```

**D-R5B — load prebuilt index at query (replace rebuild-per-query path)**:
```python
# New helper at module top (before search_corpus):
def _index_sidecar_paths(cache_dir: str, key: str) -> tuple[Path, Path, Path]:
    """Sidecar paths for BM25 tokens + embeddings + chunk metadata, keyed by content-hash key."""
    from pathlib import Path
    base = Path(cache_dir) / key
    return base.with_suffix(".chunks.json"), base.with_suffix(".embeddings.npy"), base.with_suffix(".bm25.json")

def _has_persisted_index(corpus: CorpusIndex) -> bool:
    """True if ALL docs have persisted index sidecars (D-R5B)."""
    from ingest.store import cache_key
    from parse.pdf import PARSER_VERSION
    from ingest.normalize import NORMALIZER_VERSION
    from ingest.serialize import SERIALIZER_VERSION
    for entry in corpus.manifest.documents:
        if entry.status not in ("parsed", "parsed_partial"):
            continue
        key = cache_key(entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
        chunks_path, _, _ = _index_sidecar_paths(corpus.cache_dir, key)
        if not chunks_path.exists():
            return False
    return True

# Modified search_corpus:
def search_corpus(corpus: CorpusIndex, query: str, ledger: RetrievalLedger, top_k: int = 10) -> list[dict]:
    if _has_persisted_index(corpus):
        return _search_with_persisted_index(corpus, query, ledger, top_k)
    return _search_legacy(corpus, query, ledger, top_k)   # backward compat fallback
```

**D-R5B — build and persist index at ingest** (add to `src/ingest/corpus.py` at line ~159, after `write_doc_cache`):
```python
# After write_doc_cache call (line 165), persist index sidecars atomically:
from tools.search_corpus import build_doc_index  # new helper
build_doc_index(cache_dir, key, nt, doc_id)      # writes .chunks.json, .embeddings.npy, .bm25.json
# Atomic write pattern from ingest/store.py:write_doc_cache (lines 56-67):
# tmp = final.with_suffix(".tmp"); tmp.write_text(...); os.replace(tmp, final)
```

---

### `src/retrieval/hybrid.py` (utility, transform) — D-R5A supporting change

**Analog:** `src/retrieval/hybrid.py` self (lines 1-10)

This file is read-only by the pattern change (the cosine score is computed before calling RRF in `search_corpus.py`). The only potential change here: expose a `cosine_similarity(a, b)` utility function if needed by `structural.py` for the comparison engine. The existing `reciprocal_rank_fusion` signature stays unchanged.

---

### `tests/rulebook/test_structural.py` (test, RECALL-02) — new file

**Analog:** `tests/rulebook/test_absence.py` (lines 1-60+) — exact role match

**Imports pattern** (mirror `test_absence.py` lines 1-25):
```python
from __future__ import annotations
import pytest
import rulebook.requirement_index as ri
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest, DocEntry, OutlineEntry
from rulebook.structural import detect_structural_inconsistencies
from schemas.faults import ComplianceVerdict, Fault
from tools.ledger import RetrievalLedger
```

**Test isolation pattern** (copy from `test_absence.py:29-51` — module-scoped rulebook fixture):
```python
@pytest.fixture(scope="module")
def _self_contained_rulebook_store():
    from rulebook.build import build_ecfr, build_fda, build_ich
    for rows in (build_ecfr(update_manifest=False), build_ich(update_manifest=False), build_fda(update_manifest=False)):
        errors = [r for r in rows if "error" in r]
        assert not errors
    ri.load_requirement_index.cache_clear()
    ri.build_requirement_edges()
    yield
    ri.load_requirement_index.cache_clear()
```

**Core test pattern** (adapt from `test_absence.py:55-70` corpus construction):
```python
def _corpus_with_table(tmp_path, table_cells: dict) -> CorpusIndex:
    """Construct a CorpusIndex whose cache contains a synthetic table_index for structural testing."""
    # Write a synthetic cache entry with table_index using write_doc_cache
    from ingest.store import write_doc_cache, cache_key
    ...

def test_aggregate_violation_detected(tmp_path, _self_contained_rulebook_store):
    """Table 19 analog: total cell (0.14%) < single largest component (0.15%) -> VIOLATION."""
    corpus = _corpus_with_table(tmp_path, {"t0,2,0": "Total", "t0,2,1": "0.14%",
                                            "t0,0,1": "0.10%", "t0,1,1": "0.15%"})
    ledger = RetrievalLedger()
    faults = detect_structural_inconsistencies(corpus, corpus.manifest, ledger)
    assert any(f.structural_anchor.relation in ("SUM", "MAX") for f in faults)

def test_unavailable_table_tier_skipped(tmp_path, _self_contained_rulebook_store):
    """D-STR5: a doc with tables='unavailable' must be skipped, not crash."""
    ...
```

---

### `tests/tools/test_emit_structural_finding.py` (test, gate) — new file

**Analog:** `tests/tools/test_emit_absence_finding.py` (lines 1-70+) — exact role match

**Imports pattern** (mirror `test_emit_absence_finding.py` lines 20-36):
```python
from __future__ import annotations
from ingest.anchors import mint_span
from rulebook.store import write_chunk
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import ComplianceVerdict, EvidenceClass, Fault, StructuralAnchor
from tests.rulebook.conftest import fixture_chunk
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_structural_finding
from tools.errors import ToolRejected
```

**Gate rejection test pattern** (mirror `test_emit_absence_finding.py` tests b-d):
```python
def test_structural_fabricated_claim_span_rejected(tmp_path):
    """A fabricated (never-issued) claim span is rejected with reason_code=not_retrieved_this_session."""
    ...

def test_structural_null_rule_span_accepted_for_aggregate(tmp_path):
    """D-STR6: rule_span_id=None is allowed for pure arithmetic labeled-aggregate checks."""
    anchor = StructuralAnchor(claim_span_id=..., basis_span_ids=[...], relation="SUM",
                               expected_value="0.30%", actual_value="0.14%")
    result = emit_structural_finding(corpus, rule_span_id=None, structural_anchor=anchor, ledger=ledger)
    assert isinstance(result, Fault)
    assert result.rule_span_id is None
    assert result.leg_tag == "STRUCTURAL"

def test_structural_merged_cell_dedup_abstains(tmp_path):
    """Pitfall 2: all basis cells resolve to same merged span -> reason_code=unanchored_structural."""
    ...
```

---

### `tests/evals/test_generality_guard.py` (test, guard) — additive extension

**Analog:** `tests/evals/test_generality_guard.py` self (lines 95-135 for NO-CONSTANT pattern)

**New module source paths to scan** (add alongside `_ABSENCE_SOURCE = Path("src/rulebook/absence.py")` at line 48):
```python
_STRUCTURAL_SOURCE = Path("src/rulebook/structural.py")
_REFERENCES_SOURCE = Path("src/rulebook/references.py")
_PRECEDENT_SOURCE = Path("src/rulebook/precedent_search.py")
_GUARD_VOCAB_SOURCE = Path("src/rulebook/guard_vocab.py")
_NEW_SOURCES = [_STRUCTURAL_SOURCE, _REFERENCES_SOURCE, _PRECEDENT_SOURCE]
```

**Extended NO-CONSTANT test** (mirror `test_absence_module_embeds_no_corpus_constant` pattern, lines 95-135):
```python
@pytest.mark.parametrize("source_path", [
    Path("src/rulebook/structural.py"),
    Path("src/rulebook/references.py"),
    Path("src/rulebook/precedent_search.py"),
])
def test_new_modules_embed_no_corpus_constant(source_path):
    """D-GEN2(1) STRUCTURAL NO-CONSTANT extended to structural/reference/precedent modules.
    Same three structural rejections as absence.py guard, plus guard_vocab allowlist exemption."""
    source = source_path.read_text()
    offenders = []
    # (a) CTD-family literals NOT in a re.compile() extractor context
    ...  # same pattern as lines 112-115 but add allowlist exemption for re.compile(r"3.2.[SP].")
    # (b) hardcoded float literals not in {0.0, 1.0} (threshold must come from JSON baseline)
    ...  # same pattern as lines 117-123
    # (c) backstop dataset id denylist
    ...  # same pattern as lines 125-129
    assert not offenders, ...
```

**New synthetic fixture invariants** (D-GRD2 — these MUST execute, not pytest.skip):
```python
_SYNTHETIC_FIXTURE_DIR = Path("src/evals/dataset/synthetic_fixture")

def test_same_logic_structural_on_synthetic(tmp_path):
    """D-GRD2 SAME-LOGIC: planted structural deficiency in synthetic fixture is found."""
    assert _SYNTHETIC_FIXTURE_DIR.exists(), "synthetic fixture must be committed (D-GRD1)"
    corpus = ingest_corpus(_SYNTHETIC_FIXTURE_DIR, cache_dir=str(tmp_path / "cache"))
    ledger = RetrievalLedger()
    faults = detect_structural_inconsistencies(corpus, corpus.manifest, ledger)
    assert any(f.structural_anchor for f in faults), "planted structural deficiency must fire"

def test_threshold_transfer_synthetic(tmp_path):
    """D-GRD2 THRESHOLD-TRANSFER: frozen threshold from baseline fires on synthetic fixture 2."""
    ...  # ingest a second synthetic fixture dir with different values; apply frozen threshold

def test_rename_invariance_synthetic(tmp_path):
    """D-GRD2 RENAME-INVARIANCE: renaming synthetic fixture dir yields identical candidates."""
    import shutil
    dir_a = _SYNTHETIC_FIXTURE_DIR
    dir_b = tmp_path / "renamed_fixture"
    shutil.copytree(dir_a, dir_b)
    corpus_a = ingest_corpus(dir_a, cache_dir=str(tmp_path / "cache_a"))
    corpus_b = ingest_corpus(dir_b, cache_dir=str(tmp_path / "cache_b"))
    ledger_a, ledger_b = RetrievalLedger(), RetrievalLedger()
    faults_a = detect_structural_inconsistencies(corpus_a, corpus_a.manifest, ledger_a)
    faults_b = detect_structural_inconsistencies(corpus_b, corpus_b.manifest, ledger_b)
    assert len(faults_a) == len(faults_b), "RENAME-INVARIANCE: candidate count must not change on rename"
```

---

### `tests/ingest/test_corpus_index_persistence.py` (test, file-I/O) — new file

**Analog:** `tests/ingest/test_corpus.py` (lines 1-50+) — role match

**Imports pattern** (mirror `test_corpus.py` lines 1-20):
```python
from __future__ import annotations
import shutil
from io import BytesIO
from pathlib import Path
import docx
import fitz
import pytest
import ingest.classify as classify
from ingest.corpus import ingest_corpus
from tools.search_corpus import _has_persisted_index, _index_sidecar_paths
```

**D-R5B tests:**
```python
def test_persisted_index_built_at_ingest(tmp_path, _no_creds):
    """D-R5B: after ingest_corpus, each doc must have sidecar index files."""
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "doc.pdf").write_bytes(_pdf_bytes("method validation accuracy results table"))
    corpus = ingest_corpus(root, cache_dir=str(tmp_path / "cache"))
    assert _has_persisted_index(corpus), "D-R5B: persisted index must exist after ingest"

def test_persisted_index_loads_at_query(tmp_path, _no_creds):
    """D-R5B: search_corpus loads persisted index and embeds only query (not whole corpus)."""
    ...  # verify embed_texts NOT called with corpus chunks after ingest (monkeypatch)

def test_persisted_index_invalidated_on_content_change(tmp_path, _no_creds):
    """D-CON2: changed file bytes -> new content_hash -> sidecar miss -> rebuild."""
    ...
```

---

### `src/evals/dataset/synthetic_fixture/` (config/data) — new directory, D-GRD1

**Analog:** `tests/ingest/fixtures/` (construction pattern)

**Fixture authoring constraints (D-GRD1 — all four must hold):**
1. Deficiencies specified from rulebook/structural semantics, BLIND to check implementation
2. Different surface forms than mvr1381 (different doc names, values, table layouts)
3. Realistic regulatory prose so bge-m3 cosine lands in 0.5–0.8 range (Pitfall 8)
4. Multi-doc (doc_a = QOS analog, doc_b = Module analog) serving double duty as X1/X2 end-to-end

**Recommended fixture structure (from RESEARCH.md Domain 5):**
```
src/evals/dataset/synthetic_fixture/
├── doc_a.pdf    (synthetic QOS 2.3 analog — references doc_b's spec table; has cross-ref edge)
├── doc_b.docx   (synthetic Module 3.2.P.5 analog — spec table that doc_a references)
└── doc_c.pdf    (synthetic Specification document — aggregate table error + limit exceedance)
```

---

### `src/evals/baseline/structural_threshold.json` + `precedent_threshold.json` (config)

**Analog:** `src/evals/baseline/absence_threshold.json`

**Pattern (copy exact JSON structure):**
```json
{
  "threshold": 0.0,
  "measured_on": "synthetic_fixture",
  "measured_date": "2026-08-06",
  "note": "D-STR4/D-PRC4: general threshold, not corpus-tuned. Measured on synthetic fixture, transferred to mvr1381."
}
```

---

### `src/evals/run.py` (utility, CLI) — additive `structural-gate` subcommand

**Analog:** `src/evals/run.py` self — `cmd_absence_gate` / `retrieval-gate` pattern (lines 700-720)

**Pattern:**
```python
# Add to build_parser() alongside absence-gate:
sub.add_parser("structural-gate", help="Run structural inconsistency detection, check recall on cross_reference_integrity family.")
sub.add_parser("reference-gate", help="Run reference graph detection, check recall on cross_reference_integrity family.")

# Add command function:
def cmd_structural_gate(args: argparse.Namespace) -> int:
    """D-GRD2: structural-gate — runs detect_structural_inconsistencies on eval docs,
    checks recall on cross_reference_integrity family, ratchets against committed baseline."""
    from ingest.corpus import ingest_corpus
    from rulebook.structural import detect_structural_inconsistencies
    ...  # same pattern as cmd_absence_gate
```

---

## Shared Patterns

### Grounded-candidate emit gate (dual-half validation)
**Source:** `src/tools/emit_finding.py` lines 137-230 (`emit_absence_finding`)
**Apply to:** `emit_structural_finding`, `emit_reference_finding`, `emit_precedent_finding`

```python
# Core pattern (copy for every new emit function):
# 1. RULE half: ledger.was_issued() -> wrong_store check -> open_span (HashMismatch -> ToolRejected)
# 2. Submission half: ledger.was_issued() -> wrong_store check -> open_span (HashMismatch -> ToolRejected)
# 3. Re-derivability check (analog of unanchored_absence): basis spans must exist
# 4. Return Fault(..., leg_tag=..., [leg]_anchor=anchor, source="tool:emit_[leg]_finding")
```

### D-ABS2 over-emit with scoping-confidence
**Source:** `src/rulebook/absence.py` lines 145-160 + `src/schemas/faults.py` line 84 (`claim_span_id`)
**Apply to:** `structural.py` (D-STR3), `references.py` (D-REF3), `precedent_search.py`

```python
# When a contributing cell is not cleanly addressable, over-emit with scoping_confidence="low"
# rather than silently dropping (D-ABS2 style):
anchor = StructuralAnchor(
    ...,
    scoping_confidence="low",   # NOT dropped — Phase 7 prunes
)
```

### Atomic sidecar file writes
**Source:** `src/ingest/store.py` lines 56-67 (`write_doc_cache`)
**Apply to:** D-R5B index sidecar persistence in `corpus.py` / `search_corpus.py`

```python
# Pitfall 7: use atomic write-then-rename for ALL sidecar files:
tmp = final.with_suffix(".tmp")
tmp.write_bytes(...)      # or tmp.write_text(...)
os.replace(tmp, final)    # atomic rename; crash before this leaves only .tmp, never corrupt .npy
```

### Offline test isolation (D-RB6)
**Source:** `tests/rulebook/test_absence.py` lines 29-51 + `tests/tools/conftest.py`
**Apply to:** All new test files in `tests/rulebook/`, `tests/tools/`, `tests/ingest/`

```python
# Every test uses tmp_path-scoped stores — never touches shared data/ directory.
# Module-scoped rulebook fixture: build_ecfr/build_ich/build_fda(update_manifest=False)
# then ri.load_requirement_index.cache_clear() before and after.
# No Databricks, no network, no LLM calls.
```

### NO-CONSTANT structural scan extension
**Source:** `tests/evals/test_generality_guard.py` lines 95-135
**Apply to:** `test_generality_guard.py` extended tests for `structural.py`, `references.py`, `precedent_search.py`

```python
# Three structural rejections (same logic, new source paths):
_CTD_FAMILY_LITERAL = re.compile(r"3\.2\.[SP]\.")    # line 57 — reuse unchanged
_FLOAT_LITERAL = re.compile(r"(?<![\w.])\d+\.\d+")  # line 62 — reuse unchanged
_ALLOWED_FLOAT_SENTINELS = frozenset({"0.0", "1.0"}) # line 63 — reuse unchanged
# Plus new allowlist exemption: patterns inside re.compile() calls that match CTD are
# EXTRACTORS (allowed by guard_vocab), not corpus literals.
```

### FAISS rulebook index usage (NOT the old deficiency_kb.faiss)
**Source:** `src/rulebook/store.py` lines 154-244 (`_rulebook_search_local`, `_ensure_faiss`)
**Apply to:** `src/rulebook/precedent_search.py`

```python
# CRITICAL (Pitfall 4): ALWAYS use data/rulebook.faiss via _rulebook_search_local().
# NEVER call databricks.vector._search_faiss() for precedent (uses data/deficiency_kb.faiss
# which maps to SQLite rowids, not RuleChunk doc_ids — ANDA# filter cannot work on it).
# Filter by doc_id.startswith("precedent-") (precedents.py:155 naming convention).
from rulebook.store import _rulebook_search_local, _ensure_faiss, _faiss_doc_ids
```

---

## No Analog Found

All new files have close analogs in the codebase. No file requires falling back to RESEARCH.md-only patterns.

| File | Role | Data Flow | Note |
|------|------|-----------|------|
| `src/evals/dataset/synthetic_fixture/doc_*.pdf/docx` | data | — | Synthetic content files; no code analog. Author per D-GRD1 four constraints. |
| `src/rulebook/guard_vocab.py` | config | — | Partial analog only (denylist constants in test_generality_guard.py:48-63); new concept for the allowlist registry shape. |

---

## Metadata

**Analog search scope:** `src/rulebook/`, `src/schemas/`, `src/tools/`, `src/ingest/`, `src/retrieval/`, `src/evals/`, `tests/rulebook/`, `tests/tools/`, `tests/evals/`, `tests/ingest/`
**Files scanned (read):** 28 source + test files
**Pattern extraction date:** 2026-08-06

**Key pitfalls mapped:**
- Pitfall 1: table_index keys start with `","` when table_id is empty string — use `key.split(",", 2)` not `key.split(",")`
- Pitfall 2: merged cells share a SpanID — deduplicate basis spans before recompute, abstain if all deduplicate to one
- Pitfall 3: bge-m3 unstable on `len(text) < 100` — skip short sections in precedent search
- Pitfall 4: two FAISS indexes exist — use `data/rulebook.faiss` (Phase-2 substrate) NOT `data/deficiency_kb.faiss` (old)
- Pitfall 5: `emit_structural_finding` must accept `rule_span_id=None` for pure arithmetic checks (D-STR6)
- Pitfall 6: CTD extractor regex `r"3\.2\.[SP]\."` in `references.py` must be registered in `guard_vocab` and exempted from NO-CONSTANT scan in `re.compile()` context
- Pitfall 7: sidecar files (`.npy`, `.bm25.json`) must use atomic tmp→os.replace write pattern
- Pitfall 8: synthetic fixture text must be realistic regulatory prose, not placeholder text
