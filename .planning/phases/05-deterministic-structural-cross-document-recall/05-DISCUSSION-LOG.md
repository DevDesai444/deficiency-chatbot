# Phase 5: Deterministic Structural & Cross-Document Recall (β) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 5-Deterministic Structural & Cross-Document Recall (β)
**Areas discussed:** Reference graph + contradictions (RECALL-03), Precedent candidate mechanic (RECALL-04), Anti-overfitting guard fixture (RECALL-05 guard), Shared candidate contract, Precedent index build scope

> **Note:** The structural pillar (RECALL-02) and RECALL-05 dynamic-range/index-persistence were LOCKED in a prior senior-reviewer pre-registration session (2026-08-06, recorded in STATE.md) and were NOT re-litigated in this session. This log covers only the areas discussed here.

---

## Reference graph + contradictions (RECALL-03)

| Option | Description | Selected |
|--------|-------------|----------|
| All three kinds | Hyperlinks + textual references + numeric value cross-refs | ✓ |
| Textual + numeric only | Skip hyperlink metadata | |
| Textual references only | Narrowest | |

| Option | Description | Selected |
|--------|-------------|----------|
| One ReferenceAnchor + anomaly enum | Single typed anchor, `{UNRESOLVED_REF, ABSENT_TARGET, VALUE_CONTRADICTION}` | ✓ |
| Distinct anchor per anomaly kind | Three types, three re-derivation paths | |
| Reuse StructuralAnchor for contradictions | Splits output across two anchor families | |

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit reference edge required | High precision, catches X1, may miss unlinked X2 | |
| Shared label/identifier match | Higher recall, label-collision FP risk | |
| Edge-required full + label-match low-confidence | Recall-safe without hard FPs | ✓ |

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse RECALL-02 engine identically | One comparison semantics, guard-clean | ✓ |
| Separate cross-doc comparator | Second tolerance policy to keep clean | |

| Option | Description | Selected |
|--------|-------------|----------|
| Consult coverage manifest first | Emit ABSENT_TARGET only when target present-but-missing-referent; else boundary/Phase 7 | ✓ |
| Emit ABSENT_TARGET on any failed resolution | FP from ingestion gaps | |

**User's choice:** All three edge kinds; one `ReferenceAnchor` + anomaly enum; edge-required contradictions full + label-match low-confidence; reuse RECALL-02 comparison engine; ABSENT_TARGET consults coverage manifest first.
**Notes:** Reuses `follow_reference` (same interface, replaces the pending stub) and `edges.py` provenance table.

---

## Precedent candidate mechanic (RECALL-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Section-level nearest-precedent | Per-section embed → nearest past-deficiency chunks | ✓ |
| Requirement/topic-driven | Leans on precedent taxonomy columns | |
| Whole-document similarity | Coarse, weak anchors | |

| Option | Description | Selected |
|--------|-------------|----------|
| Submission span anchors; precedent attached | Grounding on submission side (D-RB2(5)) | ✓ |
| Precedent span as co-anchor | Risks treating precedent as a finding source | |

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude same-ANDA + pattern-match only | Filter same ANDA#, match on pattern not verbatim; guard-tested | ✓ |
| Exclude same-ANDA only | Verbatim overlap could still leak | |
| No exclusion, rely on threshold | Highest leakage/overfitting risk | |

| Option | Description | Selected |
|--------|-------------|----------|
| Absolute dense-cosine, general threshold | Consistent with RECALL-05 dynamic range | ✓ |
| Top-k per section | Over-emits uniformly | |

**User's choice:** Section-level nearest-precedent; submission span anchors with precedent attached as evidence; exclude same-ANDA + pattern-match only; absolute dense-cosine general threshold.
**Notes:** `precedents.py` + `deficiency_kb.faiss` exist; no candidate tool registered yet. Generality (match OTHER submissions, no self-recognition) is the crux.

---

