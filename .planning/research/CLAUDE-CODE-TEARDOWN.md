# Claude Code Source Teardown — Transferable Mechanisms

**Read: 2026-07-30.** Source: full TypeScript source of Claude Code (~500k LOC), read directly — not the README.
Paths below are repo-relative to that source tree, kept for re-verification. The working clone was in a
session scratchpad and is **gone**; re-clone if a claim needs checking.

**Why this exists:** the mission is a CMC-document reviewer as good as Claude Code is at code. Claude Code
is the reference implementation of the architecture we're building, so its mechanisms are evidence, not
inspiration. This file is the durable record — requirements and roadmap criteria were derived from it, but
the *reasoning* lives here.

**Scope caveat — do not overstate this document.** Roughly 8 files were read deeply out of ~500k LOC:
`Tool.ts`, `FileEditTool.ts`, `FileReadTool/{limits,prompt}.ts`, `toolResultStorage.ts`, `microCompact.ts`,
`query/tokenBudget.ts`, `AgentTool/prompt.ts`, plus greps across `src/skills/` and `src/tools/`.
**`QueryEngine.ts` (1,295 lines), `query.ts` (1,729 lines), and the coordinator/teams layer were NOT read.**
Anything about the orchestration inner loop is therefore unverified.

---

## 1. Grounding is enforced at the tool boundary, by rejecting the call

**The single most important finding.** `src/tools/FileEditTool/FileEditTool.ts:274-310` — `validateInput`
refuses the edit outright, with typed error codes the model reads and self-corrects from:

| Gate | Behavior |
|---|---|
| `errorCode 6` | File was never read → refuse. **Also refuses on `isPartialView`** — if the model saw a transformed/truncated version, that does not count as having read it |
| `errorCode 7` | File changed since read → refuse, demand re-read (staleness) |
| exact match | `old_string` must match byte-for-byte **and be unique**, else fail |

Claude Code makes an ungrounded edit *structurally impossible*. It does not detect ungrounded edits
downstream. `src/utils/fileStateCache.ts` is the session-scoped read ledger these gates consult.

**Our gap:** all five planned tools (`search_corpus`, `open_doc`, `get_section`, `follow_reference`,
`read_guideline`) are *input*. There was no emit path, so a hallucinated finding would always be created
and only maybe caught by the Phase 5 verifier.

→ **`TOOLS-03`**: `emit_finding` is the only way a finding can exist; its `validateInput` re-resolves the
cited span and rejects when the quote is not byte-identical, not unique, was never retrieved this session,
or carries no rule citation. Phase 2 criterion 5 requires a test proving a fabricated quote **cannot be
emitted**. Promoted to the roadmap's third governing law.

## 2. Progressive disclosure — enumerable, not just searchable

`src/skills/loadSkillsDir.ts:98` — *"full content is only loaded on invocation"*; the always-present index
carries only `name`, `description`, `whenToUse`. Same pattern in `ToolSearchTool`, which defers entire tool
*schemas* until requested.

**Why this matters more to us than to them:** our worst failure family is `absence_of_evidence` at **0/11**.
Semantic retrieval over a submission cannot surface a requirement the submission never mentions. You cannot
retrieve your way to "this is missing." A pure vector+BM25 rulebook structurally cannot fix 0/11.

→ **`RULES-05`**: a compact **requirement index** (citation + one-line applicability trigger) the agent can
cheaply *enumerate*, with full rule text fetched on demand.

## 3. Compaction sheds evidence, never reasoning

`src/services/compact/microCompact.ts:41` — `COMPACTABLE_TOOLS` is an allowlist of *result-producing* tools
(Read, Grep, Glob, Bash, WebFetch…). Only **tool results** are cleared, replaced with
`[Old tool result content cleared]`; the N most recent are kept. Assistant reasoning is never touched.

This is *why* a finding provable in small context survives a large-corpus run: the model keeps what it
concluded after the bulk evidence is shed. → **`COST-03`**.

## 4. Prompt-cache stability is a hard engineering invariant

Two concrete mechanisms, both load-bearing:

