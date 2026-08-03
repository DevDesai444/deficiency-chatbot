import os

import fitz
import pytest

from parse.pdf import extract_pdf
from parse.section_splitter import group_sections, split_document

SAMPLE_DIR = os.environ.get(
    "SAMPLE_DATA_DIR",
    "/Users/DEVDESAI1/Desktop/University_at_Buffalo/Projects/deficiency-chatbot/Sample Data",
)

SPEC_PDF = os.path.join(SAMPLE_DIR, "32s41-Specification.pdf")
VALIDATION_PDF = os.path.join(SAMPLE_DIR, "32s43-validation-related-compounds-method.pdf")

skip_if_no_samples = pytest.mark.skipif(
    not os.path.exists(SPEC_PDF), reason="Sample PDFs not available"
)


@skip_if_no_samples
class TestSpecPDF:
    def test_extract_pages(self):
        doc = extract_pdf(SPEC_PDF)
        assert doc["page_count"] == 13
        assert len(doc["pages"]) == 13
        assert doc["filename"] == "32s41-Specification.pdf"

    def test_extract_returns_json(self):
        doc = extract_pdf(SPEC_PDF)
        assert set(doc.keys()) == {"filename", "page_count", "toc", "pages"}
        page = doc["pages"][0]
        assert {"blocks", "tables", "figures", "source", "is_scanned"} <= set(page.keys())

    def test_has_toc(self):
        doc = extract_pdf(SPEC_PDF)
        assert len(doc["toc"]) > 0

    def test_tables_found(self):
        doc = extract_pdf(SPEC_PDF)
        assert sum(len(p["tables"]) for p in doc["pages"]) > 0

    def test_split_produces_section_dicts(self):
        sections = split_document(extract_pdf(SPEC_PDF))
        assert len(sections) >= 1
        assert all(isinstance(s, dict) and "heading" in s for s in sections)

    def test_group_sections(self):
        sections = split_document(extract_pdf(SPEC_PDF))
        groups = group_sections(sections, max_sections_per_group=3)
        assert len(groups) >= 1
        assert all(len(g["sections"]) <= 3 for g in groups)


@skip_if_no_samples
class TestValidationPDF:
    def test_extract_pages(self):
        doc = extract_pdf(VALIDATION_PDF)
        assert doc["page_count"] == 55
        assert len(doc["pages"]) == 55

    def test_has_rich_toc(self):
        doc = extract_pdf(VALIDATION_PDF)
        assert len(doc["toc"]) > 5

    def test_tables_found(self):
        doc = extract_pdf(VALIDATION_PDF)
        assert sum(len(p["tables"]) for p in doc["pages"]) >= 10

    def test_split_produces_multiple_sections(self):
        sections = split_document(extract_pdf(VALIDATION_PDF))
        assert len(sections) > 3

    def test_sections_have_text(self):
        sections = split_document(extract_pdf(VALIDATION_PDF))
        for s in sections:
            assert len(s["text"]) > 0


def test_flat_text_ocr_tagged_and_preserved():
    """The flat-text OCR compat branch preserves the text AND tags source='rapidocr-flat-text'
    (D-17 regression insurance); a boxed payload yields source='rapidocr'. No network/samples."""
    import fitz

    from parse.ocr import _reconstruct_prediction

    doc = fitz.open()
    page = doc.new_page()
    # flat-text payload: a plain string NOT starting with "[" -> flat-text compat branch
    res = _reconstruct_prediction("Total impurities 0.14%", page)
    assert isinstance(res, tuple) and len(res) == 5
    assert res[0] == "Total impurities 0.14%"      # text PRESERVED (dropping it would fail here)
    assert res[4] == "rapidocr-flat-text"          # degradation is an explicit FACT
    # boxed payload -> normal source
    boxed = [{"text": "X", "x0": 0, "y0": 0, "x1": 10, "y1": 10, "score": 1.0}]
    res2 = _reconstruct_prediction(boxed, page)
    assert res2[4] == "rapidocr"
    doc.close()


def test_fallback_blocks_from_embedded_text_layer(tmp_path, monkeypatch):
    """A scanned-looking PDF with embedded text must keep blocks when OCR is unavailable."""
    import parse.pdf as pdf_parser

    token = "MVR1381-FALLBACK-BLOCK-TOKEN"
    pdf_path = tmp_path / "scanned_with_text_layer.pdf"

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 96), f"Validation Method {token}")

    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 4, 4), False)
    pix.clear_with(242)
    page.insert_image(page.rect, stream=pix.tobytes("png"))

    doc.save(pdf_path)
    doc.close()

    monkeypatch.setattr(pdf_parser, "ocr_page", lambda page: None)

    parsed = extract_pdf(pdf_path)
    page_doc = parsed["pages"][0]

    assert page_doc["source"] == "rapidocr-fallback"
    assert page_doc["is_scanned"] is True
    assert len(page_doc["blocks"]) > 0
    assert any(token in block["text"] for block in page_doc["blocks"])
