# ADR — Adopt NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 as the on-prem verify/reasoning model

**Status:** Accepted — 2026-08-05
**Deciders:** senior reviewer + user

## Context
The Phase-3 drive-loop spike is a confirmed NO-GO (`03-19-V3.3-READING.md`): the local agentic loop
on Llama-3.3-70B will not reliably convert leads into findings, and detects zero absence deficiencies.
Adopted direction is **β** — a *general* deterministic layer owns recall (rulebook-requirement
enumeration + structural checks), and the agentic loop is retained only for **verify/challenge**.
Hard constraint: on-premise / privacy — **only self-hosted open-weights models; no external LLM API**
(see the privacy decision; the γ "escalate to Claude" option is permanently excluded). We may add
exactly **one** stronger self-hosted reasoning model for the retained verify role.

## Decision
Add **`nvidia/Llama-3_3-Nemotron-Super-49B-v1_5`** (self-hosted on Databricks) as the
**verify / hard-reasoning** model, alongside the existing Llama 3.3 70B and Qwen MoE. It does **not**
own recall (recall is deterministic in β); it re-opens a candidate's cited source + rule and
confirms/refutes, and handles reasoning-heavy finding classes.

## Rationale
- **Tool-calling (the #1 pain):** DPO-tuned for tool calls, ships its own vLLM tool-call parser, and is
  the only shortlisted family with published BFCL evidence — lowest tool-plumbing risk.
- **Reasoning (vendor-reported):** AIME24 87.5 / AIME25 82.7 / GPQA-Diamond 72.0 / MMLU-Pro 79.5 /
  LiveCodeBench 73.6 — sufficient for confirm/refute + absence/numeric-cross-reference reasoning.
- **Verifier decorrelation:** different lineage from the Qwen MoE, so it is an *independent* second
  opinion (a second Qwen would share failure modes and rubber-stamp).
- **Footprint:** 49B dense, single H100/H200, NVFP4 + GGUF quants — same single-node budget as the
  existing Llama-70B, no new cluster.
- **Control:** `detailed thinking on/off` toggle — cheap non-thinking confirmation passes, escalate to
  thinking mode for hard refutations.
- **Privacy/license:** self-hosted → data-private. NVIDIA Open Model License + Llama 3.3 Community
  License (commercial use permitted). Origin: NVIDIA (US), built on Meta Llama 3.3.

## Guardrails / caveats
- The reasoning benchmarks are **NVIDIA-reported** — do not rely on them; gate adoption on an in-house probe.
- **Lineage:** built on Llama 3.3, so decorrelated from Qwen but *correlated with the existing Llama-70B*.
  Pair deliberately — do not have Llama-70B generate candidates that a Llama-derived verifier then
  "independently" confirms.

## Action items (before wiring into the loop; belong in the β milestone plan)
1. vLLM smoke-test the `detailed thinking on/off` + tool-call combo on **real verification traces**
   (our actual tool schemas / JSON args), not just benchmarks.
2. Confirm the vLLM tool-parser name/flags and the NVFP4-or-GGUF quant that fits the target GPU
   before provisioning.

## Consequences
- One additional model to serve on Databricks; used only in the verify/reasoning role.
- Does **not** reopen γ (fully self-hosted, on-prem, privacy-preserving).
- Recall remains deterministic and general (no metric-chasing / overfitting).

---

## D-19/D-20 Amendment — Quant/GPU decision (Phase 6, 06-02 gate)

**Date:** 2026-08-09
**GATE STATUS: PASSED** (D-19/D-20 hard gate — hardware confirmed before any serving build)
**Deciders:** senior reviewer (Row-1 ruling) + orchestrator (enumeration)
**Quant selected: FP8**
**Serving tier:** `GPU_XLARGE_8` (Hopper / H100)
**tensor-parallel-size: 8** (matches the 8-GPU tier and the research recommendation; tunable down without changing the quant lock — FP8-on-Hopper holds for any plausible GPU count)
**Excluded:** NVFP4 (requires Blackwell — **absent** from this workspace); BF16/AWQ-INT4 held in reserve as the mechanical fallback (see Fallback Rider).

### 1. Serving-tier facts (verbatim — chip family is the binding fact)

| Fact | Value | Source |
|---|---|---|
| GPU serving tier in use | **`GPU_XLARGE_8`** (proven on `defpredict-suggestor` + `-evaluator`, both READY, `workload_size=Small`) | serving-endpoints API (live, re-verified independently by reviewer) |
| `GPU_XLARGE` → chip | **1× H100 (80GB)**, us-west-2, enrollment-gated | Databricks AWS docs (custom-LLM serving) |
| `GPU_XLARGE_8` in public docs? | **No** — account-negotiated tier; `_8` count is **INFERRED** (⇒ 8× the XLARGE/H100 unit) and **immaterial to the quant choice** — chip *family* (Hopper/H100) is the binding fact; FP8 fits any plausible GPU count | docs + inference |
| Compute region inventory | 8× H100 (`p5.48xlarge`) **and** 8× A100 (`p4d`) exist; **no Blackwell** | `databricks clusters list-node-types` (live) |
| Chip field in serving API? | **Absent — the serving API abstracts the chip** (no gpu/instance/hardware field anywhere in the endpoint config) | serving-endpoints API (verified) |
| Scale-to-zero | **Not supported** on the H100 (`GPU_XLARGE`) tier ("H100 capacity too constrained for cold-start"); proven endpoints run **always-on** (`scale_to_zero=None`) | docs + live config |

Convergent evidence the tier is Hopper/H100 (HIGH confidence): (a) `GPU_XLARGE` is definitionally the H100 tier per docs; (b) the region physically has 8× H100 (`p5.48xlarge`); (c) the proven `GPU_XLARGE_8` endpoints run always-on, matching the documented H100 no-scale-to-zero constraint; (d) no Blackwell → NVFP4 impossible. FP8 is the correct Hopper-native quant.

### 2. Entitlement evidence
The H100 (`GPU_XLARGE`) tier is enrollment-gated per docs — **but entitlement is already proven**: `defpredict-suggestor` and `defpredict-evaluator` run on `GPU_XLARGE_8` **today**. The only open operational question is **capacity for ONE MORE endpoint** of this tier. **06-05's first action verifies available capacity** before the Nemotron build proceeds.

### 3. Cost + ops constraints (Phase-8 shadow data)
- **No scale-to-zero on the H100 tier → always-on hourly burn** (consistent with D-04, which already accepts standing GPU cost). No idle-savings lever exists on this tier.
- **Hourly cost ($/DBU):** NOT exposed by the CLI/serving API or the docs read; the H100 tier is enrollment-gated (negotiated pricing). **REQUIRED FOLLOW-UP:** obtain the `GPU_XLARGE_8` DBU/hour rate from the Databricks **account/pricing console or account team** and record it here before any extended run. (Not fabricated — pending authoritative source.)
- **DEV TEARDOWN POLICY (mandatory):** the Nemotron endpoint is **stopped/deleted between active development sessions** and **recreated from the 06-05 notebook** — **no idle H100-hours**. Recreation MUST be **fully scripted** (the 06-05 notebook IS the recovery path), so teardown costs nothing but a redeploy wait. 06-05 must make the deploy path idempotent + re-runnable to honor this.

### 4. Fallback Rider (no new gate needed — mechanical row-selection)
If 06-05's deployment hits **capacity denial** or reveals **non-Hopper hardware**, fall through the pre-ranked table **mechanically** (the decision is already made; only the row selection changes):
- **Row 2 — A100-only:** BF16 (49B ≈ ~98GB weights; fits an 8×A100-80GB tier) if an A100 tier is available and its hourly cost is defensible (record cost here).
- **Row 3 — A100-only + BF16 unaffordable/unavailable:** AWQ-INT4 on the smallest fitting tier.
- **Invariant:** the **D-06 probe suite gates verifier QUALITY regardless of quant** — a quantization that degrades discrimination below the per-class floors **fails Phase 6 on its own gates**. The quant choice therefore cannot silently cost verdict quality.

### 5. Context note — D-16 guard protects a *present* temptation
The workspace exposes **pay-per-token `databricks-claude-opus-4-8`, `databricks-gpt-5-*`, and `databricks-gemini-3-5-flash` endpoints TODAY** (confirmed READY in the live endpoint list). The D-16 deny-first allow-list guard protects against a **real, present** one-string-away misconfiguration surface — not a hypothetical one.

### Supersedes in the original ADR
- The line "single H100/H200, **NVFP4 + GGUF** quants" (Footprint) and action item 2's "NVFP4-or-GGUF" are **superseded** by this amendment: **FP8 on 8× H100**, NVFP4 excluded (no Blackwell), GGUF not vLLM-native.
