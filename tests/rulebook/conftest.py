"""Shared Plan 02-02 test scaffolding for the local rulebook store (D-RB6 offline discipline).

Mirrors tests/ingest/conftest.py's builder-function discipline: `fixture_chunk` is a plain
helper (not a `@pytest.fixture`), so callers control every input explicitly and every test
stays fully offline -- no network, no Databricks, no environment-dependent word list.
"""
from __future__ import annotations

from ingest.anchors import mint_span
from ingest.normalize import normalize
from rulebook.store import RuleChunk


def fixture_chunk(
    tmp_path,
    doc_id: str = "21-cfr-211.166",
    citation: str = "21 CFR 211.166",
    text: str = "Written stability testing procedures shall be established.",
    source: str = "ecfr",
    version: str = "2026-07-29",
    license_: str = "public domain (US Government work)",
    url: str = "https://www.ecfr.gov/current/title-21/section-211.166",
):
    """Build a real `NormalizedText` (via `ingest.normalize.normalize`) + a matching `RuleChunk`
    whose span covers the WHOLE canonical text (`mint_span(0, len(canonical))`), plus a
    tmp_path-scoped `(cache_dir, db_path)` pair so every test runs fully isolated -- no shared
    `data/` state, no network, no Databricks (D-RB6).

    Returns `(chunk, nt, cache_dir, db_path)`.
    """
    nt = normalize(text)
    span = mint_span(nt.canonical, 0, len(nt.canonical), doc_id, nt.normalizer_version)
    chunk = RuleChunk(
        doc_id=doc_id,
        citation=citation,
        source=source,
        version=version,
        license=license_,
        url=url,
        span=span,
        normalizer_version=nt.normalizer_version,
        serializer_version=nt.serializer_version,
    )
    cache_dir = str(tmp_path / "rulebook_cache")
    db_path = str(tmp_path / "rulebook_test.db")
    return chunk, nt, cache_dir, db_path
