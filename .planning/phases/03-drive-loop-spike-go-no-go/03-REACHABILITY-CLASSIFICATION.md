# Phase 03 Reachability Classification (D-GO4, amended for the third bucket)

This document pre-classifies **every scored ground-truth item** into exactly one of
three reachability buckets **before any agent run exists**. D-GO4 originally asked for
two buckets; the measurement-instrument analysis found a third (matcher-unreachable),
so the split is three-way. Committed together with `03-GO-NOGO-PREREGISTRATION.md`.

Scored documents (from `src/evals/dataset/documents.json`): `mvr1381` (`held_out=false`)
and `minispec` (`held_out=false`). `spec32s41` is `held_out=true` — **excluded from
scoring** and not classified here except for the held-out zero-token note below.

**Total classified: 32 scored items = 28 `mvr1381` + 4 `minispec`.**

## The three buckets

1. **matcher-unreachable** — the GT `evidence_anchor` yields **zero** matchable tokens
   under `match.py`'s `_TOKEN_RE = [0-9][0-9./]{3,}` (>=4 chars) and
   `_WORD_RE = [a-z]{6,}` (>=6 letters) (`match.py:27-28`), so `matches()` returns
   `False` unconditionally at `match.py:89-90` (`if not tokens: return False`).
   **Unreachable for any system, this phase or later** — this is a property of the
   scoring instrument, not of the loop. The 4-char / 6-letter floors are a deliberate,
   documented choice (`match.py:19-26`): a 3-char floor let a bare `"0.5"` false-match
   an unrelated GT item. **The matcher is not modified** (changing it is a harness
   change that voids the D-GO1(iii) comparison).

2. **single-agent-scope-unreachable** — finding the item requires resolving a reference
   into a **different submission document**, where `follow_reference` returns the typed
   `cross_document_resolution_pending_phase_4` sentinel (`follow_reference.py:18,26,39`).
   This is a **capability boundary**, not a difficulty judgment — D-GO4(a)'s named
   category, whose named next step is Phase 4's reference graph.

3. **reachable** — everything else: single-document items whose anchor tokenizes to at
   least one matchable token and whose evidence lives inside the scored document itself.
   This is the set D-GO4(a) tests *"was every structurally-reachable item found?"* against.

## (a) Empirical matcher-unreachable verification (replay, not table-trust)

Per Task 1(a), the matcher-unreachable set was verified by **replaying `match.py`'s own
`_anchor_tokens()`** over every GT anchor in the committed dataset, not by copying a
table. Command:

```
PYTHONPATH=src .venv/bin/python -c "import json; from evals.match import _anchor_tokens; \
[print(it['id'], repr(it['evidence_anchor']), _anchor_tokens(it['evidence_anchor'])) \
for it in json.load(open('src/evals/dataset/mvr1381.deficiencies.json'))]"
```

Full per-item token replay for `mvr1381` (empty token list ⇒ bucket 1):

| id | anchor | replayed tokens |
|---|---|---|
| A-01 | `'99.9%'` | `['99.9']` |
| A-02 | `'13439'` | `['13439']` |
| A-03 | `'control sample'` | `['control', 'sample']` |
| A-04 | `'degradants'` | `['degradants']` |
| A-05 | `'377.49'` | `['377.49']` |
| A-06 | `'Co-relation Coefficient'` | `['relation', 'coefficient']` |
| **A-07** | `'0.5%'` | **`[]`** |
| A-08 | `'specification level'` | `['specification']` |
| A-09 | `'<1226>'` | `['1226']` |
| A-10 | `'0.92%'` | `['0.92']` |
| A-11 | `'current in-house SOP'` | `['current']` |
| A-12 | `'05/10/2016'` | `['05/10/2016']` |
| B-01 | `'10%LOD-LOQLevel'` | `['loqlevel']` |
| B-02 | `'standard deviation of the response'` | `['standard', 'deviation', 'response']` |
| **B-03** | `'389'` | **`[]`** |
| B-04 | `'6559.876'` | `['6559.876']` |
| B-05 | `'27.0%'` | `['27.0']` |
| **B-06** | `'485'` | **`[]`** |
| B-07 | `'9.83'` | `['9.83']` |
| B-08 | `'Any Unspecified Impurity'` | `['unspecified', 'impurity']` |
| C-01 | `'11477'` | `['11477']` |
| C-02 | `'0.15'` | `['0.15']` |
| **C-03** | `'ND'` | **`[]`** |
| C-04 | `'0.14'` | `['0.14']` |
| C-05 | `'room temperature'` | `['temperature']` |
| C-06 | `'Absorptivity Factor'` | `['absorptivity', 'factor']` |
| C-07 | `'entire verification study'` | `['entire', 'verification']` |
| **D-01** | `'45, 56'` | **`[]`** |

