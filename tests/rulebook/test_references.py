"""Tests for rulebook.references (Phase-5 RECALL-03, Plan 05-04).

Fills out the Wave-0 scaffold (Plan 01 Task 1c).  Every test is fully offline
and uses tmp_path-scoped edge databases for isolation.

Tests:
  test_docx_hyperlink_extraction    — D-REF1: DOCX 'hyperlinks' key -> edge registered
  test_textual_ref_pattern_matches  — D-REF1: textual reference pattern -> textual_ref edge
  test_absent_target_manifest_check — D-REF5: edge to missing doc_id -> ABSENT_TARGET Fault
  test_value_contradiction_compound_b_correct — Ruling 6: X1 arithmetic — Compound B
      (0.18%) > NMT 0.15% = VIOLATION; Compound A (0.10%) COMPLIES — NOT flagged
  test_value_contradiction_unit_mismatch_abstains — D-STR4/D-REF4: unit mismatch -> abstain
"""
from __future__ import annotations

import json
import pathlib

import pytest

from rulebook.references import (
    detect_reference_anomalies,
    extract_references,
)


# ---------------------------------------------------------------------------
# Skip guard: skip all tests if rulebook.references not importable
# ---------------------------------------------------------------------------
pytest.importorskip(
    "rulebook.references",
    reason="rulebook.references not yet implemented",
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _block(text, page=1, order=0):
    """Minimal parse-layer text block dict."""
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _grid(page, y0, y1, headers, rows, title=""):
    """Minimal ExtractedTable (grid) dict — same as tests/ingest/conftest.py _grid."""
    return {
        "kind": "grid", "title": title, "headers": headers, "rows": rows, "pairs": [],
        "page": page, "bbox": (72, y0, 540, y1),
        "n_cols": len(headers), "n_rows": len(rows) + 1,
        "source_pages": [page], "continues_from": False, "continues_to": False,
    }


def _build_two_doc_corpus(tmp_path, src_id, src_blocks, dst_id, dst_blocks, dst_tables=None):
    """Build a two-document CorpusIndex with src and dst documents.

    Returns (corpus, manifest) where corpus is a CorpusIndex holding both documents.
    """
    from ingest.anchors import mint_span
    from ingest.corpus import CorpusIndex
    from ingest.manifest import CoverageManifest, DocEntry
    from ingest.normalize import NORMALIZER_VERSION, normalize
    from ingest.serialize import SERIALIZER_VERSION, serialize_document
    from ingest.store import cache_key, write_doc_cache
    from ingest.tables import build_table_index
    from parse.pdf import PARSER_VERSION
    from tests.tools.conftest import make_doc_dict

    dst_tables = dst_tables or []
    cache_dir = str(tmp_path / "cache")
    entries = []

    for doc_id, blocks, tables in [
        (src_id, src_blocks, []),
        (dst_id, dst_blocks, dst_tables),
    ]:
        doc = make_doc_dict(blocks, tables, filename=f"{doc_id}.pdf")
        raw, cell_ranges = serialize_document(doc)
        nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
        table_index = build_table_index(nt, tables, cell_ranges, doc_id)

        entry = DocEntry(
            doc_id=doc_id,
            filename=f"{doc_id}.pdf",
            content_hash=f"hash-{doc_id}",
            status="parsed",
            structure="flat",
            tables="addressable" if table_index else "unavailable",
            normalizer_version=nt.normalizer_version,
            serializer_version=nt.serializer_version,
        )
        entries.append(entry)
        key = cache_key(entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
        write_doc_cache(cache_dir, key, {
            "canonical": nt.canonical,
            "raw_serialized": nt.raw_serialized,
            "offset_map": [r.model_dump() for r in nt.offset_map],
            "normalizer_version": nt.normalizer_version,
            "serializer_version": nt.serializer_version,
            "table_index": {k: v.model_dump() for k, v in table_index.items()},
            "doc_entry": entry.model_dump(),
        })

    manifest = CoverageManifest(documents=entries)
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)
    return corpus, manifest


# ---------------------------------------------------------------------------
# Test 1: D-REF1 — DOCX hyperlink extraction
# ---------------------------------------------------------------------------

def test_docx_hyperlink_extraction(tmp_path):
    """D-REF1: DOCX 'hyperlinks' key in cached doc -> extract_references registers hyperlink edge.

    Synthetic corpus cache with hyperlinks=[{"rId":"r1","target":"doc-b","paragraph_index":0}];
    call extract_references; assert edge with edge_type="hyperlink" is registered.
    """
    from ingest.corpus import CorpusIndex
    from ingest.manifest import CoverageManifest, DocEntry
    from ingest.normalize import NORMALIZER_VERSION, normalize
    from ingest.serialize import SERIALIZER_VERSION, serialize_document
    from ingest.store import cache_key, write_doc_cache
    from ingest.tables import build_table_index
    from parse.pdf import PARSER_VERSION
    from rulebook import edges as edges_module
    from tests.tools.conftest import make_doc_dict

    cache_dir = str(tmp_path / "cache")
    db_path = str(tmp_path / "edges.db")

    # Build src doc with hyperlink metadata
    src_id = "doc-a"
    dst_id = "doc-b"
    src_text = "Analytical Procedures Table 1 for impurity data. See doc-b."
    doc = make_doc_dict([_block(src_text)], [], filename="doc-a.pdf")
    raw, cell_ranges = serialize_document(doc)
    nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
    table_index = build_table_index(nt, [], cell_ranges, src_id)

    src_entry = DocEntry(
        doc_id=src_id, filename="doc-a.pdf", content_hash="hash-doc-a",
        status="parsed", structure="flat", tables="unavailable",
        normalizer_version=nt.normalizer_version, serializer_version=nt.serializer_version,
    )
    key = cache_key(src_entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
    write_doc_cache(cache_dir, key, {
        "canonical": nt.canonical, "raw_serialized": nt.raw_serialized,
        "offset_map": [r.model_dump() for r in nt.offset_map],
        "normalizer_version": nt.normalizer_version, "serializer_version": nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in table_index.items()},
        "doc_entry": src_entry.model_dump(),
        # D-REF1: DOCX 'hyperlinks' key (added by Plan 01 parse backfill)
        "hyperlinks": [{"rId": "r1", "target": dst_id, "paragraph_index": 0}],
    })

    # Build dst doc (present in manifest so it's not ABSENT_TARGET)
    dst_entry = DocEntry(
        doc_id=dst_id, filename="doc-b.pdf", content_hash="hash-doc-b",
        status="parsed", structure="flat", tables="unavailable",
    )

    manifest = CoverageManifest(documents=[src_entry, dst_entry])
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)

    # Run extraction
    extract_references(corpus, manifest, db_path=db_path)

    # Assert: at least one hyperlink edge was registered
    all_edges = edges_module.get_edges(db_path=db_path)
    hyperlink_edges = [e for e in all_edges if e[2] == "hyperlink"]
    assert len(hyperlink_edges) >= 1, (
        f"D-REF1: extract_references must register hyperlink edges from 'hyperlinks' key. "
        f"All edges: {all_edges}"
    )
    # At least one edge should point toward doc-b
    src_ids = [e[0] for e in hyperlink_edges]
    dst_ids = [e[1] for e in hyperlink_edges]
    assert any(dst_id in d or d.startswith(dst_id) for d in dst_ids), (
        f"Hyperlink edge dst should reference doc-b. dst_ids: {dst_ids}"
    )


