# Phase 3: Drive-Loop Spike (GO/NO-GO) - Research

**Researched:** 2026-08-01
**Repo HEAD at research time:** `9b68856`
**Domain:** Model-driven tool loop over OpenAI-compatible Databricks FM APIs; code-enforced budgets; grounded finding emission; pre-registered measurement
**Confidence:** HIGH on code reconnaissance (read directly), HIGH on Databricks tool-calling constraints (vendor docs, verbatim), MEDIUM on long-loop degradation magnitude (published evidence is directional, not model-specific), HIGH on the measurement-instrument findings (computed from the committed dataset)

---

## Summary

Three findings reframe this phase, and each one changes what the plan must contain.

**First: the vendor documents the go/no-go risk.** Databricks' own function-calling page states verbatim: *"During Public Preview, function calling on Databricks is optimized for single turn function calling"* and *"For multi-turn function calling Databricks recommends the supported Claude models."* [CITED: docs.databricks.com/aws/en/machine-learning/model-serving/function-calling]. The same page prohibits `anyOf`/`oneOf`/`allOf`/`$ref`/`prefixItems` in tool schemas, caps JSON-schema keys at 16, caps tools at 32, and states *"Parallel function calling is not supported."* The ROADMAP's research flag is therefore not speculative — the platform's own guidance says the thing Phase 3 is chartered to test is outside its optimized envelope. That does not predict failure (the project's settled 2026-07-30 probe showed clean single tool-calls on every served model), but it does mean **the pre-registration must treat a long-loop fidelity failure as a plausible, named outcome with a diagnosis path already wired** — which is exactly what D-TEL1..5 buy.

**Second: the measurement instrument caps what any architecture can score.** Five of `mvr1381`'s 28 ground-truth items produce **zero matchable tokens** under `src/evals/match.py:88-92` and are permanent false negatives for *any* system: `A-07` (`'0.5%'`), `B-03` (`'389'`), `B-06` (`'485'`), `C-03` (`'ND'`), `D-01` (`'45, 56'`). Maximum achievable overall recall on the scored document is **23/28 = 0.821**, and `cross_reference_integrity` maxes out at **4/7 = 0.571** against a baseline already at 2/7. The two zero-families with a clean path — `derivation_plausibility` (5/5 matchable) and `regulatory_framing` (5/5 matchable) — are the cheapest routes to D-GO1(a); the headline `absence_of_evidence` family is 9/11 matchable, so D-GO1(iii)'s named expectation is reachable but not free. D-GO4 asks for a reachable/unreachable classification committed before run 1; this research supplies a **third bucket CONTEXT.md did not anticipate — matcher-unreachable** — which must be separated from single-agent-scope-unreachable or the diagnosis will blame the loop for a regex floor.

**Third: two silent-corruption seams sit directly on the critical path.** (a) `cache_key()` (`src/ingest/store.py:35-39`) folds in `NORMALIZER_VERSION` and `SERIALIZER_VERSION` but **not any parser version**, and `content_hash` is a hash of the *file bytes* (`src/ingest/corpus.py:119`) — so P2's `pdf.py` fix changes canonical text and every span offset while the cache key stays identical, and six stale entries are sitting in `data/ingest_cache/` right now. (b) The agent expresses span-IDs as strings (`[doc_id:start:end]`, the only form tools render) but `emit_finding` needs a full `SpanID` including `hash`; a loop-side re-mint bug produces `not_byte_exact` with `half='submission'` — which D-TEL3 pre-registers to read as **SPAN INVENTION by the model**. A loop bug would masquerade as a model grounding failure and produce a *wrong NO-GO*. Both need composition tests, not unit tests.

**Primary recommendation:** Build the loop as a new `src/agents/review/` package (loop / budget / telemetry / registry / prompts) driven through a **dependency-injected completion callable**, with span-IDs as **flat strings** in tool args (never nested `SpanID` models — `$ref` is prohibited by Databricks), all-required tool parameters wherever the locked contracts allow, and a per-turn record of `usage.prompt_tokens/completion_tokens/prompt_tokens_details.cached_tokens`. Land the four offline test harnesses (scripted client, forced-runaway driver, byte-identical-prefix assertion, span-ID round-trip composition test) in Wave 0, before any live run.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**GO/NO-GO gate — the pre-registered pass condition**

- **D-GO1: Family-unlock + zero-TP-lost.** GO requires **(a)** ≥1 currently-zero family (`absence_of_evidence`, `derivation_plausibility`, `regulatory_framing`) moves off 0.0 with ≥1 **grounded** true positive, **AND (b)** the baseline `found_set` `{C-01, C-02}` is not lost. Riders:
  - **(i) Derived consequence recorded, not re-litigated.** (a)+(b) jointly imply overall recall strictly above baseline (keeping both plus ≥1 new grounded TP ⇒ tp≥3 > 2). No separate overall-recall clause — but write the arithmetic down so nobody asks "but did overall move?" after the run.
  - **(ii) Precision is REPORTED, never gated**, with one named flag: fp count and precision are recorded beside the gate result, and **fp > 125 (5× the baseline's 25) ⇒ GO-WITH-CONCERNS**, read by the reviewer before Phase 4 — *not* a NO-GO. Grounded-but-irrelevant is Phase 5's job (D-EF1(4)); but emit-spam is also a signal the loop isn't reasoning, so it gets a flag instead of invisibility.
  - **(iii) Measurement integrity, frozen now.** The GO run is scored by the **same harness, matcher version, and committed baseline** that produced 0.071. Any matcher/harness change invalidates the comparison and requires re-baselining **BEFORE the spike, never after.** `absence_of_evidence` is the **named headline expectation** (the requirement index exists for it; P1 guarantees its entries can fire) — any zero-family unlock passes the gate, but the report **must state specifically whether absence moved**, because a pass while absence stays 0/11 means the mechanism built for it did not work and Phase 4 needs to know.

- **D-GO2: N=3 runs, ≥2 must pass, variance reported.** Riders:
  - **(i)** A failed/errored run is a **FAILING run, not a re-roll** — provider error, budget exhaustion, or crash counts against the ≥2. **Sole declared exception:** an infrastructure fault wholly outside the loop (endpoint 5xx / auth expiry with **zero tool calls made**) may be re-run; the re-run and its reason are recorded in the report.
  - **(ii)** All 3 runs are **fixed and identical in configuration before the first executes** — same model, budgets, prompt, corpus, harness/matcher/baseline; seeds/temperature fixed at 0. No configuration change between runs; any change **voids the set and all 3 re-run**.
  - **(iii)** The headline is the **MEDIAN run, never the max.** Report all three; the figure quoted forward to Phase 4 and externally is the median. Union scoring is **rejected as headline**, but the union MAY be reported as a separate diagnostic labelled *"what the loop can find across 3 runs."*
  - **(iv)** Variance is a **first-class result**. If the 3 runs disagree on **which** families unlock, that is **GO-WITH-CONCERNS, not a clean GO**.
  - Per-run telemetry is recorded so the five signals become a **variance estimate rather than an anecdote**.

- **D-GO3: Recall gate on Llama 3.3 70B only; Qwen proves tool fidelity only.**
  - **(i) Rationale locked:** the frozen 0.071 baseline was produced on `databricks-meta-llama-3-3-70b-instruct`. Running the recall gate on a different model changes **two variables at once**. **Baseline-matched is comparison validity, not convenience.**
  - **(ii) The Qwen fidelity probe has a pre-registered pass bar:** over a bounded multi-turn run on the same corpus, Qwen must **(a)** emit valid tool calls with schema-conformant args at **≥95% of turns** — `structured.py` coercion may fix type slips, but a call that **cannot** be repaired counts as a failure — and **(b)** produce **≥1 finding that passes the emit gate**.
  - **(iii)** The phase report records honestly that model-agnosticism is **PROVEN on the tool-fidelity axis and ASSERTED on the outcome axis.** Phase 4 inherits that as a **stated assumption, not a settled fact.**

- **D-GO4: Score the frozen whole-set; report a single-agent-reachable breakout.** The reachable / structurally-unreachable split for **every** ground-truth item is classified and **committed to the repo before the first run**. Two readings pre-registered:
  - **(a)** If the gate **FAILS but every structurally-reachable item was found**, that is a **NO-GO on the loop's single-agent SCOPE, not on the architecture** — Phase 4's reference graph is the named next step and the report must say so.
  - **(b)** If the gate **PASSES**, the headline stays the **frozen whole-set figure**, never the reachable-subset figure.

- **D-GO5: The pre-registration is a COMMITTED ARTIFACT.** All gate decisions and riders are written to `.planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION.md` and **committed before the first spike run executes**, including the pre-classified reachable/unreachable split (D-GO4), the baseline median (D-LOOP2), and the frozen budget numbers (D-BUD1). Its **commit SHA is recorded in the phase report**. **Amending it after any run begins voids the run set — re-run from scratch.**
  - **Sign-off:** the GO/NO-GO call is the **senior reviewer's**. The executor **reports numbers and telemetry; it does not declare the verdict.**
  - **On a clean NO-GO:** Phases 4–6 do **not** auto-proceed. The phase closes with the telemetry-based diagnosis (which law broke — model tool-fidelity, grounding discipline, or budget starvation).

**Spike telemetry**

- **D-TEL1: Typed per-turn JSONL + per-run summary JSON.**
  - **(i) The summary carries PROVENANCE:** run index (1..3), model id, the pre-registration file's **commit SHA**, harness/matcher/baseline versions, normalizer + serializer versions, corpus content-hash, and a **run-completed-vs-aborted flag with reason**.
  - **(ii) Both artifacts are COMMITTED** to the phase directory alongside the report (3 runs = 3 JSONL + 3 summaries + the cross-run comparison). The verdict must be re-derivable from committed files by someone who did not watch the runs.

- **D-TEL2: Open reason-code registry exported from `src/tools/errors.py`.** A `KNOWN_REASON_CODES` mapping (code → one-line meaning) that tools and telemetry both reference; tools keep emitting **plain `str`**. Anything unrecognized lands in an **`unrecognized` bucket the summary flags loudly**.

- **D-TEL3: Add a structured `half` field to `ToolRejected`** (`'submission' | 'rule' | ''`), populated by `emit_finding`; telemetry groups by `(reason_code, half)`. Purely additive. **Pre-registered reading: the two halves are OPPOSITE diagnoses and are reported SEPARATELY, never summed.**
  - `half=submission` + `not_byte_exact` ⇒ **SPAN INVENTION**. Grounding-discipline failure.
  - `half=rule` + `not_retrieved_this_session` ⇒ **NEVER CALLED `read_guideline`**. Loop-behavior failure.
  - The report's diagnosis section **must name which pattern dominated.**

- **D-TEL4: Llama gets the same ≥95% post-repair conformance bar as Qwen.** Record **PRE-repair and POST-repair malformed rates SEPARATELY.** **A loop at 95% post-repair but 40% pre-repair is a loop the fallback is carrying — that must be visible.** Below the floor ⇒ **GO-WITH-CONCERNS, never NO-GO.**

- **D-TEL5: Continuation telemetry — the AGENT-04 signal.** Record per run: `continuation_count`; `tokens_at_each_attempted_stop`; `findings_before_vs_after_each_nudge` (**the decisive number**); which **stop reason** ended the run (`completed` / `ceiling` / `diminishing-returns` / `max-turns`); **per D-BUD4** report `continuation_count` **against the permitted max** and record **which bound ended the nudging.**
  - **Pre-registered readings:** nudges yield new grounded findings ⇒ mechanism **works and is load-bearing.** Nudges yield **zero** new findings across all runs ⇒ the nudge burns budget; reconsider AGENT-04 in Phase 4. `continuation_count = 0` across all runs ⇒ **the floor was never exercised and is UNPROVEN, not validated.**

**Loop architecture**

- **D-LOOP1: Hand-rolled turn loop + pydantic arg models per tool**, with `structured.py` as the repair path. **Ships BEHIND A FLAG with the existing `run_detection` path left runnable**, so the baseline and the agent loop execute **back-to-back on the same corpus** during the spike.
- **D-LOOP2: The baseline arm is re-run 3× under the same D-GO2 procedure; the MEDIAN governs.** The baseline re-run happens **BEFORE the agent runs**, and its median is **committed to the pre-registration as the governing reference**, with its commit SHA recorded. **Pre-registered line: `|median − 0.071| > 0.03`** ⇒ reportable **measurement-stability** finding, disclosed, and the **senior reviewer confirms the new reference before the agent arm runs.** Report the baseline's own variance (**min/median/max**).
- **D-LOOP3: Tool JSON schemas are DERIVED from the pydantic arg models** via `model_json_schema()`, reusing `structured.py`'s existing `_sanitize` / `schema_for_databricks` normalization. Single source of truth.
- **D-LOOP4: Adopt COST-01's cache-stability invariant NOW and assert it with a test NOW.** System prompt and tool schemas stay **fully static**; corpus manifest, document counts, detected families and any rule enumeration go **in messages**. Ship the **cross-corpus byte-identical-prefix test** with the loop.
- **D-LOOP5: Rejection feedback is a TURN, not an exception.** A `ToolRejected` result is returned to the model **as the tool's result** and it **CONSUMES A TURN**. It never raises, never silently retries in code, never gets swallowed.
  - **Corollary for D-TEL4:** a call schema-invalid but **repaired by `structured.py` BEFORE dispatch** is *pre-repair-malformed* and does **NOT** consume a turn. A call that **dispatches and is then rejected by the gate DOES** consume a turn.

**Budgets & stop rules**

- **D-BUD1: Declared calibration run(s) first, then freeze.** Calibration executes on a **HELD-OUT corpus, NOT the scored eval set.** Pre-register: **(a)** the **multiple** applied to the observed median, chosen and written **BEFORE** calibration runs; **(b)** calibration runs are explicitly **not among the 3**, are disclosed with their consumption figures, and their **findings are neither scored nor quoted**; **(c)** if calibration reveals consumption so high that the pre-registered multiple is infeasible, **that is itself a reportable finding** — raise it to the reviewer, **never quietly lower the multiple.**
- **D-BUD2: "New grounded evidence" = new unique span-IDs retrieved OR new findings passing the emit gate.** Re-reading an already-retrieved span returns the COST-04 stub and counts as nothing. **This definition governs both AGENT-03's early stop and AGENT-04's nudge bound.**
- **D-BUD3: Circuit breaker trips on identical `(tool, args)` N times OR N consecutive rejections sharing the same `(reason_code, half)`.** Reuses the D-TEL3 matrix as the detection key.
- **D-BUD4: Nudge bounds are DR-bounded + a pre-registered hard max continuation count, ORed — whichever fires first.** Report `continuation_count` against the permitted max, and **record which bound ended the nudging.**
- **D-BUD5: The budget is PER-RUN, not per-document, and counts input + output across every turn INCLUDING tool results.** Wall-clock includes tool execution time. **Corollary:** D-BUD1's calibration must measure consumption over a **FULL multi-document review** on the held-out corpus, **not a single document extrapolated.**
- **D-BUD6: SC3's runaway load test = synthetic in CI + one real-model confirmation.** A **synthetic forced-runaway driver** runs against the **real loop and real `src/tools` functions** — deterministic, offline, CI-runnable under D-RB6. **Plus** one real-model execution with a deliberately low ceiling, **declared as not among the 3.**

**Oracle demotion & the Phase-2 entry gate**

- **D-ORC1: The seed pass is a callable `run_oracles` TOOL the agent invokes** (a 7th tool), returning annotated leads. Span-IDs are issued through the **identical path as every other tool result.** This replaces today's `pipeline.py` behavior.
- **D-ORC2: NEVER pre-record oracle spans into the `RetrievalLedger`.** The agent must **re-open each lead** before `emit_finding` will accept it. **That re-read cost IS the demotion.**
  - **Pre-registered telemetry — oracle-lead conversion:** how many leads surfaced, how many the agent **re-opened**, how many became findings that **passed the emit gate.**
- **D-VER1: The existing verify/challenge passes do NOT run over agent findings in Phase 3.** The loop's grounded findings go into `FaultReport` **directly**. **If any legacy pass IS retained for tiering metadata, it must be provably non-dropping — assert it in a test, do not assume it.**
- **D-VER2: DETECT-04's compliance verdict is an ENUMERATED field, not free text** (e.g. `violation` / `gap` / `ambiguous` — exact set is the planner's call). It travels **beside** `rule_span_id`.
- **D-PRE1: The Phase-2 preconditions become Wave-1 plans inside Phase 3**, ordering encoded in `depends_on`. **Strict sequence:** **P2** (`src/parse/pdf.py` embedded-text fix) → **P1** (real-ingestion 3.2.S.5 classification proof) → **boundary-crossing code-review hunt** → **D-LOOP2 3-run baseline re-measurement** → **commit the pre-registration** → **the 3 agent runs.**
  - **(a)** If P2 shifts the `recall_by_family` baseline, **that shift is disclosed and attributed to the parse fix.**
  - **(b)** The **boundary-crossing hunt is an executor plan with a concrete deliverable**: a written list of `enumerate→X` / `classify→Y` / `build→Z` chains unit-tested on each side but **never composed on real data**, plus a **composition test for each one found.**

### Claude's Discretion

