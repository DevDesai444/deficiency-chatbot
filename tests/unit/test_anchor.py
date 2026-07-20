"""Unit tests for deterministic span anchoring."""
from __future__ import annotations

import pytest

from agents.extraction.anchor import (
    filter_anchored,
    is_anchored,
    normalize,
    section_sources,
)
from schemas.documents import (
    ExtractionFindingOut,
    KeyValue,
    SectionExtract,
)


@pytest.fixture
def section():
    return {
        "heading": "Extractables and Leachables",
        "text": "The AET was calculated as 22.727 ug/g for the drug product.",
        "tables": [{
            "kind": "grid", "title": "Table 16",
            "headers": ["Compound", "Result"], "rows": [["2-Butanone", "8.72 ug/g"]],
            "pairs": [], "page": 16,
        }],
        "figures": [], "page_start": 14, "page_end": 17,
    }


class TestNormalize:
    def test_collapses_whitespace(self):
        assert normalize("a  \n b") == "a b"

    def test_nfkc_and_smart_quotes(self):
        assert normalize("“Ｔest’s”") == normalize('"test\'s"')

    def test_empty_is_empty(self):
        assert normalize("") == ""


class TestIsAnchored:
    def test_exact_substring(self, section):
        assert is_anchored("22.727", section_sources(section))

    def test_whitespace_differs(self, section):
        assert is_anchored("22.727  ug/g", section_sources(section))

    def test_rejects_fabrication(self, section):
        assert not is_anchored("99.999 ug/g", section_sources(section))

    def test_empty_span_false(self, section):
        assert not is_anchored("", section_sources(section))

    def test_table_cell_anchors(self, section):
        assert is_anchored("2-Butanone", section_sources(section))

    def test_table_title_anchors(self, section):
        assert is_anchored("Table 16", section_sources(section))

    @pytest.mark.parametrize(
        "corrupted",
        [
            "The AET was calculated as 32.727 ug/g for the drug product.",
            "The AET was calculated as 99.727 ug/g for the drug product.",
            "The AET was calculated as 22.727 mg/g for the drug product.",
            "The AET was calculated as 2.727 ug/g for the drug product.",
        ],
    )
    def test_long_span_with_altered_digits_rejected(self, section, corrupted):
        """Ratio dilution lets a long quote carry a wrong digit past the threshold.

        These score above _NEAR_MATCH_RATIO against the source; only the digit guard
        rejects them. A wrong digit is a different value, not rendering drift.
        """
        assert not is_anchored(corrupted, section_sources(section))

    def test_long_span_exact_still_anchors(self, section):
        assert is_anchored(
            "The AET was calculated as 22.727 ug/g for the drug product.",
            section_sources(section),
        )

    def test_value_split_across_cells_anchors_via_joined_row(self):
        s = {
            "text": "",
            "tables": [{"kind": "grid", "title": "", "headers": ["Analyte", "Value"],
                        "rows": [["22.727", "ug/g"]], "pairs": []}],
        }
        assert is_anchored("22.727 | ug/g", section_sources(s))


class TestFilterAnchored:
    def test_none_extract_yields_empty(self, section):
        assert filter_anchored(None, section) == ({}, [], 0)

    def test_key_value_survives_anchoring(self, section):
        extract = SectionExtract(
            section_index=0,
            summary="AET derivation",
            key_values=[KeyValue(label="AET", value="22.727 ug/g")],
        )
        kept_values, _, dropped = filter_anchored(extract, section)
        assert kept_values == {"AET": "22.727 ug/g"}
        assert dropped == 0

    def test_fabricated_key_value_dropped(self, section):
        extract = SectionExtract(
            section_index=0,
            summary="AET derivation",
            key_values=[KeyValue(label="AET", value="99.999 ug/g")],
        )
        kept_values, _, dropped = filter_anchored(extract, section)
        assert kept_values == {}
        assert dropped == 1

    def test_counts_drops_across_both_collections(self, section):
        extract = SectionExtract(
            section_index=0,
            summary="Mixed",
            key_values=[
                KeyValue(label="AET", value="22.727 ug/g"),
                KeyValue(label="Bogus", value="99.999 ug/g"),
            ],
            findings=[
                ExtractionFindingOut(finding="real", evidence="2-Butanone"),
                ExtractionFindingOut(finding="invented", evidence="Toluene detected"),
            ],
        )
        kept_values, kept_findings, dropped = filter_anchored(extract, section)
        assert list(kept_values) == ["AET"]
        assert [f.finding for f in kept_findings] == ["real"]
        assert dropped == 2

    def test_finding_without_evidence_kept(self, section):
        extract = SectionExtract(
            section_index=0,
            summary="Observation",
            findings=[ExtractionFindingOut(finding="Section omits a PDE", evidence="")],
        )
        _, kept_findings, dropped = filter_anchored(extract, section)
        assert len(kept_findings) == 1
        assert dropped == 0

    def test_conflicting_values_both_survive(self, section):
        """Anchoring verifies occurrence, never reconciles a disagreement."""
        extract = SectionExtract(
            section_index=0,
            summary="AET vs reported",
            key_values=[
                KeyValue(label="AET calculated", value="22.727"),
                KeyValue(label="AET applied", value="8.72"),
            ],
        )
        kept_values, _, dropped = filter_anchored(extract, section)
        assert kept_values == {"AET calculated": "22.727", "AET applied": "8.72"}
        assert dropped == 0

    def test_empty_extract_is_subtractive_noop(self, section):
        kept_values, kept_findings, dropped = filter_anchored(
            SectionExtract(section_index=0, summary="Nothing salient"), section
        )
        assert (kept_values, kept_findings, dropped) == ({}, [], 0)
