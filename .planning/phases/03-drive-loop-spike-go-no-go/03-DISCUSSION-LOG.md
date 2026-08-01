# Phase 3: Drive-Loop Spike (GO/NO-GO) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-01
**Phase:** 03-drive-loop-spike-go-no-go
**Areas discussed:** GO/NO-GO threshold, Spike telemetry, Loop architecture, Budgets & stop rules, Oracle demotion + gating

**Area selection note:** the four areas offered were all selected, and the user added a fifth — *spike telemetry / diagnosability* — on the reasoning that a NO-GO number without a diagnosis wastes the spike. Discussion order was resequenced to **gate → telemetry → architecture → budgets → oracles**: decide what pass/fail means and how it will be diagnosed, then build toward it.

---

## GO/NO-GO threshold

### Q1 — the pre-registered pass condition

| Option | Description | Selected |
|--------|-------------|----------|
| Family-unlock + zero-TP-lost | ≥1 currently-zero family moves off 0.0 with a grounded TP, AND `{C-01, C-02}` not lost. No precision gate — grounded-but-irrelevant is Phase 5's job per D-EF1(4) | ✓ |
| Family-unlock only | Simplest, hardest to game upward; permits a "win" that silently drops C-01/C-02 | |
| Family-unlock + zero-TP-lost + precision floor | Strictest; risks a NO-GO on the loop for a problem Phase 5 exists to fix | |
| Overall-recall multiple (≥2× baseline) | One clean number; satisfiable entirely inside `cross_reference_integrity` without unlocking any new check-kind | |

**User's choice:** Option 1 as written, plus three riders.
**Notes:** (i) Record the arithmetic consequence — (a)+(b) imply overall recall strictly above 0.071 — so nobody re-litigates "but did overall move" after the run. (ii) Precision reported never gated, with a pre-registered `fp > 125` GO-WITH-CONCERNS flag: *"emit-spam is also a signal the loop isn't reasoning, so it gets a named flag instead of being invisible."* (iii) Measurement integrity frozen to the same harness/matcher/baseline; re-baseline BEFORE the spike, never after; `absence_of_evidence` named as the headline expectation the report must address explicitly even when another family carries the pass.

### Q2 — the run rule

| Option | Description | Selected |
|--------|-------------|----------|
| 3 runs, ≥2 must pass, variance reported | Catches a lucky draw without letting one flaky run veto | ✓ |
| 3 runs, ALL must pass | Strongest claim, highest false-NO-GO risk | |
| 3 runs, union scored | Measures what the loop *can* find; asymmetric against a single-pass baseline | |
| Single run at temperature 0 | No variance estimate at all | |

**User's choice:** Option 1, plus four riders.
**Notes:** *(This question was asked twice — the first response was withdrawn and the question re-put unchanged.)* (i) A failed run is a **failing** run, not a re-roll — *"otherwise '3 runs' quietly becomes 'keep drawing until 2 pass'"*; sole exception is a zero-tool-call infrastructure fault, which must be recorded. (ii) Config frozen and identical across all 3 or the set voids. (iii) **Median** is the headline, never max; union permitted only as a labelled ceiling-vs-reliability diagnostic. (iv) Family-disagreement across passing runs = GO-WITH-CONCERNS, since *"the loop is unreliable in a way Phase 4's fan-out will amplify."*

### Q3 — model split

| Option | Description | Selected |
|--------|-------------|----------|
| Recall gate on Llama 3.3 70B; Qwen proves tool fidelity only | Baseline-matched; 3 recall runs + 1 probe | ✓ |
| Full 3-run gate on both, GO if either passes | 6 runs; proves agnosticism on the outcome axis | |
| Full 3-run gate on both, GO requires both | Strictest; conflates model selection with architecture | |
| Llama only, defer Qwen to Phase 4 | Drops roadmap SC1's explicit both-models clause | |

