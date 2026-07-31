"""get_section -- bounded, span-annotated section reads (TOOLS-01/02/04, COST-04).

Every returned sentence carries an inline `[doc_id:start:end]` span-ID marker (D-GRAN cat -n
pattern) minted over the doc's own canonical text + normalizer_version -- the agent SELECTS an
issued ID, it never computes offsets. An oversized range is NEVER truncated: the full range is
persisted under a handle (src/tools/oversized.py, TOOLS-04 plan-checker Blocker 2) and a
bounded, span-ID-annotated PREVIEW is returned alongside it, so the agent can cite from the
preview immediately AND page forward via the handle without inventing a new (start,end) itself.

Bounds-check / dedup-check / render ORDER matters: validate the range first (so a rejected
request never gets marked "served"), THEN dedup-check (only a genuinely valid, in-bounds
request consumes a dedup slot), THEN render.
"""
from __future__ import annotations

from ingest.anchors import mint_span
from ingest.corpus import CorpusIndex
from ingest.manifest import DocEntry
from schemas.documents import NormalizedText, OffsetRun
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.oversized import advance_cursor, load_range, persist_range
from tools.textsplit import split_sentences


def _nt_from_cache_entry(entry: dict) -> NormalizedText:
    return NormalizedText(
        canonical=entry["canonical"],
        raw_serialized=entry["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in entry["offset_map"]],
        normalizer_version=entry["normalizer_version"],
        serializer_version=entry["serializer_version"],
    )


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


def get_section(
    corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger,
    start: int | None = None, end: int | None = None, heading: str | None = None,
    handle: str | None = None, max_chars: int = 8000,
) -> str | ToolRejected:
    cache = corpus.cached_entry(doc_id)
    if cache is None:
        return ToolRejected(
            tool="get_section", reason_code="not_found",
            reason=f"doc_id {doc_id!r} has no cached substrate", hint="call open_doc first",
        )
    nt = _nt_from_cache_entry(cache)
    doc_entry = DocEntry.model_validate(cache["doc_entry"])

    if handle is not None:
        # TOOLS-04 persist+preview+handle continuation (plan-checker Blocker 2): resume an
        # earlier oversized read WITHOUT the agent computing any new (start,end) itself.
        descriptor = load_range(handle)
        if descriptor is None or descriptor["doc_id"] != doc_id:
            return ToolRejected(
                tool="get_section", reason_code="not_found",
                reason=f"handle {handle!r} is unknown, expired, or belongs to a different doc_id",
                hint="re-issue the original oversized get_section call to obtain a fresh handle",
            )
        cursor, range_end = descriptor["cursor"], descriptor["end"]
        if cursor >= range_end:
            return f"[STILL_CURRENT] handle={handle!r} range fully served -- nothing more to page forward."
        chunk_end = min(cursor + max_chars, range_end)
        text = _render_annotated(nt, doc_id, cursor, chunk_end, ledger)
        advance_cursor(handle, chunk_end)
        return text

    if heading is not None:
        matches = [o for o in doc_entry.outline if heading.lower() in o.label.lower()]
        if not matches:
            return ToolRejected(
                tool="get_section", reason_code="not_found",
                reason=f"no outline heading matches {heading!r}",
                hint="call open_doc to see the real outline labels",
            )
        ordered = sorted(doc_entry.outline, key=lambda o: o.span.start)
        idx = ordered.index(matches[0])
        start = matches[0].span.start
        end = ordered[idx + 1].span.start if idx + 1 < len(ordered) else len(nt.canonical)

    if start is None or end is None:
        return ToolRejected(
            tool="get_section", reason_code="not_found",
            reason="must pass (start,end), heading, or handle",
            hint="provide start+end char offsets, a heading string, or a previously-issued handle",
        )

    start, end = max(0, start), min(len(nt.canonical), end)
    if end <= start:
        return ToolRejected(
            tool="get_section", reason_code="not_found",
            reason=f"range [{start}:{end}) is empty or out of bounds",
            hint="pass a valid, non-empty range",
        )
    if end - start > max_chars:
        # TOOLS-04 persist+preview+handle (plan-checker Blocker 2): NEVER truncate, and NEVER
        # make the recovery step "the agent invents a smaller (start,end) by arithmetic" -- that
        # is exactly what D-GRAN forbids. Persist the full range under a handle, and hand back a
        # bounded, span-ID-annotated PREVIEW (real, issued span-IDs to cite from immediately)
        # plus that handle for a follow-up page-forward call.
        preview_end = start + max_chars
        handle_id = persist_range(
            "get_section", doc_id, start, end, nt.normalizer_version, cursor=preview_end,
        )
        preview_text = _render_annotated(nt, doc_id, start, preview_end, ledger)
        return ToolRejected(
            tool="get_section", reason_code="range_too_large",
            reason=f"requested range is {end - start} chars, exceeds the {max_chars}-char bound",
            hint=(
                f"a bounded preview is attached; call get_section(doc_id={doc_id!r}, "
                f"ledger=ledger, handle={handle_id!r}) to page forward -- never recompute "
                "(start,end) yourself"
            ),
            preview=preview_text, handle=handle_id,
        )

    if ledger.check_and_mark_served(doc_id, start, end):
        return (
            f"[STILL_CURRENT] doc={doc_id} range=[{start}:{end}) unchanged since your earlier "
            "retrieval -- refer back to that result, do not re-request it."
        )

    return _render_annotated(nt, doc_id, start, end, ledger)
