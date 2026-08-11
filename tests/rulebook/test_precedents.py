"""Tests for src/rulebook/precedents.py -- D-PREC audited precedent ingestion (Task 4).

Runs against the REAL vendored file `rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm`
(Task 3's committed output, this SAME plan) -- not a synthetic fixture, since the exact counts
below (385 chunks, 83 forward-filled rows) are THIS dataset's, per 02-PRECEDENT-AUDIT.md's
completed audit. `ingest_precedents` defaults to the REAL `rulebook.store` backend, so running
this suite populates the real local precedent chunk store -- exactly Task 4's intent (D-PREC
requires ingestion NOW, per the audit's "Coverage-gap finding (actioned)").

A SECOND vendored workbook (`ANDA-Solid-Oral-Deficiency-RoadMap.xlsm`) was added later. Its
header row spells two columns differently ("Cohort year of the Deficiency", "Catagory of
Deficiency") and it carries two unheaded trailing data columns (a source-PDF filename and a
"Link" cell). The header resolver therefore normalizes header TEXT instead of literal-matching
it, and the tests below pin BOTH real header rows to the SAME 9 canonical fields.
"""
from __future__ import annotations

import sqlite3

import pytest

import rulebook.build as build
from ingest.anchors import open_span
from rulebook.precedents import _resolve_header_fields, get_provenance, ingest_precedents
from rulebook.store import read_chunk_nt

_XLSM_PATH = "rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm"
_SOLID_ORAL_PATH = "rulebook/precedents/ANDA-Solid-Oral-Deficiency-RoadMap.xlsm"
_DB_PATH = "data/defpredict.db"

# The two REAL row-2 header tuples, copied verbatim off the vendored workbooks. They are the
# whole point of the normalizing resolver: same 9 fields, different on-sheet spelling.
_TDDS_HEADER = (
    "ANDA #", "Product Name", "Dosage Form", "CMC Section", "Deficiency Type",
    "Cohort Year of Deficiency", "Category of Deficiency", "Deficiency", "Deficiency Response",
)
_SOLID_ORAL_HEADER = (
    "ANDA #", "Product Name", "Dosage Form", "CMC Section", "Deficiency Type",
    "Cohort year of the Deficiency", "Catagory of Deficiency", "Deficiency ", "Deficiency Response",
)
_CANONICAL_ORDER = [
    "anda_number", "product_name", "dosage_form", "cmc_section", "deficiency_type",
    "cohort_year", "category", "deficiency_text", "deficiency_response",
]


def _all_provenance_rows(source_file: str | None = None) -> list[dict]:
    """Read provenance straight out of the shared store. get_provenance() is per-doc_id; at
    4,426 chunks that would be 4,426 queries, so bulk-read here instead."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    if source_file is None:
        rows = conn.execute("SELECT * FROM precedent_provenance").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM precedent_provenance WHERE source_file = ?", (source_file,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@pytest.fixture(scope="module")
def chunks():
    return ingest_precedents(_XLSM_PATH)


@pytest.fixture(scope="module")
def solid_oral_chunks():
    return ingest_precedents(_SOLID_ORAL_PATH)


def test_ingest_precedents_dedupes_to_385_chunks(chunks):
    assert len(chunks) == 385


def test_duplicated_text_chunk_has_multi_row_provenance(chunks):
    multi_row = [c for c in chunks if len(get_provenance(c.doc_id)) >= 2]
    assert multi_row, "expected at least one deduped chunk with >=2 provenance rows (80 dup groups exist)"


def test_forward_fill_stamps_anda_inferred(chunks):
    all_provenance = [row for c in chunks for row in get_provenance(c.doc_id)]

    inferred_count = sum(1 for row in all_provenance if row["anda_inferred"] == 1)
    assert inferred_count == 83

    assert any(row["anda_inferred"] == 0 for row in all_provenance)
    assert all(row["anda_number"] for row in all_provenance)  # every row is non-empty post-fill


def test_precedent_chunk_reopens_byte_exact(chunks):
    for chunk in chunks:
        nt = read_chunk_nt(chunk.doc_id)
        assert nt is not None
        raw, canonical = open_span(chunk.span, nt, chunk.doc_id)
        assert canonical == nt.canonical  # same grounding contract rule chunks get
        assert raw


# --- header resolution (BLOCKER 1) ----------------------------------------------------------


def test_header_resolver_maps_both_real_workbook_headers():
    """Pure unit, no file I/O. Both REAL header rows must land on the SAME 9 canonical fields,
    and a trailing filename/Link column must resolve to None -- NOT to anda_number. That last
    point is load-bearing: _read_rows builds `{f: v for f, v in zip(fields, raw)}`, so a later
    column mapped to an earlier column's field SILENTLY OVERWRITES it."""
    assert _resolve_header_fields(_TDDS_HEADER) == _CANONICAL_ORDER
    assert _resolve_header_fields(_SOLID_ORAL_HEADER) == _CANONICAL_ORDER

    with_extras = _SOLID_ORAL_HEADER + ("aspi-extn-tab-206392-ka-140929.pdf", "Link")
    resolved = _resolve_header_fields(with_extras)
    assert resolved[:9] == _CANONICAL_ORDER
    assert resolved[9] is None      # a source-PDF filename must NOT be read as an ANDA number
    assert resolved[10] is None
    assert resolved.index("anda_number") == 0


