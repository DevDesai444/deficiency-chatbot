# Phase 03 GO/NO-GO Pre-Registration (D-GO5 committed gate contract)

**This document is the committed gate contract. Before it exists in git, no scored spike
run may execute (D-GO5).** It fixes what every number will *mean* before any number
exists. Neither this document nor plan 03-18/03-19 declares the verdict — the GO/NO-GO
call is the senior reviewer's, made against this committed contract.

Companion artifact committed in the SAME commit: `03-REACHABILITY-CLASSIFICATION.md`
(all 32 scored GT items in three buckets, matcher-unreachable set verified by replaying
`match.py`'s own tokenization).

> **Senior-reviewer confirmed gate implications (recorded verbatim, ahead of all other
> readings):**
> (a) zero-TP-lost protects **{B-08, C-01, C-02}**;
> (b) zero families at freeze = **{derivation_plausibility, regulatory_framing}**; absence
> path to GO requires **>= 3/11 (>= 2 net-new beyond B-08)**;
> (c) gate inputs are **overall fp + recall_by_family only** — per-family fp is a
> documented frozen-harness definition quirk, excluded from the gate.

---

## 1. Gate criteria (D-GO1) — Family-unlock + zero-TP-lost

**GO requires (a) AND (b):**

- **(a)** At least one currently-**zero** family at freeze — `{derivation_plausibility,
  regulatory_framing}` — moves off `0.0` with at least one **grounded** true positive;
  **OR** `absence_of_evidence` reaches the pre-registered `>= 3/11` path (`>= 2` net-new
  grounded TPs beyond B-08).
- **(b)** The baseline `found_set` **{B-08, C-01, C-02}** is not lost.

Riders (all three written out so no result is interpreted after the fact):

- **(i) Derived arithmetic, recorded not re-litigated.** (a)+(b) jointly imply overall
  recall strictly above baseline: keeping `{B-08, C-01, C-02}` (tp = 3) plus one new
  grounded zero-family TP means tp >= 4 > 3, so overall recall moves above the frozen
  `0.107`. The absence path is stricter by ruling: it requires `>= 2` net-new beyond
  B-08 and therefore absence recall `>= 3/11`. Written down so nobody asks *"but did
  overall move?"* after the run.
- **(ii) Precision is REPORTED, never gated.** fp count and precision are recorded beside
  the gate result, and **fp > 125 (5x the baseline's 25) => GO-WITH-CONCERNS**, read by
  the reviewer before Phase 4 — *not* a NO-GO. Grounded-but-irrelevant is Phase 5's job;
  emit-spam gets a flag instead of invisibility.
- **(iii) Measurement integrity.** The GO run is scored by the **same harness, matcher
  version, and committed baseline** that produced the confirmed `0.107` reference (see
  §6 for the machine-checkable identity). `absence_of_evidence` is the **named headline
  expectation**, but it is no longer zero at freeze (B-08 = 1/11): the report **must
  state specifically whether absence reached `>= 3/11`**, because a pass through another
  family while absence stays at 1/11 means the mechanism built for it did not work and
  Phase 4 needs to know.

## 2. Run procedure (D-GO2) — N=3, at least 2 pass, variance reported

- **(i)** A failed/errored run is a **FAILING run, not a re-roll** — provider error,
  budget exhaustion, or crash counts against the `>= 2`. **Sole declared exception:** an
  infrastructure fault wholly outside the loop (endpoint 5xx / auth expiry with **zero
  tool calls made**), which may be re-run with the re-run and its reason recorded.
- **(ii)** All 3 runs are **fixed and identical in configuration before the first
  executes** — model, budgets, prompt, corpus, harness/matcher/baseline; seeds and
  temperature fixed at 0. **Any change voids the set and all 3 re-run.**
- **(iii)** The headline is the **MEDIAN, never the max.** All three are reported; the
  figure quoted forward to Phase 4 and externally is the median. Union scoring is
  rejected as headline but MAY be reported as a separate diagnostic labelled *"what the
  loop can find across 3 runs."*
- **(iv)** If the 3 runs disagree on **which** families unlock, that is
  **GO-WITH-CONCERNS, not a clean GO** — an unreliability Phase 4's fan-out amplifies.

## 3. Model scope (D-GO3) — recall gate on Llama only; Qwen proves tool fidelity only

- **(i)** The recall gate runs on **`databricks-meta-llama-3-3-70b-instruct` only**,
  because the frozen baseline was produced there; changing model and architecture
  together makes the result unattributable — the one question this phase exists to
  answer.
- **(ii)** The Qwen fidelity probe has a pre-registered pass bar: **>= 95%
  schema-conformant turns** (a call `structured.py` cannot repair counts as a failure)
  **AND >= 1 finding through the emit gate**, proving it can drive the full
  enumerate->fetch->emit chain.
- **(iii)** The report records that model-agnosticism is **PROVEN on the tool-fidelity
  axis and ASSERTED on the outcome axis.** Phase 4 inherits that as a **stated
  assumption, not a settled fact** — a fan-out on Qwen must first confirm outcome parity.

## 4. Reachability (D-GO4)

The reachable / structurally-unreachable / matcher-unreachable split for all 32 scored
GT items is in **`03-REACHABILITY-CLASSIFICATION.md`** (referenced by path only). That
document is **committed in the same commit as this one, whose SHA is recorded in
`03-PHASE-REPORT.md` §1 — no SHA is embedded here** (the two documents share one commit
SHA, which cannot be embedded in a file that commit contains; see §12's amendment note
and Task 4's circularity rule).

The three pre-registered readings, restated:

1. If the gate **FAILS but every bucket-3 (reachable) item was found**, that is a
   **NO-GO on the loop's single-agent SCOPE, not on the architecture** — Phase 4's
   reference graph is the named next step and the report must say so.
2. If the gate **PASSES**, the headline stays the **frozen whole-set figure**, never the
   reachable-subset figure, in the report and in anything quoted forward.
3. **No item in bucket 1 (matcher-unreachable) counts** against the loop, the
   architecture, or Phase 4's scope — naming `{A-07, B-03, B-06, C-03, D-01}` here
   prevents Phase 4 from chasing items no system can win.

Derived ceilings (from the classification): per-family max recall `absence 0.818`,
`derivation 1.000`, `regulatory 1.000`, `cross_reference 0.571`; **overall max
`23/28 = 0.821`** on `mvr1381`.

## 5. Frozen numbers (D-BUD1, D-GO5)

Every value below is stated here directly — **no cross-reference to another document for
the numbers themselves.** Confirmed by the senior reviewer's 03-16 ceiling ruling
(recorded in `03-BUDGET-CALIBRATION.md`).

| Knob | Frozen value | Notes |
|---|---:|---|
| `max_tokens` | **1,600,000** | 3x calibration median billed tokens (`ceil(411779.5 x 3) = 1235339`) x ~1.3 two-document adjustment, rounded. Backstop. |
| `max_wall_clock_s` | **600** | Runaway backstop; two-doc reviewing + Databricks 60s/retry backoff headroom. Includes tool-execution time (D-BUD5). |
| `max_turns` | **80** | 29 turns observed on the single calibration document; 50 could bind at two documents. Backstop. |
| `dr_window` | **3** | Diminishing-returns window (consecutive unproductive turns). |
| `breaker_repeat` | **3** | Circuit breaker on identical `(tool, args)` repeated N times (D-BUD3). |
| `breaker_same_class` | **4** | Circuit breaker on N consecutive rejections sharing the same `(reason_code, half)` (D-BUD3). |
| `max_continuations` | **5** | Hard cap on nudges, ORed with the DR bound (D-BUD4). |

**Calibration:** multiples were **pre-declared before calibration ran** as `max_tokens =
3x median billed tokens` and `max_wall_clock_s = 4x median elapsed seconds` (D-BUD1(a),
commit `86572c8`). Calibration corpus was the **held-out single document `spec32s41`**
(`data/32s41-Specification.pdf`) — the only held-out real submission; scored `mvr1381` and
`minispec` were excluded (D-BUD1). This is the D-BUD5-corollary limitation: a single
held-out document cannot exercise multi-document allocation, so the measured consumption
is a lower-bound signal and the final ceilings apply the two-document adjustments above.

**Ceilings are BACKSTOPS.** The operative stops are diminishing-returns and the breaker.
Both calibration runs terminated via DR/breaker (run 1 `diminishing-returns`, run 2
`breaker`), well inside every ceiling. **Watch item for the phase report:** the breaker
tripped in calibration run 2 — if it trips in any *scored* run, its `(reason_code, half)`
matrix must be examined at the gate before that run's result is accepted.

> **REVIEWER FLAG — divergence from the 03-17-PLAN.md literal text.** Plan 03-17's
> interfaces table and §5 body carry `max_turns=50` (the pre-declared value from commit
> `86572c8`). This pre-registration records the **reviewer-confirmed 03-16 value
> `max_turns=80`** instead, per the current work order. `max_tokens` (1,600,000) and
> `max_wall_clock_s` (600) likewise supersede the raw proposals (1,235,339 / 265). The
> reviewer must confirm these confirmed ceilings — not the older plan-text values — are
> what freezes here before this document is committed.

## 6. Governing baseline reference (D-LOOP2)

Frozen 3-run baseline on **`databricks-meta-llama-3-3-70b-instruct`**, temperature 0,
committed in `03-BASELINE-REMEASUREMENT.md` (commit
`5afb4d7165acc53a0d82650682b00c936eefed8c`).

| Family | run1 | run2 | run3 | min | **median** | max |
|---|---:|---:|---:|---:|---:|---:|
| `absence_of_evidence` | 0.091 | 0.000 | 0.091 | 0.000 | **0.091** | 0.091 |
| `cross_reference_integrity` | 0.286 | 0.000 | 0.286 | 0.000 | **0.286** | 0.286 |
| `derivation_plausibility` | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 |
| `regulatory_framing` | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** | 0.000 |
| **overall** | 0.107 | 0.000 | 0.107 | 0.000 | **0.107** | 0.107 |

- Governing overall median: **0.107**. Per-run overall recalls: **(0.107, 0.000, 0.107)**.
- Governing `found_set`: **{B-08, C-01, C-02}**. Blank-run rate: **1/3**
  (`BASELINE-BLANK-RUN-INSTABILITY` — an "above baseline" claim reads against the median
  only with this variance disclosed).
- **Drift verdict:** `|0.107 - 0.071| = 0.036 > 0.03` (the D-LOOP2 pre-registered line).
  The divergence was **confirmed by the senior reviewer under the D-LOOP2 divergence
  clause** and attributed to the P0 repair (broken planner/worker chain fixed, prompts
  de-leaked; C-02 survived without its leaked value) — a genuine repair, not leakage.

**Cross-arm harness identity (makes rider (iii) machine-checkable):**

- `src/evals/run.py` gained the `agent-run` subcommand (plan 03-15, wave 7) **after** the
  baseline arm was measured (plan 03-12, wave 5). The change is purely **additive** — a
  sibling command; `cmd_run`, `run_detection`, and the two scoring-input helpers
  `_join_source_text` and `_load_source_text` are untouched.
- **`_join_source_text` (`run.py:60-81`) and `_load_source_text` (`:107-127`) are the
  named EXCEPTION to `run.py`'s exclusion from the `HARNESS_VERSION` bump rule.** They
  build the `source_text` passed to `compute_metrics` in both `cmd_score` (`:139`) and
  `cmd_run` (`:280`), and `source_text` is what `anchor_rate` is computed against — a
  committed baseline value reported per run and compared across arms. The exclusion
  covers only the CLI surface (argument parsing, subcommand registration, sibling entry
  points), **not** these two helpers; editing either would require a bump. Plan 03-15
  edits neither, and **both arms re-score through the same `cmd_score` / `_load_source_text`
  path**, so no cross-arm asymmetry is introduced. The tempting one-line justification
  *"`run.py` is just a CLI shell"* is false and is not relied on here.
- The scoring path (`metrics.py`, `match.py`, `gate.py`, `schema.py`, `capture.py`) is
  unchanged, so **`HARNESS_VERSION` is deliberately NOT bumped** and both arms carry the
  same value. Bumping it for a CLI-shell addition would make D-GO1(iii) read the two arms
  as scored under different harnesses and invalidate the comparison for a change that
  touches no scoring logic.

**Identical provenance values across both arms** (quoted once; the reviewer confirms
cross-arm identity by comparison, from the baseline sidecars
`runs/baseline-run{1,2,3}-summary.json`):

| Field | Value |
|---|---|
| `harness_version` | `1` |
| `matcher_version` | `1` |
| `matcher_content_sha256` | `e7857edf3f5c1579e27d95f8cf5c086a9e20a443268ef35de01429c488f2c0ca` |
| `baseline_sha256` | `e680eb8638c811b5b9b1a9c7a585223250fdea66f40cf88611b426ba281a0ae3` |

The agent-run summaries will carry these same four values; any divergence voids the
cross-arm comparison.

## 7. Productivity definition (D-BUD2 + Pitfall 4)

A turn is **productive** iff it:

1. surfaced span-IDs **not previously issued this session**, **OR**
2. landed a finding through the **emit gate**, **OR**
3. **enumerated a `requirement_id` for the first time this session** (the Pitfall-4
   enumerate clause).

The third clause's reason: `read_guideline` enumerate mode records **no spans**, so
without it the loop would trip diminishing-returns during the exact RULES-05 enumeration
mechanism `absence_of_evidence` depends on. This definition governs both AGENT-03's early
stop and AGENT-04's nudge bound. Re-reading an already-issued span returns the COST-04
"still current" stub and counts as nothing.

## 8. Pre-registered readings (nothing interpreted after the fact)

- **D-TEL3 matrix.** `half=submission` + `not_byte_exact` => **SPAN INVENTION**
  (grounding-discipline failure — the gate did its job, the loop is unreliable).
  `half=rule` + `not_retrieved_this_session` => **NEVER CALLED `read_guideline`**
  (loop-behavior failure). **Reported SEPARATELY, never summed into one "rejections"
  count.** The diagnosis section must name which pattern dominated — they imply different
  NO-GO remedies (different model vs fix the loop/prompt).
- **D-TEL4.** Llama gets the same **>= 95% post-repair** conformance bar as Qwen.
  **PRE-repair and POST-repair malformed rates recorded SEPARATELY** (a loop at 95%
  post-repair but 40% pre-repair is one the fallback is carrying — that must be visible).
  Below the floor => **GO-WITH-CONCERNS, never NO-GO**: a model-reliability finding is a
  model-selection decision, not an architecture verdict.
- **D-TEL5 (three readings).** Nudges yield new grounded findings => the anti-premature-
  stop mechanism **works and is load-bearing for recall**. Nudges yield **zero** new
  findings across all runs => the nudge burns budget; reconsider AGENT-04 in Phase 4.
  **`continuation_count = 0` across all runs => the floor was never exercised and is
  UNPROVEN, not validated** — say so explicitly rather than claiming the mechanism works.
  Also record `tokens_at_each_attempted_stop`, `findings_before_vs_after_each_nudge`,
  the stop reason, `continuation_count` against the permitted max, and which bound ended
  the nudging (DR bound = genuinely finished; hard cap = the more troubling
  novelty-dripping behavior Phase 4's fan-out would multiply).
- **D-ORC2 conversion readings.** Record leads surfaced, leads re-opened, and leads that
  became emit-gate findings. A **low re-open rate** means the agent is ignoring
  deterministic leads (**recall lost to demotion — report it plainly**); a **high
  re-open-but-low-emit rate** means the oracles are surfacing noise. Either is actionable
  at the gate.
- **Pitfall 6 fallback (quoted verbatim from `registry.py`'s
  `PITFALL 6 -- PRE-REGISTERED FALLBACK` block).** Declaring it here keeps it from being a
  mid-set configuration change that D-GO2(ii) would void the run set for:

  > If the `optional_param_near_miss` counter DOMINATES the malformed-arg rate, the remedy
  > is a SCHEMA SHAPE change, not a model verdict: split the multi-mode tools into
  > single-mode schemas with all-required params over the SAME Python functions --
  > `list_requirements(family)` / `read_rule(citation)` / `continue_rule(handle)`
  > `get_section_by_heading(doc_id, heading)` / `get_section_by_span(doc_id, start, end)` /
  > `continue_section(handle)`
  > That takes the tool count from 7 to 11, well under the documented 32.

- **Pitfall 3's turn-indexed metric.** Tool fidelity is reported **per turn index**, not
  only as a run aggregate, and the turn index of the first malformed call is recorded
  (`first_malformed_turn_index`) — degradation-with-depth must be visible rather than
  averaged away.

## 9. Sign-off boundary (D-GO5)

*"The GO/NO-GO call is the senior reviewer's, made against this committed
pre-registration. The executor reports numbers and telemetry; **it does not declare the
verdict.**"*

*"On a clean NO-GO, Phases 4-6 do not auto-proceed."* The phase closes with the
telemetry-based diagnosis (which law broke — model tool-fidelity, grounding discipline,
or budget starvation), and the reviewer decides the next move at the gate.

## 10. Entry-gate status (D-PRE1 chain)

Strict D-PRE1 sequence: **P2 -> P1 -> boundary-crossing hunt -> D-LOOP2 baseline ->
commit this pre-registration -> the 3 agent runs.**

| Precondition | Document | Outcome / residual blocker |
|---|---|---|
| P2 — `pdf.py` embedded-text fix | `03-P2-BASELINE-SHIFT.md` (03-01) | Parse fix + cache invalidation applied. Retrieval hard-subset shifted `0.643 -> 0.571` (−0.071), attributed to the parse fix, **not** the agent (D-PRE1(a)). No new `mvr1381` hard anchor became reachable. |
| P1 — real-ingestion 3.2.S.5 classification | `03-P1-CLASSIFICATION-PROOF.md` (03-04) | Real ingestion classifies `mvr1381 -> 3.2.S.4.2` and `spec32s41 -> 3.2.S.4.1`; the two corrected-basis CFR entries were linked to both real families (`REQUIREMENT_INDEX_VERSION` 3->4) and enumerate for each. **Verification-queue item 5 is CLOSED** by reviewer measurement — see below. |
| Boundary-crossing hunt | `03-BOUNDARY-CROSSING-AUDIT.md` (03-10) | 16 chains examined, 1 UN-COMPOSED (oracle-lead re-open), closed with a composition test. 0 chains left open. |
| D-LOOP2 baseline | `03-BASELINE-REMEASUREMENT.md` (03-12) | Median 0.107 confirmed under the divergence clause (§6). |
| D-BUD1 calibration | `03-BUDGET-CALIBRATION.md` (03-16) | Ceilings confirmed (§5). |

**Verification-queue item 5 is CLOSED (senior-reviewer measurement, 2026-08-04, against
the real installed local rulebook store, 605 chunks).** P1's independent check reported
`rulebook.store.lookup_citation(entry.citation)` resolving **0/15**, but that outcome is
**BY DESIGN, not a gap**: requirement-index `citation` strings are rich human-readable
display strings (e.g. `ICH Q2(R2) -- Glossary: Specificity/Selectivity`), and the v3
resolution contract resolves rules through the **`rule_doc_id` fallback leg**, which the
reviewer measured at **15/15** on the live store. The dual-resolve contract
(`lookup_citation` display leg + `rule_doc_id` fallback leg) therefore resolves every
one of the 15 authored entries. P1's first-leg-only measurement was the right instinct
pointed at the wrong leg.

The composed `read_guideline(rule_doc_id)` E2E test (boundary chains #5/#7) is **NOT
synthetic-fixture-scoped**: it builds from the **real committed `rulebook/**` snapshot**
— the same chunks and the same span-IDs as the installed store — so its green result is
evidence on the real composition, not on a stand-in. There is no boundary-crossing blind
spot here.

**Consequence for the gate:** the `absence_of_evidence` live rule-retrieval path **is
proven** (15/15 dual-resolve). A `0.0` or a `1/11` stall on `absence_of_evidence` in the
spike therefore may **NOT** be attributed to a rulebook citation-resolution gap — that
gap does not exist — and must instead be read against the loop/model per D-GO1(iii)'s
named-headline-expectation discipline. Misattributing an absence stall to a phantom
rulebook gap is exactly the error this rewrite prevents.

**03-18 PRE-RUN PRECONDITION (added by reviewer).** Immediately before run 1, re-run the
15-entry dual-resolve probe (`lookup_citation` display leg + `rule_doc_id` fallback leg)
against the **installed** rulebook store — offline, seconds — and **record its 15/15
output in run-1 provenance.** This closes the only remaining risk: store drift between
this measurement (2026-08-04) and run time silently reintroducing the confounder. If the
probe returns anything other than 15/15 at run time, that is a store-state finding to
surface **before** the scored runs, not after.

## 11. Amendment clause (D-GO5)

*"Amending this document after any spike run begins **voids the run set** — all 3 re-run
from scratch (D-GO5)."* Once committed, this contract is immutable for the run set. Its
commit SHA is captured into every run summary's `prereg_commit_sha` by
`capture_provenance` and recorded in `03-PHASE-REPORT.md` §1 — never inside this document
(a commit's own hash cannot be embedded in the file that commit contains).

## 12. Decision register (every locked decision from CONTEXT.md `<decisions>`)

Recorded so every rider referenced by the gate is present in one artifact.

- **D-GO1** — Family-unlock + zero-TP-lost gate; riders (i) derived arithmetic, (ii)
  precision reported never gated / `fp > 125 => GO-WITH-CONCERNS`, (iii) measurement
  integrity. See §1.
- **D-GO2** — N=3, `>= 2` pass; riders (i)–(iv). See §2.
- **D-GO3** — recall gate on Llama only; Qwen fidelity bar; agnosticism proven-on-fidelity
  / asserted-on-outcome. See §3.
- **D-GO4** — three-bucket reachability split committed before run 1; three readings. See
  §4 and `03-REACHABILITY-CLASSIFICATION.md`.
- **D-GO5** — this committed pre-registration; sign-off is the reviewer's; NO-GO does not
  auto-proceed; amendment voids the run set. See §9, §11.
- **D-TEL1** — typed per-turn JSONL + per-run summary JSON with full provenance; both
  artifacts committed to the phase directory (3 JSONL + 3 summaries + cross-run
  comparison), re-derivable by someone who did not watch the runs.
- **D-TEL2** — open reason-code registry (`KNOWN_REASON_CODES`) exported from
  `src/tools/errors.py`; tools emit plain `str`; unrecognized codes flagged loudly.
- **D-TEL3** — structured `half` field (`submission|rule|''`); `(reason_code, half)`
  matrix reported separately, never summed. See §8.
- **D-TEL4** — Llama held to the same `>= 95%` post-repair bar; pre/post-repair recorded
  separately; below-floor => GO-WITH-CONCERNS. See §8.
- **D-TEL5** — continuation telemetry (the AGENT-04 signal); three pre-registered
  readings incl. the `continuation_count = 0` UNPROVEN case. See §8.
- **D-LOOP1** — hand-rolled turn loop + pydantic arg models, `structured.py` as repair
  path; ships behind a flag with `run_detection` left runnable so both arms run
  back-to-back on the same corpus.
- **D-LOOP2** — baseline arm re-run 3x under the D-GO2 procedure; median governs; drift
  line `|median - 0.071| > 0.03` triggers reviewer confirmation. See §6.
- **D-LOOP3** — tool JSON schemas DERIVED from the pydantic arg models via
  `model_json_schema()` reusing `structured.py`'s `_sanitize` / `schema_for_databricks`;
  single source of truth.
- **D-LOOP4** — COST-01 cache-stability invariant adopted now: system prompt + tool
  schemas fully static; dynamic values (manifest, doc counts, families, rule enumeration)
  in messages; cross-corpus byte-identical-prefix test shipped with the loop.
- **D-LOOP5** — rejection feedback is a TURN, not an exception; a `ToolRejected` result
  is returned to the model as the tool result and consumes a turn; never raises, never
  silently retries. Corollary: a call repaired by `structured.py` **before** dispatch is
  pre-repair-malformed and does NOT consume a turn; a dispatched-then-rejected call does.
- **D-BUD1** — declared calibration first then freeze; calibration on held-out corpus,
  not the scored set; multiple pre-declared before calibration; calibration runs not
  among the 3; infeasible-multiple is a reportable finding, never a quiet lowering. See §5.
- **D-BUD2** — productivity definition (new spans OR emit-gate finding OR first-time
  `requirement_id` enumeration). See §7.
- **D-BUD3** — circuit breaker on identical `(tool, args)` `breaker_repeat=3` OR N
  consecutive same-`(reason_code, half)` rejections `breaker_same_class=4`; reuses the
  D-TEL3 matrix as detection key. See §5.
- **D-BUD4** — nudge bounds are DR-bounded OR hard-cap `max_continuations=5`, whichever
  fires first; record which bound ended the nudging. See §5, §8.
- **D-BUD5** — budget is PER-RUN not per-document, counts input+output across every turn
  including tool results; wall-clock includes tool-execution time; calibration must
  measure a full multi-document review (limited here to a single held-out doc — disclosed
  in §5).
- **D-BUD6** — SC3 runaway load test = synthetic forced-runaway driver in CI + one
  real-model low-ceiling confirmation during the spike, declared not among the 3.
- **D-ORC1** — the seed pass is a callable `run_oracles` TOOL (7th tool); oracle leads
  issue span-IDs through the identical tool-result path; replaces the old
  `pipeline.py` union that bypassed every gate.
- **D-ORC2** — never pre-record oracle spans into the `RetrievalLedger`; the agent must
  re-open each lead before `emit_finding` accepts it (that re-read cost IS the demotion);
  conversion telemetry pre-registered. See §8.
- **D-VER1** — legacy `verify.py`/`challenge.py` do NOT run over agent findings in
  Phase 3 (they can drop findings and would violate EVAL-03's zero-TP-lost inside the
  gate measurement); grounded findings go into `FaultReport` directly; any retained
  legacy pass for tiering must be provably non-dropping and asserted in a test.
- **D-VER2** — DETECT-04's compliance verdict is an ENUMERATED field (e.g.
  `violation`/`gap`/`ambiguous`), not free text; travels beside `rule_span_id`.
- **D-PRE1** — Phase-2 preconditions become Wave-1 plans with ordering in `depends_on`;
  P2 before P1; baseline after both; parse-shift and boundary-hunt deliverables named.
  See §10.

---

*Companion (same commit): `03-REACHABILITY-CLASSIFICATION.md`. Governing baseline:
`03-BASELINE-REMEASUREMENT.md` (`5afb4d7`). Frozen ceilings:
`03-BUDGET-CALIBRATION.md`.*
