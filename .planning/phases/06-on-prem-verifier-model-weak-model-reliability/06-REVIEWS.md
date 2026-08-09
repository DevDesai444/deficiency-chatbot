---
phase: 6
reviewers: [opus48-recall-lens, opus48-precision-lens, opus48-generality-lens]
review_method: three independent Opus 4.8 instances, each fresh-context, mutually independent (no external CLI available; on-prem-safe — plans only, no submission data)
reviewed_at: 2026-08-09T01:20:00Z
plans_reviewed: [06-01-PLAN.md, 06-02-PLAN.md, 06-03-PLAN.md, 06-04-PLAN.md, 06-05-PLAN.md, 06-06-PLAN.md]
north_star: total recall (catch every real deficiency) + total precision (every finding real) + zero per-corpus hardcoding (LLMs own the infinite interpretive space)
---

# Cross-AI Plan Review — Phase 6 (On-Prem Verifier Model + Weak-Model Reliability)

Three independent Opus 4.8 reviewers, each in a fresh context with no knowledge of how the plans
were written, each given a distinct adversarial lens tied to the product's north star. Convened
because no external/different-model CLI or local server was installed; independence is achieved
through separate contexts + adversarial framing rather than a different model family.

**Headline:** All three reviewers — independently — identified the **same single HIGH issue**: the
**D-06b discrimination gate (Plan 06) is gameable by a near-constant-DOWNGRADE verifier** because it
pools accuracy over a ~6-KEEP-vs-~109-DOWNGRADE probe split. A verifier that downgrades almost
everything scores ~0.94 and clears the ≥0.80 bar while getting **zero of the 6 real matched-GT
deficiencies right** — i.e. Phase 6 could sign off a recall-destroying verifier and hand it to
Phase 7. This is a triple-independent consensus and is the top thing to fix before execution.

---

## Recall Review (Opus 4.8 — Recall lens)

### Summary
Phase 6 is, on balance, recall-protective by design: the D-12 XOR contract, the never-fabricate rule, the D-11 enum-never-coerced rule, and the honest telemetry discipline all correctly refuse to silently manufacture or drop verdicts, and the "caller decides never-drop" boundary is properly deferred to Phase 7 rather than pre-empted here. The reliability layer itself does not lose findings — it converts unreadable output into a *visible, typed* ParseFailed signal, which is exactly right. **The recall weakness is not in the reliability plumbing — it is in the D-06 discrimination gate and its probe substrate.** The probe set is 6 KEEP-expected vs ~109 DOWNGRADE-expected (a 95/5 imbalance, confirmed in `beta-measurement-summary.json`), and the gate is framed so that a model which systematically DOWNGRADES real deficiencies can still clear the ≥80% discrimination bar — a gate that green-lights a recall-destroying verifier into Phase 7. That is the single sharpest recall risk on the page. Secondary risks: the retry cap of 1 is not actually exercised as a *retry* in the coded `coerce_and_validate` (it returns a ParseFailed rather than re-prompting the model), and the constant-verdict tripwire only catches blanket-KEEP, not blanket-DOWNGRADE.

### Strengths
- **D-12 never-fabricate is coded and tested, not just asserted.** `coerce_and_validate` returns `(None, ParseFailed)` on failure; `test_no_fabricated_verdict` asserts `return[0] is None AND return[1] is not None`. An unreadable verifier cannot masquerade as a real verdict.
- **Parse-failure→KEEP policy is correctly deferred, not pre-empted.** The ParseFailed carries `layer`, `reason`, `raw_output`, `validation_error` — the signal Phase 7 needs to route to KEEP is preserved end to end.
- **Telemetry does not hide parse failures** (`coercion_enum_near_miss_rejected`, `reliability_exhausted_retries`, `guided_json_probe_exception_fallback`; Pitfall 5 warns on a suspiciously-zero ParseFailed counter).
- **Guided-decode degrade is fail-safe toward the real call, not toward dropping it** (D-09: any probe error → fall through to native tool-parser; never blocks the call).
- **Enum-never-coerced enforced at the right layer, tested both directions** (`test_enum_near_miss_not_coerced` + `test_enum_exact_value_unchanged`).

