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
import re
from collections import defaultdict

import structlog

from ingest.anchors import mint_span
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from rulebook import edges as edges_module
from rulebook.guard_vocab import REFERENCE_CUE_WORDS
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import Fault, ReferenceAnchor
from tools.emit_finding import emit_reference_finding
from tools.ledger import RetrievalLedger

# WR-09: standardize on structlog across the recall legs (structural.py already uses it)
# and drop the unused `ToolRejected` import. Using structlog also fixes the previously
# latent stdlib-logging calls that passed structured kwargs (doc_id=, edge_type=) which
# stdlib logging.Logger.warning does not accept.
log = structlog.get_logger()

# ---------------------------------------------------------------------------
# D-REF4: import compare_values from structural (same engine, zero divergence).
# Fallback: local implementation when structural.py is not yet built (Wave-3
# parallel execution — structural.py may be committed by its sibling executor
# before or after this module).
# ---------------------------------------------------------------------------
try:
    from rulebook.structural import compare_values
except ImportError:
    # CR-02 (project law 4 — ONE ENGINE): structural.py is committed, so this
    # fallback only fires under an import-order edge case. When it does, it MUST be
    # behavior-identical to rulebook.structural.compare_values: the full comparator
    # set (EQUALS, LEQ/NMT, GEQ/NLT, SUM, MAX, MIN, MEAN), the same relation token
    # spellings, the same precision-derived rule (round BOTH operands to the coarser
    # operand's stated decimal precision, no epsilon), and abstain-on-unparseable.
    # The previous fallback handled only LEQ/GEQ/EQ (misspelled "EQ", not "EQUALS")
    # and returned None for SUM/MAX/MIN/MEAN, silently dropping real contradictions.
    def _stated_precision(text: str) -> int:
        """Number of decimal places in the first numeric literal, else 0.

        Mirrors rulebook.structural._stated_precision exactly.
        """
        m = re.search(r"(\d+)\.(\d+)", text)
        return len(m.group(2)) if m else 0

    def _parse_numeric(text: str) -> float | None:
        """Extract first numeric value, else None (abstain).

        Mirrors rulebook.structural._parse_numeric exactly.
        """
        if text is None:
            return None
        m = re.search(r"[\d.]+", text)
        if m is None:
            return None
        try:
            return float(m.group())
        except ValueError:
            return None

    def compare_values(claim_text: str, ref_text: str, comparator: str) -> bool | None:
        """Behavior-identical mirror of rulebook.structural.compare_values (CR-02).

        Returns True = violation, False = complies, None = abstain (unparseable).
        Precision-derived (D-STR4): round both operands to the coarser operand's
        stated precision, then compare exact-equal / strict-inequality.
        """
        claim_num = _parse_numeric(claim_text)
        ref_num = _parse_numeric(ref_text)
        if claim_num is None or ref_num is None:
            return None

        # CR-03 mirror: coarser-operand precision, but never round to 0 places when
        # only ONE operand omits decimals (that discards a stated fractional value).
        prec_claim = _stated_precision(claim_text)
        prec_ref = _stated_precision(ref_text)
        prec = min(prec_claim, prec_ref)
        if prec == 0 and max(prec_claim, prec_ref) > 0:
            prec = max(prec_claim, prec_ref)
        rc = round(claim_num, prec)
        rr = round(ref_num, prec)

        if comparator in ("SUM", "MAX", "MIN", "MEAN", "EQUALS"):
            return rc != rr
        if comparator in ("LEQ", "NMT"):
            return rc > rr
        if comparator in ("GEQ", "NLT"):
            return rc < rr
        # Default: equality check for unknown comparators (matches structural.py)
        return rc != rr


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
    # D-GRD3: general parenthesized-filename pattern — any filename with a document extension
    # inside parentheses. NOT corpus-specific: matches ANY parenthesized filename with a
    # recognized document extension. Enables cross-doc resolution of explicit filename citations
    # like "(doc_b.docx)", "(procedures.pdf)", "(spec_v2.xlsx)", etc.
    re.compile(
        r"\(([\w\-]+\.(?:docx?|pdf|xlsx?|pptx?|txt|csv))\)",
        re.IGNORECASE,
    ),
]

