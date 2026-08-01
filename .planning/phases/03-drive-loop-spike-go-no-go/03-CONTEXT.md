# Phase 3: Drive-Loop Spike (GO/NO-GO) - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the one-shot pre-rendered detection call with a **single** model-driven tool loop over the six Phase-2 navigation tools: the agent requests evidence → reasons → requests more → stops on done-or-budget. Every finding it emits is dual-grounded (submission span + rule span, both re-opened byte-exact through the `emit_finding` gate) and carries a compliance verdict. Budgets, circuit breaker, diminishing-returns stop, **and the anti-premature-stop floor (AGENT-04)** are enforced **in code, never as prompt instructions**. The S9/S10/P10 deterministic oracles are demoted from primary finding source to a seed pass the loop consumes. Then the recall-by-failure-family result is compared against the single-shot baseline under a **pre-registered, committed gate** — and that comparison decides whether Phases 4–6 happen at all.

**Requirements:** AGENT-01, AGENT-03, **AGENT-04**, GROUND-01, GROUND-03, DETECT-03, DETECT-04 (7 — AGENT-04 added in commit `8760665`; ROADMAP gained success criterion 3b).

**Explicitly NOT in this phase:** orchestrator decomposition and sub-agent fan-out (Phase 4, AGENT-02); cross-document reference-graph traversal — `follow_reference` still returns typed `cross_document_resolution_pending_phase_4` (Phase 4, D-FR); the adversarial verifier and rule-*relevance* judgment (Phase 5, GROUND-02); prompt-cache hardening, compaction and cheap-model triage (Phase 6, COST-01/02/03) — though Phase 3 **builds to** COST-01's cache-stability invariant per D-LOOP4.

**The measurement is the deliverable.** A NO-GO diagnosed by telemetry is a successful Phase 3. An undiagnosed number is not.

</domain>

<decisions>
## Implementation Decisions

### GO/NO-GO gate — the pre-registered pass condition

