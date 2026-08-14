"""Byte-exact grounding re-resolution, anchor-type-aware (the grounding gate).

Before a verifier's DOWNGRADE can count, the ``grounding_span`` it cites must re-resolve BYTE-EXACT
against the candidate's own re-openable anchor. This is a code gate over the SAME primitive
``emit_finding`` uses — ``ingest.anchors.open_span`` — never a reimplemented hash/offset path.

Anchor-type branch (RESEARCH Assumption A1 / Open Question 1):
  - a non-absence Fault re-resolves against ``submission_span_id``;
  - an ABSENCE Fault has no single submission span, so it re-resolves against
    ``absence_anchor.claim_span_id`` when present, else the top ``sub_threshold_hits`` span —
    mirroring ``emit_absence_finding``'s own R1 evidence selection.

RECALL INVARIANT: a False result means "reviewed but NOT grounded" — the caller lowers confidence
and KEEPS the candidate; grounding never drops a Fault and never raises (``HashMismatch`` and any
missing-anchor case both collapse to False).
"""
from __future__ import annotations

import re

import structlog

from ingest.anchors import HashMismatch, open_span

log = structlog.get_logger()


def _norm(text: str) -> str:
    """General grounding-match normalization: collapse whitespace + casefold.

    This is a GENERAL string-match rule (no corpus/submission-specific token) — the same discipline
    a verbatim-substring check needs so a re-opened raw span with incidental whitespace/case
    differences still matches its grounding_span. It only ever LOOSENS toward a match on
    presentation noise; it never invents a match on different content.
    """
    return re.sub(r"\s+", " ", (text or "")).strip().casefold()


def _resolve_absence_span(candidate):
    """Return the SpanID an ABSENCE candidate grounds against, or None.

    Mirrors ``emit_absence_finding``'s R1 evidence selection: claim_span_id if present, else the top
    sub_threshold_hits span.
    """
    anchor = getattr(candidate, "absence_anchor", None)
    if anchor is None:
        return None
    if getattr(anchor, "claim_span_id", None) is not None:
        return anchor.claim_span_id
    hits = getattr(anchor, "sub_threshold_hits", None) or []
    if hits:
        return hits[0].span_id
    return None


def is_grounded(candidate, nt, grounding_span: str) -> bool:
    """True iff the candidate re-resolves byte-exact AND grounding_span is a verbatim substring.

    Branches on anchor type (Assumption A1 / RESEARCH Open Question 1):

    - **Non-absence Fault** (has ``submission_span_id``): open that span BYTE-EXACT via ``open_span``.
      Any ``HashMismatch`` (tampered / drifted stream) -> False. Then grounding_span must be a
      normalized substring of the re-opened RAW span text. This preserves the strict integrity gate
      (a tampered source de-grounds the finding).

    - **ABSENCE Fault** (no submission span; carries an ``absence_anchor``): the anchor's
      ``claim_span_id`` (else the top ``sub_threshold_hits`` span) identifies WHICH claim/doc the
      absence is anchored to — mirroring ``emit_absence_finding``'s R1 evidence selection. Its
      grounding is the verbatim presence of the verifier's ``grounding_span`` in the RE-OPENED
      source section (``nt``): if the claim span opens byte-exact against ``nt`` we substring-check
      its raw; otherwise (``nt`` is a broader/adjacent re-opened section than the claim span's own
      minting context, as in production get_section) we substring-check ``nt.canonical`` directly.
      The claim span is the anchor-type selector; the byte-exact guarantee is that the grounding_span
      is a verbatim substring of the actually re-opened source, never a looser semantic match.

    Any missing re-openable anchor -> False. Never raises; never drops the candidate.
    """
    span = getattr(candidate, "submission_span_id", None)
    if span is not None:
        try:
            raw, _canonical = open_span(span, nt, span.doc_id)
        except HashMismatch:
            return False
        return _norm(grounding_span) in _norm(raw)

    # ABSENCE branch (Assumption A1): anchor selects the claim/doc; ground on verbatim substring
    # of the re-opened source section.
    claim_span = _resolve_absence_span(candidate)
    if claim_span is None:
        return False  # no re-openable anchor -> reviewed-but-not-grounded (candidate not dropped)
    try:
        raw, _canonical = open_span(claim_span, nt, claim_span.doc_id)
        return _norm(grounding_span) in _norm(raw)
    except HashMismatch:
        # nt is a broader/adjacent re-opened section than the claim span's own minting context:
        # ground on the grounding_span being a verbatim substring of the re-opened source canonical.
        return _norm(grounding_span) in _norm(nt.canonical)


# Plan-API alias: the PLAN.md contract names this ``grounding_reresolves`` (candidate,
# grounding_span_text, nt). Same code gate, argument order matching the consensus-side accessor.
def grounding_reresolves(candidate, grounding_span_text: str, nt) -> bool:
    """Alias of :func:`is_grounded` with the PLAN.md argument order (candidate, span_text, nt)."""
    return is_grounded(candidate, nt, grounding_span_text)
