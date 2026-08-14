---
plan: 06-06
title: D-06 verifier gate — β-pivot to served on-prem fleet + phase completion
status: complete
completed: 2026-08-14
requirements: [MODEL-01, MODEL-02, RELIABILITY-01, RELIABILITY-02, RELIABILITY-03]
---

# 06-06 SUMMARY — Verifier gate GREEN across the on-prem fleet (β-pivot)

## One-liner
The Phase-6 verifier was unblocked by pivoting off the unservable Nemotron onto the
already-served on-prem fleet (Llama 3.3 70B + Qwen35-122b-a10b + Qwen3-next-80b-a3b). The
D-06 gate now runs **live** and **D-06a conformance passes all three models in both thinking
modes**. Three weak-model tool-reliability failure modes surfaced and were fixed generally.
D-06b single-shot discrimination was reclassified to a **non-blocking diagnostic**
(reviewer-approved); precision is proven at Phase 7.

## Why the pivot (context)
Nemotron-Super-49B is unservable on `aip-amn-dev` (custom-entrypoint serving disabled
workspace-wide; H100 tiers unenrolled — see `06-06-GATE-BLOCKED-STATUS.md`). Rather than wait
on a Databricks entitlement ticket, the verifier role now runs on models already served through
the OpenAI-compatible dispatch. This is **recall-safe by construction**: recall is deterministic
(Phase 5) and the Phase-7 verifier is downgrade-never-drop (unsure→KEEP), so verifier model
strength affects **precision only, never true-positive loss**. On-prem law upheld — all fleet
models are self-hosted; no external LLM API is configured or called (guard test green).

## What changed (all general, no corpus tuning)
- **`src/config.py`** — `verifier_model` resolves via env-overridable `verifier_model_name`
  (default = served Llama 3.3 70B; set `VERIFIER_MODEL_NAME=defpredict-nemotron` to restore
  Nemotron when serving is enabled). New **`VERIFIER_FLEET`** (Llama + 2 Qwen) — the pool the
  gate validates and Phase 7 fans out across for decorrelated Llama⟂Qwen consensus.
- **`src/llm/verifier_prompt.py`** (new) — canonical, corpus-agnostic verifier prompt that
  SPECIFIES the downgrade-never-drop invariant (KEEP by default; DOWNGRADE only on *affirmative*
  disproof). Family-aware reasoning soft-switch (Qwen `/think`·`/no_think`, Nemotron
  `detailed thinking`, Llama plain).
- **`src/schemas/llm.py`** — `VERDICT.grounding_span` now `min_length=1` + non-blank validator,
  so an empty span routes through the reliability corrective-retry path.
- **`src/llm/client.py`** — a `BadRequestError` whose message is a model-output format rejection
  ("did not respect the required format" — Llama emitting native `<function=…>` syntax) is
  surfaced as a no-tool-call turn (→ retry/parse-fail) instead of aborting the run.
- **`tests/evals/test_verifier_probe.py`** — gate parametrized over `VERIFIER_FLEET` × thinking
  mode; bounded field-level corrective-retry loop (RELIABILITY-02) wired into `run_probe_batch`;
  reasoning-model token budgets (off 256→2048, on 2048→4096) so Qwen MoE reaches the tool call;
  D-06b reclassified to a logged non-blocking diagnostic.

## Weak-model reliability failure modes found & fixed (the Phase-6 thesis, realized)
Swapping to the real served models surfaced failure modes the Nemotron-era code never exercised:
1. **Global-lean discrimination** (blanket-KEEP or blanket-DOWNGRADE) → invariant-aligned prompt.
2. **Empty `grounding_span`** on a valid VERDICT → schema constraint + field-level retry.
3. **Native `<function=…>` tool syntax → 400 format-reject** → client-layer recovery.
4. **Reasoning models starved of tokens** (Qwen MoE hit `finish_reason=length` before the tool
   call; 0% → 100% conformance) → generous fleet-wide budgets. `confidence` string→float
   coercion (RELIABILITY-03) also confirmed firing live.

## Live gate results (RAW, both thinking modes, 115 candidates)
**D-06a Conformance — BLOCKING, floor ≥98% — ALL PASS:**

| Model | family | on-mode | off-mode |
|-------|--------|---------|----------|
| databricks-meta-llama-3-3-70b-instruct | llama | 114/115 = 99.1% ✓ | 114/115 = 99.1% ✓ |
| databricks-qwen35-122b-a10b | qwen | 115/115 = 100% ✓ | 115/115 = 100% ✓ |
| databricks-qwen3-next-80b-a3b-instruct | qwen | 115/115 = 100% ✓ | 115/115 = 100% ✓ |

**D-06b Discrimination — DIAGNOSTIC (non-blocking), floors keep-recall & downgrade-rate ≥0.80:**

| Model | mode | keep-recall | downgrade-rate | tripwire |
|-------|------|-------------|----------------|----------|
| llama-3.3-70b | on  | 11/11 | 0/2 | fired |
| llama-3.3-70b | off | 9/11  | 1/2 | fired |
| qwen35-122b-a10b | on  | 11/11 | 1/2 | fired |
| qwen35-122b-a10b | off | 11/11 | 2/2 | fired |
| qwen3-next-80b-a3b | on  | 10/11 | 0/2 | fired |
| qwen3-next-80b-a3b | off | 11/11 | 0/2 | fired |

## Why D-06b is a diagnostic, not a gate (reviewer-approved 2026-08-13)
1. **Weak-model discrimination is unstable single-shot** — downgrade-rate swings 0/2↔2/2 across
   near-identical configs; no weak model reliably clears a per-item discrimination floor solo.
2. **The metric is structurally mis-calibrated for this candidate set** — only 2 of 115 candidates
   are known-false, so a *perfect* verifier keeps 113/115 = 98.3%, which trips the 0.95 blanket-keep
   wire. Proof: Qwen122B off-mode scored **11/11 keep + 2/2 downgrade** (perfect on the scored
   subset) yet the tripwire STILL fired.
3. The Phase-7 verifier is not this probe: it re-opens the **full** source + rule via tools (not a
   ≤500-char excerpt) and uses **decorrelated Llama⟂Qwen consensus**. Precision is proven there,
   by end-to-end F1 against a properly labeled FP set, with zero-TP-loss vs. Phase 5.

## Requirements status
- **MODEL-01 / MODEL-02** ✓ — verifier served self-hosted through OpenAI-compatible dispatch;
  no external LLM endpoint configured/called (on-prem guard green); pre-wiring probes pass live.
- **RELIABILITY-01/02/03** ✓ — field-level actionable errors + bounded corrective retry +
  targeted semantic coercion (numeric-string, grounding_span, tool-format recovery), advertised
  schemas unchanged; measurably recovers previously-fatal weak-model tool-arg failures.

## Deferred / carried forward
- **Nemotron** deploy deferred (notebook committed; restorable via `VERIFIER_MODEL_NAME` + the
  drafted support ticket) — off the critical path.
- **Verifier precision** carried to Phase 7 — the central P7 criterion: full re-opened context +
  decorrelated multi-agent consensus, proven by end-to-end F1.

## Verification
- Live gate GREEN: `pytest -m integration tests/evals/test_verifier_probe.py` — 2 passed per
  model × 3 models (logs: `session/gate_fleet_raw_{llama,qwen122b,qwen3next}.log`).
- No-endpoint suite: 130 passed / 11 skipped; generality guard 12/12 (anti-overfitting intact);
  full non-integration regression sweep green (no deterministic-recall regression).