The replay yields **exactly five** zero-token `mvr1381` items — `A-07`, `B-03`, `B-06`,
`C-03`, `D-01` — matching the pre-registered expectation. Because the replayed set is
identical to the expected set, the dataset and matcher have **not** moved and the
comparison basis is intact. (The held-out `spec32s41` item `H-02` `'NMT 3.5%.'` also
tokenizes to `[]`, but held-out is not scored; noted here only for completeness.) All
four `minispec` anchors tokenize to a non-empty set (`0.14`→`['0.14']`,
`Maximum`→`['maximum']`, `Accuracy of the method was established`→`['accuracy',
'method', 'established']`, `Impurity B 0.15 0.10`→`['0.15', '0.10', 'impurity']`), so
`minispec` has **no** bucket-1 items.

## (b) Full classification — all 28 `mvr1381` items

| id | family | anchor | tokens | bucket | reason |
|---|---|---|---|---|---|
| A-01 | absence_of_evidence | `'99.9%'` | `['99.9']` | reachable | single-document; §1.2/Appendix 1 within `mvr1381` |
| A-02 | cross_reference_integrity | `'13439'` | `['13439']` | reachable | Table 2/Appendix 6 within `mvr1381` |
| A-03 | absence_of_evidence | `'control sample'` | `['control','sample']` | reachable | §1.4.1/Table 2 within `mvr1381` |
| A-04 | absence_of_evidence | `'degradants'` | `['degradants']` | reachable | §1.4.1 within `mvr1381` |
| A-05 | derivation_plausibility | `'377.49'` | `['377.49']` | reachable | Table 3 within `mvr1381` |
| A-06 | derivation_plausibility | `'Co-relation Coefficient'` | `['relation','coefficient']` | reachable | Tables 3/6 within `mvr1381` |
| **A-07** | absence_of_evidence | `'0.5%'` | `[]` | **matcher-unreachable** | `%` outside `_TOKEN_RE`; `0.5` is 3 chars, below the 4-char floor |
| A-08 | regulatory_framing | `'specification level'` | `['specification']` | reachable | §1.1/§1.4.4/Table 13 within `mvr1381` |
| A-09 | regulatory_framing | `'<1226>'` | `['1226']` | reachable | §1.1 within `mvr1381` |
| A-10 | absence_of_evidence | `'0.92%'` | `['0.92']` | reachable | §1.2/Appendix 3 within `mvr1381` |
| A-11 | absence_of_evidence | `'current in-house SOP'` | `['current']` | reachable | §1.1/§1.3 within `mvr1381` |
| A-12 | regulatory_framing | `'05/10/2016'` | `['05/10/2016']` | reachable | Approval page within `mvr1381` |
| B-01 | derivation_plausibility | `'10%LOD-LOQLevel'` | `['loqlevel']` | reachable | §1.4.3/§1.4.4/App 9-10 within `mvr1381` |
| B-02 | absence_of_evidence | `'standard deviation of the response'` | `['standard','deviation','response']` | reachable | §1.4.3/§1.4.4 within `mvr1381` |
| **B-03** | cross_reference_integrity | `'389'` | `[]` | **matcher-unreachable** | 3 chars, below the 4-char floor |
| B-04 | derivation_plausibility | `'6559.876'` | `['6559.876']` | reachable | Table 11 within `mvr1381` |
| B-05 | derivation_plausibility | `'27.0%'` | `['27.0']` | reachable | §1.4.5/Table 11 within `mvr1381` |
| **B-06** | absence_of_evidence | `'485'` | `[]` | **matcher-unreachable** | 3 chars, below the 4-char floor |
| B-07 | absence_of_evidence | `'9.83'` | `['9.83']` | reachable | Table 10 within `mvr1381` |
| B-08 | absence_of_evidence | `'Any Unspecified Impurity'` | `['unspecified','impurity']` | reachable | Table 13/15; **baseline found_set member** |
| C-01 | cross_reference_integrity | `'11477'` | `['11477']` | reachable | Table 20; **`tp_required`**, baseline found_set member |
| C-02 | cross_reference_integrity | `'0.15'` | `['0.15']` | reachable | Table 19/§1.4.8; **`tp_required`**, baseline found_set member |
| **C-03** | cross_reference_integrity | `'ND'` | `[]` | **matcher-unreachable** | 2 letters, below the 6-letter `_WORD_RE` floor |
| C-04 | cross_reference_integrity | `'0.14'` | `['0.14']` | reachable | Table 19 within `mvr1381` |
| C-05 | absence_of_evidence | `'room temperature'` | `['temperature']` | reachable | §1.4.7 within `mvr1381` |
| C-06 | regulatory_framing | `'Absorptivity Factor'` | `['absorptivity','factor']` | reachable | §1.5 within `mvr1381` |
| C-07 | regulatory_framing | `'entire verification study'` | `['entire','verification']` | reachable | §1.4.9/Table 20 within `mvr1381` |
| **D-01** | cross_reference_integrity | `'45, 56'` | `[]` | **matcher-unreachable** | both `45` and `56` are 2 chars, below the 4-char floor |

