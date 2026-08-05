# Claude Code Benchmark — Gap Analysis vs DefPredict

Source: de-obfuscated Claude Code TS source at `../claude-code-ref` (1425 `.ts` + 552 `.tsx`, real code, not minified), dissected by 7 parallel subsystem agents 2026-08-05, then each claim verified against our actual code by the senior reviewer. Goal lens throughout: **catch ALL deficiencies (recall) and every emitted one correct (precision)** on weak local LLMs (Llama 3.3 70B / Qwen MoE).

## Verdict

Our plan is sound and, on the **correctness-critical** mechanisms, **equal-to or ahead-of Claude Code**. Grounding is stronger than CC's. The genuine gaps are concentrated in (a) **weak-model tool-call reliability**, (b) the **not-yet-planned Phases 4–6**, where CC's fan-out / verifier / compaction mechanisms should be encoded, and (c) a few **hard-gate** recall levers where we currently have only soft/advisory versions.

None of the gaps invalidate the Phase-3 GO/NO-GO design. Most are diagnostic hypotheses to test *after* the spike, not blind pre-run additions.

## Where we are already ahead of / equal to CC (do NOT "fix" these)

| Concern | CC | Us | Ref |
|---|---|---|---|
| Grounding by retyped text → smart-quote/ligature/NBSP false-rejects | Model retypes `old_string`; substring match, deliberately *widened* (curly↔straight, whitespace) | **Span-ID selection, never authoring**; `open_span` re-verifies byte-exact at emit (TOCTOU) | `emit_finding.py`; CC `FileEditTool.ts:316`, `utils.ts:73` |
| "Quote occurs N times — which one?" ambiguity | Uniqueness check needed (`FileEditTool.ts:329`) | **Unreachable by construction** — a span-ID names exactly one offset range | `emit_finding.py:9-18` |
| Finding lost on compaction | **No structured store** — survival relies on summariser reproducing prose (weak models paraphrase → drop) | `findings: list[Fault]` held outside the message stream | `loop.py:263,380`; CC `compact.ts:387` |
| Early evidence evicted → silent recall loss | `FileStateCache` is a 100-entry/25 MB **LRU** — entries evict | `RetrievalLedger._issued` **unbounded set**; issuance tracked independent of message presence | `ledger.py:17,26`; CC `fileStateCache.ts:18` |
| Anti-premature-stop | Token-budget continuation nudge + DR halt | Same shape: NUDGE + DR (tracks **new findings**) + per-continuation findings telemetry | `loop.py:332-355`, `budget.py:75-83,133-144` |
| Coverage awareness (CC todo reminder) | TodoWrite re-injected every 10 turns | Code-computed coverage reminder every 8 turns (unopened / opened-no-finding / oracle engagement) | `loop.py:184-229` |
| Don't trust `finish_reason` on weak models | Tracks tool_use presence, ignores `stop_reason` | Loop drives off parsed `turn.tool_calls` | `loop.py:332` |
| Strict args (no smuggled fields) | `z.strictObject` | `extra="forbid"` on every args model | `registry.py:73` |
| Mid-run injection off the cached prefix | `isMeta` `<system-reminder>` user turns | Coverage reminder is a runtime user message; static `prompts.py` only | `loop.py:411`, `prompts.py:4-6` |

## Adopt-list — what CC has that we don't (ranked, phase-mapped)

### A. Weak-model reliability (touches the Phase-3 loop — FREEZE-SENSITIVE)
1. **Field-level malformed-arg feedback.** We return generic *"send a JSON object matching this tool's schema exactly"* (`registry.py:234`). CC rewrites the validation error into imperatives — *"required param `X` missing"*, *"`top_k` expected number, got string"* (`toolErrors.ts:66-132`). Surface the pydantic error detail into the hint. **High leverage, low effort.**
2. **Guided/constrained tool-calling at decode time.** We have strict `response_format` wired for the *structured/repair* path (`structured.py:76`, used by `parse_structured`) but the *tool-call generation* path relies on validate-reflect. Add server-side guided tool-calling (vLLM guided `tool_choice` / Ollama `format`) — the one lever that beats after-the-fact validation, and we control the server. **Spike-worthy, medium confidence.**
3. **Targeted semantic coercion** as pydantic `BeforeValidator`s (quoted numbers/bools, single-key-wrapper unwrap) — CC's `semanticBoolean`/`semanticNumber`. Pydantic lax mode covers basic `"10"→10`; arg-wrapping and enum coercion are gaps. Keep advertised schema strict; be lenient only in the parser. **Medium.**

### B. Sub-agent fan-out (Phase 4 — currently TBD, safe to encode now)
4. **Assignment key = coverage detector.** Give every reviewer a stable `docId:sectionId:ruleId`; findings carry it → dedup key **and** a missing assignment (no finding returned) is mechanically detectable. Directly implements Phase-4 SC3. (CC `runAgent` merges on `tool_use_id`.)
5. **Distill at the boundary.** Orchestrator ingests only each worker's **final structured message**; full transcript to a disk sidechain. Keeps the orchestrator window flat at corpus scale. (CC `finalizeAgentTool`, `agentToolUtils.ts:276`.)
6. **Isolation by construction, not by prompt.** Each worker gets fresh empty history + scoped tools (CC `createSubagentContext`) → Reviewer B cannot re-emit Reviewer A's finding. Star topology; strip worker-to-worker messaging; dedup only in orchestrator.
7. **Empty-result sentinel.** A worker must emit an explicit "no deficiencies in this section" — CC found weak models read a blank result as "nothing to do" and quit (`AgentTool.tsx`). Makes our "no unqualified *compliant*" guarantee real.
8. **DO NOT use CC's `fork` (inherit-full-context) path.** Affordable only via Anthropic prompt caching; on weak/uncached models it is exactly the context-blowup we avoid. Use isolated empty-history sub-agents. Budget does **not** auto-propagate — thread the global fan-out budget yourself.

