"""Section splitting from structured blocks: TOC anchoring, data-row rejection, stitching."""
import os
import re

import pytest

from parse.section_splitter import (
    _geometry_headings,
    _stitch_cross_page_tables,
    classify_document,
    split_document,
)
from schemas.documents import CTDSection, ExtractedTable, LayoutBlock

SAMPLE_DIR = os.environ.get("SAMPLE_DATA_DIR", "Sample Data")
VALIDATION_PDF = os.path.join(SAMPLE_DIR, "32s43-validation-related-compounds-method.pdf")
skip_if_no_samples = pytest.mark.skipif(
    not os.path.exists(VALIDATION_PDF), reason="Sample PDFs not available"
)


@pytest.fixture
def offline(monkeypatch):
    """Force the no-Databricks OCR fallback so the test is fast and deterministic."""
    from config import Settings
    import parse.ocr as ocrmod

    monkeypatch.setattr(ocrmod, "get_settings", lambda: Settings(databricks_host="", databricks_token=""))


@skip_if_no_samples
def test_split_matches_toc_not_data_rows(offline):
    from parse.pdf import extract_pdf

    doc = extract_pdf(VALIDATION_PDF)
    assert classify_document(doc) == CTDSection.S_4_3_VALIDATION

    sections = split_document(doc)
    # the flat-text splitter produced 95 sections; structure should give ~20
    assert 12 <= len(sections) <= 30
    headings = [s.heading for s in sections]
    assert any("Linearity" in h for h in headings)
    assert any("Conclusions" in h for h in headings)

    # no data-row false headings: every heading number is a real (small) section number
    for h in headings:
        match = re.match(r"^(\d+(?:\.\d+)*)\s", h)
        if match:
            assert all(int(p) <= 50 for p in match.group(1).split("."))


def test_geometry_headings_reject_data_rows():
    blocks = [
        LayoutBlock(text="1.4.2 Linearity", page=1, reading_order=0),
        LayoutBlock(text="6920.93 Intercept", page=1, reading_order=1),   # data, not a heading
        LayoutBlock(text="281.39 CAS Number", page=1, reading_order=2),   # data, not a heading
        LayoutBlock(text="1.5 Conclusions", page=1, reading_order=3),
    ]
    nums = [num for _, num, _ in _geometry_headings(blocks)]
    assert nums == ["1.4.2", "1.5"]


def test_cross_page_grid_is_stitched():
    a = ExtractedTable(
        kind="grid", headers=["Lvl", "Conc", "Area"],
        rows=[["4", "0.78", "5118"], ["5", "0.97", "6645"]],
        page=5, bbox=(72, 600, 540, 740), n_cols=3, n_rows=3, source_pages=[5],
    )
    b = ExtractedTable(
        kind="grid", headers=["6", "1.17", "7594"], rows=[["7", "1.46", "9720"]],
        page=6, bbox=(72, 80, 540, 160), n_cols=3, n_rows=2, source_pages=[6],
    )
    out = _stitch_cross_page_tables([a, b], {5: 792.0, 6: 792.0})
    assert len(out) == 1
    assert out[0].continues_to is True
    assert out[0].source_pages == [5, 6]
    assert ["6", "1.17", "7594"] in out[0].rows   # B's first row was data, kept
    assert ["7", "1.46", "9720"] in out[0].rows


def test_unrelated_tables_not_stitched():
    a = ExtractedTable(kind="grid", headers=["A", "B"], rows=[["1", "2"]],
                       page=5, bbox=(72, 600, 300, 740), n_cols=2, n_rows=2, source_pages=[5])
    b = ExtractedTable(kind="grid", headers=["X", "Y", "Z"], rows=[["1", "2", "3"]],
                       page=6, bbox=(72, 80, 540, 160), n_cols=3, n_rows=2, source_pages=[6])
    out = _stitch_cross_page_tables([a, b], {5: 792.0, 6: 792.0})
    assert len(out) == 2   # different column counts -> left separate


def test_no_overstitch_when_middle_fragment_does_not_reach_bottom():
    # a reaches the bottom of p5, b continues but ENDS mid-page on p6, c is on p7.
    # c must not stitch onto b (b didn't reach the bottom) -- the 3rd-fragment check
    # must look at b's geometry, not a's.
    def frag(page, y0, y1, first):
        return ExtractedTable(kind="grid", headers=first, rows=[["r", "s", "t"]],
                              page=page, bbox=(72, y0, 540, y1), n_cols=3, n_rows=2, source_pages=[page])
    a = frag(5, 600, 740, ["H1", "H2", "H3"])
    b = frag(6, 80, 300, ["6", "x", "y"])   # continues a, but ends at y=300 (not the bottom)
    c = frag(7, 80, 160, ["7", "x", "y"])
    out = _stitch_cross_page_tables([a, b, c], {5: 792.0, 6: 792.0, 7: 792.0})
    assert len(out) == 2
    assert out[0].source_pages == [5, 6]     # a+b stitched, c left separate


def test_geometry_headings_accept_trailing_dot():
    blocks = [
        LayoutBlock(text="1. Purpose", page=1, reading_order=0),
        LayoutBlock(text="2. Scope", page=1, reading_order=1),
        LayoutBlock(text="3.1. Procedure Detail", page=1, reading_order=2),
    ]
    nums = [num for _, num, _ in _geometry_headings(blocks)]
    assert nums == ["1", "2", "3.1"]


def test_tables_only_document_surfaces_them():
    from parse.pdf import PageContent, PDFDocument

    table = ExtractedTable(kind="grid", headers=["A", "B"], rows=[["1", "2"]],
                           page=2, bbox=(0, 0, 10, 10), n_cols=2, n_rows=2, source_pages=[2])
    doc = PDFDocument(
        filename="x.pdf", page_count=2, toc=[],
        pages=[
            PageContent(page_number=1, text=""),
            PageContent(page_number=2, text="", tables=[table]),
        ],
    )
    sections = split_document(doc)
    assert len(sections) == 1
    assert sections[0].tables and sections[0].tables[0].headers == ["A", "B"]


def test_render_section_renders_key_value_pairs():
    from agents.extraction.agent import _render_section
    from schemas.documents import ParsedSection, TablePair

    section = ParsedSection(
        heading="Appendix 2",
        text="Certificate",
        tables=[ExtractedTable(kind="key_value", title="CoA",
                               pairs=[TablePair(label="Purity", value="98.4%")])],
    )
    rendered = "\n".join(_render_section(section, "Appendix 2"))
    assert "Purity: 98.4%" in rendered
