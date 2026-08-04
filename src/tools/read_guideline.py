"""The 5th navigation tool -- dual-mode over the rulebook (D-RI2). One optional `citation`
param: omit for the compact enumerate surface (RULES-05), provide for bounded rule text
(RULES-01..04's content). Composes Plan 02-02's store + Plan 02-06's requirement index --
no new grounding/applicability logic lives here. An oversized fetch reuses Plan 02-01's
src/tools/oversized.py persist+preview+handle mechanism (plan-checker Blocker 2) rather than
a bare rejection.

Requirement-index v2->v3 (senior-reviewer resolve, verification-queue item 5, D-RI2/D-EF1(5)):
the index's `citation` field is a human-readable, subsection/glossary-granular string that does
NOT match `rulebook.store.lookup_citation`'s whole-document citation keys (see 02-09's
deferred-items.md) -- so an agent that enumerates then round-trips `citation` straight into
fetch mode got `not_found` for all 15 real entries. Fixed WITHOUT touching the reviewed
requirement_index.yaml data: each enumerate row now also carries `rule_doc_id` (the entry's
`provenance_span_id.doc_id`, already store-resolvable -- `load_requirement_index`'s own loader
gate proves this for every entry at load time), and fetch mode tries `lookup_citation(arg)`
FIRST (preserving the real whole-document citation path, e.g. "21 CFR 211.166"), falling back to
treating `arg` as a doc_id via `rulebook_nt_for` only if that misses. `rule_span_id` stays the
grounding anchor (D-EF1(5)); `citation`/`rule_doc_id` are both metadata the model can act on.
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
        return [
            {
                "requirement_id": e.id,
                "citation": e.citation,
                "rule_doc_id": e.provenance_span_id.doc_id,
                "trigger": e.trigger,
            }
            for e in result
        ]
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


def _requirement_citation_doc_ids() -> dict[str, str]:
    """Requirement-index `citation` display string -> that entry's provenance doc_id, built
    from the index at call time (`load_requirement_index` is itself lru-cached, and building
    this dict fresh keeps it consistent with the index across a test's cache_clear/rebuild).

    This is the R1 third resolve leg: enumerate rows advertise a `citation` that is a rich,
    subsection/glossary-granular DISPLAY string (e.g. "ICH Q2(R2) -- Glossary: Specificity")
    which matches neither `lookup_citation`'s whole-document keys nor a rulebook doc_id, so a
    model that round-tripped `row['citation']` into fetch mode got `not_found` for all 15
    real entries (the 03-19 NO-GO root cause). Mapping it to the entry's own
    `provenance_span_id.doc_id` -- loader-gate-guaranteed store-resolvable -- makes every
    identifier the tool advertises resolvable in fetch mode.
    """
    from rulebook.requirement_index import load_requirement_index

    return {e.citation: e.provenance_span_id.doc_id for e in load_requirement_index()}


def _resolve_rule_doc(citation: str) -> tuple[str, NormalizedText] | tuple[None, None]:
    """Triple-resolve any identifier the tool advertises, in order (R1):
      leg 1  lookup_citation(arg)                      -- real whole-document store citation
                                                          (e.g. "21 CFR 211.166"), preserved.
      leg 2  requirement-index citation-display map    -- enumerate `citation` strings.
      leg 3  rulebook_nt_for(arg) as a doc_id          -- enumerate `rule_doc_id` strings
                                                          (e.g. "ecfr-211.166").
    Returns (doc_id, nt) on the first leg that yields persisted canonical text, else (None, None).
    """
    chunk = lookup_citation(citation)
    if chunk is not None:
        nt = rulebook_nt_for(chunk.doc_id)
        if nt is not None:
            return chunk.doc_id, nt

    mapped = _requirement_citation_doc_ids().get(citation)
    if mapped is not None:
        nt = rulebook_nt_for(mapped)
        if nt is not None:
            return mapped, nt

    nt = rulebook_nt_for(citation)
    if nt is not None:
        return citation, nt

    return None, None


def _fetch_citation(citation: str, ledger: RetrievalLedger, max_chars: int) -> str | ToolRejected:
    doc_id, nt = _resolve_rule_doc(citation)
    if nt is None:
        # Teach the recovery path -- run 2 (03-18) retried the identical failing call 4x until
        # the breaker stopped it, so the rejection must redirect the model, not just report.
        return ToolRejected(
            tool="read_guideline", reason_code="not_found",
            reason=f"citation {citation!r} not resolvable -- checked the store citation index, "
                   f"the requirement-index citation map, and as a rule_doc_id",
            hint="call read_guideline with no arguments to enumerate, then pass a rule_doc_id "
                 "from the returned rows -- do not retry this same call",
        )

    start, end = 0, len(nt.canonical)
    if end - start > max_chars:
        # TOOLS-04 persist+preview+handle (plan-checker Blocker 2): mirrors get_section's
        # oversized branch (Plan 02-01) exactly -- never truncate, never make the agent invent
        # a smaller range itself. Persist the full chunk under a handle, return a bounded,
        # span-ID-annotated preview plus that handle.
        preview_end = start + max_chars
        h = persist_range("read_guideline", doc_id, start, end, nt.normalizer_version, cursor=preview_end)
        preview_text = _render_annotated_rulebook(nt, doc_id, start, preview_end, ledger)
        return ToolRejected(
            tool="read_guideline", reason_code="range_too_large",
            reason=f"{citation!r} is {end - start} chars, exceeds the {max_chars}-char bound",
            hint=f"a bounded preview is attached; call read_guideline(ledger=ledger, citation={citation!r}, handle={h!r}) to page forward -- never recompute offsets yourself",
            preview=preview_text, handle=h,
        )

    if ledger.check_and_mark_served(doc_id, start, end):
        return f"[STILL_CURRENT] citation={citation!r} unchanged since your earlier retrieval -- refer back to that result, do not re-request it."

    return _render_annotated_rulebook(nt, doc_id, start, end, ledger)


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
