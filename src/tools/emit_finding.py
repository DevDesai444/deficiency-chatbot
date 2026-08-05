"""The grounding gate (TOOLS-03, D-EF1) -- the ONLY path by which a Fault can exist.

Re-opens BOTH the submission quote and the cited rule clause via ingest.anchors.open_span
(never reimplemented), validates both span-IDs were actually issued THIS session (the
ledger -- D-GRAN selection-not-authoring), validates store membership (a rule span must
resolve in the RULEBOOK store, a submission span in the CORPUS store), and ONLY THEN
constructs a Fault. Every failure is a typed ToolRejected, never a raised exception.

Note on TOOLS-03/SC5's "not unique" rejection condition (plan-checker Blocker 1): under
D-EF1's span-ID-only input contract (never retyped text, D-GRAN selection-not-authoring), a
finding's evidence is a {doc_id,start,end}+hash -- a literal offset range, not a text
pattern. The classic "this quoted text occurs in N places, which one?" ambiguity the
"not_unique" reason_code was written to guard against is structurally UNREACHABLE here: a
span-ID always resolves to exactly the ONE location its own (start,end) names, never to a
substring SEARCH that could match multiple places (D-GRAN: "issued IDs are unique by
construction, which simplifies the gate's uniqueness check"). No reason_code="not_unique"
path exists below for that reason -- see tests/tools/test_emit_finding.py::
test_span_id_unique_by_construction for the proof.

Note on `rulebook_cache_dir`: rulebook.store.rulebook_nt_for reads from a cache_dir argument
(default rulebook.store.DEFAULT_RULEBOOK_CACHE_DIR) exactly like every other rulebook.store
consumer (see tests/rulebook/test_store.py, which threads an explicit tmp_path-scoped
cache_dir through every call for D-RB6 offline test isolation). emit_finding threads the same
parameter through so its own tests can resolve a rule span against an isolated fixture store
instead of the shared data/ directory -- the CORPUS half gets this for free because
CorpusIndex already carries its own cache_dir instance field (ingest/corpus.py); the RULEBOOK
half is a module-level store, so the same isolation has to be an explicit parameter here.
"""
from __future__ import annotations

from ingest.anchors import HashMismatch, open_span
from ingest.corpus import CorpusIndex
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR, rulebook_nt_for
from schemas.documents import NormalizedText, OffsetRun, SpanID
from schemas.faults import ComplianceVerdict, CoverageAbsenceAnchor, EvidenceClass, Fault, Tier
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger


