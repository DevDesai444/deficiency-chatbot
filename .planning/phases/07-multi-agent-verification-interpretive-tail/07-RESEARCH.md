# Phase 7: Multi-Agent Verification + Interpretive Tail (β) - Research

**Researched:** 2026-08-13
**Domain:** LLM-as-judge ensemble/consensus verification + agentic interpretive detection, over an on-prem fleet, wired into an existing grounded deterministic recall pipeline
**Confidence:** HIGH (codebase-grounded; the reusable stack was read in full). MEDIUM on the interpretive-tail loop shape (novel, no prior art in-repo — the P3 drive-loop NO-GO is the governing caution).

## Summary

Phase 7 is the **precision half** of DefPredict. Recall is already owned deterministically by Phases 4–5 (absence enumeration + structural/reference/precedent legs, each emitting a grounded `Fault` with a typed anchor). Phase 6 proved two things that fix the shape of this phase: (a) the verifier reliability stack (`verifier_prompt` + `reliability.coerce_and_validate` + `client.chat_completion_tools`) works live across the served on-prem fleet, and (b) **no single weak on-prem model discriminates KEEP-vs-DOWNGRADE reliably solo** (D-06b, downgrade-rate swings 0/2↔2/2 across near-identical configs). Precision therefore cannot come from a stronger prompt or a single model — it must come from **architecture**: full re-opened source+rule context (not the ≤500-char excerpt the probe used) + **decorrelated cross-family fleet consensus** (Llama⟂Qwen), downgrading a candidate only on affirmative majority agreement.

The invariant that makes this recall-safe by construction is fixed and non-negotiable: **downgrade-never-drop, enforced in code.** No verifier path deletes a candidate; unsure / ungrounded / parse-failed / split-vote all resolve to KEEP and only lower confidence. This is what lets a *weak* verifier fleet raise precision without ever costing a true positive — the entire reason β repurposed the agent as a verifier after the P3 recall NO-GO. The external ensemble literature independently confirms the design: decorrelated errors (not combination itself) drive ensemble gains, and cross-model voting is the standard countermeasure to a single model's familial/agreeableness bias.

**Primary recommendation:** Build a thin, hand-rolled orchestrator (NO framework) that, per candidate `Fault`, fans out `len(VERIFIER_FLEET)` isolated verifier calls whose family excludes the producer's family, each re-opening the candidate's own typed anchor via `get_section`/`read_guideline`, parses each verdict through the existing `reliability` stack into the existing `VERDICT` schema (EXTENDED, never redefined), applies a code-gated consensus rule (DOWNGRADE only on affirmative decorrelated majority; everything else → KEEP), re-resolves every surfaced `grounding_span` byte-exact via `ingest.anchors.open_span` before it is called "grounded," and emits a coverage report keyed on `dedup_key` = `docId:sectionId:ruleId`. Prove precision with `evals.run` end-to-end F1 + `beta-recall-gate` zero-TP-loss. Keep the interpretive tail (Qwen producer, Llama-inclusive verifier panel) small and gate it through the *same* consensus verifier + the same byte-exact grounding gate.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Verifier agent (VERIFY-01):**
- Each candidate → an **isolated, write-disabled** verifier sub-agent. It re-opens the cited source via `get_section` and rule via `read_guideline` — **full context, NOT the ≤500-char pre-rendered excerpt** the Phase-6 probe used. Tools are read-only for the verifier (no `emit_finding`/write).
- Returns machine-parsed `VERDICT: KEEP | DOWNGRADE` via the Phase-6 reliability stack (`verifier_system_prompt`, `coerce_and_validate` + bounded field-level retry, `<function=>` 400 recovery, reasoning-model token budgets, string→num coercion).
- **downgrade-never-drop enforced in CODE, not prompt**: no verifier path removes a candidate; an unsure/ungrounded/parse-failed verdict resolves to **KEEP** and only lowers confidence. A test asserts no code path deletes a candidate. This is the recall invariant.

**Orchestrator + fleet consensus + decorrelation (VERIFY-02, VERIFY-03):**
- Orchestrator fans out verifiers keyed on `docId:sectionId:ruleId`, **consolidates and dedups**, emits a **coverage report**: exactly what was reviewed and what could not be located — never an unqualified "compliant"/"no deficiencies."
- **Fleet consensus across `config.VERIFIER_FLEET` (Llama 3.3 70B + 2 Qwen MoE).** A candidate is **DOWNGRADEd only on affirmative consensus** — a **majority of decorrelated verifiers independently DOWNGRADE with grounding**; otherwise KEEP. Because DOWNGRADE requires agreement and unsure→KEEP, consensus **cannot cost recall**.
- **Cross-family decorrelation:** the verifier panel for a candidate must not be the same family as whatever produced it, and no verifier sees the producer's chain-of-thought — only claim + re-opened source + rule. For deterministic candidates (no model producer) any fleet mix is valid; for interpretive-tail candidates the verifier family ≠ the tail producer's family. A test asserts the verifier cannot see the producer's reasoning. Lineage via `config.MODEL_LINEAGE`.

**Interpretive tail (VERIFY-04):**
- Producer family = **Qwen** (so the Llama-inclusive verifier panel is cross-family from it — pick the panel to exclude the producer family).
- Surfaces grounded deficiencies no deterministic rule expresses; **each pinned to a re-openable verbatim quote + cited rule**, then passed through the SAME consensus verifier (precision gate).
- Precision-gated: on the Phase-0 eval set, adding verification + interpretive-tail iterations **does not lower end-to-end F1 and loses ZERO true positives vs. Phase-5 output** (the gate).

**Grounding (byte-exact — deferred from Phase 6):**
- `grounding_span` must byte-exact re-resolve against the source corpus before any finding is surfaced. A finding whose span cannot be re-resolved is not emitted as grounded (but the candidate is not dropped — confidence lowered).