### C. Adversarial verifier (Phase 5 — TBD, safe to encode now). CC has the direct analog: `verificationAgent.ts`
9. **Write-disabled verifier.** Strip Edit/Write; read-only source+rule access only, so it physically cannot fabricate/patch evidence.
10. **Machine-parsed single-token verdict.** End with `VERDICT: KEEP | DOWNGRADE` (never `DROP`; **"unsure" resolves to KEEP** — mirrors CC's "PARTIAL only for environmental limits, never uncertainty"). Removes hedgy-prose verdicts weak models produce.
11. **Enumerated-failure-mode / inoculation prompt** ("your job is not to confirm — try to break it; you will feel the urge to skip, do the opposite").
12. **Evidence-or-reject, symmetric with our grounding.** A refutation without a verbatim re-opened source span + rule text is auto-rejected (CC rejects any PASS lacking command+output).
13. **BEFORE-ISSUING-FAIL gate** — before downgrading, the verifier must rule out "already handled / intentional / not-actionable."
14. **Bidirectional anti-hedging** — also guard against *over*-downgrading correct findings (CC `prompts.ts:240`). Our downgrade-never-drop already leans to recall; add the reciprocal.

### D. Hard recall gate (Phase 3 stop-logic and/or Phase 4 — FREEZE-SENSITIVE for P3)
15. **Hard end-of-turn coverage gate (CC Stop-hook analog).** We have a *soft* coverage reminder (advisory). CC's Stop hook returns a `blockingError` re-injected as the next user turn with `stopHookActive` — **the loop cannot terminate while work is incomplete** (`stopHooks.ts`, `query.ts:1282-1305`). A hard "refuse `completed` while unopened docs / unaddressed oracle leads remain (bounded)" is the single biggest recall lever. Include CC's **death-spiral guards** (skip on API-error turns; preserve compaction state across retries).

### E. Compaction detail (Phase 6 — TBD, safe to encode now)
16. **Re-inject the findings list verbatim after every compaction** — data is already safe in `findings`; this restores the *model's awareness* of what it found (CC re-injects plan files / recent reads wholesale, never summarized).
17. **Persist-then-handle shedding** — shed evidence to disk with a re-openable handle (doc→section→span), never a dead stub, so a cited span stays re-openable.
18. **Freeze the decision to NOT replace** (not just replacements) via a `seenIds` set; **group budgets by wire-merge boundaries**; **subtract freed tokens** after clearing or you falsely escalate to summarization; ≥1 keep-floor. (CC `toolResultStorage.ts:390`, `tokens.ts:226`.)

### F. Cheap polish (any phase)
19. Tag all mid-run injections as `<system-reminder>` and exclude from persisted transcript (CC `messages.ts:3101`). We already inject as user messages; adopt the tag + persistence rule.

## Open verifications (not yet closed)
- **`get_section` partial-read grounding**: confirm it records the span-ID of *exactly the bytes rendered* (not a wider section), so a windowed read cannot be cited beyond returned bytes (CC's partial-view = not-read, `FileEditTool.ts:276`). — `src/tools/get_section.py`
- **Dispatch-exception sibling orphaning**: today `loop.py:369-375` aborts on first tool exception, so remaining tool_call_ids get no result — safe *only because it returns*. If dispatch-exception ever becomes recoverable, synthesize error results for sibling calls (CC `query.ts:123` orphan guard) or the next request 400s.

## Sequencing vs the Phase-3 GO/NO-GO gate
Items **A** and **D-15** change how the loop behaves per turn. Adding them before the scored runs would test a *different* system than the one the baseline (`median 0.107`) was measured against and than the plan describes — confounding the GO/NO-GO and, if added after the prereg commits, voiding the run set (D-GO5). Senior-reviewer position: **run the GO/NO-GO on the current design; treat A/D-15 as the leading diagnosis-driven improvements for a Phase-3.x hardening pass or Phases 4–6, chosen by what the telemetry says the bottleneck actually is.** Encode B/C/E now (unplanned phases; safe).

## Terminology (KB / FKB) — deferred, scoped
- **KB** = FDA+ICH rules + past deficiencies (Databricks). **FKB** = the processed submission folder (today: corpus index / manifest / per-submission FAISS).
- Standardize in living docs + code identifiers/comments. **Exclude**: `src/evals/*` scoring machinery, the frozen baseline doc, `runs/` artifacts, and the uncommitted prereg. Execute after the sequencing decision, not mid-gate.

## CLI (deferred, captured)
Single `rich.Live` status line mapped to loop events: `✻ Reviewing… (mm:ss · docs · chunks · findings · budget% · esc to stop)`; stream tool calls → collapse to `✓ summary`; commit confirmed findings to scrollback; explicit `· compacting…` beat; tear down Live and print the full report inline at the end. Build in the CLI phase, not now.
