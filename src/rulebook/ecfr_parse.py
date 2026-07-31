"""eCFR DIV8/SECTION XML -> the unified document-dict contract (RULES-01).

Converges on the SAME {filename,page_count,toc,pages:[{blocks,tables,figures}]} shape
extract_pdf/extract_docx emit, so eCFR content flows through the UNCHANGED Phase-1 substrate
(serialize_document -> normalize -> mint_span) exactly like a submission PDF/DOCX. This is the
ONE new parser this phase needs -- everything downstream of the dict is reused verbatim.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET


def _paragraph_text(p: ET.Element) -> str:
    return "".join(p.itertext()).strip()


def _section_citation(div8: ET.Element, part_n: str) -> str:
    raw = div8.get("hierarchy_metadata", "")
    if raw:
        try:
            parsed = json.loads(raw)
            citation = parsed.get("citation", "")
            if citation:
                return citation
        except (json.JSONDecodeError, AttributeError):
            pass
    n = div8.get("N", "")
    return f"21 CFR {n}" if n else f"21 CFR Part {part_n}"


def parse_ecfr_sections(xml_text: str, part_n: str) -> list[tuple[dict, str]]:
    root = ET.fromstring(xml_text)
    results: list[tuple[dict, str]] = []
    for div8 in root.iter("DIV8"):
        if div8.get("TYPE") != "SECTION":
            continue
        citation = _section_citation(div8, part_n)
        assert "_SUBSTITUTE_DATE_" not in citation, f"placeholder leaked into citation for {div8.get('N')!r}"
        head = (div8.findtext("HEAD") or "").strip()
        blocks = [{"text": head, "page": 1, "reading_order": 0, "lines": []}] if head else []
        for i, p in enumerate(div8.findall("P"), start=1):
            text = _paragraph_text(p)
            if text:
                blocks.append({"text": text, "page": 1, "reading_order": i, "lines": []})
        doc_dict = {
            "filename": f"ecfr-{div8.get('N', part_n)}.xml", "page_count": 1, "toc": [],
            "pages": [{
                "page_number": 1, "page_label": "", "width": 612.0, "height": 792.0,
                "rotation": 0, "source": "ecfr-xml", "is_scanned": False,
                "blocks": blocks, "tables": [], "figures": [],
            }],
        }
        results.append((doc_dict, citation))
    return results