**Anti-overfitting / on-prem (β laws):**
- All verifier/consensus/tail logic stays rulebook/structure/graph-general — no submission- or corpus-specific constants. Eval corpus is a proxy, never a target. On-prem only: every model call routes through `VERIFIER_FLEET` (on-prem guard holds).

### Claude's Discretion
- Exact consensus threshold (simple majority vs. weighted-by-family), panel size per candidate, and whether to short-circuit obvious KEEPs for cost — chosen at implementation time to hit the F1/zero-TP-loss gate; the invariant (DOWNGRADE needs affirmative decorrelated agreement, unsure→KEEP) is fixed.

### Deferred Ideas (OUT OF SCOPE)
- Cost governor: stable cached prefix, escalating compaction, cheap-model triage, large-corpus load test — **Phase 8**.
- Restoring Nemotron into the fleet if Databricks custom serving is later enabled — infra, not P7.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VERIFY-01 | Each candidate judged by isolated, write-disabled verifier sub-agent → `VERDICT: KEEP \| DOWNGRADE` (never DROP; unsure→KEEP; enforced in code) | `VERDICT` schema (`schemas/llm.py`) exists and is EXTEND-only; `verifier_system_prompt` already specifies the downgrade-never-drop invariant; `reliability.coerce_and_validate` returns `ParseFailed` which the orchestrator maps to KEEP (it deliberately does NOT bake fallback-KEEP in — see reliability.py docstring). Re-open via read-only `get_section`/`read_guideline`. |
| VERIFY-02 | Orchestrator fans out keyed on `docId:sectionId:ruleId`, consolidates/dedups, coverage report | `Fault.dedup_key` field ALREADY = `"{doc_id}:{section_id}:{rule_id_or_null}"` (schemas/faults.py:189) — the fan-out key exists. Typed anchors (`StructuralAnchor`/`ReferenceAnchor`/`PrecedentAnchor`/`CoverageAbsenceAnchor`) carry everything a verifier needs to re-derive. `ComplianceVerdict` makes an unqualified "compliant" structurally unrepresentable (faults.py:40). |
| VERIFY-03 | Verifier cross-family / decorrelated from candidate source | `config.MODEL_LINEAGE` maps every endpoint → family ("llama"/"qwen"); `config.VERIFIER_FLEET` is the pool. Decorrelation = pick panel where `MODEL_LINEAGE[verifier] != producer_family`. |
| VERIFY-04 | Agentic interpretive-tail pass surfaces grounded deficiencies no deterministic rule expresses | Reuses the Phase-2 tool layer (`search_corpus`/`get_section`/`read_guideline`/`follow_reference`) + `emit_finding` grounding gate (byte-exact) + the same consensus verifier as the precision gate. P3 NO-GO is the governing caution — keep it tightly scoped and precision-gated. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fleet verifier calls (KEEP/DOWNGRADE) | LLM serving (Databricks on-prem) | — | Model reasoning; must route through `VERIFIER_FLEET` + on-prem guard |
| Verdict parse / coerce / retry | Reliability stack (`llm/reliability.py`) | — | Already the single hardened place; verifier inherits it for free |
| Verdict schema | Schema layer (`schemas/llm.py` `VERDICT`) | — | EXTEND-only; stable guided-decode target |
| Re-opening source + rule (full context) | Tool layer (`tools/get_section`, `tools/read_guideline`) | — | Read-only, span-annotated; the verifier's ONLY view into evidence |
| Consensus decision (downgrade-never-drop) | Orchestrator (NEW, code gate) | — | Load-bearing invariant → code, never prompt (β law) |
| Decorrelation (family exclusion) | Orchestrator (NEW) reading `config.MODEL_LINEAGE` | — | Pure config lookup; no model call |
| Byte-exact `grounding_span` re-resolution | `ingest/anchors.open_span` + `emit_finding` gate | — | The primitive already exists and raises `HashMismatch`; reuse, never reimplement |
| Dedup / consolidation | Orchestrator (NEW) on `Fault.dedup_key` | — | Key already minted by Phase-5 emit gates |
| Coverage report | Orchestrator (NEW) | Report/CLI surface | Reviewed-KEEP / reviewed-DOWNGRADE / could-not-locate — honest "what was checked" |
| Interpretive tail producer | Agentic loop (reuse `agents/review`) on Qwen | Tool layer | Novel-deficiency generation; grounded via `emit_finding` |
| F1 / zero-TP-loss gate | Eval harness (`evals/run.py`, `evals/match.py`) | — | The gate the whole phase is graded against |

## Standard Stack

**No new external libraries.** The project law (CLAUDE.md "What NOT to Use" + on-prem MEMORY constraint) forbids adopting an agent framework and forbids any external LLM API. Every dependency this phase needs is already in the repo. The "stack" here is the existing internal modules.

