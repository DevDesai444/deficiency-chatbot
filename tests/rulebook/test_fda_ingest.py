"""Tests for FDA guidance vendoring (Task 3, RULES-03) -- the stable direct fda.gov URL path
(Pitfall 10), not the regulations.gov attachment pipeline.

Runs against the REAL vendored PDF (Task 3's committed rulebook/fda/*.pdf) and the REAL
persisted chunk store (this plan's live build).
"""
from __future__ import annotations

from rulebook.build import FDA_GUIDANCE
from rulebook.store import all_chunks, lookup_citation


def test_fda_guidance_ingests():
    _doc_id, citation, url, _rel_path = FDA_GUIDANCE

    chunk = lookup_citation(citation)

    assert chunk is not None
    assert chunk.source == "fda"
    assert chunk.url == url
    assert "public domain" in chunk.license.lower()

    fda_chunks = [c for c in all_chunks() if c.source == "fda"]
    assert len(fda_chunks) == 1
