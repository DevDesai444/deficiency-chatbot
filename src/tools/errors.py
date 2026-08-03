"""ToolRejected -- the typed, self-correcting rejection sentinel every tool in src/tools/
RETURNS (never raises) on a bad call. Mirrors schemas.llm.ParseFailed's sentinel shape, chosen
over ingest.anchors.HashMismatch's exception shape because a tool rejection must flow back to
the CALLING MODEL as a message, not unwind a Python call stack (RESEARCH.md Pattern 3).
"""
from __future__ import annotations

from typing import Literal

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
    # D-TEL3: WHICH half of the dual citation failed. Populated by emit_finding only; every
    # other tool leaves it "". Telemetry groups by (reason_code, half) because the two halves
    # are OPPOSITE diagnoses and must never be summed into one "rejections" count:
    #   half="submission" + not_byte_exact          => SPAN INVENTION (grounding-discipline failure)
    #   half="rule"       + not_retrieved_this_session => NEVER CALLED read_guideline (loop-behavior failure)
    # Different remedies (swap the model vs. fix the loop), hence separate reporting.
    half: Literal["submission", "rule", ""] = ""
    # TOOLS-04 persist+preview+handle (plan-checker Blocker 2): populated on an oversized-range
    # rejection (reason_code="range_too_large") -- `preview` is a bounded, span-ID-annotated
    # string; `handle` is the re-openable key for a follow-up page-forward call. Both default to
    # "" for every OTHER rejection reason, where they don't apply.
    preview: str = ""
    handle: str = ""


# D-TEL2: the OPEN registry telemetry joins against. `reason_code` on ToolRejected stays a plain
# `str` (see above) so later plans add codes without editing this file's model; this mapping is
# the human-readable index of the ones we know about. A code absent from here is NOT an error --
# telemetry buckets it under "unrecognized" and the run summary flags it loudly, which is how a
# newly-added code announces itself instead of silently disappearing into a total.
# A telemetry-side COPY of this mapping is forbidden (RESEARCH.md Anti-Patterns): it would drift
# from the gate and mislabel the single most diagnostic signal the spike produces.
KNOWN_REASON_CODES: dict[str, str] = {
    "not_found": "The requested document, heading, handle or citation does not exist.",
    "range_too_large": "The requested span exceeds max_chars; a preview and a page-forward handle are supplied.",
    "not_byte_exact": "The cited span did not re-open byte-for-byte (hash mismatch).",
    "not_retrieved_this_session": "The cited span-ID was never issued to the model this session.",
    "wrong_store": "The span-ID resolved in the wrong store (submission span in the rulebook, or vice versa).",
    "family_not_in_registry": "The requested requirement family is not present in the requirement index.",
    "no_rule_citation": "emit_finding was called without a rule span-ID or rule citation.",
}
