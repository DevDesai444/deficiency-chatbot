"""Tests for rulebook/manifest.yaml -- RULES-04 metadata completeness (Task 2 baseline; Task 3
extends this file to assert the full 13-row manifest once ICH/FDA/precedent vendoring lands).

Offline, fixture-based: reads the COMMITTED rulebook/manifest.yaml from disk -- does NOT
re-fetch network. This is deliberately not tmp_path-isolated like tests/rulebook/test_store.py:
RULES-04 is a property of the ACTUAL vendored artifact this plan commits, not a synthetic
fixture -- the manifest under test IS the one `git status` shows as tracked/staged.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_MANIFEST_PATH = Path("rulebook/manifest.yaml")
_REQUIRED_FIELDS = ("source", "citation", "version", "license", "url")


def _load_manifest_rows() -> list[dict]:
    return yaml.safe_load(_MANIFEST_PATH.read_text()) or []


def test_every_chunk_has_required_metadata_and_no_placeholder_date():
    rows = _load_manifest_rows()
    assert rows, "rulebook/manifest.yaml is empty -- expected at least the 7 eCFR part rows"

    for row in rows:
        if "error" in row:
            # a recorded fetch/parse failure (D-16 never-abort discipline) -- exempt from the
            # field checks below; its presence IS the required record for that source.
            assert row["error"]
            continue
        for field in _REQUIRED_FIELDS:
            assert row.get(field), f"row {row!r} missing required field {field!r}"

    raw_text = _MANIFEST_PATH.read_text()
    assert "_SUBSTITUTE_DATE_" not in raw_text