### Concerns
- **[HIGH] The D-06b discrimination bar can be cleared by a verifier that systematically DOWNGRADES real deficiencies.** 6 KEEP-expected vs ~109 DOWNGRADE-expected (`matched_gt_ids` = 5 + MS-01; `fp_count` = 100). Discrimination = `correct/total`. A model that DOWNGRADES everything scores ~109/115 = **0.948** — far above 0.80 — while getting **every real deficiency wrong (0/6 KEEP recall)**. The tripwire only fires at `max(keep_ratio, downgrade_ratio) ≥ 0.95`; a model at 0.939 DOWNGRADE passes both the tripwire and the 0.80 bar with near-zero KEEP recall. The gate certifies a recall-catastrophic verifier as Phase-6-complete.
- **[HIGH] The known-good (KEEP) half is too small/easy to certify recall.** Only 6 of 115 are KEEP-expected (the already-matched GT). No per-class KEEP-recall floor; a model could miss 3/6 and still land ~0.92 overall.
- **[MEDIUM] Retry cap = 1 is not a real corrective retry in code.** `coerce_and_validate` on `ValidationError` with `retries_remaining > 0` returns `ParseFailed(layer="reliability-L3", ...)` and stops — it never re-prompts the model. D-13's "one corrective retry recovers transient malformed args" does not happen inside Phase 6; a transiently-malformed-but-recoverable verdict becomes ParseFailed. Plan should match code or implement the loop.
- **[MEDIUM] D-14 "measurably reduced" harness replays 5 hand-authored synthetic VERDICT dicts, not real Phase-3 traces.** `QWEN_FAILURE_CLASS_SAMPLES` are fabricated to be exactly the ones `strict_coerce` recovers, diffed against `QWEN_POST_REPAIR_RATE = 0.80` (which came from a *different* real failure class). The test passes by construction and proves nothing about the real malformed-arg loss rate.
- **[MEDIUM] Constant-verdict tripwire is asymmetric** — designed to catch blanket-KEEP (the recall-*safe* failure) but weakest against blanket-DOWNGRADE (the recall-*fatal* one), and its 0.95 threshold sits right on the 95/5 legitimate-behavior noise floor.
- **[LOW] D-16 allow-list is a hardcoded frozenset in `client.py` duplicated from `config.DETECTOR_MODELS`;** a legitimate new on-prem model omitted from the second copy fails loud → halts the run → total recall failure for that folder.
- **[LOW] Nemotron endpoint-down runtime handling** is (correctly) out of Phase 6 scope, but the Phase-7 handoff should carry an explicit "verifier-unreachable ⇒ KEEP" requirement so the signal lands recall-safe.

### Suggestions
- Add a **per-class KEEP-recall floor** to `DiscriminationAccuracyMetric` (e.g. `keep_recall ≥ 5/6` AND balanced accuracy ≥ 0.80).
- Make the tripwire **two-sided** (fire on `downgrade_ratio ≥ 0.90` too); add a test where an all-DOWNGRADE stub verifier FAILS the suite.
- In `coerce_and_validate`, **either implement the actual corrective-retry loop or delete the D-13 "corrective retry" language** so the recall accounting is truthful.
- Replace the 5 synthetic D-14 dicts with a **replay of the actual Phase-3 malformed-arg traces**, or mark D-14 as a directional smoke test, not a gate.
- **Derive `_ON_PREM_ALLOW_LIST` from config** (or unit-test set-equality) so a valid on-prem model can't be silently rejected.
- Add a Phase-7 handoff line: "verifier unreachable / VERDICT ParseFailed ⇒ KEEP (never-drop), enforced in code."

### Risk Assessment
**Overall RECALL risk: MEDIUM–HIGH.** Reliability plumbing is recall-safe and honestly instrumented, but the D-06b gate as coded can certify a systematically-DOWNGRADING verifier — the exact machine Phase 7 builds on. Fix the gate (per-class KEEP floor + two-sided tripwire) and the retry/D-14 honesty, and this drops to LOW.

---

## Precision Review (Opus 4.8 — Precision lens)

