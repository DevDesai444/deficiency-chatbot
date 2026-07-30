"""Tests for the data-driven CTD-family registry (Plan 05, Task 1 / D-05, D-06)."""
from __future__ import annotations

from ingest.registry import (
    as_ctd_section,
    families_catalog_text,
    family_ids,
    load_families,
    load_lexicon,
)
from schemas.documents import CTDSection

# The four validation sections checklists.py keys on -- ids the registry MUST cover.
_VALIDATION_SECTION_VALUES = {
    CTDSection.S_4_3_VALIDATION.value,
    CTDSection.P_4_3_VALIDATION.value,
    CTDSection.S_4_2_ANALYTICAL_PROCEDURES.value,
    CTDSection.P_4_2_ANALYTICAL_PROCEDURES.value,
}


def test_every_family_id_is_a_valid_ctdsection_value():
    valid = {s.value for s in CTDSection}
    assert family_ids() <= valid, family_ids() - valid


def test_family_ids_superset_of_validation_sections():
    assert _VALIDATION_SECTION_VALUES <= family_ids()


def test_lexicon_keys_subset_of_families():
    assert set(load_lexicon().keys()) <= family_ids()


def test_each_entry_has_required_keys():
    for entry in load_families():
        assert {"id", "label", "applicability_trigger"} <= set(entry), entry


def test_unknown_is_not_a_family():
    assert CTDSection.UNKNOWN.value not in family_ids()


def test_as_ctd_section_roundtrips_and_defaults():
    assert as_ctd_section("3.2.S.4.1") is CTDSection.S_4_1_SPECIFICATION
    assert as_ctd_section("not-a-family") is CTDSection.UNKNOWN


def test_catalog_text_renders_ids_and_triggers():
    txt = families_catalog_text()
    assert "3.2.S.4.1" in txt
    assert "Drug Substance Specification" in txt
