"""Rendered span-reference parsing for the review loop.

This module is the only loop-side path from the model-visible ``[doc_id:start:end]`` form
back to a content-addressed span. The model selects span IDs that tools rendered; it never
computes offsets or hashes.
"""
from __future__ import annotations

import re
from typing import Literal

from ingest.anchors import mint_span
from ingest.corpus import CorpusIndex
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR, rulebook_nt_for
from schemas.documents import NormalizedText, OffsetRun, SpanID
from tools.errors import ToolRejected

SPAN_REF_RE = re.compile(r"\[[^:\[\]]+:\d+:\d+\]")
_SPANREF = re.compile(r"^\[?([^:\[\]]+):(\d+):(\d+)\]?$")


def _nt_from_cache_entry(entry: dict) -> NormalizedText:
    return NormalizedText(
        canonical=entry["canonical"],
        raw_serialized=entry["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in entry["offset_map"]],
        normalizer_version=entry["normalizer_version"],
        serializer_version=entry["serializer_version"],
    )


def _reject(reason_code: str, reason: str) -> ToolRejected:
    return ToolRejected(
        tool="parse_span_ref",
        reason_code=reason_code,
        reason=reason,
        hint="re-open the section with get_section and cite a span-ID from its output",
        half="",
    )


def parse_span_ref(
    ref: str,
    corpus: CorpusIndex,
    rulebook_cache_dir: str,
    expect: Literal["submission", "rule"],
) -> SpanID | ToolRejected:
    """Resolve a rendered span-ID string into a span, or return a typed rejection.

    Pitfall 1 -- THE reason this module exists. The ledger keys on (doc_id,start,end) and
    ignores the content hash, so was_issued() passes even on a wrongly minted span; open_span
    then fails its hash check and emit_finding returns not_byte_exact/half=submission -- which
    D-TEL3 pre-registers as MODEL SPAN INVENTION. A loop-side re-mint bug would therefore be
    diagnosed as a model grounding failure and could drive a WRONG NO-GO. Hence: one path, the
    normalizer_version taken from the store rather than assumed, and DISTINCT loop-side reason
    codes that can never be confused with a gate rejection.

    `expect` is REQUIRED, not inferred: Security Domain V4 forbids resolving against whichever
    store answers first. emit_finding enforces the same separation at the gate; this mirrors it
    at the loop boundary so a store-crossing reference is caught before it reaches the gate.
    """
    match = _SPANREF.fullmatch(ref.strip())
    if match is None:
        return _reject(
            "span_ref_unparseable",
            "span reference did not match the rendered [doc_id:start:end] form",
        )

    doc_id, start_s, end_s = match.groups()
    start, end = int(start_s), int(end_s)

    if expect == "submission":
        entry = corpus.cached_entry(doc_id)
        if entry is None:
            return _reject(
                "span_ref_unknown_doc",
                f"doc_id {doc_id!r} is not in the expected submission corpus store",
            )
        nt = _nt_from_cache_entry(entry)
    else:
        nt = rulebook_nt_for(doc_id, cache_dir=rulebook_cache_dir)
        if nt is None:
            return _reject(
                "span_ref_unknown_doc",
                f"doc_id {doc_id!r} is not in the expected rulebook store",
            )

    if end <= start or end > len(nt.canonical):
        return _reject(
            "span_ref_out_of_range",
            f"span [{start}:{end}) is outside canonical text length {len(nt.canonical)}",
        )

    return mint_span(nt.canonical, start, end, doc_id, nt.normalizer_version)


__all__ = ["SPAN_REF_RE", "parse_span_ref"]