def test_header_resolver_first_column_wins_on_duplicate_field():
    """Defense in depth against the clobber above: if two columns resolve to the same field,
    the FIRST wins and the later one is dropped."""
    resolved = _resolve_header_fields(_TDDS_HEADER + ("ANDA Number",))
    assert resolved[0] == "anda_number"
    assert resolved[9] is None


def test_header_resolver_rejects_a_header_missing_canonical_fields():
    """The silent-NULL failure class becomes a loud, self-describing failure."""
    from rulebook.precedents import _read_rows  # noqa: F401  (module import sanity)

    resolved = _resolve_header_fields(("ANDA #", "Product Name"))
    assert resolved == ["anda_number", "product_name"]  # resolver itself is total; _read_rows raises


def test_read_rows_raises_on_unmapped_canonical_fields(tmp_path):
    import openpyxl

    from rulebook.precedents import _SHEET_NAME, _read_rows

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _SHEET_NAME
    ws.append(["title row"])
    ws.append(["ANDA #", "Product Name", "Deficiency"])
    ws.append(["123", "Widget", "some deficiency"])
    path = tmp_path / "broken.xlsx"
    wb.save(path)

    with pytest.raises(ValueError) as exc:
        _read_rows(path)
    assert "unmapped canonical fields" in str(exc.value)
    assert "cohort_year" in str(exc.value)


# --- second workbook (Solid Oral) -----------------------------------------------------------


def test_solid_oral_dedupes_to_4426_chunks(solid_oral_chunks):
    assert len(solid_oral_chunks) == 4426


def test_solid_oral_forward_fill_count(solid_oral_chunks):
    rows = _all_provenance_rows("ANDA-Solid-Oral-Deficiency-RoadMap.xlsm")
    assert len(rows) == 5096
    inferred_count = sum(1 for row in rows if row["anda_inferred"] == 1)
    assert inferred_count == 50


def test_solid_oral_cohort_year_and_category_are_populated(solid_oral_chunks):
    """THE BLOCKER-1 regression test. The old literal `_HEADER_MAP` silently produced NULL
    cohort_year/category for every Solid Oral row, because that workbook spells the headers
    'Cohort year of the Deficiency' / 'Catagory of Deficiency'."""
    rows = _all_provenance_rows("ANDA-Solid-Oral-Deficiency-RoadMap.xlsm")
    assert rows, "no Solid Oral provenance rows found"

    cohort_populated = sum(1 for r in rows if str(r["cohort_year"] or "").strip())
    category_populated = sum(1 for r in rows if str(r["category"] or "").strip())
    assert cohort_populated > 0
    assert category_populated > 0
    assert cohort_populated == 4636
    assert category_populated == 4921


def test_provenance_rows_carry_source_file(chunks, solid_oral_chunks):
    rows = _all_provenance_rows()
    assert all((r["source_file"] or "").strip() for r in rows)
    assert {r["source_file"] for r in rows} == {
        "ANDA-TDDS-Deficiency-Roadmap.xlsm",
        "ANDA-Solid-Oral-Deficiency-RoadMap.xlsm",
    }


