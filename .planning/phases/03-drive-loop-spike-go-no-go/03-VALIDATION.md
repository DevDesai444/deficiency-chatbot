---
phase: 3
slug: drive-loop-spike-go-no-go
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-01
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` § Validation Architecture (line 1048).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (present and configured — no install needed) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]`: `pythonpath=["src"]`, `testpaths=["tests"]`, `asyncio_mode="auto"` |
| **Quick run command** | `.venv/bin/pytest tests/agents/review tests/tools -x -q` |
| **Full suite command** | `.venv/bin/pytest -q` |
| **Estimated runtime** | quick ~15s · full ~90s (46+ existing test files) |
| **Offline contract (D-RB6)** | Enforced by test design today; **no CI workflow exists** — see Wave 0 optional item |
| **Key reusable fixture** | `tests/tools/conftest.py::build_corpus_index(tmp_path, doc_id, blocks, ...)` — builds a real, persisted single-document `CorpusIndex` through the genuine `serialize_document → normalize → build_table_index → write_doc_cache` path. **Use this everywhere; never hand-roll a cache dict.** |

**Enabling design decision:** the loop receives a **completion callable** (dependency injection), not a module-global client. Every offline test below follows from this and requires zero monkeypatching. Three fixture flavours: `ScriptedChatClient` (fixed turn list), `ForcedRunaway` (never stops), `ReplayClient` (committed real-run transcript).

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest tests/agents/review tests/tools -x -q`
- **After every plan wave:** `.venv/bin/pytest -q`
- **Before `/gsd-verify-work`:** full suite green **plus** `python -m evals.run gate` green
- **Max feedback latency:** 15 seconds (quick), 90 seconds (full)

---

## Per-Task Verification Map

> Task IDs are assigned by the planner; this table maps **requirement → behavior → automated command**.
> The planner MUST attach each row to the task that delivers it.

| Requirement | Behavior verified | Threat Ref | Test Type | Automated Command | File Exists | Status |
|-------------|-------------------|------------|-----------|-------------------|-------------|--------|
| AGENT-01 | Loop issues tool calls, dispatches, appends results, terminates | — | unit | `pytest tests/agents/review/test_loop_basic.py -x` | ❌ W0 | ⬜ pending |
| AGENT-01 | Tool schemas contain no `$ref`/`$defs`/`anyOf`/`oneOf`/`allOf`/`prefixItems`/`pattern`; ≤16 keys; ≤32 tools (Databricks restrictions) | — | unit | `pytest tests/agents/review/test_tool_schemas.py -x` | ❌ W0 | ⬜ pending |
| AGENT-01 | Assistant `tool_calls` echoed verbatim; every `tool` message's `tool_call_id` matches | — | unit | `pytest tests/agents/review/test_message_history.py -x` | ❌ W0 | ⬜ pending |
| AGENT-03 | Token ceiling trips → `stop_reason="ceiling"`, grounded partial returned, no exception | T-03-BUDGET | unit | `pytest tests/agents/review/test_loop_budget.py::test_token_ceiling -x` | ❌ W0 | ⬜ pending |
| AGENT-03 | Wall-clock ceiling trips (injected clock) | T-03-BUDGET | unit | `pytest tests/agents/review/test_loop_budget.py::test_wallclock_ceiling -x` | ❌ W0 | ⬜ pending |
| AGENT-03 | DR stop after N unproductive turns; an enumerate turn counts as **productive** (D-BUD2) | — | unit | `pytest tests/agents/review/test_loop_budget.py::test_diminishing_returns -x` | ❌ W0 | ⬜ pending |
| AGENT-03 | Breaker trips on identical `(tool, args)` × N | T-03-LOOP | unit | `pytest tests/agents/review/test_loop_budget.py::test_breaker_identical_args -x` | ❌ W0 | ⬜ pending |
| AGENT-03 | Breaker trips on N consecutive same `(reason_code, half)` | T-03-LOOP | unit | `pytest tests/agents/review/test_loop_budget.py::test_breaker_same_class -x` | ❌ W0 | ⬜ pending |
| AGENT-03 | **D-BUD6 forced runaway vs REAL loop + REAL `src/tools`** — ceiling trips, grounded partial, no crash, no overspend | T-03-BUDGET | **integration (offline)** | `pytest tests/agents/review/test_runaway.py -x` | ❌ W0 | ⬜ pending |
| AGENT-04 | No tool call + under budget + not DR ⇒ nudge injected, turn consumed, `continuation_count` increments | — | unit | `pytest tests/agents/review/test_continuation_floor.py::test_nudge_on_premature_stop -x` | ❌ W0 | ⬜ pending |
| AGENT-04 | Nudging stops at DR bound; `which_bound == "diminishing_returns"` | — | unit | `pytest tests/agents/review/test_continuation_floor.py::test_nudge_bounded_by_dr -x` | ❌ W0 | ⬜ pending |
| AGENT-04 | Nudging stops at hard cap; `which_bound == "max_continuations"` | — | unit | `pytest tests/agents/review/test_continuation_floor.py::test_nudge_bounded_by_cap -x` | ❌ W0 | ⬜ pending |
| AGENT-04 | `findings_before_vs_after_each_nudge` recorded per continuation (D-TEL5 decisive number) | — | unit | `pytest tests/agents/review/test_continuation_floor.py::test_continuation_telemetry -x` | ❌ W0 | ⬜ pending |
| GROUND-01 | **Span-ID round-trip composition test** — render → parse → re-mint → `was_issued` → `open_span` byte-exact, over a real `build_corpus_index`, for all 5 rendering tools | T-03-SPAN | **composition** | `pytest tests/agents/review/test_spanref_roundtrip.py -x` | ❌ W0 | ⬜ pending |
| GROUND-01 | Loop-side unresolvable span ref returns a **distinct** reason code, never `not_byte_exact` (a loop bug must not masquerade as model span-invention) | T-03-SPAN | unit | `pytest tests/agents/review/test_spanref_roundtrip.py::test_unresolvable_ref_is_not_span_invention -x` | ❌ W0 | ⬜ pending |
| GROUND-01/03 | `emit_finding` rejections carry the correct `half` at all 7 rejection sites (D-TEL3) | — | unit | `pytest tests/tools/test_emit_finding.py -k half -x` | ⚠️ file exists, assertions ❌ | ⬜ pending |
| GROUND-03 | `rule_span_id` + `verdict` survive onto the `Fault` — node `test_verdict_and_span_ids_survive_onto_the_fault` (plan 03-02 Task 3(f)) | — | unit | `pytest tests/unit/test_schemas.py -k verdict -x` | ⚠️ file exists, assertion ❌ | ⬜ pending |
| DETECT-03 | `run_oracles`-the-tool returns leads; **no span pre-recorded in the ledger** (D-ORC2) | T-03-ORACLE | unit | `pytest tests/agents/review/test_oracles_tool.py::test_no_prerecorded_spans -x` | ❌ W0 | ⬜ pending |
| DETECT-03 | S9, S10, P10 each produce a lead on a fixture that omits the element | — | unit | `pytest tests/agents/review/test_oracles_tool.py::test_s9_s10_p10_leads -x` | ❌ W0 (**S10 does not exist in code today**) | ⬜ pending |
| DETECT-04 | Verdict is enum-constrained; a free-text verdict is rejected | — | unit | `pytest tests/agents/review/test_tool_schemas.py::test_verdict_enum -x` | ❌ W0 | ⬜ pending |
| D-LOOP4 | Rendered prefix **byte-identical across two different corpora**, plus a negative control proving the test is not vacuous | — | unit (offline) | `pytest tests/agents/review/test_prefix_stability.py -x` | ❌ W0 | ⬜ pending |
| D-VER1 | If any legacy pass is retained, it is **provably non-dropping**; and nothing between the emit gate and the report removes a finding | — | unit | `pytest tests/agents/review/test_verify_nondropping.py -x` | ❌ W0 | ⬜ pending |
| D-TEL1 | Summary carries every provenance field; aborted run is self-evidently distinguishable from completed | — | unit | `pytest tests/agents/review/test_telemetry.py -x` | ❌ W0 | ⬜ pending |
| D-TEL2 | Every `reason_code` a tool can emit is in `KNOWN_REASON_CODES`; unknown codes land in the `unrecognized` bucket | — | unit | `pytest tests/tools/test_contracts.py -k reason_codes -x` | ⚠️ file exists, assertion ❌ | ⬜ pending |
| D-TEL4 | Pre-repair and post-repair malformed rates counted **separately**; a pre-repair fix consumes **no** turn (D-LOOP5 corollary) | — | unit | `pytest tests/agents/review/test_repair_accounting.py -x` | ❌ W0 | ⬜ pending |
| P2 (D-PRE1) | `pdf.py` fallback branch yields non-empty blocks on a scanned-with-text-layer fixture | T-03-PARSE | unit | `pytest tests/unit/test_parse.py -k fallback_blocks -x` | ❌ W0 | ⬜ pending |
| P2 (D-PRE1) | A `PARSER_VERSION` bump changes `cache_key` (stale-cache corruption guard) | T-03-PARSE | unit | `pytest tests/ingest/test_store.py -k parser_version -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## The four load-bearing test designs

