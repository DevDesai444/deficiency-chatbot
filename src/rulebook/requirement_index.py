"""The compact requirement index (RULES-05) -- what a submission MUST contain, enumerable
independent of what it does contain (the absence-of-evidence mechanism, D-RB4).

`load_requirement_index` is the D-RI1(1) loader gate: every entry's `family` must exist in the
D-05 registry and its `provenance_span_id` must re-open byte-exact against the REAL vendored
rulebook content (Plan 02-03) -- a mis-drafted entry fails at LOAD, not at review-time
attention. `enumerate_requirements` is the D-RI2 server-side applicability resolver: it answers
"what must THIS submission contain" from the manifest's content-derived profile via the UNION of
two generic-edge-table relations (D-RB4) -- the agent never asserts or invents what applies.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

import ingest.registry as registry
from ingest.anchors import open_span
from ingest.manifest import CoverageManifest
from rulebook import edges
from rulebook.store import rulebook_nt_for
from schemas.documents import SpanID
from tools.errors import ToolRejected

_PATH = Path(__file__).parent / "requirement_index.yaml"


class RequirementEntry(BaseModel):
    id: str
    family: str                  # must exist in ingest.registry.family_ids()
    citation: str                 # human-readable citation, e.g. "ICH Q2(R2) -- Specificity"
    trigger: str                   # one-line applicability trigger (D-05-mirrored shape)
    provenance_span_id: SpanID     # the rule span-ID that JUSTIFIES this entry (loader-gate enforced)


@lru_cache(maxsize=1)
def load_requirement_index(path: str | Path = _PATH) -> list[RequirementEntry]:
    """Load + validate every entry (D-RI1(1)): family must resolve in the D-05 registry, and
    provenance_span_id must re-open byte-exact against the rulebook store (via `rulebook_nt_for`
    + `open_span`) -- a mis-drafted entry raises here, never silently accepted.
    """
    raw = yaml.safe_load(Path(path).read_text()) or []
    entries = [RequirementEntry.model_validate(e) for e in raw]
    valid_families = registry.family_ids()
    for e in entries:
        if e.family not in valid_families:
            raise ValueError(f"{e.id}: family {e.family!r} not in the D-05 registry")
        nt = rulebook_nt_for(e.provenance_span_id.doc_id)
        if nt is None:
            raise ValueError(
                f"{e.id}: provenance doc_id {e.provenance_span_id.doc_id!r} not found in the rulebook store"
            )
        open_span(e.provenance_span_id, nt, e.provenance_span_id.doc_id)  # raises HashMismatch on drift
    return entries


def submission_profile(manifest: CoverageManifest) -> set[str]:
    """Content-derived (D-09 discipline: never path/folder-driven)."""
    families_present = {
        d.classification.family_guess
        for d in manifest.documents
        if d.classification and d.classification.family_guess
    }
    profiles: set[str] = set()
    if any(f.startswith("3.2.S") for f in families_present):
        profiles.add("drug_substance")
    if any(f.startswith("3.2.P") for f in families_present):
        profiles.add("drug_product")
    return profiles


def enumerate_requirements(
    manifest: CoverageManifest, family: str | None = None
) -> list[RequirementEntry] | ToolRejected:
    """D-RI2 enumerate mode: applicability resolved server-side from the manifest -- the agent
    asks "what applies here?" and never asserts/invents a profile or family (D-RI2(2)).
    """
    if family is not None and family not in registry.family_ids():
        return ToolRejected(
            tool="read_guideline",
            reason_code="family_not_in_registry",
            reason=f"{family!r} is not a registered CTD family",
            hint=f"use one of: {sorted(registry.family_ids())[:5]}...",
        )

    families_present = {
        d.classification.family_guess
        for d in manifest.documents
        if d.classification and d.classification.family_guess
    }
    # D-RB4 UNION: (a) families literally classified in the manifest, PLUS (b) families the
    # manifest's derived profile requires to exist at all (profile_requires_family) -- so a
    # family with ZERO classified documents can still surface a requirement (the absence
    # mechanism), not merely a direct .family filter over present documents.
    applicable_families = set(families_present)
    for profile_id in submission_profile(manifest):
        for _src, dst, _etype, _prov in edges.get_edges(src_id=profile_id, edge_type="profile_requires_family"):
            applicable_families.add(dst)

    entries_by_id = {e.id: e for e in load_requirement_index()}
    requirement_ids: set[str] = set()
    for fam in applicable_families:
        for _src, dst, _etype, _prov in edges.get_edges(src_id=fam, edge_type="family_requires_requirement"):
            requirement_ids.add(dst)

    result = [entries_by_id[rid] for rid in requirement_ids if rid in entries_by_id]
    if family is not None:
        result = [e for e in result if e.family == family]
    return sorted(result, key=lambda e: e.id)
