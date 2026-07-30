"""Coverage-manifest schema (INGEST-03, D-30) — the declared per-document availability contract.

The manifest states, per document and UP FRONT, a typed status and three availability tiers so
downstream phases read capability from the manifest instead of discovering it at runtime (SC6):

  * canonical text + span-IDs are ALWAYS available for any document that parses at all;
  * the section OUTLINE (structure: outlined | flat) is best-effort — a flat/structureless doc
    still grounds, it just has no heading outline;
  * TABLE addressing (tables: addressable | unavailable) is best-effort — a scanned-table-lost or
    PDF-merge-ambiguous doc reports `unavailable` rather than appearing complete.

`parsed_partial` (D-17) mirrors ParseFailed's "isPartialView" ethos: a document that parsed but
DEGRADED carries, in its reason, exactly what degraded, so downstream grounding refuses to treat
it as complete evidence.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.documents import DocClassification, SpanID

# status vocabulary (D-16/D-17)
STATUSES = ("parsed", "parsed_partial", "parse_failed", "unsupported")
# availability tiers (D-30)
STRUCTURE_TIERS = ("outlined", "flat")
TABLE_TIERS = ("addressable", "unavailable")


class OutlineEntry(BaseModel):
    """One section-outline entry (D-04/D-18): identity is the span-ID; heading text is a LABEL only."""
    span: SpanID                 # section IDENTITY (content-addressed, D-18)
    label: str = ""              # human-readable heading text — a LABEL, never the identity (D-18)
    level: int = 0


class DocEntry(BaseModel):
    """One document's coverage row: status + reason + availability tiers + classification + outline."""
    doc_id: str
    filename: str
    content_hash: str
    status: str = "parsed"        # parsed | parsed_partial | parse_failed | unsupported (D-16/D-17)
    reason: str = ""              # for partial/failed/unsupported: WHAT degraded (D-17)
    structure: str = "flat"       # outlined | flat (D-30) — flat still grounds
    tables: str = "unavailable"   # addressable | unavailable (D-30)
    classification: DocClassification | None = None   # document-level classification (D-01/D-04)
    title: str = ""
    outline: list[OutlineEntry] = Field(default_factory=list)   # section outline stored in the index (D-04, SC3)
    normalizer_version: str = ""
    serializer_version: str = ""


class CoverageManifest(BaseModel):
    """The per-submission corpus coverage manifest (INGEST-03, SC3)."""
    documents: list[DocEntry] = Field(default_factory=list)
    escalation_rate: dict[str, float] = Field(default_factory=dict)   # per tier regex/lexicon/llm (D-27)
    counts: dict[str, int] = Field(default_factory=dict)              # per status
    created_at: str = ""
