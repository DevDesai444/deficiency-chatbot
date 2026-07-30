"""Tests for the coverage manifest + content-hash store (Plan 07 / INGEST-03, D-14/D-24/D-30/D-32)."""
from __future__ import annotations

from ingest.manifest import CoverageManifest, DocEntry, OutlineEntry
from ingest.store import (
    cache_key,
    content_hash,
    load_manifest,
    read_doc_cache,
    save_manifest,
    write_doc_cache,
)
from schemas.documents import DocClassification, SpanID


def test_cache_resume_and_invalidate(tmp_path):
    cache_dir = tmp_path / "cache"
    h = content_hash(b"file-bytes-v1")
    nv, sv = "nfc-.../1-lex1", "reading-order-cells/1"
    key = cache_key(h, nv, sv)
    entry = {"canonical": "specification", "raw_serialized": "specifi-\ncation",
             "offset_map": [], "normalizer_version": nv, "serializer_version": sv}

    write_doc_cache(cache_dir, key, entry)
    # skip-unchanged: same (hash, versions) -> hit
    got = read_doc_cache(cache_dir, key)
    assert got is not None and got["canonical"] == "specification"
    # atomic write leaves NO .tmp after success
    assert list(cache_dir.glob("*.tmp")) == []

    # normalizer-version bump -> different key -> MISS (invalidation, D-24)
    key_bumped = cache_key(h, "nfc-.../2-lex1", sv)
    assert key_bumped != key
    assert read_doc_cache(cache_dir, key_bumped) is None

    # simulated crash BEFORE rename: only a .tmp exists -> read still returns None (no half entry)
    crash_key = cache_key(content_hash(b"other"), nv, sv)
    (cache_dir / f"{crash_key}.tmp").write_text("{partial", encoding="utf-8")
    assert read_doc_cache(cache_dir, crash_key) is None


def test_manifest_availability_tiers(tmp_path):
    db = str(tmp_path / "corpus.db")
    span = SpanID(doc_id="d", start=0, end=3, hash="ab")
    flat = DocEntry(
        doc_id="d", filename="scan.pdf", content_hash="h",
        status="parsed_partial", reason="scanned page 4: OCR flat text, tables not reconstructed",
        structure="flat", tables="unavailable",
        classification=DocClassification(label="scanned spec", family_guess="3.2.S.4.1", confidence=0.4, tier="llm"),
        outline=[OutlineEntry(span=span, label="Specification", level=1)],
    )
    outlined = DocEntry(doc_id="d2", filename="ok.pdf", content_hash="h2",
                        status="parsed", structure="outlined", tables="addressable")
    m = CoverageManifest(documents=[flat, outlined], counts={"parsed": 1, "parsed_partial": 1},
                        escalation_rate={"regex": 0.5, "llm": 0.5}, created_at="2026-07-30")

    save_manifest(m, corpus_id="c1", db_path=db)
    loaded = load_manifest(corpus_id="c1", db_path=db)
    assert loaded is not None
    assert loaded.documents[0].structure == "flat" and loaded.documents[0].tables == "unavailable"
    assert "OCR flat text" in loaded.documents[0].reason
    assert loaded.documents[0].outline[0].label == "Specification"
    assert loaded.documents[1].tables == "addressable"
    assert loaded.escalation_rate == {"regex": 0.5, "llm": 0.5}
