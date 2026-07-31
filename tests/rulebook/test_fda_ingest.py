"""Tests for FDA guidance vendoring (Task 3, RULES-03) -- the stable direct fda.gov URL path
(Pitfall 10), not the regulations.gov attachment pipeline.

OFFLINE (D-RB6): builds the FDA chunk from the REAL, COMMITTED rulebook/fda/*.pdf snapshot
(Task 3's vendored file) via build_fda's local-file-first path (src/rulebook/build.py) into an
ISOLATED tmp_path_factory-scoped store -- NO network call, NO dependence on the shared default
data/ store. A module-scoped fixture builds once; every test reads through lookup_citation/
all_chunks with an explicit db_path.
"""
from __future__ import annotations

import pytest

from rulebook.build import FDA_GUIDANCE, build_fda
from rulebook.store import all_chunks, lookup_citation


@pytest.fixture(scope="module")
def fda_db_path(tmp_path_factory):
    tmp_dir = tmp_path_factory.mktemp("fda_rulebook")
    cache_dir = str(tmp_dir / "cache")
    db_path = str(tmp_dir / "rulebook_test.db")

    rows = build_fda(cache_dir=cache_dir, db_path=db_path, update_manifest=False)

    assert not any("error" in row for row in rows), f"build_fda reported an error offline: {rows}"
    return db_path


def test_fda_guidance_ingests(fda_db_path):
    _doc_id, citation, url, _rel_path = FDA_GUIDANCE

    chunk = lookup_citation(citation, db_path=fda_db_path)

    assert chunk is not None
    assert chunk.source == "fda"
    assert chunk.url == url
    assert "public domain" in chunk.license.lower()

    fda_chunks = [c for c in all_chunks(db_path=fda_db_path) if c.source == "fda"]
    assert len(fda_chunks) == 1
