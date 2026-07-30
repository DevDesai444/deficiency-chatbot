"""Span-ID mint + the re-open/verify primitive -- the anchor half of the grounding contract.

A span-ID is content-addressed identity: a char range over the CANONICAL stream plus a short
hash of that substring bound to the normalizer version (D-19). `open_span` is the D-21 re-open
primitive Phase 2's navigation tools rest on: given a span-ID it returns BOTH the raw source
substring (the verbatim citation, D-22) AND the canonical substring, or raises `HashMismatch` --
never one, never a silently-wrong substring. Geometry NEVER enters identity (the boundary law):
physical layout coordinates hang off a span as optional provenance elsewhere, never here.
"""
from __future__ import annotations

import hashlib

from schemas.documents import NormalizedText, SpanID


def short_hash(canonical_substr: str, normalizer_version: str) -> str:
    """Short content-hash of a canonical substring bound to the normalizer version (D-19/D-24).

    Hashing the CANONICAL substring + version gives clean normalizer-drift detection: a
    normalization change shifts the substring and the hash fails loudly on re-open, while the
    version stamp distinguishes an intentional change from tampering. blake2b is a checksum for
    integrity/drift, not an authentication boundary.
    """
    payload = (normalizer_version + "\x00" + canonical_substr).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=8).hexdigest()


class HashMismatch(Exception):
    """Raised when a re-opened span's canonical substring no longer hashes to its span-ID.

    Typed + self-correcting (mirrors ParseFailed): the stored stream drifted, was tampered, or the
    span-ID was minted under a different normalizer version. Never return a wrong citation.
    """

    def __init__(self, span: SpanID, expected: str, actual: str):
        super().__init__(
            f"span {span.doc_id}[{span.start}:{span.end}] hash mismatch: "
            f"expected {expected}, got {actual}"
        )
        self.span = span
        self.expected = expected
        self.actual = actual


def mint_span(canonical: str, start: int, end: int, doc_id: str, normalizer_version: str) -> SpanID:
    """Mint a content-addressed SpanID over canonical[start:end] (arbitrary ranges are valid)."""
    return SpanID(
        doc_id=doc_id,
        start=start,
        end=end,
        hash=short_hash(canonical[start:end], normalizer_version),
    )


def open_span(span: SpanID, nt: NormalizedText, doc_id: str) -> tuple[str, str]:
    """Re-open a span-ID -> (raw_source_substring, canonical_substring) or raise HashMismatch (D-21).

    Verifies the stored canonical substring still hashes to the span-ID (integrity), then renders
    the RAW source substring (the citation) via the offset map -- a canonical range spanning a
    dropped hyphen returns the hyphen+newline on the raw side. Returns BOTH, never one.
    """
    if span.doc_id != doc_id:
        raise HashMismatch(span, span.doc_id, doc_id)
    from ingest.normalize import canon_range_to_raw  # local import: avoids an import cycle at load

    canonical = nt.canonical[span.start:span.end]
    actual = short_hash(canonical, nt.normalizer_version)
    if actual != span.hash:
        raise HashMismatch(span, span.hash, actual)
    raw_s, raw_e = canon_range_to_raw(nt.offset_map, span.start, span.end)
    return nt.raw_serialized[raw_s:raw_e], canonical
