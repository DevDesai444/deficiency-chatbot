"""follow_reference -- same-document reference resolution + real cross-document edge lookup
(D-FR, TOOLS-01, RECALL-03, Ruling 7).

Resolves a same-document heading/section reference against the doc's own already-built outline
(no new resolution machinery -- just a search over spans minted at ingest time). For references
that cross a document boundary (or same-doc references not found in the outline), performs a
REAL cross-document edge lookup via the edges table (rulebook.edges.get_edges).

Phase 5 (Wave 5) — B4 fix: the cross-document-pending sentinel is NO LONGER returned by any
code path.  Every call path now returns a CONCRETE status:
  - "resolved" / dict with resolved=True:  same-document outline match
  - "resolved_cross_doc":                  real cross-document edge found and resolved
  - "UNRESOLVED_REF":                      no resolved edge found (cross-doc referent absent
                                           or not ingested)

The module-level constant `_CROSS_DOC_PENDING` is RETAINED (not deleted) solely because
src/evals/run.py:813 imports it as a probe sentinel to detect whether follow_reference has
been wired for cross-doc resolution (Plan 06 owns run.py; it is never edited by this plan).
run.py checks `probe_status == _CROSS_DOC_PENDING` to decide the DEFERRED vs HARD path.
After this Wave, NO code path returns _CROSS_DOC_PENDING, so the probe always takes the
HARD path.  The constant is a dead-code value at runtime -- NEVER returned, NEVER set in
any result dict.

Ruling 7 (db_path): all call sites may pass db_path= explicitly; callers that do not pass
it receive the module-default _DB_PATH (same as edges.py's internal default), which is the
correct production path.  Because db_path has a default value, ALL existing call sites
(run.py:822, registry.py:317, test files, etc.) remain valid without modification.
"""
from __future__ import annotations

import logging

from ingest.corpus import CorpusIndex
from ingest.manifest import DocEntry
from rulebook.edges import _DB_PATH as DEFAULT_DB_PATH
from rulebook.edges import get_edges
from tools.ledger import RetrievalLedger

log = logging.getLogger(__name__)

# RETAINED for Plan-06 back-compat import in src/evals/run.py:813.
# This constant is NEVER returned by any follow_reference code path (B4 fix, Wave 5).
# run.py probes: `if probe_status == _CROSS_DOC_PENDING` → since follow_reference now
# returns a real status, this condition is always False → HARD path activated.
_CROSS_DOC_PENDING = "cross_document_resolution_pending_phase_4"


def follow_reference(
    corpus: CorpusIndex,
    doc_id: str,
    ref_text: str,
    ledger: RetrievalLedger,
    span_start: int | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """Resolve a reference against the corpus.

    Resolution order:
    1. Same-document outline search (fast, no DB) — returned immediately if matched.
    2. Cross-document edge lookup via edges table (B4 fix, Ruling 7):
       - If span_start is provided: exact src_key = f"{doc_id}:{span_start}"
       - If span_start is None: log warning; scan all edges for this doc_id prefix
       - Resolved edge → return resolved_cross_doc dict
       - No resolved edge → return UNRESOLVED_REF dict

    The sentinel _CROSS_DOC_PENDING is NEVER returned (B4 fix).

    Parameters
    ----------
    corpus      : ingested CorpusIndex for the submission
    doc_id      : document whose reference to resolve
    ref_text    : the reference text (e.g. "Section 2.3", "Table 19")
    ledger      : retrieval ledger for recording spans
    span_start  : byte offset of the reference span in canonical text (optional; enables
                  exact edge-key lookup when provided)
    db_path     : path to the SQLite edges database (Ruling 7; defaults to the module
                  default so existing call sites need not pass it)
    """
    # ------------------------------------------------------------------
    # Step 1: Same-document outline search (UNCHANGED from Phase 2)
    # ------------------------------------------------------------------
    cache = corpus.cached_entry(doc_id)
    if cache is not None:
        doc_entry = DocEntry.model_validate(cache["doc_entry"])
        matches = [o for o in doc_entry.outline if ref_text.strip().lower() in o.label.lower()]
        if matches:
            span = matches[0].span
            ledger.record_span(span)
            return {
                "doc_id": doc_id, "resolved": True,
                "span_id": span.model_dump(), "label": matches[0].label,
            }

    # ------------------------------------------------------------------
    # Step 2: Cross-document edge lookup (B4 fix — replaces _CROSS_DOC_PENDING sentinel)
    # ------------------------------------------------------------------
    if span_start is not None:
        src_key = f"{doc_id}:{span_start}"
        edges = get_edges(src_id=src_key, db_path=db_path)
    else:
        log.warning(
            "follow_reference: span_start not provided for doc_id=%s; "
            "scanning all edges for this doc prefix (slow path)",
            doc_id,
        )
        all_edges = get_edges(src_id=None, db_path=db_path)
        edges = [e for e in all_edges if e[0].startswith(f"{doc_id}:")]

    # Find a resolved (non-"unresolved") edge
    for src_id, dst_id, edge_type, _provenance in edges:
        if dst_id and dst_id != "unresolved":
            # Parse dst_id: "{dst_doc_id}:{dst_start}"
            try:
                dst_doc_id, _dst_start_str = dst_id.rsplit(":", 1)
            except ValueError:
                dst_doc_id = dst_id
            return {
                "doc_id": dst_doc_id,
                "resolved": True,
                "edge_type": edge_type,
                "label": ref_text,
                "status": "resolved_cross_doc",
            }

    # No resolved edge found — return a typed UNRESOLVED_REF status.
    # This is a REAL typed status (not the pending sentinel) — see module docstring.
    return {"doc_id": doc_id, "ref_text": ref_text, "status": "UNRESOLVED_REF"}
