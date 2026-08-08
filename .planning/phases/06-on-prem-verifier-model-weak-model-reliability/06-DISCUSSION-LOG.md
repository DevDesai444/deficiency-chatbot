# Phase 6: On-Prem Verifier Model + Weak-Model Reliability (β) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-08
**Phase:** 6-On-Prem Verifier Model + Weak-Model Reliability (β)
**Areas discussed:** Serving reality, Probe substrate, Coercion safety, Guided-decode scope, On-prem enforcement, Retry-cap value, Reliability layer siting, P7 decorrelation scaffold, Probe pass bar, Reliability baseline, Thinking-mode policy, Quant/GPU fit

**Standing mandate restated at open:** goal = catch ALL real deficiencies
(recall) + every caught deficiency correct (precision); no hardcoding of check
conditions (AI handles the infinite interpretive space); on-prem law (no
external LLM API ever).

---

## Serving reality (MODEL-01)

Live Databricks query (`aip-amn-dev`) run mid-discussion at the user's request.
Finding: Nemotron is **not deployed** anywhere — 0/58 endpoints, no UC model in
any catalog. The "NVIDIA one we installed" is not reachable.

| Option | Description | Selected |
|--------|-------------|----------|
| Deploy it this phase | Register weights + GPU endpoint + probe live Nemotron | ✓ |
| Wire now, deploy-gated | Build wiring + probe on stand-in, gate live-served | |
| Verify install first | User re-checks where Nemotron actually is | |

**User's choice:** Deploy it this phase.

| Option (serve how) | Description | Selected |
|--------|-------------|----------|
| Self-managed vLLM | vLLM flags reachable → SC2/SC3 achievable | ✓ |
| Managed PT if supported | Simplest ops; hides vLLM flags; arch risk | |
| Researcher decides | Defer mechanism to plan-time | |

**User's choice:** Self-managed vLLM.

| Option (GPU cost) | Description | Selected |
|--------|-------------|----------|
| Scale-to-zero | Cheapest; cold start | |
| Always-on | Warm; standing cost | ✓ |
| No approval yet | Blocked on cost sign-off | |

**User's choice:** Always-on.
**Notes:** GPU capacity confirmed live — `defpredict-suggestor`/`-evaluator` run
on `GPU_XLARGE_8`. Forbidden-but-reachable Claude/GPT/Gemini endpoints noted.

---

## Probe substrate (MODEL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 5 real candidates | Real emitted findings (TP + FP over-emit) | ✓ |
| Synthesized triples | Hand-crafted verdict edge cases | |
| Both | Real primary + synthetic corners | |

**User's choice:** Phase 5 real candidates.

| Option (verdict schema) | Description | Selected |
|--------|-------------|----------|
| Define minimal here | Minimal VERDICT model in P6; P7 extends | ✓ |
| Defer to Phase 7 | Loose token check only now | |
| You decide | — | |

**User's choice:** Define minimal here.

---

## Coercion safety (RELIABILITY-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Strict lossless allow-list | Unambiguous casts only; enums never guessed | |
| Broader best-effort | Fuzzy enum/synonym recovery | |
| Strict + logged near-misses | Strict, plus log rejected near-misses | ✓ |

**User's choice:** Strict + logged near-misses.

| Option (on failure) | Description | Selected |
|--------|-------------|----------|
| Typed failure, caller decides | Never fabricate verdict; P7 maps →KEEP | ✓ (Claude decided) |
| Default to KEEP here | Bakes P7 policy into parse layer | |
| You decide | — | ✓ |

**User's choice:** "You decide" → Claude ruled **Typed failure, caller decides**.
**Notes:** Rationale — clean layering; mirrors `structured.py` L6 + `ToolRejected`;
preserves telemetry distinguishing fallback-KEEP from real-KEEP (Phase-3 lesson).

---

## Guided-decode scope (RELIABILITY-01)

| Option | Description | Selected |
|--------|-------------|----------|
| All tool-calls where supported | guided_json on all 7 tools + VERDICT | ✓ |
| Verdict-shaped only | Only VERDICT constrained | |
| You decide | — | |

**User's choice:** All tool-calls where supported.

| Option (fallback) | Description | Selected |
|--------|-------------|----------|
| Detect-once, cache per endpoint | Probe capability, cache, fail-safe | ✓ (Claude decided) |
| Per-call graceful degrade | Re-pay rejected call each time | |
| You decide | — | ✓ |

**User's choice:** "You decide, keep the goal in mind" → Claude ruled
**Detect-once/per-endpoint** (cheapest, testable, runtime-probed not hardcoded).

---

## On-prem enforcement (MODEL-01)

