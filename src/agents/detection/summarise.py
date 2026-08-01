"""Stage 3, part 1' — the lossless summariser (runs in parallel with the planner).

Produces one *section-shaped* summary per section so the assembler can drop a summary in wherever
a section is not a worker's focus. The LLM only condenses PROSE; TABLES ARE CARRIED VERBATIM BY CODE
(never sent through the model), so no table can be reformatted, reordered, or corrupted. A fidelity
guard keeps the original prose whenever the condensed version dropped a number — losing a number is
exactly how a cross-section (intersection) fault becomes invisible to a neighbour worker.
"""
from __future__ import annotations

import concurrent.futures
import re

import structlog
from pydantic import BaseModel, Field

from agents.detection.prompts import SUMMARISER
from config import get_settings
from llm.structured import structured_call

log = structlog.get_logger()

_MAX_WORKERS = 10
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]*\b")   # USP, LOQ, ICH, AET, ETFE, HPLC, RRT, Q3D ...


class ProseSummary(BaseModel):
    summary: str = Field(default="", description="Condensed prose; every number and named limit kept.")


def _key_terms(text: str) -> set[str]:
    """Facts that MUST survive condensation: every number, plus technical acronyms / named entities
    (USP, LOQ, ETFE, Q3D...). Dropping any of these is how a non-numeric cross-section fact goes
    missing from a neighbour worker's context, so their loss forces the full-prose fallback."""
    t = text or ""
    return set(_NUM_RE.findall(t)) | set(_ACRONYM_RE.findall(t))


def _section_summary(index: int, section: dict, summary: str, lossy: bool) -> dict:
    return {
        "section_index": index,
        "heading": section.get("heading", ""),
        "summary": summary,
        "tables": section.get("tables", []),          # carried verbatim, never through the LLM
        "page_start": section.get("page_start", 0),
        "page_end": section.get("page_end", 0),
        "lossy": lossy,
    }


def _summarise_one(index: int, section: dict, model: str) -> dict:
    prose = section.get("text", "") or ""
    if not prose.strip():
        return _section_summary(index, section, "", lossy=False)

    inst, _failure = structured_call(
        messages=[
            {"role": "system", "content": SUMMARISER},
            {"role": "user", "content": f"Heading: {section.get('heading', '')}\n\n{prose}"},
        ],
        model_cls=ProseSummary,
        model=model,
        temperature=0.0,
        max_tokens=1024,
        repair_context="summariser",
    )
    summary = inst.summary if inst else ""
    # Fidelity guard: if any number OR named entity from the prose vanished, keep the original prose
    # (lossless wins) — this is what makes the summary safe to hand a neighbour worker as context.
    if not summary.strip() or (_key_terms(prose) - _key_terms(summary)):
        return _section_summary(index, section, prose, lossy=True)
    return _section_summary(index, section, summary, lossy=False)


def summarise_sections(sections: list[dict], model: str | None = None) -> list[dict]:
    model = model or get_settings().detector_model
    results: list[dict | None] = [None] * len(sections)
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_summarise_one, i, s, model): i for i, s in enumerate(sections)}
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as exc:  # noqa: BLE001 - fall back to full prose on any error
                log.warning("summarise_failed", index=i, error=str(exc)[:200])
                results[i] = _section_summary(i, sections[i], sections[i].get("text", ""), lossy=True)
    return [r for r in results if r is not None]
