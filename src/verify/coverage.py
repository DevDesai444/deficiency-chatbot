"""The honest coverage report (VERIFY-02) + the consolidation-by-dedup-key helper.

A ``CoverageReport`` is the verifier layer's account of *what it reviewed and how it stood behind
each candidate* — deliberately NOT a pass/fail compliance verdict. It has three surfaces and NO
positive-pass field (the same ComplianceVerdict discipline that makes such a verdict unrepresentable
in ``schemas.faults``): a "no deficiencies found" result is expressed ONLY as ``reviewed_keep == []``
together with a ``could_not_locate`` list that names exactly what was searched-but-not-gradeable —
there is deliberately no positive "this submission passes" assertion anywhere.

``reviewed_downgrade`` is ALSO the audit trail for the Gap-1 assembly filter (``verify.assemble``):
every dedup_key recorded here was DOWNGRADEd by consensus, so it is excluded from the scored
``FaultReport.faults`` (its FP no longer counts) yet RETAINED here (nothing is silently dropped —
the β no-drop law: a downgrade changes which SURFACE a fault appears on, never its existence).

``consolidate`` groups Phase-5 Faults by ``Fault.dedup_key`` — MERGE, never drop. Summed group
member counts always equal the input length (asserted below), so a consolidation collision can
never silently discard a distinct candidate (T-07-08).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CoverageReport(BaseModel):
    """What the verifier reviewed — reviewed_keep / reviewed_downgrade / could_not_locate.

    There is NO positive-pass field, by design (ComplianceVerdict discipline): the report never
    asserts a submission passes, only what it reviewed. A "no deficiencies" outcome is
    ``reviewed_keep == [] AND could_not_locate`` enumerating precisely what was searched but not
    gradeable — an honest "here is what I could and could not stand behind", never a bare pass.
    """

    #: dedup_keys the panel affirmed (consensus KEEP) — surfaced ACTIVE in the scored report.
    reviewed_keep: list[str] = Field(default_factory=list)
    #: [{dedup_key, agreeing_verifiers: [model, ...]}] — DOWNGRADEd candidates live HERE and are
    #: excluded from the scored FaultReport.faults (Gap-1) but never dropped (still visible to the
    #: human + to the zero-TP-loss recall accounting).
    reviewed_downgrade: list[dict] = Field(default_factory=list)
    #: [{dedup_key, half: "source"|"rule", reason}] — a candidate whose source or rule could not be
    #: re-opened. Reviewed-but-not-gradeable: confidence NOT raised, candidate NOT dropped, and NOT
    #: a DOWNGRADE (so it stays ACTIVE in the scored report).
    could_not_locate: list[dict] = Field(default_factory=list)


class _CandidateGroup:
    """A consolidation group: a shared ``dedup_key`` + its merged member Faults (merge, never drop)."""

    def __init__(self, dedup_key: str):
        self.dedup_key = dedup_key
        self.members: list = []


def _fallback_key(candidate) -> str:
    """A never-None grouping key for a candidate lacking a ``dedup_key``.

    Prefer a submission-span-derived ``{doc_id}:{start}:null`` key (VERIFY-02 / RESEARCH). For an
    ABSENCE-family candidate (no submission_span_id) fall back to the absence anchor's claim span,
    then to a per-object identity key — so consolidation NEVER crashes and NEVER drops a candidate.
    """
    span = getattr(candidate, "submission_span_id", None)
    if span is not None:
        return f"{span.doc_id}:{span.start}:null"
    anchor = getattr(candidate, "absence_anchor", None)
    claim = getattr(anchor, "claim_span_id", None) if anchor is not None else None
    if claim is not None:
        req = getattr(anchor, "requirement_id", "req")
        return f"{claim.doc_id}:{claim.start}:{req}"
    return f"candidate:{id(candidate)}"


def consolidate(candidates: list) -> list:
    """Group candidates by ``Fault.dedup_key`` (VERIFY-02). MERGE, never drop.

    Two Faults with the same dedup_key land in one group (count preserved across members); distinct
    keys stay separate; a candidate with a None dedup_key falls back to a doc:start:null (or
    absence-anchor-derived) key. Returns a list of groups, each exposing ``.dedup_key`` + ``.members``.
    """
    groups: dict[str, _CandidateGroup] = {}
    for c in candidates:
        key = getattr(c, "dedup_key", None) or _fallback_key(c)
        groups.setdefault(key, _CandidateGroup(key)).members.append(c)  # MERGE, never drop
    # Invariant (T-07-08): consolidation preserves every candidate — no distinct one is discarded.
    assert sum(len(g.members) for g in groups.values()) == len(candidates)
    return list(groups.values())
