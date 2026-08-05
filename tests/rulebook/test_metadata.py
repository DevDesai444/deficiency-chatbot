"""Tests for rulebook/manifest.yaml -- RULES-04 metadata completeness.

Offline, fixture-based: reads the COMMITTED rulebook/manifest.yaml (and, for the sha256 check,
the committed vendored files it references) from disk -- does NOT re-fetch network. This is
deliberately not tmp_path-isolated like tests/rulebook/test_store.py: RULES-04 is a property of
the ACTUAL vendored artifact this plan commits, not a synthetic fixture -- the manifest under
test IS the one `git status` shows as tracked/staged.

Task 2 baseline: every-row metadata completeness (7 eCFR rows at that point). Task 3 extends
this file with the full manifest check (sha256-verified against the actual committed files) and
the D-PREC vendor-only boundary note. Phase 4 (RULES-06) grew ich 4 -> 5 (ICH Q1A(R2) vendored),
so the manifest is now 14 rows.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

_MANIFEST_PATH = Path("rulebook/manifest.yaml")
_REQUIRED_FIELDS = ("source", "citation", "version", "license", "url")
# RULES-04's metadata-completeness contract names "eCFR, ICH, FDA" chunks explicitly (this
# plan's <interfaces> block) -- rule TEXT fetched from a network source. The precedent row
# (Task 3) is a local, vendor-only copy (D-PREC: copy + hash + manifest row, never fetched) with
# no source URL by design -- `url` is legitimately empty there, not a completeness bug.
_URL_EXEMPT_SOURCES = ("precedent",)


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
        fields = [f for f in _REQUIRED_FIELDS if not (f == "url" and row.get("source") in _URL_EXEMPT_SOURCES)]
        for field in fields:
            assert row.get(field), f"row {row!r} missing required field {field!r}"

    raw_text = _MANIFEST_PATH.read_text()
    assert "_SUBSTITUTE_DATE_" not in raw_text


def test_manifest_has_14_rows_with_verified_sha256_and_dprec_boundary():
    rows = _load_manifest_rows()
    # 7 ecfr + 5 ich + 1 fda + 1 precedent. ich grew 4 -> 5 in Phase 4 (RULES-06): ICH Q1A(R2)
    # stability was vendored + added to ICH_GUIDELINES.
    assert len(rows) == 14

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
        if "error" in row:
            continue
        path = Path(row["path"])
        assert path.exists(), f"manifest row references a missing file: {row['path']}"
        actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual_sha256 == row["sha256"], f"{row['path']} sha256 does not match the manifest"

    assert counts == {"ecfr": 7, "ich": 5, "fda": 1, "precedent": 1}

    precedent_rows = [r for r in rows if r["source"] == "precedent"]
    assert len(precedent_rows) == 1
    assert "senior-reviewer" in precedent_rows[0]["note"]
