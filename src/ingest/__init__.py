"""Corpus ingestion package (Phase 1).

Turns an arbitrary directory of PDF+DOCX documents into an ingested corpus: the
span-anchor substrate (canonical text + content-addressed span-IDs + table-cell
addressing + a re-open/verify primitive) that later phases ground on.

The public library barrel (`ingest_corpus`, `CorpusIndex`, `open_span`) is
finalized in Plan 09; earlier plans import the concrete modules directly
(`ingest.serialize`, `ingest.limits`, ...).
"""