Full code sketches live in `03-RESEARCH.md:1120-1184`. Summary of why each is non-negotiable:

1. **Span-ID round-trip (composition).** Render → parse → re-mint → `was_issued` → `open_span`, over a real persisted corpus, for all five rendering tools. This is the boundary-crossing test whose absence would let a loop-side re-mint bug ship — and that bug would surface as `not_byte_exact`/`half=submission`, which D-TEL3 pre-registers as **model span-invention**. A loop bug would therefore produce a **wrong NO-GO**. Mirrors `tests/tools/test_enumerate_fetch_emit_e2e.py`.
2. **D-BUD6 forced-runaway driver.** Real loop, real `src/tools`, real offline `CorpusIndex`, zero LLM spend. Set `max_turns` deliberately high so the **token ceiling** is what trips — otherwise the test proves the wrong gate.
3. **D-LOOP4 prefix stability + negative control.** `render_prefix` must serialize **both** the system message and the tool-schema list. Without the negative control, a trivially-constant prefix passes forever and proves nothing.
4. **D-VER1 proof-by-test.** Expect the "legacy verify drops findings" assertion to **pass today** (i.e. it documents that `verify_and_tier` IS dropping — `verify.py:136-144`), justifying the agent-path bypass. Then assert the positive property on the shipped path: `len(report.faults) == len(emitted_faults)`.

