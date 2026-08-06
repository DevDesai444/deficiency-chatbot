"""The deterministic absence pass (RECALL-01, D-ABS1/D-ABS3) -- the structural answer to three
consecutive Phase-3 drive-cycle NO-GOs: recall is NO LONGER the agentic driver's responsibility.

`enumerate_absences` is a PURE FUNCTION over `(corpus, manifest, ledger, threshold)` -- NOT a
drive-cycle tool, NOT gated on the agentic driver (D-ABS3). It composes three verified analogs:

    enumerate_requirements   (applicability -- rulebook.requirement_index, NEVER reinvented)
        ->  search_corpus     (retrieval-threshold query per requirement trigger)
        ->  emit_absence_finding  (the byte-exact grounding gate -- Plan 04-02)

For each applicable requirement, it queries the ephemeral submission index with the requirement's
own `trigger` (rulebook text, NEVER a corpus literal -- D-GEN2 no-constant). When the top-hit
score falls below the recorded threshold, it OVER-EMITS an absence candidate (D-ABS2: no precision
cutoff in the recall layer -- Phase 7's verifier prunes). A required family with ZERO classified
documents fires whole-section absence, profile-gated so a family no active profile requires never
fires (D-SEC1/D-SEC2). Every candidate emits through `emit_absence_finding`, so the rule half is
byte-exact and the `CoverageAbsenceAnchor` is re-derivable (D-GATE1/D-GATE2).

The threshold is NEVER a code constant here (D-THR): it is passed in by the caller, which reads it
from the committed `src/evals/baseline/absence_threshold.json`.
"""
from __future__ import annotations

from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from rulebook import edges
from rulebook.requirement_index import (
    RequirementEntry,
    enumerate_requirements,
    submission_profile,
)
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.documents import SpanID
from schemas.faults import CoverageAbsenceAnchor, Fault, RetrievalHit
from tools.emit_finding import emit_absence_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.search_corpus import search_corpus


def _manifest_span_ids(manifest: CoverageManifest, family: str | None = None) -> list[SpanID]:
    """Manifest span-IDs proving the search space enumerated (D-GATE2).

    Collects each classified document's outline span-IDs so the anchor records WHAT was searched.
    When `family` is given, restricts to documents classified into that family (whole-section /
    requirement-family scoping); when None, includes every classified document. These spans are
    informational evidence of the search space -- the emit gate does not re-open them, so an empty
    list is valid (e.g. a whole-section zero-document family has no documents to point at).
    """
    span_ids: list[SpanID] = []
    for doc in manifest.documents:
        fam = doc.classification.family_guess if doc.classification else None
        if family is not None and fam != family:
            continue
        for entry in doc.outline:
            span_ids.append(entry.span)
    return span_ids


def _emit_candidate(
    corpus: CorpusIndex,
    entry: RequirementEntry,
    anchor: CoverageAbsenceAnchor,
    ledger: RetrievalLedger,
    rulebook_cache_dir: str,
    title: str,
) -> Fault | None:
    """Record the rule span in the ledger, then emit through the byte-exact gate (D-GATE1).

    The requirement entry's `provenance_span_id` is loader-gate-guaranteed to re-open byte-exact in
    the rulebook store; recording it in the ledger is what lets the emit gate's `was_issued` pass on
    the RULE half. A `ToolRejected` is telemetried by being skipped (returns None), never raised and
    never emitted as a Fault (D-GATE1 -- only grounded candidates survive).
    """
    ledger.record_span(entry.provenance_span_id)
    result = emit_absence_finding(
        corpus,
        entry.provenance_span_id,
        anchor,
        ledger,
        requirement_id=entry.id,
        rule_citation=entry.citation,
        title=title,
        rulebook_cache_dir=rulebook_cache_dir,
    )
    return result if isinstance(result, Fault) else None