### Summary
This plan protects precision more seriously than most — the D-06 two-dimensional bar, the constant-verdict tripwire, D-11 enum-never-coerced, and the D-12 XOR-no-fabrication contract are present, tested, and mostly hard-coded as literals with anti-tamper self-checks. The reliability layer is well-defended against admitting a *malformed* verdict. **The weakest link is the discrimination measurement itself (D-06b).** The probe's ground-truth split treats *every one of the ~109 FP-tail candidates as DOWNGRADE-expected* and *every one of the 6 matched-GT as KEEP-expected*, but that labeling is an over-approximation on both sides: some of the 109 "FP" candidates may be genuine deficiencies the Phase-5 scorer simply didn't match to a GT id, and the 80% bar plus 95% tripwire leave a wide corridor in which a **systematically KEEP-biased Nemotron can pass the gate while still waving through dozens of real false positives into Phase 7**. Precision is measured against a proxy label set whose "known-bad" half is not actually verified bad.

### Strengths
- **Parse-rate-only loophole explicitly closed** (D-06b + tripwire: `score = 0.0` when `max(keep_ratio, downgrade_ratio) ≥ 0.95`).
- **Discrimination denominator is the stricter choice** (`correct/total`, not `correct/parsed`; pinned against change without user approval).
- **Enum coercion forbidden and tested both directions** (`"keep"` → ParseFailed, never snapped to `KEEP`).
- **Never-fabricate is a hard, tested contract** (XOR return + per-iteration XOR assertion in 06-06).
- **`grounding_span` is a required VERDICT field.**
- **Guided schema routed through `tool_schema_for_databricks`, never raw** (Pitfall 7 grep gate forbidding `build_guided_extra_body_from_tools`).
- **D-14 is arithmetic** (literals pinned Wave 0, self-check, anti-tamper STRIDE entry).