- **System-prompt wording** — reviewer persona and enumerate→investigate→emit workflow instructions. Bounded by D-LOOP4 (prefix static and cache-stable) and by "budgets are code gates, never prompt instructions."
- **Held-out calibration corpus** — the existing `spec32s41` held-out document is the default choice. **If the planner finds it insufficient for a full multi-document consumption measurement (D-BUD5's corollary), FLAG it rather than substituting scored data.**
- **The concrete N values** — circuit-breaker repeat count, diminishing-returns consecutive-turn count, hard max continuation count, and the calibration multiple. All are the planner's to propose, but **every one must land in the committed pre-registration before run 1** (D-GO5).
- **The verdict enum's exact members** (D-VER2), the loop's module path, and the flag mechanism (config vs CLI vs env).
- **Where the grounded partial surfaces** in `FaultReport` and how loop progress reaches the existing `event_bus`/WebSocket UI.
- Whether `S9`/`S10`/`P10` live in `oracles.py` or `checklists.py` today — **resolve during research/planning.** *(RESOLVED below — see Code Reconnaissance §D6.)*

### Deferred Ideas (OUT OF SCOPE)

- **Orchestrator + sub-agent fan-out** (AGENT-02) — Phase 4.
- **Cross-document reference graph / full `follow_reference`** — Phase 4; the typed pending-result stays a boundary this phase respects.
- **Adversarial verifier** (GROUND-02) — Phase 5.
- **Prompt-cache hardening, compaction, cheap-model triage** (COST-01/02/03) — Phase 6. D-LOOP4 pre-pays only the cache-*stability* invariant.
- **Precedent-search as an agent tool** — deferred pending Phase-3 evidence (Phase 2 D-RB3).
- **Reconsidering AGENT-04 itself** — that verdict lands in Phase 4, not here.
- **Reranker (`bge-reranker-v2-m3`)**, **multi-hop GraphRAG**, **Git LFS for `rulebook/**`**, **rulebook FAISS dense rebuild** — carried Phase-2 hygiene/optional items, non-blocking.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **AGENT-01** | Detection runs as a model-driven, model-agnostic tool loop, replacing the one-shot pre-rendered call | §Architecture Patterns 1-3 (turn loop over injected completion callable); §Code Recon D1 (`chat_completion_full` extension points), D5 (`pipeline.py` seam); §Standard Stack (no new runtime deps); §Pitfalls 1, 3, 6 |
| **AGENT-03** | Hard per-run budgets + circuit breaker in code, plus a diminishing-returns stop | §Architecture Pattern 4 (BudgetLedger); §Recommendations for N values; §Pitfall 4 (enumerate turns are productive but yield no spans — D-BUD2 needs an amendment); §Validation Architecture (D-BUD6 forced-runaway driver) |
| **AGENT-04** | Bidirectional budget — continuation floor; loop refuses a premature stop and injects a nudge | §Architecture Pattern 5; §Code Recon D1 (no-tool-call detection needs `ChatResult.tool_calls`); §Validation Architecture (scripted-stop test); Claude Code precedent `tokenBudget.ts:59` (`continuationCount >= 3`, deltas < 500 tokens) |
| **GROUND-01** | Every claimed deficiency pinned to a verbatim, re-openable source quote the agent actually retrieved | §Code Recon D3 (`emit_finding` 7 rejection sites, `ledger.was_issued` keys on `(doc_id,start,end)` only); §Pitfall 1 (span-ID string round-trip is the silent-corruption seam); §Validation Architecture (round-trip composition test) |
| **GROUND-03** | Each finding dual-cited — submission passage AND the specific FDA/ICH rule clause | §Code Recon D3 (`rule_span_id` validated but NOT persisted — `schemas/faults.py` has no field); §Pitfall 2; §Recommendation: add `rule_span_id` + `verdict` to `Fault` in this phase |
| **DETECT-03** | Deterministic quick-win oracles: LOD/LOQ presence (S9), reference standards (S10), stability commitment (P10) | §Code Recon D6 — **RESOLVED and it is worse than assumed:** S9 lives in `checklists.py`, S10 **does not exist anywhere**, P10 exists only as an E&L-specific `leachable_commitment`. `run_oracles`-the-tool must build S10 and generalize P10 |
| **DETECT-04** | Compliance verdict per finding tied to a cited FDA/ICH rule | §Code Recon D3 (`verdict: str` accepted at `emit_finding.py:48` but stuffed into `detail` at line 98); §Recommendation: 3-member enum `violation`/`gap`/`ambiguous`, `compliant` deliberately unrepresentable |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

Directives the planner must not contradict:

| Directive | Source | Effect on this phase |
|-----------|--------|---------------------|
| Build-your-own tool loop on `openai`; PydanticAI only MEDIUM | Technology Stack | Reinforces D-LOOP1. **No framework adoption in Phase 3.** |
| Keep `structured.py`; do not replace wholesale | What NOT to Use | `_sanitize`/`schema_for_databricks` are reused, extended additively (see §Pitfall 5). |
| Do not adopt AutoGen; remove `autogen-*` deps | What NOT to Use | `pyproject.toml:agents` still pins `autogen-agentchat>=0.4` / `autogen-ext[openai]>=0.4` — dead weight. Removal is a safe, verifiable hygiene task for this phase [VERIFIED: `pyproject.toml`]. |
| Model-agnostic OpenAI-compatible loop; Anthropic SDK is additive only | What NOT to Use | The loop must not depend on `cache_control`; Databricks prefix caching is implicit (see §State of the Art). |
| No finding may exist without a verbatim source anchor (doc → section → span) **plus the rule it violates** | Constraints / Grounding | `emit_finding` is the only path; the missing `rule_span_id` persistence is a live gap (§Pitfall 2). |
| No assumptions about document count, folder names, or nesting depth | Constraints / Generality | The agent arm must be corpus-wide; `run_detection` is single-document (§Code Recon D5) — a new harness entry point is required, not an `if`. |
| Cost/latency actively managed (caching / compaction / cheap-triage / budgets) | Constraints | D-BUD5 accounting must use real `usage` (§Code Recon D1), and `search_corpus`'s per-call re-embedding is a wall-clock hazard (§Pitfall 7). |
| All work on `CLI_for_folders` | Constraints | Confirmed current branch. |
| Trust code, not README/PIPELINE/DIAGNOSIS/RELIABILITY/PHASES | PROJECT.md / memory | Every claim below is cited to `file:line` read this session. |
| GSD workflow enforcement — no direct edits outside a GSD command | CLAUDE.md | Research made no code edits. |

**Project skills:** none found — `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, `.codex/skills/` are all absent [VERIFIED: filesystem].

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Turn orchestration, stop decisions | Loop (`src/agents/review/loop.py`) | — | D-LOOP1: budgets/breaker/floor are *this phase's deliverable as code*; nothing load-bearing may live in the model or a framework. |
| Tool-call transport (`tools=`, `tool_calls`) | LLM client (`src/llm/client.py`) | — | Keep the existing retry/backoff/rate-limit machinery; add a turn entry point, not a new client. |
| Tool-arg schema derivation & repair | Structured layer (`src/llm/structured.py`) | Loop (dispatch-time coercion) | D-LOOP3 single source of truth; pre-repair vs post-dispatch classes must not conflate (D-LOOP5 corollary). |
| Evidence retrieval / span issuance | Tool layer (`src/tools/*`) | Ingest substrate (`src/ingest/anchors.py`) | Phase-2 contracts locked; the loop only dispatches and renders. |
| Grounding enforcement | `emit_finding` gate | Ledger (`was_issued`) | TOOLS-03 — the gate is the only path a Fault can exist. |
| Budget accounting (tokens, turns, wall-clock) | Loop `BudgetLedger` | LLM client (surfaces `usage`) | D-BUD5 per-run, includes tool results and tool execution time. |
| Telemetry / provenance | Telemetry module (`src/agents/review/telemetry.py`) | `src/tools/errors.py` (`KNOWN_REASON_CODES`) | D-TEL2: one registry, tools and telemetry both reference it; a telemetry-side copy would drift. |
| Deterministic seed leads | `run_oracles` tool (new, wraps `oracles.py` + `checklists.py`) | — | D-ORC1: an oracle lead is just another tool result. |
| Scoring / gate | Eval harness (`src/evals/*`) | Committed baseline JSON | Frozen by D-GO1(iii); the loop must not touch it. |
| UI progress | `event_bus` / WebSocket | `schemas/events.py` | `EventType` is a closed `Literal` — must be extended additively (§Code Recon D8). |
| Parse-layer text recovery (P2) | `src/parse/pdf.py` | `src/ingest/store.py` cache key | Fix is 2 lines; **cache invalidation is the hard part** (§Runtime State Inventory). |

---

## Standard Stack

### Core — no new runtime dependencies are required for this phase

| Library | Installed version | Purpose | Why standard |
|---------|-------------------|---------|--------------|
| `openai` | **2.43.0** [VERIFIED: `importlib.metadata` in `.venv`] | Tool-call transport (`tools=`, `message.tool_calls`, `usage`) | Already the client; `ChatCompletionMessage.tool_calls` and `CompletionUsage.prompt_tokens_details.cached_tokens` both exist in this version [VERIFIED: introspected]. `pyproject.toml` pins `openai>=1.40`; the installed 2.43.0 satisfies it. |
| `pydantic` | **2.13.4** [VERIFIED] | Tool arg models → `model_json_schema()` (D-LOOP3) | Already the schema substrate for `structured.py` and every `src/schemas/*`. |
| `json-repair` | **0.61.2** [VERIFIED] | L3 deterministic salvage of malformed tool args | Already wired at `structured.py:18,137`. |
| `structlog` | **26.1.0** [VERIFIED] | Run/telemetry logging | Already used across `client.py`, `structured.py`, `pipeline.py`. |
| `pytest` | **9.1.1** [VERIFIED], `asyncio_mode=auto` | Offline test harness | Configured at `pyproject.toml [tool.pytest.ini_options]`. |

**Installation:** none. Adding a dependency for this phase would be a smell — the loop is ~400 lines of control flow over primitives that already exist.

### Supporting — hygiene, not new capability

| Change | Why |
|--------|-----|
| Remove `autogen-agentchat>=0.4`, `autogen-ext[openai]>=0.4` from `pyproject.toml` | CLAUDE.md "What NOT to Use"; the AutoGen design was removed. Dead weight in the dependency tree. |
| Consider bumping the `openai` pin from `>=1.40` to `>=2.40` | The loop relies on `tool_calls` and `usage.prompt_tokens_details`; a `>=1.40` floor permits an SDK where the latter is absent [ASSUMED — the exact SDK version that introduced `prompt_tokens_details` was not verified]. |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled loop | PydanticAI 2.x | Locked out by D-LOOP1 and rated MEDIUM in CLAUDE.md. Its usage-limit and typed-tool machinery *is* what this phase builds — owning it is the point. |
| Server-side guided decoding for tool args | `outlines` / `xgrammar` | Databricks applies constrained decoding server-side for `tools=` already [ASSUMED]; adding a client-side grammar engine is Phase-6 belt-and-suspenders, not Phase-3 scope. |
| A tokenizer for budget accounting | `tiktoken` / `transformers` | Prefer the provider's own `usage` object. Only if Databricks omits `usage` does an estimator become necessary — and then a declared `len//4` char estimate flagged in telemetry beats a wrong-tokenizer number that *looks* exact (§Pitfall 8). |

---

## Architecture Patterns

### System Architecture Diagram

```
                    ┌──────────────── STATIC PREFIX (D-LOOP4: byte-identical across corpora) ───┐
                    │  system prompt (reviewer persona, enumerate→investigate→emit workflow)     │
                    │  tool schemas  (7 × derived from pydantic arg models via _sanitize)        │
                    └───────────────────────────────┬───────────────────────────────────────────┘
                                                    │
  corpus manifest, doc counts, families ────────────┤  (DYNAMIC → messages only, never the prefix)
                                                    ▼
   ┌────────────────────────────────── DRIVE LOOP (src/agents/review/loop.py) ───────────────────┐
   │                                                                                              │
   │   ┌──────────────┐   messages+tools   ┌────────────────────┐   ChatTurn(tool_calls, usage)   │
   │   │ BudgetLedger │◄──────────────────►│ complete: Callable │◄────────────────────────────┐   │
   │   │ tokens/turns │  (INJECTED — real  │  llm/client.py     │  usage.prompt_tokens        │   │
   │   │ wall-clock   │   OR scripted fake)│  retry/backoff kept│  completion_tokens          │   │
   │   └──────┬───────┘                    └────────────────────┘  cached_tokens              │   │
   │          │                                      │                                        │   │
   │          │                             tool_calls?                                       │   │
   │          │                    ┌─────────── YES ──┴── NO ───────────┐                     │   │
   │          │                    ▼                                    ▼                     │   │
   │          │      ┌──────────────────────────┐        ┌──────────────────────────────┐    │   │
   │          │      │ ARG COERCION             │        │ AGENT-04 CONTINUATION FLOOR  │    │   │
   │          │      │ pydantic validate        │        │ under budget AND not in DR   │    │   │
   │          │      │  ├─ ok ──────────────┐   │        │  AND continuations < max?    │    │   │
   │          │      │  └─ fail → json_repair│   │        │   YES → inject nudge, ────────────┘   │
   │          │      │       (PRE-REPAIR:    │   │        │          consume a turn      │        │
   │          │      │        NO turn spent) │   │        │   NO  → stop_reason=completed│        │
   │          │      └──────────────────────┬┘   │        └──────────────────────────────┘        │
   │          │                             ▼    │                                                 │
   │          │      ┌───────────────────────────────────────────────────────────────┐            │
   │          │      │ DISPATCH → src/tools/*  (span-ID strings parsed → SpanID)      │            │
   │          │      │  search_corpus · open_doc · get_section · read_guideline       │            │
   │          │      │  follow_reference · emit_finding · run_oracles (NEW, 7th)      │            │
   │          │      └───────┬──────────────────────────────────────┬────────────────┘            │
   │          │              │ result / ToolRejected                │ RetrievalLedger              │
   │          │              ▼                                      │ record_span / was_issued     │
   │          │      ┌───────────────────────────┐                  │ check_and_mark_served        │
   │          └─────►│ TELEMETRY (per-turn JSONL)│◄─────────────────┘ dedup_hit_rate               │
   │                 │ (reason_code, half) matrix│                                                 │
   │                 │ pre/post-repair rates     │   D-LOOP5: a rejection IS the tool result,      │
   │                 │ continuation events       │   goes back to the model, CONSUMES A TURN ──────┼──┐
   │                 │ oracle-lead conversion    │                                                 │  │
   │                 └───────────┬───────────────┘                                                 │  │
   │                             │                        ┌─── D-BUD3 CIRCUIT BREAKER ◄────────────┼──┘
   │                             │                        │  identical (tool,args) × N              │
   │                             │                        │  OR N consecutive same (reason_code,half)
   │                             ▼                        └─────────────────────────────────────────┘
   │            stop_reason ∈ {completed, ceiling, diminishing-returns, max-turns, breaker}          │
   └────────────────────────────────────┬────────────────────────────────────────────────────────────┘
                                        │ grounded partial (always returned, never crashes)
                                        ▼
        ┌──────────────────┐     D-VER1: verify.py / challenge.py are NOT in this path
        │   FaultReport    │◄─── (they can DROP findings — proven at verify.py:120-122 & 136-144)
        └────────┬─────────┘
                 │ serialize → commit               ┌──────────────────────────────┐
                 ├─────────────────────────────────►│ 03-*/run{1,2,3}.json (Fault- │
                 │                                  │ Report) + .jsonl + summary   │
                 ▼                                  └──────────────┬───────────────┘
        ┌──────────────────────────────┐                           │ evals.capture.load_captured
        │ event_bus → WebSocket (UI)   │                           ▼
        └──────────────────────────────┘            ┌──────────────────────────────────────┐
                                                    │ evals: match.py → metrics.py → gate.py│
                                                    │ recall_by_family vs FROZEN baseline   │
                                                    └──────────────────────────────────────┘
```

### Recommended Project Structure

```
src/agents/review/          # NEW — mirrors agents/detection/ per ARCHITECTURE.md:117
├── __init__.py             #   public entry: run_review(corpus, ...) -> ReviewResult
├── loop.py                 #   the turn loop; takes `complete` as a parameter (DI)
├── budget.py               #   BudgetLedger: tokens/turns/wall-clock, DR, breaker, floor
├── registry.py             #   ToolRegistry: 7 pydantic arg models → schemas → dispatch
├── spanref.py              #   "[doc:start:end]" ⇄ SpanID; corpus-or-rulebook resolution
├── telemetry.py            #   per-turn JSONL writer + summary JSON + provenance
├── oracles_tool.py         #   run_oracles-the-tool (D-ORC1) — wraps oracles + checklists
└── prompts.py              #   STATIC system prompt (no f-strings over corpus data)

src/tools/errors.py         # + KNOWN_REASON_CODES (D-TEL2), + half field (D-TEL3)
src/tools/emit_finding.py   # + half= on 7 rejection sites; + structured verdict/rule_span
src/schemas/faults.py       # + ComplianceVerdict enum, + verdict, + rule_span_id
src/llm/client.py           # + chat_completion_tools() returning tool_calls + usage
src/llm/structured.py       # + tool_schema_for_databricks() (inlines $defs, no $ref)
src/evals/run.py            # + `agent-run` subcommand (corpus-wide, per-run budget)
src/parse/pdf.py            # P2 fix (2 lines) + PARSER_VERSION
src/ingest/store.py         # cache_key() folds in PARSER_VERSION

tests/agents/review/        # NEW
├── conftest.py             #   ScriptedChatClient, transcript fixtures, corpus builders
├── test_loop_budget.py     #   ceiling / DR / breaker / floor — all offline
├── test_runaway.py         #   D-BUD6 forced-runaway driver vs REAL tools
├── test_prefix_stability.py#   D-LOOP4 byte-identical prefix across two corpora
├── test_spanref_roundtrip.py # boundary-crossing composition test (the big one)
└── test_verify_nondropping.py# D-VER1 proof-by-test
```

### Pattern 1: Dependency-injected completion callable (makes the loop testable offline)

**What:** The loop never imports `chat_completion_*` directly. It receives a callable.
**When to use:** Always — it is the single enabler for D-RB6 offline CI, D-BUD6's synthetic driver, and the AGENT-04 floor test.
**Precedent in this repo:** `RetrievalLedger` is already documented as *"Constructor-injected, never a module global (Security Domain V3 — Pitfall 9): one instance per agent run, threaded explicitly through every tool call"* [`src/tools/ledger.py:3-5`]. The loop applies the identical discipline to the model client.

```python
# src/agents/review/loop.py  (shape, not final)
from collections.abc import Callable

CompleteFn = Callable[[list[dict], list[dict]], "ChatTurn"]   # (messages, tool_schemas) -> turn

def run_review(
    corpus: CorpusIndex,
    manifest: CoverageManifest,
    ledger: RetrievalLedger,
    budget: BudgetLedger,
    telemetry: TurnLog,
    complete: CompleteFn,                 # ← injected: real client OR ScriptedChatClient
    registry: ToolRegistry,
) -> ReviewResult: ...
```

### Pattern 2: Span-IDs cross the model boundary as STRINGS, never nested models

**What:** Tool args carry `submission_span_id: str` in the exact form the tools already render — `"mvr1381:14820:14975"` — and the loop parses it back into a `SpanID` by re-minting.
**Why this is forced, not preferred:** Databricks prohibits `$ref` in tool schemas [CITED: docs.databricks.com — *"Complex nested or schema composition and validation using: `anyOf`, `oneOf`, `allOf`, `prefixItems`, or `$ref`"*]. A pydantic arg model declaring `submission_span_id: SpanID` emits `{"$ref": "#/$defs/SpanID"}` + a `$defs` block, and `structured.py::_sanitize` **preserves `$defs`** by design [`src/llm/structured.py:37` docstring, `:43-73`]. The schema would be rejected or silently degraded.
**Why it also happens to be right:** tools render `[{doc_id}:{start}:{end}]` and nothing else [`get_section.py:48`, `read_guideline.py:72`, `search_corpus.py:73`] — D-GRAN's *"cite IDs you can SEE"*. A string arg is the only form the model can honestly produce.
**The catch that makes this a composition-test target:** `SpanID` requires a `hash` [`src/schemas/documents.py:136-139`] which is **not** in the rendered string. The loop must re-mint via `mint_span(nt.canonical, start, end, doc_id, nt.normalizer_version)`. `RetrievalLedger` keys on `(doc_id, start, end)` only and ignores the hash [`src/tools/ledger.py:17,23,26`], so `was_issued()` passes regardless — but `emit_finding` then calls `open_span`, which **does** verify the hash [`src/ingest/anchors.py:56-64`]. See §Pitfall 1.

```python
# src/agents/review/spanref.py  (shape)
_SPANREF = re.compile(r"^\[?([^:\[\]]+):(\d+):(\d+)\]?$")

def parse_span_ref(ref: str, corpus: CorpusIndex, rulebook_cache_dir: str) -> SpanID | ToolRejected:
    """Resolve a rendered span-ID string against the CORPUS store, then the RULEBOOK store.
    Returns a typed rejection (never raises) so a malformed ref is a teaching turn, and
    tags loop-side parse failures distinctly from gate rejections so telemetry cannot
    mistake a loop bug for model span-invention (D-TEL3)."""
```

### Pattern 3: Rejections are tool results (D-LOOP5), with a two-layer failure taxonomy

Two failure classes must never merge in telemetry (D-LOOP5 corollary):

| Layer | Where | Turn consumed? | Telemetry bucket |
|-------|-------|----------------|------------------|
| Arg does not validate against the pydantic model, repaired by `json_repair`/coercion **before dispatch** | `registry.py` | **No** | `pre_repair_malformed` (D-TEL4's honest measure) |
| Arg does not validate and **cannot** be repaired | `registry.py` | **Yes** (returned to model as an error tool result) | `post_repair_malformed` — trips the ≥95% floor |
| Call dispatched, tool returns `ToolRejected` | `src/tools/*` | **Yes** | `(reason_code, half)` matrix |

```python
# Rendering a rejection back to the model — the hint field is the self-correction affordance
def render_rejection(r: ToolRejected) -> str:
    parts = [f"REJECTED[{r.reason_code}] {r.reason}"]
    if r.hint:    parts.append(f"HINT: {r.hint}")
    if r.preview: parts.append(r.preview)      # TOOLS-04 oversized path carries real span-IDs
    if r.handle:  parts.append(f"handle={r.handle}")
    return "\n".join(parts)
```

### Pattern 4: BudgetLedger — every stop condition is a method, none is a prompt sentence

```python
@dataclass
class BudgetLedger:
    max_tokens: int; max_turns: int; max_wall_clock_s: float
    dr_window: int; breaker_repeat: int; breaker_same_class: int; max_continuations: int
    # accumulated
    billed_tokens: int = 0        # Σ(prompt_tokens + completion_tokens) — see §Pitfall 8
    cached_tokens: int = 0        # Σ prompt_tokens_details.cached_tokens (COST-01 visibility)
    turns: int = 0; continuations: int = 0
    def over_ceiling(self) -> bool: ...
    def in_diminishing_returns(self) -> bool: ...      # D-BUD2 productivity over dr_window turns
    def breaker_tripped(self) -> bool: ...             # D-BUD3, keyed on (reason_code, half)
    def may_nudge(self) -> bool: ...                   # D-BUD4: NOT DR AND continuations < max
```

Productivity per D-BUD2 is computed from the ledger, not re-derived: a turn is productive iff it added at least one span-ID to `RetrievalLedger._issued` **or** landed a `Fault` through the gate. See §Pitfall 4 for the enumerate-turn hole in that definition.

### Pattern 5: AGENT-04 continuation floor, verbatim from the Claude Code precedent

`src/query/tokenBudget.ts:59` continues while under 90% of budget but stops early when `continuationCount >= 3` **and** successive deltas are `< 500` tokens; on continue it injects a nudge message rather than silently looping [CITED: `.planning/research/CLAUDE-CODE-TEARDOWN.md:84-86`]. The nudge string precedent is *"Stopped at {pct}% of token target. Keep working — do not summarize."* [CITED: `.planning/REQUIREMENTS.md:38`, `03-CONTEXT.md` §specifics].

```python
if not turn.tool_calls:
    if budget.may_nudge():
        telemetry.continuation(tokens_at_stop=budget.billed_tokens,
                               findings_before=len(findings))
        messages.append({"role": "user", "content": NUDGE})   # NUDGE is a module constant
        budget.continuations += 1; budget.turns += 1
        continue
    return ReviewResult(findings, stop_reason="completed")
```

`NUDGE` must be a **module-level constant**, not an f-string over run state — otherwise it enters the message list with varying bytes and complicates the D-LOOP4 story (the prefix stays safe either way, but a stable nudge keeps the transcript diffable across the 3 runs).

### Anti-Patterns to Avoid

- **A single `if agent_mode:` inside `run_detection`.** The signatures are incompatible: `run_detection(doc: dict, sections, groups, ...)` is **per-document** [`pipeline.py:37-39`] and the eval harness calls it in a per-document loop [`evals/run.py:259-281`], while D-BUD5 mandates a **per-run budget over a multi-document review**. Forcing the flag inside `run_detection` would either smuggle a per-document budget back in — *"2/28 by a different route"* — or corrupt the legacy arm.
- **Passing `tools=` and `response_format=` in the same call.** `client.py:104-113` only knows how to drop `response_format` on a `BadRequestError`; with `response_format=None` it logs and re-raises. Keep tool turns `tools=`-only; reserve `response_format` for the `structured.py` repair call.
- **Recomputing `dedup_hit_rate` in telemetry.** `RetrievalLedger.dedup_hit_rate()` already exists [`ledger.py:39-40`]; D-TEL1 reads it.
- **A telemetry-side copy of the reason codes.** D-TEL2 is explicit; `errors.py:14-16` is the source.
- **Letting the model author quote text.** Nothing in the loop should accept free-text evidence — `evidence` on a Fault comes from `open_span` [`emit_finding.py:82,112-116`].

---

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---------|-------------|-------------|-----|
| Retry / backoff / `Retry-After` / rate-limit escalation | A new client for tool turns | Extend `llm/client.py`'s existing loop [`client.py:96-128`] | Already handles `RateLimitError` with header-aware delays up to 60s and `_RETRYABLE` connection/timeout errors. A parallel implementation will drift. |
| Malformed JSON args | A bespoke arg parser | `structured.py::parse_structured` [`:119-147`] — `_extract_json_blob` → `json_repair` → pydantic validate | Layers L3+L4 are already hardened and instrumented with structlog counters. |
| Databricks schema normalization | Hand-editing tool JSON | `schema_for_databricks` / `_sanitize` [`:30-73`] **plus a `$defs`-inlining extension** | Already strips `pattern` and flattens `anyOf[X,null]` — both Databricks requirements. It does **not** inline `$ref` (§Pitfall 5). |
| Re-opening a span byte-exact | A substring search | `ingest.anchors.open_span` [`:56-64`] | Verifies the content hash and renders the RAW citation via the offset map. `emit_finding` already calls it; the loop must not bypass it. |
| Issued-span tracking / read dedup | A set in the loop | `RetrievalLedger` [`ledger.py`] | `was_issued` is D-GRAN's enforcement point; `check_and_mark_served` is COST-04. One instance per run, injected. |
| Oversized results | Truncation | `tools/oversized.py` persist/preview/handle [`get_section.py:113-125`] | Claude Code A/B: truncating over-cap reads *"dropped tool error rate but raised mean tokens"* and was reverted; an error tool-result is ~100 bytes vs ~25k for a truncated one [CITED: `CLAUDE-CODE-TEARDOWN.md:88-97`]. |
| Loading a committed run for re-scoring | A custom JSON reader | `evals.capture.load_captured` [`capture.py:16-18`] | Already validates a serialized `FaultReport`. This makes D-TEL1(ii)'s *"verdict re-derivable from committed files"* nearly free — commit `run{1,2,3}.json` and re-score with `python -m evals.run score --captured`. |
| Recall-by-family arithmetic | A spike-local scorer | `metrics.recall_by_family` [`metrics.py:230-234`] | D-GO1(iii) freezes the harness; a second implementation *is* a harness change. |

**Key insight:** almost everything this phase needs already exists as a Phase 0–2 deliverable. The genuinely new code is control flow (loop, budget, telemetry, registry) plus three small additive schema changes. Every place the plan reaches for a new implementation of an existing primitive is a place the gate's number stops being comparable.

---

## Code Reconnaissance

Every claim below was read this session at `9b68856`.

### D1 — `src/llm/client.py`: what exists, what must change

| Item | Location | Note |
|------|----------|------|
| `ChatResult` | `client.py:33-36` | `content: str`, `finish_reason: str`. **No `tool_calls`. No `usage`.** |
| `chat_completion_full(messages, model=None, temperature=None, max_tokens=4096, response_format=None) -> ChatResult` | `client.py:76-130` | The only full-response entry point. |
| Response handling | `client.py:98-103` | Reads `choice.message.content` and `choice.finish_reason` — **`response.usage` and `choice.message.tool_calls` are discarded.** |
| `BadRequestError` graceful degradation | `client.py:104-113` | Drops `response_format` and retries **once**; with `response_format=None` it logs `llm_bad_request` and re-raises. Safe for tool turns (it will not silently drop `tools=`). |
| Rate-limit handling | `client.py:114-121` | `Retry-After`-aware, base 8.0s, cap 60.0s, 5 attempts. **Keep.** |
| Connection/timeout retry | `client.py:122-128` | `APIConnectionError`, `APITimeoutError`, exponential from 1.0s. **Keep.** |
| Client construction | `client.py:39-55` | Databricks base_url `{host}/serving-endpoints`, 120s timeout. Module-global `_client` singleton. |

**Minimal tool-turn entry point that preserves the resilience layer** — add alongside, do not modify `chat_completion_full`:

```python
@dataclass
class ChatTurn:
    content: str
    finish_reason: str
    tool_calls: list          # openai ChatCompletionMessageToolCall
    raw_message: dict         # message.model_dump() — MUST be echoed back verbatim
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    usage_present: bool = False    # False ⇒ telemetry flags an ESTIMATED budget

def chat_completion_tools(messages, tools, model=None, temperature=0.0, max_tokens=4096,
                          tool_choice="auto") -> ChatTurn:
    ...  # identical retry/backoff body; kwargs["tools"]=tools, kwargs["tool_choice"]=tool_choice
```

**Verified SDK support** [VERIFIED: introspected `openai` 2.43.0 in `.venv`]:
- `ChatCompletionMessage` fields include `tool_calls`.
- `CompletionUsage` fields: `completion_tokens`, `prompt_tokens`, `total_tokens`, `completion_tokens_details`, `prompt_tokens_details`.
- `PromptTokensDetails` fields: `audio_tokens`, **`cached_tokens`**.

**Open risk:** whether Databricks *populates* `usage.prompt_tokens_details.cached_tokens` is **unverified**. A 3-line probe against a live endpoint answers it. Plan a fallback (§Pitfall 8).

### D2 — `src/llm/structured.py`: does D-LOOP3's derivation actually work for tool schemas?

| Item | Location | Behavior |
|------|----------|----------|
| `schema_for_databricks(model_cls)` | `:30-40` | `model_cls.model_json_schema()` → `_sanitize` |
| `_sanitize(node)` | `:43-73` | Flattens `anyOf[X, {"type":"null"}]` → X **only when exactly one non-null variant** (`:48-57`); keeps `anyOf` otherwise (`:59`); `node.pop("pattern")` (`:62`); forces `additionalProperties: false` on objects (`:65-66`); recurses (`:68-69`) |
| `build_response_format` | `:76-87` | Wraps in `{"type":"json_schema", "json_schema":{name, schema, strict}}` — **response_format shape, not tool shape** |
| `parse_structured` | `:119-147` | `_extract_json_blob` → `json.loads` → `repair_json` → `model_validate`; returns `(instance, None)` or `(None, error_json)` |
| `repair_with_moderator` | `:210-279` | L5 one-shot repair on the caller's model |

**Answer: partially. Two concrete gaps must be closed before D-LOOP3 is sound.**

1. **`$ref` / `$defs` are preserved and Databricks prohibits them.** The docstring at `:37` states *"$defs preserved"*, and `_sanitize` never inlines a `$ref`. Any tool arg model with a nested `BaseModel` (the obvious `submission_span_id: SpanID`) emits `$ref` + `$defs`. → **Add a `$defs`-inlining pass**, exposed as a distinct `tool_schema_for_databricks()` so the response_format path is unchanged. Or avoid nesting entirely (Pattern 2 does both — belt and braces).
2. **`build_response_format`'s wrapper is the wrong shape for tools.** Tools need `{"type":"function","function":{"name","description","parameters": <schema>}}`. `schema_for_databricks`'s *output* slots into `parameters`; the wrapper does not. Add a sibling `build_tool_schema(model_cls, name, description)`.

**Things that already work in our favour:** `pattern` stripping (`:62`) matches the Databricks prohibition exactly; `anyOf[X,null]` flattening (`:48-57`) handles `str | None` optional args, which are unavoidable given the locked D-RI2 contract; `additionalProperties:false` matches strict-mode expectations.

**Residual risk to verify with a live call:** `_sanitize` does **not** add every property to `required`, and `model_json_schema()` also emits a top-level `"title"`. Neither is prohibited by the documented rules, but strict tool-schema validation on some endpoints requires all-properties-required [ASSUMED]. Cheapest mitigation: keep tool arg models flat with **required** fields wherever the locked contracts allow (§Pitfall 6).

### D3 — `src/tools/*`: exact signatures the loop must call

```python
# src/tools/search_corpus.py:39
search_corpus(corpus: CorpusIndex, query: str, ledger: RetrievalLedger, top_k: int = 10) -> list[dict]
#   returns [{"doc_id", "span_id": <SpanID dict>, "score", "snippet": "[doc:start:end] text"}]
#   NEVER returns ToolRejected. Records every returned span (search_corpus.py:71).

# src/tools/open_doc.py:14
open_doc(corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger) -> dict | ToolRejected
#   returns {doc_id,title,filename,status,structure,tables,classification,outline:[{label,level,span_id}]}
#   records EVERY outline span (open_doc.py:22-23) — outline labels become citable immediately.

# src/tools/get_section.py:51
get_section(corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger,
            start: int | None = None, end: int | None = None, heading: str | None = None,
            handle: str | None = None, max_chars: int = 8000) -> str | ToolRejected
#   4 optional params — see Pitfall 6. Rejections: not_found (no cache / bad handle / no
#   heading match / no mode given / empty range), range_too_large (with preview+handle).

# src/tools/read_guideline.py:33
read_guideline(manifest: CoverageManifest, ledger: RetrievalLedger,
               citation: str | None = None, family: str | None = None,
               handle: str | None = None, max_chars: int = 8000) -> list[dict] | str | ToolRejected
#   citation=None  → ENUMERATE: [{"requirement_id","citation","rule_doc_id","trigger"}]
#                    *** records NO spans *** (read_guideline.py:45-57) — see Pitfall 4
#   citation=str   → FETCH via _fetch_citation (:74), annotated + spans recorded

# src/tools/follow_reference.py:21
follow_reference(corpus: CorpusIndex, doc_id: str, ref_text: str, ledger: RetrievalLedger) -> dict
#   NEVER returns ToolRejected. Same-doc outline hit → {"resolved": True, "span_id", "label"};
#   otherwise {"status": "cross_document_resolution_pending_phase_4"} (follow_reference.py:18,27,38)
#   *** The loop MUST treat this as an honest boundary, not a failure, and MUST NOT retry it. ***

# src/tools/emit_finding.py:40-51
emit_finding(corpus: CorpusIndex, submission_span_id: SpanID, rule_span_id: SpanID | None,
             ledger: RetrievalLedger, verdict: str, requirement_id: str = "",
             rule_citation: str = "", title: str = "", detail: str = "",
             rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR) -> Fault | ToolRejected
```

**`emit_finding`'s 7 rejection sites — the exact `half` assignment D-TEL3 requires:**

| Line | `reason_code` | `half` |
|------|---------------|--------|
| `:53` | `no_rule_citation` | `rule` |
| `:58` | `not_retrieved_this_session` | `submission` |
| `:62` | `not_retrieved_this_session` | `rule` |
| `:68` | `wrong_store` | `submission` |
| `:73` | `wrong_store` | `rule` |
| `:84` | `not_byte_exact` | `submission` |
| `:90` | `not_byte_exact` | `rule` |

Every rejection in every other tool gets `half=""`. `ToolRejected` [`errors.py:11-28`] has `tool`, `reason_code` (open `str`, deliberately not a `Literal` — `:13-19`), `reason`, `hint`, `preview`, `handle`. Known codes listed in the comment at `:14-16`: `not_found | range_too_large | not_byte_exact | not_retrieved_this_session | wrong_store | family_not_in_registry | no_rule_citation`; `not_unique` is deliberately excluded (`:16-19`).

**`RetrievalLedger`** [`ledger.py`]: `record_span(span)` `:22`, `was_issued(span) -> bool` `:25`, `check_and_mark_served(doc_id,start,end) -> bool` `:28`, `dedup_hit_rate() -> float` `:39`. Internal sets are `tuple[str,int,int]` — **hash is not part of the key** (`:17`).

**What `emit_finding` produces** [`:112-117`]: `Fault(title=title or "Deficiency", detail=detail_with_verdict, tier=CORROBORATED, evidence_class=QUOTE_ANCHORED, confidence=0.7, evidence=submission_raw, source="tool:emit_finding", guidance_refs=[rule_citation or rule_span_id.doc_id] + ([requirement_id] if requirement_id else []))`.

Two consequences the planner must act on:
- `verdict` is **stringified into `detail`** at `:98` — D-VER2 needs a real field.
- `rule_span_id` **does not survive** into the Fault. The module documents this explicitly at `:100-111` as a Phase-2 boundary because `schemas/faults.py` was off-limits: *"only its human-readable citation string survives into guidance_refs… If a later phase (Phase 5's verifier) needs to re-open the EXACT rule span a Fault cites, that requires either a Fault schema change… or a side-channel span store."* **Phase 3 is that later phase** — GROUND-03 asks for dual citation on the finding, not merely at the call.
- `title or "Deficiency"` means an untitled finding gets a constant title. Harmless for scoring (`match.matches` reads `evidence` only, `match.py:91`) but catastrophic if any dedup on title is ever applied (§D5).

### D4 — `src/agents/detection/oracles.py` + `checklists.py`

```python
# oracles.py:218
ORACLES = [result_vs_limit, value_vs_inline_limit, cross_reference_consistency]
# oracles.py:221
run_oracles(doc: dict) -> list[Fault]      # try/except per check, one bad check never sinks the battery
# checklists.py:184
run_checklists(doc: dict, ctd: CTDSection) -> list[Fault]
```

Both take the **`extract_pdf`-shaped `doc: dict`** (`doc["pages"][i]["blocks"|"tables"]`), *not* a `CorpusIndex` and *not* canonical text. `run_oracles`-the-tool must bridge that gap (§Pitfall 9).

### D5 — `src/agents/detection/pipeline.py`: the flag seam

```python
# pipeline.py:37-39
def run_detection(doc: dict, sections: list[dict], groups: list[dict],
                  job_id: str = "", model: str | None = None) -> FaultReport
```

- `groups` is accepted and **never used** in the body — dead parameter.
- `oracle_faults = run_oracles(doc)` `:51`; `checklist_faults = run_checklists(doc, ctd)` `:52`.
- **`faults = verify_and_tier(oracle_faults + checklist_faults + agent_faults, doc)` at `:86`** — the union D-ORC1/D-VER1 dismantle, exactly as CONTEXT.md states.
- `faults = challenge_faults(faults, sections, doc, model=detector_model)` `:87`.
- Callers: `evals/run.py:273` (harness) and `agents/orchestrator.py:34` (API path). Re-exported at `agents/detection/__init__.py:1`.

**Cleanest flag seam (recommendation):** do **not** branch inside `run_detection`. Add:
1. `src/agents/review/__init__.py::run_review(corpus, ...) -> ReviewResult` — a parallel entry point.
2. `python -m evals.run agent-run [--model ...] [--out ...]` — a new subcommand beside `run` [`evals/run.py:323-327`], corpus-wide with a per-run budget, writing a committed `FaultReport` JSON per run.
3. `Settings.detection_mode: Literal["legacy","agent"] = "legacy"` in `config.py` for the API path only.

This satisfies D-LOOP1's *"both arms execute back-to-back on the same corpus"* without touching the legacy code path at all — which is what keeps the baseline re-derivable at gate time.

**D-VER1 is empirically justified, not merely prudent.** `verify_and_tier` [`verify.py:111-152`] drops and mutates:
- `:117` exempts only `CODE_VERIFIED` and `CHECKLIST` from the soft-finding block. `emit_finding` produces `QUOTE_ANCHORED` → **not exempt**.
- `:120-122` `_concedes_compliance(f)` → `continue` — **drops the finding outright.** (`_concedes_compliance` scans `title` and `detail` for self-negation regexes; the docstring records *"a live run emitted 10 of 31 'faults' whose own title ended 'compliant. No finding.'"*)
- `:124-134` **overwrites** `evidence_class`, `tier`, `confidence`, `novel`. Agent findings carry no `precedents` → every one is forced to `Tier.ADVISORY`, `confidence=0.4`.
- `:136-144` dedup on `_dedup_key(f) = (_norm(title)[:60], _norm(section), _norm(table_ref))` [`verify.py:107-108`] — with `emit_finding`'s `title or "Deficiency"` default and empty `section`/`table_ref`, **every untitled agent finding collapses to one key and all but one are dropped.**

A downstream reporting artifact to note: `_verifier_metrics` [`metrics.py:159-193`] keeps findings whose `tier != ADVISORY`. On the agent path *all* findings are `CORROBORATED` [`emit_finding.py:114`], so the `verifier` metric degenerates to the same numbers as `end_to_end`. Say so in the report rather than presenting it as an independent measurement.

### D6 — RESOLVED: where S9 / S10 / P10 actually live

**This is worse than the CONTEXT.md question implies. The answer is "neither file, mostly."**

| Roadmap oracle | Actual implementation | Location | Gate |
|----------------|----------------------|----------|------|
| **S9** — LOD/LOQ presence | `_VALIDATION_REQUIRED` entries `"limit of detection (LOD)"` and `"limit of quantitation (LOQ)"`, run by `_validation_checklist(doc)` | **`checklists.py:22-23`**, function at **`:74-96`** | Only fires when `ctd in _VALIDATION_SECTIONS` [`checklists.py:184-186`, set at `:34-39`]. Emits `EvidenceClass.CHECKLIST`. |
| **S10** — reference standards | **DOES NOT EXIST.** `grep -rn -i "reference standard" --include=*.py src/` returns **nothing** [VERIFIED]. | — | Must be **built** in Phase 3. |
| **P10** — stability commitment | Closest analogue is `leachable_commitment(doc)` — an *E&L leachable-monitoring* commitment, not a general stability commitment | **`checklists.py:161-182`**, regex at **`:44-48`** | Only fires when `is_el_report(doc)` [`checklists.py:69-71,187`]. |
| (the actual `oracles.py` battery) | `result_vs_limit`, `value_vs_inline_limit`, `cross_reference_consistency` | `oracles.py:218` | Arithmetic/consistency checks — **none of them is S9, S10 or P10.** |

**Planner consequence:** DETECT-03 is not a wrapping exercise. `run_oracles`-the-tool must (a) call the existing `oracles.py` battery, (b) call `checklists.py`'s S9 path, (c) **implement S10**, and (d) either generalize `leachable_commitment` into a P10 stability-commitment check or implement P10 separately. Scope this honestly in the plan — "demote the oracles" implies three oracles exist, and two of them do not.

### D7 — `src/evals/*`: how the harness is invoked, and what "harness/matcher version" is

| Item | Location | Note |
|------|----------|------|
| `cmd_run` | `run.py:240-302` | Iterates `eval_set.documents`, **skips `held_out`** (`:260-261`), parses + `run_detection` **per document** (`:263-273`), `compute_metrics(report, eval_set, doc.doc_id, source_text=...)` (`:280`), writes `args.out` (`:287`), optional `check_gate` per doc (`:295-301`). One document raising never crashes the run (`:274-276`). |
| Constants | `run.py:53-57` | `DEFAULT_DOC_ID="mvr1381"`, `BASELINE_PATH = evals/baseline/recall_by_family.json`, `RETRIEVAL_BASELINE_PATH`. |
| Subcommands | `run.py:305-335` | `score`, `gate`, `run`, `retrieval-gate`. |
| `compute_metrics` | `metrics.py:196-228` | Produces `end_to_end`, `end_to_end_by_family`, **`recall_by_family`**, `retrieval_recall_at_k`, `parse_fidelity`, `anchor_rate`, `verifier`. |
| `recall_by_family` | `metrics.py:230-234` | `{family: values["recall"]}` from `_end_to_end_by_family` (`:57-72`), which re-scores the same finding list against each family's GT subset in turn. All four family keys always present. |
| `matches(fault, gt)` | `match.py:66-92` | `_anchor_tokens(gt.evidence_anchor)` → all tokens must appear in `_norm(fault["evidence"])`. **`evidence` only — never title/detail** (`:74-83`). **`if not tokens: return False`** (`:89-90`). |
| `_TOKEN_RE` / `_WORD_RE` | `match.py:27-28` | `[0-9][0-9./]{3,}` (≥4 chars) and `[a-z]{6,}`. |
| `score` | `match.py:105-139` | Many-to-one collapse for recall; per-finding FP counting. |
| `check_gate` | `gate.py:51-64` | `lost = baseline_ids - matched`; `ok = not lost`. Finding *more* never fails. |
| `baseline_found_ids` | `gate.py:21-34` | `{tp_required ids} ∪ extra` (extra = the committed `found_set`). |
| `load_captured` / `golden_report` | `capture.py:16-28` | Loads a serialized `FaultReport` for LLM-free re-scoring. |

**What a "harness/matcher version" concretely is today: nothing.** `grep -rn "VERSION\|__version__\|_version" src/evals/*.py` returns **no results** [VERIFIED]. There is no version constant anywhere in the eval package. D-TEL1(i) therefore requires **building** it. Recommendation:

```python
# src/evals/__init__.py
HARNESS_VERSION = "1"      # bump on any change to run.py / metrics.py / gate.py / schema.py
MATCHER_VERSION = "1"      # bump on any change to match.py's tokenization or matching rule
```
plus a computed `matcher_content_sha256` over `match.py` recorded in each run summary. The constant is the human contract; the content hash is the thing that cannot be forgotten. Both go in the D-TEL1 provenance block and in the pre-registration, so rider (iii) is machine-checkable rather than a promise.

**Scripting the 3-run median comparison (D-GO2/D-LOOP2):** each arm writes `FaultReport` JSON per run → `capture.load_captured` → `metrics.recall_by_family(report, eval_set, "mvr1381")` → `statistics.median` per family across the 3 runs, plus min/max for the variance report. No new metric code, no re-implementation. Pure composition of existing functions — which is exactly what rider (iii) demands.

### D8 — `event_bus` / WebSocket

`emit_sync(job_id, layer, event_type, agent_name="", message="")` [`event_bus.py:39-45`] handles both running-loop and no-loop contexts. `AgentEvent` [`schemas/events.py:22-29`] has `job_id, layer, event_type, agent_name, message, metadata: dict`.

**Constraint:** `EventType` is a **closed `Literal`** [`events.py:7-17`] with 9 members and `LayerName` is `Literal["parse","detection"]` [`:19`]. Agent-step events must **add** members (e.g. `"agent_turn"`, `"tool_call"`, `"budget_update"`, `"continuation"`) and likely `"review"` to `LayerName`. This is additive and low-risk, but it is a schema edit, not a free extension — and `metadata: dict` is the right carrier for per-turn numbers so the message string stays human-readable.

### D9 — `src/config.py`

```python
# config.py:93-98
DETECTOR_MODELS = {
    "databricks-meta-llama-3-3-70b-instruct": "Llama 3.3 70B",
    "databricks-qwen35-122b-a10b":            "Qwen3.5 122B · A10B (MoE)",
    "databricks-qwen3-next-80b-a3b-instruct": "Qwen3-Next 80B · A3B (MoE)",
}
# config.py:100-105
resolve_detector_model(model: str | None) -> str   # allow-list only, else Settings.detector_model
```
Also relevant: `structured_output_strict: bool = True` `:49`, `structured_output_max_repair_calls: int = 1` `:50`, `max_tokens_ceiling: int = 8000` `:51`, `detector_model` property `:70`.

Both Qwen endpoint names appear in the Databricks FM APIs supported-models list [CITED: docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models], though that page does not document function-calling support per model — the project's settled 2026-07-30 probe is the authority there.

**Note for D-BUD5:** `max_tokens_ceiling = 8000` caps *per-call output*, not the run. The run ceiling is a new, separate concept owned by `BudgetLedger`. Do not overload the existing setting.

### D10 — `src/parse/pdf.py`: P2's target, located exactly

```python
# pdf.py:214-237
for page in doc:
    tables  = extract_tables(page)
    scanned = is_scanned_page(page)
    blocks: list[LayoutBlock] = []          # :217  ← stays EMPTY on the fallback branch
    figures: list[LayoutFigure] = []        # :218
    source = "pymupdf"
    if scanned:
        source = "rapidocr"
        ocr_result = ocr_page(page)
        if ocr_result is not None:
            text, ocr_tables, blocks, figures, ocr_source = ocr_result   # :225
            ...
        else:
            source = "rapidocr-fallback"    # :232
            text = page.get_text("text")    # :233  ← COMPUTED AND THEN DISCARDED
    else:
        text   = page.get_text("text")      # :235
        blocks = _digital_blocks(page, tables)   # :236
        figures = _digital_figures(page, blocks) # :237
    pages.append({... "blocks": [...], "tables": [...], "figures": [...]})   # :239-252
```

**Why `text` is discarded:** the appended page dict at `:239-252` contains `page_number, page_label, width, height, rotation, source, is_scanned, blocks, tables, figures` — **there is no `text` key.** `text` is used only for `_detect_page_label(text)` at `:242`. Every downstream consumer reads `blocks`: `ingest/serialize.py:55-57`, `checklists._reading_order_text` [`checklists.py:51-56`], `verify._doc_corpus` [`verify.py:97-98`].

**When the branch is taken:** `ocr_page` returns `None` when *"no OCR API available (e.g. local dev without creds) → skip"* [`ocr.py:82`]. `is_scanned_page` returns True when any image covers > the coverage threshold **or** a glyphless font is present [`ocr.py:53-72`] — i.e. a scan carrying an invisible OCR text layer is flagged scanned, and offline the embedded layer is then thrown away. Exactly the SC4 7/12 gap.

**Minimal fix (2 lines):**
```python
        else:
            source = "rapidocr-fallback"
            text   = page.get_text("text")
            blocks = _digital_blocks(page, tables)      # NEW
            figures = _digital_figures(page, blocks)    # NEW
```
`_digital_lines`/`_digital_blocks` read `page.get_text("dict")` [`pdf.py:123`], which returns the embedded text layer regardless of the page also carrying a full-page image. On a genuinely image-only scan it yields zero text blocks — identical to today's behavior, so the fix is safe in both directions.

**The fix is 2 lines; the cache invalidation is the real work.** See §Runtime State Inventory.

---

## The Measurement Instrument: what can and cannot be scored

Computed this session from the committed dataset [VERIFIED: `src/evals/dataset/*.deficiencies.json` + `src/evals/match.py` tokenization replayed].

### Frozen baseline

`src/evals/baseline/recall_by_family.json`: `generated_from "golden:mvr1381_run3"`, overall recall **0.071** (tp 2, fp 25, fn 26), precision 0.074, `anchor_rate` 0.581, `found_set ["C-01","C-02"]`, `recall_by_family {absence_of_evidence 0.0, derivation_plausibility 0.0, cross_reference_integrity 0.286, regulatory_framing 0.0}`. It records **no model id** — D-LOOP2's re-measurement closes that gap.

### Ground-truth inventory

| doc_id | held_out | absence | derivation | cross-ref | regulatory | total |
|--------|----------|---------|------------|-----------|------------|-------|
| `mvr1381` | no | 11 | 5 | 7 | 5 | **28** |
| `minispec` | no | 1 | 0 | 3 | 0 | 4 |
| `spec32s41` | **yes** | 2 | 0 | 1 | 0 | 3 |

`documents.json`: `mvr1381` → `data/32s43-validation-related-compounds-method.pdf` (pdf); `minispec` → `src/evals/dataset/docs/mini_spec.docx` (docx); `spec32s41` → `data/32s41-Specification.pdf` (pdf, `held_out: true`).

### ⚠ Structurally unmatchable ground truth — six items no architecture can score

`match.matches()` returns `False` unconditionally when `_anchor_tokens(gt.evidence_anchor)` is empty [`match.py:89-90`]. Six GT anchors produce zero tokens under `_TOKEN_RE = [0-9][0-9./]{3,}` (≥4 chars) and `_WORD_RE = [a-z]{6,}` [`match.py:27-28`]:

| doc | id | family | anchor | why zero tokens |
|-----|----|--------|--------|-----------------|
| `mvr1381` | **A-07** | absence_of_evidence | `'0.5%'` | `%` outside the char class; `0.5` is 3 chars |
| `mvr1381` | **B-06** | absence_of_evidence | `'485'` | 3 chars, below the 4-char floor |
| `mvr1381` | **B-03** | cross_reference_integrity | `'389'` | 3 chars |
| `mvr1381` | **C-03** | cross_reference_integrity | `'ND'` | 2 letters, below the 6-letter floor |
| `mvr1381` | **D-01** | cross_reference_integrity | `'45, 56'` | both 2 chars |
| `spec32s41` | H-02 | cross_reference_integrity | `'NMT 3.5%.'` | `3.5` is 3 chars; `NMT` 3 letters |

**Ceilings this imposes on the scored document:**

| Family | GT items | Unmatchable | **Max recall** | Baseline | Headroom |
|--------|---------|-------------|----------------|----------|----------|
| `absence_of_evidence` | 11 | 2 | **0.818** (9/11) | 0.0 | 9 items — the headline family is reachable |
| `derivation_plausibility` | 5 | 0 | **1.000** | 0.0 | 5 items — **cleanest path to D-GO1(a)** |
| `regulatory_framing` | 5 | 0 | **1.000** | 0.0 | 5 items — **cleanest path to D-GO1(a)** |
| `cross_reference_integrity` | 7 | 3 | **0.571** (4/7) | 0.286 (C-01, C-02) | only 2 more items exist |
| **overall (`mvr1381`)** | **28** | **5** | **0.821** (23/28) | 0.071 | — |

The 4-char / 6-letter floors are a deliberate, documented choice [`match.py:19-26`] — the comment records that a 3-char floor let a bare `"0.5"` false-match an unrelated GT item. **Do not change it.** Changing the matcher is a harness change and voids the D-GO1(iii) comparison. The correct response is to **classify these items in the pre-registration**, not to fix them.

**Direct consequence for D-GO4:** the pre-registration needs **three** buckets, not two:
1. **Matcher-unreachable** — the 5 `mvr1381` items above. Unreachable for *any* system, this phase or later. Naming them prevents Phase 4 from chasing them.
2. **Structurally unreachable by a single agent** — items needing cross-document traversal (`follow_reference` returns `cross_document_resolution_pending_phase_4`). D-GO4(a)'s named category.
3. **Reachable** — everything else. This is the set D-GO4(a) tests "was every reachable item found?" against.

The `tp_required` protected set is exactly `{C-01 ('11477'), C-02 ('0.15')}` [VERIFIED: both `tp_required: true`, both in `cross_reference_integrity`, both tokenize cleanly] — consistent with `gate.baseline_found_ids` and the committed `found_set`.

### ⚠ FLAG (D-BUD1 / D-BUD5 corollary): the held-out calibration corpus is inadequate

CONTEXT.md instructs flagging rather than substituting. **Flagging.**

`spec32s41` is the **only** genuinely held-out real submission document, and it is **one PDF**. Everything else available:

| Path | Status |
|------|--------|
| `data/32s41-Specification.pdf` | = `spec32s41`, held out, but **carries 3 GT deficiencies** |
| `data/32s43-validation-related-compounds-method.pdf` | = `mvr1381` — **scored** |
| `src/evals/dataset/docs/mini_spec.docx` | = `minispec` — **scored** |
| `Sample Data/*.pdf` | byte-duplicates of the two `data/` PDFs |
| `data/test_spec.pdf` | 1,425 bytes — a toy fixture, not a submission document |

D-BUD5's corollary requires calibration over a **FULL multi-document review**, because a per-run budget's whole purpose is to measure how an agent *allocates* across documents. A single document cannot exercise that — the observed consumption would be a lower bound with unknown scaling, and freezing a `3× median` ceiling on it risks D-BUD1(c)'s "infeasible multiple" scenario discovered *during* run 1.

Three options for the reviewer, none of which touches scored data:

| Option | What it costs | What it buys |
|--------|---------------|--------------|
| **(a) Source 2–4 additional real submission PDFs/DOCX** with no GT labels, register them as a `calibration/` corpus outside `src/evals/dataset/` | External sourcing effort | A genuine multi-document consumption measurement. **Recommended.** |
| **(b) Generate a synthetic multi-document corpus** via `src/evals/make_docx_fixture.py`'s deterministic pattern (`:1-25`) — e.g. 3–4 DOCX modules of realistic length | Small build effort; consumption may under-represent real PDFs (no scanned pages, simpler tables) | Deterministic, committed, repeatable. Acceptable **if the report states the figure is a lower bound.** |
| **(c) Calibrate on `spec32s41` alone and declare the limitation** | Zero effort | Violates D-BUD5's corollary in substance. **Only acceptable with an explicit, reviewer-confirmed disclosure**, and the ceiling should then be set from a *larger* multiple with the reasoning recorded. |

This is a **reviewer decision before the pre-registration is committed**, since the calibration multiple and the corpus both land in it.

---

## Runtime State Inventory

Phase 3 contains a parse-layer change (P2) whose blast radius is cached state, so this section applies.

| Category | Items found | Action required |
|----------|-------------|-----------------|
| **Stored data / caches** | **`data/ingest_cache/` — 6 entries, all keyed `{content_hash}__nfc-wscollapse-gdehyph-lig_1-lex1__reading-order-cells_1.json`.** `cache_key(content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION)` [`ingest/store.py:35-39`] and `content_hash = content_hash(file_bytes)` [`ingest/corpus.py:119`]. **No parser version participates in the key.** A `pdf.py` change alters canonical text and every span offset while the key stays identical. | **Data migration + code edit.** (1) Add `PARSER_VERSION` to `src/parse/pdf.py` and fold it into `cache_key` (matches the existing D-24 version-stamping discipline). (2) Purge `data/ingest_cache/` and re-ingest as an explicit, verified task step. (3) A test asserting a `pdf.py`-version bump changes the cache key. |
| | `data/tool_scratch/` — `oversized.py` persist/preview handles [`oversized.py:15 DEFAULT_SCRATCH_DIR`]. Handles are per-run and consumed by `get_section(handle=...)`. | **None required**, but the loop should not assume handles survive across runs; treat a `not_found` on a handle as an ordinary teaching rejection [`get_section.py:75-80`]. |
| | `data/defpredict.db`, `data/deficiency_kb.faiss`, `data/rulebook_cache/` (607 entries) | **None.** Rulebook cache is keyed by rulebook build, untouched by `pdf.py`. |
| **Live service config** | None — no external service holds Phase-3-relevant configuration. Databricks endpoints are named in `config.py`, in git. | None. |
| **OS-registered state** | None — no scheduled tasks, no daemons, no pm2/systemd/launchd units found. | None. |
| **Secrets / env vars** | `DATABRICKS_HOST` / `DATABRICKS_TOKEN` via `Settings` [`config.py`]; no key names change this phase. | None. |
| **Build artifacts / installed packages** | `.venv` has `openai 2.43.0` while `pyproject.toml` pins `openai>=1.40`; `autogen-agentchat` / `autogen-ext` are still pinned but unused. | Optional hygiene: remove the `autogen-*` pins; consider raising the `openai` floor (§Standard Stack). |
| **Committed baselines** | `src/evals/baseline/recall_by_family.json` (0.071) and `retrieval_recall.json` (0.875 / 0.643). **P2 can move both.** | D-PRE1(a): the shift is measured, disclosed, and attributed to the parse fix. D-LOOP2's re-baselining runs *after* P2 for exactly this reason. |

**The canonical question — after every file is updated, what runtime state still holds the old value?** Answer for this phase: **the ingest cache, and only the ingest cache.** It is invisible to `git status`, it has no version guard against parser changes, and it is upstream of every span offset the entire grounding contract rests on. If P2 ships without cache invalidation, the recall baseline is re-measured against stale canonical text and the "measurement integrity, frozen now" rider is silently violated.

---

## Common Pitfalls

### Pitfall 1 — A span-ID re-mint bug is indistinguishable from model span-invention (produces a WRONG NO-GO)

**What goes wrong:** the loop parses `"mvr1381:14820:14975"` and re-mints a `SpanID` with the wrong `normalizer_version` (or resolves against the wrong store). `ledger.was_issued()` passes — it keys on `(doc_id,start,end)` only [`ledger.py:17,23,26`] — then `open_span` raises `HashMismatch` [`anchors.py:56-64`] and `emit_finding` returns `not_byte_exact` with `half='submission'` [`emit_finding.py:83-86`].
**Why it's severe:** D-TEL3 pre-registers `half=submission` + `not_byte_exact` as **SPAN INVENTION — grounding-discipline failure, the loop is unreliable.** A loop-side parsing bug would present as the model fabricating quotes and could drive a NO-GO on the wrong diagnosis, on a gate that decides three subsequent phases.
**How to avoid:** (a) a `spanref` module that is the single parse/mint path, resolving `normalizer_version` from `corpus.cached_entry(doc_id)["normalizer_version"]` or `rulebook_nt_for(doc_id).normalizer_version`; (b) a **distinct loop-side reason code** (e.g. `span_ref_unparseable`, `span_ref_unknown_doc`) so a reference the loop could not resolve never reaches the gate as a fabricated-quote signal; (c) the round-trip composition test in §Validation Architecture.
**Warning signs:** `half=submission` + `not_byte_exact` at a high, *uniform* rate across turns and documents — model invention should be bursty and correlated with context depth, not flat.

### Pitfall 2 — GROUND-03 is satisfied at the call and lost in the output

**What goes wrong:** `emit_finding` validates `rule_span_id` thoroughly, then discards it — only `rule_citation or rule_span_id.doc_id` survives in `guidance_refs` [`emit_finding.py:112-117`]. `verdict` is stringified into `detail` [`:98`]. Both are documented as accepted Phase-2 boundaries at `:94-97` and `:100-111` because `schemas/faults.py` was off-limits.
**Why it matters:** GROUND-03 asks that *each finding is dual-cited*; DETECT-04 asks for an enumerated verdict the harness can score. Neither is true of the stored object today, and Phase 5's verifier explicitly needs to re-open the exact rule span.
**How to avoid:** add to `Fault` in this phase — `verdict: ComplianceVerdict`, `rule_span_id: SpanID | None`, and (recommended) `submission_span_id: SpanID | None` so a finding is fully re-openable. All defaulted, so every existing construction site and the committed golden fixtures keep validating.
**Warning sign:** a plan that treats DETECT-04 as prompt-craft rather than a schema change.

### Pitfall 3 — Multi-turn is outside Databricks' documented envelope

**What goes wrong:** the platform states *"During Public Preview, function calling on Databricks is optimized for single turn function calling"* and *"For multi-turn function calling Databricks recommends the supported Claude models"* [CITED: docs.databricks.com/aws/en/machine-learning/model-serving/function-calling].
**How to avoid:** do not design around it — that is the phase's question. Do (a) pre-register a **turn-indexed** fidelity metric, not just a run aggregate, so degradation-with-depth is visible rather than averaged away; (b) record the turn index at which the first malformed call appears; (c) treat the result as a **model-selection** finding per D-TEL4, never an architecture verdict.
**Corroborating evidence, honestly rated:** published multi-turn degradation figures (~39% average accuracy drop; severe drop-offs beyond ~40 turns; middle-turn citation below 20%) are **directional, not model-specific** — LOW-to-MEDIUM confidence, drawn from secondary summaries. One arXiv-derived claim that *"Llama 3.3 models are generally unable to produce executable tool calls"* **directly contradicts this project's own settled probe** (2026-07-30: every served model returned a valid `search_corpus` tool_call on the first try). The project's probe is the higher-confidence evidence for single-call behavior; the published work is only weak evidence about *depth*.

### Pitfall 4 — `read_guideline` enumerate turns are productive but yield zero span-IDs (D-BUD2 hole)

**What goes wrong:** in enumerate mode (`citation=None`), `read_guideline` returns requirement metadata `[{requirement_id, citation, rule_doc_id, trigger}]` and **records no spans** [`read_guideline.py:45-57` — no `ledger.record_span` on that path]. Under D-BUD2's literal definition ("new unique span-IDs retrieved OR new findings passing the emit gate"), an enumerate turn is **unproductive**. Two enumerate calls plus one already-seen search would trip a DR window of 3 and halt the loop **during the exact RULES-05 mechanism `absence_of_evidence` depends on.**
**Why it's easy to miss:** every other tool records spans, so the definition looks total.
**How to avoid:** amend D-BUD2 in the pre-registration to add a third productivity clause — *"or a requirement_id enumerated for the first time this session."* Small, principled, and it keeps the enumerate→fetch→emit chain from being punished by the stop rule built to catch circling.
**Warning sign:** runs ending `diminishing-returns` with a low turn count and `absence_of_evidence` still at 0.0.

### Pitfall 5 — `_sanitize` was built for `response_format`, and tool schemas have stricter rules

**What goes wrong:** `_sanitize` **preserves `$defs`** by design [`structured.py:37`], and Databricks prohibits `$ref` in tool schemas [CITED, verbatim: *"Complex nested or schema composition and validation using: `anyOf`, `oneOf`, `allOf`, `prefixItems`, or `$ref`"*]. It also keeps `anyOf` when there are 2+ non-null variants [`:59`]. `build_response_format` [`:76-87`] emits the wrong wrapper for tools.
**How to avoid:** add `tool_schema_for_databricks()` and `build_tool_schema()` **beside** the existing functions (never modify them — `structured.py` is a hardened asset). Keep arg models flat so `$ref` never appears in the first place; the inlining pass is then a safety net with an assertion, not a load-bearing transform. **Ship a test that asserts no `$ref`, no `$defs`, no `anyOf`/`oneOf`/`allOf`/`prefixItems`, no `pattern`, and ≤16 keys in every emitted tool schema** — cheap, offline, and it catches the whole class.
**Warning sign:** a `BadRequestError` on the first tool turn that the `client.py:104-113` handler re-raises with `llm_bad_request`.

### Pitfall 6 — Multiple optional tool parameters cause repeated near-miss calls on Qwen, starting ~30k tokens

**What goes wrong:** a reported failure with Qwen3.5-35B-A3B and Qwen3-Coder-Next: *"It repeatedly calls the same tool; the call is almost correct, but one optional parameter is missing; after noticing the mistake, it retries; the retry misses a different parameter or still omits one."* Failures become noticeable around **30,000 tokens (~20% of context)**, and *"when I changed the `offset` parameter from optional to required, the problem disappeared entirely."* [CITED: github.com/ggml-org/llama.cpp/issues/20164 — MEDIUM confidence: a single well-documented issue on a different serving stack, but the mechanism is schema-shape-driven and stack-independent.]
**Why it lands squarely here:** `get_section` has **four** optional params (`start`, `end`, `heading`, `handle`) [`get_section.py:51-54`] and `read_guideline` has **three** (`citation`, `family`, `handle`) [`read_guideline.py:33-39`] — and D-RI2 deliberately locks the single-optional-`citation` enumerate-vs-fetch surface as *"exactly"* what the Phase-3 go/no-go tests. Worse, this failure mode presents as D-BUD3's "identical `(tool, args)` N times" and as a D-TEL4 malformed-arg rate — i.e. it would be **diagnosed as model incompetence when it is a fixable schema shape.**
**How to avoid — a recommendation that respects the lock:** keep the D-RI2 surface as the primary (testing it is the charter), **and** (a) add a dedicated telemetry counter for *"same tool, args differing only by which optional field is absent"* so the pattern is nameable in the report rather than folded into the breaker count; (b) pre-register a **named, bounded fallback**: if that counter dominates, split the multi-mode tools into single-mode schemas with all-required params over the *same* Python functions (`list_requirements(family)` / `read_rule(citation)` / `continue_rule(handle)`; `get_section_by_heading` / `get_section_by_span` / `continue_section`). Databricks allows 32 tools, so 11 is fine. Declaring the fallback in the pre-registration keeps it from being a mid-set configuration change (which D-GO2(ii) would void the set for).

### Pitfall 7 — `search_corpus` re-embeds the entire corpus on every call

**What goes wrong:** `search_corpus` calls `_build_chunks(corpus)` [`search_corpus.py:40`] — which walks every parsed document, re-reads each cache entry, and re-windows it into 800-char chunks [`:24-36`] — then `embed_texts([...])` over **all** chunks [`:49`]. `embed_texts` has **no caching** [`retrieval/vector_search.py:40-50`]; on Databricks it makes a network call per batch of 16 [`:20-37`], and locally it runs SentenceTransformer with `show_progress_bar=True`.
**Why it matters here specifically:** D-BUD5 states *"Wall-clock includes tool execution time"* and the ceiling *"bounds real elapsed cost, not model-thinking time alone."* A 30-turn loop making 10 `search_corpus` calls re-embeds the corpus 10 times. On the held-out calibration corpus this inflates the measured median, and the frozen ceiling then encodes an artifact.
**How to avoid:** memoize `_build_chunks` + embeddings per `CorpusIndex` instance for the life of a run (keyed on the manifest content-hash). This is a **tool-layer performance fix, not a contract change** — identical results, identical span-IDs. If the planner judges it out of scope, then **measure and report the embedding time separately** so the calibration median is honest about what it contains.
**Warning sign:** wall-clock dominated by tool time with a low token count; `dedup_hit_rate()` near zero while elapsed time climbs.

### Pitfall 8 — Token accounting: `usage` is discarded today, and naive summation has two different meanings

**What goes wrong:** `client.py:98-103` never reads `response.usage`. Without it, D-BUD5 cannot be implemented at all. And once it is available, `Σ(prompt_tokens + completion_tokens)` across turns **re-counts conversation history every turn** — it is the *billed* total, not the unique-token total, and the two diverge by a large factor over 30 turns.
**How to avoid:** (a) surface `prompt_tokens`, `completion_tokens`, `cached_tokens`, `usage_present` on the turn result; (b) **pre-register that the budget is billed tokens** — `Σ(prompt_tokens + completion_tokens)` — because that is real cost and it naturally penalizes history growth, which is exactly the pressure D-BUD5 intends; (c) record `Σ cached_tokens` separately so the D-LOOP4 caching lever is visible even though Phase 6 owns exploiting it; (d) if `usage` is absent, fall back to a declared `len(text)//4` estimate and set `usage_present=False` on the run summary so no reader mistakes an estimate for a measurement.
**Warning sign:** a budget curve in the JSONL that is linear in turns rather than super-linear — that means history is not being counted.

### Pitfall 9 — `run_oracles`-the-tool sits across an impedance mismatch

**What goes wrong:** `run_oracles(doc: dict)` [`oracles.py:221`] and `run_checklists(doc: dict, ctd)` [`checklists.py:184`] consume the `extract_pdf` page/block dict. The tool layer consumes `CorpusIndex` + canonical text + span-IDs. Worse, checklist findings are **absence** findings whose `evidence` is a *synthesized* string (`"No mention of {element} (searched for: ...)"` [`checklists.py:92`]) — **there is no source span for text that is absent.**
**Why it matters:** D-ORC1 requires leads whose span-IDs are issued through the identical path as every other tool result, and D-ORC2 requires the agent to re-open each lead before `emit_finding` accepts it. An absence lead has nothing to re-open.
**How to avoid:** `run_oracles`-the-tool returns two lead kinds, honestly typed:
- **positive leads** (from `oracles.py`'s arithmetic/consistency battery, which *do* quote real text) → carry a `doc_id` + a locating hint the agent turns into a real `get_section` call; the span-ID is issued by `get_section`, never by the oracle tool (D-ORC2).
- **absence leads** (S9/S10/P10) → carry the *expected element* and the *scope searched*, and direct the agent to `read_guideline` for the requiring rule plus `get_section` on the section that **should** contain it. The submission span the finding ultimately cites is the **surrounding section that demonstrably lacks the element** — which is a real, re-openable span, and is also what the GT anchors expect (`A-04`'s anchor is `'degradants'`, `B-02`'s is `'standard deviation of the response'` — tokens that appear in the *nearby* text).
This last point is the mechanism by which `absence_of_evidence` can move at all, and it deserves to be stated explicitly in the plan rather than discovered at run time.
**Warning sign:** an `absence_of_evidence` recall of 0.0 accompanied by a high `half=submission` `not_retrieved_this_session` count — the agent is trying to cite absence without a span.

### Pitfall 10 — Message-history construction for tool turns

**What goes wrong:** OpenAI-compatible tool protocols require the assistant message carrying `tool_calls` to be echoed back into `messages` **verbatim**, and each tool result appended as `{"role":"tool","tool_call_id": <id>,"content": <str>}`. Reconstructing the assistant message by hand (dropping `tool_calls`, or mismatching `tool_call_id`) produces 400s or silent context loss. [ASSUMED — standard OpenAI protocol behavior, not verified against Databricks this session.]
**How to avoid:** keep `raw_message` on the turn object (`message.model_dump()`) and append it unmodified. Assert in a test that every `tool` message's `tool_call_id` exists in the immediately preceding assistant message.
**Also:** *"Parallel function calling is not supported"* [CITED: Databricks] — the loop should still iterate `tool_calls` (a list) defensively, but must not *depend* on more than one per turn.

---

## Code Examples

### Deriving a Databricks-legal tool schema (D-LOOP3)

```python
# src/llm/structured.py  (ADD — never modify schema_for_databricks/_sanitize)
def _inline_refs(node, defs: dict):
    """Resolve $ref against $defs and drop the $defs block.
    Databricks tool schemas prohibit $ref (docs.databricks.com/.../function-calling)."""
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return _inline_refs(defs[name], defs)
        return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(v, defs) for v in node]
    return node


def tool_schema_for_databricks(model_cls: type[BaseModel]) -> dict:
    raw  = model_cls.model_json_schema()
    defs = raw.get("$defs", {})
    return _sanitize(_inline_refs(raw, defs))          # reuse the hardened pass


def build_tool_schema(model_cls: type[BaseModel], name: str, description: str) -> dict:
    return {"type": "function",
            "function": {"name": name, "description": description,
                         "parameters": tool_schema_for_databricks(model_cls)}}
```

### A tool arg model that is legal under every documented restriction

```python
# src/agents/review/registry.py
class EmitFindingArgs(BaseModel):
    """Flat scalars only: no nested models ($ref prohibited), no unions beyond `X | None`
    (anyOf prohibited beyond the null-flattening _sanitize already performs), 8 keys ≤ 16."""
    submission_span_id: str = Field(description="A span-ID exactly as shown, e.g. mvr1381:14820:14975")
    rule_span_id:       str = Field(description="A rule span-ID returned by read_guideline")
    verdict:            ComplianceVerdict            # StrEnum → {"type":"string","enum":[...]}
    title:              str
    detail:             str
    rule_citation:      str = ""
    requirement_id:     str = ""
```
`ComplianceVerdict` as a `StrEnum` renders as `{"type":"string","enum":["violation","gap","ambiguous"]}` — no `anyOf`, no `$ref`. `title` is **required** so findings are distinguishable (see §D5's `_dedup_key` collapse).

### The static-prefix invariant (D-LOOP4)

```python
# src/agents/review/prompts.py
SYSTEM_PROMPT = """..."""          # module constant — no f-string, no .format(), no corpus data

# src/agents/review/loop.py
def build_messages(corpus_brief: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},        # ← STATIC PREFIX
        {"role": "user",   "content": corpus_brief},         # ← manifest/doc-count/families HERE
    ]
```
Precedent: Claude Code moved the agent list **out of the tool description** into an attachment message; a dynamic description busted the whole tool-schema cache, measured at *"~10.2% of fleet cache-creation tokens"* [CITED: `.planning/research/CLAUDE-CODE-TEARDOWN.md:69-71`].

---

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|--------------|------------------|--------------|-------------|
| Anthropic-style explicit `cache_control` breakpoints | **Databricks prompt caching is implicit** — *"customers do not need to configure anything"* — covering GPT-OSS 20B/120B, Gemma 3 12B, Llama 3.1 8B, and **Llama 3.3 70B**, across batch, pay-per-token and provisioned throughput | Announced on the Databricks blog [CITED: databricks.com/blog/accelerating-llm-inference-prompt-caching-open-source-models-databricks] | D-LOOP4 is about **prefix stability**, not about calling a caching API. No client change is needed to *get* caching — only discipline to *keep* it. A production pipeline in that post reports *"a relatively low cache hit ratio of 30%"*, which is a useful reality check on Phase 6's expectations. |
| Tool schemas as free-form JSON Schema | Databricks restricts: no `pattern`, no `anyOf`/`oneOf`/`allOf`/`prefixItems`/`$ref`, ≤16 keys, ≤32 functions, no parallel calls | Documented on the function-calling page [CITED] | Directly shapes every tool arg model (§Pitfall 5, §Pitfall 6). |
| "Tool calling works, therefore agents work" | Vendor guidance separates **single-turn** (optimized) from **multi-turn** (recommends Claude models) | Same page [CITED] | Elevates the ROADMAP research flag from a design worry to a documented platform boundary. |

**Deprecated / outdated in this repo:**
- `autogen-agentchat` / `autogen-ext` pinned in `pyproject.toml` — the AutoGen design was removed (CLAUDE.md "What NOT to Use").
- Repo `README` / `PIPELINE` / `DIAGNOSIS` / `RELIABILITY` / `PHASES` describe the removed 3-layer AutoGen design — do not trust their file references (PROJECT.md "Known debt to avoid inheriting").
- `.planning/STATE.md:75` records *"Uncommitted working tree: a partial planner/summariser/sandwich/workers redesign is uncommitted on branch `CLI_for_folders`."* **This is now stale** — see Open Question 1.

---

## Recommendations for the Discretionary Values

Every one of these lands in the committed pre-registration (D-GO5). Each carries its rationale so the reviewer can overrule with information.

### Concrete N values

| Parameter | Recommendation | Rationale |
|-----------|---------------|-----------|
| **Circuit breaker — identical `(tool, args)`** (D-BUD3) | **3** | Claude Code's own budget logic uses `continuationCount >= 3` as its repetition threshold [`CLAUDE-CODE-TEARDOWN.md:84-86`]. Three byte-identical calls is unambiguous circling with no plausible innocent reading. |
| **Circuit breaker — consecutive same `(reason_code, half)`** (D-BUD3) | **4** | More permissive than the identical-args rule *by design*: D-LOOP5 makes a rejection a teaching turn with a `hint`, so the model deserves 2–3 genuine self-correction attempts. Four consecutive same-class failures means the hint is not landing — which is the actual pathology D-BUD3(second condition) targets. |
| **Diminishing-returns window** (AGENT-03 / D-BUD2) | **3 consecutive unproductive turns** | Matches the Claude Code precedent's `>= 3`. **2 is unsafe** given Pitfall 4 (an enumerate turn yields no spans) even *with* the recommended D-BUD2 amendment, because a plausible legitimate sequence is enumerate → enumerate(different family) → search-returning-known-spans. |
| **Hard max continuations** (D-BUD4) | **5** | D-TEL5's own example wording in CONTEXT.md is *"nudged 4 of a permitted 5"* — the decision authors were already reasoning at 5. It gives headroom over the DR bound (3) so the two bounds are genuinely distinguishable, which is precisely what D-BUD4 wants to measure ("record which bound ended the nudging"). |
| **Hard max turns** | **50** | The ROADMAP frames the unknown as "20–50 turns." Pitfall 6's evidence puts the degradation onset near 30k tokens; 50 turns comfortably contains both the reliable zone and the degradation zone, so the telemetry actually captures the transition instead of stopping before it. |
| **Calibration multiple — tokens** (D-BUD1a) | **3× the observed median billed tokens** | The example in D-BUD1(a) itself. Written before calibration executes. |
| **Calibration multiple — wall-clock** (D-BUD1a) | **4× the observed median elapsed** | A separate, larger multiple because tool-execution time is heavier-tailed than token count — `search_corpus` re-embeds the corpus per call (§Pitfall 7) and Databricks rate-limit backoff reaches 60s per retry [`client.py:19`]. Using one multiple for both would make wall-clock the binding constraint for infrastructure reasons rather than agent reasons. |

### D-VER2 verdict enum — recommend exactly three members

```python
class ComplianceVerdict(StrEnum):
    VIOLATION = "violation"   # the submission's text contradicts an explicit requirement of the cited rule
    GAP       = "gap"         # the rule requires something the submission does not contain
    AMBIGUOUS = "ambiguous"   # the rule applies, but the submission is insufficient to determine compliance
```

Rationale, in three parts:
1. **They map onto the families that must move.** `gap` ↔ `absence_of_evidence` (the headline expectation); `violation` ↔ `cross_reference_integrity` and `derivation_plausibility`; `ambiguous` ↔ `regulatory_framing`. A verdict distribution then becomes a second, independent read on *which mechanism fired* — useful diagnostic value for free.
2. **Mutually exclusive and exhaustive over "this is a deficiency."** Any finding is one of: contradicts, omits, or is under-determined.
3. **`compliant` is deliberately unrepresentable.** `verify.py::_concedes_compliance` exists because a live run emitted 10 of 31 "faults" whose own title ended *"compliant. No finding."* [`verify.py` docstring]. Making a compliant verdict impossible to express is the code-gate version of that lesson — the same discipline as `not_unique` being structurally unreachable in `emit_finding` [`emit_finding.py:9-18`].

### Loop module path

**`src/agents/review/`** — mirroring `src/agents/detection/` file-for-file. This is not invention: `.planning/research/ARCHITECTURE.md` already specifies *"`agents/review/` mirrors the existing `agents/detection/` file-for-file so the evolution is legible… Keep `agents/detection/` intact until `review/` passes eval, then retire it."* It also satisfies D-LOOP1's flag requirement structurally rather than by branching.

### Flag mechanism

**A new entry point + a new harness subcommand, plus a config setting for the API path only.**

The signatures are incompatible (`run_detection` is per-document; the loop is per-corpus with a per-run budget), so a pure config flag cannot express the difference without smuggling a per-document budget back in — *"2/28 by a different route."* Recommend:
1. `src/agents/review/__init__.py::run_review(corpus, ...)`
2. `python -m evals.run agent-run --model ... --out ...` beside the existing `run` [`evals/run.py:323-327`]
3. `Settings.detection_mode: Literal["legacy","agent"] = "legacy"` for `agents/orchestrator.py:34`

Both arms then run back-to-back on the same corpus from one CLI, with the legacy path byte-identical.

### Where the grounded partial surfaces

Return `FaultReport` with a `stop_reason` recorded in `domains_checked` **or** — cleaner — add `stop_reason: str = ""` and `budget_exhausted: bool = False` to `FaultReport` [`schemas/faults.py:65-73`], both defaulted so every existing construction and the committed golden fixtures keep validating. A partial must be indistinguishable from a complete run *in structure* and completely distinguishable *in metadata*, per D-TEL1(i)'s "run-completed-vs-aborted flag with reason."

---

## Sequencing Assessment (D-PRE1): how much work is each precondition really?

| Step | Concrete work | Effort | Risk |
|------|--------------|--------|------|
| **P2** — `pdf.py` embedded-text fix | **2 lines** at `pdf.py:231-233` (add `_digital_blocks` + `_digital_figures` to the fallback branch). **Plus** the real work: `PARSER_VERSION` folded into `cache_key` [`store.py:35-39`], purge + re-ingest `data/ingest_cache/` (6 entries), a test asserting a parser-version bump changes the key, and a test asserting the fallback branch now yields non-empty blocks on a fixture. | **Small code, medium plumbing.** 1 plan. | **Medium.** It moves both committed baselines (`recall_by_family.json`, `retrieval_recall.json`). D-PRE1(a) requires disclosure. The cache-invalidation trap makes a silent no-op the likeliest failure. |
| **P1** — 3.2.S.5 real-ingestion classification proof | Run real `ingest_corpus` on `mvr1381` + `spec32s41`; confirm the 3.2.S.5 family is classified so `CFR-211160B-SOUND-BASIS` / `CFR-211194-CALCULATIONS` fire in production, not only in the 14/14 unit fixture. If real classification differs, re-tag the two requirement-index entries from the manifest [CITED: `02-PHASE-VERIFICATION-QUEUE.md:19-21`]. | **Small — a measurement, not a build**, *unless* classification differs, in which case add index re-tagging. | **Medium.** This is the gate on whether `absence_of_evidence` entries can fire at all — the named headline expectation of D-GO1(iii). |
| **Boundary-crossing hunt** | A written list of `enumerate→X` / `classify→Y` / `build→Z` chains unit-tested on each side but never composed on real data, **plus a composition test for each**. 3 were found in Phase 2. `tests/tools/test_enumerate_fetch_emit_e2e.py` is the exemplar to imitate — its docstring names the exact failure class. | **Medium — genuinely open-ended.** Budget it as its own plan. | **Medium.** The deliverable is a list + tests, so "we looked and it seemed fine" cannot pass. Candidate chains this research already surfaced: the span-ID round-trip (§Pitfall 1), `run_oracles`→`get_section`→`emit_finding` (§Pitfall 9), `cache_key`→parse output (§Runtime State Inventory). |
| **D-LOOP2 baseline re-measurement** | 3× `python -m evals.run run --model databricks-meta-llama-3-3-70b-instruct`, capture each `FaultReport`, compute `recall_by_family` median + min/max, compare against 0.071 with the `\|median − 0.071\| > 0.03` line. | **Small in code, real in wall-clock** — 3 live multi-document detector runs. | **Medium.** If P2 shifts it past the line, the reviewer must confirm a new reference before the agent arm runs. Sequence this **after** P2 and P1, exactly as D-PRE1 requires. |
| **Commit the pre-registration** | `03-GO-NOGO-PREREGISTRATION.md` with all riders, the 3-bucket reachability classification, the baseline median + SHA, and every frozen N value. | **Small.** | **High if skipped or amended late** — D-GO5 voids the run set on any post-run amendment. |
| **The 3 agent runs** | Fixed config, temperature 0, same corpus/harness/baseline. | Wall-clock + spend. | The measurement. |

**One material item D-PRE1 does not name.** `02-PHASE-VERIFICATION-QUEUE.md:32-34` records verification item **5** as **MATERIAL**: *"all 15 requirement-index `citation` strings fail to resolve via `rulebook.store.lookup_citation`"* and *"Must resolve before Phase 3 wires the agent loop (the enumerate→emit chain is the RULES-05 headline mechanism)."* The queue header marks it **RESOLVED** (`9c1f191`, 15/15 e2e) and `tests/tools/test_enumerate_fetch_emit_e2e.py` exists asserting the full chain — so this appears closed. **Verify it is green before planning depends on it**, because `absence_of_evidence` (the named headline family) is entirely downstream of it.

---

## Environment Availability

| Dependency | Required by | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python venv at `.venv` | all | ✓ | 3.12 | — |
| `openai` | tool-call transport | ✓ | 2.43.0 | — |
| `pydantic` | arg models / schemas | ✓ | 2.13.4 | — |
| `json-repair` | L3 salvage | ✓ | 0.61.2 | — |
| `structlog` | telemetry logs | ✓ | 26.1.0 | — |
| `pytest` (+ asyncio auto) | offline test harness | ✓ | 9.1.1 | — |
| `pymupdf` | P2 parse fix | ✓ | 1.27.2.3 | — |
| `sentence-transformers` | local embeddings for `search_corpus` | ✓ | 5.6.0 | Databricks embeddings when `is_databricks` |
| `faiss-cpu` | dense retrieval leg | ✓ | 1.14.3 | — |
| Databricks endpoint + token | the 3 agent runs, the baseline re-runs, the Qwen probe | **unverified this session** | — | **None** — the live runs cannot be faked. Offline tests (D-RB6) cover every code gate; only the model-behavior measurement needs the endpoint. |
| Vendored `rulebook/**` | `read_guideline`, the e2e fixture | ✓ | 7 eCFR XML + 5 PDFs + 1 xlsm; `data/rulebook_cache/` has 607 entries | — |
| `data/ingest_cache/` | corpus substrate | ✓ (6 entries) | **stale after P2** | Purge + re-ingest (§Runtime State Inventory) |
| **CI runner** | D-RB6 offline contract | **✗ — `.github/workflows/` does not exist** [VERIFIED] | — | The offline contract is currently enforced by test *design*, not by a pipeline. Either add a minimal workflow running `pytest` with no Databricks credentials, or state plainly in the plan that D-RB6 is a convention. |

**Missing with no fallback:** a live Databricks endpoint for the measurement runs (expected — it is the phase's purpose).
**Missing with fallback:** CI enforcement of D-RB6 (a ~15-line workflow closes it, and it is the only thing that makes "offline" checkable rather than asserted).

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json` — this section is mandatory.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` **9.1.1** |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]`: `pythonpath=["src"]`, `testpaths=["tests"]`, `asyncio_mode="auto"` |
| Existing suite | **46 test files** across `tests/{agents,evals,ingest,integration,rulebook,tools,unit}` |
| Quick run command | `.venv/bin/pytest tests/agents/review -x -q` |
| Full suite command | `.venv/bin/pytest -q` |
| Offline contract (D-RB6) | Enforced by test design today; **no CI workflow exists** |
| Reusable fixture | `tests/tools/conftest.py::build_corpus_index(tmp_path, doc_id, blocks, ...)` — builds a **real, persisted single-document `CorpusIndex`** through the genuine `serialize_document → normalize → build_table_index → write_doc_cache` path, so `cached_entry()` is byte-identical to a real ingest. **Use this everywhere; never hand-roll a cache dict.** |

### How to test a model-driven loop deterministically, offline

The single enabling decision is Pattern 1: **the loop receives a completion callable**. Everything below follows from it and requires no monkeypatching of module globals.

```python
# tests/agents/review/conftest.py
@dataclass
class ScriptedChatClient:
    """Deterministic stand-in for chat_completion_tools. Replays a scripted list of turns and
    records what it was asked, so message-history construction is assertable."""
    script: list[ChatTurn]
    seen_messages: list[list[dict]] = field(default_factory=list)
    seen_tools:    list[list[dict]] = field(default_factory=list)
    def __call__(self, messages, tools, **kw) -> ChatTurn:
        self.seen_messages.append(copy.deepcopy(messages))
        self.seen_tools.append(copy.deepcopy(tools))
        return self.script[min(len(self.seen_messages) - 1, len(self.script) - 1)]
```

Three fixture flavours cover every gate:
- **Scripted** — a fixed list of turns (tool call → tool call → no-tool-call → …). Drives budgets, floor, breaker, rejection rendering.
- **Forced-runaway** — always returns a tool call, never a stop (D-BUD6).
- **Replay** — a recorded transcript from a real run, committed as a fixture, so a real model's *actual* call sequence can be regression-tested offline without spend.

### Phase Requirements → Test Map

| Req | Behavior | Type | Automated command | Exists? |
|-----|----------|------|-------------------|---------|
| AGENT-01 | Loop issues tool calls, dispatches, appends results, terminates | unit | `pytest tests/agents/review/test_loop_basic.py -x` | ❌ Wave 0 |
| AGENT-01 | Tool schemas contain no `$ref`/`$defs`/`anyOf`/`oneOf`/`allOf`/`prefixItems`/`pattern`, ≤16 keys, ≤32 tools | unit | `pytest tests/agents/review/test_tool_schemas.py -x` | ❌ Wave 0 |
| AGENT-01 | Assistant `tool_calls` echoed verbatim; every `tool` message's `tool_call_id` matches | unit | `pytest tests/agents/review/test_message_history.py -x` | ❌ Wave 0 |
| AGENT-03 | Token ceiling trips → `stop_reason="ceiling"`, grounded partial returned, no exception | unit | `pytest tests/agents/review/test_loop_budget.py::test_token_ceiling -x` | ❌ Wave 0 |
| AGENT-03 | Wall-clock ceiling trips (injected clock) | unit | `...::test_wallclock_ceiling -x` | ❌ Wave 0 |
| AGENT-03 | DR stop after N unproductive turns; an enumerate turn is **productive** under the amended D-BUD2 | unit | `...::test_diminishing_returns -x` | ❌ Wave 0 |
| AGENT-03 | Breaker on identical `(tool,args)` × N | unit | `...::test_breaker_identical_args -x` | ❌ Wave 0 |
| AGENT-03 | Breaker on N consecutive same `(reason_code, half)` | unit | `...::test_breaker_same_class -x` | ❌ Wave 0 |
| AGENT-03 | **D-BUD6 forced runaway vs REAL loop + REAL tools** | integration (offline) | `pytest tests/agents/review/test_runaway.py -x` | ❌ Wave 0 |
| AGENT-04 | No tool call + under budget + not DR ⇒ nudge injected, turn consumed, `continuation_count` increments | unit | `pytest tests/agents/review/test_continuation_floor.py::test_nudge_on_premature_stop -x` | ❌ Wave 0 |
| AGENT-04 | Nudging stops at DR bound; `which_bound == "diminishing_returns"` | unit | `...::test_nudge_bounded_by_dr -x` | ❌ Wave 0 |
| AGENT-04 | Nudging stops at hard cap; `which_bound == "max_continuations"` | unit | `...::test_nudge_bounded_by_cap -x` | ❌ Wave 0 |
| AGENT-04 | `findings_before_vs_after_each_nudge` recorded per continuation | unit | `...::test_continuation_telemetry -x` | ❌ Wave 0 |
| GROUND-01 | **Span-ID round-trip composition test** — render → parse → re-mint → `was_issued` → `open_span` byte-exact, over a real `build_corpus_index`, for all 5 rendering tools | **composition** | `pytest tests/agents/review/test_spanref_roundtrip.py -x` | ❌ Wave 0 |
| GROUND-01 | Loop-side unresolvable span ref returns a **distinct** reason code, never `not_byte_exact` | unit | `...::test_unresolvable_ref_is_not_span_invention -x` | ❌ Wave 0 |
| GROUND-01/03 | `emit_finding` rejections carry the correct `half` at all 7 sites | unit | `pytest tests/tools/test_emit_finding.py -k half -x` | ⚠️ file exists, `half` assertions ❌ |
| GROUND-03 | `rule_span_id` + `verdict` survive onto the `Fault` | unit | `pytest tests/unit/test_schemas.py -k verdict -x` | ❌ Wave 0 |
| DETECT-03 | `run_oracles`-the-tool returns leads; **no span pre-recorded in the ledger** (D-ORC2) | unit | `pytest tests/agents/review/test_oracles_tool.py::test_no_prerecorded_spans -x` | ❌ Wave 0 |
| DETECT-03 | S9, S10, P10 each produce a lead on a fixture that omits the element | unit | `...::test_s9_s10_p10_leads -x` | ❌ Wave 0 (S10 does not exist yet) |
| DETECT-04 | Verdict is enum-constrained; a free-text verdict is rejected | unit | `pytest tests/agents/review/test_tool_schemas.py::test_verdict_enum -x` | ❌ Wave 0 |
| D-LOOP4 | **Rendered prefix byte-identical across two different corpora** + negative control | unit (offline) | `pytest tests/agents/review/test_prefix_stability.py -x` | ❌ Wave 0 |
| D-VER1 | If any legacy pass is retained, it is **provably non-dropping** | unit | `pytest tests/agents/review/test_verify_nondropping.py -x` | ❌ Wave 0 |
| D-TEL1 | Summary carries every provenance field; aborted ≠ completed | unit | `pytest tests/agents/review/test_telemetry.py -x` | ❌ Wave 0 |
| D-TEL2 | Every `reason_code` a tool can emit is in `KNOWN_REASON_CODES`; unknown → `unrecognized` bucket | unit | `pytest tests/tools/test_contracts.py -k reason_codes -x` | ⚠️ file exists, assertion ❌ |
| D-TEL4 | Pre-repair and post-repair malformed rates counted separately; a pre-repair fix consumes **no** turn | unit | `pytest tests/agents/review/test_repair_accounting.py -x` | ❌ Wave 0 |
| P2 | Fallback branch yields non-empty blocks on a scanned-with-text-layer fixture | unit | `pytest tests/unit/test_parse.py -k fallback_blocks -x` | ❌ Wave 0 |
| P2 | A `PARSER_VERSION` bump changes `cache_key` | unit | `pytest tests/ingest/test_store.py -k parser_version -x` | ❌ Wave 0 |

### The four load-bearing test designs, in detail

**1. Span-ID round-trip (the boundary-crossing test this phase most needs)**
```python
def test_every_rendered_span_survives_the_round_trip(tmp_path):
    corpus = build_corpus_index(tmp_path, "d1", blocks=[...], outline_headings=["3.2.S.5"])
    ledger = RetrievalLedger()
    rendered = get_section(corpus, "d1", ledger, heading="3.2.S.5")
    for ref in _SPAN_RE.findall(rendered):                    # exactly what the model sees
        span = parse_span_ref(ref, corpus, RULEBOOK_CACHE)    # exactly what the loop does
        assert not isinstance(span, ToolRejected)
        assert ledger.was_issued(span)                        # D-GRAN
        raw, canon = open_span(span, nt_for(corpus, "d1"), "d1")   # the hash check emit_finding runs
        assert raw                                            # byte-exact or HashMismatch
```
Repeat for `search_corpus`, `open_doc` (outline spans), `read_guideline` fetch mode, and `follow_reference` resolved mode. **This is the test whose absence would let Pitfall 1 ship.** It is exactly the shape of `tests/tools/test_enumerate_fetch_emit_e2e.py`, whose docstring names the failure class: *"green unit tests on each side… but nothing drove the REAL committed… all the way through in one composed test."*

**2. D-BUD6 forced-runaway driver (real loop, real tools, zero spend)**
```python
class ForcedRunaway:
    """Never emits a stop; always requests more evidence. Cycles real tool calls so the REAL
    src/tools functions execute against a REAL offline CorpusIndex."""
    def __call__(self, messages, tools, **kw) -> ChatTurn:
        self.i += 1
        return ChatTurn(content="", finish_reason="tool_calls",
                        tool_calls=[_call("search_corpus", {"query": f"impurity {self.i}"})],
                        raw_message={...}, prompt_tokens=4000, completion_tokens=200)

def test_runaway_trips_ceiling_and_returns_grounded_partial(tmp_path):
    result = run_review(corpus, manifest, ledger, BudgetLedger(max_tokens=50_000, max_turns=1000,
             max_wall_clock_s=600), telemetry, complete=ForcedRunaway(), registry=real_registry())
    assert result.stop_reason == "ceiling"
    assert budget.billed_tokens <= 50_000            # no overspend
    assert isinstance(result.report, FaultReport)     # grounded partial, never a crash
    assert all(f.evidence for f in result.report.faults)
```
Set `max_turns` deliberately high so the **token ceiling** is what trips — otherwise the test proves the wrong gate.

**3. D-LOOP4 byte-identical prefix, with a negative control**
```python
def test_prefix_is_byte_identical_across_different_corpora(tmp_path):
    a = build_corpus_index(tmp_path / "a", "alpha", blocks=[...])                       # 1 doc
    b = build_corpus_index(tmp_path / "b", "beta",  blocks=[...], outline_headings=[...])  # different
    pa = render_prefix(build_registry(a));  pb = render_prefix(build_registry(b))
    assert sha256(pa) == sha256(pb)

def test_prefix_test_is_not_vacuous():
    """Negative control: if a doc count leaks into the prefix, the assertion MUST fail.
    Without this, a prefix that is trivially constant passes forever and proves nothing."""
    with_leak = SYSTEM_PROMPT + f"\nCorpus contains {2} documents."
    assert sha256(with_leak.encode()) != sha256(SYSTEM_PROMPT.encode())
```
`render_prefix` must serialize **both** the system message and the tool-schema list, since a dynamic tool *description* is the exact failure Claude Code measured at ~10.2% of cache-creation tokens.

**4. D-VER1's "provably non-dropping" — as a test, and expect it to fail today**
```python
def test_legacy_verify_would_drop_agent_findings():
    """D-VER1 requires: if any legacy pass is retained for tiering metadata, it must be
    provably NON-DROPPING. This test documents that verify_and_tier is NOT, so the agent
    path must bypass it. If a future phase re-introduces it, this test is the gate."""
    faults = [_agent_fault(title="", detail="Section 3 omits LOD."),      # title -> "Deficiency"
              _agent_fault(title="", detail="Section 4 omits LOQ.")]      # same _dedup_key
    assert len(verify_and_tier(faults, _doc())) < len(faults)   # DROPS — verify.py:136-144
```
Then assert the positive property for the path actually shipped: `len(review_result.report.faults) == len(emitted_faults)` — nothing between the gate and the report may remove a finding.

### Sampling Rate

- **Per task commit:** `.venv/bin/pytest tests/agents/review tests/tools -x -q` (fast, fully offline)
- **Per wave merge:** `.venv/bin/pytest -q` (full 46+ file suite)
- **Phase gate:** full suite green **plus** `python -m evals.run gate` green **before** `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/agents/review/__init__.py` + `conftest.py` — `ScriptedChatClient`, `ForcedRunaway`, replay fixtures, multi-doc corpus builder (extend `build_corpus_index` to N documents)
- [ ] `tests/agents/review/test_loop_basic.py` — AGENT-01
- [ ] `tests/agents/review/test_tool_schemas.py` — D-LOOP3 + Databricks restriction assertions + verdict enum
- [ ] `tests/agents/review/test_message_history.py` — tool_call_id / raw_message echo
- [ ] `tests/agents/review/test_loop_budget.py` — AGENT-03 (ceiling / wall-clock / DR / breaker ×2)
- [ ] `tests/agents/review/test_runaway.py` — D-BUD6
- [ ] `tests/agents/review/test_continuation_floor.py` — AGENT-04 ×4
- [ ] `tests/agents/review/test_spanref_roundtrip.py` — GROUND-01 composition test
- [ ] `tests/agents/review/test_prefix_stability.py` — D-LOOP4 + negative control
- [ ] `tests/agents/review/test_verify_nondropping.py` — D-VER1
- [ ] `tests/agents/review/test_telemetry.py` — D-TEL1 provenance
- [ ] `tests/agents/review/test_repair_accounting.py` — D-TEL4 pre/post split
- [ ] `tests/agents/review/test_oracles_tool.py` — D-ORC1/D-ORC2 + S9/S10/P10
- [ ] Extend `tests/tools/test_emit_finding.py` — `half` at all 7 sites
- [ ] Extend `tests/tools/test_contracts.py` — `KNOWN_REASON_CODES` coverage
- [ ] Extend `tests/unit/test_parse.py` — P2 fallback blocks
- [ ] Extend `tests/ingest/test_store.py` — `PARSER_VERSION` in `cache_key`
- [ ] **Optional but recommended:** `.github/workflows/test.yml` running `pytest` with no Databricks credentials — makes D-RB6 checkable rather than asserted

*(Framework install: none needed — pytest 9.1.1 is present and configured.)*

---

## Security Domain

`security_enforcement` is not present in `.planning/config.json`; absent = enabled.

### Applicable ASVS Categories

| ASVS category | Applies | Standard control |
|---------------|---------|------------------|
| V2 Authentication | no | No new auth surface; Databricks token via `Settings`. |
| V3 Session Management | **yes** (agent-run isolation) | `RetrievalLedger` and `BudgetLedger` are **constructor-injected, one instance per run, never module globals** — the discipline already documented at `ledger.py:3-5`. A shared ledger across runs would let run 2 emit findings citing run 1's spans, silently voiding `was_issued`'s meaning and corrupting the 3-run comparison. |
| V4 Access Control | **yes** (store separation) | `emit_finding` enforces that a rule span resolves in the RULEBOOK store and a submission span in the CORPUS store [`emit_finding.py:66-75`]. Preserve it — the loop must not resolve a span against whichever store happens to answer first. |
| V5 Input Validation | **yes** | Every tool arg validated against a pydantic model before dispatch; span-ID strings validated by regex + store resolution, never `eval`/`split`-and-trust. Model-supplied `doc_id` must be looked up, never used to build a filesystem path. |
| V6 Cryptography | **yes (hashing only)** | `ingest.anchors.short_hash` / `open_span` are the integrity mechanism. **Never hand-roll a span comparison** — always `open_span`. |
| V12 Files & Resources | **yes** | `oversized.py` handles are opaque keys resolved through `_path_for(handle, scratch_dir)` [`oversized.py:25-27`]. A model-supplied handle must never become a path component without validation — `load_range` returning `None` for an unknown handle is the current guard [`oversized.py:47`], and `get_section` correctly turns that into a typed rejection [`get_section.py:75-80`]. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard mitigation |
|---------|--------|---------------------|
| Model-supplied `doc_id` used as a path segment | Tampering / Information disclosure | Resolve through `corpus.cached_entry(doc_id)` / manifest membership; typed `not_found` otherwise [`open_doc.py:15-21`]. Already correct — do not regress in the new dispatch layer. |
| Model-supplied `handle` used as a filename | Tampering | `load_range` lookup + `descriptor["doc_id"] != doc_id` check [`get_section.py:71-80`]. Preserve. |
| Prompt injection from submission text into tool calls | Tampering | Structural, not textual: the model can only invoke declared tools with validated args, and `emit_finding` accepts only ledger-issued span-IDs. Injected text cannot manufacture a span the ledger never issued. **This is the strongest security property the design already has** — do not weaken it by adding a free-text evidence path. |
| Unbounded resource consumption | Denial of service | AGENT-03 code ceilings + D-BUD3 breaker; D-BUD6's runaway test is the proof. |
| Secret leakage into committed telemetry | Information disclosure | The D-TEL1(ii) JSONL/summary artifacts are **committed to git**. Assert no `DATABRICKS_TOKEN`, no `Authorization` header, and no full document text lands in them — a test worth 5 lines given these files are permanent repo history. |
| Credential exposure in exception text | Information disclosure | `client.py` truncates error strings (`str(exc)[:200]`) but does not scrub. Low risk; note it. |

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|-------|---------|---------------|
| A1 | Databricks populates `usage.prompt_tokens_details.cached_tokens` on FM API responses | Code Recon D1, Pitfall 8 | D-BUD5 accounting falls back to a char estimate; the COST-01 cache signal is unobservable in Phase 3. **Cheap to resolve: one live call.** |
| A2 | Databricks applies server-side constrained decoding for `tools=` args | Standard Stack | If not, pre-repair malformed rates will be higher than expected; `structured.py` carries more load. D-TEL4's pre/post split is designed to reveal exactly this — no plan change needed. |
| A3 | Tool arg schemas need not list every property in `required` for Databricks tool calling | Code Recon D2 | First tool turn 400s. Mitigated by making args required wherever the locked contracts allow, plus the schema-shape test. |
| A4 | Standard OpenAI tool-message protocol (echo assistant `tool_calls`; `tool` role messages carry `tool_call_id`) holds on Databricks FM APIs | Pitfall 10 | Message construction breaks on turn 2. **First thing to verify in the first live smoke run.** |
| A5 | The `openai` SDK version that introduced `prompt_tokens_details` is ≥ the `>=1.40` pin floor | Standard Stack | A fresh install at the pin floor could lack the field. Mitigated by raising the pin. |
| A6 | Verification-queue item 5 (requirement-index citation ↔ store granularity) is genuinely closed by `9c1f191` | Sequencing Assessment | `absence_of_evidence` — the headline family — is entirely downstream. **Verify the 15/15 e2e test is green before planning depends on it.** |
| A7 | `_digital_blocks` produces correct blocks on scanned pages carrying an embedded text layer | Code Recon D10 | P2's fix under-delivers. Mitigated by the P2 fixture test, and it is the exact hypothesis the SC4 7/12 → 12/12 measurement tests. |
| A8 | The published multi-turn degradation figures (~39%, >40-turn drop-offs) generalize to Llama 3.3 70B on Databricks | Pitfall 3 | Directional only; explicitly rated LOW-MEDIUM in-text and never used to set a threshold. The pre-registered bars come from D-GO3(ii)/D-TEL4, not from these numbers. |
| A9 | Databricks prompt caching covers the specific Llama 3.3 70B endpoint this project uses (the blog names "Llama 3.1 8B and 3.3 70B") | State of the Art | D-LOOP4 is a stability invariant that costs nothing either way; only Phase 6's payoff estimate would move. |

---

## Open Questions

1. **The "uncommitted redesign" premise in STATE.md and CLAUDE.md is STALE — the work is committed.**
   - What we verified: `git status --porcelain` shows only `.planning/config.json` and `rulebook/manifest.yaml` modified. `git diff HEAD --stat -- src/` is **empty**. `git ls-files src/agents/detection/` lists **all 16 files including `planning.py`, `summarise.py`, `sandwich.py`, `workers.py`** as tracked. `git stash list` is empty. There are no untracked files.
   - What this means: there is no uncommitted work to build on or clobber. The redesign **is** `HEAD` (`9b68856`), it is exercised by `tests/agents/detection/test_planner_redesign.py` (338+ lines) and `tests/unit/test_detection.py`, and `pipeline.py:58-83` drives it (concurrent `run_planner` ∥ `summarise_sections`, then `run_workers`).
   - How the loop should relate to it: **leave it entirely alone.** It is the *baseline arm*. D-LOOP1 requires it stay runnable; D-LOOP2 re-runs it 3× to produce the governing reference. Building `src/agents/review/` as a sibling package touches none of it. No conflict exists with D-LOOP1, D-ORC1 or D-VER1 — those decisions describe what the **agent path** does differently, not edits to the legacy path.
   - **Recommendation:** correct `.planning/STATE.md:75` and the CLAUDE.md branch note as a small hygiene task, so no later agent re-derives a stale premise.

2. **Is the held-out calibration corpus adequate? — FLAGGED, reviewer decision required.**
   - What we know: `spec32s41` is the only genuinely held-out real document, it is a single PDF, and it carries 3 GT deficiencies.
   - What's unclear: whether a single-document consumption figure can support a `3×` multiple over a multi-document review.
   - Recommendation: option (a) — source 2–4 unlabeled real submission documents into a `calibration/` corpus. Option (b) — synthesize with `make_docx_fixture.py`'s deterministic pattern and report the figure as a lower bound. **Do not substitute scored data.** Resolve before the pre-registration is committed.

3. **Does Databricks report cache hits, and does the static prefix actually hit?**
   - What we know: caching is implicit and covers Llama 3.3 70B; `PromptTokensDetails.cached_tokens` exists in the SDK.
   - What's unclear: whether the field is populated by this provider.
   - Recommendation: a 3-line probe during the first smoke run. If absent, record `usage_present=False` and note in the report that D-LOOP4's invariant is asserted by test but its *payoff* is unmeasured until Phase 6. Do not let this block anything.

4. **Will P2 move the frozen baselines, and by how much?**
   - What we know: P2 recovers text on 5 anchors in `mvr1381`'s exact-identifier hard subset (SC4 7/12), and both `recall_by_family.json` and `retrieval_recall.json` are downstream.
   - What's unclear: the magnitude, and whether the D-LOOP2 `|median − 0.071| > 0.03` line trips.
   - Recommendation: measure and disclose per D-PRE1(a). If the line trips, the reviewer confirms a new reference **before** the agent arm runs — the sequence D-LOOP2 designed for precisely this.

5. **How large is the boundary-crossing hunt?**
   - What we know: 3 chains were found in Phase 2; this research surfaced 3 more candidates (span-ID round-trip, `run_oracles`→`get_section`→`emit_finding`, `cache_key`→parse output).
   - What's unclear: the total.
   - Recommendation: plan it as its own executor plan with the written-list deliverable D-PRE1(b) specifies, seeded with the three candidates above so it starts from evidence rather than a blank page.

6. **Does S10 have a ground-truth item to hit at all?**
   - What we know: S10 (reference standards) does not exist in code, and `mvr1381`'s GT anchors include `'control sample'` (A-03) and `'current in-house SOP'` (A-11) which are plausibly reference-standard adjacent — but no anchor names a reference standard directly.
   - What's unclear: whether building S10 buys any measurable recall on the scored set.
   - Recommendation: build it (DETECT-03 names it), but **do not count on it for the D-GO1(a) family unlock**. `derivation_plausibility` and `regulatory_framing` (5/5 matchable each, both at 0.0) are the better-odds targets, and the report should say which mechanism produced the unlock.

---

## Sources

### Primary (HIGH confidence)

- **This repository at `9b68856`**, read directly this session — every `file:line` claim above: `src/llm/client.py`, `src/llm/structured.py`, `src/tools/{errors,ledger,emit_finding,get_section,open_doc,search_corpus,read_guideline,follow_reference,oversized,textsplit}.py`, `src/agents/detection/{pipeline,verify,checklists,oracles}.py`, `src/agents/event_bus.py`, `src/evals/{run,metrics,match,gate,schema,capture,make_docx_fixture}.py`, `src/schemas/{faults,documents,events}.py`, `src/ingest/{store,corpus,serialize,anchors,normalize}.py`, `src/parse/{pdf,ocr}.py`, `src/retrieval/vector_search.py`, `src/config.py`, `tests/tools/{conftest,test_enumerate_fetch_emit_e2e}.py`, `pyproject.toml`
- **Computed from the committed dataset** — `src/evals/dataset/*.deficiencies.json` + `documents.json` replayed through `src/evals/match.py`'s tokenization: family counts, the six zero-token anchors, per-family recall ceilings, the `tp_required` set
- **Installed package versions** — `importlib.metadata` in `.venv`; `openai` SDK field introspection (`ChatCompletionMessage.tool_calls`, `CompletionUsage`, `PromptTokensDetails.cached_tokens`)
- **git state** — `git status --porcelain`, `git diff HEAD --stat -- src/`, `git ls-files src/agents/detection/`, `git stash list`
- **[Databricks — Function calling](https://docs.databricks.com/aws/en/machine-learning/model-serving/function-calling)** — verbatim: single-turn optimization + Claude recommendation for multi-turn; `anyOf`/`oneOf`/`allOf`/`prefixItems`/`$ref`/`pattern` prohibition; 16-key max; 32-function max; no parallel function calling; `tool_choice` values
- **[Databricks — Supported FM API models](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models)** — Llama 3.3 70B 128k context; both configured Qwen endpoints present in the catalog
- **[Databricks blog — Prompt caching for open-source models](https://www.databricks.com/blog/accelerating-llm-inference-prompt-caching-open-source-models-databricks)** — caching is implicit ("customers do not need to configure anything"); model coverage incl. Llama 3.3 70B; a production pipeline at ~30% hit ratio
- **`.planning/` governance** — `ROADMAP.md` (Phase 3 goal, SC 1/2/3/3b/4/5, research flag), `REQUIREMENTS.md` (AGENT-01/03/04, GROUND-01/03, DETECT-03/04), `03-CONTEXT.md`, `02-CONTEXT.md`, `02-PHASE-VERIFICATION-QUEUE.md`, `research/{ARCHITECTURE,PITFALLS,CLAUDE-CODE-TEARDOWN}.md`

### Secondary (MEDIUM confidence)

- **[llama.cpp issue #20164](https://github.com/ggml-org/llama.cpp/issues/20164)** — Qwen3.5-35B-A3B / Qwen3-Coder-Next repeated near-miss tool calls with multiple optional params; onset ~30k tokens (~20% of context); "changed `offset` from optional to required and the problem disappeared entirely." Single well-documented report on a different serving stack, but the mechanism is schema-shape-driven and the model family matches ours.
- **[BFCL V3 multi-turn benchmark overview](https://www.emergentmind.com/topics/bfcl-v3-multi-turn-benchmark)** — 800 multi-turn tasks, static offline evaluation with pre-defined tool catalogs; the standard instrument for this class of measurement.

### Tertiary (LOW confidence — flagged, never used to set a threshold)

- **[ICLR summary — LLMs lose ~39% accuracy in multi-turn conversations](https://beam.ai/agentic-insights/iclr-2026-llms-lose-accuracy-in-multi-turn-conversations)** and **[FutureAGI — multi-turn LLM degradation](https://futureagi.com/glossary/multi-turn-llm-conversation-degradation/)** — lost-in-the-middle (<20% mid-turn citation), compounding errors, severe drop-offs beyond ~40 turns. Secondary summaries; directional only.
- **[Function Calling Benchmarks Leaderboard](https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/)** and assorted arXiv-derived figures (Qwen3 32B 75.7% BFCL v3; "Llama-70B 37.0% BFCL multi-turn"; xLAM-2-70b-fc-r 75.12%) — **no verified figure for Llama 3.3 70B specifically.** One search-surfaced claim that Llama 3.3 "generally cannot produce executable tool calls" **contradicts this project's own settled 2026-07-30 probe** and is recorded here only as a contradiction, not as evidence.

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Code reconnaissance (D1–D10) | **HIGH** | Every file read directly at `9b68856`; every claim carries a line number. |
| Measurement-instrument ceilings | **HIGH** | Computed by replaying `match.py`'s own tokenization over the committed dataset; reproducible in one command. |
| Databricks tool-calling constraints | **HIGH** | Vendor documentation, quoted verbatim, fetched this session. |
| Databricks prompt caching behavior | **MEDIUM-HIGH** | Official blog; per-model coverage and `cached_tokens` reporting not exhaustively documented. |
| Long-loop degradation magnitude | **LOW-MEDIUM** | Published evidence is directional and not specific to Llama 3.3 70B on Databricks. **This is the phase's genuine unknown — which is why the phase exists.** |
| Standard stack | **HIGH** | No new dependencies; installed versions verified. |
| Architecture patterns | **HIGH** | Derived from locked decisions + verified constraints + existing repo precedent (injected ledger, typed sentinels, code-gate-first). |
| Pitfalls | **HIGH** for 1, 2, 4, 5, 7, 8, 9 (all code-derived); **MEDIUM** for 3, 6 (external evidence); **MEDIUM** for 10 (protocol assumption). |
| Sequencing assessment | **MEDIUM-HIGH** | P2's fix is precisely located; the boundary-crossing hunt is open-ended by nature. |

**Research date:** 2026-08-01
**Valid until:** 2026-08-31 for the code reconnaissance (stable unless the branch moves); **2026-08-15** for the Databricks constraints — function calling is in Public Preview and the single-turn caveat is exactly the kind of statement that changes at GA. Re-check the function-calling page before committing the pre-registration.
