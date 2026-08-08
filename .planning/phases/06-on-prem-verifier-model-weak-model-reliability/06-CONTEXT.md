# Phase 6: On-Prem Verifier Model + Weak-Model Reliability (β) - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the reasoning/verification model the β verifier runs on — **NVIDIA
Llama-3.3-Nemotron-Super-49B-v1.5**, served **self-hosted on the company's
Databricks** (`aip-amn-dev`) alongside Llama 3.3 70B + Qwen MoE, with **no
external LLM API (Claude/GPT/Gemini) ever called** — and prove it is
production-wired before Phase 7 depends on it. Because the verifier still runs
on weaker open-weights models, harden tool-call reliability here: server-side
guided decoding, field-level actionable errors, and targeted semantic arg
coercion — so the `KEEP|DOWNGRADE` verdicts in Phase 7 parse reliably instead
of dropping findings to malformed args.

**In scope:** Nemotron deployment (self-managed vLLM, GPU endpoint) + pre-wiring
probes; a shared reliability layer (guided decode + strict coercion +
field-level errors) consumed by both the review tool-call path and
`structured.py`; a minimal `VERDICT` arg-model; on-prem allow-list guard;
role-routing + lineage-tag scaffolding for Phase 7 decorrelation.

**Out of scope (Phase 7):** the actual verifier sub-agents, the
never-drop→KEEP orchestrator policy, decorrelation *enforcement* logic, the
thinking-mode escalation *trigger*, the interpretive-tail pass.

**Requirements:** MODEL-01, MODEL-02, RELIABILITY-01, RELIABILITY-02, RELIABILITY-03.
</domain>

<decisions>
## Implementation Decisions

### Serving reality (MODEL-01)
- **D-01: Nemotron is NOT currently deployed** — verified live against
  `aip-amn-dev` Databricks on 2026-08-08. Searched all 58 serving endpoints (0
  match nemotron/nvidia/49b by name **or** served entity) and Unity Catalog
  across every catalog (`defpredict`, `project_dev`, `amn_dev_databricks`,
  `system.ai`/marketplace) — no registered Nemotron model anywhere. The "NVIDIA
  one we installed" is not reachable. **This phase deploys it from scratch.**
- **D-02: Deploy Nemotron THIS phase** against a **live endpoint** — no
  deferral. MODEL-02 probes must hit the real Nemotron, not a stand-in.
- **D-03: Serve via self-managed vLLM**, NOT Databricks managed Provisioned
  Throughput. Rationale: SC2/SC3 require vLLM-native controls (custom
  tool-parser flag, `detailed thinking on/off` toggle, `guided_json`) that
  managed PT does not expose; PT may also not support Nemotron's NAS-pruned
  Llama arch. Self-managed vLLM (Databricks GPU cluster/app or custom model
  serving with a vLLM entrypoint) is the only path that fully satisfies SC2+SC3
  as written.
- **D-04: Always-on GPU endpoint** (kept warm; no cold start). GPU serving
  capacity is proven — `defpredict-suggestor`/`-evaluator` already run live on
  `GPU_XLARGE_8`. Standing GPU cost accepted by the user.

### Probe substrate & pass bar (MODEL-02)
- **D-05: Probe corpus = the 115 real β-measurement candidates** — the asset we
  already own. mvr1381 = 112 emitted (5 matched-GT: A-09/A-11/B-01/C-01/C-06 +
  100 FP over-emit; legs: 8 absence / 3 structural / 101 reference [97
  UNRESOLVED_REF + 4 VALUE_CONTRADICTION]); minispec = 3. Real over-emit, real
  evidence, **zero synthesis cost**. The reports already label matched-GT vs FP
  → the known-good/known-bad split is free.
