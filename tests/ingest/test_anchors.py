"""Tests for the span-ID re-open/verify primitive (Plan 06 Task 1 / INGEST-04, D-21)."""
from __future__ import annotations

import pytest

from ingest.anchors import HashMismatch, mint_span, open_span, short_hash
from ingest.normalize import normalize


def test_reopen_and_hash_mismatch():
    nt = normalize("specifi-\ncation and assay")  # "specification" rejoins: hyphen+\n dropped
    doc_id = "d1"

    # whole-document span re-opens byte-for-byte on BOTH sides
    full = mint_span(nt.canonical, 0, len(nt.canonical), doc_id, nt.normalizer_version)
    raw, canonical = open_span(full, nt, doc_id)
    assert canonical == nt.canonical
    assert raw == nt.raw_serialized

    # a span over "specification" returns the dropped hyphen+newline on the RAW side (D-22)
    start = nt.canonical.index("specification")
    end = start + len("specification")
    span = mint_span(nt.canonical, start, end, doc_id, nt.normalizer_version)
    raw2, canon2 = open_span(span, nt, doc_id)
    assert canon2 == "specification"
    assert "-" in raw2 and "\n" in raw2

    # TAMPER within the span (same length, preserves offsets) -> HashMismatch
    tampered = nt.model_copy(update={"canonical": nt.canonical[:start] + "X" * (end - start) + nt.canonical[end:]})
    with pytest.raises(HashMismatch):
        open_span(span, tampered, doc_id)

    # WRONG normalizer version at mint -> HashMismatch on open under the real version
    wrong_ver = mint_span(nt.canonical, start, end, doc_id, "some-other-version/9")
    with pytest.raises(HashMismatch):
        open_span(wrong_ver, nt, doc_id)

    # wrong doc_id -> HashMismatch (never a wrong-doc citation)
    with pytest.raises(HashMismatch):
        open_span(span, nt, "d2")


def test_short_hash_is_version_bound():
    assert short_hash("abc", "v1") != short_hash("abc", "v2")
    assert short_hash("abc", "v1") == short_hash("abc", "v1")