def emit_finding(
    corpus: CorpusIndex,
    submission_span_id: SpanID,
    rule_span_id: SpanID | None,
    ledger: RetrievalLedger,
    verdict: str,
    requirement_id: str = "",
    rule_citation: str = "",
    title: str = "",
    detail: str = "",
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
) -> Fault | ToolRejected:
    try:
        compliance_verdict = ComplianceVerdict(verdict)
    except ValueError:
        return ToolRejected(
            tool="emit_finding", reason_code="invalid_verdict", half="",
            reason=f"verdict must be one of {[m.value for m in ComplianceVerdict]}",
            hint="re-call emit_finding with verdict set to violation, gap or ambiguous",
        )

    if rule_span_id is None:
        return ToolRejected(tool="emit_finding", reason_code="no_rule_citation",
                            half="rule",
                            reason="a finding must cite a specific rule clause span, none was provided",
                            hint="call read_guideline first, then pass its returned rule span-ID as rule_span_id")

    if not ledger.was_issued(submission_span_id):
        return ToolRejected(tool="emit_finding", reason_code="not_retrieved_this_session",
                            half="submission",
                            reason="submission_span_id was never actually retrieved this session",
                            hint="re-fetch via get_section/search_corpus, then cite the span-ID it returns")
    if not ledger.was_issued(rule_span_id):
        return ToolRejected(tool="emit_finding", reason_code="not_retrieved_this_session",
                            half="rule",
                            reason="rule_span_id was never actually retrieved this session",
                            hint="re-fetch via read_guideline, then cite the span-ID it returns")

    corpus_cache = corpus.cached_entry(submission_span_id.doc_id)
    if corpus_cache is None:
        return ToolRejected(tool="emit_finding", reason_code="wrong_store",
                            half="submission",
                            reason=f"submission_span_id.doc_id={submission_span_id.doc_id!r} does not resolve in the CORPUS store",
                            hint="submission_span_id must come from get_section/search_corpus over THIS corpus")
    rule_nt = rulebook_nt_for(rule_span_id.doc_id, cache_dir=rulebook_cache_dir)
    if rule_nt is None:
        return ToolRejected(tool="emit_finding", reason_code="wrong_store",
                            half="rule",
                            reason=f"rule_span_id.doc_id={rule_span_id.doc_id!r} does not resolve in the RULEBOOK store",
                            hint="rule_span_id must come from read_guideline, not get_section")

    submission_nt = NormalizedText(canonical=corpus_cache["canonical"], raw_serialized=corpus_cache["raw_serialized"],
                                   offset_map=[OffsetRun.model_validate(r) for r in corpus_cache["offset_map"]],
                                   normalizer_version=corpus_cache["normalizer_version"], serializer_version=corpus_cache["serializer_version"])

    try:
        submission_raw, _ = open_span(submission_span_id, submission_nt, submission_span_id.doc_id)
    except HashMismatch:
        return ToolRejected(tool="emit_finding", reason_code="not_byte_exact",
                            half="submission",
                            reason="submission_span_id no longer re-opens byte-exact against the corpus store",
                            hint="re-fetch the current text via get_section and cite its freshly-issued span-ID")
    try:
        rule_raw, _ = open_span(rule_span_id, rule_nt, rule_span_id.doc_id)
    except HashMismatch:
        return ToolRejected(tool="emit_finding", reason_code="not_byte_exact",
                            half="rule",
                            reason="rule_span_id no longer re-opens byte-exact against the rulebook store",
                            hint="re-fetch the current rule text via read_guideline and cite its freshly-issued span-ID")

    # Phase 2 has no compliance-verdict CLASSIFICATION logic yet (DETECT-04 lands in Phase 3) --
    # `verdict` is accepted per D-EF1's finding schema {submission_span_id, rule_span_id, verdict...}
    # and threaded into `detail` for now rather than a dedicated Fault field (none exists on the
    # unmodified schemas.faults.Fault); Phase 3 owns any future verdict-specific field/logic.
    detail_with_verdict = f"{detail} [verdict: {verdict}]".strip() if verdict else detail

    # KNOWN LIMITATION (plan-checker Warning 2, D-EF1(5)): D-EF1(5) says the finding "carries
    # BOTH rule_span_id (grounding) and requirement_id/citation (metadata)". schemas.faults.Fault
    # is OFF-LIMITS this phase and has no field for a structured SpanID -- only
    # guidance_refs: list[str]. Accepted interpretation: D-EF1(5) is an INPUT-VALIDATION
    # requirement (the emit_finding CALL carries rule_span_id, and THIS gate re-opens + validates
    # it via was_issued/open_span above BEFORE a Fault can exist at all), not an OUTPUT-STORAGE
    # promise. rule_span_id's grounding proof is fully spent by the time this Fault is
    # constructed; only its human-readable citation string survives into guidance_refs. If a
    # later phase (Phase 5's verifier) needs to re-open the EXACT rule span a Fault cites, that
    # requires either a Fault schema change (schemas/faults.py, currently off-limits) or a
    # side-channel span store -- do not treat guidance_refs' string-only shape as a regression
    # introduced here; it is this phase's accepted, schema-constrained boundary.
    return Fault(
        title=title or "Deficiency", detail=detail_with_verdict,
        tier=Tier.CORROBORATED, evidence_class=EvidenceClass.QUOTE_ANCHORED, confidence=0.7,
        verdict=compliance_verdict, rule_span_id=rule_span_id, submission_span_id=submission_span_id,
        evidence=submission_raw, source="tool:emit_finding",
        guidance_refs=[rule_citation or rule_span_id.doc_id] + ([requirement_id] if requirement_id else []),
    )