**User's choice:** Option 1, plus three pre-registrations.
**Notes:** *(The first response to this question returned the prior answer's text verbatim; the question was re-put and answered.)* (i) *"Running the recall gate on a different model changes TWO variables at once… Baseline-matched is not a convenience, it is the comparison's validity."* (ii) Qwen's probe gets a falsifiable bar: ≥95% schema-conformant tool calls (unrepairable calls count as failures despite `structured.py` coercion of type slips like the known `top_k`-as-string) **and** ≥1 finding clearing the emit gate — *"otherwise 'fidelity proven' is unfalsifiable."* (iii) Report that agnosticism is proven on fidelity, asserted on outcome; Phase 4 must confirm outcome parity before fanning out on Qwen — *"the same discipline as the 3.2.S.5 item: name the untested assumption at the boundary."*

**Context surfaced during this question:** the committed baseline JSON records `generated_from` but not the producing model; `config.py`'s `detector_model` resolves to `databricks-meta-llama-3-3-70b-instruct`.

### Q4 — the denominator

| Option | Description | Selected |
|--------|-------------|----------|
| Score frozen whole-set; report a reachable breakout | No denominator surgery; diagnosis separates "missed it" from "couldn't reach it" | ✓ |
| Frozen whole-set only, no breakout | One number, but a weak result cannot be attributed | |
| Re-scope the denominator to reachable items | Changes the denominator that produced 0.071 | |
| Score both, gate on the reachable subset | Swaps the pre-registered comparison for a friendlier one at gate time | |

**User's choice:** Option 1, with the split committed before the runs.
**Notes:** *"Classifying misses after seeing results is post-hoc rationalization wearing a diagnostic's clothes."* Two readings pre-registered: a failed gate with all reachable items found is a NO-GO on **single-agent scope**, not architecture, naming Phase 4's reference graph as the next step; a passing gate quotes the whole-set figure forward, never the subset.

### Closed inline (no options presented) — pre-registration as artifact

**User's decision:** All gate decisions go to `03-GO-NOGO-PREREGISTRATION.md`, committed before the first run with the pre-classified ground-truth split; its SHA recorded in the phase report; amendment after a run voids the set. The verdict is the senior reviewer's — *"the executor reports the numbers and the telemetry, it does not declare the verdict."* A clean NO-GO does not auto-proceed to Phases 4–6; the telemetry diagnosis determines the next move as a reviewer decision, not a planned branch.

---

## Spike telemetry

*(Area added by the user during selection: "a NO-GO number without a diagnosis wastes the spike… If the loop fails, these tell us WHICH law it broke — model reliability vs grounding discipline vs budget starvation — and that decides whether NO-GO means 'different model,' 'fix the loop,' or 'abandon the approach.' Cheap to record, decisive at the gate.")*

### Q1 — telemetry form

| Option | Description | Selected |
|--------|-------------|----------|
| Typed per-turn JSONL + per-run summary JSON | Schema is code with a test; plain-file, fully offline; matches the existing `baseline/*.json` shape | ✓ |
| structlog events parsed post-hoc | Untyped, untested; a renamed field breaks the diagnosis silently | |
| OpenTelemetry spans | Best long-term observability; heavy for a spike, awkward to diff in CI | |
| Existing job store + event_bus | Free UI visibility; couples the gate's evidence to runtime infra, against D-RB6 | |

**User's choice:** Option 1, plus two additions and a constraint.
**Notes:** (i) The summary must carry provenance (run index, model id, pre-registration SHA, harness/matcher/baseline + normalizer + serializer versions, corpus content-hash, completed-vs-aborted flag) — *"an aborted run must be self-evidently distinguishable from a completed one, per D-GO2(i)."* (ii) Both artifacts committed, not scratch — *"the verdict must be re-derivable from committed files by someone who did not watch the runs."* Constraint: the reason-code enum must be the same one the tool raises, imported not restated.

### Q2 — reason-code source of truth

**Context surfaced:** `ToolRejected.reason_code` is deliberately a plain `str`, not a closed `Literal` — the docstring states *"later plans add codes without editing this file."* There is no enum to import, so the constraint above needed reconciling.

| Option | Description | Selected |
|--------|-------------|----------|
| Open registry exported from `errors.py` | Tools keep plain str; telemetry imports the registry; unrecognized codes flagged loudly | ✓ |
| Close to a StrEnum now | Drift impossible by construction; reverses the Phase-2 note deliberately | |
| Plain str, group by exact match | Zero coupling; a typo silently splits the most diagnostic signal | |

**User's choice:** Option 1.

### Q3 — submission vs rule half

**Context surfaced:** `emit_finding` returns the same `reason_code` for both halves; the distinction exists only in free-text `reason`.

| Option | Description | Selected |
|--------|-------------|----------|
| Structured `half` field on `ToolRejected` | Purely additive; groups by `(reason_code, half)` with no string parsing | ✓ |
| Half-specific reason codes | No schema change; breaks code names shared with other tools | |
| Parse the free-text reason | No code change; brittle exactly where diagnosis matters most | |

**User's choice:** Option 1, with the reading pre-registered.
**Notes:** The halves are opposite diagnoses and are reported separately, never summed. `submission`+`not_byte_exact` = span invention (grounding-discipline failure); `rule`+`not_retrieved_this_session` = never called `read_guideline` (loop-behavior failure). *"These imply different NO-GO remedies… the phase report's diagnosis section must name which pattern dominated."*

### Q4 — does fidelity gate anything?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-registered floor; below it = GO-WITH-CONCERNS | Same shape as the fp>125 flag; recall stays the sole gate | ✓ |
| Hard co-gate: below floor = NO-GO regardless of recall | Most literal reading of SC1; conflates wrong-model with wrong-architecture | |
| Report only, no Llama bar | The model carrying the gate would be the one with no reliability bar | |

**User's choice:** Option 1, with the measurement pinned.
**Notes:** Record pre-repair and post-repair rates separately — *"a loop at 95% post-repair but 40% pre-repair is a loop the fallback is carrying — that must be visible in the report, not hidden behind a passing number."*

### Closed inline — continuation telemetry (D-TEL5)

**User's decision:** The AGENT-04 floor is unmeasured by the above and aimed squarely at the 2/28 failure, so it gets its own record: `continuation_count`, tokens at each attempted stop, findings before-vs-after each nudge, and the terminal stop reason. Three readings pre-registered, including the null case: *"continuation_count = 0 across all runs => the model never tried to stop early; the floor was never exercised and is UNPROVEN, not validated. Say so explicitly rather than claiming the mechanism works."*

---

## Loop architecture

### Q1 — AGENT-04's requirement identity

**Raised by Claude:** plans citing AGENT-04 would fail the requirements-coverage gate, since REQUIREMENTS.md had only AGENT-01/02/03 and Phase 3's list carried six IDs.

| Option | Description | Selected |
|--------|-------------|----------|
| Amend AGENT-03 to be bidirectional | No new ID, count unchanged | |
| Add AGENT-04 as a distinct v1 requirement | Independently verifiable; requires REQUIREMENTS/ROADMAP edits | ✓ *(already done on disk)* |
| CONTEXT.md decision only, no requirement ID | Nothing gates it; invisible at milestone level | |

**User's choice:** Already resolved in commit `8760665` before this question was asked.
**Notes:** Rationale for a distinct ID over amending AGENT-03: *"the floor must fail verification INDEPENDENTLY of the ceiling — they are opposite mechanisms aimed at opposite failure modes (ceiling = runaway cost; floor = premature stop, which is the 2/28 recall failure), and folding them into one ID lets a passing ceiling mask an unbuilt floor."* Verified on disk: REQUIREMENTS.md:38, traceability row → Phase 3, counts 33/33 with Phase 3 → 7, ROADMAP Requirements line updated, new success criterion 3b added.

### Q2 — how the loop is built

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-rolled loop over the existing openai client | Owns exactly the code the gate measures | |
| PydanticAI typed agent layer | Free arg validation; stop/budget machinery would live in framework code | |
| Hand-rolled loop + pydantic arg models per tool | Framework-free control flow plus typed validation to point at for the ≥95% number | ✓ |

**User's choice:** Option 3, plus the flag requirement.
**Notes:** The loop ships behind a flag with `run_detection` left runnable — *"if the old path is replaced outright, the comparison depends on a frozen number nobody can re-derive at gate time."*

### Q3 — the baseline arm's stochasticity

| Option | Description | Selected |
|--------|-------------|----------|
| Re-run baseline 3× under D-GO2; median governs | Symmetric treatment of both arms | ✓ |
| Committed 0.071 governs; re-run is confirmation | Preserves the frozen reference; leaves the gate on a single-draw control | |
| Re-run 3×; worst baseline run governs | Asymmetry in the opposite direction | |

**User's choice:** Option 1, with the frozen-reference discipline preserved by sequencing.
**Notes:** The baseline re-run precedes the agent arm and its median is committed to the pre-registration — *"the sequence makes that impossible"* (re-baselining after seeing results). A `|median − 0.071| > 0.03` divergence is a reportable measurement-stability finding requiring reviewer confirmation. Baseline min/median/max reported: *"if the single-shot detector swings widely, 'above baseline' is a weaker claim than it looks, and the gate reading must say so."*

### Q4 — tool schema source

| Option | Description | Selected |
|--------|-------------|----------|
| Derived from the pydantic arg models | Single source of truth via `model_json_schema()` + existing sanitize path | ✓ |
| Hand-authored alongside the models | Full control of descriptions; drift corrupts the D-TEL4 signal | |
| Derived + hand-written description layer | Single structural source with separate prompt-craft | |

**User's choice:** Option 1.

### Q5 — cache-stability invariant timing

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt the invariant now, assert it with a test now | Nearly free while writing the loop; Phase 6 hardens a proven-stable prefix | ✓ |
| Adopt now, defer the test to Phase 6 | Intent-only through the window where Phase 4/5 add per-corpus context | |
| Ignore — Phase 6 owns it entirely | SC1c warns this "silently forfeits the entire caching lever" | |

**User's choice:** Option 1.

### Closed inline — rejection feedback (D-LOOP5)

**User's decision:** A `ToolRejected` is returned to the model as the tool's result and consumes a turn. *"Rejections invisible to the model make the emit gate a wall instead of a teacher — the agent would keep re-emitting the same fabricated quote with no idea why nothing lands."* Counting the turn keeps the budget honest and lets the breaker see repeated-failure patterns. Corollary: repaired-before-dispatch is pre-repair malformed and consumes no turn; dispatched-then-rejected consumes one — *"different failure classes at different layers and the telemetry must not conflate them."*

---

## Budgets & stop rules

### Q1 — how the ceilings are set

| Option | Description | Selected |
|--------|-------------|----------|
| Declared calibration run(s) first, then freeze | Removes budget starvation as a confounder; gate runs stay frozen-config | ✓ |
| Pick a priori from first principles | Guessing low manufactures a named NO-GO diagnosis | |
| Generous ceiling; diminishing-returns does the stopping | Starvation-proof; SC3 still needs a ceiling that trips | |

**User's choice:** Option 1, with a contamination guard.
**Notes:** Calibration runs on a held-out corpus, never the scored eval set — *"consumption generalizes across corpora; findings do not, so nothing is lost by calibrating elsewhere."* The multiple is written before calibration *"so the number cannot be tuned to a result"*; calibration findings are neither scored nor quoted; an infeasible multiple is escalated, *"never quietly lower the multiple."*

### Q2 — the diminishing-returns metric

| Option | Description | Selected |
|--------|-------------|----------|
| New unique span-IDs retrieved OR new gate-passing findings | Circling trips DR; gathering-before-emitting does not | ✓ |
| New accepted findings only | Halts an agent mid-investigation | |
| New unique span-IDs only | An agent that never emits never trips DR | |

**User's choice:** Option 1.

### Q3 — circuit breaker trip

| Option | Description | Selected |
|--------|-------------|----------|
| Identical `(tool, args)` N times OR N consecutive same `(reason_code, half)` | Catches arg-perturbation while failing identically | ✓ |
| Identical `(tool, args)` only | Trivially evaded | |
| N consecutive rejections of any kind | Penalizes genuine self-correction | |

**User's choice:** Option 1.

### Q4 — nudge cap

| Option | Description | Selected |
|--------|-------------|----------|
| DR-bounded + pre-registered hard max count | Closes the one-trivial-span-per-turn gap | ✓ |
| DR-bounded only, as AGENT-04 is written | Relies on the token ceiling as sole backstop | |
| Hard max only, drop the DR coupling | Keeps nudging a finished agent up to the cap | |

**User's choice:** Option 1, with the interaction stated explicitly.
**Notes:** The bounds are ORed, whichever fires first — *"DR is the productivity signal, the cap is the anti-gaming backstop."* Which bound fired is itself diagnostic: DR means genuinely finished and the floor was correctly permissive; the hard cap means *"the model was producing just enough novelty to keep being nudged, which is a different and more troubling behavior that Phase 4's fan-out would multiply."*

### Q5 — the SC3 runaway load test

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic forced-runaway driver in CI | Deterministic, offline, zero LLM spend | |
| Synthetic in CI + one real-model confirmation | Permanent CI guarantee plus real-model evidence | ✓ |
| Real model against an oversized corpus only | Entangles model behavior with the gate's | |

**User's choice:** Option 2.

### Closed inline — budget unit (D-BUD5)

**User's decision:** Per-run, not per-document; counts input + output across every turn including tool results; wall-clock includes tool execution. *"A per-document budget would let an agent exhaust itself on document 1 and skim the rest — reproducing the 2/28 ceiling by a different route, while each document individually looked well-behaved."* Corollary: calibration must measure a full multi-document review, not a single document extrapolated.

---

## Oracle demotion + gating

### Q1 — the seeding mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| A callable `run_oracles` tool the agent invokes | Span-IDs issued through the identical path; zero new grounding machinery | ✓ |
| Pre-seeded as an initial message | No turn cost; puts run-specific content near the cached prefix | |
| Keep oracles emitting Faults directly | Contradicts SC4; leaves findings that never pass the emit gate | |

**User's choice:** Option 1.

### Q2 — ledger treatment of oracle spans

| Option | Description | Selected |
|--------|-------------|----------|
| Never pre-record — the agent must re-open each lead | `was_issued()` keeps meaning "the model saw it" | ✓ |
| Pre-record oracle spans as issued | Saves a turn; creates a span-invention blind spot | |
| Pre-record but tag for separate handling | Preserves the saving with an audit trail; a second grounding path | |

**User's choice:** Option 1, with conversion telemetry pre-registered.
**Notes:** *"That re-read cost IS the demotion."* Record leads surfaced → re-opened → emitted: a low re-open rate is recall lost to demotion, reported plainly; high-re-open/low-emit means the oracles surface noise. *"Without the metric, 'we demoted the oracles' is an architectural claim with no evidence attached."*

### Q3 — P1/P2 precondition tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Wave-1 plans inside Phase 3, loop plans depend on them | Gate enforced structurally; baseline re-measurement sequences after | ✓ |
| P1/P2 as plans; boundary hunt stays a review activity | Enforceable things enforced, exploratory thing exploratory | |
| Handled outside Phase 3 before planning | Nothing mechanical enforces the gate | |

**User's choice:** Option 1, with the ordering encoded in `depends_on` rather than implied by wave numbering.
**Notes:** P2 before P1 *"because the 3.2.S.5 classification signal may sit on the very scanned pages P2 recovers — proving classification against text that pdf.py currently discards would prove the wrong thing."* Baseline re-measurement after both *"because P2 changes parse output and therefore the number being frozen."* A P2-induced baseline shift is attributed to the parse fix, *"not to the agent, and not silently absorbed."* The boundary hunt ships a written chain list plus a composition test for each, *"so it cannot pass as 'we looked and it seemed fine.'"*

### Closed inline — legacy passes and the verdict field

**D-VER1:** `verify.py` and `challenge.py` do not run over agent findings. *"A dropped finding would silently depress the recall number the gate is reading, and we would attribute a loop failure to the loop when a legacy filter caused it."* Running them would violate EVAL-03's zero-TP-lost discipline inside the measurement deciding Phases 4–6. Any legacy pass retained for tiering metadata *"must be provably non-dropping — assert it in a test, do not assume it."*

**D-VER2:** DETECT-04's compliance verdict is enumerated, not free text — *"free text cannot be scored deterministically by the harness, cannot be compared across the 3 runs, and cannot be diffed against the baseline — the same reason the reason_code registry is enumerated."*

---

## Claude's Discretion

- System-prompt wording (reviewer persona, enumerate→investigate→emit workflow) — *"prompt-craft to iterate on"*, bounded by D-LOOP4's static-prefix requirement.
- Held-out calibration corpus — the existing `spec32s41` held-out document is the default; *"if the planner finds it insufficient for a full multi-document consumption measurement, flag it rather than substituting scored data."*
- The concrete N values (breaker repeat count, DR consecutive-turn count, hard max continuations, calibration multiple) — planner's to propose, all must land in the committed pre-registration before run 1.
- The verdict enum's exact members; the loop's module path; the flag mechanism (config vs CLI vs env).
- Where the grounded partial surfaces in `FaultReport`; how loop progress reaches the `event_bus`/WebSocket UI.
- Whether S9/S10/P10 currently live in `oracles.py` or `checklists.py` — the roadmap calls them oracles; the code splits deterministic checks across both.

## Deferred Ideas

No scope creep was raised during this discussion. Items noted as belonging to later phases:

- Orchestrator + sub-agent fan-out (AGENT-02), cross-document reference graph — Phase 4. Four decisions deliberately hand Phase 4 a *stated assumption* rather than a silent inheritance: D-GO3(iii) Qwen outcome parity, D-GO4(a) single-agent scope, D-GO2(iv) family-disagreement variance, D-BUD4's hard-cap reading.
- Adversarial verifier (GROUND-02) — Phase 5, the designed successor to the `challenge.py` pass D-VER1 removes.
- Prompt caching, compaction, cheap-model triage (COST-01/02/03) — Phase 6; only the cache-*stability* invariant is pre-paid here.
- Reconsidering AGENT-04 itself — D-TEL5 pre-registers the reading under which the nudge is judged to burn budget rather than buy recall; that verdict lands in Phase 4.
- Carried Phase-2 hygiene: precedent-search as a 6th tool, reranker, multi-hop GraphRAG, Git LFS for `rulebook/**`, rulebook FAISS dense rebuild.
