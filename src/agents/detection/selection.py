"""Stage 3, part 1 — pick the domains to deep-dive, and pull precedent for each.

The count is adaptive: the selector ranks the domains relevant to THIS document (up to a
cap). Selection only *adds* specialists — the open reviewers still read every section, so a
domain that isn't selected is still covered by breadth. Never a fault ceiling.
"""
from __future__ import annotations

import json
import re

import structlog

from agents.detection.catalog import CANONICAL_DOMAINS, domain_catalog_text
from agents.detection.prompts import DOMAIN_SELECTOR
from config import get_settings
from llm.client import chat_completion
from retrieval.knowledge_base import find_similar_deficiencies
from schemas.flaws import SimilarDeficiency

log = structlog.get_logger()

_MAX_DOMAINS = 8

_FALLBACK_HINTS: dict[str, list[str]] = {
    "method-validation": ["validation", "linearity", "precision", "specificity", "system suitability", "lod", "loq"],
    "impurities": ["impurit", "related compound", "related substance"],
    "elemental-impurities": ["elemental", "q3d", "metal"],
    "residual-solvents": ["residual solvent", "q3c"],
    "stability": ["stability"],
    "dissolution": ["dissolution", "ivrt", "in-vitro"],
    "container-closure": ["leachable", "extractable", "container", "closure", "e&l", "e & l"],
    "specification": ["specification", "acceptance criteria", "assay", "coa"],
}


def _doc_digest(sections: list[dict]) -> str:
    heads = [s.get("heading", "") for s in sections if s.get("heading")]
    return "Section headings:\n" + "\n".join(f"- {h}" for h in heads[:40])


def _parse_domain_array(resp: str) -> list[str]:
    match = re.search(r"\[.*\]", resp or "", re.S)
    if not match:
        return []
    try:
        arr = json.loads(match.group())
    except Exception:  # noqa: BLE001
        return []
    return [str(x).strip() for x in arr if isinstance(x, str)]


def _fallback_domains(sections: list[dict]) -> list[str]:
    text = " ".join(s.get("heading", "") + " " + s.get("text", "") for s in sections).lower()
    hits = [dom for dom, kws in _FALLBACK_HINTS.items() if any(k in text for k in kws)]
    return hits or ["specification", "method-validation", "impurities"]


def select_domains(doc: dict, sections: list[dict], model: str | None = None) -> list[str]:
    picked: list[str] = []
    try:
        resp = chat_completion(
            messages=[
                {"role": "system", "content": DOMAIN_SELECTOR.format(catalog=domain_catalog_text())},
                {"role": "user", "content": f"Document: {doc.get('filename', '')}\n\n{_doc_digest(sections)}"},
            ],
            model=model or get_settings().detector_model,
            max_tokens=200,
        )
        picked = [d for d in _parse_domain_array(resp) if d in CANONICAL_DOMAINS]
    except Exception as exc:  # noqa: BLE001
        log.warning("domain_selection_failed", error=str(exc)[:200])

    if not picked:
        picked = _fallback_domains(sections)

    seen: set[str] = set()
    ordered: list[str] = []
    for d in picked:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    return ordered[:_MAX_DOMAINS]


def gather_precedents(domain: str, doc: dict, top_k: int = 3) -> list[SimilarDeficiency]:
    query = f"{domain}: {CANONICAL_DOMAINS.get(domain, '')} — {doc.get('filename', '')}"
    try:
        return find_similar_deficiencies(query, top_k=top_k)
    except Exception as exc:  # noqa: BLE001 - retrieval is best-effort; absence of precedent is not an error
        log.warning("precedent_retrieval_failed", domain=domain, error=str(exc)[:200])
        return []
