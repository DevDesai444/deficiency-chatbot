"""Unit tests for the deficiency category catalog."""
from __future__ import annotations

import pytest

from agents.detection.flaw_types import FLAW_TYPE_DEFINITIONS, format_flaw_catalog

_RULE_WORDS = ("must", "shall", "should", "require")


class TestCatalog:
    def test_catalog_includes_absence_categories(self):
        catalog = format_flaw_catalog()
        assert "- Commitments/Undertakings:" in catalog
        assert "- Coverage Gaps:" in catalog

    @pytest.mark.parametrize("name,desc", list(FLAW_TYPE_DEFINITIONS.items()))
    def test_catalog_descriptions_encode_no_rules(self, name, desc):
        lowered = desc.lower()
        for word in _RULE_WORDS:
            assert word not in lowered, f"{name} description encodes a rule: {word!r}"
        assert not any(ch.isdigit() for ch in desc), f"{name} description encodes a threshold"

    def test_defect_categories_remain_first_four(self):
        """classifier.py's no-JSON fallback slices the first four keys — new entries append."""
        assert list(FLAW_TYPE_DEFINITIONS)[:4] == [
            "Specification/CoA",
            "Method/Validation",
            "Impurities",
            "Stability",
        ]
