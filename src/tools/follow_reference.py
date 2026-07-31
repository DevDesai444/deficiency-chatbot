"""follow_reference -- same-document reference resolution + typed cross-document-pending stub
(D-FR, TOOLS-01).

Resolves a same-document heading/section reference against the doc's own already-built outline
(no new resolution machinery -- just a search over spans minted at ingest time). Anything this
tool cannot resolve WITHIN this document -- because it genuinely crosses a document boundary, or
because a same-doc reference could not be located -- returns the SAME typed
`cross_document_resolution_pending_phase_4` sentinel: an honest, DECLARED capability boundary
(D-30 ethos), never a silent empty dict/None, never a fabricated span pointing at unrelated text.
Phase 4's full reference graph fills the SAME interface without changing this contract.
"""
from __future__ import annotations

from ingest.corpus import CorpusIndex
from ingest.manifest import DocEntry
from tools.ledger import RetrievalLedger

_CROSS_DOC_PENDING = "cross_document_resolution_pending_phase_4"


def follow_reference(
    corpus: CorpusIndex, doc_id: str, ref_text: str, ledger: RetrievalLedger,
) -> dict:
    cache = corpus.cached_entry(doc_id)
    if cache is None:
        return {"doc_id": doc_id, "ref_text": ref_text, "status": _CROSS_DOC_PENDING}
    doc_entry = DocEntry.model_validate(cache["doc_entry"])
    matches = [o for o in doc_entry.outline if ref_text.strip().lower() in o.label.lower()]
    if matches:
        span = matches[0].span
        ledger.record_span(span)
        return {
            "doc_id": doc_id, "resolved": True,
            "span_id": span.model_dump(), "label": matches[0].label,
        }
    # Cannot tell "genuinely cross-document" from "same-doc reference we failed to locate"
    # without Phase 4's reference graph -- both are honestly reported the same way (D-30:
    # declare the boundary, never fake resolution). Never a silent {} / None.
    return {"doc_id": doc_id, "ref_text": ref_text, "status": _CROSS_DOC_PENDING}