- **D-GO1: Family-unlock + zero-TP-lost.** GO requires **(a)** ≥1 currently-zero family (`absence_of_evidence`, `derivation_plausibility`, `regulatory_framing`) moves off 0.0 with ≥1 **grounded** true positive, **AND (b)** the baseline `found_set` `{C-01, C-02}` is not lost. Riders:
  - **(i) Derived consequence recorded, not re-litigated.** (a)+(b) jointly imply overall recall strictly above baseline (keeping both plus ≥1 new grounded TP ⇒ tp≥3 > 2). No separate overall-recall clause — but write the arithmetic down so nobody asks "but did overall move?" after the run.
  - **(ii) Precision is REPORTED, never gated**, with one named flag: fp count and precision are recorded beside the gate result, and **fp > 125 (5× the baseline's 25) ⇒ GO-WITH-CONCERNS**, read by the reviewer before Phase 4 — *not* a NO-GO. Grounded-but-irrelevant is Phase 5's job (D-EF1(4)); but emit-spam is also a signal the loop isn't reasoning, so it gets a flag instead of invisibility.
  - **(iii) Measurement integrity, frozen now.** The GO run is scored by the **same harness, matcher version, and committed baseline** that produced 0.071. Any matcher/harness change invalidates the comparison and requires re-baselining **BEFORE the spike, never after.** `absence_of_evidence` is the **named headline expectation** (the requirement index exists for it; P1 guarantees its entries can fire) — any zero-family unlock passes the gate, but the report **must state specifically whether absence moved**, because a pass while absence stays 0/11 means the mechanism built for it did not work and Phase 4 needs to know.

- **D-GO2: N=3 runs, ≥2 must pass, variance reported.** Riders:
  - **(i)** A failed/errored run is a **FAILING run, not a re-roll** — provider error, budget exhaustion, or crash counts against the ≥2. Otherwise "3 runs" quietly becomes "keep drawing until 2 pass." **Sole declared exception:** an infrastructure fault wholly outside the loop (endpoint 5xx / auth expiry with **zero tool calls made**) may be re-run; the re-run and its reason are recorded in the report.
  - **(ii)** All 3 runs are **fixed and identical in configuration before the first executes** — same model, budgets, prompt, corpus, harness/matcher/baseline; seeds/temperature fixed at 0. No configuration change between runs; any change **voids the set and all 3 re-run**.
  - **(iii)** The headline is the **MEDIAN run, never the max.** Report all three; the figure quoted forward to Phase 4 and externally is the median. Union scoring is **rejected as headline**, but the union MAY be reported as a separate diagnostic labelled *"what the loop can find across 3 runs"* (genuinely informative about ceiling vs reliability — it just isn't the comparison number).
  - **(iv)** Variance is a **first-class result**, not a footnote. If the 3 runs disagree on **which** families unlock (e.g. 2 pass but on different families), that is **GO-WITH-CONCERNS, not a clean GO** — the loop is unreliable in a way Phase 4's fan-out amplifies. Pre-registered now so it can't be argued away later.
  - Per-run telemetry is recorded so the five signals become a **variance estimate rather than an anecdote** — most of the value of N=3 beyond the gate itself.

- **D-GO3: Recall gate on Llama 3.3 70B only; Qwen proves tool fidelity only.**
  - **(i) Rationale locked:** the frozen 0.071 baseline was produced on `databricks-meta-llama-3-3-70b-instruct`. Running the recall gate on a different model changes **two variables at once** (architecture AND model), so the result could not be attributed to becoming-an-agent — the only question Phase 3 exists to answer. **Baseline-matched is comparison validity, not convenience.**
  - **(ii) The Qwen fidelity probe has a pre-registered pass bar**, not just "reported": over a bounded multi-turn run on the same corpus, Qwen must **(a)** emit valid tool calls with schema-conformant args at **≥95% of turns** — `structured.py` coercion may fix type slips (e.g. the known `top_k`-as-string), but a call that **cannot** be repaired counts as a failure — and **(b)** produce **≥1 finding that passes the emit gate**, proving it can drive the full enumerate→fetch→emit chain, not just format a call. Otherwise "fidelity proven" is unfalsifiable.
  - **(iii)** The phase report records honestly that model-agnosticism is **PROVEN on the tool-fidelity axis and ASSERTED on the outcome axis.** Phase 4 inherits that as a **stated assumption, not a settled fact** — if Phase 4 fans out on Qwen for cost reasons it must first confirm outcome parity. Same discipline as the 3.2.S.5 item: name the untested assumption at the boundary instead of letting a later phase inherit it silently.

- **D-GO4: Score the frozen whole-set; report a single-agent-reachable breakout.** The reachable / structurally-unreachable split for **every** ground-truth item is classified and **committed to the repo before the first run** — classifying misses after seeing results is post-hoc rationalization wearing a diagnostic's clothes, the exact failure rider (iii) exists to prevent. Two readings pre-registered:
  - **(a)** If the gate **FAILS but every structurally-reachable item was found**, that is a **NO-GO on the loop's single-agent SCOPE, not on the architecture** — Phase 4's reference graph is the named next step and the report must say so.
  - **(b)** If the gate **PASSES**, the headline stays the **frozen whole-set figure**, never the reachable-subset figure, in the report and in anything quoted forward.

- **D-GO5: The pre-registration is a COMMITTED ARTIFACT** — otherwise D-GO1..D-GO4 are just intent. All gate decisions and riders are written to `.planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION.md` and **committed before the first spike run executes**, including the pre-classified reachable/unreachable split (D-GO4), the baseline median (D-LOOP2), and the frozen budget numbers (D-BUD1). Its **commit SHA is recorded in the phase report**, so gate criteria are provably timestamped ahead of results. **Amending it after any run begins voids the run set — re-run from scratch.**
  - **Sign-off:** the GO/NO-GO call is the **senior reviewer's**, made against the committed pre-registration. The executor **reports numbers and telemetry; it does not declare the verdict.**
  - **On a clean NO-GO:** Phases 4–6 do **not** auto-proceed. The phase closes with the telemetry-based diagnosis (which law broke — model tool-fidelity, grounding discipline, or budget starvation) and that determines the next move (different model / fix the loop / rethink the approach). A **reviewer decision at the gate, not a planned branch.**

### Spike telemetry — a NO-GO without a diagnosis wastes the spike

- **D-TEL1: Typed per-turn JSONL + per-run summary JSON.**
  - **(i) The summary carries PROVENANCE**, since it is the gate's evidence: run index (1..3), model id, the pre-registration file's **commit SHA**, harness/matcher/baseline versions, normalizer + serializer versions, corpus content-hash, and a **run-completed-vs-aborted flag with reason**. Without these a reviewer cannot prove the run was scored under rider (iii)'s frozen conditions — and an aborted run must be self-evidently distinguishable from a completed one, per D-GO2(i).
  - **(ii) Both artifacts are COMMITTED** to the phase directory alongside the report (3 runs = 3 JSONL + 3 summaries + the cross-run comparison), **not** left in a gitignored scratch dir. The verdict must be re-derivable from committed files by someone who did not watch the runs.

- **D-TEL2: Open reason-code registry exported from `src/tools/errors.py`.** A `KNOWN_REASON_CODES` mapping (code → one-line meaning) that tools and telemetry both reference; tools keep emitting **plain `str`**, preserving Phase 2's deliberate open design (*"plain str, NOT a closed Literal — later plans add codes without editing this file"*). Anything unrecognized lands in an **`unrecognized` bucket the summary flags loudly** rather than silently absorbing. A telemetry-side copy of the enum would drift from the gate and quietly mislabel the single most diagnostic signal available.

- **D-TEL3: Add a structured `half` field to `ToolRejected`** (`'submission' | 'rule' | ''`), populated by `emit_finding`; telemetry groups by `(reason_code, half)`. Purely additive to the Phase-2 schema — no existing `reason_code` changes, nothing changes in what the model sees. **Pre-registered reading: the two halves are OPPOSITE diagnoses and are reported SEPARATELY, never summed into one "rejections" count.**
  - `half=submission` + `not_byte_exact` ⇒ **SPAN INVENTION** (model fabricated or retyped a corpus quote). Grounding-discipline failure — the gate did its job; the loop is unreliable.
  - `half=rule` + `not_retrieved_this_session` ⇒ **NEVER CALLED `read_guideline`** (model asserted a rule without reading it). Loop-behavior failure — the enumerate→fetch→emit chain isn't being followed.
  - These imply **different NO-GO remedies** (different model vs fix the loop/prompt), so the summary reports the full matrix and the report's diagnosis section **must name which pattern dominated.** Part of the D-GO pre-registration.

- **D-TEL4: Llama gets the same ≥95% post-repair conformance bar as Qwen**, written into the pre-registration before the first run.
  - Record **PRE-repair and POST-repair malformed rates SEPARATELY.** Post-repair trips the flag; pre-repair is the honest measure of how much work `structured.py` is doing. **A loop at 95% post-repair but 40% pre-repair is a loop the fallback is carrying — that must be visible, not hidden behind a passing number.**
  - Below the floor ⇒ **GO-WITH-CONCERNS, never NO-GO**: recall remains the sole gate. A model-reliability finding is a **model-selection** decision (swap the model), not an architecture verdict — and Phase 4's fan-out amplifies it, so it must be surfaced loudly rather than silently absorbed.

- **D-TEL5: Continuation telemetry — the AGENT-04 signal.** The floor is unmeasured by D-TEL1..4 and is aimed squarely at the 2/28 recall failure, so it gets its own pre-registered reading. Record per run:
  - `continuation_count` (how many times the model tried to stop early)
  - `tokens_at_each_attempted_stop` (was it quitting at 20% of budget?)
  - `findings_before_vs_after_each_nudge` — **the decisive number**: did nudged turns produce **new grounded findings**, or just more tokens?
  - which **stop reason** ultimately ended the run (harness-owned taxonomy: `completed` / `ceiling` / `diminishing-returns` / `max-turns`)
  - **Per D-BUD4:** report `continuation_count` **against the permitted max** ("nudged 4 of a permitted 5") and record **which bound ended the nudging.**
  - **Pre-registered readings:** nudges yield new grounded findings ⇒ the anti-premature-stop mechanism **works and is load-bearing for recall**, report it as such. Nudges yield **zero** new findings across all runs ⇒ the model was genuinely done, the nudge burns budget, and AGENT-04 should be reconsidered in Phase 4 rather than carried forward on faith. `continuation_count = 0` across all runs ⇒ the model never tried to stop early, **the floor was never exercised and is UNPROVEN, not validated** — say so explicitly rather than claiming the mechanism works.

### Loop architecture

- **D-LOOP1: Hand-rolled turn loop + pydantic arg models per tool**, with `structured.py` as the repair path. This phase's deliverable **is** the budget/breaker/floor/telemetry machinery as code gates — owning the loop means owning exactly the code the gate measures, with nothing important living inside a framework's control flow. (PydanticAI is rated MEDIUM for adoption in `CLAUDE.md`; build-your-own is rated HIGH.)
  - **Ships BEHIND A FLAG with the existing `run_detection` path left runnable**, so the baseline and the agent loop execute **back-to-back on the same corpus** during the spike. If the old path is replaced outright, the comparison depends on a frozen number nobody can re-derive at gate time.

- **D-LOOP2: The baseline arm is re-run 3× under the same D-GO2 procedure; the MEDIAN governs.**
  - Both arms identical: N=3, temperature 0, frozen config, median as headline. **Arm asymmetry is what was rejected in union-vs-single scoring, and a single-draw control is the same error pointed the other way.**
  - The baseline re-run happens **BEFORE the agent runs**, and its median is **committed to the pre-registration as the governing reference**, with its commit SHA recorded. Rider (iii) is honored **in substance**: the reference is frozen before any agent result exists — **the sequence makes "re-baselining after seeing results" impossible.**
  - If the baseline median lands materially off the committed 0.071 — **pre-registered line: `|median − 0.071| > 0.03`** — that is itself a reportable **measurement-stability** finding, disclosed in the report, and the **senior reviewer confirms the new reference before the agent arm runs.**
  - Report the baseline's own variance (**min/median/max** across its 3 runs). If the single-shot detector swings widely, *"above baseline"* is a weaker claim than it looks, **and the gate reading must say so.**

- **D-LOOP3: Tool JSON schemas are DERIVED from the pydantic arg models** via `model_json_schema()`, reusing `structured.py`'s existing `_sanitize` / `schema_for_databricks` normalization. Single source of truth — same discipline as D-TEL2's registry: the schema the model is shown and the model that validates its reply **cannot drift apart, because they are the same object.**

- **D-LOOP4: Adopt COST-01's cache-stability invariant NOW and assert it with a test NOW.** System prompt and tool schemas stay **fully static**; corpus manifest, document counts, detected families and any rule enumeration go **in messages**. Ship the **cross-corpus byte-identical-prefix test** with the loop rather than waiting for Phase 6. Nearly free while the loop is being written; retrofitting means re-threading every dynamic value out of the prefix after three phases of code depend on it. Phase 6 SC1c warns that getting this wrong *"silently forfeits the entire caching lever."*

- **D-LOOP5: Rejection feedback is a TURN, not an exception.** A `ToolRejected` result is returned to the model **as the tool's result** — the typed, self-correcting message it reads and retries from — and it **CONSUMES A TURN** like any other. It never raises, never silently retries in code, never gets swallowed.
  - *Rationale:* the whole point of typed rejections (Claude Code's `FileEditTool.validateInput` errorCodes) is that the model reads the error and fixes its own call. **Rejections invisible to the model make the emit gate a wall instead of a teacher** — the agent would keep re-emitting the same fabricated quote with no idea why nothing lands. Counting the turn also keeps the budget honest (repair attempts are real work and must show in the token curve) and lets the circuit breaker see the repeated-identical-failing-call pattern.
  - **Corollary for D-TEL4's conformance measurement:** a call that is schema-invalid but **repaired by `structured.py` BEFORE dispatch** is *pre-repair-malformed* and does **NOT** consume a turn (it never reached the tool). A call that **dispatches and is then rejected by the gate DOES** consume a turn. **Different failure classes at different layers — the telemetry must not conflate them.**

### Budgets & stop rules

- **D-BUD1: Declared calibration run(s) first, then freeze.** Calibration executes on a **HELD-OUT corpus, NOT the scored eval set** — measuring consumption on the same documents the gate scores would mean seeing agent findings on scored data before freezing the criteria, the exact post-hoc contamination the pre-registration exists to prevent, arriving through the back door. **Consumption generalizes across corpora; findings do not**, so nothing is lost by calibrating elsewhere. Pre-register:
  - **(a)** the **multiple** applied to the observed median (e.g. ceiling = 3× median), chosen and written **BEFORE** calibration runs so the number cannot be tuned to a result;
  - **(b)** calibration runs are explicitly **not among the 3**, are disclosed in the report with their consumption figures, and their **findings are neither scored nor quoted**;
  - **(c)** if calibration reveals consumption so high that the pre-registered multiple is infeasible, **that is itself a reportable finding** — raise it to the reviewer before freezing, **never quietly lower the multiple.**

- **D-BUD2: "New grounded evidence" = new unique span-IDs retrieved OR new findings passing the emit gate.** A turn is productive if it surfaced span-IDs not previously issued this session, or landed a finding through the gate. Re-reading an already-retrieved span returns the COST-04 *"still current"* stub and counts as nothing — so an agent **circling over familiar evidence trips diminishing-returns**, while one **legitimately gathering before it emits does not.** Covers both halves of enumerate→investigate→emit. **This definition governs both AGENT-03's early stop and AGENT-04's nudge bound.**

- **D-BUD3: Circuit breaker trips on identical `(tool, args)` N times OR N consecutive rejections sharing the same `(reason_code, half)`.** The second condition catches the real pathology — a model that **varies its args slightly while making the same class of mistake** (e.g. repeatedly emitting submission-half `not_byte_exact` = it cannot stop inventing spans). Reuses the D-TEL3 matrix as the detection key, so **the breaker and the diagnosis speak the same language.**

- **D-BUD4: Nudge bounds are DR-bounded + a pre-registered hard max continuation count, ORed — whichever fires first.** Neither replaces the other: **DR is the productivity signal, the cap is the anti-gaming backstop** against an agent dripping one trivial-but-novel span per turn to stay under the DR threshold forever. D-TEL5 amended accordingly: report `continuation_count` against the permitted max, and **record which bound ended the nudging** — hitting the **DR bound** means the model was genuinely finished and the floor was correctly permissive; hitting the **hard cap** means the model was producing just enough novelty to keep being nudged, **a different and more troubling behavior that Phase 4's fan-out would multiply.**

- **D-BUD5: The budget is PER-RUN, not per-document, and counts input + output across every turn INCLUDING tool results.** Wall-clock includes tool execution time.
  - **Per-run** because it is the recall mechanism's denominator: AGENT-04's floor asks *"is this agent still under budget for the whole review?"*, and a per-document budget would let an agent **exhaust itself on document 1 and skim the rest — reproducing the 2/28 ceiling by a different route, while each document individually looked well-behaved.** It also makes the loop's own triage decisions (which documents deserve depth) real rather than pre-empted by an even split.
  - **Tool results count** because they are the dominant token cost in a retrieval loop — excluding them makes the ceiling meaningless and the D-TEL1 budget curve unreadable. Wall-clock includes tool execution for the same reason: the ceiling bounds **real elapsed cost**, not model-thinking time alone.
  - **Corollary:** D-BUD1's calibration must measure consumption over a **FULL multi-document review** on the held-out corpus, **not a single document extrapolated.**

- **D-BUD6: SC3's runaway load test = synthetic in CI + one real-model confirmation.** A **synthetic forced-runaway driver** (never emits a stop, always requests more evidence) runs against the **real loop and real `src/tools` functions** — deterministic, offline, CI-runnable under D-RB6's no-Databricks contract, zero LLM spend, and it exercises exactly what SC3 claims (ceiling trips, grounded partial returned, no crash, no overspend). *A code gate deserves a test that cannot be flaky for model reasons.* **Plus** one real-model execution with a deliberately low ceiling during the spike, to confirm the gate behaves identically under a real tool-calling model — **declared as not among the 3.**

### Oracle demotion & the Phase-2 entry gate

- **D-ORC1: The seed pass is a callable `run_oracles` TOOL the agent invokes** (a 7th tool), returning annotated leads. Span-IDs are issued through the **identical path as every other tool result**, so ledger semantics need no special case — **an oracle lead becomes just another tool result, which is what "demoted to a seed" means structurally.** The system prompt may direct the agent to start there. This replaces today's `pipeline.py` behavior, where `run_oracles(doc) → list[Fault]` with `evidence_class=CODE_VERIFIED` flows straight into `verify_and_tier(oracle_faults + checklist_faults + agent_faults, doc)` — findings that never pass any gate, breaking GROUND-01/03's *"every finding"* claim.

- **D-ORC2: NEVER pre-record oracle spans into the `RetrievalLedger`.** The agent must **re-open each lead** (`get_section` / `open_doc`) before `emit_finding` will accept it. `was_issued()` keeps meaning exactly what it says: *the model actually saw this text rendered in a result.* **That re-read cost IS the demotion** — it makes oracle output evidence to investigate rather than a finding to rubber-stamp, and keeps D-TEL3's `not_retrieved_this_session` signal free of blind spots.
  - **Pre-registered telemetry — oracle-lead conversion:** how many leads `run_oracles` surfaced, how many the agent actually **re-opened**, and how many became findings that **passed the emit gate.** A **low re-open rate** means the agent is ignoring deterministic leads (**recall lost to demotion — report it plainly**); a **high re-open-but-low-emit rate** means the oracles are surfacing noise. Either reading is actionable at the gate. **Without the metric, "we demoted the oracles" is an architectural claim with no evidence attached.**

- **D-VER1: The existing verify/challenge passes do NOT run over agent findings in Phase 3.** The loop's grounded findings go into `FaultReport` **directly**. `verify.py`'s anchor/tier/dedup and `challenge.py` were built for the single-shot detector and **can DROP findings** — a dropped finding would silently depress the recall number the gate is reading, and a **legacy filter's failure would be attributed to the loop.** Running them would also violate **EVAL-03's zero-true-positives-lost discipline inside the very measurement that decides Phases 4–6.** The emit gate is already the grounding filter (TOOLS-03); Phase 5's verifier is the **designed successor** to `challenge.py`. **If any legacy pass IS retained for tiering metadata, it must be provably non-dropping — assert it in a test, do not assume it.**

- **D-VER2: DETECT-04's compliance verdict is an ENUMERATED field, not free text** (e.g. `violation` / `gap` / `ambiguous` — exact set is the planner's call). Free text cannot be scored deterministically by the harness, compared across the 3 runs, or diffed against the baseline — **the same reason the reason-code registry is enumerated.** It travels **beside** `rule_span_id`, which remains the grounding.

- **D-PRE1: The Phase-2 preconditions become Wave-1 plans inside Phase 3**, with the ordering encoded in `depends_on` rather than implied by wave numbering. **Strict sequence:**

  > **P2** (`src/parse/pdf.py` embedded-text fix) → **P1** (real-ingestion 3.2.S.5 classification proof) → **boundary-crossing code-review hunt** → **D-LOOP2 3-run baseline re-measurement** → **commit the pre-registration** → **the 3 agent runs.**

  - **P2 before P1** because the 3.2.S.5 classification signal **may sit on the very scanned pages P2 recovers** — proving classification against text `pdf.py` currently discards would prove the wrong thing.
  - **Baseline re-measurement AFTER both** because P2 changes parse output and therefore **the number being frozen**; re-baselining before the fix would freeze a figure the fix immediately invalidates.
  - **(a)** If P2 shifts the `recall_by_family` baseline, **that shift is disclosed in the phase report and attributed to the parse fix — not to the agent, and not silently absorbed.**
  - **(b)** The **boundary-crossing hunt is an executor plan with a concrete deliverable**: a written list of `enumerate→X` / `classify→Y` / `build→Z` chains that are unit-tested on each side but **never composed on real data**, plus a **composition test for each one found** — so it cannot pass as *"we looked and it seemed fine."* (3 such chains were found in Phase 2.)

### Claude's Discretion (within the locked contracts)

- **System-prompt wording** — the reviewer persona and the enumerate→investigate→emit workflow instructions are prompt-craft to iterate on. Bounded by D-LOOP4 (prefix must stay static and cache-stable) and by "budgets are code gates, never prompt instructions."
- **Held-out calibration corpus** — the existing `spec32s41` held-out document is the default choice. **If the planner finds it insufficient for a full multi-document consumption measurement (D-BUD5's corollary), FLAG it rather than substituting scored data.**
- **The concrete N values** — circuit-breaker repeat count, diminishing-returns consecutive-turn count, hard max continuation count, and the calibration multiple. All are the planner's to propose, but **every one must land in the committed pre-registration before run 1** (D-GO5).
- **The verdict enum's exact members** (D-VER2), the loop's module path, and the flag mechanism (config vs CLI vs env).
- **Where the grounded partial surfaces** in `FaultReport` and how loop progress reaches the existing `event_bus`/WebSocket UI.
- Whether `S9`/`S10`/`P10` live in `oracles.py` or `checklists.py` today — the roadmap names them as oracles; the code splits deterministic checks across both files. Resolve during research/planning.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase governance
- `.planning/ROADMAP.md` — Phase 3 goal + Success Criteria 1, 2, 3, **3b** (bidirectional budget), 4, 5; the Research flag (per-model tool-call reliability over long loops is the go/no-go unknown); Phase 4/5/6 boundaries this phase must not cross.
- `.planning/REQUIREMENTS.md` — **this phase:** AGENT-01, AGENT-03, **AGENT-04** (line 38 — full text with the Claude Code `token_budget_continuation` precedent), GROUND-01, GROUND-03, DETECT-03, DETECT-04. **Downstream:** AGENT-02/DETECT-01/02/05 (Phase 4), GROUND-02 (Phase 5), COST-01/02/03 (Phase 6). Out of Scope table (anti-features).
- `.planning/PROJECT.md` — Key Decisions (grounding-mandatory; guidelines-as-reference-not-oracles; cost via caching/compaction/triage/budgets). **"Known debt to avoid inheriting":** README/PHASES/DIAGNOSIS/RELIABILITY/PIPELINE describe a **removed** AutoGen design — do not trust their file refs.
- `.planning/phases/02-retrieval-navigation-tools-rulebook/02-PHASE-VERIFICATION-QUEUE.md` — **the P1/P2 entry gate D-PRE1 encodes.** P1 = 3.2.S.5 real-ingestion classification proof; P2 = `src/parse/pdf.py` drops the embedded text layer on OCR-less scanned pages (SC4 7/12); code-review 2 = the un-crossed-boundary hunt.
- `.planning/phases/02-retrieval-navigation-tools-rulebook/02-CONTEXT.md` — the tool contracts this loop calls: **D-EF1** (dual byte-exact grounding, span-IDs on both halves, typed rejections), **D-GRAN** (agent selects issued IDs, never computes offsets), **D-RI2** (`read_guideline` enumerate-vs-fetch on one optional `citation` param — *"the Phase-3 Llama/Qwen go/no-go tests exactly this call pattern"*), **D-FR** (`follow_reference` typed `cross_document_resolution_pending_phase_4`), **D-RB6** (offline contract), **D-SC4** (retrieval ratchet).
- `.planning/phases/01-ingestion-foundation/01-CONTEXT.md` — the span-anchor substrate (D-18..D-32).

### The Claude Code precedents this phase implements
- `.planning/research/CLAUDE-CODE-TEARDOWN.md` — the loop layers; source of AGENT-04's `token_budget_continuation` precedent (`query.ts:1338` + `utils/tokenBudget.ts:72` — *"Keep working — do not summarize"*) and of D-LOOP5's `FileEditTool.validateInput` typed-errorCode pattern.
- `.planning/research/ARCHITECTURE.md` — drive-loop design over an **extended** `llm/client.py` (tool-call turn handling); OpenAI-compatible `tools`/`tool_calls` **verified available** on Databricks FM APIs (Llama 3.3 70B, 128k ctx) and Ollama (Qwen 3/2.5, Llama 3.x) — **the availability probe is settled; long-loop fidelity is not.**
- `.planning/research/PITFALLS.md` — citation hallucination in agentic loops (the model reconstructs a passage from 20 calls ago rather than re-opening it); hard code-enforced ceilings and the circuit breaker on repeated/failing calls.

### The tool layer the loop drives (Phase 2 deliverables — do not reinvent)
- `src/tools/emit_finding.py` — the **only** path a finding can exist; dual span-ID re-open + store-membership validation. **D-TEL3 adds the `half` field here.**
- `src/tools/errors.py` — `ToolRejected` sentinel; `reason_code` deliberately open `str`. **D-TEL2 adds `KNOWN_REASON_CODES` here; D-TEL3 adds `half`.**
- `src/tools/ledger.py` — `RetrievalLedger`: `record_span` / `was_issued` (D-GRAN issuance) + `check_and_mark_served` / `dedup_hit_rate` (COST-04). **D-ORC2 turns on `was_issued`'s meaning; `dedup_hit_rate()` is a D-TEL1 signal.**
- `src/tools/get_section.py`, `open_doc.py`, `search_corpus.py`, `read_guideline.py`, `follow_reference.py` — the five navigation tools; `oversized.py` (TOOLS-04 persist/preview/handle), `textsplit.py` (span annotation).

### The code Phase 3 extends or replaces
- `src/llm/client.py` — **has NO tool support today**: `chat_completion_full` takes no `tools=` and returns only `content` + `finish_reason`. Needs a tool-call turn entry point; **keep its retry/backoff/rate-limit handling.**
- `src/llm/structured.py` — `schema_for_databricks` / `_sanitize` / `build_response_format` (**reused by D-LOOP3 for tool-schema derivation**) and the malformed-arg repair path (D-GO3(ii), D-TEL4).
- `src/agents/detection/pipeline.py` — `run_detection`; **line 86** `verify_and_tier(oracle_faults + checklist_faults + agent_faults, doc)` is the union D-ORC1/D-VER1 dismantle. **Left runnable behind the flag (D-LOOP1).**
- `src/agents/detection/oracles.py` + `checklists.py` — the deterministic checks becoming `run_oracles`-the-tool.
- `src/agents/detection/verify.py`, `challenge.py` — **excluded from the agent path by D-VER1** (they can drop findings).
- `src/parse/pdf.py` — **P2's target** (discards `page.get_text("text")` on OCR-less scanned pages).
- `src/schemas/faults.py` — `Fault`, `EvidenceClass`, tiering; **D-VER2's enumerated verdict field.**
- `src/config.py` — `DETECTOR_MODELS` allow-list (`databricks-meta-llama-3-3-70b-instruct`, `databricks-qwen35-122b-a10b`, `databricks-qwen3-next-80b-a3b-instruct`); `detector_model` default is the **baseline-matched Llama** (D-GO3).

### The measurement instrument
- `src/evals/baseline/recall_by_family.json` — **the frozen reference**: overall recall **0.071**, precision 0.074, tp=2 / fp=25 / fn=26, anchor_rate 0.581, `found_set ["C-01","C-02"]`, `recall_by_family {absence_of_evidence 0.0, derivation_plausibility 0.0, cross_reference_integrity 0.286, regulatory_framing 0.0}`. **Note: it does not record which model produced it — D-LOOP2's re-measurement closes that gap.**
- `src/evals/baseline/retrieval_recall.json` — SC4 ratchet: overall recall@k 0.875, exact-identifier subset 0.643 (mvr1381 7/12 — **P2's target**).
- `src/evals/run.py`, `metrics.py`, `match.py`, `gate.py`, `schema.py` — the harness/matcher whose **versions rider (iii) freezes**.
- `src/evals/dataset/golden/mvr1381_run3.json`, `minispec_run1.json` — the scored set. **`spec32s41` is held-out and is D-BUD1's default calibration corpus.**

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`src/llm/client.py`'s resilience layer** — retry/backoff, `Retry-After` handling, rate-limit escalation, and the `BadRequestError`→drop-`response_format` graceful degradation are all worth keeping; the loop needs a **tool-call turn handler added, not a new client.**
- **`src/llm/structured.py`'s `schema_for_databricks` / `_sanitize`** — already normalizes pydantic JSON schemas for these exact endpoints. **D-LOOP3 derives tool schemas through it**, so tool schemas get the same endpoint-compatibility treatment structured outputs already have.
- **`src/tools/ledger.py`'s `dedup_hit_rate()`** — a telemetry signal that already exists; D-TEL1 reads it rather than recomputing.
- **`ToolRejected`'s `hint` field** — the self-correction affordance D-LOOP5 depends on; the loop just has to render it back to the model as a tool result.
- **`src/evals/run.py`'s "import the library, record, never crash" shape** — the model for the spike harness and the committed run artifacts.

### Established Patterns
- **Typed sentinel returns, never exceptions, at the tool boundary** (`ToolRejected` mirrors `ParseFailed`) — D-LOOP5 extends this into the loop: a rejection is a *message to the model*, not a stack unwind.
- **Code gate first, LLM on top** (loader gates, emit gate, oracle-before-specialist) — Phase 3 applies it to *stopping*: budgets, breaker, DR, and the AGENT-04 floor are all code, never prompt.
- **Declared capability boundary, never a fake result** (D-30, D-FR) — the loop must treat `cross_document_resolution_pending_phase_4` as an **honest boundary**, not a tool failure, and must not retry it.
- **Content-addressed, version-stamped grounding** — extends into telemetry provenance (D-TEL1: normalizer + serializer versions, corpus content-hash).
- **Offline / no-external-dependency in CI** (D-RB6) — D-BUD6's synthetic load test and D-LOOP4's prefix test both live inside that contract.

### Integration Points
- **`pipeline.py` `run_detection`** — the flag seam (D-LOOP1). The old union at line 86 is what D-ORC1/D-VER1 replace on the agent path only; the legacy path stays intact for the baseline arm.
- **`src/tools/__init__.py`** — where `run_oracles`-the-tool registers as the 7th tool (D-ORC1).
- **`src/tools/errors.py`** — the single file both D-TEL2 (`KNOWN_REASON_CODES`) and D-TEL3 (`half`) touch; **additive only**, no existing `reason_code` values change.
- **`event_bus` / WebSocket** — existing UI contract; agent-step events (tool calls, budget consumption, continuations) extend it.
- **The phase directory itself** is an integration point this time: `03-GO-NOGO-PREREGISTRATION.md`, 3 run JSONLs, 3 summaries, and the cross-run comparison are **committed deliverables**, not scratch output.

</code_context>

<specifics>
## Specific Ideas

- **"An un-diagnosed NO-GO wastes the spike."** The framing that produced the whole telemetry area: a gate result without a diagnosis cannot tell you whether to swap the model, fix the loop, or abandon the approach — so the five signals are as much the deliverable as the number.
- **`not_byte_exact` vs `not_retrieved_this_session` = span invention vs ledger miss.** Two codes that look like one "rejections" statistic but point at opposite diseases and opposite remedies — the reason D-TEL3 forbids summing them.
- **"The emit gate must teach, not wall"** (D-LOOP5) — the argument for surfacing rejections to the model and charging them a turn.
- **"2/28 by a different route"** (D-BUD5) — why a per-document budget is dangerous: it reproduces the baseline's recall ceiling while every individual document looks well-behaved.
- **"Consumption generalizes across corpora; findings do not"** (D-BUD1) — the precise reason calibration on a held-out corpus costs nothing and calibration on scored data would be contamination.
- **"Baseline-matched is not a convenience, it is the comparison's validity"** (D-GO3(i)) — changing model and architecture together makes the result unattributable.
- **"The sequence makes re-baselining after seeing results impossible"** (D-LOOP2) — process design as an integrity guarantee, rather than a rule someone must remember to follow.
- **The `cat -n` lineage** — D-GRAN's "cite IDs you can SEE" carries into the loop unchanged; the model never computes an offset, and `emit_finding` accepts only ledger-issued IDs.
- **The Claude Code continuation string** — `"Stopped at {pct}% of token target. Keep working — do not summarize."` is the verbatim precedent AGENT-04 implements in code.

</specifics>

<deferred>
## Deferred Ideas

- **Orchestrator + sub-agent fan-out** (AGENT-02) — Phase 4. Several decisions here are explicitly written to hand Phase 4 a *stated assumption* rather than a silent inheritance: D-GO3(iii) outcome-parity on Qwen, D-GO4(a) single-agent scope, D-GO2(iv) family-disagreement variance, D-BUD4's hard-cap reading.
- **Cross-document reference graph / full `follow_reference`** — Phase 4; the typed pending-result stays a boundary this phase respects.
- **Adversarial verifier** (GROUND-02) — Phase 5, the designed successor to `challenge.py` that D-VER1 removes from the agent path.
- **Prompt-cache hardening, compaction, cheap-model triage** (COST-01/02/03) — Phase 6. D-LOOP4 pre-pays only the cache-*stability* invariant, because retrofitting it later is expensive; the caching itself is not built here.
- **Precedent-search as an agent tool** — deferred pending Phase-3 evidence (Phase 2 D-RB3); nothing in this phase depends on it.
- **Reconsidering AGENT-04 itself** — D-TEL5 pre-registers the reading under which the nudge is judged to burn budget rather than buy recall; that verdict lands in Phase 4, not here.
- **Reranker (`bge-reranker-v2-m3`)**, **multi-hop GraphRAG**, **Git LFS for `rulebook/**`**, **rulebook FAISS dense rebuild** — carried Phase-2 hygiene/optional items, non-blocking.

None of the above are scope creep — each was raised, bounded, and consciously placed.

</deferred>

---

*Phase: 03-drive-loop-spike-go-no-go*
*Context gathered: 2026-08-01*