### Core (existing, reuse verbatim)
| Module | Purpose | Why Standard |
|--------|---------|--------------|
| `src/config.py` — `VERIFIER_FLEET`, `MODEL_LINEAGE`, `verifier_model` | The fleet pool + family lineage the orchestrator fans out over and decorrelates on | `[VERIFIED: read src/config.py]` Built in Phase 6 explicitly "for Phase 7 fan-out". Fleet = Llama 3.3 70B + 2 Qwen MoE. |
| `src/llm/verifier_prompt.py` — `verifier_system_prompt(thinking_mode, model)` | The invariant-aligned, family-aware skeptical-reviewer prompt | `[VERIFIED]` Corpus-agnostic; already specifies downgrade-never-drop; the SAME prompt the D-06 gate validated. |
| `src/llm/reliability.py` — `coerce_and_validate`, `format_field_level_reprompt`, `build_guided_extra_body`, `supports_guided_json` | Verdict parse + bounded field-level corrective retry + guided-decode + string→num coercion; returns `(instance, None) XOR (None, ParseFailed)` | `[VERIFIED]` Contract: NEVER fabricates a verdict. `ParseFailed` → caller maps to KEEP (invariant lives in the ORCHESTRATOR, deliberately not baked here). |
| `src/llm/client.py` — `chat_completion_tools(...)` | The tool-calling turn with `<function=>` 400 recovery, on-prem allow-list guard, guided-decode auto-inject, rate-limit backoff | `[VERIFIED]` `finish_reason="tool_parse_error"` on native-syntax 400 → no-tool-call turn → orchestrator's parse-fail→KEEP path. On-prem guard (`get_client`) fails loud before any HTTP call. |
| `src/schemas/llm.py` — `VERDICT`, `VerdictChoice`, `ParseFailed` | The verdict model. **EXTEND (add fields), NEVER redefine** — its docstring says so and `tool_schema_for_databricks(VERDICT)` is the stable guided-decode target. | `[VERIFIED]` `verdict` enum NEVER coerced (off-value → ParseFailed); `grounding_span` already `min_length=1` + non-blank. |
| `src/tools/get_section.py`, `src/tools/read_guideline.py` | The read-only re-open surface. Returns span-ID-annotated text; oversized → preview+handle (never truncates). | `[VERIFIED]` This is the "full context, not the ≤500-char excerpt" the verifier must use. `read_guideline(citation=...)` fetches rule text; `get_section(start,end/heading)` fetches source. |
| `src/ingest/anchors.py` — `open_span(span, nt, doc_id)`, `HashMismatch`, `mint_span`, `short_hash` | The byte-exact re-open/verify primitive — the grounding gate | `[VERIFIED]` Returns (raw, canonical) or raises `HashMismatch`. This IS the byte-exact `grounding_span` re-resolution for the Phase-7 gate. Never reimplement. |
| `src/tools/emit_finding.py` — `emit_finding`, `emit_*_finding`, `issue_cached_span` | The only path a Fault exists; re-opens both submission + rule byte-exact via `open_span` | `[VERIFIED]` The interpretive tail emits through `emit_finding` (verdict/rule/span all re-validated). The pattern to re-use for byte-exact re-resolution. |
| `src/evals/run.py`, `src/evals/match.py`, `src/evals/metrics.py` | F1 / recall-by-family / zero-TP-loss + `beta-recall-gate` | `[VERIFIED]` `score()` is the frozen matcher; `beta-recall-gate` is the "no baseline matched id lost" ratchet; `_end_to_end`/`_end_to_end_by_family` give precision+recall+F1 inputs. |
| `src/schemas/faults.py` — `Fault`, `dedup_key`, `confidence`, `confidence_tier`, typed anchors | The candidate objects the verifier judges and the orchestrator consolidates | `[VERIFIED]` `dedup_key` = `"{doc_id}:{section_id}:{rule_id_or_null}"` IS the VERIFY-02 fan-out key. `confidence`/`confidence_tier` are the fields a DOWNGRADE lowers. |

### Supporting (existing, reuse as needed)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `src/tools/ledger.py` — `RetrievalLedger` | Records issued span-IDs; `was_issued` gates `emit_finding` | Every verifier re-open records spans; the tail's emit needs issued spans. |
| `src/agents/review/*` (`loop.py::run_review`, `registry.py`, `budget.py`, `telemetry.py`, `prompts.py`) | The Phase-3 hand-rolled tool loop + budget ledger + per-turn telemetry | The interpretive tail reuses this loop machinery (it already exists and is HEAD). Do NOT rebuild a loop. |
| `src/llm/structured.py` — `tool_schema_for_databricks`, `parse_structured` | Databricks-legal tool schema derivation (strips `$ref`/`anyOf`/`pattern`) | Deriving the VERDICT tool schema; called internally by `build_guided_extra_body`. |
| `src/rulebook/structural.py`, `references.py`, `precedent_search.py`, `absence.py` | Phase 4/5 candidate producers (consumed, not modified) | The verifier's input; the tail is a sibling producer, not a replacement. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled orchestrator | PydanticAI / LangGraph agent framework | **Rejected by project law.** CLAUDE.md: hand-rolled loop over the OpenAI-compatible endpoints; frameworks fight the bespoke grounding/consensus. `[CITED: ./CLAUDE.md "What NOT to Use"]` |
| `openai` 1.109.1 (installed) | `openai` 2.50.0 (CLAUDE.md-recommended upgrade) | **Do NOT bundle the upgrade into Phase 7.** `[VERIFIED: python3 -c import openai → 1.109.1]` The repo still pins 1.x; `chat_completion_tools` is written against it. A major-version bump is its own risk (v2 changed client internals) — out of scope; note it, don't do it here. |
| Simple unweighted majority | Weighted-by-family / quorum vote | Claude's Discretion. Literature notes plain majority "cannot distinguish 5-4 from 9-0" `[CITED: arxiv 2511.15714]`. But given only 2 families and unsure→KEEP, a simple "≥ majority of panel affirmatively DOWNGRADE-with-grounding" is safe; pick the threshold empirically against the F1 gate. |

**Installation:** none. `[VERIFIED]` `openai` 1.109.1 and `pydantic` 2.12.0 already installed; no new package.

**Version verification:** `[VERIFIED: python3 -c "import openai,pydantic"]` → `openai 1.109.1`, `pydantic 2.12.0` (2026-08-13). CLAUDE.md's "upgrade `openai` to 2.50.0" is a **future** item, not a Phase-7 dependency.

## Architecture Patterns

### System Architecture Diagram