- **D-06: Pre-register a TWO-DIMENSIONAL falsifiable pass bar** (a parse-rate
  bar alone is gameable by a model that answers KEEP every time with perfect
  syntax):
  - **(a) Conformance** — machine-parsable `VERDICT` on **≥98% of probes
    post-repair** (bar sits ABOVE Phase 3's 95% because verdict-parsing is an
    easier task than Phase 3's open tool-calling); **thinking-mode ON and OFF
    each separately** above the bar; **plus one tool-call round-trip probe**.
  - **(b) Discrimination** — the probe set contains known-good and
    known-planted-bad candidates and Nemotron must **separate them**;
    pre-register the split (e.g. **≥80% correct on knowns**).
  - "Probes pass" becomes falsifiable — or Phase 6 repeats the SC5 mistake.
- **D-07: Define a minimal `VERDICT` arg-model in Phase 6** (`verdict:
  KEEP|DOWNGRADE`, `confidence`, `rationale`, `grounding_span`) living in
  `schemas/`. It is the probe's assertion target AND the concrete schema this
  phase's guided-decode + coercion protect. **Phase 7 extends it, never
  redefines.**

### Reliability hardening (RELIABILITY-01/02/03)
- **D-08: Guided decoding (`guided_json`) wired into the tool-call turn for ALL
  7 review tools + the VERDICT**, on every endpoint that supports it (not
  verdict-only). The tool-call path (`chat_completion_tools`) passes NO
  guided-decode args today — this closes that gap.
- **D-09: Detect-once, cache per-endpoint `guided_json` capability.** Capability
  is **probed at runtime per endpoint** (NOT a hardcoded model-name allow-list —
  that would rot). Fail-safe: if the probe itself errors, assume unsupported and
  fall through (never block the call).
- **D-10: Defense-in-depth stack (all models):** `guided_json` (if
  probed-supported) → native tool-parser → **strict lossless coercion** →
  field-level actionable error + bounded retry → **typed `ParseFailed`
  sentinel**.
- **D-11: Coercion = strict lossless allow-list + logged near-misses.** Coerce
  ONLY unambiguous, information-preserving cases: numeric-string→number (whole
  string is a number), `'true'`/`'false'`→bool, single-key wrapper unwrap (key
  matches expected arg). **Enum values are NEVER guessed** — a verdict token
  that isn't exactly KEEP/DOWNGRADE FAILS, never coerced. **Advertised schema is
  unchanged (SC4).** Every rejected near-miss is logged (structlog counter) so
  we can see the tail and tighten later with evidence — without loosening.
- **D-12: On exhausted retries → typed field-level failure; the CALLER
  decides.** The reliability layer returns `VERDICT xor typed-failure` and
  **never fabricates a verdict**. It does not decide KEEP/DOWNGRADE — that's
  Phase 7 orchestrator policy (parse-failure→KEEP, never-drop). Baking a
  fallback-KEEP here would conflate "verifier said keep" with "we couldn't read
  the verifier" and destroy the telemetry that shows how often the fallback
  carries the loop (the Phase-3 hidden-fallback lesson). Mirrors the existing
  `structured.py` L6 sentinel and `dispatch`/`ToolRejected` contracts.
- **D-13: Retry cap = 1 corrective retry, budget-counted, configurable
  (default 1).** One field-level corrective re-prompt (name the field + expected
  type), then surface typed failure. Each corrective call counts toward the
  run's token/turn budget (honest accounting — Phase-3 "the fallback's work must
  be visible" discipline). Value lives in config (mirrors
  `structured_output_max_repair_calls=1`); bump only if near-miss telemetry
  proves 2 recovers materially more without precision loss.