- `src/tools/AgentTool/prompt.ts:56` — the agent list was **moved out of the tool description** into an
  attachment message. A dynamic description busts the whole tool-schema cache: measured at **~10.2% of
  fleet cache-creation tokens.**
- `src/utils/toolResultStorage.ts:390` — `ContentReplacementState` freezes every compaction decision by
  `tool_use_id`. Once a result's fate is decided it never changes; replacements are re-applied
  byte-identically from a cached string (zero I/O, cannot fail). Decisions are persisted to the transcript
  so they survive resume.

→ **`COST-01`** invariant + Phase 6 criterion 1c (byte-identity test across two runs over *different*
corpora). **This constraint must be honored from Phase 2**, even though it is measured in Phase 6 — bake the
corpus manifest or rule list into the system prompt while building tools and the caching lever cannot be
recovered without a rewrite.

## 5. Budgets stop on diminishing returns, not only at the ceiling

`src/query/tokenBudget.ts:59` — continue while under 90% of budget, but stop early when
`continuationCount >= 3` and successive deltas are `< 500` tokens. On continue it injects a nudge message
rather than silently looping. → **`AGENT-03`** amended.

## 6. Overflow throws; it does not truncate

`src/tools/FileReadTool/limits.ts` header comment records a real A/B: truncating over-cap reads instead of
throwing **dropped tool error rate but raised mean tokens**, and was reverted (#21841, Mar 2026). An error
tool-result is ~100 bytes; a truncated result is ~25k tokens at the cap.

Caps: `maxTokens` 25,000 (checked post-read on actual output), `maxSizeBytes` 256KB (checked pre-read on
total file size). Aggregate per-message tool-result budget: 200,000 chars
(`src/constants/toolLimits.ts`), which stops N parallel tools each hitting their individual cap.
Results over 50,000 chars persist to disk; the model gets a 2KB preview plus the path. → **`TOOLS-04`**.

## 7. Read deduplication

`FILE_UNCHANGED_STUB` (`src/tools/FileReadTool/prompt.ts`) — *"File unchanged since last read. The content
from the earlier Read tool_result in this conversation is still current — refer to that instead of
re-reading."* Lives **inside the read tool**, not in a cost module. → **`COST-04`, placed in Phase 2** for
that reason: a reviewer re-opens the same spec table many times per run, and every Phase 3–5 eval iteration
pays for its absence.

## 8. Sub-agent discipline (prompt-craft, for Phase 4)

From `src/tools/AgentTool/prompt.ts`. Copy these into the fan-out design:

- **"Never delegate understanding."** Do not write "based on your findings, fix the bug" — that pushes
  synthesis onto the sub-agent. The orchestrator must synthesize and hand over specifics.
- **"Don't peek."** Reading a sub-agent's transcript mid-flight pulls its tool noise into the orchestrator's
  context and defeats the isolation you paid for.
- **"Don't race."** Never fabricate or predict a pending sub-agent's results.
- **Fork vs fresh:** a fork inherits parent context *and shares its prompt cache* (so never override the
  model on a fork — a different model cannot reuse the cache); a fresh agent starts blank and needs a full
  briefing. Terse command-style prompts to fresh agents produce shallow work.

---

## Open question for Phase 1 planning (not yet decided)

**Claude Code does not pre-index the codebase.** It navigates live with Glob/Grep/Read — pure just-in-time
retrieval, no upfront corpus build. Our Phase 1 builds a corpus index + coverage manifest upfront. That is a
real divergence and should be a conscious decision, not a default.

The likely resolution — to be confirmed during Phase 1 discussion, not assumed here:

- **Enumeration + classification must be eager and complete.** `DETECT-05` requires a coverage manifest so
  that "no deficiencies found" is meaningful, and `INGEST-01` forbids a document cap. You cannot assert
  completeness over a set you never enumerated. Claude Code has no equivalent guarantee to make, which is
  why it can skip this.
- **Full parsing should probably stay lazy.** Parsing every page of every document upfront is the
  context-stuffing anti-pattern in a different costume, and it is explicitly out of scope
  (REQUIREMENTS.md "Full-corpus context stuffing").

So: eager cheap pass (walk → classify → outline → manifest), lazy expensive pass (parse section text on
`get_section`). Phase 1 should decide where exactly that line sits, and the eval harness should measure it.

---

# Second pass (2026-07-31) — the loop layers the first pass never read

First pass read the tool/grounding/compaction contracts and flagged `query.ts`, `QueryEngine.ts`,
and the sub-agent layer as **unread**. This pass read them (query.ts main loop in full,
toolOrchestration/toolExecution, runAgent.ts, autoCompact triggers, todo-reminder mechanism) —
timed for Phase 3 (drive loop) and Phase 4 (fan-out), which build exactly these layers.

## Confirmations (our derived design independently matches the real loop)

- **Loop shape:** `while(true)`; one API call per iteration; continue iff the assistant turn
  contains tool_use blocks; a plain-text turn = done (then stop-hooks, then completion).
  `maxTurns` is a hard cap. Matches Phase 3's planned loop exactly.
- **Malformed tool input → the model sees** `<tool_use_error>InputValidationError: …</tool_use_error>`
  as a normal `is_error` tool_result and the loop continues — the exact shape of our typed
  self-correcting `ToolRejected`. Independent convergence, not imitation.
- **Sub-agent = the same loop re-entered** with its own context, own read-state, own maxTurns;
  its final text is the return value; per-message sidechain transcript. Matches Phase 4's plan.
  Notably each sub-agent gets an **isolated readFileState** — the analog of our per-run
  RetrievalLedger (02-01 already chose per-run; confirmed correct).

## New lessons (4, all Phase-3-load-bearing)

**L1 — Transcript repair on interruption (`yieldMissingToolResultBlocks`).** If the loop stops
after tool_use blocks were emitted but before their results (abort, error, budget), CC
synthesizes an error tool_result for every dangling tool_use so the conversation stays
API-valid. OpenAI-compatible endpoints have the same constraint (400 on dangling tool_calls).
**Phase 3 requirement: a budget/breaker stop that fires mid-tool-batch MUST synthesize results
for dangling calls before the final grounded-partial report call** — or the report call itself 400s.

**L2 — Recovery ladder with never-twice guards.** Every failure path has an escalating retry, a
retry-count cap, and an explicit do-not-re-enter flag threaded through loop state
(`hasAttemptedReactiveCompact` survives across stop-hook retries; stop hooks NEVER run on API
errors — error→hook→retry→error is a named death spiral). **Phase 3 requirement: provider
errors (Databricks 5xx/timeouts) get bounded backoff-retry DISTINCT from the budget stop;
each recovery is attempted at most once per state; a run that dies on provider error after
retries = a FAILING run per D-GO2(i), never silently re-rolled.**

**L3 — Multi-tool-call turns are the norm, not the edge case.** CC partitions each assistant
turn's tool_use blocks: concurrency-safe (read-only) batches run parallel (cap 10), unsafe
serial, order preserved; malformed input → conservative serial. **Phase 3 requirement: the loop
must answer EVERY tool_call in an assistant turn before the next API call (models emit parallel
calls). Spike may execute serially (simpler; deterministic telemetry ordering) — but the
read-only/write partition is pre-decided for later: 5 nav tools concurrency-safe,
emit_finding serial.**

**L4 — Long-loop discipline via periodic code-injected reminders.** CC injects a `todo_reminder`
attachment when N turns pass without task-state updates — code decides, not the model. **Our
analog for Phase 3: every N turns, inject a code-computed COVERAGE reminder (which applicable
requirements are addressed / unaddressed so far, from the ledger + emitted findings) as a
message attachment.** Cheap, targets exactly the 30-turn drift risk on weak models, and honors
COST-01 (dynamic content in messages, never in the system prompt).

Also noted for Phase 6: autoCompact triggers at context-window minus reserved-output-headroom
(p99.99 of summary size), warning threshold 20k earlier — anchor compaction numbers to real
window/output sizes, not intuition.

## Verdict

Direction CONFIRMED at the loop layer. No architectural change required anywhere in Phases 3–6.
The four lessons are additive requirements inside Phase 3's already-planned areas (loop
architecture + budgets), arriving before planning locks — exactly when they're free to adopt.
