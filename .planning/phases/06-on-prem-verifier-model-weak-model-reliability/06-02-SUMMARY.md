# 06-02 SUMMARY — D-19/D-20 Quant/GPU HARD GATE

**Plan:** 06-02 (Wave 1, `autonomous: false` — BLOCKING human-verify checkpoint)
**Status:** ✅ COMPLETE — **GATE PASSED**
**Completed:** 2026-08-09

## Gate outcome
**Row 1 LOCKED — FP8 on `GPU_XLARGE_8` (Hopper / H100), tensor-parallel-size 8, always-on.** NVFP4 excluded (no Blackwell in workspace). BF16 (Row 2) / AWQ-INT4 (Row 3) held as the mechanical fallback if 06-05 hits capacity denial or non-Hopper hardware.

## How the gate was resolved (Option A — serving-tier probe, not compute inventory)
1. `databricks clusters list-node-types` (compute inventory): workspace region has 8× H100 (`p5.48xlarge`) **and** 8× A100 (`p4d`); **no Blackwell**.
2. `databricks serving-endpoints get defpredict-suggestor/-evaluator`: both run `workload_type=GPU_XLARGE_8`, `workload_size=Small`, always-on (`scale_to_zero=None`). Serving API **abstracts the chip** (no hardware field).
3. Databricks docs: **`GPU_XLARGE` = 1× H100 (80GB)**, enrollment-gated, no scale-to-zero. `GPU_XLARGE_8` is an account-negotiated tier not in public docs; `_8` count inferred and immaterial (chip *family* is binding).
4. Reviewer independently re-verified the live tier fact (`defpredict-suggestor: GPU_XLARGE_8/Small`) and issued the Row-1 ruling.

## Deliverable
- **`.planning/ADR-nemotron-verifier-model.md`** amended with the "D-19/D-20 Amendment" section carrying: (1) serving-tier facts table verbatim incl. "API abstracts the chip" + docs mapping, `_8` marked inferred/immaterial; (2) entitlement evidence (proven via suggestor/evaluator; capacity-for-one-more verified by 06-05's first action); (3) cost+ops — no scale-to-zero → always-on burn, DBU $ flagged as required follow-up (not fabricated), **DEV TEARDOWN POLICY** (stop/delete between sessions, recreate from 06-05 notebook, fully scripted); (4) Fallback Rider (Row 2 BF16 → Row 3 AWQ-INT4 mechanical; D-06 gates quality regardless of quant); (5) D-16 present-temptation note (live claude/gpt/gemini pay-per-token endpoints).
- Original ADR's "NVFP4 + GGUF" footprint line + action-item-2 marked superseded.

## Gate-token verification (06-02 acceptance criteria)
- `grep 'D-19/D-20 Amendment'` → 1 ✓
- `grep 'GATE STATUS.*PASSED'` → 1 ✓
- `grep 'Quant selected: FP8'` → 1 ✓
- `grep 'tensor-parallel-size: [0-9]+'` → 1 ✓

## Downstream contracts for Wave 2+
- **06-05 first action:** verify `GPU_XLARGE_8` capacity for one more endpoint; deploy path must be idempotent/re-runnable (teardown policy recovery path); if capacity denial or non-Hopper → apply Fallback Rider mechanically.
- **06-06 (D-06 probes):** gate verifier quality regardless of quant — a quant that drops discrimination below per-class floors fails Phase 6.

## Open follow-up (non-blocking)
- Obtain `GPU_XLARGE_8` hourly DBU rate from the Databricks account/pricing console and record it in the ADR amendment.
