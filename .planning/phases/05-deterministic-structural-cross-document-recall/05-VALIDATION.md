---
phase: 5
slug: deterministic-structural-cross-document-recall
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-06
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini |
| **Quick run command** | `pytest tests/ -q -x` |
| **Full suite command** | `pytest tests/ -q` |
| **Estimated runtime** | ~60–120 seconds (fast lane; slow/corpus-gated lane separate) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/<touched-area> -q`
- **After every plan wave:** Run `pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full fast suite + anti-overfitting guard (SAME-LOGIC / THRESHOLD-TRANSFER / RENAME) must be green
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

*Populated by the planner from PLAN.md tasks. See RESEARCH.md "## Validation Architecture" → "Phase Requirements → Test Map" for the requirement→test seed mapping.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | RECALL-02/03/04/05 | — | N/A | unit | `pytest tests/ -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Synthetic multi-doc guard fixture (D-GRD1/D-GRD4) — committed, runnable in fast CI (unblocks SAME-LOGIC / THRESHOLD-TRANSFER / RENAME invariants + X1/X2 end-to-end)
- [ ] Shared candidate-envelope schema + anchor types (StructuralAnchor / ReferenceAnchor / PrecedentAnchor) — the contract every leg's tests assert against
- [ ] Test seams for the recall-by-family harness (structural, cross-document, precedent families) with zero-true-positives-lost gate

*Final Wave 0 list is set by the planner from RESEARCH.md "Wave 0 Gaps".*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Anti-overfitting generality on the REAL held-out corpus (spec32s41) | RECALL-05 guard | Corpus is gitignored — cannot run in stock GitHub CI | Slow lane: place spec32s41 corpus, run the corpus-gated guard job; confirm same-logic candidates + threshold transfer |

*The synthetic fixture provides the automated every-build tripwire; the real-corpus witness is the manual/slow-lane stronger check.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