```
Phase 5 output: list[Fault]  (each with dedup_key, typed anchor, confidence)
        │
        ▼
┌───────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR (new, hand-rolled, code gates only)                       │
│                                                                         │
│  1. CONSOLIDATE / DEDUP by Fault.dedup_key  (docId:sectionId:ruleId)    │
│         │                                                               │
│  2. for each unique candidate:                                          │
│         │                                                               │
│    ┌────┴─── decorrelation: producer_family = family(candidate)         │
│    │         panel = [m for m in VERIFIER_FLEET                         │
│    │                  if MODEL_LINEAGE[m] != producer_family]           │
│    │         (deterministic candidate ⇒ producer_family=None ⇒ any mix) │
│    │                                                                    │
│    │   FAN OUT (isolated call per panel member, no shared CoT):         │
│    │   ┌──────────────────────────────────────────────────────┐        │
│    │   │ VERIFIER call k  (write-disabled; sees ONLY:          │        │
│    │   │   claim + re-opened SOURCE (get_section, full)        │        │
│    │   │        + re-opened RULE   (read_guideline, full)      │        │
│    │   │   NOT the producer's reasoning/CoT)                   │        │
│    │   │   → chat_completion_tools(VERDICT schema, model=k)    │        │
│    │   │   → coerce_and_validate → VERDICT | ParseFailed       │        │
│    │   │   → ParseFailed / parse_error / empty span ⇒ KEEP     │        │
│    │   └──────────────────────────────────────────────────────┘        │
│    │        │ (one verdict per panel member)                            │
│    │        ▼                                                           │
│  3. CONSENSUS GATE (code, invariant):                                   │
│       downgrade_votes = verdicts that are DOWNGRADE                     │
│                         AND grounding_span re-resolves byte-exact       │
│       if affirmative_majority(downgrade_votes, panel): DOWNGRADE        │
│                (lower Fault.confidence / confidence_tier — NEVER drop)  │
│       else: KEEP  (unsure / split / lone-downgrade / parse-fail)        │
│                                                                         │
│  4. GROUNDING GATE: open_span(grounding_span) byte-exact or            │
│       "reviewed but not grounded" (confidence lowered, not dropped)     │
└───────────────────────────────────────────────────────────────────────┘
        │
        ├──────────────► COVERAGE REPORT
        │                {reviewed & KEEP, reviewed & DOWNGRADE (which
        │                 verifiers agreed), could-not-locate source/rule}
        │
        ▼
   Verified Fault list ─────────────────────────────────────────────┐
        ▲                                                            │
        │  (same consensus verifier = precision gate)                │
┌───────┴───────────────────────────────────────────────┐           │
│  INTERPRETIVE TAIL (Qwen producer, agentic)            │           │
│  reuse agents/review loop → search_corpus/get_section/ │           │
│  read_guideline/follow_reference → emit_finding        │           │
│  (byte-exact grounding gate) → candidate Faults ───────┘           │
│  panel excludes Qwen (producer family) ⇒ Llama-inclusive           │
└────────────────────────────────────────────────────────────────────┘
        │
        ▼
   evals.run: end-to-end F1 + recall-by-family + beta-recall-gate
   (zero-TP-loss vs Phase-5 output)  ← THE PHASE GATE
```

### Recommended Structure (new files; sibling packages, do not clobber HEAD)
```
src/verify/                        # NEW package — the β verifier orchestration
├── __init__.py
├── panel.py          # decorrelation: producer family → panel (reads config.MODEL_LINEAGE/VERIFIER_FLEET)
├── verifier.py       # ONE isolated verifier call: prompt → chat_completion_tools → coerce_and_validate → VERDICT|KEEP
├── consensus.py      # the code-gated invariant: DOWNGRADE only on affirmative decorrelated majority; else KEEP
├── grounding.py      # byte-exact grounding_span re-resolution via ingest.anchors.open_span (thin wrapper)
├── orchestrator.py   # fan-out over dedup_key, consolidate/dedup, apply consensus+grounding, build coverage report
└── coverage.py       # CoverageReport model (reviewed-KEEP / reviewed-DOWNGRADE / could-not-locate)

src/verify/tail.py    # interpretive tail: Qwen agentic producer → emit_finding → same consensus verifier
```
(Placement rationale `[VERIFIED: STATE.md "verifier + deterministic recall are sibling packages"]` — Phase-5 legs live under `src/rulebook/`; the verifier is a new sibling, not an edit to the recall legs.)

### Pattern 1: Isolated single verifier call (the atom)
**What:** One panel member judges one candidate against re-opened full context.
**When to use:** Every fan-out leg.
```python
# Source: composes src/llm/verifier_prompt.py + src/llm/client.py + src/llm/reliability.py (VERIFIED)
def verify_once(candidate, source_text, rule_text, model) -> VERDICT | Literal["KEEP"]:
    system = verifier_system_prompt(thinking_mode="off", model=model)  # family-aware
    messages = [
        {"role": "system", "content": system},
        # ONLY claim + re-opened source + rule. NEVER the producer's chain-of-thought (decorrelation-in-code).
        {"role": "user", "content": render_candidate(candidate, source_text, rule_text)},
    ]
    turn = chat_completion_tools(messages, tools=[verdict_tool], model=model,
                                 temperature=0.0, guided_model_cls=VERDICT)
    if turn.finish_reason in ("tool_parse_error", "error") or not turn.tool_calls:
        return "KEEP"                                   # invariant: unreadable ⇒ KEEP
    args = json.loads(turn.tool_calls[0].function.arguments)
    verdict, failed = coerce_and_validate(args, VERDICT, retries_remaining=s.verifier_max_repair_calls)
    if failed is not None:
        # one bounded corrective re-prompt using failed.reason, then:
        return "KEEP"                                   # invariant: parse-fail ⇒ KEEP
    return verdict
```

### Pattern 2: Consensus gate (the invariant, in code)
**What:** Aggregate panel verdicts; DOWNGRADE only on affirmative decorrelated majority.
```python
# Source: encodes CONTEXT.md locked invariant (VERIFIED against 06-06-SUMMARY finding)
def consensus(candidate, verdicts, panel_size) -> tuple[str, list[str]]:
    # A vote counts as a DOWNGRADE only if it is DOWNGRADE *and* its grounding_span re-resolves.
    downgraders = [v.model for v in verdicts
                   if isinstance(v.verdict, VerdictChoice) and v.verdict == VerdictChoice.DOWNGRADE
                   and grounding_reresolves(candidate, v.grounding_span)]
    if len(downgraders) * 2 > panel_size:               # simple affirmative majority (Discretion: threshold)
        return "DOWNGRADE", downgraders                 # lower confidence — caller NEVER removes the Fault
    return "KEEP", downgraders                           # unsure / split / lone ⇒ KEEP
```

