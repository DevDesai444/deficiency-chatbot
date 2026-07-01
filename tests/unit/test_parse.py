import os

import pytest

from parse.pdf import extract_pdf
from parse.section_splitter import classify_document, group_sections, split_document
from schemas.documents import CTDSection

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
        assert doc.page_count == 13
        assert len(doc.pages) == 13
        assert doc.filename == "32s41-Specification.pdf"

    def test_has_toc(self):
        doc = extract_pdf(SPEC_PDF)
        assert len(doc.toc) > 0

    def test_classify_as_s41(self):
        doc = extract_pdf(SPEC_PDF)
        section = classify_document(doc)
        assert section == CTDSection.S_4_1_SPECIFICATION

    def test_tables_found(self):
        doc = extract_pdf(SPEC_PDF)
        total_tables = sum(len(p.tables) for p in doc.pages)
        assert total_tables > 0

    def test_split_produces_sections(self):
        doc = extract_pdf(SPEC_PDF)
        sections = split_document(doc)
        assert len(sections) >= 1
        assert all(s.section_id == CTDSection.S_4_1_SPECIFICATION for s in sections)

    def test_group_sections(self):
        doc = extract_pdf(SPEC_PDF)
        sections = split_document(doc)
        groups = group_sections(sections, max_sections_per_group=3)
        assert len(groups) >= 1
        assert all(len(g.sections) <= 3 for g in groups)


@skip_if_no_samples
class TestValidationPDF:
    def test_extract_pages(self):
        doc = extract_pdf(VALIDATION_PDF)
        assert doc.page_count == 55
        assert len(doc.pages) == 55

    def test_has_rich_toc(self):
        doc = extract_pdf(VALIDATION_PDF)
        assert len(doc.toc) > 5

    def test_classify_as_s43(self):
        doc = extract_pdf(VALIDATION_PDF)
        section = classify_document(doc)
        assert section == CTDSection.S_4_3_VALIDATION

    def test_tables_found(self):
        doc = extract_pdf(VALIDATION_PDF)
        total_tables = sum(len(p.tables) for p in doc.pages)
        assert total_tables >= 10

    def test_split_produces_multiple_sections(self):
        doc = extract_pdf(VALIDATION_PDF)
        sections = split_document(doc)
        assert len(sections) > 3

    def test_sections_have_text(self):
        doc = extract_pdf(VALIDATION_PDF)
        sections = split_document(doc)
        for s in sections:
            assert len(s.text) > 0