## Anti-overfitting guard fixture (RECALL-05 guard)

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic planted-deficiency fixture | Committable, license-clean, deterministic | ✓ |
| Reuse spec32s41 held-out witness | Real content, confidentiality reason it's gitignored | |
| Redacted real-submission subset | Redaction effort + residual risk | |

| Option | Description | Selected |
|--------|-------------|----------|
| All three in fast CI | SAME-LOGIC + THRESHOLD-TRANSFER + RENAME every build | ✓ |
| Fast SAME-LOGIC+RENAME; slow THRESHOLD-TRANSFER | Heavier invariant in slow lane | |

| Option | Description | Selected |
|--------|-------------|----------|
| Registered general-vocabulary allowlist | Declared registry; flag any other inline literal | ✓ |
| Type-based rejection only | A corpus-specific word in a list would slip through | |
| Manual reviewer sign-off per check | Not a code gate | |

**User's choice:** Synthetic planted-deficiency fixture (with four binding constraints); all three invariants in fast CI; registered general-vocabulary allowlist.
**Notes (user, verbatim intent):** The trap is authoring the fixture from the same mental model as the check code — planting exactly the deficiencies the code catches (this codebase's signature bug). Binding constraints: (1) planted deficiencies specified from rulebook/structural semantics, blind to the check implementation; (2) different surface forms than mvr1381 so RENAME/THRESHOLD-TRANSFER exercise transfer not recognition; (3) realistic enough that bge-m3 cosine lands in the real regime; (4) two-tier — synthetic fixture = every-build tripwire, real gitignored spec32s41 = slow-lane stronger witness.

---

## Shared candidate contract

| Option | Description | Selected |
|--------|-------------|----------|
| One grounded-candidate envelope | Union anchor + leg tag + confidence tier + dedup key | ✓ |
| Per-leg shapes | (not chosen) | |

**User's choice:** One envelope extending Phase-4's Fault + anchor pattern. Union anchor `{CoverageAbsenceAnchor | StructuralAnchor | ReferenceAnchor | PrecedentAnchor}`, leg tag `{ABSENCE, STRUCTURAL, REFERENCE, PRECEDENT}`, confidence tier (full/low), dedup key `(docId, sectionId, ruleId?)` with nullable ruleId, submission span always present + rule span only when a rule applies.
**Notes:** Uniform envelope ⇒ uniform Phase 7 verification + coverage reporting. Natural continuation of the contract, not a new abstraction.

---

## Precedent index build scope

| Option | Description | Selected |
|--------|-------------|----------|
| Static global asset, query-time exclusion, local-primary | Build once at reference-build time; ANDA# metadata filter; local FAISS | ✓ |
| (per-submission / rebuild-based) | (not chosen) | |

**User's choice:** Static GLOBAL reference asset built once (rebuilt only when the ANDA deficiency corpus changes); per-chunk ANDA# metadata so same-ANDA exclusion is a query-time filter; local FAISS (`deficiency_kb.faiss`) primary, Databricks mirror optional/serving-only so the guard fixture runs in stock CI without Databricks.
**Notes:** Also confirmed as already-decided: candidate consolidation = envelope dedup key + confidence-tier ordering + Phase 7 pruning; index persistence keys on the Phase-1 content hash.

---

## Claude's Discretion

- Exact module/file layout for the new legs (sibling packages to Phase-4 absence), internal decomposition, test structure — follow the Phase-4 pattern.
- Concrete reference-extraction regexes / hyperlink-metadata plumbing, provided they stay general and register any cue-word vocabulary in the guard allowlist.

## Deferred Ideas

- Semantic/interpretive cross-reference contradictions (X3/X5/X6) and any interpretation-judgment checks → Phase 7 interpretive tail (fails the pure-computation litmus).
- Prose value-pairing → Phase 7 (Phase 5 restricted to addressable table cells).
- Databricks mirror as a precedent query backend → optional/serving-only, not built in Phase 5.
- Cross-leg ranking beyond confidence-tier ordering → left to Phase 7 pruning.
