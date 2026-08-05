# Phase 4: Rulebook Enrichment + Absence Enumeration (β) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-05
**Phase:** 04-rulebook-enrichment-absence-enumeration
**Areas discussed:** Does-not-address test, Enrichment target + stop rule, Whole-section absence scope, Corpus-generality guard, Emit-gate contract for absences

**Scout finding that framed the discussion:** all `absence_of_evidence` ground truth in the eval corpora (mvr1381 ×11, MS-03) is requirement-LEVEL "claim/requirement present, supporting data absent" — none is whole-section. The 15-entry index (~all ICH Q2, family `3.2.S.4.3`) already has triggers shaped for this. Phase 2 built `enumerate_requirements`/`submission_profile`/`build_requirement_edges` (2 closure edges); the absence *consumer* does not exist yet.

---

## Does-not-address test (heart of RECALL-01)

| Question | Options | Selected |
|----------|---------|----------|
| Absence signal | Retrieval-threshold over-emit ✓ / Structural-only / Hybrid structural+retrieval | Retrieval-threshold over-emit |
| Precision posture | Over-emit; verifier prunes ✓ / Balanced in-phase | Over-emit; verifier prunes |
| Placement vs drive loop | Deterministic pre-loop pass ✓ / Agent-invoked tool | Deterministic pre-loop pass |
| What proves the negative | Rule span + manifest evidence (+claim span when present) ✓ / manifest-only / claim-only | Rule + manifest (+claim when present) |

**Notes:** Retrieval chosen because structural-only is blind to the eval's dominant "narrative claims X, no data table" pattern. Placement decision is the deliberate structural response to three consecutive Phase-3 drive-loop NO-GOs — recall is no longer the loop's job. → D-ABS1..4, D-THR.

---

## Enrichment target + stop rule (RULES-06)

| Question | Options | Selected |
|----------|---------|----------|
| Stop rule | Traceability floor + reviewer-general breadth ✓ / Traceability floor only / Broad reviewer-general | Traceability floor + reviewer-general breadth |
| Which rules | Decompose Q3A/Q3B/Q6A then add Q1 stability ✓ / Only decompose vendored / Eval-family-driven only | Decompose Q3A/Q3B/Q6A, then add Q1 |
| Coverage bar | Recorded metric ratcheted (no invented target) ✓ / Fixed target counts | Recorded metric, ratcheted |
| Authoring workflow | LLM-draft → code gate + traceability test → senior diff spot-check ✓ / Full entry-by-entry review | LLM-draft → gate → senior diff |

**Notes:** Q3A/Q3B/Q6A already vendored but under-indexed → highest coverage gain per effort. Q1 (stability) is a new vendoring task (date-pin, sha256, ICH copyright per chunk). Authoring scales via code gate + traceability test; senior reviews the versioned diff, not entry-by-entry. → D-ENR1..4.

---

## Whole-section (zero-document) absence scope

| Question | Options | Selected |
|----------|---------|----------|
| In scope? | In scope — expand closure edges ✓ / In scope but minimal / Defer to later phase | In scope — expand closure edges |
| False-absence guard | Profile-gated + over-emit candidate ✓ / Require corroborating cross-reference | Profile-gated + over-emit candidate |

**User's choice / notes:** In scope, expand `profile_requires_family` closure edges — **with the added constraint** that whole-section absence is validated by targeted OFF-eval composition tests (constructed corpus omits a required family → absence fires; omits a non-required family → nothing fires), since the main eval can't measure this class. Profile-gated + over-emit. → D-SEC1, D-SEC2.

---

## Corpus-generality guard (SC3)

| Question | Options | Selected |
|----------|---------|----------|
| Guard corpus | Held-out real + constructed omission fixtures ✓ / Held-out real only / Constructed only | Held-out real + constructed fixtures |
| Invariants | Three invariants ✓ / Rename-invariance + no-constant only | Three invariants |
| Enforcement | Automated CI test in harness ✓ / One-time phase-close audit | Automated CI test |

**User's choice / notes:** The held-out REAL witness **must be heldout32s41 (spec32s41), NOT mvr1381** — mvr1381 is the corpus recall is optimized/threshold-tuned against, so using it as the generality witness would be circular. Real generality has to be proven on a corpus never tuned on. Three invariants: no-constant, rename-invariance, same-logic transfer. → D-GEN1..3.

---

## Emit-gate contract for absences (Phase-2 ↔ Phase-4 integration boundary)

| Question | Options | Selected |
|----------|---------|----------|
| Gate shape | Absence-typed finding: byte-exact rule span + typed manifest-coverage anchor ✓ / Require submission anchor always / Null-sentinel span | Absence-typed finding + CoverageAbsenceAnchor |
| Re-open on absence side | Re-derivable, not a frozen assertion ✓ / Recorded snapshot | Re-derivable |

**Notes:** Surfaced during Area 1 as the integration boundary (D-EF1 demands dual byte-exact grounding, but never-mentioned / whole-section absences have no positive submission span). Rule half stays byte-exact; submission half becomes a typed `CoverageAbsenceAnchor` (enumerate inputs + sub-threshold retrieval hits) that a Phase-7 verifier deterministically re-runs. → D-GATE1, D-GATE2.

---

## Claude's Discretion

- Threshold-tuning mechanic for D-THR (absolute vs top-k gap vs relative) — bounded by "measured, recorded, ratcheted."
- `CoverageAbsenceAnchor` field layout / serialized shape.
- LLM-drafting prompt + batching for D-ENR4 (bounded by loader gate + traceability test).
- One code path vs two for requirement-level vs whole-section absence.
- Retrieval query construction from a requirement trigger (bounded by D-GEN2 no-constant).

## Deferred Ideas

- Rule-relevance judgment + adversarial verification of candidates → Phase 7 (VERIFY-01..04).
- Structural/cross-document recall → RECALL-02/03, Phase 5.
- Precedent-similarity recall → RECALL-04, Phase 5.
- Broad reviewer-general enrichment beyond Q1/Q3/Q6 (Q8–Q12, full CFR per-requirement) → later.
- Dynamic rulebook refresh → post-v1.
- Structural+retrieval hybrid absence signal → precision lever only if measured to help.
