"""Corpus ingestion package (Phase 1).

Turns an arbitrary directory of PDF+DOCX documents into an ingested corpus: the
span-anchor substrate (canonical text + content-addressed span-IDs + table-cell
addressing + a re-open/verify primitive) that later phases ground on.

The public library barrel exposes the corpus entry point and the re-open primitive; evals and
later agent phases import THIS library (the `python -m ingest` CLI is only an ergonomic shell, D-11).

The barrel is LAZY (PEP 562 `__getattr__`): `agents.detection.ctd` imports `ingest.registry`, which
runs this package init, so eagerly importing `ingest.corpus` here would create a circular import
(corpus -> classify -> agents.detection.ctd, while ctd is mid-import). Lazy resolution binds the
names only on first access, after ctd has finished.
"""

__all__ = ["ingest_corpus", "CorpusIndex", "open_span"]


def __getattr__(name: str):
    if name in ("ingest_corpus", "CorpusIndex"):
        from ingest import corpus
        return getattr(corpus, name)
    if name == "open_span":
        from ingest.anchors import open_span
        return open_span
    raise AttributeError(f"module 'ingest' has no attribute {name!r}")