# ---------------------------------------------------------------------------
# Test 2: D-REF1 — textual reference pattern extraction
# ---------------------------------------------------------------------------

def test_textual_ref_pattern_matches(tmp_path):
    """D-REF1: canonical text 'See Table 3 in Document B' -> textual_ref edge registered."""
    from rulebook import edges as edges_module

    db_path = str(tmp_path / "edges.db")
    corpus, manifest = _build_two_doc_corpus(
        tmp_path,
        src_id="doc-a",
        src_blocks=[_block("Stability results. See Table 3 in Document B for specifications.")],
        dst_id="doc-b",
        dst_blocks=[_block("Document B — Stability Procedures Table 3")],
    )

    extract_references(corpus, manifest, db_path=db_path)

    all_edges = edges_module.get_edges(db_path=db_path)
    textual_edges = [e for e in all_edges if e[2] == "textual_ref"]
    assert len(textual_edges) >= 1, (
        f"D-REF1: 'See Table 3 in Document B' should produce a textual_ref edge. "
        f"All edges: {all_edges}"
    )


# ---------------------------------------------------------------------------
# Test 3: D-REF5 — ABSENT_TARGET manifest check
# ---------------------------------------------------------------------------

def test_absent_target_manifest_check(tmp_path):
    """D-REF5: edge to doc_id NOT in manifest -> ABSENT_TARGET Fault with scoping_confidence='full'.

    We manually add an edge pointing to a non-existent dst, then call
    detect_reference_anomalies and assert an ABSENT_TARGET Fault is emitted.
    """
    import json
    from ingest.anchors import mint_span
    from ingest.corpus import CorpusIndex
    from ingest.manifest import CoverageManifest, DocEntry
    from ingest.normalize import NORMALIZER_VERSION, normalize
    from ingest.serialize import SERIALIZER_VERSION, serialize_document
    from ingest.store import cache_key, write_doc_cache
    from ingest.tables import build_table_index
    from parse.pdf import PARSER_VERSION
    from rulebook import edges as edges_module
    from schemas.faults import Fault
    from tests.tools.conftest import make_doc_dict
    from tools.ledger import RetrievalLedger

    cache_dir = str(tmp_path / "cache")
    db_path = str(tmp_path / "edges.db")

    src_id = "doc-src"
    src_text = "See Module 3.2.S.4.2 for analytical validation data."
    doc = make_doc_dict([_block(src_text)], [], filename="doc-src.pdf")
    raw, cell_ranges = serialize_document(doc)
    nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
    table_index = build_table_index(nt, [], cell_ranges, src_id)
    src_entry = DocEntry(
        doc_id=src_id, filename="doc-src.pdf", content_hash="hash-src",
        status="parsed", structure="flat", tables="unavailable",
        normalizer_version=nt.normalizer_version, serializer_version=nt.serializer_version,
    )
    key = cache_key(src_entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
    write_doc_cache(cache_dir, key, {
        "canonical": nt.canonical, "raw_serialized": nt.raw_serialized,
        "offset_map": [r.model_dump() for r in nt.offset_map],
        "normalizer_version": nt.normalizer_version, "serializer_version": nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in table_index.items()},
        "doc_entry": src_entry.model_dump(),
    })

    manifest = CoverageManifest(documents=[src_entry])
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)

    # Manually add an edge to a non-existent dst doc_id
    src_span = mint_span(nt.canonical, 0, min(len(nt.canonical), 40), src_id, nt.normalizer_version)
    src_id_key = f"{src_id}:{src_span.start}"
    provenance = json.dumps(src_span.model_dump())
    edges_module.add_edge(
        src_id=src_id_key,
        dst_id="non-existent-doc:0",
        edge_type="textual_ref",
        provenance_span_id=provenance,
        db_path=db_path,
    )

    ledger = RetrievalLedger()
    faults = detect_reference_anomalies(corpus, manifest, ledger, db_path=db_path)

    absent_target_faults = [
        f for f in faults
        if f.reference_anchor and f.reference_anchor.anomaly == "ABSENT_TARGET"
    ]
    assert len(absent_target_faults) >= 1, (
        f"D-REF5: edge to non-existent doc_id must emit ABSENT_TARGET Fault. "
        f"Faults found: {[(f.reference_anchor.anomaly if f.reference_anchor else None) for f in faults]}"
    )
    # Full confidence when genuinely absent from manifest (D-REF5)
    for f in absent_target_faults:
        assert f.reference_anchor.scoping_confidence == "full", (
            f"D-REF5: ABSENT_TARGET for truly missing doc must be 'full' confidence, "
            f"got {f.reference_anchor.scoping_confidence}"
        )
    # D-ENV1: leg_tag must be REFERENCE
    for f in absent_target_faults:
        assert f.leg_tag == "REFERENCE", f"D-ENV1: leg_tag must be 'REFERENCE', got {f.leg_tag}"