def test_ingest_derives_chunk_filename_from_its_own_workbook(tmp_path, monkeypatch):
    """BLOCKER 2: every chunk's doc_dict filename must be derived from xlsm_path. It used to be
    hardcoded to the TDDS name, so a second workbook's chunks would all claim to come from the
    first one."""
    import openpyxl

    from rulebook import precedents

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = precedents._SHEET_NAME
    ws.append(["title row"])
    ws.append(list(_SOLID_ORAL_HEADER))
    ws.append(["206392", "Widget", "Tablet", "Drug Product", "Specification/CoA",
               "GD-I - CY-4", "IR", "a synthetic deficiency", "2014-09-29"])
    path = tmp_path / "Some-Other-Workbook.xlsx"
    wb.save(path)

    seen_doc_dicts: list[dict] = []
    seen_source_files: list[str] = []

    def _fake_persist(doc_dict, doc_id, citation, store):
        seen_doc_dicts.append(doc_dict)
        return doc_id

    monkeypatch.setattr(precedents, "_persist_chunk", _fake_persist)
    monkeypatch.setattr(
        precedents, "_write_provenance",
        lambda doc_id, group_rows, source_file, db_path=None: seen_source_files.append(source_file),
    )

    precedents.ingest_precedents(path, store=object())

    assert [d["filename"] for d in seen_doc_dicts] == ["Some-Other-Workbook.xlsx"]
    assert seen_source_files == ["Some-Other-Workbook.xlsx"]


# --- multi-workbook vendoring (BLOCKER 3) ---------------------------------------------------


def test_vendor_precedent_preserves_sibling_rows(tmp_path, monkeypatch):
    """Vendoring workbook B must REPLACE only B's own manifest row -- workbook A's precedent
    row and every non-precedent row survive."""
    manifest = tmp_path / "manifest.yaml"
    monkeypatch.setattr(build, "RULEBOOK_DIR", tmp_path)
    monkeypatch.setattr(build, "MANIFEST_PATH", manifest)

    dest_a = str(tmp_path / "precedents" / "A.xlsm")
    dest_b = str(tmp_path / "precedents" / "B.xlsm")
    build._save_manifest_rows([
        {"source": "ecfr", "citation": "21 CFR Part 211", "path": "rulebook/ecfr/title-21/part-211.xml"},
        {"source": "precedent", "citation": "A (precedent spreadsheet)", "path": dest_a},
    ])

    src_b = tmp_path / "src_B.xlsm"
    src_b.write_bytes(b"workbook B bytes")
    build.vendor_precedent(str(src_b), dest_b, "B (precedent spreadsheet)")

    rows = build._load_manifest_rows()
    assert any(r.get("source") == "ecfr" for r in rows)
    precedent_rows = [r for r in rows if r.get("source") == "precedent"]
    assert len(precedent_rows) == 2
    assert {r["path"] for r in precedent_rows} == {dest_a, dest_b}


def test_vendor_precedent_is_offline_first(tmp_path, monkeypatch):
    """D-RB6: `Sample Data/` is gitignored, so a clean checkout must still refresh the manifest
    from the already-vendored bytes when the src is missing."""
    manifest = tmp_path / "manifest.yaml"
    monkeypatch.setattr(build, "RULEBOOK_DIR", tmp_path)
    monkeypatch.setattr(build, "MANIFEST_PATH", manifest)

    dest = tmp_path / "precedents" / "B.xlsm"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"already vendored bytes")

    row = build.vendor_precedent(str(tmp_path / "does-not-exist.xlsm"), str(dest), "B (precedent spreadsheet)")
    assert row["sha256"] == build._sha256(b"already vendored bytes")
    assert dest.read_bytes() == b"already vendored bytes"


def test_precedent_workbooks_list_has_both_entries():
    paths = {dest for _src, dest, _citation in build.PRECEDENT_WORKBOOKS}
    assert paths == {
        "rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm",
        "rulebook/precedents/ANDA-Solid-Oral-Deficiency-RoadMap.xlsm",
    }
