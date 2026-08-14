# Phase 7: Multi-Agent Verification + Interpretive Tail (β) - Context

**Gathered:** 2026-08-14
**Status:** Ready for planning
**Mode:** Smart-discuss (autonomous; decisions pre-selected from Phase 6 findings + ROADMAP success criteria, reviewer directive "you decide")

<domain>
## Phase Boundary

Repurpose the agent as the β **verifier** and add a precision-gated **interpretive tail**. Each
deterministic candidate from Phase 5 is judged by an isolated, write-disabled verifier that
re-opens the cited source + rule and returns a machine-parsed `VERDICT: KEEP | DOWNGRADE`
(**never DROP**; unsure→KEEP). An orchestrator fans verifiers out across the on-prem fleet keyed
on `docId:sectionId:ruleId`, consolidates/dedups, and emits a coverage report. Verifiers are
cross-family decorrelated (Llama⟂Qwen). A final agentic interpretive-tail pass surfaces grounded
deficiencies no deterministic rule expresses. **In scope:** verifier agent, orchestrator/consensus,
decorrelation, coverage report, interpretive tail, grounding byte-exact re-resolution, F1 gate.
**Out of scope:** cost governor / compaction / triage (Phase 8); new deterministic recall rules
(Phase 5 owns recall).
</domain>

<decisions>
## Implementation Decisions

### Verifier agent (VERIFY-01)
- Each candidate → an **isolated, write-disabled** verifier sub-agent. It re-opens the cited
  source via `get_section` and rule via `read_guideline` — **full context, NOT the ≤500-char
  pre-rendered excerpt** the Phase-6 probe used (that impoverished input was why solo single-shot
  discrimination was weak). Tools are read-only for the verifier (no `emit_finding`/write).
- Returns machine-parsed `VERDICT: KEEP | DOWNGRADE` via the Phase-6 reliability stack
  (`verifier_system_prompt` invariant-aligned prompt, `coerce_and_validate` + bounded field-level
  retry, `<function=>` 400 recovery, reasoning-model token budgets, string→num coercion).
- **downgrade-never-drop enforced in CODE, not prompt**: no verifier path removes a candidate; an
  unsure/ungrounded/parse-failed verdict resolves to **KEEP** and only lowers confidence. A test
  asserts no code path deletes a candidate. This is the recall invariant — it makes a weak verifier
  recall-safe by construction (the Phase-6 finding).

### Orchestrator + fleet consensus + decorrelation (VERIFY-02, VERIFY-03)
- Orchestrator fans out verifiers keyed on `docId:sectionId:ruleId`, **consolidates and dedups**,
  emits a **coverage report**: exactly what was reviewed and what could not be located — never an
  unqualified "compliant"/"no deficiencies."
- **Fleet consensus across `config.VERIFIER_FLEET` (Llama 3.3 70B + 2 Qwen MoE).** A candidate is
  **DOWNGRADEd only on affirmative consensus** — i.e. a **majority of decorrelated verifiers
  independently DOWNGRADE with grounding**; otherwise KEEP. Because DOWNGRADE requires agreement
  and unsure→KEEP, consensus **cannot cost recall** (a lone or split downgrade keeps the candidate).
  This is the real answer to the Phase-6 finding that no *single* weak model discriminates reliably.
- **Cross-family decorrelation:** the verifier panel for a candidate must not be the same family
  as whatever produced it, and no verifier sees the producer's chain-of-thought — only claim +
  re-opened source + rule. For deterministic candidates (no model producer) any fleet mix is valid;
  for interpretive-tail candidates the verifier family ≠ the tail producer's family. A test asserts
  the verifier cannot see the producer's reasoning. Lineage via `config.MODEL_LINEAGE`.

### Interpretive tail (VERIFY-04)
- Producer family = **Qwen** (so the Llama-inclusive verifier panel is cross-family from it, and
  vice-versa — pick the panel to exclude the producer family).
- Surfaces grounded deficiencies no deterministic rule expresses; **each pinned to a re-openable
  verbatim quote + cited rule**, then passed through the SAME consensus verifier (precision gate).
- Precision-gated: on the Phase-0 eval set, adding verification + interpretive-tail iterations
  **does not lower end-to-end F1 and loses ZERO true positives vs. Phase-5 output** (the gate).

### Grounding (byte-exact — deferred from Phase 6)
- `grounding_span` must byte-exact re-resolve against the source corpus before any finding is
  surfaced (the Phase-7 gate FIX-6 deferred from Phase 6). A finding whose span cannot be
  re-resolved is not emitted as grounded (but the candidate is not dropped — confidence lowered).

### Anti-overfitting / on-prem (β laws)
- All verifier/consensus/tail logic stays rulebook/structure/graph-general — no submission- or
  corpus-specific constants (generality guard extended if needed). Eval corpus is a proxy, never a
  target. On-prem only: every model call routes through `VERIFIER_FLEET` (on-prem guard holds).

### Claude's Discretion
- Exact consensus threshold (simple majority vs. weighted-by-family), panel size per candidate,
  and whether to short-circuit obvious KEEPs for cost — chosen at implementation time to hit the
  F1/zero-TP-loss gate; the invariant (DOWNGRADE needs affirmative decorrelated agreement,
  unsure→KEEP) is fixed and non-negotiable.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/llm/verifier_prompt.py` — canonical invariant-aligned, family-aware verifier prompt (Phase 6).
- `src/llm/reliability.py` — `coerce_and_validate` + field-level retry + coercions (RELIABILITY-01/02/03).
- `src/llm/client.py` — `chat_completion_tools` with `<function=>` 400 recovery + on-prem allow-list guard.
- `src/config.py` — `VERIFIER_FLEET`, `MODEL_LINEAGE`, `verifier_model`/`VERIFIER_MODEL_NAME`.
- `src/schemas/llm.py` — `VERDICT` (KEEP/DOWNGRADE, non-empty grounding_span) — Phase 7 EXTENDS, never redefines.
- Phase 5 deterministic candidate producers + `src/evals/match.py` (matcher) + `src/evals/run.py` (F1 harness).
- Navigation tools `get_section` / `read_guideline` (Phase 2 tool layer) for verifier re-open.

### Established Patterns
- Load-bearing invariants are CODE gates at the tool boundary, never prompt instructions (β law).
- Grounding = verbatim quote + cited rule per finding; no finding without a re-openable anchor.
- Recall-by-family + zero-TP-loss gate (Phase 0) gates every β phase.

### Integration Points
- Consumes Phase-5 deterministic candidates; emits verified/coverage output for the CLI report surface.
- Reuses the full Phase-6 verifier reliability stack for every fleet call.
</code_context>

<specifics>
## Specific Ideas

- The Phase-6 diagnostic showed each fleet model keeps-leans individually but *different* models
  catch *different* FPs (e.g. Qwen122B off caught 2/2 planted FPs). Consensus exploits this: fan
  across families and downgrade only on agreement — turning weak individual discriminators into a
  usable precision filter without risking recall.
- Coverage report must distinguish "reviewed & KEEP", "reviewed & DOWNGRADE (with which verifiers
  agreed)", and "could not locate source/rule" — feeding the CLI's honest "what was checked" surface.
</specifics>

<deferred>
## Deferred Ideas

- Cost governor: stable cached prefix, escalating compaction, cheap-model triage, large-corpus load
  test — **Phase 8**.
- Restoring Nemotron into the fleet if Databricks custom serving is later enabled — infra, not P7.
</deferred>
