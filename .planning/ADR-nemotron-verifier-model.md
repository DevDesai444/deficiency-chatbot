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
