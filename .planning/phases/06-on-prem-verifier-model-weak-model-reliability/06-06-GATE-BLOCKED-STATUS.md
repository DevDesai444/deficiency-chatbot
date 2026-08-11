# 06-06 Gate — BLOCKED on Databricks serving entitlement (status + resume plan)

**Date:** 2026-08-11
**Status:** The Phase-6 gate CODE is complete, committed, and verified locally — but the gate could NOT be run live, because Nemotron cannot be served on workspace `aip-amn-dev` at all. This is a Databricks platform/entitlement wall, not a code issue.

## What is DONE and verified (committed)
- `tests/evals/test_verifier_probe.py` — D-06 probe suite; KEEP-label bug fixed (derives via `src/evals/match.matches`; keep_scored 0→11, all 6 GT ids recovered); DOWNGRADE labels (MIN/MEAN plate faults) arithmetically confirmed FP; anti-gaming stub test passes. Commits `87695b9`, `591852b`.
- `tests/evals/test_reliability_baseline.py` — D-14 coercion-recovery smoke test. Commit `6d2e929`.
- `tests/evals/token_observer.py` + `tests/evals/conftest.py` — fail-open per-mode token observer (proven live against a cheap endpoint). Commit `a7e1811`.
- `notebooks/deploy_nemotron.py` — parametrized (env `NEMOTRON_WORKLOAD_TYPE` / `NEMOTRON_DTYPE` / `NEMOTRON_MAX_MODEL_LEN`), FP8/`GPU_XLARGE_8` defaults preserved; `_latest_registered_version()` fixes the hardcoded "1". Commit `756eb84`.
- Local no-endpoint checks green: `123 passed, 11 skipped` (`test_reliability_baseline.py` + `test_on_prem_guard.py` + `tests/unit/`).
- **UC model `defpredict.main.defpredict_nemotron`: v1 = FP8 entrypoint, v2 = BF16 entrypoint — both READY.**

## Why the gate can't run (the wall)
`aip-amn-dev` does NOT support **Custom Model Serving with a custom `entrypoint`** (self-managed vLLM). Endpoint create returns `BAD_REQUEST: Served entity ... with entrypoint is not supported for your workspace` on every GPU tier/quant/version. Also, H100 custom-serving tiers (`GPU_XLARGE`, `GPU_XLARGE_8`) are not enrolled (only T4/A10G/L40 tiers are). Provisioned-Throughput can't serve Nemotron's custom DeciLM arch. See memory `nemotron-gpu-xlarge8-not-enrolled`.

## Path B (GPU-cluster vLLM) — explored, then stopped (poor ROI)
Ran vLLM on a Databricks GPU cluster to bypass the serving entitlement. Cleared: GPU capacity (zone=auto), UC Volume access (`SINGLE_USER` mode), repo/deps, and **the OpenSSL FIPS abort** (via a cluster init-script that rewrites the default `openssl.cnf` system-wide to drop the FIPS provider — verified: `openssl list -providers` shows only `default`, `vllm --help` no longer SIGABRTs). Init-script content preserved at Volume `/Volumes/defpredict/main/artifacts/init/nonfips_openssl.sh`. **Next wall hit:** CUDA lib mismatch (`libnvJitLink.so.13 missing` — vLLM 0.27.1's torch wants CUDA 13; runtime ships a different CUDA). Stopped here (6th successive wall; DeciLM-arch support + 8×A10G TP-8 fit likely still ahead). Total GPU spend across all attempts ≈ 1.5 A10G-hours; all clusters terminated (verified).

## RESUME PLAN (do this when unblocked)
**Primary — after Track 1 lands:** once Databricks enables Custom Model Serving + custom entrypoint (request drafted at `session/databricks-custom-serving-request.md`):
1. `python notebooks/deploy_nemotron.py --deploy-only --use-version 1 --timeout-minutes 45` (FP8/H100 if H100 tier also enabled) OR set `NEMOTRON_WORKLOAD_TYPE`/`--use-version 2` for BF16 on an A10G tier.
2. Run the guarded gate: `scripts/nemotron_gate_session.sh` (FP8) or `scripts/nemotron_gate_session_a10g.sh 2` (BF16).
3. Reviewer rules `phase-6-complete` / `gate-failed` on the raw numbers.

**Alt — GPU-cluster route (only if entitlement never granted):** reuse the FIPS init-script; fix CUDA by pinning vLLM/torch to the runtime's CUDA (or `LD_LIBRARY_PATH`); confirm the chosen vLLM supports DeciLM (`--trust-remote-code`); serve on `GPU_MEDIUM_8` cluster (8×A10G) TP-8 BF16; run the gate on-cluster with `ENVIRONMENT=local LLM_MODEL=defpredict-nemotron LLM_BASE_URL=http://localhost:8080/v1`.
