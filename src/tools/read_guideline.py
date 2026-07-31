"""The 5th navigation tool -- dual-mode over the rulebook (D-RI2). One optional `citation`
param: omit for the compact enumerate surface (RULES-05), provide for bounded rule text
(RULES-01..04's content). Composes Plan 02-02's store + Plan 02-06's requirement index --
no new grounding/applicability logic lives here. An oversized fetch reuses Plan 02-01's
src/tools/oversized.py persist+preview+handle mechanism (plan-checker Blocker 2) rather than
a bare rejection.
"""
from __future__ import annotations

from ingest.anchors import mint_span
from ingest.manifest import CoverageManifest
from rulebook.requirement_index import enumerate_requirements
from rulebook.store import lookup_citation, rulebook_nt_for
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.oversized import advance_cursor, load_range, persist_range
from tools.textsplit import split_sentences


def read_guideline(
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    citation: str | None = None,
    family: str | None = None,
    handle: str | None = None,
    max_chars: int = 8000,
) -> list[dict] | str | ToolRejected:
    if handle is not None:
        return _resume_handle(handle, ledger, max_chars)
    if citation is None:
        result = enumerate_requirements(manifest, family=family)
        if isinstance(result, ToolRejected):
            return result
        return [{"requirement_id": e.id, "citation": e.citation, "trigger": e.trigger} for e in result]
    return _fetch_citation(citation, ledger, max_chars)


def _fetch_citation(citation: str, ledger: RetrievalLedger, max_chars: int) -> str | ToolRejected:
    """Implemented in Task 2 of this plan (includes the TOOLS-04 persist+preview+handle
    oversized branch, plan-checker Blocker 2)."""
    raise NotImplementedError


def _resume_handle(handle: str, ledger: RetrievalLedger, max_chars: int) -> str | ToolRejected:
    """Implemented in Task 2 of this plan -- mirrors get_section's handle branch (Plan 02-01)
    exactly, applied to the rulebook store instead of the corpus store."""
    raise NotImplementedError
