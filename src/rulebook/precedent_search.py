"""RECALL-04: Precedent-similarity recall leg.

Decisions honored:
  D-PRC1: match unit is section-level — each submission section text is embedded via
           embed_query; results are compared against precedent chunk embeddings.
  D-PRC2: each above-threshold match carries a PrecedentAnchor with submission_span_id
           (the re-openable grounding span on the submission side) + precedent_doc_ids
           + similarity_scores + threshold.
  D-PRC3: same-ANDA exclusion — when submission_anda_number is provided, chunks whose
           anda_number in precedent_provenance matches are excluded. Default None → no
           exclusion (acceptable per A2).
  D-PRC4: absolute dense-cosine threshold (0–1, real range), general, loaded from
           src/evals/baseline/precedent_threshold.json at call time.
  D-PIX1: queries the static global rulebook.faiss asset; NEVER rebuilds it or touches
           the per-submission ephemeral index (Pitfall 4: wrong index type).
  D-PIX3: local FAISS primary; no Databricks mirror in this leg.

B2 fix: _search_rulebook_faiss_with_scores uses direct FAISS IndexFlatIP.search for real
inner-product scores (= cosine for L2-normalized vectors). _rulebook_search_local is NOT
used for this leg because it returns RuleChunk objects without cosine scores.

Pitfall 3: sections with len(section_text) < 100 are skipped silently (degenerate
bge-m3 embeddings on very short text produce unreliable cosine scores).

Pitfall 4 guard: this module NEVER references the per-submission SQLite-rowid index
that cannot support ANDA# metadata filtering. Only rulebook.faiss is queried here.

D-GEN2 note: the inline threshold fallback float is allowed ONLY inside
_load_precedent_threshold. All other functions call _load_precedent_threshold() and
never reference the float literal directly.
Ruling 9 MEDIUM item d: the verify step strips _load_precedent_threshold body before
the inline-float scan.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import numpy as np

import rulebook.precedents as _precedents_module
from rulebook.store import _ensure_faiss, _faiss_doc_ids, _faiss_index
from retrieval.vector_search import embed_query
from schemas.faults import PrecedentAnchor

if TYPE_CHECKING:
    from ingest.corpus import CorpusIndex
    from schemas.faults import Fault
    from tools.errors import ToolRejected
    from tools.ledger import RetrievalLedger

logger = logging.getLogger(__name__)

_PRECEDENT_PREFIX = "precedent-"
_THRESHOLD_PATH = "src/evals/baseline/precedent_threshold.json"
_MIN_SECTION_LEN = 100  # Pitfall 3: skip degenerate-embedding sections


def _load_precedent_threshold() -> float:
    """D-GEN2 exemption: sole function allowed to contain the 0.6 fallback float.
    Reads the absolute dense-cosine threshold from precedent_threshold.json.
    All callers (search_precedents, tests) must use this function, not the literal.
    D-PRC4: the threshold is a general absolute value (0–1 real range), never hardcoded
    in module-level code or in any other function.
    """
    try:
        with open(_THRESHOLD_PATH) as f:
            return float(json.load(f)["threshold"])
    except Exception:
        return 0.6  # D-GEN2 exemption: sole inline float allowed in this function


def _search_rulebook_faiss_with_scores(
    query_text: str,
    top_k: int,
) -> list[tuple[str, float]]:
    """B2 fix: query rulebook FAISS via direct IndexFlatIP.search for real cosine scores.

    Uses _faiss_index (faiss.IndexFlatIP) and _faiss_doc_ids (list[str]) directly.
    IndexFlatIP with L2-normalized vectors: inner product == cosine similarity (range 0–1).

    NOT _rulebook_search_local — that returns RuleChunk objects with no cosine score.
    NOT the per-submission SQLite-rowid index — that is the Pitfall 4 wrong index.

    Returns [(doc_id, cosine_score)] with cosine_score in [0, 1] for L2-normalized vectors.
    """
    _ensure_faiss()
    if _faiss_index is None or not _faiss_doc_ids:
        logger.debug("FAISS index not loaded or empty; returning no results")
        return []

    qv = embed_query(query_text).reshape(1, -1).astype("float32")
    distances, indices = _faiss_index.search(qv, top_k)

    results: list[tuple[str, float]] = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(_faiss_doc_ids):
            continue
        doc_id = _faiss_doc_ids[idx]
        results.append((doc_id, float(dist)))  # IndexFlatIP: dist = cosine for L2-normalized
    return results


def _filter_precedent_chunks(
    raw_results: list[tuple[str, float]],
    submission_anda_number: str | None,
    threshold: float,
) -> list[tuple[str, float]]:
    """Apply three filters to raw FAISS results for the precedent leg.

    Filter 1: doc_id must start with "precedent-" (SC3 — only precedent chunks).
    Filter 2: same-ANDA exclusion via get_provenance when submission_anda_number is set (D-PRC3).
    Filter 3: cosine_score >= threshold (absolute dense-cosine threshold, D-PRC4).

    Receives [(doc_id, cosine_score)] tuples (B2 fix — thresholds on REAL cosine value,
    not on a rank or proxy). Contains NO inline threshold float.
    """
    kept: list[tuple[str, float]] = []
    for doc_id, cosine_score in raw_results:
        # Filter 1: precedent prefix
        if not doc_id.startswith(_PRECEDENT_PREFIX):
            continue

        # Filter 2: same-ANDA exclusion (D-PRC3)
        if submission_anda_number is not None:
            provenance = _precedents_module.get_provenance(doc_id)
            if any(
                str(row.get("anda_number") or "").strip() == str(submission_anda_number).strip()
                for row in provenance
            ):
                logger.debug(
                    "Excluding same-ANDA precedent chunk %s (ANDA# %s)",
                    doc_id,
                    submission_anda_number,
                )
                continue

        # Filter 3: absolute dense-cosine threshold (D-PRC4)
        if cosine_score < threshold:
            continue

        kept.append((doc_id, cosine_score))
    return kept


def search_precedents(
    section_text: str,
    top_k: int = 5,
    threshold: float | None = None,
    submission_anda_number: str | None = None,
) -> list[tuple[str, float]]:
    """Search the rulebook FAISS index for precedent chunks similar to section_text.

    D-PRC1: match unit is section-level; section_text is embedded via embed_query.
    D-PRC3: same-ANDA exclusion via submission_anda_number (None → no exclusion).
    D-PRC4: absolute dense-cosine threshold from precedent_threshold.json.
    Pitfall 3: sections shorter than 100 chars are silently skipped.

    Returns [(doc_id, cosine_score)] sorted by descending cosine score.
    Contains NO inline threshold float — threshold loaded from _load_precedent_threshold().
    """
    # Pitfall 3: skip degenerate-embedding sections (bge-m3 unreliable on very short text)
    if len(section_text) < _MIN_SECTION_LEN:
        logger.debug("Skipping short section (len=%d < %d)", len(section_text), _MIN_SECTION_LEN)
        return []

    effective_threshold = threshold if threshold is not None else _load_precedent_threshold()

    # Retrieve wide (3x top_k) then filter
    raw = _search_rulebook_faiss_with_scores(section_text, top_k * 3)
    filtered = _filter_precedent_chunks(raw, submission_anda_number, effective_threshold)

    # Return sorted by descending cosine score, capped at top_k
    filtered.sort(key=lambda x: -x[1])
    return filtered[:top_k]


def detect_precedent_candidates(
    corpus: "CorpusIndex",
    manifest: object,
    ledger: "RetrievalLedger",
    submission_anda_number: str | None = None,
) -> list["Fault"]:
    """Scan every section in the manifest for precedent similarity candidates.

    For each document in manifest.documents, iterates over outline entries,
    retrieves section text, calls search_precedents per section, and for each
    above-threshold match calls emit_precedent_finding (from Plan 01 / Wave 0).

    D-PRC2: each candidate carries a PrecedentAnchor with submission_span_id,
    precedent_doc_ids, similarity_scores, and threshold.

    Emit path: emit_precedent_finding (imported from tools.emit_finding, defined in
    Plan 01 — no write to emit_finding.py in this plan, B5 fix).
    """
    from tools.emit_finding import emit_precedent_finding
    from schemas.documents import SpanID
    from tools.errors import ToolRejected

    threshold = _load_precedent_threshold()
    faults: list[Fault] = []

    for doc_entry in getattr(manifest, "documents", []):
        doc_id = getattr(doc_entry, "doc_id", None)
        if not doc_id:
            continue

        for outline_entry in getattr(doc_entry, "outline", []):
            section_text = getattr(outline_entry, "text", "") or ""
            if len(section_text) < _MIN_SECTION_LEN:
                continue

            matches = search_precedents(
                section_text,
                submission_anda_number=submission_anda_number,
                threshold=threshold,
            )
            if not matches:
                continue

            # Build a submission span for this section using the outline's span ID
            span_id = getattr(outline_entry, "span_id", None)
            if span_id is None:
                logger.debug("No span_id on outline entry for doc %s; skipping", doc_id)
                continue

            precedent_doc_ids = [doc_id for doc_id, _ in matches]
            similarity_scores = [score for _, score in matches]

            anchor = PrecedentAnchor(
                submission_span_id=span_id,
                precedent_doc_ids=precedent_doc_ids,
                similarity_scores=similarity_scores,
                threshold=threshold,
                anda_excluded=(submission_anda_number is not None),
            )

            result = emit_precedent_finding(
                corpus=corpus,
                precedent_anchor=anchor,
                ledger=ledger,
                title="Precedent similarity candidate",
                detail=(
                    f"Section matched {len(matches)} precedent deficiency pattern(s) "
                    f"with cosine similarity >= {threshold:.3f} (D-PRC4). "
                    f"Top similarity: {similarity_scores[0]:.3f}."
                ),
            )
            if isinstance(result, ToolRejected):
                logger.debug("emit_precedent_finding rejected: %s", result.reason)
            else:
                faults.append(result)

    return faults
