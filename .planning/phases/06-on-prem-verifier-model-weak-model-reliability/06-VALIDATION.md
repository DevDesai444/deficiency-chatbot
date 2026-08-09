---
phase: 6
slug: on-prem-verifier-model-weak-model-reliability
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 06-RESEARCH.md "## Validation Architecture" + the D-06 two-dimensional
> falsifiable pass bar and D-14 pinned-baseline diff harness.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + deepeval 4.x (asyncio_mode=auto already set) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) — existing |
| **Quick run command** | `pytest tests/unit/test_reliability.py tests/unit/test_on_prem_guard.py tests/unit/test_verdict_schema.py -x` |
| **Full suite command** | `deepeval test run tests/evals/test_verifier_probe.py --identifier "phase6-verifier-conformance-discrimination"` |
| **Estimated runtime** | ~30s unit; live-endpoint evals gated behind `@pytest.mark.integration` |

---

## Sampling Rate

- **After every task commit:** `pytest tests/unit/test_reliability.py tests/unit/test_on_prem_guard.py tests/unit/test_verdict_schema.py -x`
- **After every plan wave:** `pytest tests/unit/ tests/evals/test_reliability_baseline.py -x`
- **Before `/gsd-verify-work`:** `deepeval test run tests/evals/test_verifier_probe.py --identifier "phase6-verifier-conformance-discrimination"` — full suite green
- **Max feedback latency:** ~30s (unit); live-endpoint eval runs on-demand

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| MODEL-01 (SC1) | No external endpoint ever configured/called; forbidden ids raise | unit | `pytest tests/unit/test_on_prem_guard.py -x` | ❌ W0 |
| MODEL-02 (SC2) | Nemotron pre-wiring probes pass (vLLM tool-call + thinking ON/OFF + tool-parser flags) | integration (live) | `pytest tests/integration/test_nemotron_probe.py -x` | ❌ W0 |
| RELIABILITY-01 | `guided_json`/`structured_outputs` capability probe returns True/False; `extra_body` wired on supported endpoints | unit | `pytest tests/unit/test_reliability.py::test_guided_probe_caches -x` | ❌ W0 |
| RELIABILITY-02 | Field-level errors name failing field + expected type (not generic hint) | unit | `pytest tests/unit/test_reliability.py::test_field_level_error_format -x` | ❌ W0 |
| RELIABILITY-03 | Coercion handles numeric-string→number, bool-string, single-key unwrap; enums never coerced | unit | `pytest tests/unit/test_reliability.py::test_strict_coerce -x` | ❌ W0 |
| D-06a (conformance) | ≥98% parsable VERDICT post-repair, thinking ON + OFF each | integration (live) | `deepeval test run tests/evals/test_verifier_probe.py` | ❌ W0 |
| D-06b (discrimination) | ≥80% correct on known-good/known-bad split | integration (live) | `deepeval test run tests/evals/test_verifier_probe.py` | ❌ W0 |
| D-12 (typed-failure honesty) | `ParseFailed` on exhausted retry; no fabricated verdict | unit | `pytest tests/unit/test_reliability.py::test_no_fabricated_verdict -x` | ❌ W0 |
| D-14 (baseline delta) | Post-hardening malformed-arg rate < pinned Phase-3 baseline | integration (replay) | `pytest tests/evals/test_reliability_baseline.py -x` | ❌ W0 |
| D-16 (allow-list guard) | Forbidden ids (`databricks-claude-*`/`-gpt-5-*`/`-gemini-*`) raise ValueError | unit | `pytest tests/unit/test_on_prem_guard.py -x` | ❌ W0 |
| D-17 (lineage tags) | `verifier_model` resolves to Nemotron; lineage tag = `nemotron-on-llama` | unit | `pytest tests/unit/test_config.py::test_verifier_model_role -x` | ❌ W0 |
| D-18 (thinking-mode split) | Both modes clear D-06a; latency/token counts differ between modes | integration | included in `test_verifier_probe.py` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/unit/test_reliability.py` — RELIABILITY-01/02/03, D-09, D-11, D-12
- [x] `tests/unit/test_on_prem_guard.py` — MODEL-01 / D-16
- [x] `tests/unit/test_verdict_schema.py` — D-07 VERDICT model + schema derivation
- [x] `tests/integration/test_nemotron_probe.py` — MODEL-02 (live endpoint; `@pytest.mark.integration`)
- [x] `tests/evals/test_verifier_probe.py` — D-06a/D-06b/D-18 (live Nemotron; DeepEval harness)
- [x] `tests/evals/test_reliability_baseline.py` — D-14 pinned-baseline diff harness
- [x] `tests/unit/test_config_verifier.py` — D-17 `verifier_model` + lineage tags

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confirm exact GPU hardware on `GPU_XLARGE_8` (H100 vs Blackwell) | MODEL-02 / D-19-D-20 | Requires live workspace CLI query; gates quant choice | `databricks clusters list-node-types --profile amneal-dev` Day 0 of Wave 1 (D-20 gate) — record result, then pick FP8 (Hopper) vs NVFP4 (Blackwell) |
| Nemotron weights reachable + NVIDIA Open Model License accepted org-wide | MODEL-02 | Org network/license state not machine-assertable from repo | Confirm HuggingFace hub reachability from Databricks workspace; verify license acceptance before serving build |
| Reasoning-toggle string (`/no_think` vs `detailed thinking off`) | MODEL-02 / D-18 | Must be empirically probed against live Nemotron | Compare `completion_tokens` between modes in `test_nemotron_probe.py` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit); live evals on-demand
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-08
