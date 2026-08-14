# labeled_fp_candidates.json — labeled false-positive / true-positive fixture

Phase 6's precision metric was mis-calibrated: only 2 of 115 candidates were known-false, so
end-to-end precision was not measurable. This fixture plants a balanced, **STRUCTURE-described**
set of candidates so the Gap-1 report-assembly filter test (Plan 03/04) can prove that:

- a DOWNGRADEd **FP** is NOT scored as an FP (precision rises), and
- a DOWNGRADEd **TP** is STILL counted as matched (zero TP loss).

## Shape

A JSON list of `{"fault": <Fault dict>, "label": "TP" | "FP", "why": "<STRUCTURE rationale>"}`.
Every `fault` is a `schemas.faults.Fault`-valid dict (validated at build time), pre-verification
`confidence_tier: "full"`, with a real `dedup_key`, `leg_tag`, and a re-openable
`submission_span_id` / `absence_anchor.claim_span_id` / `reference_anchor.src_span_id` so grounding
re-resolution can run on each one.

## Generality guard (RECALL-05 / T-07-01)

Each FP is a genuine false positive **by structure, not by corpus value** — no submission-specific
constant (batch no., doc name, spec value, section path) selects it. The `why` field on every
record names the STRUCTURE that makes it FP or TP:

| leg | FP structure | TP structure |
|-----|--------------|--------------|
| STRUCTURAL | a claimed aggregate mismatch whose recompute AGREES; a result-vs-limit that COMPLIES at stated precision | aggregate total below the largest tabulated single value; labeled max disagrees with recomputed max |
| ABSENCE | absence emitted for a requirement the doc demonstrably ADDRESSES (claim span proves presence) | a genuinely absent required justification / risk assessment |
| REFERENCE | an "unresolved reference" that in fact RESOLVES; a value cross-ref that AGREES once normalized | a reference whose target section is genuinely absent; a genuine cross-document value contradiction |

Coverage: >= 6 FP + >= 6 TP spanning ABSENCE / STRUCTURAL / REFERENCE so precision is not dominated
by one family. The values above are illustrative structures authored for this fixture — they are NOT
drawn from the eval corpus, so the RECALL-05 generality guard cannot flag a corpus-specific constant.
