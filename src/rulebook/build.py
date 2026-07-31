"""One-time, versioned rulebook build orchestration (D-RB2). Run manually; dynamic refresh is
post-v1. Fetches eCFR/ICH/FDA sources, parses each into the unified document-dict contract,
flows every source through the SAME Phase-1 substrate a submission uses, and persists via
rulebook.store.write_chunk. One bad source becomes a recorded skip, never a crashed build (D-16).
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import httpx
import yaml

from ingest.anchors import mint_span
from ingest.normalize import NORMALIZER_VERSION, normalize
from ingest.serialize import SERIALIZER_VERSION, serialize_document
from rulebook.ecfr_parse import parse_ecfr_sections
from rulebook.store import RuleChunk, rebuild_local_index, write_chunk

ECFR_PARTS = ("210", "211", "314", "320", "600", "601", "11")
RULEBOOK_DIR = Path("rulebook")
MANIFEST_PATH = RULEBOOK_DIR / "manifest.yaml"
_MAX_RETRIES = 3


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_with_retry(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        resp = client.get(url, **kwargs)
        if resp.status_code == 429 and attempt < _MAX_RETRIES - 1:
            time.sleep(2**attempt)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"unreachable: {url}")


def fetch_ecfr_part(part: str, title: str = "21") -> tuple[str, str]:
    """(xml_text, edition_date). edition_date is ALWAYS the queried up_to_date_as_of -- NEVER
    datetime.now() (Pitfall 3: unpublished/wall-clock dates 404)."""
    with httpx.Client(timeout=60.0) as client:
        titles = _get_with_retry(client, "https://www.ecfr.gov/api/versioner/v1/titles.json").json()
        edition_date = next(t["up_to_date_as_of"] for t in titles["titles"] if t["number"] == int(title))
        resp = _get_with_retry(
            client,
            f"https://www.ecfr.gov/api/versioner/v1/full/{edition_date}/title-{title}.xml",
            params={"part": part},
        )
        return resp.text, edition_date


def _ingest_and_persist(
    doc_dict: dict, doc_id: str, citation: str, source: str, version: str, license_text: str, url: str
) -> RuleChunk:
    raw, _cell_ranges = serialize_document(doc_dict)
    nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
    span = mint_span(nt.canonical, 0, len(nt.canonical), doc_id, nt.normalizer_version)
    chunk = RuleChunk(
        doc_id=doc_id, citation=citation, source=source, version=version,
        license=license_text, url=url, span=span,
        normalizer_version=nt.normalizer_version, serializer_version=nt.serializer_version,
    )
    write_chunk(chunk, nt)
    return chunk


def _load_manifest_rows() -> list[dict]:
    if MANIFEST_PATH.exists():
        return yaml.safe_load(MANIFEST_PATH.read_text()) or []
    return []


def _save_manifest_rows(rows: list[dict]) -> None:
    RULEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(yaml.safe_dump(rows, sort_keys=False))


def build_ecfr(parts: tuple[str, ...] = ECFR_PARTS) -> list[dict]:
    out_dir = RULEBOOK_DIR / "ecfr" / "title-21"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [r for r in _load_manifest_rows() if r.get("source") != "ecfr"]
    ecfr_public_domain_notice = "Public domain (17 U.S.C. 105 -- U.S. Government work; no copyright)."
    for part in parts:
        try:
            xml_text, edition_date = fetch_ecfr_part(part)
            part_path = out_dir / f"part-{part}.xml"
            part_path.write_text(xml_text, encoding="utf-8")
            sections = parse_ecfr_sections(xml_text, part)
            url = f"https://www.ecfr.gov/api/versioner/v1/full/{edition_date}/title-21.xml?part={part}"
            for doc_dict, citation in sections:
                # doc_id derived deterministically from the citation string, e.g.
                # "21 CFR 211.166" -> "ecfr-211.166"; "21 CFR Part 11" -> "ecfr-Part-11".
                # No two sections within one part share a citation, so no collision risk.
                doc_id = "ecfr-" + citation.replace("21 CFR ", "").replace(" ", "-")
                _ingest_and_persist(doc_dict, doc_id, citation, "ecfr", edition_date, ecfr_public_domain_notice, url)
            rows.append({
                "source": "ecfr", "citation": f"21 CFR Part {part}", "version": edition_date,
                "license": ecfr_public_domain_notice, "url": url, "sha256": _sha256(xml_text.encode("utf-8")),
                "path": str(part_path), "section_count": len(sections),
            })
        except Exception as exc:  # noqa: BLE001 -- one bad part must never abort the other 6 (D-16)
            rows.append({"source": "ecfr", "citation": f"21 CFR Part {part}", "error": str(exc)[:300]})
            continue
    _save_manifest_rows(rows)
    return rows