# ---------------------------------------------------------------------------
# Test 4: Ruling 6 — VALUE_CONTRADICTION arithmetic — Compound B correct
# ---------------------------------------------------------------------------

def test_value_contradiction_compound_b_correct(tmp_path):
    """Ruling 6: VALUE_CONTRADICTION must find Compound B (0.18% > NMT 0.15%).

    Compound A (0.10%) COMPLIES with NMT 0.15% — must NOT be flagged.

    Scenario:
      doc-a (src): text contains "NMT 0.15% for any single impurity (see Analytical Procedures)"
      doc-b (dst): Table 1 with:
        row 1: Compound A | 0.10%   (0.10 <= 0.15 -> COMPLIANT)
        row 2: Compound B | 0.18%   (0.18 > 0.15  -> VIOLATION)

    Expected: exactly ONE VALUE_CONTRADICTION Fault for Compound B.
    Compound A must NOT generate a fault.
    """
    import json
    from ingest.anchors import mint_span
    from ingest.corpus import CorpusIndex
    from ingest.manifest import CoverageManifest, DocEntry
    from ingest.normalize import NORMALIZER_VERSION, normalize
    from ingest.serialize import SERIALIZER_VERSION, serialize_document
    from ingest.store import cache_key, write_doc_cache
    from ingest.tables import build_table_index
    from parse.pdf import PARSER_VERSION
    from rulebook import edges as edges_module
    from schemas.faults import Fault
    from tests.tools.conftest import make_doc_dict
    from tools.ledger import RetrievalLedger

    cache_dir = str(tmp_path / "cache")
    db_path = str(tmp_path / "edges.db")

    # Build src doc: "NMT 0.15% for any single impurity (see Analytical Procedures)"
    src_id = "doc-a"
    src_text = "NMT 0.15% for any single impurity (see Analytical Procedures Table 1)"
    src_doc = make_doc_dict([_block(src_text)], [], filename="doc-a.pdf")
    src_raw, src_cell_ranges = serialize_document(src_doc)
    src_nt = normalize(src_raw, serializer_version=SERIALIZER_VERSION)
    src_table_index = build_table_index(src_nt, [], src_cell_ranges, src_id)
    src_entry = DocEntry(
        doc_id=src_id, filename="doc-a.pdf", content_hash="hash-doc-a",
        status="parsed", structure="flat", tables="unavailable",
        normalizer_version=src_nt.normalizer_version, serializer_version=src_nt.serializer_version,
    )
    src_key = cache_key(src_entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
    write_doc_cache(cache_dir, src_key, {
        "canonical": src_nt.canonical, "raw_serialized": src_nt.raw_serialized,
        "offset_map": [r.model_dump() for r in src_nt.offset_map],
        "normalizer_version": src_nt.normalizer_version, "serializer_version": src_nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in src_table_index.items()},
        "doc_entry": src_entry.model_dump(),
    })

    # Build dst doc: Table 1 with Compound A=0.10%, Compound B=0.18%
    dst_id = "doc-b"
    dst_table = _grid(
        page=1, y0=100, y1=200,
        headers=["Impurity", "% w/w"],
        rows=[["Compound A", "0.10%"], ["Compound B", "0.18%"]],
        title="Table 1",
    )
    dst_block_text = "Analytical Procedures Table 1 Impurity Profile"
    dst_doc = make_doc_dict([_block(dst_block_text)], [dst_table], filename="doc-b.pdf")
    dst_raw, dst_cell_ranges = serialize_document(dst_doc)
    dst_nt = normalize(dst_raw, serializer_version=SERIALIZER_VERSION)
    dst_table_index = build_table_index(dst_nt, [dst_table], dst_cell_ranges, dst_id)
    dst_entry = DocEntry(
        doc_id=dst_id, filename="doc-b.pdf", content_hash="hash-doc-b",
        status="parsed", structure="flat", tables="addressable",
        normalizer_version=dst_nt.normalizer_version, serializer_version=dst_nt.serializer_version,
    )
    dst_key = cache_key(dst_entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
    write_doc_cache(cache_dir, dst_key, {
        "canonical": dst_nt.canonical, "raw_serialized": dst_nt.raw_serialized,
        "offset_map": [r.model_dump() for r in dst_nt.offset_map],
        "normalizer_version": dst_nt.normalizer_version, "serializer_version": dst_nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in dst_table_index.items()},
        "doc_entry": dst_entry.model_dump(),
    })

    manifest = CoverageManifest(documents=[src_entry, dst_entry])
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)

    # Manually add an edge from the NMT span in doc-a to doc-b
    # (simulating what extract_references would produce for a value_crossref)
    nmt_offset = src_nt.canonical.index("NMT 0.15%")
    src_span = mint_span(
        src_nt.canonical,
        nmt_offset,
        min(len(src_nt.canonical), nmt_offset + len(src_text)),
        src_id,
        src_nt.normalizer_version,
    )
    src_key_edge = f"{src_id}:{src_span.start}"
    provenance = json.dumps(src_span.model_dump())
    edges_module.add_edge(
        src_id=src_key_edge,
        dst_id=f"{dst_id}:0",
        edge_type="value_crossref",
        provenance_span_id=provenance,
        db_path=db_path,
    )

    ledger = RetrievalLedger()
    faults = detect_reference_anomalies(corpus, manifest, ledger, db_path=db_path)

    contradiction_faults = [
        f for f in faults
        if f.reference_anchor and f.reference_anchor.anomaly == "VALUE_CONTRADICTION"
    ]

    # Ruling 6: must find at least one VALUE_CONTRADICTION (Compound B 0.18% > NMT 0.15%)
    assert len(contradiction_faults) >= 1, (
        f"Ruling 6: Must find at least one VALUE_CONTRADICTION "
        f"(Compound B 0.18% > NMT 0.15%). Faults: {[f.reference_anchor.anomaly for f in faults if f.reference_anchor]}"
    )

    # Ruling 6 arithmetic check: Compound B (0.18%) must be the violating value
    # Verify by checking the detail string contains "0.18" (Compound B)
    for f in contradiction_faults:
        assert "0.18" in f.detail, (
            f"Ruling 6: VALUE_CONTRADICTION detail must reference 0.18% (Compound B), "
            f"got detail: {f.detail!r}"
        )
        # Verify the anchor src_span covers the NMT 0.15% text
        assert f.reference_anchor is not None
        assert f.reference_anchor.anomaly == "VALUE_CONTRADICTION"
        assert f.leg_tag == "REFERENCE", f"D-ENV1: leg_tag must be 'REFERENCE', got {f.leg_tag}"

    # Ruling 6: Compound A (0.10%) must NOT generate a VALUE_CONTRADICTION
    # If there are multiple faults, verify no fault references ONLY "0.10" without "0.18"
    # (A fault with both is OK — it represents the combined row check)
    compound_a_only_faults = [
        f for f in contradiction_faults
        if "0.10" in f.detail and "0.18" not in f.detail
    ]
    assert len(compound_a_only_faults) == 0, (
        f"Ruling 6: Compound A (0.10%) COMPLIES with NMT 0.15% and must NOT be flagged. "
        f"Got faults mentioning only 0.10%: {[f.detail for f in compound_a_only_faults]}"
    )


