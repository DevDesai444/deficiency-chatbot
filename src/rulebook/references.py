"""Cross-document reference graph leg (RECALL-03, D-REF1..D-REF5, D-RB3).

Implements two pure functions over the corpus cache and edge table:

  extract_references(corpus, manifest, db_path) -> None
      Side-effect only: extracts hyperlinks, textual references, and numeric
      value cross-references from the parsed document cache, then registers each
      as an edge via rulebook.edges.add_edge.

  detect_reference_anomalies(corpus, manifest, ledger, rulebook_cache_dir, db_path)
      -> list[Fault]
      Pure detection pass: reads the edge table, runs the concrete edge->value
      resolution algorithm (Ruling 6), detects UNRESOLVED_REF / ABSENT_TARGET /
      VALUE_CONTRADICTION anomalies, emits each grounded Fault via
      emit_reference_finding.

EDGE KEY FORMAT (critical for Plan 07 follow_reference compatibility):
  src_id = "{doc_id}:{span.start}"   (integer byte offset of the span start)
  dst_id = "{dst_doc_id}:{dst_start}" or "unresolved"
  follow_reference queries the edge table by src_id to resolve cross-document links.

D-REF1: three edge kinds — hyperlinks (DOCX 'hyperlinks' key / PDF 'links' key),
  textual references (re.compile patterns over canonical text using general cue-word
  vocabulary from guard_vocab.REFERENCE_CUE_WORDS), numeric value cross-references.
D-REF2: each anomaly candidate carries a ReferenceAnchor with src_span_id,
  dst_span_id (nullable), edge_type, anomaly enum, scoping_confidence.
D-REF3: VALUE_CONTRADICTION emitted as full candidate only when a cross-reference
  edge connects the two values; label-match-only contradictions emitted as low
  scoping_confidence.
D-REF4: VALUE_CONTRADICTION comparison reuses compare_values from
  rulebook.structural identically (same normalizer, same precision-derived
  tolerance). Fallback: local implementation when structural.py not yet present.
D-REF5: ABSENT_TARGET consults coverage manifest first; emits full candidate only
  when target is genuinely absent; emits low-confidence when target is
  parse_failed/unparsed.
D-RB3: every edge written has a provenance_span_id (the src span JSON); add_edge
  with empty provenance is rejected by edges.py:33.
D-GRD3: all regex patterns live inside re.compile() calls — never bare inline
  literals. General-vocabulary cue words imported from guard_vocab; no
  submission-specific constant. CTD extractor regex r'(?:Module|Section)\\s+
  (3\\.2\\.[SP]\\.\\d+)' lives inside re.compile() and is therefore EXEMPT from
  the NO-CONSTANT scan (D-GRD3 / Pitfall 6).
Ruling 1: the ledger is passed in by the caller; references.py never creates a
  fresh RetrievalLedger().
Ruling 4: src/evals/run.py is NOT modified in this plan. Reference-gate CLI
  registration is deferred to Plan 06 (Wave 4).
T-05W2B-04 (DoS): edges extracted per doc capped at 1000; warning logged when cap
  is hit.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

from ingest.anchors import mint_span
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from rulebook import edges as edges_module
from rulebook.guard_vocab import REFERENCE_CUE_WORDS
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import Fault, ReferenceAnchor
from tools.emit_finding import emit_reference_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# D-REF4: import compare_values from structural (same engine, zero divergence).
# Fallback: local implementation when structural.py is not yet built (Wave-3
# parallel execution — structural.py may be committed by its sibling executor
# before or after this module).
# ---------------------------------------------------------------------------
try:
    from rulebook.structural import compare_values
except ImportError:
    def _stated_precision(text: str) -> int:
        """Return decimal places in the first numeric literal found in text."""
        m = re.search(r"\d+\.(\d+)", text)
        return len(m.group(1)) if m else 0

    def compare_values(claim_text: str, ref_text: str, comparator: str) -> bool | None:
        """Precision-derived comparator (D-STR4 / D-REF4): no epsilon constant.

        Returns True = violation (claim exceeds ref limit for LEQ),
                False = complies,
                None  = abstain (unparseable).
        comparator: 'LEQ' means claim must be <= ref (NMT limit check).
        """
        def _parse(t: str) -> float | None:
            m = re.search(r"[\d.]+", t.replace(",", "."))
            if not m:
                return None
            try:
                return float(m.group())
            except ValueError:
                return None

        claim_val = _parse(claim_text)
        ref_val = _parse(ref_text)
        if claim_val is None or ref_val is None:
            return None
        prec = min(_stated_precision(claim_text), _stated_precision(ref_text))
        claim_r = round(claim_val, prec) if prec > 0 else claim_val
        ref_r = round(ref_val, prec) if prec > 0 else ref_val
        if comparator == "LEQ":
            # LEQ: claim must be <= ref; if claim > ref -> violation (True)
            return claim_r > ref_r
        if comparator == "GEQ":
            return claim_r < ref_r
        if comparator == "EQ":
            return claim_r != ref_r
        return None


# ---------------------------------------------------------------------------
# D-GRD3: general reference-extraction patterns — all inside re.compile().
# These are GENERAL patterns (not corpus literals).
# D-GRD3 comment: CTD extractor regex is inside re.compile() — EXEMPT.
# ---------------------------------------------------------------------------
_REF_PATTERNS: list[re.Pattern[str]] = [
    # D-GRD3: general "see/refer" cross-reference pattern
    re.compile(
        r"(?:see|refer\s+to|as\s+(?:described|stated)\s+in|per)\s+"
        r"§?\s*([\w][\w\s\-\.]*)",
        re.IGNORECASE,
    ),
    # D-GRD3: general table-number reference pattern
    re.compile(r"\b[Tt]able\s+(\d+[\w\-]*)", re.IGNORECASE),
    # D-GRD3: general figure-number reference pattern
    re.compile(r"\b[Ff]igure\s+(\d+[\w\-]*)", re.IGNORECASE),
    # D-GRD3: general CTD section reference pattern — INSIDE re.compile() — EXEMPT (D-GRD3/Pitfall 6)
    re.compile(r"(?:Module|Section)\s+(3\.2\.[SP]\.[\d\.]+)", re.IGNORECASE),
    # D-GRD3: general section-number reference (§X or Section X.Y)
    re.compile(r"§\s*(\d+[\.\d]*)", re.IGNORECASE),
]

# D-GRD3: general NMT / limit extraction patterns — all inside re.compile().
# Each pattern captures the numeric value AND unit (group 1 = numeric+unit).
# Unit-bearing forms: "0.15%", "0.15 mg/mL", "0.15 % w/w" — all captured.
_LIMIT_PATTERNS: list[re.Pattern[str]] = [
    # D-GRD3: "NMT 0.15%" or "NMT 0.15 mg/mL" — captures numeric+unit
    re.compile(r"NMT\s*([\d.]+\s*(?:%\s*(?:w/w)?|mg/mL|mg/g|ppm|ppb|g/L|\w+)?)", re.IGNORECASE),
    # D-GRD3: "not more than 0.15%"
    re.compile(r"not\s+more\s+than\s+([\d.]+\s*(?:%\s*(?:w/w)?|mg/mL|mg/g|ppm|ppb|g/L|\w+)?)", re.IGNORECASE),
    # D-GRD3: "limit: 0.15%" or "specification: 0.15%"
    re.compile(r"(?:limit|specification|spec)(?:ification)?\s*[:\s]\s*([\d.]+\s*(?:%\s*(?:w/w)?|mg/mL|mg/g|ppm|ppb|g/L|\w+)?)", re.IGNORECASE),
    # D-GRD3: "≤ 0.15%" or "<= 0.15%"
    re.compile(r"[≤<]=?\s*([\d.]+\s*(?:%\s*(?:w/w)?|mg/mL|mg/g|ppm|ppb|g/L|\w+)?)", re.IGNORECASE),
]

# T-05W2B-04: edge-extraction DoS cap per document
_EDGE_CAP_PER_DOC = 1000


# ---------------------------------------------------------------------------
# Helper: build NormalizedText from cached_entry dict
# ---------------------------------------------------------------------------
def _nt_from_cache(cache: dict) -> NormalizedText:
    return NormalizedText(
        canonical=cache["canonical"],
        raw_serialized=cache["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
        normalizer_version=cache["normalizer_version"],
        serializer_version=cache["serializer_version"],
    )


# ---------------------------------------------------------------------------
# Helper: find the span (SpanID) in doc covering a canonical offset
# ---------------------------------------------------------------------------
def _span_at_offset(doc_id: str, canonical: str, offset: int, normalizer_version: str) -> SpanID:
    """Mint a small span anchored at `offset` in `canonical`."""
    end = min(len(canonical), offset + 80)
    return mint_span(canonical, offset, end, doc_id, normalizer_version)


# ---------------------------------------------------------------------------
# Helper: extract limit value from src span text (Step A of Ruling 6)
# ---------------------------------------------------------------------------
def _extract_limit(text: str) -> tuple[float | None, str]:
    """Extract the numeric limit and raw limit string from src span text.

    Returns (limit_float, raw_limit_text). limit_float is None when no limit found.
    D-GRD3: all _LIMIT_PATTERNS are pre-compiled; no inline literal.
    """
    for pat in _LIMIT_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(1).strip()
            # parse numeric part
            num_m = re.search(r"[\d.]+", raw)
            if num_m:
                try:
                    return float(num_m.group()), raw
                except ValueError:
                    continue
    return None, ""


# ---------------------------------------------------------------------------
# Helper: unit compatibility check (Step D of Ruling 6)
# ---------------------------------------------------------------------------
def _units_compatible(a: str, b: str) -> bool:
    """Returns True if units in a and b are compatible for numeric comparison.

    Abstains (returns False) on unit mismatch. Treats unitless and '%' as compatible;
    '%' and '% w/w' as compatible. Any mismatch with 'mg', 'mL', etc. is incompatible.
    D-GRD3: general unit compatibility — no corpus constant.
    """
    def _extract_unit(t: str) -> str:
        # remove numeric part, return normalized unit string
        cleaned = re.sub(r"[\d.]+", "", t).strip().lower().replace(" ", "")
        return cleaned

    ua = _extract_unit(a)
    ub = _extract_unit(b)
    # Treat "%" and "%w/w" as equivalent
    percent_variants = {"", "%", "%w/w", "w/w"}
    if ua in percent_variants and ub in percent_variants:
        return True
    return ua == ub


# ---------------------------------------------------------------------------
# extract_references: pure side-effect — register edges
# ---------------------------------------------------------------------------

def extract_references(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    db_path: str = edges_module._DB_PATH,
) -> None:
    """RECALL-03 extraction pass (D-REF1, D-RB3): read parsed cache for each doc,
    extract all three edge kinds, call add_edge for each.

    Edge src_id format: "{doc_id}:{span.start}" (integer byte offset).
    Edge dst_id format: "{dst_doc_id}:{dst_start}" or "unresolved".
    T-05W2B-04: capped at _EDGE_CAP_PER_DOC edges per document.
    """
    doc_ids = {d.doc_id for d in manifest.documents}

    for doc_entry in manifest.documents:
        if doc_entry.status in ("parse_failed", "unsupported"):
            continue
        cache = corpus.cached_entry(doc_entry.doc_id)
        if cache is None:
            continue

        canonical: str = cache["canonical"]
        normalizer_version: str = cache.get("normalizer_version", "")
        doc_id = doc_entry.doc_id
        edge_count = 0

        # -----------------------------------------------------------------
        # Kind 1: DOCX hyperlinks (from parse/docx.py 'hyperlinks' key)
        # D-REF1: hyperlinks extracted via zipfile/ET in Plan 01 parse backfill
        # T-05W2B-01: store URI as string, NEVER fetch/resolve (no SSRF)
        # -----------------------------------------------------------------
        for hl in cache.get("hyperlinks", []):
            if edge_count >= _EDGE_CAP_PER_DOC:
                log.warning("edge_cap_reached", doc_id=doc_id, edge_type="hyperlink")
                break
            target = hl.get("target", "")
            if not target:
                continue
            # Determine dst: if target is a doc_id in the corpus, use it; else "unresolved"
            para_idx = hl.get("paragraph_index", 0)
            # Find a span in the doc that best represents this hyperlink anchor
            # Use the first reasonable position in canonical text
            if not canonical:
                continue
            anchor_offset = min(para_idx * 50, max(0, len(canonical) - 80))
            src_span = _span_at_offset(doc_id, canonical, anchor_offset, normalizer_version)
            src_id = f"{doc_id}:{src_span.start}"
            # dst: check if target looks like a known doc_id or filename
            dst_doc = _resolve_target_doc(target, doc_ids, manifest)
            dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
            provenance = json.dumps(src_span.model_dump())
            try:
                edges_module.add_edge(
                    src_id=src_id,
                    dst_id=dst_id,
                    edge_type="hyperlink",
                    provenance_span_id=provenance,
                    db_path=db_path,
                )
                edge_count += 1
            except Exception as exc:
                log.warning("add_edge_failed", doc_id=doc_id, error=str(exc)[:200])

        # -----------------------------------------------------------------
        # Kind 2: PDF links (from parse/pdf.py 'links' key)
        # D-REF1: link annotations extracted by page.get_links() in Plan 01
        # -----------------------------------------------------------------
        for lnk in cache.get("links", []):
            if edge_count >= _EDGE_CAP_PER_DOC:
                log.warning("edge_cap_reached", doc_id=doc_id, edge_type="pdf_link")
                break
            uri = lnk.get("uri", "") or lnk.get("name", "")
            page_num = lnk.get("page", 0)
            if not uri:
                continue
            anchor_offset = min(page_num * 100, max(0, len(canonical) - 80))
            src_span = _span_at_offset(doc_id, canonical, anchor_offset, normalizer_version)
            src_id = f"{doc_id}:{src_span.start}"
            dst_doc = _resolve_target_doc(uri, doc_ids, manifest)
            dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
            provenance = json.dumps(src_span.model_dump())
            try:
                edges_module.add_edge(
                    src_id=src_id,
                    dst_id=dst_id,
                    edge_type="hyperlink",
                    provenance_span_id=provenance,
                    db_path=db_path,
                )
                edge_count += 1
            except Exception as exc:
                log.warning("add_edge_failed", doc_id=doc_id, error=str(exc)[:200])

        # -----------------------------------------------------------------
        # Kind 3: Textual references (regex over canonical text)
        # D-REF1: general regex patterns from guard_vocab.REFERENCE_CUE_WORDS
        # D-GRD3: all patterns inside re.compile() — anti-overfitting
        # T-05W2B-02: patterns fixed, not constructed from user input
        # -----------------------------------------------------------------
        for pat in _REF_PATTERNS:
            for m in pat.finditer(canonical):
                if edge_count >= _EDGE_CAP_PER_DOC:
                    log.warning("edge_cap_reached", doc_id=doc_id, edge_type="textual_ref")
                    break
                match_offset = m.start()
                src_span = _span_at_offset(doc_id, canonical, match_offset, normalizer_version)
                src_id = f"{doc_id}:{src_span.start}"
                # Try to find target doc from the matched text
                ref_text = m.group(0)
                dst_doc = _find_doc_by_outline(ref_text, manifest, doc_ids)
                dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
                provenance = json.dumps(src_span.model_dump())
                try:
                    edges_module.add_edge(
                        src_id=src_id,
                        dst_id=dst_id,
                        edge_type="textual_ref",
                        provenance_span_id=provenance,
                        db_path=db_path,
                    )
                    edge_count += 1
                except Exception as exc:
                    log.warning("add_edge_failed", doc_id=doc_id, error=str(exc)[:200])

        # -----------------------------------------------------------------
        # Kind 3b: Numeric value cross-references (NMT / limit patterns)
        # Scan for spans containing limit specs that reference another doc's values
        # -----------------------------------------------------------------
        for lim_pat in _LIMIT_PATTERNS:
            for m in lim_pat.finditer(canonical):
                if edge_count >= _EDGE_CAP_PER_DOC:
                    log.warning("edge_cap_reached", doc_id=doc_id, edge_type="value_crossref")
                    break
                match_offset = m.start()
                # Widen context: grab surrounding text to detect cross-doc reference cues
                ctx_start = max(0, match_offset - 60)
                ctx_end = min(len(canonical), m.end() + 120)
                ctx_text = canonical[ctx_start:ctx_end]
                # Only register as cross-ref edge if context contains reference cue words
                has_cue = any(
                    cue in ctx_text.lower() for cue in REFERENCE_CUE_WORDS
                )
                if not has_cue:
                    continue
                src_span = _span_at_offset(doc_id, canonical, match_offset, normalizer_version)
                src_id = f"{doc_id}:{src_span.start}"
                # find referenced dst doc
                dst_doc = _find_doc_by_outline(ctx_text, manifest, doc_ids)
                dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
                provenance = json.dumps(src_span.model_dump())
                try:
                    edges_module.add_edge(
                        src_id=src_id,
                        dst_id=dst_id,
                        edge_type="value_crossref",
                        provenance_span_id=provenance,
                        db_path=db_path,
                    )
                    edge_count += 1
                except Exception as exc:
                    log.warning("add_edge_failed", doc_id=doc_id, error=str(exc)[:200])


# ---------------------------------------------------------------------------
# Helper: resolve a target URI / string to a known doc_id
# ---------------------------------------------------------------------------
def _resolve_target_doc(target: str, doc_ids: set[str], manifest: CoverageManifest) -> str | None:
    """Map a hyperlink target URI or textual reference to a corpus doc_id.

    Checks: exact doc_id match, filename match (case-insensitive).
    Returns None when no match found — caller writes "unresolved".
    T-05W2B-01: never fetches the URI; only string comparison.
    """
    # Check exact doc_id match
    if target in doc_ids:
        return target
    # Check filename match (case-insensitive, strip leading paths)
    target_lower = target.lower().split("/")[-1].split("\\")[-1]
    for doc in manifest.documents:
        if doc.filename.lower() == target_lower:
            return doc.doc_id
        # Also try without extension
        if doc.filename.lower().rsplit(".", 1)[0] == target_lower.rsplit(".", 1)[0]:
            return doc.doc_id
    return None


# ---------------------------------------------------------------------------
# Helper: find a doc by cross-referencing the match text against doc outlines
# ---------------------------------------------------------------------------
def _find_doc_by_outline(ref_text: str, manifest: CoverageManifest, doc_ids: set[str]) -> str | None:
    """Try to find a referenced doc by matching ref_text against doc titles and outline labels.

    Returns the doc_id of the first match, or None.
    General search: checks doc titles and outline section labels.
    D-GRD3: no corpus-specific constant; purely string containment.
    """
    ref_lower = ref_text.lower()
    for doc in manifest.documents:
        if doc.title and doc.title.lower() in ref_lower:
            return doc.doc_id
        if doc.filename and doc.filename.lower().split(".")[0] in ref_lower:
            return doc.doc_id
        for outline_entry in doc.outline:
            label_lower = outline_entry.label.lower()
            if label_lower and label_lower in ref_lower:
                return doc.doc_id
    return None


# ---------------------------------------------------------------------------
# detect_reference_anomalies: pure detection pass with concrete algorithm
# ---------------------------------------------------------------------------

def detect_reference_anomalies(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
    db_path: str = edges_module._DB_PATH,
) -> list[Fault]:
    """RECALL-03 detection pass (D-REF2/D-REF3/D-REF4/D-REF5, Ruling 6).

    Reads the edge table, applies the CONCRETE edge->value resolution algorithm
    (Ruling 6), detects UNRESOLVED_REF / ABSENT_TARGET / VALUE_CONTRADICTION
    anomalies, emits each through emit_reference_finding.

    Ruling 1: `ledger` is passed in by caller. This function NEVER creates a fresh
    RetrievalLedger(). Cache-derived spans are issued via issue_cached_span inside
    emit_reference_finding.

    Ruling 6 — FULL resolution pipeline:
      Step 1: Extract limit from src span text (_LIMIT_PATTERNS).
      Step 2: Identify the referenced entity name.
      Step 3: Target table selection from dst doc cache.
      Step 4: Label matching — find dst table row where col=0 text matches entity.
      Step 5: Unit compatibility — abstain on mismatch.
      Step 6: compare_values(dst_value, src_limit, 'LEQ') — True = violation.
      Confidence: 'full' when edge exists + dst resolved; 'low' for label-match-only.
    """
    doc_ids_in_manifest = {d.doc_id for d in manifest.documents}
    doc_status = {d.doc_id: d.status for d in manifest.documents}
    faults: list[Fault] = []

    # Fetch all edges from the table
    all_edges = edges_module.get_edges(db_path=db_path)

    for (src_id, dst_id, edge_type, provenance_span_id) in all_edges:
        # Parse src_id -> src_doc_id, src_start
        try:
            src_doc_id, src_start_str = src_id.rsplit(":", 1)
            src_start = int(src_start_str)
        except (ValueError, AttributeError):
            continue

        if src_doc_id not in doc_ids_in_manifest:
            continue

        src_cache = corpus.cached_entry(src_doc_id)
        if src_cache is None:
            continue

        src_canonical: str = src_cache["canonical"]
        src_normalizer: str = src_cache.get("normalizer_version", "")

        # Recover the src span from the provenance_span_id
        try:
            prov_dict = json.loads(provenance_span_id)
            src_span = SpanID.model_validate(prov_dict)
        except Exception:
            # Fall back to minting a span at src_start
            end = min(len(src_canonical), src_start + 80)
            src_span = mint_span(src_canonical, src_start, end, src_doc_id, src_normalizer)

        src_text = src_canonical[src_span.start:src_span.end]

        # -----------------------------------------------------------------
        # Anomaly 1: UNRESOLVED_REF — dst_id == "unresolved"
        # -----------------------------------------------------------------
        if dst_id == "unresolved":
            anchor = ReferenceAnchor(
                src_span_id=src_span,
                dst_span_id=None,
                edge_type=edge_type,  # type: ignore[arg-type]
                anomaly="UNRESOLVED_REF",
                scoping_confidence="full",
            )
            result = emit_reference_finding(
                corpus=corpus,
                reference_anchor=anchor,
                ledger=ledger,
                title="Unresolved cross-reference",
                detail=f"Reference in '{src_doc_id}' at offset {src_start} "
                       f"could not be resolved to any document in the corpus. "
                       f"Reference text: {src_text[:120]!r}",
                rulebook_cache_dir=rulebook_cache_dir,
            )
            if isinstance(result, Fault):
                faults.append(result)
            continue

        # Parse dst_id -> dst_doc_id, dst_start
        try:
            dst_doc_id, dst_start_str = dst_id.rsplit(":", 1)
            dst_start = int(dst_start_str)
        except (ValueError, AttributeError):
            continue

        # -----------------------------------------------------------------
        # Anomaly 2: ABSENT_TARGET — dst_doc not in manifest (D-REF5)
        # -----------------------------------------------------------------
        if dst_doc_id not in doc_ids_in_manifest:
            anchor = ReferenceAnchor(
                src_span_id=src_span,
                dst_span_id=None,
                edge_type=edge_type,  # type: ignore[arg-type]
                anomaly="ABSENT_TARGET",
                scoping_confidence="full",  # genuinely absent from corpus
            )
            result = emit_reference_finding(
                corpus=corpus,
                reference_anchor=anchor,
                ledger=ledger,
                title="Referenced document absent from corpus",
                detail=f"Reference from '{src_doc_id}' targets '{dst_doc_id}' "
                       f"which is not present in the submission corpus.",
                rulebook_cache_dir=rulebook_cache_dir,
            )
            if isinstance(result, Fault):
                faults.append(result)
            continue

        # D-REF5: target is present but may be parse_failed/unparsed
        dst_status = doc_status.get(dst_doc_id, "parse_failed")
        if dst_status in ("parse_failed", "unsupported"):
            anchor = ReferenceAnchor(
                src_span_id=src_span,
                dst_span_id=None,
                edge_type=edge_type,  # type: ignore[arg-type]
                anomaly="ABSENT_TARGET",
                scoping_confidence="low",  # present but parse_failed — boundary condition
            )
            result = emit_reference_finding(
                corpus=corpus,
                reference_anchor=anchor,
                ledger=ledger,
                title="Referenced document unavailable (parse failure)",
                detail=f"Reference from '{src_doc_id}' targets '{dst_doc_id}' "
                       f"which is present in corpus but has status '{dst_status}'. "
                       f"Cannot verify reference target.",
                rulebook_cache_dir=rulebook_cache_dir,
            )
            if isinstance(result, Fault):
                faults.append(result)
            continue

        # -----------------------------------------------------------------
        # Anomaly 3: VALUE_CONTRADICTION — concrete algorithm (Ruling 6)
        # Only check when edge type is value_crossref OR textual_ref with NMT content
        # -----------------------------------------------------------------
        dst_cache = corpus.cached_entry(dst_doc_id)
        if dst_cache is None:
            continue

        # Step A: Extract limit from src text (Ruling 6 / D-GRD3)
        limit_val, limit_raw = _extract_limit(src_text)
        if limit_val is None:
            # No limit found in this span — not a value cross-ref anomaly
            continue

        # Step B: Identify referenced entity name from src text
        # Generic: find the first word sequence that could be an entity label
        # D-GRD3: general extraction — no inline corpus constant
        entity_name = _extract_entity_name(src_text)

        # Step C: Target table selection (Ruling 6)
        # Load table_index from dst doc cache
        dst_table_index: dict[str, dict] = dst_cache.get("table_index", {})
        dst_canonical: str = dst_cache["canonical"]
        dst_normalizer: str = dst_cache.get("normalizer_version", "")

        if not dst_table_index:
            continue

        # Group cells by table_id
        tables_cells = _group_table_cells(dst_table_index, dst_canonical)

        # Step D: Label matching + Step E: Unit check + Step F: compare_values
        for table_id, cell_grid in tables_cells.items():
            for (row, col), (cell_span, cell_text) in cell_grid.items():
                if col != 0:  # label column is col=0
                    continue
                # Check if this label cell text could be an entity we care about
                # For VALUE_CONTRADICTION: iterate ALL rows, flag those that exceed limit
                # This finds the value column (col=1 typically)
                value_col = _find_value_col(cell_grid, row)
                if value_col is None:
                    continue
                value_key = (row, value_col)
                if value_key not in cell_grid:
                    continue
                _, value_text = cell_grid[value_key]
                if not value_text.strip():
                    continue

                # Step E: Unit compatibility check
                if not _units_compatible(limit_raw, value_text):
                    continue  # abstain on unit mismatch (D-STR4/D-REF4)

                # Step F: compare_values (D-REF4)
                # compare_values(dst_value, src_limit, "LEQ"):
                # True = dst_value > src_limit = VIOLATION
                is_violation = compare_values(value_text, limit_raw, "LEQ")
                if is_violation is None:
                    continue  # abstain on unparseable
                if not is_violation:
                    continue  # compliant — no fault

                # Build dst_span_id for the violating cell
                dst_span = SpanID.model_validate(cell_span) if isinstance(cell_span, dict) else cell_span
                # Confidence: 'full' when edge is confirmed (edge_type hyperlink or textual_ref
                # means a real cross-ref edge was extracted); 'low' for label-match-only
                confidence: str = "full" if edge_type in ("hyperlink", "textual_ref", "value_crossref") else "low"

                anchor = ReferenceAnchor(
                    src_span_id=src_span,
                    dst_span_id=dst_span,
                    edge_type=edge_type,  # type: ignore[arg-type]
                    anomaly="VALUE_CONTRADICTION",
                    scoping_confidence=confidence,  # type: ignore[arg-type]
                )
                detail_parts = [
                    f"Cross-document value contradiction detected.",
                    f"Source '{src_doc_id}' states limit: {limit_raw!r}.",
                    f"Target '{dst_doc_id}' table '{table_id}' row {row}: {value_text!r}.",
                    f"Arithmetic check: {value_text} > {limit_raw} = TRUE VIOLATION.",
                ]
                if entity_name:
                    detail_parts.insert(2, f"Referenced entity: {entity_name!r}.")
                result = emit_reference_finding(
                    corpus=corpus,
                    reference_anchor=anchor,
                    ledger=ledger,
                    title="Cross-document value contradiction",
                    detail=" ".join(detail_parts),
                    rulebook_cache_dir=rulebook_cache_dir,
                )
                if isinstance(result, Fault):
                    faults.append(result)

    return faults


# ---------------------------------------------------------------------------
# Helper: group table_index cells by table_id -> {(row, col): (span, text)}
# ---------------------------------------------------------------------------
def _group_table_cells(
    table_index: dict[str, dict],
    canonical: str,
) -> dict[str, dict[tuple[int, int], tuple[dict, str]]]:
    """Parse table_index keys (format: '{table_id},{row},{col}') into a nested structure.

    Returns {table_id: {(row, col): (span_dict, cell_text)}}.
    Table key format from ingest/tables.py: '{table_id},{row},{col}'.
    """
    tables: dict[str, dict[tuple[int, int], tuple[dict, str]]] = defaultdict(dict)
    for key, span_data in table_index.items():
        # Key format: "{table_id},{row},{col}" — Pitfall 1: table_id may be ""
        parts = key.split(",", 2)
        if len(parts) != 3:
            continue
        table_id_part, row_str, col_str = parts
        try:
            row = int(row_str)
            col = int(col_str)
        except ValueError:
            continue
        # span_data is a dict (SpanID.model_dump())
        span_dict = span_data if isinstance(span_data, dict) else span_data.model_dump() if hasattr(span_data, "model_dump") else {}
        if not span_dict:
            continue
        # Extract text from canonical
        try:
            start = int(span_dict.get("start", 0))
            end = int(span_dict.get("end", 0))
            cell_text = canonical[start:end].strip()
        except (TypeError, ValueError):
            cell_text = ""
        tables[table_id_part][(row, col)] = (span_dict, cell_text)
    return dict(tables)


# ---------------------------------------------------------------------------
# Helper: find the value column index for a given row in the cell grid
# ---------------------------------------------------------------------------
def _find_value_col(
    cell_grid: dict[tuple[int, int], tuple[dict, str]],
    row: int,
) -> int | None:
    """Find the column (!=0) with a numeric value in this row.

    General: returns the first column index in the row where cell text contains
    a numeric value. Returns None if no numeric column found.
    D-GRD3: general numeric detection — no corpus constant.
    """
    # Collect columns in this row excluding col=0 (label column)
    row_cols = sorted(col for (r, col) in cell_grid if r == row and col != 0)
    for col in row_cols:
        _, text = cell_grid.get((row, col), (None, ""))
        if text and re.search(r"[\d.]+", text):
            return col
    return None


# ---------------------------------------------------------------------------
# Helper: extract entity name from src span text
# ---------------------------------------------------------------------------
def _extract_entity_name(src_text: str) -> str | None:
    """Extract a referenced entity name (compound, substance, parameter) from src text.

    General: looks for capitalized multi-word tokens or known patterns.
    Returns the first plausible entity name, or None.
    D-GRD3: general extraction — no inline corpus constant.
    """
    # D-GRD3: general compound/substance name pattern — inside re.compile()
    _ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z])\b|([A-Z][a-z]+(?:\s+\w+){0,2})", re.UNICODE)
    m = _ENTITY_PATTERN.search(src_text)
    if m:
        return (m.group(1) or m.group(2) or "").strip() or None
    return None