def emit_absence_finding(
    corpus: CorpusIndex,
    rule_span_id: SpanID | None,
    absence_anchor: CoverageAbsenceAnchor,
    ledger: RetrievalLedger,
    requirement_id: str = "",
    rule_citation: str = "",
    title: str = "",
    detail: str = "",
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR,
) -> Fault | ToolRejected:
    """The absence-typed grounding gate (D-GATE1/D-GATE2) -- the ONLY path by which an
    absence-typed Fault can exist.

    An absence finding (a never-mentioned or whole-section absence) has no single submission text
    span, so its submission half is a typed `CoverageAbsenceAnchor` (the enumerate inputs +
    sub-threshold retrieval hits + manifest span-IDs) rather than a `submission_span_id`. The RULE
    half stays byte-exact and UNCHANGED from `emit_finding` (D-EF1): it is re-opened via
    `open_span`, validated as issued THIS session (ledger), and validated to resolve in the
    RULEBOOK store. When the anchor additionally carries a narrative-claim CORPUS span (D-ABS4 /
    mvr / MS-03), that span is re-opened byte-exact via the SAME `corpus.cached_entry` + `open_span`
    path `emit_finding` uses. The gate also proves the negative is RE-DERIVABLE (D-GATE2): an
    anchor missing the enumerate inputs (family / requirement_id) needed to re-run the search is
    rejected as `unanchored_absence`. Every failure is a typed `ToolRejected`, never a raised
    exception. Absence findings carry the existing `ComplianceVerdict.GAP` -- no new verdict.
    """
    # --- 1. RULE half: byte-exact and UNCHANGED (D-EF1) --------------------------------------
    if rule_span_id is None:
        return ToolRejected(tool="emit_absence_finding", reason_code="no_rule_citation",
                            half="rule",
                            reason="an absence finding must cite a specific rule clause span, none was provided",
                            hint="call read_guideline first, then pass its returned rule span-ID as rule_span_id")

    if not ledger.was_issued(rule_span_id):
        return ToolRejected(tool="emit_absence_finding", reason_code="not_retrieved_this_session",
                            half="rule",
                            reason="rule_span_id was never actually retrieved this session",
                            hint="re-fetch via read_guideline, then cite the span-ID it returns")

    rule_nt = rulebook_nt_for(rule_span_id.doc_id, cache_dir=rulebook_cache_dir)
    if rule_nt is None:
        return ToolRejected(tool="emit_absence_finding", reason_code="wrong_store",
                            half="rule",
                            reason=f"rule_span_id.doc_id={rule_span_id.doc_id!r} does not resolve in the RULEBOOK store",
                            hint="rule_span_id must come from read_guideline, not get_section")

    try:
        open_span(rule_span_id, rule_nt, rule_span_id.doc_id)
    except HashMismatch:
        return ToolRejected(tool="emit_absence_finding", reason_code="not_byte_exact",
                            half="rule",
                            reason="rule_span_id no longer re-opens byte-exact against the rulebook store",
                            hint="re-fetch the current rule text via read_guideline and cite its freshly-issued span-ID")

    # --- 2. Optional narrative-claim CORPUS span (D-ABS4): re-open byte-exact, SAME path -----
    claim_span_id = absence_anchor.claim_span_id
    if claim_span_id is not None:
        if not ledger.was_issued(claim_span_id):
            return ToolRejected(tool="emit_absence_finding", reason_code="not_retrieved_this_session",
                                half="submission",
                                reason="the narrative-claim span was never actually retrieved this session",
                                hint="re-fetch via search_corpus/get_section, then cite the span-ID it returns")
        corpus_cache = corpus.cached_entry(claim_span_id.doc_id)
        if corpus_cache is None:
            return ToolRejected(tool="emit_absence_finding", reason_code="wrong_store",
                                half="submission",
                                reason=f"claim_span_id.doc_id={claim_span_id.doc_id!r} does not resolve in the CORPUS store",
                                hint="the claim span must come from search_corpus/get_section over THIS corpus")
        claim_nt = NormalizedText(canonical=corpus_cache["canonical"], raw_serialized=corpus_cache["raw_serialized"],
                                  offset_map=[OffsetRun.model_validate(r) for r in corpus_cache["offset_map"]],
                                  normalizer_version=corpus_cache["normalizer_version"], serializer_version=corpus_cache["serializer_version"])
        try:
            open_span(claim_span_id, claim_nt, claim_span_id.doc_id)
        except HashMismatch:
            return ToolRejected(tool="emit_absence_finding", reason_code="not_byte_exact",
                                half="submission",
                                reason="the narrative-claim span no longer re-opens byte-exact against the corpus store",
                                hint="re-fetch the current text via search_corpus/get_section and cite its freshly-issued span-ID")

    # --- 3. The negative must be RE-DERIVABLE (D-GATE2) --------------------------------------
    if absence_anchor.requirement_id == "" or absence_anchor.family == "":
        return ToolRejected(tool="emit_absence_finding", reason_code="unanchored_absence",
                            half="submission",
                            reason="absence anchor missing enumerate inputs required to re-run the negative",
                            hint="populate CoverageAbsenceAnchor.family and .requirement_id so the verifier can RE-RUN the search")

    # --- 4. Construct the absence-typed Fault (GAP; no submission_span_id) -------------------
    return Fault(
        title=title or "Absent required element", detail=detail,
        tier=Tier.CORROBORATED, evidence_class=EvidenceClass.CHECKLIST, confidence=0.7,
        verdict=ComplianceVerdict.GAP, rule_span_id=rule_span_id, submission_span_id=None,
        absence_anchor=absence_anchor, source="tool:emit_absence_finding",
        guidance_refs=[rule_citation or rule_span_id.doc_id] + ([requirement_id] if requirement_id else []),
    )