- **D-14: Reliability baseline is PINNED before any hardening lands (SC3).**
  Metric = **pre-repair malformed-arg rate** (+ post-repair residual) — the
  exact D-TEL4 counters Phase 3's telemetry already emits. Baseline numbers are
  extracted from the committed Phase-3 run summaries (Llama's rates in the v2/v3
  artifacts; Qwen's 4/5 post-repair failures from the fidelity probe) and
  written as **numbers in the plan** before code changes. Harness = replay the
  same probe suite through `llm/reliability.py` and **diff the rates**. Without
  the pinned number "measurably reduced" is vibes; with it, arithmetic.

### Layer siting
- **D-15: One shared reliability module** (e.g. `src/llm/reliability.py`)
  holding capability-probe + `guided_json` builder + strict coercion +
  field-level error formatter. Both `registry.dispatch` AND `structured.py`
  consume it; **Phase 7's verifier inherits the hardening for free**; the
  defense stack is tested in ONE place.

### On-prem guarantee (MODEL-01)
- **D-16: Minimal allow-list guard at the client boundary** (`get_client` /
  model resolution): reject any model-id not in the on-prem allow-list {Llama,
  Qwen, Nemotron, defpredict fine-tunes}. Rationale is **config drift**, not
  deliberate use — model-ids come from env vars (`LLM_MODEL`) and UI overrides
  (`detector_model`), and the workspace exposes `databricks-claude-*`,
  `databricks-gpt-5-*`, `databricks-gemini-*` one string away. A wrong id must
  **fail loudly** instead of silently sending regulated pharma data to an
  external model. This is a security allow-list, NOT the forbidden kind of
  hardcoding (which is per-corpus check conditions). Satisfies MODEL-01 SC1
  minimally — no ceremony beyond the guard.

### Phase-7 decorrelation scaffold
- **D-17: Role + lineage metadata now; enforcement in Phase 7.** Add a
  `verifier_model` role (resolves to Nemotron) to config/allow-list AND tag each
  on-prem model with its lineage family (`llama` / `qwen` / `nemotron-on-llama`).
  Phase 7 reads the tags to enforce the ADR guardrail (Nemotron is Llama-3.3
  lineage → must NOT "independently" verify Llama-produced candidates) by
  construction. No enforcement logic built in P6. (Note: in β, recall candidates
  come from the deterministic engine, not a model — lineage-correlation mainly
  bites in Phase 7's interpretive-tail generator-vs-verifier pairing.)

### Thinking-mode
- **D-18: Lock the SPLIT, not the policy.** Phase 6 PROVES the toggle — both
  `detailed thinking on` and `off` return a parsable VERDICT above the D-06 bar
  — and **records latency + token cost per mode**. That cost data is exactly
  what Phase 7 needs to design the escalation trigger; the trigger itself
  depends on Phase 7's orchestration + budget shape, which doesn't exist yet.
  Same data-now/policy-later split as D-17.

### Quant/GPU fit — RESEARCH-FIRST with a hard decision gate
- **D-19: Do NOT pick a quant blind.** Choosing NVFP4 today would hardcode a
  guess about unconfirmed hardware: NVFP4 needs Blackwell; Hopper (H100) wants
  FP8/AWQ; GGUF isn't vLLM-native at all. **Day-one research task:** enumerate
  what GPU classes this workspace's model serving actually offers (a CLI/docs
  query — hours, not days), THEN pick the quant that fits the confirmed runtime,
  THEN amend `ADR-nemotron-verifier-model.md` with the decision recorded.
- **D-20: The plan MUST carry an explicit decision gate — no serving build
  starts until the quant/GPU pair is confirmed vLLM-compatible.** This is the
  "will vLLM even run" gate; hitting it mid-build instead of up front is how a
  phase loses a week.

### Claude's Discretion
- **D-12 (failure boundary)** and **D-13 (retry-cap value)** were "you decide" —
  decided as above, tied to the recall+precision mandate and the codebase's
  existing sentinel/telemetry conventions.
- **D-09 fallback strategy** was "you decide, keep the goal in mind" — decided
  as detect-once/per-endpoint (cheapest + most testable, runtime-probed not
  hardcoded).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Model decision & constraints
- `.planning/ADR-nemotron-verifier-model.md` — the accepted decision to adopt
  Nemotron-Super-49B as the verify/reasoning model; DPO tool-calling, vLLM
  tool-parser, `detailed thinking on/off`, NVFP4/GGUF quant note, decorrelation
  guardrail (Llama-lineage), and the pre-wiring action items. **D-19 amends this
  ADR with the confirmed quant/GPU decision.**
- `.planning/ROADMAP.md` §"Phase 6" (lines ~195-204) — goal, success criteria
  SC1-SC4, dependencies, requirements.
- `.planning/REQUIREMENTS.md` — MODEL-01/02 (lines 85-86), RELIABILITY-01/02/03
  (lines 89-91).

### Weak-model tool-arg failure baseline (SC3, D-14)
- `.planning/phases/03-drive-loop-spike-go-no-go/03-18-SUMMARY.md` — D-TEL4
  pre/post-repair malformed-rate telemetry; the wholesale `post_repair_malformed`
  breaker pattern; the `top_k`-as-string known failure mode.
- `.planning/phases/03-drive-loop-spike-go-no-go/03-19-V2-RUN-NOTES.md`,
  `03-19-V3-RUN-NOTES.md` — Llama malformed-arg rates to pin as the baseline.
- `.planning/phases/03-drive-loop-spike-go-no-go/03-CONTEXT.md` §pre-registered
  Qwen fidelity probe (≥95% schema-conformant; `top_k`-as-string coercion) — the
  precedent for D-06's falsifiable-bar discipline and Qwen's 4/5 post-repair
  failures.

### Probe substrate (MODEL-02, D-05)
- `.planning/phases/05-deterministic-structural-cross-document-recall/beta-measurement/beta-mvr1381.report.json`
  — 112 emitted candidates (faults array), matched-GT vs FP labels.
- `.planning/phases/05-deterministic-structural-cross-document-recall/beta-measurement/beta-minispec.report.json`
  — 3 emitted candidates.
- `.planning/phases/05-deterministic-structural-cross-document-recall/beta-measurement/beta-measurement-summary.json`
  — per-leg counts, matched_gt_ids, fp_count (the known-good/known-bad split).

### Code the phase extends
- `src/llm/client.py` — `chat_completion_tools` (tool-call turn; add guided
  decode here), `get_client` (add on-prem allow-list guard here), the existing
  `response_format` BadRequestError→degrade pattern D-09 mirrors.
- `src/llm/structured.py` — L1-L6 defense (json_schema strict, truncation retry,
  json-repair, pydantic, moderator rescue, `ParseFailed` sentinel); consumes the
  new shared `reliability` module (D-15); `parse_structured` is the coercion
  insertion point.
- `src/agents/review/registry.py` — `ToolRegistry.dispatch` (arg validation +
  `ToolRejected` reason codes `not_found`/`post_repair_malformed`; the generic
  `hint` becomes field-level per RELIABILITY-02); `_direct_validate`,
  `TOOL_SPECS`, `OPTIONAL_FIELDS`.
- `src/config.py` — `Settings`, role properties (`moderator_model`,
  `detector_model` → add `verifier_model`), `DETECTOR_MODELS` allow-list (add
  Nemotron + lineage tags D-17), `resolve_detector_model` (allow-list precedent
  for D-16), `max_tokens_ceiling`, `structured_output_max_repair_calls` (D-13).
- `src/databricks/serving.py` — `_DB_MODELS` map, `get_llm_client`,
  `resolve_model`; where the Nemotron endpoint id lands.
- `src/tools/errors.py` — `ToolRejected` (the typed-failure precedent for D-12).
- `src/schemas/llm.py` — `ParseFailed`; where the minimal `VERDICT` model (D-07)
  lives.

### Live infra facts (verified 2026-08-08)
- Databricks profile `amneal-dev` → `https://aip-amn-dev.cloud.databricks.com`,
  user `dev.desai@amneal.com`, `databricks` CLI v1.6.0 authed.
- READY self-hosted open-weights: `databricks-meta-llama-3-3-70b-instruct`,
  `databricks-meta-llama-3-1-8b-instruct`, `databricks-qwen35-122b-a10b`,
  `databricks-qwen3-next-80b-a3b-instruct`. GPU custom serving proven:
  `defpredict-suggestor`/`-evaluator` on `GPU_XLARGE_8`.
- FORBIDDEN-but-reachable (D-16 guard target): `databricks-claude-*`,
  `databricks-gpt-5-*`, `databricks-gemini-*`.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `structured.py` L1-L6 defense-in-depth + `ParseFailed` sentinel — the pattern
  and contract the shared reliability module (D-15) generalizes; do NOT rewrite
  it wholesale (hardened asset).
- `client.py` `response_format` BadRequestError→drop-and-retry fallback — the
  exact degrade mechanism D-09 turns into a cached per-endpoint capability probe.
- `config.py` `resolve_detector_model` allow-list ("never lets an arbitrary
  client string reach the LLM call") — the precedent D-16 extends to the client
  boundary for the on-prem guard.
- `registry.py` `dispatch` split of pre-repair vs post-repair failure
  (`repair_layer` none/pre/post; D-TEL4) — the telemetry seam field-level errors
  (RELIABILITY-02) and the D-14 baseline measurement plug into.
- GPU serving template: `defpredict-suggestor`/`-evaluator` UC-registered custom
  models on `GPU_XLARGE_8` — the deployment shape D-02/D-03 follows for Nemotron.

### Established Patterns
- Role→model routing via `Settings` properties + a display allow-list — add
  `verifier_model` and lineage tags the same way (D-17).
- Typed-sentinel-or-value return contract (`instance XOR ParseFailed`,
  `result XOR ToolRejected`) — D-12 keeps the reliability layer on this contract.
- Config-tunable knobs (`structured_output_max_repair_calls`,
  `max_tokens_ceiling`) — D-13's retry cap follows (no magic constants).

### Integration Points
- New `src/llm/reliability.py` sits under both `structured.py` and
  `registry.dispatch`; Phase 7's verifier calls the same module.
- New minimal `VERDICT` model in `src/schemas/llm.py` (D-07).
- Nemotron endpoint id threads through `config.py` + `serving.py`; the on-prem
  guard sits in `client.get_client` / model resolution.
</code_context>

<specifics>
## Specific Ideas

- Use the **115 real β candidates** as the probe corpus verbatim — no synthetic
  substitute for the primary set (D-05).
- Pass bar is explicitly two-dimensional and pre-registered (D-06) — the user
  called out that a parse-rate-only bar is gameable by a constant-KEEP model.
- Baseline is **arithmetic, not vibes** — pin the Phase-3 numbers in the plan
  before touching code (D-14).
- The quant/GPU decision is a **hard gate** — the plan blocks serving-build on
  it (D-20).
- On-prem: the user's stance is "if we don't add them they won't be there" —
  the guard exists ONLY to catch env/override drift, kept deliberately minimal
  (D-16).
</specifics>

<deferred>
## Deferred Ideas

- **Verifier sub-agents, orchestrator fan-out, never-drop→KEEP mapping,
  decorrelation enforcement, interpretive-tail pass** — Phase 7 (VERIFY-01..04).
- **Thinking-mode escalation trigger** (cheap-confirm → escalate-to-thinking on
  hard refutation) — Phase 7, informed by D-18's per-mode cost data.
- **Prompt-cache stable prefix / compaction / cheap-triage cost governance** —
  Phase 8 (COST-01/02/03).
- **Loosening coercion / broader best-effort recovery** — only if D-11's logged
  near-miss telemetry later proves a real recoverable pattern is being dropped;
  evidence-driven, not now.
- **Bumping the retry cap to 2** — only if D-13/D-14 telemetry proves it recovers
  materially more without precision loss.

None of the above are in Phase 6 scope — discussion stayed within the phase
boundary.
</deferred>

---

*Phase: 6-On-Prem Verifier Model + Weak-Model Reliability (β)*
*Context gathered: 2026-08-08*