### Concerns
- **[HIGH] The D-06b "known-bad" half is unverified, so precision is measured against a soft label.** `expected = "KEEP" if fid in matched_gt_ids else "DOWNGRADE"`. The summary's own `fn_gt_ids` shows 23 real GT deficiencies were *missed* by Phase 5. The ~109 "FP-tail" candidates are labeled DOWNGRADE-expected purely because the scorer didn't match them — but "unmatched" ≠ "false." If any FP-tail candidate is actually real (e.g. a legitimately-unresolved reference), the probe *rewards a verifier that downgrades real deficiencies* and *penalizes one that keeps them* — the inversion of the never-drop invariant. Falsifiable: inspect 10 of the 97 `UNRESOLVED_REF` candidates; if any is a genuine deficiency, the DOWNGRADE-expected label is wrong.
- **[HIGH] 0.80 discrimination + 6:109 imbalance means the gate can pass while ~17 false positives survive as KEEP.** `correct ≥ 0.80·115 ≈ 92` passes; a model emitting ~85% DOWNGRADE / ~15% KEEP sails under the 95% tripwire and over the 0.80 floor while KEEP-ing 15+ false positives into Phase 7 as confirmed findings.
- **[MEDIUM] KEEP-expected set is only 6; per-class discrimination never asserted.** The `keep_expected_total`/`downgrade_expected_total` counters are computed (lines 262-263) but never used in scoring — a model getting all 6 KEEP wrong still scores 0.948.
- **[MEDIUM] Thinking-ON vs OFF compared only on token count, never on discrimination quality** (`test_thinking_mode_token_split_is_detected` asserts only `on_tokens > off_tokens`). D-18's precision concern (reasoning-ON manufacturing plausible-but-wrong rationales) is untested.
- **[LOW] `grounding_span` required but never re-resolved byte-for-byte against the source** in Phase 6 (unlike `emit_finding`'s dual byte-exact gate). State that byte-exact re-resolution is a Phase-7 gate.
- **[LOW] `test_thinking_on_inflates_completion_tokens` contains `assert ... or True`** — a tautology that can never fail; dead assertion in a precision-critical probe file.

### Suggestions
- **Do not treat the full 109-candidate FP-tail as verified DOWNGRADE-expected.** Hand-verify a labeled *known-bad* (planted/confirmed-false) subset and compute discrimination over `known-good ∪ known-bad` only, matching D-06b's pre-registered wording ("known-good and known-**planted**-bad") — which the implementation silently widened to "everything not matched-GT." Highest-value edit.
- **Add per-class floors** (`keep_recall ≥ 0.80` AND `downgrade_recall ≥ 0.80` separately; the counters already exist).
- **Add an absolute FP-KEEP ceiling** (≤ K DOWNGRADE-expected verified KEEP, K pre-registered in D-06).
- **Compare discrimination across thinking modes** (`discrimination(on) ≥ discrimination(off) − ε`).
- **Delete the `assert ... or True` tautology.**
- **State that VERDICT `grounding_span` byte-exact re-resolution is a Phase-7 gate.**

### Risk Assessment
**PRECISION risk: MEDIUM-HIGH.** Arg-layer guards (enum-never-coerced, never-fabricate, sanitized guided schema, required grounding_span) are strong and well-tested — a malformed or fabricated-shape verdict cannot survive. But the headline precision instrument, D-06b, measures against an unverified proxy label set and permits a KEEP-biased verifier to forward ~15-17 false positives into Phase 7 while passing; its majority-class pooling can even reward downgrading real deficiencies.

---

## Generality / No-Hardcoding Review (Opus 4.8 — Generality + engineering lens)

### Summary
A genuinely well-engineered plan set, and on the specific generality traps this review targets it is **mostly clean by construction**: capability detection (D-09) is runtime-probed and cached, never a model-name allow-list; the on-prem guard (D-16) is a config-driven set; lineage tags (D-17) are a config dict; the quant/GPU choice (D-19/D-20) is gated on a live CLI query with a blocking human checkpoint; and enum coercion is explicitly forbidden (D-11). Test-first (Nyquist), XOR/never-fabricate enforced with a per-iteration invariant, D-14 baseline pinned as literals. **The one HIGH concern is not the reliability layer — it is that the D-06b discrimination gate is measured against a fixed, extremely skewed 6-KEEP-vs-109-DOWNGRADE probe set in a way trivially satisfiable by a near-constant-DOWNGRADE model, and does not generalize to a new folder.** Several MEDIUM guard-robustness/ordering issues also warrant fixes.

### Strengths
- **D-09 is textbook-correct** (runtime probe, cache per served-model-name, fail-safe to unsupported; explicitly "NOT a hardcoded model-name allow-list — that would rot").
- **D-16 correctly scoped as a security allow-list; adding an on-prem model is a config edit.**
- **Enum-never-coerced (D-11) defended in depth** (Pitfall 6 + threat T-06-03-02 + test).
- **VERDICT schema does not over-constrain the interpretive space** (forces the decision envelope, not the reasoning; free-text `rationale` + `grounding_span`).
- **D-19/D-20 is a real gate, not a rubber stamp** (blocking human checkpoint; rejects NVFP4 unless Blackwell confirmed; defaults to safe FP8; serving build blocked until ADR amended).
- **Probe set used as eval substrate, not a tuning target** (intent stated out loud; tripwire is an anti-gaming guard).
- **Honest telemetry discipline (D-12/D-14).**

### Concerns
- **[HIGH] C-1: D-06b discrimination gate is measured on a fixed ~6:109-skewed split in a way a near-constant model passes.** DOWNGRADE-all → 0.948 (tripwire correctly fires); DOWNGRADE-109/KEEP-7-8 → downgrade_ratio ≈ 0.93 (under the tripwire) and ~0.90+ accuracy purely from base rate, having gotten *zero* of the real matched-GT KEEPs right. KEEP-recall is only 6/115 of the score, so the gate can pass a verifier with near-zero recall on the exact findings the product exists to catch; nothing transfers to a new folder with a different base rate. Fix: score KEEP-recall and DOWNGRADE-rate separately with explicit per-class floors.
- **[MEDIUM] C-2: The D-16 allow-list is a hand-copied literal in `client.py`, decoupled from `config.DETECTOR_MODELS` — it will drift.** Add a model to `DETECTOR_MODELS` but forget the `client.py` copy → a legitimate on-prem model rejected at the boundary. Fix: single source of truth (`config.ON_PREM_ALLOW_LIST` imported by both) + `test` asserting `ON_PREM_ALLOW_LIST >= set(DETECTOR_MODELS)`.
- **[MEDIUM] C-3: The guard keys on exact model-ids, but real serving names carry version/variant suffixes** (`-v1_5`, dated variants); a legitimate id one character off fails closed. Consider a **deny-list-first** substring check (`claude`/`gpt`/`gemini`) combined with the allow-list, so a new on-prem model isn't blocked while external families still fail loudly.
- **[MEDIUM] C-4: `chat_completion_tools`/`get_client` signature change is cross-cutting with no enumerated caller audit, and existing callers call `get_client()` with no model arg — so the D-16 guard never runs for them.** The guard only fires when a caller passes `model=`. Fix: grep the call sites and confirm the guard sits on the model-resolution path (`resolve_model`/dispatch), not only an optional kwarg most callers won't pass.
- **[MEDIUM] C-5: (a) Circular-import risk `reliability.py` ↔ `structured.py`** (each now imports the other) — asserted "no circular import" via grep but not explained; pin it deliberately (function-local import if needed) + a `import llm.client` smoke test. **(b) The D-08 guided-decode auto-inject only fires when a caller passes `guided_model_cls`; Phase 6's own review-tool path is untyped, so guided decode for the 7 review tools is never actually exercised in Phase 6** — only the VERDICT path is. SC3/D-08's "wired for ALL 7 review tools" is not demonstrated by any Phase-6 test. Add one test calling `chat_completion_tools(tools=[...], guided_model_cls=VERDICT)` against a mock asserting `extra_body` is injected.
- **[LOW] C-6: `strict_coerce` numeric coercion is not annotation-aware** — it coerces *any* numeric-looking string to a number keyed only on "is it numeric," not the target field's type. As a *shared* module used by `structured.py`, a legitimate `str` field holding `"12345"` (batch number, CFR-ish token, version string) is silently coerced to `int`. Fix: gate coercion on the target field's annotation (only string→number when the field expects a number) — which also makes it genuinely lossless.
- **[LOW] C-7: `MATCHED_GT_IDS` is duplicated as a hardcoded literal in the test shell** while Plan 06 reads it from `beta-measurement-summary.json`; drop the literal or assert-equal to the JSON.
- **[LOW] C-8: Assert the KEEP-expected set is exactly 6** (`assert len(keep_expected) == 6`) so a corrupted/renamed summary can't silently shrink the KEEP class and worsen C-1.

### Suggestions
1. **Plan 06 Task 1 — replace pooled `correct/total` with per-class floors** (KEEP-recall on the 6 matched-GT ≥ ~0.80 AND FP-tail DOWNGRADE-rate ≥ 0.80; keep the tripwire as a third guard). Update D-06b wording in `06-CONTEXT.md` for pre-registration integrity.
2. **Plan 04 Task 1 — single source of truth for the allow-list** (`config.ON_PREM_ALLOW_LIST`, imported by `client.py`; test `>= set(DETECTOR_MODELS)`).
3. **Plan 04 Task 1 — add a deny-first substring check + a caller audit** (`grep -rn "get_client(" src/ && grep -rn "chat_completion_tools(" src/`; confirm the guard is on the model-resolution path).
4. **Plan 03/04 — pin the import direction explicitly + test the tools-turn guided path.**
5. **Plan 03 — make `strict_coerce` annotation-aware.**
6. **Plans 01/06 — one source for `matched_gt_ids`** (drop the literal or assert-equal; add `assert len(keep_expected) == 6`).

### Risk Assessment
**Overall GENERALITY / ENGINEERING risk: MEDIUM.** The reliability layer and the four named generality traps (D-09 runtime probe, D-16 config-driven guard, D-17 config lineage, D-19/D-20 live-hardware gate) are handled correctly and by-construction — a model of no-hardcoding discipline. The rating is driven by one HIGH metric-design flaw (C-1) plus a cluster of MEDIUM guard-drift/coverage issues. None are per-corpus hardcoding of *check conditions*; they are eval-validity and guard-robustness gaps, all fixable with targeted edits without re-architecting the phase.

---

## Consensus Summary

### Agreed Strengths (2+ reviewers)
- **The reliability plumbing is sound and honest.** D-12 never-fabricate (`VERDICT XOR ParseFailed`) is coded + tested; D-11 enum-never-coerced is enforced and tested both directions; guided schema is sanitized through `tool_schema_for_databricks` (Pitfall 7 grep gate); telemetry does not hide failures. (all 3)
- **The four named generality traps are handled by-construction:** D-09 runtime capability probe (not a rotting model-name list), D-16 config-driven security guard, D-17 config lineage tags, D-19/D-20 live-hardware gate with a blocking checkpoint. (recall + generality)
- **The parse-rate-only loophole is explicitly closed** by the D-06 two-dimensional bar + constant-verdict tripwire, and the discrimination denominator is the stricter `correct/total`. (precision + recall)
- **D-14 baseline is pinned as literals with anti-tamper self-checks.** (precision + generality)

### Agreed Concerns (2+ reviewers — priority order)
1. **[HIGH — ALL THREE, independently] The D-06b discrimination gate is gameable by a near-constant-DOWNGRADE verifier.** Pooled `correct/total` over a ~6-KEEP-vs-~109-DOWNGRADE split lets a blanket-DOWNGRADE model score ~0.94 and pass the ≥0.80 bar while getting **0/6 of the real deficiencies right**; the one-sided tripwire (fires only near 0.95 single-verdict uniformity) doesn't catch it. This is the phase's headline "prove the verifier works" gate, and it can certify a recall-destroying verifier into Phase 7. **The per-class `keep_expected_total`/`downgrade_expected_total` counters already exist in the code but are never used in scoring.** → **Fix: per-class floors (KEEP-recall AND DOWNGRADE-rate each ≥ ~0.80) + a two-sided tripwire + an absolute FP-KEEP ceiling.** This is the single most important edit and should block execution of Plan 06 until fixed.
2. **[HIGH/precision, echoed by recall] The "known-bad" half of the probe is unverified** — `else "DOWNGRADE"` labels every unmatched candidate as false, but Phase 5 missed 23 real GT deficiencies and 97 candidates are `UNRESOLVED_REF`; "unmatched" ≠ "false." The gate can reward downgrading real deficiencies. → **Fix: discriminate over a hand-verified known-good ∪ known-planted-bad subset (D-06b's original wording), not "everything not matched-GT."**
3. **[MEDIUM — recall + generality] The D-16 allow-list is a hardcoded literal in `client.py` decoupled from `config.DETECTOR_MODELS`** → drift → a legitimate on-prem model gets fail-loud rejected → the whole folder goes unreviewed (a total recall failure). → **Fix: single config source of truth + set-equality test; consider deny-first substring check; audit that the guard actually sits on the model-resolution path (today it only fires if `model=` is passed).**
4. **[MEDIUM — recall + precision] Two honesty gaps between plan claims and code:** (a) retry-cap-1 is described as a "corrective retry" but `coerce_and_validate` never re-prompts the model — it returns ParseFailed; (b) the D-14 "measurably reduced" harness replays 5 synthetic dicts built to be recoverable, not the real Phase-3 failure traces, so it passes by construction. → **Fix: make plan match code (implement the retry loop or drop the claim) and replay real traces (or label D-14 a smoke test, not a gate).**

### Divergent Views
- **Overall severity rating differs by lens, not substance:** Recall and Precision both rate their dimension **MEDIUM-HIGH**; Generality rates **MEDIUM**. The difference is scope of blast radius, not disagreement about the facts — all three point at the same D-06b root cause. Net: treat the phase as **plan-solid but with one execution-blocking eval-validity defect** (D-06b) plus a handful of MEDIUM guard/honesty fixes.
- **Unique-but-worth-noting singletons:** precision-only — thinking-ON/OFF compared only on token count not discrimination (D-18), `grounding_span` not byte-verified in-phase, and a dead `assert ... or True` tautology; generality-only — `strict_coerce` not annotation-aware (latent bug when `structured.py` reuses it on arbitrary models), circular-import risk `reliability.py`↔`structured.py`, and D-08 guided decode for the 7 review tools never actually exercised in Phase 6.

### Bottom line
The plans are well-engineered and disciplined on no-hardcoding — the generality traps this project cares most about are handled by-construction. But **the phase's own success gate (D-06b) does not currently prove what it claims**: because of the 6:109 class imbalance and pooled scoring, it can pass a verifier that keeps false positives and/or drops real deficiencies — directly against the recall+precision north star. Fix D-06b (per-class floors + verified known-bad labels) and the two plan-vs-code honesty gaps before executing Plan 06; the MEDIUM guard-robustness items should be folded into Plan 04.

---

*To incorporate this feedback into the plans:* `/gsd-plan-phase 6 --reviews`
