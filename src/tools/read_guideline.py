"""The 5th navigation tool -- dual-mode over the rulebook (D-RI2). One optional `citation`
param: omit for the compact enumerate surface (RULES-05), provide for bounded rule text
(RULES-01..04's content). Composes Plan 02-02's store + Plan 02-06's requirement index --
no new grounding/applicability logic lives here. An oversized fetch reuses Plan 02-01's
src/tools/oversized.py persist+preview+handle mechanism (plan-checker Blocker 2) rather than
a bare rejection.
"""
from __future__ import annotations

from ingest.anchors import mint_span
from ingest.manifest import CoverageManifest
from rulebook.requirement_index import enumerate_requirements
from rulebook.store import lookup_citation, rulebook_nt_for
from schemas.documents import NormalizedText
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.oversized import advance_cursor, load_range, persist_range
from tools.textsplit import split_sentences


def read_guideline(
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    citation: str | None = None,
    family: str | None = None,
    handle: str | None = None,
    max_chars: int = 8000,
) -> list[dict] | str | ToolRejected:
    if handle is not None:
        return _resume_handle(handle, ledger, max_chars)
    if citation is None:
        result = enumerate_requirements(manifest, family=family)
        if isinstance(result, ToolRejected):
            return result
        return [{"requirement_id": e.id, "citation": e.citation, "trigger": e.trigger} for e in result]
    return _fetch_citation(citation, ledger, max_chars)


def _render_annotated_rulebook(
    nt: NormalizedText, doc_id: str, start: int, end: int, ledger: RetrievalLedger,
) -> str:
    """Same cat -n annotation shape as get_section._render_annotated (Plan 02-01), applied over
    the RULEBOOK store's NormalizedText -- shared by the normal fetch path, the oversized-preview
    path, and the handle-continuation path so all three annotate identically."""
    out = []
    for s_off, e_off in split_sentences(nt.canonical[start:end]):
        s_abs, e_abs = start + s_off, start + e_off
        span = mint_span(nt.canonical, s_abs, e_abs, doc_id, nt.normalizer_version)
        ledger.record_span(span)
        out.append(f"[{doc_id}:{s_abs}:{e_abs}] {nt.canonical[s_abs:e_abs]}")
    return "\n".join(out)


def _fetch_citation(citation: str, ledger: RetrievalLedger, max_chars: int) -> str | ToolRejected:
    chunk = lookup_citation(citation)
    if chunk is None:
        return ToolRejected(tool="read_guideline", reason_code="not_found",
                             reason=f"citation {citation!r} does not resolve to any vendored rulebook chunk",
                             hint="call read_guideline() with no citation to see the applicable requirement index and its usable citation strings")
    nt = rulebook_nt_for(chunk.doc_id)
    if nt is None:
        return ToolRejected(tool="read_guideline", reason_code="not_found",
                             reason=f"chunk {chunk.doc_id!r} has no persisted canonical text", hint="")

    start, end = 0, len(nt.canonical)
    if end - start > max_chars:
        # TOOLS-04 persist+preview+handle (plan-checker Blocker 2): mirrors get_section's
        # oversized branch (Plan 02-01) exactly -- never truncate, never make the agent invent
        # a smaller range itself. Persist the full chunk under a handle, return a bounded,
        # span-ID-annotated preview plus that handle.
        preview_end = start + max_chars
        h = persist_range("read_guideline", chunk.doc_id, start, end, nt.normalizer_version, cursor=preview_end)
        preview_text = _render_annotated_rulebook(nt, chunk.doc_id, start, preview_end, ledger)
        return ToolRejected(
            tool="read_guideline", reason_code="range_too_large",
            reason=f"{citation!r} is {end - start} chars, exceeds the {max_chars}-char bound",
            hint=f"a bounded preview is attached; call read_guideline(ledger=ledger, citation={citation!r}, handle={h!r}) to page forward -- never recompute offsets yourself",
            preview=preview_text, handle=h,
        )

    if ledger.check_and_mark_served(chunk.doc_id, start, end):
        return f"[STILL_CURRENT] citation={citation!r} unchanged since your earlier retrieval -- refer back to that result, do not re-request it."

    return _render_annotated_rulebook(nt, chunk.doc_id, start, end, ledger)


def _resume_handle(handle: str, ledger: RetrievalLedger, max_chars: int) -> str | ToolRejected:
    descriptor = load_range(handle)
    if descriptor is None:
        return ToolRejected(tool="read_guideline", reason_code="not_found",
                             reason=f"handle {handle!r} is unknown or expired",
                             hint="re-issue the original oversized read_guideline(citation=...) call for a fresh handle")
    doc_id, cursor, range_end = descriptor["doc_id"], descriptor["cursor"], descriptor["end"]
    nt = rulebook_nt_for(doc_id)
    if nt is None or cursor >= range_end:
        return f"[STILL_CURRENT] handle={handle!r} range fully served -- nothing more to page forward."
    chunk_end = min(cursor + max_chars, range_end)
    text = _render_annotated_rulebook(nt, doc_id, cursor, chunk_end, ledger)
    advance_cursor(handle, chunk_end)
    return text
