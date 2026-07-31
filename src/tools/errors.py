"""ToolRejected -- the typed, self-correcting rejection sentinel every tool in src/tools/
RETURNS (never raises) on a bad call. Mirrors schemas.llm.ParseFailed's sentinel shape, chosen
over ingest.anchors.HashMismatch's exception shape because a tool rejection must flow back to
the CALLING MODEL as a message, not unwind a Python call stack (RESEARCH.md Pattern 3).
"""
from __future__ import annotations

from pydantic import BaseModel


class ToolRejected(BaseModel):
    tool: str
    # Known reason codes (plain str, NOT a closed Literal -- later plans add codes without
    # editing this file): not_found | range_too_large | not_byte_exact |
    # not_retrieved_this_session | wrong_store | family_not_in_registry | no_rule_citation
    # NOTE: not_unique is deliberately excluded from this list. D-EF1's span-ID-only input
    # contract (see src/tools/emit_finding.py's module docstring) makes the classic "this quoted
    # text occurs in N places" ambiguity structurally unreachable -- a span-ID is a literal
    # {doc_id,start,end} offset range, never a text-pattern search (plan-checker Blocker 1).
    reason_code: str
    reason: str
    hint: str = ""
    # TOOLS-04 persist+preview+handle (plan-checker Blocker 2): populated on an oversized-range
    # rejection (reason_code="range_too_large") -- `preview` is a bounded, span-ID-annotated
    # string; `handle` is the re-openable key for a follow-up page-forward call. Both default to
    # "" for every OTHER rejection reason, where they don't apply.
    preview: str = ""
    handle: str = ""
