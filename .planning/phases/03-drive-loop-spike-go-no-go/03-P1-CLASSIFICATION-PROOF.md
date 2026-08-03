# P1 Classification Proof

This proof discharges the P1 classification precondition for D-PRE1 and records the material verification-queue item 5 finding before any scored drive-loop run.

## Real Classification Results

Real `ingest_corpus` was run against a temporary corpus containing:

- `data/32s43-validation-related-compounds-method.pdf` (`mvr1381`)
- `data/32s41-Specification.pdf` (`spec32s41`)

The run used the production parser, normalizer, cache-entry writer, and content classifier, with manifest DB persistence disabled for the measurement. Both files parsed successfully and resolved at the deterministic regex tier.

| doc_id | source file | classified family / CTD section | label | tier | confidence | matches the D-RI1(2) fixture assumption? |
|---|---|---|---|---|---:|---|
| `mvr1381` | `data/32s43-validation-related-compounds-method.pdf` | `3.2.S.4.2` | Drug Substance Analytical Procedures | regex | 0.99 | no |
| `spec32s41` | `data/32s41-Specification.pdf` | `3.2.S.4.1` | Drug Substance Specification | regex | 0.99 | no |

Measured output:

```text
REAL_INGEST_CLASSIFICATION
spec32s41	32s41-Specification.pdf	doc_id=218cb269df8f4fc442d8df255632211b	status=parsed	family=3.2.S.4.1	label=Drug Substance Specification	tier=regex	confidence=0.99
mvr1381	32s43-validation-related-compounds-method.pdf	doc_id=ae0ca3bc994c6a3fe32f0593fabed6a6	status=parsed	family=3.2.S.4.2	label=Drug Substance Analytical Procedures	tier=regex	confidence=0.99

ENUMERATION_BY_REAL_FAMILY
spec32s41	family=3.2.S.4.1	count=2	targets_present=[]
mvr1381	family=3.2.S.4.2	count=0	targets_present=[]
```

## Requirement-Index Firing Under Real Families

Because the two real classified families differ, a destructive one-family move would only repair one document. The fix keeps the reviewed entry data intact and changes only the family linkage in `src/rulebook/requirement_index.py`: the two corrected-basis CFR entries now have supplemental `family_requires_requirement` edges for both measured real families. `REQUIREMENT_INDEX_VERSION` was bumped from `"3"` to `"4"`.

| requirement_id | citation unchanged? | rule_doc_id unchanged? | trigger unchanged? | before family linkage | after family linkage |
|---|---|---|---|---|---|
| `CFR-211160B-SOUND-BASIS` | yes | yes | yes | primary `3.2.S.5` only | primary `3.2.S.5`, plus real-family links `3.2.S.4.1` and `3.2.S.4.2` |
| `CFR-211194-CALCULATIONS` | yes | yes | yes | primary `3.2.S.5` only | primary `3.2.S.5`, plus real-family links `3.2.S.4.1` and `3.2.S.4.2` |

Targeted integration verification:

```text
.                                                                        [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 5 warnings in 172.96s (0:02:52)
sys:1: DeprecationWarning: builtin type swigvarlink has no __module__ attribute
```

## Verification-Queue Item 5

The existing boundary-crossing composition test passes on the committed rulebook fixture path:

```text
..                                                                       [100%]
=============================== warnings summary ===============================
<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute

<frozen importlib._bootstrap>:488
<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type SwigPyObject has no __module__ attribute

<frozen importlib._bootstrap>:488
  <frozen importlib._bootstrap>:488: DeprecationWarning: builtin type swigvarlink has no __module__ attribute

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
2 passed, 5 warnings in 41.62s
```

The independent production-store check required by this plan loaded the real requirement index, queried the real committed local rulebook store, and called `rulebook.store.lookup_citation(entry.citation)` for every authored `citation` string. The store contained 605 chunks at verification time.

| requirement_id | citation | lookup_citation result | resolved doc_id |
|---|---|---:|---|
| `Q2-SPECIFICITY` | `ICH Q2(R2) -- Glossary: Specificity/Selectivity` | NOT_FOUND | - |
| `Q2-LINEARITY` | `ICH Q2(R2) -- 3.2 Linearity` | NOT_FOUND | - |
| `Q2-DETECTION-LIMIT` | `ICH Q2(R2) -- Glossary: Detection Limit (DL)` | NOT_FOUND | - |
| `Q2-QUANTITATION-LIMIT` | `ICH Q2(R2) -- Glossary: Quantitation Limit (QL)` | NOT_FOUND | - |
| `Q2-PRECISION` | `ICH Q2(R2) -- Glossary: Precision` | NOT_FOUND | - |
| `Q2-ACCURACY` | `ICH Q2(R2) -- Glossary: Accuracy` | NOT_FOUND | - |
| `Q2-ROBUSTNESS` | `ICH Q2(R2) -- Glossary: Robustness` | NOT_FOUND | - |
| `Q2-SYSTEM-SUITABILITY` | `ICH Q2(R2) -- Glossary: System Suitability Test (SST)` | NOT_FOUND | - |
| `FDA-SOLUTION-STABILITY` | `FDA Guidance: Analytical Procedures and Methods Validation for Drugs and Biologics -- Section VII.F Standards Control Solution Preparation` | NOT_FOUND | - |
| `Q6A-WATER-CONTENT-TEST` | `ICH Q6A -- 3.3(e) Water Content` | NOT_FOUND | - |
| `CFR-211194-METHOD-IDENTIFICATION` | `21 CFR 211.194(a)(2)` | NOT_FOUND | - |
| `CFR-211160B-SOUND-BASIS` | `21 CFR 211.160(b)` | NOT_FOUND | - |
| `CFR-211194-CALCULATIONS` | `21 CFR 211.194(a)(5)` | NOT_FOUND | - |
| `Q3A-SPECIFIED-IMPURITY-COMPLETENESS` | `ICH Q3A(R2) -- Glossary: Specified Impurity` | NOT_FOUND | - |
| `CFR-211166-STABILITY-PROGRAM` | `21 CFR 211.166(a)` | NOT_FOUND | - |

Total: `0/15 resolved`.

## BLOCKER: verification-queue item 5 is NOT closed on real data

The composed `read_guideline(rule_doc_id)` path is green, but direct `lookup_citation(entry.citation)` on the authored requirement-index citation strings resolves `0/15` against the real local rulebook store. Under this plan's strict item-5 check, `absence_of_evidence` does not yet have a proven live path from requirement enumeration through rule fetch to `emit_finding`. A `0.0` on that family in the spike would be attributable to this rulebook citation-resolution gap rather than to the agent loop.

`git status --porcelain rulebook/manifest.yaml` reported ` M rulebook/manifest.yaml` before this task and after this task; the file was already dirty and was not staged or intentionally modified by this plan.