def enumerate_absences(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    threshold: float,
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
    top_k: int = 10,
) -> list[Fault]:
    """Deterministic pre-cycle absence pass (D-ABS1/D-ABS3): applicability -> retrieval-threshold
    over-emit -> byte-exact grounding gate. Returns every grounded absence Fault (verdict GAP).

    Two complementary candidate sources, one deterministic pass (D-ABS3):
      1. REQUIREMENT-LEVEL (D-ABS1): every applicable requirement whose `trigger` retrieves nothing
         above `threshold` is over-emitted (D-ABS2).
      2. WHOLE-SECTION (D-SEC1/D-SEC2): every requirement in a profile-required family that has ZERO
         classified documents is over-emitted, profile-gated so a non-required family never fires.
    """
    applicable = enumerate_requirements(manifest)
    if isinstance(applicable, ToolRejected):
        # family_not_in_registry (or similar) -- propagate as "nothing to enumerate", never raise.
        return []

    profiles = sorted(submission_profile(manifest))
    families_present = {
        d.classification.family_guess
        for d in manifest.documents
        if d.classification and d.classification.family_guess
    }

    faults: list[Fault] = []
    # Track (family, requirement_id) already emitted so a requirement that is BOTH sub-threshold and
    # in a zero-document family is not double-counted across the two candidate sources.
    emitted_keys: set[tuple[str, str]] = set()
    entries_by_id = {e.id: e for e in applicable}

    # --- 1. REQUIREMENT-LEVEL (D-ABS1): retrieval-threshold over-emit -------------------------
    for entry in applicable:
        hits = search_corpus(corpus, entry.trigger, ledger, top_k=top_k)
        top_score = hits[0]["score"] if hits else 0.0
        if top_score >= threshold:
            continue  # the search-and-found path: strong evidence, NOT an absence.

        sub_threshold_hits = [
            RetrievalHit(span_id=SpanID(**h["span_id"]), score=h["score"]) for h in hits
        ]
        # D-ABS4: if the strongest near-miss hit reads like an unsupported narrative claim, cite its
        # ledger-issued CORPUS span -- the emit gate re-opens it byte-exact. We attach the top hit's
        # span (already recorded by search_corpus, so was_issued passes) as the claim span when a hit
        # exists; the gate rejects it only if it drifted, which cannot happen for a just-issued span.
        claim_span_id = SpanID(**hits[0]["span_id"]) if hits else None
        anchor = CoverageAbsenceAnchor(
            profile=profiles,
            family=entry.family,
            requirement_id=entry.id,
            threshold=threshold,
            sub_threshold_hits=sub_threshold_hits,
            manifest_span_ids=_manifest_span_ids(manifest),
            claim_span_id=claim_span_id,
        )
        fault = _emit_candidate(
            corpus,
            entry,
            anchor,
            ledger,
            rulebook_cache_dir,
            title=f"Required item not addressed: {entry.citation}",
        )
        if fault is not None:
            faults.append(fault)
            emitted_keys.add((entry.family, entry.id))

    # --- 2. WHOLE-SECTION (D-SEC1/D-SEC2): profile-required family with zero documents ---------
    for profile_id in profiles:
        for _src, dst_family, _etype, _prov in edges.get_edges(
            src_id=profile_id, edge_type="profile_requires_family"
        ):
            if dst_family in families_present:
                continue  # the family HAS documents -- requirement-level pass covers it, not whole-section.
            # Zero classified documents in a profile-required family: every requirement in it is
            # unaddressed. Emit one whole-section candidate per requirement in that family.
            for entry in (e for e in entries_by_id.values() if e.family == dst_family):
                if (entry.family, entry.id) in emitted_keys:
                    continue
                anchor = CoverageAbsenceAnchor(
                    profile=profiles,
                    family=dst_family,
                    requirement_id=entry.id,
                    threshold=threshold,
                    sub_threshold_hits=[],
                    manifest_span_ids=_manifest_span_ids(manifest, family=dst_family),
                    claim_span_id=None,
                )
                fault = _emit_candidate(
                    corpus,
                    entry,
                    anchor,
                    ledger,
                    rulebook_cache_dir,
                    title=f"Entire required section absent ({dst_family}): {entry.citation}",
                )
                if fault is not None:
                    faults.append(fault)
                    emitted_keys.add((entry.family, entry.id))

    return faults
