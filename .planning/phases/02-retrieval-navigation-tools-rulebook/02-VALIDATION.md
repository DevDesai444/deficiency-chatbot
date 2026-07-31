---
phase: 2
slug: retrieval-navigation-tools-rulebook
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 02-RESEARCH.md `## Validation Architecture`. The Per-Task map is populated during planning.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode=auto) |
| **Config file** | pyproject.toml / pytest.ini |
| **Quick run command** | `PYTHONPATH=src uv run pytest tests/ -x -q` |
| **Full suite command** | `PYTHONPATH=src uv run pytest tests/ -q` |
| **Estimated runtime** | ~TBD seconds (planner/Wave 0 to confirm) |

**Offline contract (D-RB6):** every test in this phase runs against the LOCAL build from the vendored snapshot (same chunks + span-IDs, FAISS/BM25). No test or eval-harness path may import or reach Databricks — the config switch defaults to the local backend under test.

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=src uv run pytest tests/ -x -q`
- **After every plan wave:** Run `PYTHONPATH=src uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** TBD seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _(populated during planning)_ | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Anchor validations (from RESEARCH §Validation Architecture — MUST have automated coverage)

- **SC4 retrieval recall@k** — measured over the Phase-0 answer spans, recorded as a committed baseline; the exact-identifier subset (batch numbers, table labels) passes HARD; recorded recall@k becomes a no-regress floor (D-SC4).
- **emit_finding fabrication rejection** — a deliberately fabricated quote **cannot** be emitted: proven by a test that the gate rejects (not "emitted then caught"). Both halves (submission span + rule span) re-open byte-exact via `open_span`; store-membership enforced (D-EF1, TOOLS-03).
- **Requirement-index ground-truth traceability** — for every Phase-0 absence-family deficiency, ≥1 index entry FIRES for that submission's profile (D-RI1); the loader gate rejects any entry whose provenance span fails byte-exact re-open or whose tags are not in the D-05 registry.
- **TOOLS-04 oversized handling** — an over-large `get_section` fails with a narrow-your-range error rather than truncating; oversized results persist + return a bounded preview + re-openable handle.
- **COST-04 read-dedup** — re-retrieving an unchanged span returns a "still current" stub; hit-rate reported.

---

## Wave 0 Requirements

- [ ] Test module stubs for the 6 requirement-clusters (tools / rulebook / retrieval / requirement-index / emit-gate / cost) — populated during planning
- [ ] Shared fixtures: local rulebook build from a tiny pinned snapshot slice; a fabricated-quote fixture; the Phase-0 eval answer-span set
- [ ] Confirm pytest + asyncio config present (installed via existing infra)

*If none needed after planning: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ich.org site-wide terms wording | RULES-02 | JS-rendered page; per-document notice already verified, site-wide terms need one human browser check | Open the ICH legal-notice page in a browser, confirm the public-license acknowledgment wording matches the stored constant |
| Databricks runtime serving parity | D-RB2/D-RB5 | Databricks is runtime-only, off the CI path (D-RB6); Vector Search Admin API is token-scope-blocked (403) | Senior reviewer verifies the client-side-cosine fallback path serves the rulebook once token scope is resolved |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < TBD s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
