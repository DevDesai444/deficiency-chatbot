"""Corpus orchestrator — the substrate swap: one PDF path -> an ingested corpus (INGEST-01/03).

`ingest_corpus(root)` walks an arbitrary, deeply-nested directory of mixed PDF+DOCX with NO count
or depth cap, classifies each document by CONTENT (never folder name, D-09), builds each doc's
canonical substrate + table index + classification, determines a typed status + availability tiers
(D-17/D-30), and persists a resumable corpus index + coverage manifest. One bad file becomes a
manifest row and never aborts the batch (D-16). It leaves the existing single-file detection
entry point and the single-file upload API UNTOUCHED -- it neither imports nor modifies them (D-13).

parsed_partial is read from an explicit source FACT (`source == "rapidocr-flat-text"` /
`"rapidocr-fallback"`, or a table `_parse_failed` marker), NEVER inferred from empty blocks -- a
genuinely blank scanned page (`source == "rapidocr"`, no text) is complete, not degraded (D-17).
"""
from __future__ import annotations

from pathlib import Path

import structlog
from pydantic import BaseModel

from parse.docx import extract_docx
from parse.pdf import PARSER_VERSION, extract_pdf
from parse.section_splitter import split_document

from ingest import limits
from ingest.anchors import mint_span
from ingest.classify import EscalationStats, classify_document
from ingest.manifest import CoverageManifest, DocEntry, OutlineEntry
from ingest.normalize import NORMALIZER_VERSION, normalize
from ingest.serialize import SERIALIZER_VERSION, serialize_document
from ingest.store import (
    DEFAULT_CACHE_DIR,
    cache_key,
    content_hash,
    read_doc_cache,
    save_manifest,
    write_doc_cache,
)
from ingest.tables import build_table_index

log = structlog.get_logger()

_DEGRADED_SOURCES = ("rapidocr-flat-text", "rapidocr-fallback")