---

## Wave 0 Requirements

- [ ] `tests/agents/review/__init__.py` + `conftest.py` — `ScriptedChatClient`, `ForcedRunaway`, replay fixtures, **multi-document** corpus builder (extend `build_corpus_index` to N documents)
- [ ] `tests/agents/review/test_loop_basic.py` — AGENT-01
- [ ] `tests/agents/review/test_tool_schemas.py` — D-LOOP3 + Databricks schema-restriction assertions + verdict enum
- [ ] `tests/agents/review/test_message_history.py` — `tool_call_id` / `raw_message` echo
- [ ] `tests/agents/review/test_loop_budget.py` — AGENT-03 (ceiling / wall-clock / DR / breaker ×2)
- [ ] `tests/agents/review/test_runaway.py` — D-BUD6
- [ ] `tests/agents/review/test_continuation_floor.py` — AGENT-04 ×4
- [ ] `tests/agents/review/test_spanref_roundtrip.py` — GROUND-01 composition test
- [ ] `tests/agents/review/test_prefix_stability.py` — D-LOOP4 + negative control
- [ ] `tests/agents/review/test_verify_nondropping.py` — D-VER1
- [ ] `tests/agents/review/test_telemetry.py` — D-TEL1 provenance
- [ ] `tests/agents/review/test_repair_accounting.py` — D-TEL4 pre/post split
- [ ] `tests/agents/review/test_oracles_tool.py` — D-ORC1/D-ORC2 + S9/S10/P10
- [ ] Extend `tests/tools/test_emit_finding.py` — `half` at all 7 rejection sites
- [ ] Extend `tests/tools/test_contracts.py` — `KNOWN_REASON_CODES` coverage
- [ ] Extend `tests/unit/test_schemas.py` — `test_verdict_and_span_ids_survive_onto_the_fault` (GROUND-03 / DETECT-04)
- [ ] Extend `tests/unit/test_parse.py` — P2 fallback blocks
- [ ] Extend `tests/ingest/test_store.py` — `PARSER_VERSION` in `cache_key`
- [ ] *Optional but recommended:* `.github/workflows/test.yml` running pytest with no Databricks credentials — makes D-RB6 **checkable** rather than asserted

*Framework install: none needed — pytest 9.1.1 is present and configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The 3 scored agent runs (D-GO2) | AGENT-01, GROUND-01/03, DETECT-03/04 | Requires live Databricks Llama 3.3 70B; costs real tokens; the result **is** the measurement, not a pass/fail assertion | Run the agent arm 3× under frozen config per D-GO2(ii); commit 3 JSONL + 3 summaries + cross-run comparison to the phase directory |
| The 3 baseline re-runs (D-LOOP2) | EVAL gate reference | Same — live model, and its median is the committed governing reference | Run **before** the agent arm; commit median to the pre-registration with its SHA |
| Qwen tool-fidelity probe (D-GO3(ii)) | AGENT-01 | Live Qwen endpoint; pass bar is ≥95% schema-conformant turns + ≥1 finding through the emit gate | Bounded multi-turn run on the same corpus; record pre- and post-repair rates separately |
| Real-model low-ceiling confirmation (D-BUD6) | AGENT-03 | Confirms the code gate behaves identically under a real tool-calling model | One run with a deliberately low ceiling; **declared as not among the 3** |
| Budget calibration run(s) (D-BUD1) | AGENT-03 | Live model on a **held-out** corpus; multiple pre-registered before it executes | Measure full multi-document consumption; disclose figures in the report; findings neither scored nor quoted |
| **GO/NO-GO verdict** | phase gate | **Senior reviewer's call** against the committed pre-registration (D-GO5 sign-off). The executor reports numbers and telemetry; it does **not** declare the verdict | Read the 3 summaries + cross-run comparison against `03-GO-NOGO-PREREGISTRATION.md` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all ❌ MISSING references above
- [x] No watch-mode flags
- [x] Feedback latency < 15s (quick) / 90s (full)
- [x] Every manual-only verification is listed above with instructions (live-model work cannot be automated)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-01

> `wave_0_complete` stays `false` deliberately. The Wave 0 test files above genuinely do not exist
> yet — that flag flips during **execution**, not planning. Everything else in this contract is
> settled against the 19 plans as written.
