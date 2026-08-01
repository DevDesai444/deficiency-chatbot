"""Stage 3 assembly — build each worker's sandwich JSON (deterministic, no LLM).

A worker's sandwich is the whole document as an ordered list of section objects: the worker's own
section(s) kept FULL (verbatim text + tables), every other section replaced by its summary. JSON in /
JSON out — structure and section order are preserved so the worker can cite and cross-reference.
Tables are never degraded (full on focus, verbatim on context). "Nothing more or less" than a swap.
"""
from __future__ import annotations

import json


def _focused_obj(index: int, section: dict) -> dict:
    return {
        "section_index": index,
        "role": "focused",
        "heading": section.get("heading", ""),
        "page_start": section.get("page_start", 0),
        "page_end": section.get("page_end", 0),
        "text": section.get("text", ""),
        "tables": section.get("tables", []),
    }


def _context_obj(index: int, section: dict, summary: dict) -> dict:
    return {
        "section_index": index,
        "role": "context",
        "heading": summary.get("heading", "") or section.get("heading", ""),
        "page_start": summary.get("page_start", 0),
        "page_end": summary.get("page_end", 0),
        "summary": summary.get("summary", ""),
        "tables": summary.get("tables", section.get("tables", [])),
    }


def build_sandwich(sections: list[dict], summaries: list[dict], focused_indices: list[int]) -> dict:
    """`summaries` is aligned to `sections` (from summarise_sections). `focused_indices` are the
    positions kept full; every other position becomes its summary."""
    focus = set(focused_indices)
    out_sections: list[dict] = []
    for i, section in enumerate(sections):
        if i in focus:
            out_sections.append(_focused_obj(i, section))
        else:
            summary = summaries[i] if i < len(summaries) and summaries[i] else {}
            out_sections.append(_context_obj(i, section, summary))
    return {"focused_section_indices": sorted(focus), "sections": out_sections}


def render_sandwich(sandwich: dict) -> str:
    return json.dumps(sandwich, ensure_ascii=False, indent=1)


def open_review_chunks(n_sections: int, max_per: int = 2) -> list[list[int]]:
    """Mechanical sweep grouping for the open-review pass — 1-2 sections per chunk, independent of the
    planner, so a bad plan cannot leave a section unreviewed."""
    chunks: list[list[int]] = []
    for start in range(0, n_sections, max_per):
        chunks.append(list(range(start, min(start + max_per, n_sections))))
    return chunks