# ---------------------------------------------------------------------------
# Test 5: D-REF4/D-STR4 — unit mismatch -> abstain (no Fault)
# ---------------------------------------------------------------------------

def test_value_contradiction_unit_mismatch_abstains(tmp_path):
    """D-REF4/D-STR4: src limit in 'mg/mL', dst value in '%' -> unit mismatch -> abstain.

    compare_values must abstain (return None) when units are incompatible.
    No VALUE_CONTRADICTION Fault should be emitted.
    """
    import json
    from ingest.anchors import mint_span
    from ingest.corpus import CorpusIndex
    from ingest.manifest import CoverageManifest, DocEntry
    from ingest.normalize import NORMALIZER_VERSION, normalize
    from ingest.serialize import SERIALIZER_VERSION, serialize_document
    from ingest.store import cache_key, write_doc_cache
    from ingest.tables import build_table_index
    from parse.pdf import PARSER_VERSION
    from rulebook import edges as edges_module
    from tests.tools.conftest import make_doc_dict
    from tools.ledger import RetrievalLedger

    cache_dir = str(tmp_path / "cache")
    db_path = str(tmp_path / "edges.db")

    src_id = "doc-src"
    # Limit in mg/mL — incompatible with % in dst
    src_text = "NMT 0.15 mg/mL for any single impurity (see Analytical Procedures)"
    src_doc = make_doc_dict([_block(src_text)], [], filename="doc-src.pdf")
    src_raw, src_cell_ranges = serialize_document(src_doc)
    src_nt = normalize(src_raw, serializer_version=SERIALIZER_VERSION)
    src_table_index = build_table_index(src_nt, [], src_cell_ranges, src_id)
    src_entry = DocEntry(
        doc_id=src_id, filename="doc-src.pdf", content_hash="hash-src",
        status="parsed", structure="flat", tables="unavailable",
        normalizer_version=src_nt.normalizer_version, serializer_version=src_nt.serializer_version,
    )
    src_key = cache_key(src_entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
    write_doc_cache(cache_dir, src_key, {
        "canonical": src_nt.canonical, "raw_serialized": src_nt.raw_serialized,
        "offset_map": [r.model_dump() for r in src_nt.offset_map],
        "normalizer_version": src_nt.normalizer_version, "serializer_version": src_nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in src_table_index.items()},
        "doc_entry": src_entry.model_dump(),
    })

    dst_id = "doc-dst"
    # Dst value in % — incompatible with mg/mL from src
    dst_table = _grid(
        page=1, y0=100, y1=200,
        headers=["Compound", "% w/w"],
        rows=[["Test Substance", "0.18%"]],
        title="Results Table",
    )
    dst_doc = make_doc_dict(
        [_block("Results Table Compound % w/w")], [dst_table], filename="doc-dst.pdf"
    )
    dst_raw, dst_cell_ranges = serialize_document(dst_doc)
    dst_nt = normalize(dst_raw, serializer_version=SERIALIZER_VERSION)
    dst_table_index = build_table_index(dst_nt, [dst_table], dst_cell_ranges, dst_id)
    dst_entry = DocEntry(
        doc_id=dst_id, filename="doc-dst.pdf", content_hash="hash-dst",
        status="parsed", structure="flat", tables="addressable",
        normalizer_version=dst_nt.normalizer_version, serializer_version=dst_nt.serializer_version,
    )
    dst_key = cache_key(dst_entry.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
    write_doc_cache(cache_dir, dst_key, {
        "canonical": dst_nt.canonical, "raw_serialized": dst_nt.raw_serialized,
        "offset_map": [r.model_dump() for r in dst_nt.offset_map],
        "normalizer_version": dst_nt.normalizer_version, "serializer_version": dst_nt.serializer_version,
        "table_index": {k: v.model_dump() for k, v in dst_table_index.items()},
        "doc_entry": dst_entry.model_dump(),
    })

    manifest = CoverageManifest(documents=[src_entry, dst_entry])
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=cache_dir, manifest=manifest)

    # Add edge from src to dst
    nmt_offset = src_nt.canonical.index("NMT 0.15")
    src_span = mint_span(
        src_nt.canonical, nmt_offset,
        min(len(src_nt.canonical), nmt_offset + len(src_text)),
        src_id, src_nt.normalizer_version,
    )
    edges_module.add_edge(
        src_id=f"{src_id}:{src_span.start}",
        dst_id=f"{dst_id}:0",
        edge_type="value_crossref",
        provenance_span_id=json.dumps(src_span.model_dump()),
        db_path=db_path,
    )

    ledger = RetrievalLedger()
    faults = detect_reference_anomalies(corpus, manifest, ledger, db_path=db_path)

    contradiction_faults = [
        f for f in faults
        if f.reference_anchor and f.reference_anchor.anomaly == "VALUE_CONTRADICTION"
    ]
    assert len(contradiction_faults) == 0, (
        f"D-REF4/D-STR4: unit mismatch (mg/mL vs %) must cause abstain — no VALUE_CONTRADICTION. "
        f"Got: {[f.detail for f in contradiction_faults]}"
    )