# D-GRD3: general NMT / limit extraction patterns — all inside re.compile().
# Each pattern captures the numeric value AND unit (group 1 = numeric+unit).
# Unit-bearing forms: "0.15%", "0.15 mg/mL", "0.15 % w/w" — all captured.
#
# WR-03: the unit alternation is a CLOSED set of recognized regulatory units. The
# previous trailing `\w+` catch-all matched an arbitrary FOLLOWING word when no real
# unit applied — e.g. "NMT 0.15 for" captured "0.15 for", and _units_compatible then
# treated "for" as the unit, corrupting the unit-compatibility gate (spurious mismatch
# -> recall loss, or coincidental match). The number is now anchored to the immediate
# unit token only; a stray following word is no longer swallowed.
_UNIT_ALT = r"(?:%\s*(?:w/w)?|mg/mL|mg/g|mg/kg|mg|mL|ppm|ppb|g/L|µg|ug|kg|g|L)?"
_LIMIT_PATTERNS: list[re.Pattern[str]] = [
    # D-GRD3: "NMT 0.15%" or "NMT 0.15 mg/mL" — captures numeric+unit
    re.compile(r"NMT\s*([\d.]+\s*" + _UNIT_ALT + r")", re.IGNORECASE),
    # D-GRD3: "not more than 0.15%"
    re.compile(r"not\s+more\s+than\s+([\d.]+\s*" + _UNIT_ALT + r")", re.IGNORECASE),
    # D-GRD3: "limit: 0.15%" or "specification: 0.15%"
    re.compile(r"(?:limit|specification|spec)(?:ification)?\s*[:\s]\s*([\d.]+\s*" + _UNIT_ALT + r")", re.IGNORECASE),
    # D-GRD3: "≤ 0.15%" or "<= 0.15%"
    re.compile(r"[≤<]=?\s*([\d.]+\s*" + _UNIT_ALT + r")", re.IGNORECASE),
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


def _real_anchor_offset(canonical: str, *candidates: str) -> int:
    """WR-01: return the offset of a REAL occurrence of the link anchor in canonical.

    The prior code anchored hyperlink/PDF-link edges at a FABRICATED offset
    (`para_idx * 50`, `page_num * 100`) that has no relationship to where the link
    actually occurs. That span was byte-exact re-openable, so the grounding gate
    passed — but it cited the WRONG text, undermining the verbatim-anchor guarantee
    (grounding integrity).

    This helper searches canonical (case-insensitively) for the first candidate anchor
    string — e.g. the link target's filename stem or the display text — and returns its
    real offset. When no candidate is found in canonical there IS no in-text position
    for the link (it lives in relationship XML / a PDF annotation, not the flowed text),
    so we return 0 (document start) — a truthful "somewhere in this document" anchor —
    rather than minting a plausible-looking but fabricated offset. Callers that need to
    signal the reduced certainty do so via scoping_confidence at detection time.
    """
    if not canonical:
        return 0
    haystack = canonical.lower()
    for cand in candidates:
        if not cand:
            continue
        needle = cand.strip().lower()
        # Try the filename stem too (targets are often "path/spec_v2.pdf").
        for probe in (needle, needle.split("/")[-1].split("\\")[-1].rsplit(".", 1)[0]):
            probe = probe.strip()
            if probe and len(probe) >= 3:
                idx = haystack.find(probe)
                if idx >= 0:
                    return idx
    return 0


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

def _build_doc_first_lines(corpus: CorpusIndex, manifest: CoverageManifest) -> dict[str, str]:
    """Build a mapping of doc_id -> first non-empty line from canonical text.

    General: extracts the actual heading/title from the parsed document content,
    independent of the classification label (which may use a CTD family name
    rather than the document's own heading). Used by _find_doc_by_outline to match
    reference text against document headings.
    D-GRD3: no corpus-specific constant — derived entirely from document content.
    """
    first_lines: dict[str, str] = {}
    for doc_entry in manifest.documents:
        cache = corpus.cached_entry(doc_entry.doc_id)
        if cache is None:
            continue
        canonical: str = cache.get("canonical", "") or ""
        # First non-empty line from canonical text (may be the document heading)
        for line in canonical.splitlines():
            stripped = line.strip()
            if stripped and len(stripped) >= 4:
                first_lines[doc_entry.doc_id] = stripped.lower()
                break
    return first_lines


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
    # Build first-line index for general content-title matching (D-GRD3: no constants)
    doc_first_lines = _build_doc_first_lines(corpus, manifest)

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
        # WR-02: de-duplicate edges at WRITE time by (src_id, dst_id, edge_type).
        # _REF_PATTERNS overlap (the generic see/refer pattern, the §X pattern and the
        # Table N pattern can all match around the same location) and _span_at_offset
        # coarsens offsets, so multiple matches collapse to the same src_id and would
        # otherwise write near-identical edges -> redundant UNRESOLVED_REF faults
        # downstream (precision noise). Track seen keys in-memory and skip repeats.
        seen_edges: set[tuple[str, str, str]] = set()

        def _add(src_id: str, dst_id: str, edge_type: str, provenance: str) -> bool:
            """Write one edge iff its (src_id, dst_id, edge_type) key is new.

            Returns True when an edge was actually written (so the caller can bump the
            DoS edge_count only for real writes).
            """
            key = (src_id, dst_id, edge_type)
            if key in seen_edges:
                return False
            seen_edges.add(key)
            try:
                edges_module.add_edge(
                    src_id=src_id,
                    dst_id=dst_id,
                    edge_type=edge_type,
                    provenance_span_id=provenance,
                    db_path=db_path,
                )
                return True
            except Exception as exc:
                log.warning("add_edge_failed", doc_id=doc_id, error=str(exc)[:200])
                return False

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
            if not canonical:
                continue
            # WR-01: anchor at a REAL occurrence of the link target in canonical text,
            # not a fabricated `para_idx * 50` offset. If the target string does not
            # appear in the flowed text (it lives in the DOCX relationship XML), fall
            # back to offset 0 — a truthful document-start anchor, never a plausible
            # fake. (CR-01 is now moot here since paragraph_index is no longer used to
            # compute the offset, but the parser still emits it as None.)
            anchor_offset = _real_anchor_offset(canonical, target, hl.get("display", ""))
            src_span = _span_at_offset(doc_id, canonical, anchor_offset, normalizer_version)
            src_id = f"{doc_id}:{src_span.start}"
            # dst: check if target looks like a known doc_id or filename
            dst_doc = _resolve_target_doc(target, doc_ids, manifest)
            dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
            provenance = json.dumps(src_span.model_dump())
            if _add(src_id, dst_id, "hyperlink", provenance):
                edge_count += 1

        # -----------------------------------------------------------------
        # Kind 2: PDF links (from parse/pdf.py 'links' key)
        # D-REF1: link annotations extracted by page.get_links() in Plan 01
        # -----------------------------------------------------------------
        for lnk in cache.get("links", []):
            if edge_count >= _EDGE_CAP_PER_DOC:
                log.warning("edge_cap_reached", doc_id=doc_id, edge_type="pdf_link")
                break
            uri = lnk.get("uri", "") or lnk.get("name", "")
            if not uri:
                continue
            if not canonical:
                continue
            # WR-01: anchor at a REAL occurrence of the link URI in canonical, not a
            # fabricated `page_num * 100` offset. PDF link annotations carry no canonical
            # text offset; if the URI text is not present in the flowed text, fall back
            # to offset 0 rather than a fake per-page offset.
            anchor_offset = _real_anchor_offset(canonical, uri)
            src_span = _span_at_offset(doc_id, canonical, anchor_offset, normalizer_version)
            src_id = f"{doc_id}:{src_span.start}"
            dst_doc = _resolve_target_doc(uri, doc_ids, manifest)
            dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
            provenance = json.dumps(src_span.model_dump())
            if _add(src_id, dst_id, "hyperlink", provenance):
                edge_count += 1

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
                dst_doc = _find_doc_by_outline(ref_text, manifest, doc_ids, doc_first_lines)
                dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
                provenance = json.dumps(src_span.model_dump())
                if _add(src_id, dst_id, "textual_ref", provenance):
                    edge_count += 1

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
                dst_doc = _find_doc_by_outline(ctx_text, manifest, doc_ids, doc_first_lines)
                dst_id = f"{dst_doc}:0" if dst_doc else "unresolved"
                provenance = json.dumps(src_span.model_dump())
                if _add(src_id, dst_id, "value_crossref", provenance):
                    edge_count += 1


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
def _find_doc_by_outline(
    ref_text: str,
    manifest: CoverageManifest,
    doc_ids: set[str],
    doc_first_lines: dict[str, str] | None = None,
) -> str | None:
    """Try to find a referenced doc by matching ref_text against doc titles, filenames and outline labels.

    Resolution strategy (general, D-GRD3: no corpus-specific constant):
    1. Parenthesized filename: if ref_text contains a parenthesized filename that matches a corpus
       doc's filename, return that doc (most precise resolution path).
    2. Bidirectional title containment: checks doc.title, outline labels, and first-line content
       (from doc_first_lines if provided) against ref_text using leading-phrase matching.
       This handles the case where the classification label differs from the document's own
       heading (e.g. classified as "Drug Substance Specification" but heading starts with
       "Analytical Procedures — Impurity Profile").
    3. Filename stem: the doc filename without extension appears in ref_text.

    D-GRD3: all resolution is based on actual doc metadata and corpus content, never corpus-specific
    constants. The caller is responsible for passing the manifest with populated .title / .outline.

    Parameters
    ----------
    ref_text      : the reference text to match against (regex match or context span)
    manifest      : corpus coverage manifest with doc metadata
    doc_ids       : set of known doc_ids (for fast membership checks)
    doc_first_lines : optional {doc_id -> first_line_lower} from _build_doc_first_lines;
                      when provided, enables first-line heading resolution so that a reference
                      like "Analytical Procedures, Table 1" resolves to the doc whose canonical
                      text starts with "Analytical Procedures — Impurity Profile".
    """
    ref_lower = ref_text.lower()

    # --- Pass 1: parenthesized filename (most precise) ---
    # Extract any "(filename.ext)" pattern from ref_text and match against doc filenames.
    # D-GRD3: general regex for any parenthesized document-extension filename.
    _PAREN_FNAME_RE = re.compile(
        r"\(([\w\-]+\.(?:docx?|pdf|xlsx?|pptx?|txt|csv))\)",
        re.IGNORECASE,
    )
    for m in _PAREN_FNAME_RE.finditer(ref_text):
        fname = m.group(1)
        resolved = _resolve_target_doc(fname, doc_ids, manifest)
        if resolved:
            return resolved

    # --- Pass 2: bidirectional title / first-line containment ---
    for doc in manifest.documents:
        # Build candidate title strings from all available sources:
        # (a) classification label  (b) outline entry labels  (c) first-line canonical heading
        candidate_titles: list[str] = []
        if doc.title:
            candidate_titles.append(doc.title.lower())
        for outline_entry in doc.outline:
            if outline_entry.label:
                candidate_titles.append(outline_entry.label.lower())
        if doc_first_lines and doc.doc_id in doc_first_lines:
            candidate_titles.append(doc_first_lines[doc.doc_id])

        for candidate_title in candidate_titles:
            if not candidate_title:
                continue
            # Forward: full candidate title appears inside ref_lower
            if candidate_title in ref_lower:
                return doc.doc_id
            # Bidirectional: leading N words of candidate title appear as a phrase in ref_lower.
            # Progressively shorter leading phrases (min 2 words, min 6 chars).
            # General: "Analytical Procedures" from "Analytical Procedures — Impurity Profile"
            # matches "see Analytical Procedures, Table 1" (ref truncates at comma).
            title_words = re.split(r"[\s\-—–]+", candidate_title)
            for length in range(len(title_words), 1, -1):
                phrase = " ".join(title_words[:length])
                if len(phrase) >= 6 and phrase in ref_lower:
                    return doc.doc_id

    # --- Pass 3: filename stem containment ---
    for doc in manifest.documents:
        if doc.filename:
            stem = doc.filename.lower().rsplit(".", 1)[0]
            if stem and len(stem) >= 3 and stem in ref_lower:
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
                # cell_text here is the col-0 ROW LABEL for this row.
                label_text = cell_text
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

                # CR-05 (Ruling 6, Step 4 — LABEL MATCHING): the referenced limit
                # governs the referenced ENTITY, not every over-limit row in the table.
                # Emit 'full' confidence ONLY when this row's col-0 label matches the
                # referenced entity_name (case-insensitive containment, both directions).
                # When there is no confident entity match we do NOT drop the candidate
                # (that would cost recall); instead we over-emit at LOWERED 'low'
                # confidence so the Phase-7 verifier can adjudicate (recall-biased
                # handoff, D-REF3). Only a real cross-ref edge type can ever reach 'full'.
                label_matches = _entity_matches_label(entity_name, label_text)
                edge_is_crossref = edge_type in ("hyperlink", "textual_ref", "value_crossref")
                if label_matches and edge_is_crossref:
                    confidence = "full"
                else:
                    # value exceeds limit but the row is not the referenced entity
                    # (or entity was not confidently extracted): recall-biased lead.
                    confidence = "low"

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

    return _dedup_reference_faults(faults)


# ---------------------------------------------------------------------------
# Helper: de-duplicate anomaly faults (WR-02)
# ---------------------------------------------------------------------------
def _dedup_reference_faults(faults: list[Fault]) -> list[Fault]:
    """WR-02: drop near-identical anomaly faults, preserving every DISTINCT one.

    Edge-level dedup (in extract_references) removes duplicate edges, but overlapping
    patterns / coarse offsets can still yield faults that describe the SAME anomaly
    between the same document pair anchored at the same span. Dedup on a key that is
    specific enough to NEVER merge two genuinely different findings:
      (anomaly, src_doc, src_start, dst_doc, dst_start)
    The src/dst START offsets keep two contradictions about different table rows (or
    two references at different positions) as separate faults — recall-safe.
    """
    seen: set[tuple] = set()
    unique: list[Fault] = []
    for f in faults:
        anchor = f.reference_anchor
        if anchor is None:
            unique.append(f)
            continue
        src = anchor.src_span_id
        dst = anchor.dst_span_id
        key = (
            anchor.anomaly,
            getattr(src, "doc_id", None), getattr(src, "start", None),
            getattr(dst, "doc_id", None), getattr(dst, "start", None),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)
    return unique


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
# Helper: entity <-> row-label match (CR-05, Ruling 6 Step 4)
# ---------------------------------------------------------------------------
def _entity_matches_label(entity_name: str | None, label_text: str) -> bool:
    """Return True when the referenced entity plausibly names this dst row.

    CR-05: full-confidence VALUE_CONTRADICTION requires that the dst row's col-0
    label corresponds to the entity the src limit governs. Match is case-insensitive
    containment in EITHER direction (the row label may abbreviate/extend the
    referenced entity, or vice versa). No confident entity or empty label -> no
    match (caller then emits a LOW-confidence recall-biased lead, never drops it).
    D-GRD3: pure string comparison over document content, no corpus constant.
    """
    if not entity_name:
        return False
    e = entity_name.strip().lower()
    lab = (label_text or "").strip().lower()
    if not e or not lab:
        return False
    return e in lab or lab in e


# ---------------------------------------------------------------------------
# Helper: extract entity name from src span text
# ---------------------------------------------------------------------------
# WR-08: general stop-phrases that the broad capitalized-prose pattern would
# otherwise mint as a spurious "entity" (e.g. "Not More", "See Analytical",
# "The Specification"). These are cue/limit/article words, never entity names.
# D-GRD3: general English function words + this module's own cue vocabulary —
# NOT a corpus-specific constant.
_ENTITY_STOPWORDS = frozenset({
    "the", "not", "more", "less", "than", "see", "refer", "per", "as",
    "described", "stated", "in", "for", "any", "single", "limit",
    "specification", "spec", "section", "module", "table", "figure", "and", "or",
})


def _extract_entity_name(src_text: str) -> str | None:
    """Extract a referenced entity name (compound, substance, parameter) from src text.

    WR-08: the previous pattern matched almost any capitalized word (plus up to two
    trailing words), so "See Analytical", "Not More", or "The Specification" became
    the entity. Now we require a capitalized head token that is NOT a stop/cue word,
    and we strip trailing stop words. Returns None when no confident entity is found
    (abstain) rather than a generic phrase — CR-05 then emits a low-confidence lead.
    D-GRD3: general extraction — no inline corpus constant.
    """
    # D-GRD3: general compound/substance name pattern — inside re.compile()
    _ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z0-9][\w]*){0,2})\b", re.UNICODE)
    for m in _ENTITY_PATTERN.finditer(src_text):
        candidate = m.group(1).strip()
        tokens = candidate.split()
        # Reject if the HEAD token is a stop/cue word (kills "See ...", "Not ...",
        # "The ...", "Section ...").
        if tokens and tokens[0].lower() in _ENTITY_STOPWORDS:
            continue
        # Drop trailing stop words so "Compound A for" -> "Compound A".
        while tokens and tokens[-1].lower() in _ENTITY_STOPWORDS:
            tokens.pop()
        if not tokens:
            continue
        result = " ".join(tokens).strip()
        if result:
            return result
    return None