### Pattern 3: Byte-exact grounding re-resolution (reuse, do not reinvent)
**What:** Prove the `grounding_span` the verdict cites still re-opens byte-exact.
```python
# Source: src/ingest/anchors.py (VERIFIED) — the SAME primitive emit_finding uses
def grounding_reresolves(candidate, grounding_span_text) -> bool:
    # The candidate carries a re-openable SpanID (submission_span_id / anchor span). The verifier's
    # grounding_span is a verbatim substring assertion; re-resolution means: the cited span-ID
    # still open_span()s (no HashMismatch) AND grounding_span_text is a substring of that raw text.
    try:
        raw, _ = open_span(candidate.submission_span_id, nt, candidate.submission_span_id.doc_id)
    except HashMismatch:
        return False
    return _norm(grounding_span_text) in _norm(raw)
```

### Anti-Patterns to Avoid
- **Putting the recall invariant in the prompt.** `[VERIFIED: CLAUDE.md β law]` "Load-bearing invariants are CODE gates at the tool boundary, never prompt instructions." The prompt may *describe* downgrade-never-drop (it does), but the *guarantee* must be a code path with a test asserting no branch deletes a candidate.
- **Letting a verifier see the producer's chain-of-thought.** Correlated reasoning = rubber-stamp. A test must assert the verifier message contains only claim + re-opened source + rule.
- **Baking fallback-KEEP into `coerce_and_validate`.** `[VERIFIED: reliability.py docstring]` It deliberately returns `ParseFailed` so "verifier said keep" is never conflated with "we couldn't read the verifier." The KEEP mapping belongs in the orchestrator.
- **Counting a DOWNGRADE whose grounding doesn't re-resolve.** An ungrounded downgrade must not lower confidence toward drop — it collapses to KEEP (recall invariant).
- **Redefining `VERDICT` or `Fault`.** EXTEND only (add fields). `tool_schema_for_databricks(VERDICT)` is the frozen guided-decode target.
- **Chasing the F1 metric with corpus-specific tuning.** `[VERIFIED: MEMORY on-hardcoding]` RECALL-05 guard forbids submission-specific constants; the eval corpus is a proxy.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Verdict JSON parse + retry + coercion | A new parser | `reliability.coerce_and_validate` | Already handles string→num, single-key unwrap, field-level reprompt, XOR contract; tested in one place. |
| Byte-exact span re-resolution | New hashing/offset logic | `ingest.anchors.open_span` / `HashMismatch` | The content-addressed primitive with normalizer-version binding; reimplementing risks silent wrong citations. |
| The verifier prompt | A new prompt | `verifier_prompt.verifier_system_prompt` | Corpus-agnostic, family-aware, invariant-aligned; is the prompt the D-06 gate validated. |
| On-prem model guard | A new allow-list check | `client.get_client` (imports `ON_PREM_ALLOW_LIST`) | Deny-first substring + exact allow-list, fails loud before any HTTP call. Single source of truth. |
| Tool-call turn / 400 recovery / backoff | A new client call | `client.chat_completion_tools` | `<function=>` 400 → `tool_parse_error` no-tool-call turn; rate-limit backoff; guided-decode auto-inject. |
| Fan-out key | A new key scheme | `Fault.dedup_key` | Already = `docId:sectionId:ruleId` (VERIFY-02's exact key). |
| Family lineage / fleet pool | Hardcoding model names | `config.MODEL_LINEAGE`, `config.VERIFIER_FLEET` | Env-overridable; guarded by `test_config_verifier`. |
| Interpretive-tail loop | A new agent loop | `agents/review/loop.run_review` + `registry` + `budget` | The hand-rolled loop already exists at HEAD with budgets/telemetry. |
| F1 / zero-TP-loss gate | A new scorer | `evals.match.score`, `evals.run beta-recall-gate` | Frozen matcher; the gate that catches real-corpus TP loss. |

**Key insight:** Phase 6 was explicitly built so that Phase 7 is *assembly*, not invention. Almost every hard part (grounding primitive, reliability stack, on-prem guard, fleet config, dedup key, F1 harness) already exists and is tested. The genuinely new code is small: `panel.py` (decorrelation lookup), `consensus.py` (the code invariant), `orchestrator.py` (fan-out + coverage), and a tightly-scoped `tail.py`.

## Runtime State Inventory

Phase 7 is code + model-orchestration only — no rename/migration. One data-adjacency note:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None new — verifier reads the existing corpus cache + rulebook store via `get_section`/`read_guideline`; writes nothing. | None — verifier is write-disabled by design. |
| Live service config | `VERIFIER_FLEET` names three Databricks serving endpoints; all already served + validated live in 06-06. | None — verified served (06-06-SUMMARY live gate). |
| OS-registered state | None. | None. |
| Secrets/env vars | `VERIFIER_MODEL_NAME`, `VERIFIER_FLEET` overridable via env; `DATABRICKS_TOKEN`/`DATABRICKS_HOST` already configured. | None — reuse existing. |
| Build artifacts | None. | None. |

**Precedent-leg dependency:** `data/rulebook.faiss` gates the precedent leg (`precedent-gate` structured-skips when absent). If Phase-7 F1 must include precedent candidates, the FAISS asset must be present in the run environment. `[VERIFIED: evals/run.py cmd_precedent_gate]`

## Common Pitfalls

### Pitfall 1: Weak-model discrimination is unstable single-shot (the whole reason for the fleet)
**What goes wrong:** Trusting one verifier's DOWNGRADE. `[VERIFIED: 06-06-SUMMARY D-06b]` downgrade-rate swings 0/2↔2/2 across near-identical configs; a perfect verifier on that set still tripped the tripwire.
**Why:** Weak open-weights models global-lean (blanket-KEEP or blanket-DOWNGRADE); different families catch *different* FPs (Qwen122B-off caught 2/2 planted FPs where Llama caught 0/2).
**How to avoid:** Fan across families; DOWNGRADE only on affirmative decorrelated majority. This converts unreliable individual discriminators into a usable precision filter without risking recall.
**Warning signs:** A verifier that returns the same verdict for every candidate (measure per-verifier downgrade-rate; a rate near 0 or 1 is a global lean, not discrimination).

### Pitfall 2: The impoverished-input trap (why P6 solo failed)
**What goes wrong:** Feeding the verifier a truncated ≤500-char excerpt. `[VERIFIED: CONTEXT.md]` "that impoverished input was why solo single-shot discrimination was weak."
**How to avoid:** Re-open **full** source via `get_section` (paginate via handle if oversized — never truncate) and full rule via `read_guideline`. The verifier's input quality is the dominant precision lever, above model choice.

### Pitfall 3: Confirmation / agreeableness bias
**What goes wrong:** A candidate framed as a "finding" gets rubber-stamped KEEP. `[VERIFIED: verifier_prompt.py docstring]` + `[CITED: arxiv 2510.11822 "agreeableness bias"]`.
**How to avoid:** The prompt already supplies skeptical-reviewer discipline ("KEEP unless you can AFFIRMATIVELY DISPROVE"). Cross-family voting is the standard countermeasure to a single model's familial bias `[CITED: arxiv 2607.10139]`.

### Pitfall 4: Silent recall loss through a non-obvious code path
**What goes wrong:** A `del`/filter somewhere (dedup collision, exception handler, "compliant" early-return) removes a candidate.
**How to avoid:** A test asserting **no code path in `src/verify/` deletes a Fault** — the DOWNGRADE path may only mutate `confidence`/`confidence_tier`. Consolidation must merge, never drop. Run `beta-recall-gate` after every change (in the MAIN tree — `[VERIFIED: MEMORY beta-recall-gate]` subagent worktree runs are meaningless without the gitignored corpus).

### Pitfall 5: The F1 metric is mis-calibrated on a keep-heavy candidate set
**What goes wrong:** `[VERIFIED: 06-06-SUMMARY]` Only 2 of 115 candidates were known-false, so a perfect verifier keeps 98.3% and can trip a blanket-keep wire. Optimizing a per-item discrimination floor on this distribution is misleading.
**How to avoid:** Grade on **end-to-end F1 against a properly-labeled FP set + zero-TP-loss**, not a per-item downgrade-rate. Ensure the eval set carries enough labeled false positives for precision to be measurable (a Wave-0 gap to check — see Validation Architecture).

### Pitfall 6: Decorrelation hole when producer family isn't recorded
**What goes wrong:** Interpretive-tail candidate produced by Qwen but verified by a Qwen-inclusive panel → correlated rubber-stamp.
**How to avoid:** Tag each candidate with its producer family (deterministic legs → None → any panel; tail → "qwen" → panel excludes qwen). Assert in a test that a tail candidate's panel contains no `MODEL_LINEAGE[m] == "qwen"`.

### Pitfall 7: `openai` version drift
**What goes wrong:** Assuming `openai` 2.x semantics; the repo runs 1.109.1.
**How to avoid:** `[VERIFIED]` Code against the installed 1.x client (as `client.py` already does). Do not fold the CLAUDE.md-recommended 2.50.0 upgrade into this phase.

## Code Examples

### Decorrelation panel selection
```python
# Source: reads config.MODEL_LINEAGE + config.VERIFIER_FLEET (VERIFIED src/config.py)
from config import MODEL_LINEAGE, VERIFIER_FLEET

def panel_for(producer_family: str | None) -> tuple[str, ...]:
    """Deterministic candidate → producer_family is None → any fleet mix is valid.
    Interpretive-tail candidate → exclude the producer's family (VERIFY-03)."""
    if producer_family is None:
        return VERIFIER_FLEET
    panel = tuple(m for m in VERIFIER_FLEET if MODEL_LINEAGE.get(m, "") != producer_family)
    return panel or VERIFIER_FLEET  # never empty; if a family owns the whole fleet, fall back (log it)
```

### Consolidation by the existing dedup key
```python
# Source: Fault.dedup_key = "{doc_id}:{section_id}:{rule_id_or_null}" (VERIFIED schemas/faults.py:189)
def consolidate(faults: list[Fault]) -> dict[str, list[Fault]]:
    groups: dict[str, list[Fault]] = {}
    for f in faults:
        key = f.dedup_key or f"{f.submission_span_id.doc_id}:{f.submission_span_id.start}:null"
        groups.setdefault(key, []).append(f)   # MERGE, never drop
    return groups
```

### Coverage report shape (VERIFY-02, honest "what was checked")
```python
# Source: encodes CONTEXT.md "specifics" + ComplianceVerdict discipline (VERIFIED)
class CoverageReport(BaseModel):
    reviewed_keep: list[str]         # dedup_keys reviewed → KEEP
    reviewed_downgrade: list[dict]   # {dedup_key, agreeing_verifiers: [model...]}
    could_not_locate: list[dict]     # {dedup_key, half: "source"|"rule", reason}
    # There is NO "compliant" field — a "no deficiencies" result is expressed only as
    # (reviewed_keep == [] AND could_not_locate states exactly what was searched).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single LLM-as-judge | Cross-model **jury/ensemble** consensus | 2025–2026 literature | `[CITED: arxiv 2607.10139]` cross-model consensus outperforms single judges; matches CONTEXT design exactly. |
| Plain majority vote | Diversity/decorrelation-aware, calibration-aware aggregation | 2025–2026 | `[CITED: arxiv 2511.15714]` "decorrelated errors, not combination itself, drive ensemble gains." Validates the Llama⟂Qwen decorrelation requirement. |
| Trust the judge's agreement | Mitigate agreeableness bias explicitly | 2025 | `[CITED: arxiv 2510.11822]` recommends cross-model voting to counter familial bias + report inter-rater reliability. |
| P3 model-driven recall loop | Deterministic recall + write-disabled verifier | 2026-08-05 (β pivot) | `[VERIFIED: STATE.md]` The loop can't do recall on weak local models; the agent is precision-only now. |

**Deprecated/outdated for this repo:**
- Anthropic `cache_control` / Claude-orchestrator variant: **permanently excluded** by the on-prem law `[VERIFIED: MEMORY on-prem-privacy-constraint]`. Any CLAUDE.md note about a Claude verifier is overridden.
- The `openai` 2.50.0 recommendation in CLAUDE.md: **not yet applied**; repo runs 1.109.1.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A candidate's `submission_span_id` (or anchor span) is always present + re-openable for grounding re-resolution. Absence findings carry a `CoverageAbsenceAnchor` (no single submission span) — its grounding must re-resolve via the anchor's `claim_span_id`/`sub_threshold_hits`, not `submission_span_id`. | Grounding gate | If missed, absence-family findings fail grounding re-resolution and get wrongly de-grounded. Planner must branch grounding on anchor type. |
| A2 | Simple affirmative majority (`>panel/2`) is the right default consensus threshold. | Consensus | Discretion item; if precision is too low, may need weighted/quorum. Tune against F1 gate. |
| A3 | The eval set carries enough labeled false positives for precision (not just recall) to be measurable. | Validation | If FP labels are sparse (P6 had 2/115), F1 precision signal is weak — may need Wave-0 FP labeling. |
| A4 | Phase 5 (`src/rulebook/structural|references|precedent`, `absence`) is landed and emitting `Fault`s with `dedup_key` before Phase 7 runs end-to-end. | Whole phase | STATE shows Phase 6 complete; Phase 5 legs exist in code + gates. Confirm Phase-5 F1 baseline is committed (`beta_recall_baseline.json`) before gating Phase 7 against it. |
| A5 | `producer_family` can be reliably attached to each candidate (None for deterministic legs, "qwen" for tail). | Decorrelation | If a candidate arrives untagged, decorrelation silently degrades. Tag at production time (add a field or map by `leg_tag`/`source`). |

## Open Questions

1. **How does `grounding_span` re-resolution work for absence-typed findings (no submission span)?**
   - What we know: `CoverageAbsenceAnchor` has `claim_span_id` (optional) + `sub_threshold_hits` + `manifest_span_ids`; `emit_absence_finding` already re-opens `claim_span_id` byte-exact.
   - What's unclear: which of these the verifier's `grounding_span` must match against.
   - Recommendation: grounding for an absence finding re-resolves against `claim_span_id` if present, else the top `sub_threshold_hits` span (mirror `emit_absence_finding`'s own R1 evidence logic). Planner: make grounding gate anchor-type-aware.

2. **Consensus threshold + panel size (Claude's Discretion).**
   - What we know: fleet = 3 (1 Llama + 2 Qwen); for a Qwen-produced tail candidate the decorrelated panel is just the 1 Llama.
   - What's unclear: a 1-member panel can't form a "majority" — a lone Llama DOWNGRADE would need special handling.
   - Recommendation: for a single-member decorrelated panel, require that lone verdict to be a grounded DOWNGRADE to downgrade (still recall-safe: unsure→KEEP), OR widen the panel by allowing a same-family verifier as a *second opinion* that cannot by itself cause a downgrade. Decide against the F1 gate; log the choice.

3. **Does the interpretive tail run per-document or corpus-wide, and under what budget?**
   - What we know: `agents/review/loop.run_review` + `BudgetLedger` exist; cost governor is Phase 8.
   - Recommendation: keep the tail tightly budgeted (reuse `BudgetLedger` ceilings), scope small, and precision-gate hard. It must not lower F1 — if it adds FPs the consensus verifier doesn't catch, disable it for that run.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `openai` (Python) | fleet calls | ✓ | 1.109.1 | — (do NOT upgrade in P7) |
| `pydantic` | schemas | ✓ | 2.12.0 | — |
| Databricks serving: Llama 3.3 70B | verifier fleet | ✓ | live | — (validated 06-06) |
| Databricks serving: Qwen35-122b-a10b | verifier fleet | ✓ | live | — |
| Databricks serving: Qwen3-next-80b-a3b | verifier fleet | ✓ | live | — |
| `DATABRICKS_HOST`/`DATABRICKS_TOKEN` | fleet routing | ✓ (assumed configured) | — | — |
| `data/rulebook.faiss` | precedent-leg candidates in F1 | ✗ in clean checkout | — | precedent-gate structured-skips; F1 measured on absence+structural+reference legs |
| Local eval corpus (`data/`, gitignored) | `beta-recall-gate` real-corpus measurement | ✗ in CI | — | gate structured-skips (WR-03); MUST run in MAIN tree with corpus present |

**Missing dependencies with no fallback:** none blocking. **With fallback:** FAISS asset + local corpus both structured-skip in CI; the real precision measurement must run where the gitignored corpus + FAISS exist.

## Validation Architecture

> nyquist_validation is `true` in .planning/config.json → this section is REQUIRED.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`asyncio_mode=auto` already set per CLAUDE.md) |
| Config file | repo `pyproject.toml` / pytest config (existing) |
| Quick run command | `python3 -m pytest tests/verify/ -x -q` (new dir) |
| Full suite command | `python3 -m pytest -q` (no-endpoint suite; 130 passed/11 skipped baseline in 06-06) |
| Live gate command | `python3 -m evals.run beta-recall-gate` (MAIN tree, corpus present) + `python3 -m pytest -m integration tests/verify/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VERIFY-01 | No code path deletes a candidate; unsure/parse-fail/error ⇒ KEEP | unit | `pytest tests/verify/test_invariant_no_drop.py -x` | ❌ Wave 0 |
| VERIFY-01 | Verifier is write-disabled (no emit/write tool reachable) | unit | `pytest tests/verify/test_verifier_readonly.py -x` | ❌ Wave 0 |
| VERIFY-02 | Fan-out keyed on dedup_key; consolidation merges, never drops | unit | `pytest tests/verify/test_orchestrator_consolidate.py -x` | ❌ Wave 0 |
| VERIFY-02 | Coverage report has no "compliant"; states reviewed/could-not-locate | unit | `pytest tests/verify/test_coverage_report.py -x` | ❌ Wave 0 |
| VERIFY-03 | Verifier message never contains the producer's chain-of-thought | unit | `pytest tests/verify/test_decorrelation.py -x` | ❌ Wave 0 |
| VERIFY-03 | Tail candidate panel excludes producer family (qwen) | unit | `pytest tests/verify/test_panel_family.py -x` | ❌ Wave 0 |
| VERIFY-01/03 | DOWNGRADE requires affirmative grounded majority; lone/split ⇒ KEEP | unit | `pytest tests/verify/test_consensus.py -x` | ❌ Wave 0 |
| grounding | `grounding_span` re-resolves byte-exact or finding is not "grounded" (not dropped) | unit | `pytest tests/verify/test_grounding_reresolve.py -x` | ❌ Wave 0 |
| VERIFY-04 | Tail candidate is grounded via emit_finding + passes same consensus gate | unit | `pytest tests/verify/test_tail_gate.py -x` | ❌ Wave 0 |
| gate | Verification+tail does not lower F1, loses zero TP vs Phase 5 | live gate | `python3 -m evals.run beta-recall-gate` | ✅ exists |
| gate | Fleet verdict conformance still passes (regression) | integration | `pytest -m integration tests/evals/test_verifier_probe.py` | ✅ exists |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/verify/ -x -q`
- **Per wave merge:** `python3 -m pytest -q` (full no-endpoint suite) + `python3 -m evals.run beta-recall-gate` in the MAIN tree
- **Phase gate:** end-to-end F1 (precision+recall by family) not below Phase-5 baseline AND zero baseline-matched TP lost, before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/verify/` directory + `conftest.py` — scripted fleet doubles (a `ScriptedFleetClient` returning canned per-model VERDICTs, mirroring the Phase-3 `ScriptedChatClient` pattern in `agents/review`) so consensus/decorrelation/invariant tests run offline and deterministic.
- [ ] Labeled false-positive fixtures — confirm the eval set has enough FP labels for precision to be measurable (P6 had 2/115). If sparse, add planted-FP candidates to the fixture so the F1 precision signal is real.
- [ ] A committed **Phase-5 F1/precision baseline** for the "does not lower F1" comparison (Phase-5's `beta_recall_baseline.json` covers recall/matched-set; confirm a precision/F1 reference exists or add one).
- [ ] No framework install needed (hand-rolled). Existing pytest infra covers the rest.

## Security Domain

> `security_enforcement` not present in config → treat as enabled; scoped to what's relevant.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `VERDICT` pydantic schema + `coerce_and_validate` (enum never coerced; off-value → ParseFailed); tool schemas sanitized via `tool_schema_for_databricks`. |
| V6 Cryptography | no (checksum only) | `blake2b` span hash is an integrity/drift checksum, not an auth boundary (documented in `anchors.py`). Do not repurpose as security. |
| V9/V12 Data confidentiality (21 CFR Part 11) | yes | `client.get_client` on-prem allow-list (deny-first substring `claude`/`gpt`/`gemini` + exact `ON_PREM_ALLOW_LIST`) — every fleet call must route through it; no external LLM API, ever. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Regulated submission text leaking to an external LLM | Information disclosure | On-prem guard fails loud before any HTTP call; `VERIFIER_FLEET` is all self-hosted; guard test green (`[VERIFIED: 06-06]`). |
| Prompt-injected content in a submission steering the verifier | Tampering | Verifier is write-disabled (read-only tools); grounding re-resolution is byte-exact code (not model-trusted); DOWNGRADE requires grounded majority — a single manipulated verdict can't drop a candidate. |
| Silent citation drift (wrong quote surfaced as verbatim) | Tampering | `open_span` raises `HashMismatch` on any normalizer/text drift; never returns a wrong substring. |

## Sources

### Primary (HIGH confidence)
- `src/config.py`, `src/llm/{verifier_prompt,reliability,client,structured}.py`, `src/schemas/{llm,faults}.py`, `src/tools/{get_section,read_guideline,emit_finding,ledger}.py`, `src/ingest/anchors.py`, `src/evals/{run,match,metrics}.py` — read in full this session.
- `.planning/phases/07-.../07-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/06-.../06-06-SUMMARY.md` — read in full.
- `python3 -c "import openai,pydantic"` → openai 1.109.1, pydantic 2.12.0 (2026-08-13).
- `./CLAUDE.md` (project law: hand-rolled loop, no framework, on-prem), user MEMORY (on-prem-privacy-constraint, beta-recall-gate, no-hardcoding).

### Secondary (MEDIUM confidence — external, corroborating the locked design)
- LLMs as a Jury: Cross-Model Consensus Can Outperform single judges — arxiv 2607.10139
- Majority Rules: LLM Ensemble for Content Categorization (decorrelated errors drive gains) — arxiv 2511.15714
- Beyond Consensus: Mitigating Agreeableness Bias in LLM Judge Evaluations — arxiv 2510.11822

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every module read directly; no new dependency.
- Architecture: HIGH — the invariant, dedup key, grounding primitive, and fleet config all pre-exist and are tested; the orchestrator is thin assembly.
- Pitfalls: HIGH — sourced from the 06-06 live findings, not speculation.
- Interpretive tail: MEDIUM — novel; P3 NO-GO is the governing caution; keep small + hard-gated.

**Research date:** 2026-08-13
**Valid until:** ~2026-09-13 (stable internal codebase; re-check only if Phase 5 legs or `openai` pin change)

Sources:
- [LLMs as a Jury: Cross-Model Consensus](https://arxiv.org/pdf/2607.10139)
- [Majority Rules: LLM Ensemble for Content Categorization](https://arxiv.org/html/2511.15714v1)
- [Beyond Consensus: Mitigating the Agreeableness Bias in LLM Judge Evaluations](https://arxiv.org/html/2510.11822v2)
