"""open_doc -- lightweight per-document metadata + outline (TOOLS-01).

Returns identifiers only (status, structure/table availability tiers, classification, an
outline of span-ID-anchored headings) -- NEVER the document's full canonical text. The agent
opens a document to decide WHERE to read next; `get_section` is what actually returns text.
"""
from __future__ import annotations

from ingest.corpus import CorpusIndex
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger


def open_doc(corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger) -> dict | ToolRejected:
    entry = next((d for d in corpus.manifest.documents if d.doc_id == doc_id), None)
    if entry is None:
        return ToolRejected(
            tool="open_doc", reason_code="not_found",
            reason=f"doc_id {doc_id!r} is not in this corpus's manifest",
            hint="call search_corpus first to discover valid doc_ids",
        )
    for outline_entry in entry.outline:
        ledger.record_span(outline_entry.span)
    return {
        "doc_id": entry.doc_id,
        "title": entry.title,
        "filename": entry.filename,
        "status": entry.status,
        "structure": entry.structure,
        "tables": entry.tables,
        "classification": entry.classification.model_dump() if entry.classification else None,
        "outline": [
            {"label": o.label, "level": o.level, "span_id": o.span.model_dump()}
            for o in entry.outline
        ],
    }