User initially pushed back: "if we don't add them they won't be there — nothing
to test." Claude clarified the risk is **env/override config drift** (model-ids
come from `.env`/UI overrides; Claude/GPT one string away), not deliberate use.

| Option | Description | Selected |
|--------|-------------|----------|
| Both: runtime guard + static test | Defense-in-depth | |
| Static test only | Test coverage only | |
| Runtime guard only | (superseded — see below) | |
| Minimal allow-list guard | One boundary guard; wrong id fails loudly | ✓ |

**User's choice:** Minimal allow-list guard (after the drift clarification).
**Notes:** Kept deliberately minimal — satisfies MODEL-01 SC1 without ceremony.

---

## Retry-cap value (RELIABILITY-02)

| Option | Description | Selected |
|--------|-------------|----------|
| 1 retry, budget-counted, configurable | One corrective re-prompt, then fail | ✓ (Claude decided) |
| 2 retries, budget-counted | Two attempts | |
| You decide | — | ✓ |

**User's choice:** "You decide" → Claude ruled **1 retry, budget-counted,
configurable (default 1)**. Rationale — one field-level re-prompt recovers the
bulk; a stuck model's output shouldn't be trusted into a verdict; honest budget
accounting; config-tunable, not a magic constant.

---

## Reliability layer siting

| Option | Description | Selected |
|--------|-------------|----------|
| Shared module, both paths consume | `llm/reliability.py`; P7 inherits | ✓ |
| Bolt onto each path | Duplicated; drift risk | |
| You decide | — | |

**User's choice:** Shared module, both paths consume.

---

## P7 decorrelation scaffold

| Option | Description | Selected |
|--------|-------------|----------|
| Role + lineage metadata now | verifier_model role + lineage tags; P7 enforces | ✓ |
| Role only, tags in P7 | Defer tagging | |
| You decide | — | |

**User's choice:** Role + lineage metadata now.

---

## Probe pass bar (MODEL-02) — user-authored ruling

**User's ruling:** LOCK NOW, two-dimensional (a parse-rate bar alone is gameable
by a constant-KEEP model): (a) **conformance** — machine-parsable VERDICT on
**≥98%** post-repair (above Phase-3's 95% since verdict-parsing is easier than
open tool-calling), thinking-mode on AND off each above the bar, + one tool-call
round-trip probe; (b) **discrimination** — known-good vs known-planted-bad,
Nemotron must separate them, pre-register the split (e.g. ≥80% correct on
knowns). Probe corpus = the **115 real β candidates** (zero synthesis cost).
"Probes pass" becomes falsifiable or Phase 6 repeats the SC5 mistake.

---

## Reliability baseline (SC3) — user-authored ruling

**User's ruling:** LOCK NOW; machinery exists. Metric = pre-repair malformed-arg
rate (+ post-repair residual) — the D-TEL4 counters Phase-3 already emits.
Baseline extracted from committed Phase-3 run summaries (Llama v2/v3; Qwen 4/5
post-repair failures), pinned as numbers in the plan before hardening lands.
Harness = replay the probe suite through `llm/reliability.py`, diff the rates.
"Without the pinned number, 'measurably reduced' is vibes; with it, arithmetic."

---

## Thinking-mode policy — user-authored ruling

**User's ruling:** LOCK THE SPLIT, not the policy. P6 proves the toggle (both
modes return parsable VERDICT above the bar) + records latency/token cost per
mode — that cost data is what P7 needs for the escalation trigger, which depends
on P7 orchestration/budget shape not yet existing. Same data-now/policy-later
split as decorrelation.

---

## Quant/GPU fit — user-authored ruling

**User's ruling:** LOCK AS RESEARCH-FIRST with a decision gate. Choosing NVFP4
today hardcodes a hardware guess (NVFP4→Blackwell; Hopper→FP8/AWQ; GGUF not
vLLM-native). Day-one research: enumerate the workspace's serving GPU classes
(CLI/docs query), pick the quant that fits, amend the ADR. Plan carries an
explicit gate: **no serving build starts until quant/GPU pair confirmed
compatible** — the "will vLLM even run" gate; hitting it mid-build loses a week.

---

## Claude's Discretion

- Coercion failure boundary → Typed failure, caller decides (D-12).
- Guided-decode fallback strategy → Detect-once, cache per-endpoint (D-09).
- Retry-cap value → 1 corrective retry, budget-counted, configurable (D-13).

## Deferred Ideas

- Verifier sub-agents / orchestrator / never-drop→KEEP / decorrelation
  enforcement / interpretive-tail → Phase 7.
- Thinking-mode escalation trigger → Phase 7 (informed by D-18 cost data).
- Prompt-cache / compaction / cheap-triage → Phase 8.
- Loosening coercion; bumping retry cap to 2 → evidence-driven, later only.
