"""One-time, versioned rulebook build orchestration (D-RB2). Run manually; dynamic refresh is
post-v1. Fetches eCFR/ICH/FDA sources, parses each into the unified document-dict contract,
flows every source through the SAME Phase-1 substrate a submission uses, and persists via
rulebook.store.write_chunk. One bad source becomes a recorded skip, never a crashed build (D-16).

OFFLINE-FIRST (D-RB6): every build_* function checks the COMMITTED rulebook/** snapshot path
first. When that file already exists on disk, the build reads/parses it locally -- NO network
call -- so a clean checkout of this repo (CI, a fresh worktree, tests) can rebuild the local
chunk store deterministically from the vendored snapshot alone. A live fetch only happens in
"vendoring mode": the source file is genuinely missing (first-time vendoring of a new source).
Every build_* function also accepts an optional `(cache_dir, db_path)` pair so a caller (tests)
can target an ISOLATED store instead of the shared default `data/` store, and `update_manifest`
to opt out of writing to the committed `rulebook/manifest.yaml` when building into such a store.
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
from parse.pdf import extract_pdf
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
    doc_dict: dict,
    doc_id: str,
    citation: str,
    source: str,
    version: str,
    license_text: str,
    url: str,
    cache_dir: str | None = None,
    db_path: str | None = None,
) -> RuleChunk:
    """cache_dir/db_path are OPTIONAL -- None (the default) forwards nothing to write_chunk, so
    it falls back to its own module defaults (the shared data/ store). Pass both to target an
    ISOLATED store instead (e.g. a tmp_path-scoped store for tests, D-RB6)."""
    raw, _cell_ranges = serialize_document(doc_dict)
    nt = normalize(raw, serializer_version=SERIALIZER_VERSION)
    span = mint_span(nt.canonical, 0, len(nt.canonical), doc_id, nt.normalizer_version)
    chunk = RuleChunk(
        doc_id=doc_id, citation=citation, source=source, version=version,
        license=license_text, url=url, span=span,
        normalizer_version=nt.normalizer_version, serializer_version=nt.serializer_version,
    )
    write_kwargs = {}
    if cache_dir is not None:
        write_kwargs["cache_dir"] = cache_dir
    if db_path is not None:
        write_kwargs["db_path"] = db_path
    write_chunk(chunk, nt, **write_kwargs)
    return chunk


def _load_manifest_rows() -> list[dict]:
    if MANIFEST_PATH.exists():
        return yaml.safe_load(MANIFEST_PATH.read_text()) or []
    return []


def _save_manifest_rows(rows: list[dict]) -> None:
    RULEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(yaml.safe_dump(rows, sort_keys=False))


def _prior_manifest_row(rows: list[dict], source: str, citation: str) -> dict | None:
    for row in rows:
        if row.get("source") == source and row.get("citation") == citation and "error" not in row:
            return row
    return None


def build_ecfr(
    parts: tuple[str, ...] = ECFR_PARTS,
    cache_dir: str | None = None,
    db_path: str | None = None,
    update_manifest: bool = True,
) -> list[dict]:
    out_dir = RULEBOOK_DIR / "ecfr" / "title-21"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = _load_manifest_rows()
    rows = [r for r in manifest_rows if r.get("source") != "ecfr"]
    ecfr_public_domain_notice = "Public domain (17 U.S.C. 105 -- U.S. Government work; no copyright)."
    for part in parts:
        try:
            part_path = out_dir / f"part-{part}.xml"
            citation_guess = f"21 CFR Part {part}"
            if part_path.exists():
                # OFFLINE: build from the committed snapshot, no network call. The edition date
                # + URL are recovered from the manifest row recorded when this exact XML was
                # vendored -- a deterministic re-build from the snapshot (D-RB2), never a
                # fabricated date. Falls back to a self-describing placeholder only if the
                # snapshot's own manifest record is unexpectedly absent.
                xml_text = part_path.read_text(encoding="utf-8")
                prior = _prior_manifest_row(manifest_rows, "ecfr", citation_guess)
                edition_date = prior["version"] if prior else "offline (no prior manifest record)"
                url = (
                    prior["url"]
                    if prior
                    else f"https://www.ecfr.gov/api/versioner/v1/full/{edition_date}/title-21.xml?part={part}"
                )
            else:
                xml_text, edition_date = fetch_ecfr_part(part)  # vendoring mode: file missing, fetch once
                part_path.write_text(xml_text, encoding="utf-8")
                url = f"https://www.ecfr.gov/api/versioner/v1/full/{edition_date}/title-21.xml?part={part}"
            sections = parse_ecfr_sections(xml_text, part)
            for doc_dict, citation in sections:
                # doc_id derived deterministically from the citation string, e.g.
                # "21 CFR 211.166" -> "ecfr-211.166"; "21 CFR Part 11" -> "ecfr-Part-11".
                # No two sections within one part share a citation, so no collision risk.
                doc_id = "ecfr-" + citation.replace("21 CFR ", "").replace(" ", "-")
                _ingest_and_persist(
                    doc_dict, doc_id, citation, "ecfr", edition_date, ecfr_public_domain_notice, url,
                    cache_dir=cache_dir, db_path=db_path,
                )
            rows.append({
                "source": "ecfr", "citation": citation_guess, "version": edition_date,
                "license": ecfr_public_domain_notice, "url": url, "sha256": _sha256(xml_text.encode("utf-8")),
                "path": str(part_path), "section_count": len(sections),
            })
        except Exception as exc:  # noqa: BLE001 -- one bad part must never abort the other 6 (D-16)
            rows.append({"source": "ecfr", "citation": f"21 CFR Part {part}", "error": str(exc)[:300]})
            continue
    if update_manifest:
        _save_manifest_rows(rows)
    return rows


# --- ICH + FDA + precedent vendoring (Task 3) ---------------------------------------------

ICH_LEGAL_NOTICE = (
    "This document is protected by copyright and may be used, reproduced, incorporated "
    "into other works, adapted, modified, translated or distributed under a public license "
    "provided that ICH's copyright in the document is acknowledged at all times. In case of "
    "any adaption, modification or translation of the document, reasonable steps must be "
    "taken to clearly label, demarcate or otherwise identify that changes were made to or "
    "based on the original document. Any impression that the adaption, modification or "
    "translation of the original document is endorsed or sponsored by the ICH must be avoided. "
    "The document is provided \"as is\" without warranty of any kind. In no event shall the "
    "ICH or the authors of the original document be liable for any claim, damages or other "
    "liability arising from the use of the document. The above-mentioned permissions do not "
    "apply to content supplied by third parties. Therefore, for documents where the copyright "
    "vests in a third party, permission for reproduction must be obtained from this copyright holder."
)

ICH_GUIDELINES = [
    ("Q2-R2", "ICH Q2(R2)", "2023-11-30", "https://database.ich.org/sites/default/files/ICH_Q2(R2)_Guideline_2023_1130.pdf", "rulebook/ich/Q2-R2_Guideline_2023-11-30.pdf"),
    ("Q3A-R2", "ICH Q3A(R2)", "2006-10-25", "https://database.ich.org/sites/default/files/Q3A_R2__Guideline.pdf", "rulebook/ich/Q3A-R2_Guideline.pdf"),
    ("Q3B-R2", "ICH Q3B(R2)", "2006-06-02", "https://database.ich.org/sites/default/files/Q3B(R2)%20Guideline.pdf", "rulebook/ich/Q3B-R2_Guideline.pdf"),
    ("Q6A", "ICH Q6A", "1999-10-06", "https://database.ich.org/sites/default/files/Q6A%20Guideline.pdf", "rulebook/ich/Q6A_Guideline.pdf"),
]
FDA_GUIDANCE = ("fda-analytical-procedures", "FDA Guidance: Analytical Procedures and Methods Validation for Drugs and Biologics",
               "https://www.fda.gov/files/drugs/published/Analytical-Procedures-and-Methods-Validation-for-Drugs-and-Biologics.pdf",
               "rulebook/fda/analytical-procedures-and-methods-validation-for-drugs-and-biologics.pdf")


def _fetch_pdf_bytes(url: str) -> bytes:
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        return _get_with_retry(client, url).content


def build_ich(
    cache_dir: str | None = None,
    db_path: str | None = None,
    update_manifest: bool = True,
) -> list[dict]:
    rows = [r for r in _load_manifest_rows() if r.get("source") != "ich"]
    for doc_id, citation, version, url, rel_path in ICH_GUIDELINES:
        try:
            path = Path(rel_path)
            if path.exists():
                data = path.read_bytes()  # OFFLINE: build from the committed snapshot, no network
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                data = _fetch_pdf_bytes(url)  # vendoring mode: source file missing, fetch once
                path.write_bytes(data)
            parsed = extract_pdf(path)   # REUSE verbatim -- ordinary PDF, no new parser
            _ingest_and_persist(
                parsed, f"ich-{doc_id}", citation, "ich", version, ICH_LEGAL_NOTICE, url,
                cache_dir=cache_dir, db_path=db_path,
            )
            rows.append({"source": "ich", "citation": citation, "version": version, "license": "ICH_LEGAL_NOTICE (applied uniformly, see src/rulebook/build.py -- stored regardless of whether the source PDF embeds its own copy, Pitfall 4)",
                        "url": url, "sha256": _sha256(data), "path": rel_path})
        except Exception as exc:  # noqa: BLE001
            rows.append({"source": "ich", "citation": citation, "error": str(exc)[:300]})
            continue
    if update_manifest:
        _save_manifest_rows(rows)
    return rows


def build_fda(
    cache_dir: str | None = None,
    db_path: str | None = None,
    update_manifest: bool = True,
) -> list[dict]:
    rows = [r for r in _load_manifest_rows() if r.get("source") != "fda"]
    doc_id, citation, url, rel_path = FDA_GUIDANCE
    try:
        path = Path(rel_path)
        if path.exists():
            data = path.read_bytes()  # OFFLINE: build from the committed snapshot, no network
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = _fetch_pdf_bytes(url)  # vendoring mode: source file missing, fetch once
            path.write_bytes(data)
        parsed = extract_pdf(path)
        _ingest_and_persist(
            parsed, doc_id, citation, "fda", "current as vendored",
            "U.S. Government work -- public domain (17 U.S.C. 105).", url,
            cache_dir=cache_dir, db_path=db_path,
        )
        rows.append({"source": "fda", "citation": citation, "version": "current as vendored",
                    "license": "U.S. Government work -- public domain (17 U.S.C. 105).",
                    "url": url, "sha256": _sha256(data), "path": rel_path})
    except Exception as exc:  # noqa: BLE001
        rows.append({"source": "fda", "citation": citation, "error": str(exc)[:300]})
    if update_manifest:
        _save_manifest_rows(rows)
    return rows


def vendor_precedent(src: str = "Sample Data/ANDA-TDDS-Deficiency Roadmap.xlsm",
                     dest: str = "rulebook/precedents/ANDA-TDDS-Deficiency-Roadmap.xlsm") -> dict:
    """D-PREC: VENDOR ONLY (copy + hash + manifest row). Do NOT parse, ingest, or dedupe here --
    the schema-vs-deficiency_kb audit and dedupe policy are the senior reviewer's recorded
    manual step (02-CONTEXT.md D-PREC), not executable work for this phase."""
    src_path, dest_path = Path(src), Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    data = src_path.read_bytes()
    dest_path.write_bytes(data)
    row = {"source": "precedent", "citation": "ANDA-TDDS Deficiency Roadmap (precedent spreadsheet)",
          "version": "vendored as-is", "license": "internal", "url": "",
          "sha256": _sha256(data), "path": dest, "note": "D-PREC: schema audit + dedupe policy vs defpredict.main.deficiency_kb is a senior-reviewer manual step, NOT performed here."}
    rows = [r for r in _load_manifest_rows() if r.get("source") != "precedent"]
    rows.append(row)
    _save_manifest_rows(rows)
    return row


def main() -> int:
    build_ecfr(); build_ich(); build_fda(); vendor_precedent()
    rebuild_local_index()
    print(f"rulebook build complete: {len(_load_manifest_rows())} manifest rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