**Bucket 2 (single-agent-scope-unreachable) is EMPTY for `mvr1381`.** Every non-bucket-1
item is anchored to a section, table, or appendix **inside `mvr1381` itself** (see the
`section_hint` in each GT row) — none requires resolving a reference into a *different
submission document*, so none would drive `follow_reference` to
`cross_document_resolution_pending_phase_4`. Bucket 2 is a capability boundary; no
`mvr1381` item crosses it. (Absence-of-evidence items additionally need a *rule* fetched
via `read_guideline` — that is the rule-half of the chain, not a cross-document
submission reference, and is tracked as an infrastructure blocker in the
pre-registration §10, not as a bucket-2 assignment.)

`mvr1381` counts: **5 matcher-unreachable, 0 single-agent-scope-unreachable, 23 reachable = 28.**

## (c) Full classification — all 4 `minispec` items

| id | family | anchor | tokens | bucket | reason |
|---|---|---|---|---|---|
| MS-01 | cross_reference_integrity | `'0.14'` | `['0.14']` | reachable | Total-impurities row within `minispec` |
| MS-02 | cross_reference_integrity | `'Maximum'` | `['maximum']` | reachable | Maximum row within `minispec` |
| MS-03 | absence_of_evidence | `'Accuracy of the method was established'` | `['accuracy','method','established']` | reachable | narrative paragraph within `minispec` |
| MS-04 | cross_reference_integrity | `'Impurity B 0.15 0.10'` | `['0.15','0.10','impurity']` | reachable | Impurity B row within `minispec` |

`minispec` counts: **0 matcher-unreachable, 0 single-agent-scope-unreachable, 4 reachable = 4.**

`spec32s41` (held out) is not scored and is excluded from all buckets and ceilings.

## (d) Derived per-family ceilings (computed from this classification)

Computed by replaying `_anchor_tokens` per family over `mvr1381` (not copied):

| Family | GT items | matcher-unreachable | Max recall | Baseline | Headroom |
|---|---:|---:|---|---|---|
| `absence_of_evidence` | 11 | 2 (A-07, B-06) | **9/11 = 0.818** | 0.091 (B-08) | 8 additional matchable items; GO via absence requires >= 3/11 (>= 2 net-new beyond B-08) |
| `derivation_plausibility` | 5 | 0 | **5/5 = 1.000** | 0.000 | 5 items — cleanest path to D-GO1(a) |
| `regulatory_framing` | 5 | 0 | **5/5 = 1.000** | 0.000 | 5 items — cleanest path to D-GO1(a) |
| `cross_reference_integrity` | 7 | 3 (B-03, C-03, D-01) | **4/7 = 0.571** | 0.286 (C-01, C-02) | only 2 more matchable items exist |
| **overall (`mvr1381`)** | 28 | 5 | **23/28 = 0.821** | 0.107 | — |

`tp_required` (from the dataset's `tp_required: true` flags) is exactly **{C-01 (`'11477'`),
C-02 (`'0.15'`)}**. The senior-reviewer-confirmed governing **protected `found_set` is
{B-08, C-01, C-02}** (03-BASELINE-REMEASUREMENT.md), extending the two `tp_required`
items with the confirmed baseline absence-of-evidence hit B-08.

## (e) Pre-registered D-GO4 readings

1. **Scope, not architecture:** *"If the gate FAILS but every item in bucket 3 (reachable)
   was found, that is a NO-GO on the loop's single-agent SCOPE, not on the architecture —
   Phase 4's reference graph is the named next step and the report must say so."*
2. **Headline stays whole-set:** *"If the gate PASSES, the headline stays the frozen
   whole-set figure, never the reachable-subset figure, in the report and in anything
   quoted forward."*
3. **Bucket-1 never counts (the third-bucket reading):** *"No item in bucket 1
   (matcher-unreachable) counts against the loop, the architecture, or Phase 4's scope.
   Naming them here prevents Phase 4 from chasing items no system can win."*

## (f) Matcher untouched

`src/evals/match.py` is **not modified** by this plan. Its 4-char / 6-letter floors are
deliberate and documented; changing them is a harness change that voids D-GO1(iii)'s
comparison. `git diff --quiet -- src/evals/match.py` returns clean.
