"""Content classifier (INGEST-01, D-01/02/03/04/07/08/09/10/27/28/29).

Deterministic-first (regex -> body lexicon -> first-N-lines title block), with cheap-model LLM
escalation via the hardened `structured.py` only when the deterministic layer has no confident
signal. Emits `{label, family_guess, confidence, tier, triggering_span}` and records a measured
per-tier escalation rate (D-27) -- the guard that keeps the deterministic layer from silently
degrading into per-document LLM classification at full cost.

D-09 is enforced BY CONSTRUCTION: `classify_document` takes canonical text + outline + doc_id only
-- never a filename or path -- so a hostile folder name cannot flip a document's class. D-03: no
hard threshold; a low score is recorded and returned, never dropped (non-CTD docs are first-class,
D-02). D-29: the resolving tier and the span-ID that triggered the classification are both recorded
(the three tiers emit confidence on incomparable scales; provenance makes that explicit).
"""
from __future__ import annotations

import re

import structlog
from pydantic import BaseModel

from config import get_settings
from llm.structured import structured_call
from schemas.documents import DocClassification, NormalizedText, SpanID

from agents.detection.ctd import detect_family
from ingest.anchors import mint_span
from ingest.registry import families_catalog_text, load_families, load_lexicon

log = structlog.get_logger()

_TITLE_BLOCK_LINES = 15          # D-28: the first ~15 lines are the title block of a flat doc
_TITLE_BLOCK_CHARS = 1000
_REGEX_CONFIDENCE = 0.99         # a literal CTD-number hit is effectively certain (D-29)


class ClassifyResult(BaseModel):
    """The LLM escalation tier's structured output contract."""
    label: str = ""
    family: str = ""
    confidence: float = 0.0


class EscalationStats:
    """Per-tier resolution counter -> escalation_rate (D-27), surfaced in the run summary."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def record(self, tier: str) -> None:
        self.counts[tier] = self.counts.get(tier, 0) + 1

    def escalation_rate(self) -> dict[str, float]:
        total = sum(self.counts.values()) or 1
        return {tier: c / total for tier, c in self.counts.items()}


def _family_label(family_id: str) -> str:
    for entry in load_families():
        if entry["id"] == family_id:
            return entry["label"]
    return ""


def _mint(nt: NormalizedText, start: int, end: int, doc_id: str) -> SpanID:
    return mint_span(nt.canonical, start, end, doc_id, nt.normalizer_version)


def _regex_tier(nt: NormalizedText, doc_id: str, text: str | None = None, base: int = 0) -> DocClassification | None:
    """Literal CTD-number match over canonical text (reuses ctd.detect_family, Plan 05)."""
    canonical = nt.canonical if text is None else text
    fid = detect_family(canonical)
    if not fid:
        return None
    # locate the match for a triggering span (CTD number with optional internal whitespace)
    loose = re.escape(fid).replace(r"\.", r"\.\s*")
    m = re.search(loose, canonical, re.IGNORECASE)
    start, end = (base + m.start(), base + m.end()) if m else (0, min(len(nt.canonical), 12))
    return DocClassification(
        label=_family_label(fid), family_guess=fid, confidence=_REGEX_CONFIDENCE,
        tier="regex", triggering_span=_mint(nt, start, end, doc_id),
    )


def _lexicon_tier(nt: NormalizedText, doc_id: str, text: str | None = None, base: int = 0) -> DocClassification | None:
    """Score each family by body-lexicon keyword hits (D-08); best family with >=1 hit wins."""
    canonical = nt.canonical if text is None else text
    low = canonical.lower()
    lexicon = load_lexicon()
    best_family, best_hits, best_off = "", 0, 0
    for family_id, keywords in lexicon.items():
        hits = [kw for kw in keywords if kw in low]
        if len(hits) > best_hits:
            best_family, best_hits = family_id, len(hits)
            best_off = low.find(hits[0])
    if best_hits < 1:
        return None
    confidence = min(0.9, 0.2 + 0.15 * best_hits)   # similarity-style, normalized (D-29 own scale)
    kw_len = len(load_lexicon().get(best_family, [""])[0]) or 1
    start = base + max(0, best_off)
    return DocClassification(
        label=_family_label(best_family), family_guess=best_family, confidence=confidence,
        tier="lexicon", triggering_span=_mint(nt, start, start + kw_len, doc_id),
    )


def _title_block_tier(nt: NormalizedText, doc_id: str) -> DocClassification | None:
    """Classify from the first ~15 lines / ~1000 chars (D-28) — no TOC/heading markup assumed."""
    lines = nt.canonical.splitlines()
    head = "\n".join(lines[:_TITLE_BLOCK_LINES])[:_TITLE_BLOCK_CHARS]
    if not head.strip():
        return None
    return _regex_tier(nt, doc_id, text=head, base=0) or _lexicon_tier(nt, doc_id, text=head, base=0)


def _llm_tier(nt: NormalizedText, doc_id: str, model: str | None = None) -> DocClassification | None:
    """Cheap-model escalation via structured_call; skipped with no Databricks creds (ocr.py:78)."""
    s = get_settings()
    if not (s.databricks_host and s.databricks_token):
        return None  # no creds -> skip the LLM tier; the doc stays at its deterministic tier
    head = nt.canonical[:_TITLE_BLOCK_CHARS]
    messages = [
        {"role": "system",
         "content": "Classify the regulatory document by CONTENT into one CTD family. "
                    "Reply with a free-form label, the best-matching family id, and a 0-1 confidence.\n"
                    f"Families:\n{families_catalog_text()}"},
        {"role": "user", "content": head},
    ]
    instance, failure = structured_call(messages, ClassifyResult, model=model)
    if instance is None:
        return None  # ParseFailed -> caller keeps the deterministic guess (never a raw leak)
    return DocClassification(
        label=instance.label, family_guess=instance.family, confidence=instance.confidence,
        tier="llm", triggering_span=_mint(nt, 0, min(len(nt.canonical), len(head)), doc_id),
    )


def classify_document(
    nt: NormalizedText,
    outline: list | None = None,
    doc_id: str = "",
    model: str | None = None,
    stats: EscalationStats | None = None,
) -> DocClassification:
    """Classify a document by CONTENT (no path/filename, D-09). Never dropped, no threshold (D-02/D-03)."""
    result = (
        _regex_tier(nt, doc_id)
        or _title_block_tier(nt, doc_id)
        or _lexicon_tier(nt, doc_id)
    )
    if result is None:
        # non-CTD / no deterministic signal -> escalate to the LLM tier (D-07)
        result = _llm_tier(nt, doc_id, model=model)
    if result is None:
        # still nothing (non-CTD doc, or LLM skipped/failed): a first-class free-form label (D-01/D-02)
        first_line = next((ln.strip() for ln in nt.canonical.splitlines() if ln.strip()), "")
        result = DocClassification(
            label=first_line[:120], family_guess="", confidence=0.0, tier="none",
            triggering_span=_mint(nt, 0, min(len(nt.canonical), len(first_line[:120])), doc_id) if first_line else None,
        )
    if stats is not None:
        stats.record(result.tier)
    return result
