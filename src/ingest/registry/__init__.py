"""Data-driven CTD-family registry (D-05) — the single source of truth for classification vocab.

Moves the CTD-family vocabulary out of the `CTDSection` Python enum into version-controlled
YAML so adding a family (Modules 1/2/4/5, biologics — v2) is a DATA edit, not a code change.
Registry ids EQUAL the `CTDSection` StrEnum values (migration-safety: existing consumers keyed
on those values keep matching — do NOT renumber). The `{id, label, applicability_trigger}` entry
shape mirrors Phase 2's RULES-05 requirement index; `body_lexicon.yaml` (D-06) holds the per-family
content keywords the deterministic classifier (Plan 08) scores over body text.

Entry point: `from ingest.registry import load_families, load_lexicon, family_ids`.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from schemas.documents import CTDSection

_DIR = Path(__file__).parent
_FAMILIES_PATH = _DIR / "ctd_families.yaml"
_LEXICON_PATH = _DIR / "body_lexicon.yaml"


@lru_cache(maxsize=1)
def load_families() -> list[dict]:
    """Return the CTD-family entries [{id, label, applicability_trigger}, ...] (cached)."""
    with open(_FAMILIES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


@lru_cache(maxsize=1)
def load_lexicon() -> dict[str, list[str]]:
    """Return the per-family body keyword lexicon {family_id: [keyword, ...]} (cached, D-06)."""
    with open(_LEXICON_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def family_ids() -> set[str]:
    """The set of all registry family ids (== a subset of CTDSection values)."""
    return {e["id"] for e in load_families()}


def families_catalog_text() -> str:
    """Render the registry for an LLM prompt, mirroring catalog.py domain_catalog_text() (Plan 08)."""
    return "\n".join(
        f"- {e['id']} ({e['label']}): {e['applicability_trigger']}" for e in load_families()
    )


_VALUE_TO_MEMBER = {s.value: s for s in CTDSection}


def as_ctd_section(family_id: str) -> CTDSection:
    """D-05 compat shim: map a registry id back to its CTDSection member (UNKNOWN if unmapped).

    Lets consumers that still type-annotate `CTDSection` interoperate with the registry.
    """
    return _VALUE_TO_MEMBER.get(family_id, CTDSection.UNKNOWN)