class CorpusIndex(BaseModel):
    """The per-submission corpus index: root + coverage manifest + cache location."""
    root: str
    cache_dir: str = DEFAULT_CACHE_DIR
    manifest: CoverageManifest = CoverageManifest()

    def cached_entry(self, doc_id: str) -> dict | None:
        """Fetch a document's persisted cache entry (full canonical text + offset map + index)."""
        for d in self.manifest.documents:
            if d.doc_id == doc_id:
                key = cache_key(d.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
                return read_doc_cache(self.cache_dir, key)
        return None


def _degradation(parsed: dict) -> str:
    """Return a reason string if any page/table degraded (source FACT / _parse_failed), else ''."""
    reasons: list[str] = []
    for page in parsed.get("pages", []):
        if page.get("source") in _DEGRADED_SOURCES:
            reasons.append(f"page {page.get('page_number')}: OCR {page['source']} (text preserved, tables/boxes lost)")
        for t in page.get("tables", []):
            if isinstance(t, dict) and "_parse_failed" in t:
                reasons.append(str(t["_parse_failed"].get("reason", "table parse failed")))
    return "; ".join(reasons)


def _build_outline(sections: list[dict], nt, doc_id: str) -> list[OutlineEntry]:
    """Best-effort section outline: identity = span over the heading in canonical text (D-18)."""
    outline: list[OutlineEntry] = []
    for sec in sections:
        heading = (sec.get("heading") or "").strip()
        if not heading:
            continue
        probe = heading[:40]
        pos = nt.canonical.find(probe)
        if pos < 0:
            pos = 0
        span = mint_span(nt.canonical, pos, min(len(nt.canonical), pos + len(probe)), doc_id, nt.normalizer_version)
        outline.append(OutlineEntry(span=span, label=heading))
    return outline


def _real_tables(parsed: dict) -> list[dict]:
    """Flatten real (non-_parse_failed) table dicts across pages, in serialization order."""
    out: list[dict] = []
    for page in parsed.get("pages", []):
        for t in page.get("tables", []):
            if isinstance(t, dict) and "_parse_failed" not in t:
                out.append(t)
    return out


def ingest_corpus(root: str | Path, cache_dir: str = DEFAULT_CACHE_DIR, model: str | None = None) -> CorpusIndex:
    """Walk `root` uncapped, ingest every PDF+DOCX by content, and return a CorpusIndex (D-16 never-abort)."""
    root = Path(root)
    entries: list[DocEntry] = []
    stats = EscalationStats()

    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        ext = path.suffix.lower()
        try:
            safe = limits.safe_resolve(root, path)          # reject symlink/.. escapes (T-01-03)
        except limits.LimitExceeded as exc:
            continue  # a path escaping the corpus root is not ingested
        if ext not in (".pdf", ".docx"):
            entries.append(DocEntry(doc_id=str(path.relative_to(root)), filename=path.name,
                                    content_hash="", status="unsupported",
                                    reason=f"unsupported extension {ext}"))
            continue

        try:
            file_bytes = safe.read_bytes()
            chash = content_hash(file_bytes)
            doc_id = chash
            key = cache_key(chash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
            cached = read_doc_cache(cache_dir, key)
            if cached is not None and cached.get("doc_entry"):
                entries.append(DocEntry.model_validate(cached["doc_entry"]))   # skip-unchanged (D-14)
                stats.record(cached["doc_entry"].get("classification", {}).get("tier", "none") if cached["doc_entry"].get("classification") else "none")
                continue

            limits.check_file_limits(safe)                                     # byte cap before heavy parse
            if ext == ".docx":
                limits.docx_zip_guard(safe)                                    # zip-bomb/zip-slip before parse
            parsed = extract_pdf(safe) if ext == ".pdf" else extract_docx(safe)
        except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run (D-16)
            entries.append(DocEntry(doc_id=str(path.relative_to(root)), filename=path.name,
                                    content_hash="", status="parse_failed", reason=str(exc)[:300]))
            continue

        # --- substrate assembly (content only; the path never reaches classification, D-09) ---
        raw, cell_ranges = serialize_document(parsed)
        nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
        table_index = build_table_index(nt, _real_tables(parsed), cell_ranges, doc_id)
        sections = split_document(parsed)
        outline = _build_outline(sections, nt, doc_id)
        classification = classify_document(nt, outline=outline, doc_id=doc_id, model=model, stats=stats)

        # --- status + availability tiers by explicit FACT (D-17/D-30) ---
        degraded = _degradation(parsed)
        status = "parsed_partial" if degraded else "parsed"
        structure = "outlined" if outline else "flat"
        has_lost_table = any("_parse_failed" in t for page in parsed.get("pages", []) for t in page.get("tables", []) if isinstance(t, dict))
        tables_tier = "addressable" if (table_index and not has_lost_table) else "unavailable"

        entry = DocEntry(
            doc_id=doc_id, filename=path.name, content_hash=chash,
            status=status, reason=degraded, structure=structure, tables=tables_tier,
            classification=classification, title=classification.label,
            outline=outline, normalizer_version=NORMALIZER_VERSION, serializer_version=SERIALIZER_VERSION,
        )
        entries.append(entry)
        write_doc_cache(cache_dir, key, {
            "canonical": nt.canonical, "raw_serialized": nt.raw_serialized,
            "offset_map": [r.model_dump() for r in nt.offset_map],
            "normalizer_version": NORMALIZER_VERSION, "serializer_version": SERIALIZER_VERSION,
            "table_index": {k: v.model_dump() for k, v in table_index.items()},
            "doc_entry": entry.model_dump(),
        })

    counts: dict[str, int] = {}
    for e in entries:
        counts[e.status] = counts.get(e.status, 0) + 1
    manifest = CoverageManifest(documents=entries, escalation_rate=stats.escalation_rate(), counts=counts)
    index = CorpusIndex(root=str(root), cache_dir=cache_dir, manifest=manifest)
    try:
        save_manifest(manifest, corpus_id=str(root))
    except Exception as exc:  # noqa: BLE001 -- persistence failure must not lose the in-memory index
        log.warning("manifest_persist_failed", error=str(exc)[:200])
    log.info("ingest_complete", docs=len(entries), counts=counts, escalation_rate=stats.escalation_rate())
    return index
