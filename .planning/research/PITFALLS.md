# Pitfalls Research

**Domain:** Agentic FDA/ICH compliance reviewer over arbitrary PDF+DOCX submission corpora (model-driven loop + tools + retrieval + grounded adversarial verification)
**Researched:** 2026-07-30
**Confidence:** HIGH — most pitfalls are corroborated by this project's *own measured runs* (`docs/eval/MEASUREMENT.md`), the existing code gates (`verify.py`, `challenge.py`, `summarise.py`), current FDA enforcement, and the research literature.

> **Read this first.** This is a SUBSEQUENT milestone on a brownfield system that has *already measured itself*. Run 3 on the estradiol method-validation PDF scored **precision 16–24 %, recall 7 % (2 of 28 real deficiencies)**. Every fix that session was a *filter* that removed wrong findings; **none moved recall**. The pitfalls below are ordered so the #1 threat to the core value ("all faults, and only faults") comes first. Treat the numbered pitfalls as gating; the tables at the end are supporting detail.

---

## Critical Pitfalls

### Pitfall 1: Precision theater — every improvement is a filter, recall never moves

**What goes wrong:**
The team ships filter after filter (concession gate, arithmetic refutation, dedup) and watches precision climb from 2.4 % → 24 %, declaring progress. Recall stays pinned at 7 %. The product's core promise is *both* precision and recall ("all faults, and only faults that actually exist"), and a corpus reviewer that finds 2 of 28 real deficiencies is not a reviewer — it is a spellchecker with good manners. Filters can only ever *remove* findings; a 90 %-precision / 7 %-recall system passes an audit demo and fails the mission.

**Why it happens:**
Precision failures are loud and embarrassing (56 false "blabber" findings on screen), so they get fixed first. Recall failures are *invisible* — you cannot see the 26 deficiencies the system never mentioned without an independent ground-truth set. The measured miss families (`MEASUREMENT.md`) need reasoning the pipeline has *no mechanism for*: assertion-vs-evidence sweeps ("the report says it analysed X — is X anywhere?"), derivation plausibility ("LOQ = exactly 2.00×LOD for all four analytes"), summary/total integrity, statistical-outlier checks, regulatory-premise review. Depth of attention is not the constraint; the *kinds of check* are. The whole reason to become an agent (tools + exploration + reference retrieval) is to add those missing capabilities — if the milestone only hardens filters, it rebuilds the same 7 %-recall ceiling with a nicer loop.

**How to avoid:**
- Make **recall the primary success metric of this milestone**, tracked per *failure family* (absence-of-evidence, derivation-plausibility, cross-reference integrity, regulatory-framing), not a single number. A filter that raises precision without moving family-level recall is *not* progress this milestone.
- Add the *missing check kinds* as first-class capabilities: an **assertion-vs-evidence pass** (largest single missed family, ~6 findings), a **summary/total integrity oracle** (`stated max == max(rows)`, `total ≥ max(component)`, `total == sum(components)` — deterministic, generalizes, catches 2 CERTAIN findings), and a **document-control / regulatory-premise reviewer** (the USP <1226>-vs-DMF mis-framing was arguably the single most consequential deficiency and was missed entirely).
- Enforce the existing **"downgrade-never-drop" invariant** (`schemas/faults.py`): recall lives in the ADVISORY tier; nothing is silently suppressed except deterministic oracle-disproof.
- Gate every filter change behind "**zero true positives lost**" measured on ground truth (this is already how the concession gate was validated — keep it mandatory).

**Warning signs:**
- Session summaries report precision deltas but flat or absent recall numbers.
- The fix list is all `verify.py`/`challenge.py` filters, no new *generative* capability.
- The system emits N restatements of one real error (run 3: **six** findings about Table 20's Max) while missing an impossibility in a table it also reviewed (Table 19 total < largest component).
- "We improved accuracy" with no per-failure-family breakdown.

**Phase to address:**
Eval harness must exist *before* the agentic loop is built (see Pitfall 11), then every capability phase (assertion-sweep, integrity oracles, agentic reasoning) is gated on recall-by-family. This is the spine of the whole milestone.

---

### Pitfall 2: Ungrounded findings & citation drift — the quote is not in the source

**What goes wrong:**
A finding cites a verbatim "quote" or a table cell that does not appear in the document — the model paraphrased, normalized a number ("0.15%" → "0.15 %" → "0.150"), stitched two cells, or invented the passage outright. In a compliance tool this is fatal: the entire value proposition is "prove it with the exact text," and a single hallucinated citation surfaced to an FDA analyst destroys trust in the whole run. At corpus scale the model also drifts citations *across documents* — attributing a real quote to the wrong file/section.

**Why it happens:**
LLMs generate citations as plausible text, not as retrieval operations. Citation hallucination is rising sharply in the wild (146k+ fabricated references catalogued in 2025 alone). Agentic loops make it worse: the model "remembers" a passage from 20 tool-calls ago and reconstructs it from memory rather than re-opening it, so the quote is *near* the truth but not verbatim — the hardest kind to catch by eye.

**How to avoid:**
- **Deterministic quoting, enforced in code, not prompt.** A finding's `evidence` must substring-match the source after normalization — the pattern already in `verify.py::_anchored` (`len(n) >= 4 and n in corpus`) and `challenge.py::_cell_in_corpus` (short numeric cells). Extend this from single-doc to **corpus-wide**: the anchor must resolve to a specific `(doc_id, section_index, char_span)` the agent actually retrieved, and re-opening that span must reproduce the quote byte-for-byte.
- Never let the model emit the citation *text* freely — have tools return `(span_id, verbatim_text)` and require findings to reference a `span_id`, so the quote is *selected*, not *authored* (the "deterministic quoting" pattern for healthcare LLMs).
- Any finding whose anchor fails to resolve is **downgraded to MODEL_JUDGMENT / ADVISORY**, never shown as verified (existing behavior — preserve it corpus-wide).

**Warning signs:**
- `evidence` field fails the substring check but the finding still ships as QUOTE_ANCHORED.
- Quotes contain re-typeset numbers, "..." elisions, or merged clauses.
- The cited page/section exists but the sentence does not (drift), especially for findings the agent raised late in a long loop.
- Rising rate of `MODEL_JUDGMENT` re-classification in logs after adding the corpus anchor check — good (it's catching drift), but investigate the generators.

**Phase to address:**
Grounding & adversarial-verification phase, with the corpus-anchor primitive built in the retrieval/tools phase (tools must return span IDs, not free text).

---

### Pitfall 3: Over-trusting the model on the compliance call — regulatory liability

**What goes wrong:**
The system renders a confident "COMPLIANT / no deficiency" verdict, or silently *omits* a required check, and a human acts on it. In April 2026 the FDA issued its **first warning letter for AI over-reliance** (Purolea Cosmetics Lab): staff didn't know a process-validation requirement existed *because the AI agent they relied on never flagged it*. FDA's position is now enforcement, not guidance — "over-reliance on AI, treating it as a substitute for human expert judgment, regulatory knowledge, or quality oversight, is not acceptable, and will be treated as a CGMP violation," and the Quality Unit's accountability **cannot be delegated to an algorithm.** A false-negative from this tool is not a bug ticket; it is the exact failure mode the FDA just penalized.

**Why it happens:**
Absence-of-evidence is the hardest class for an LLM (it's easier to critique text that exists than to notice text that *should* exist and doesn't) — and it was this project's single largest missed family (~6 of 28). A reviewer that only reasons over what's in front of it will confidently conclude "equivalency demonstrated" while never asking "where is the control-sample chromatogram the report says it ran?" Teams then present the clean output as an answer rather than a *lead for a human*.

**How to avoid:**
- **Frame every output as advisory, human-in-the-loop, and non-exhaustive** — in the UI, the data model, and any report. Never emit an unqualified "compliant" verdict; emit "no deficiency *found* by this pass" with explicit coverage (which sections/checks ran, which did not). This is already partly enforced: `verify.py` drops self-negating findings, but the *system-level* "all clear" claim is the dangerous one.
- Build the **assertion-vs-evidence / required-elements checklist** as a positive obligation: enumerate what a compliant submission *must contain* (from the ICH/FDA reference corpus, not hardcoded), then report every required element with no supporting data as a deficiency. This directly attacks the false-negative liability.
- **Log coverage gaps as first-class output.** "I could not locate the governing SOP / the accuracy study / the water-content determination" is a finding, not a silence.
- Keep the human in the loop by design (already Out-of-Scope to auto-file). Make the analyst's verification action explicit and recorded.

**Warning signs:**
- Output ever reads "the submission is compliant" without a coverage manifest.
- No findings of type "required element absent" — only critiques of present text.
- Analysts start rubber-stamping runs (automation complacency) — measure their override rate; if it trends to zero, they've stopped reviewing.
- A missed deficiency in eval is an absence-of-evidence case (highest liability, hardest to catch).

**Phase to address:**
Cross-cutting: required-elements/assertion-sweep capability phase for the false-negative mechanism; UX/reporting phase for the advisory framing and coverage manifest. Bake the "non-exhaustive, human-must-review" contract in from the first agentic phase.

---

### Pitfall 4: Treating prompt instructions as enforcement

**What goes wrong:**
The team writes "if your detail concedes compliance, DELETE the finding" or "N/A cells are usually intentional" into a prompt and assumes the rule holds. It doesn't. This repo *measured it twice*: the "N/A" instruction was ignored 15× in run 1; the self-suppression instruction was ignored 18× in run 2 — the model wrote *"This is not a finding."* into the detail and **shipped the finding anyway.** Every reliable improvement that session came from a **code gate** (`verify.py`, `challenge.py`), never a prompt. An agentic loop multiplies the surface area for this delusion: budget rules, tool-use discipline, grounding rules, stop conditions — all silently violated if they live only in the system prompt.

**Why it happens:**
Prompts feel like control and are cheap to write. Under load (long context, many tool results, temperature > 0, structured-output pressure) the model reverts to its priors and ignores soft constraints. Developers conflate "I told it to" with "it will."

**How to avoid:**
- **Anything that matters is enforced in code**, downstream of the model: grounding (substring anchor), arithmetic (recompute cells, don't trust the model's verdict — `challenge.py::_arithmetic_refutation`), budgets (hard token/step ceilings, not "please stop"), coverage (deterministic `_ensure_coverage` in `planning.py`), dedup, tier stamping. The model *proposes*; code *disposes*.
- For the new agentic loop specifically: **tool-call limits, per-run token budgets, and stop conditions are runtime guards**, not instructions. A circuit breaker that trips after N repeated/again-failing tool calls, enforced by the orchestrator.
- Treat every prompt rule as advisory and ask "what happens when the model ignores this?" If the answer is "bad output ships," build the gate.

**Warning signs:**
- A reliability fix is a prompt edit with no code change and no measured before/after.
- Logs show the model violating an explicit instruction (concession text in shipped findings; tool calls past the "budget").
- "We told it not to" appears in a design doc as a mitigation.

**Phase to address:**
Architectural principle for *every* phase. Make "enforced in code vs. asked in prompt" an explicit column in each phase's design. The agentic-loop phase must ship its budget/stop/circuit-breaker guards as code on day one.

---

### Pitfall 5: Runaway agent loops and cost/latency blowup at corpus scale

**What goes wrong:**
The single-document detector was a bounded fan-out (finite workers, one `structured_call` each). The new **model-driven loop over an uncapped corpus** can retry-retry-retry, re-open the same document, chase circular cross-references, or fan sub-agents over hundreds of files — turning a $2 review into a $2,000–$8,000 incident nobody notices until finance emails. Agent paths cost ~3.2× a linear approach at 5 steps and >100× at 200 steps; the dominant driver is *context accumulation*, which compounds exactly when the corpus is large (the target use case). Latency blows up in parallel — the estradiol single doc already took 1171 s before concurrency fixes brought it to 320 s; a 500-document corpus with an unbounded loop is unshippable.

**Why it happens:**
The loop's stopping condition is model judgment ("decide when it is done"), and models under-stop (fear of missing something → recall anxiety) or thrash on ambiguous evidence. "No cap on document count or nesting depth" (a core requirement) meets an unbudgeted loop and the cost is unbounded by construction.

**How to avoid:**
- **Hard, code-enforced ceilings per run and per sub-agent:** max tool calls, max tokens (input+output), max wall-clock, max documents deeply-reasoned. Graduated: warn at 80 %, throttle at 90 %, halt at 100 %. These are the Claude-Code cost lessons the PROJECT.md already cites — implement them as runtime guards, not hopes.
- **Circuit breaker** on repeated/failing tool calls (same doc opened N times, same failing call) — trip and force the loop to conclude with what it has.
- **Cheap-model triage before expensive reasoning:** classify/skim with a small model, escalate only documents that show signal — so cost scales with *docs that need deep reasoning*, not raw corpus size (explicit project goal).
- **Prompt caching** (one stable cached prefix) + **escalating context compaction** to bound the working set (see Pitfall 8) + **isolated sub-agents** so exploration cost is paid once and returns distilled findings.
- **Per-run budget dashboards + kill switch** in the job store; every run records tokens/cost/steps for post-mortem.

**Warning signs:**
- Token/step count per document has a long right tail; a few docs dominate spend.
- The loop's step-count distribution has no hard ceiling in code.
- Re-opening the same span repeatedly in one run (thrash).
- Runtime scales super-linearly with corpus size in load tests.

**Phase to address:**
Agentic-loop & cost-controls phase — budgets, circuit breaker, and cheap triage are *acceptance criteria for that phase*, not follow-ups. Load-test against a synthetic large corpus before declaring it done.

---

### Pitfall 6: Retrieval misses = silent recall gaps (the corpus is bigger than the window)

**What goes wrong:**
Because the reviewer reasons over a corpus far larger than the context window, a fault only exists to the system if retrieval surfaces the right passage. If `search_corpus` misses the section that contains the violation — or retrieves the right *document* but the wrong *chunk* — the deficiency is never seen and never reported. This is invisible recall loss: nothing errors, the finding simply never exists. Long-document regulatory QA research shows a frequent failure is "correct document retrieved, but the answer-bearing page/chunk missed, so the generator extrapolates from incomplete context." Cross-document consistency checks (spec limit in doc A vs. method in doc B) are *entirely* gated on retrieval linking the two — a miss means the contradiction is undetectable.

**Why it happens:**
Regulatory submissions are structured artifacts, not flat prose: numbers get their meaning from distant headers, "see Section 3.2.S.4.1" references live in other files, and a single embedding query rarely co-locates a spec limit with the batch result that violates it. Semantic search alone under-recalls exact identifiers (batch numbers, notebook citations like `8133/...56` vs. `...46`, RRT values). Naive top-k retrieval optimizes for the *most similar* chunk, not *coverage* of everything that must be checked.

**How to avoid:**
- **Hybrid retrieval** (dense embeddings + BM25/exact-match) so identifiers, batch numbers, and criteria strings are found literally, not just semantically.
- **Two-stage retrieval:** broad recall, then cross-encoder re-rank — bias stage 1 toward recall (over-fetch), let re-rank handle precision.
- **Follow references as a first-class tool** (`follow_reference`): resolve "see Section X" and hyperlinks into a reference graph, so cross-document faults become reachable instead of depending on a lucky embedding hit.
- **Don't rely on retrieval alone for coverage.** Keep the deterministic **`_ensure_coverage` invariant** conceptually at corpus scale: every document/section is *seen* by at least one open-review pass, not only the sections retrieval happened to rank highly. Retrieval is for *depth and linking*; a mechanical sweep guarantees *breadth*.
- Measure retrieval as **recall@k against known answer spans** in the eval set, separately from end-to-end recall, so you can tell a retrieval miss from a reasoning miss.

**Warning signs:**
- End-to-end recall is low but the model reasons well on what it's given (→ retrieval, not reasoning, is the bottleneck).
- Cross-document findings are near zero.
- Findings cluster in the first/most-obvious sections; deep or oddly-named sections never produce findings.
- Exact-identifier queries (a batch number, a table label) fail to retrieve their home document.

**Phase to address:**
Retrieval & reference-corpus phase. Ship recall@k measurement with it. The corpus-navigation tools (`search_corpus`, `follow_reference`) are where breadth-vs-depth coverage is decided.

---

### Pitfall 7: Table & document parsing failures — the evidence is corrupted before reasoning starts

**What goes wrong:**
Both of this system's *only* two true-positive families are "compare a number against a limit / against another cell" — pure table-cell arithmetic. If table extraction mangles a merged cell, drops a multi-page continuation, mis-associates a header, or an OCR pass corrupts a digit, then even the oracle-shaped wins vanish and the anchor check will (correctly) reject the finding as ungrounded — you lose the finding *and* can't tell why. Adding a **new DOCX parse path** (converging on the same structured model as the PyMuPDF/OCR PDF path) doubles the surface: Word tables, tracked changes, embedded objects, and footnotes parse differently and can silently diverge from the PDF model the rest of the pipeline assumes.

**Why it happens:**
A table is a 2-D structure forced into a 1-D representation; flattening severs row-column relationships and "turns tables into word soup." Merged cells break spatial logic, borderless tables (common in CMC/financial forms) remove the only cue grid parsers use, multi-page tables need continuation logic, and scanned pages add OCR skew/noise that cascades into structure errors. A single-pass LLM-OCR approach scored <40 % on complex documents and introduces *silent* corruption (missing totals, lost merged cells) — worst case, because it looks clean.

**How to avoid:**
- **Layout-aware extraction, not LLM-OCR guessing** for tables; preserve `(row, col, header)` structure into the document model (the existing `src/parse/layout.py` + geometry + section splitter is the right shape — extend, don't replace with a monolithic vision call).
- **Carry tables verbatim, never through the LLM** — already the rule in `summarise.py` (tables carried by code, prose-only condensation) and `sandwich.py`. Preserve this invariant on the DOCX path.
- **Parse-fidelity checks as gates:** row/column counts stable across a page break, totals reconcilable, no all-empty extracted table where the page clearly has one. Emit a typed `ParseFailed` (existing pattern) rather than passing corrupt tables downstream.
- **Converge DOCX to the identical structured model** and run the *same* parse-fidelity test suite against both paths; add DOCX fixtures with merged cells, tracked changes, and multi-page tables.
- Treat **scanned/low-quality PDFs** as a distinct quality tier — flag low OCR confidence so downstream findings on those pages carry appropriate caution.

**Warning signs:**
- Findings that should be provable fail the verbatim anchor check (the number in the model doesn't match the number on the page → parse corruption, not a hallucination).
- Table row/column counts differ between the two halves of a multi-page table.
- DOCX and PDF versions of the same content produce different structured models.
- OCR'd pages produce far fewer findings than digital pages of similar content.

**Phase to address:**
Corpus-ingestion & parsing phase (DOCX path + parse-fidelity gates). This is foundational — everything downstream inherits its errors, so parse fidelity is an acceptance criterion for that phase, tested on adversarial table fixtures.

---

### Pitfall 8: Context overflow & compaction that silently drops the deciding evidence

**What goes wrong:**
To reason over a large corpus the loop must compact/summarize its working set — and compaction is where a critical number, entity, or cross-reference quietly disappears, making a real fault invisible. This system already learned it at single-doc scale: a summariser that dropped a number made a cross-section (intersection) fault invisible to a neighbour worker, which is why `summarise.py` has a **fidelity guard** that reverts to full prose whenever a number *or named entity* vanished. At corpus scale the same failure returns as (a) **lost-in-the-middle**: long-context models miss information placed mid-window (>30 % accuracy drop vs. start/end positions), and (b) **context rot**: accumulated tool results dilute attention so the model stops "seeing" evidence it technically holds. Compaction of the agent's memory (KV/summary) trades tokens for information loss precisely on the facts that decide a deficiency.

**Why it happens:**
Compression is necessary (you can't hold 500 documents in context) but lossy, and the loss is not random — summarizers drop specifics (a single value, a batch number, a "see §X") in favor of gist, and those specifics are exactly what compliance faults hinge on. Positional bias (RoPE decay, attention dilution) means even *retained* evidence buried mid-context is under-weighted.

**How to avoid:**
- **Extend the `summarise.py` fidelity-guard discipline to the agent's working memory:** any compaction that would drop a number, named entity, criterion, or reference either keeps it verbatim or spills it to a *retrievable* store the agent can re-open — never a summary that silently omits it.
- **Never compact tables through the model** (already the rule) — keep them in a structured store addressed by ID.
- **Position the highest-value evidence at the start/end** of any assembled context; put re-rank winners at the extremes, not the middle.
- **Re-open, don't recall.** When the agent makes a finding, require it to *re-fetch* the anchor span fresh (cheap, exact) rather than cite from compacted memory — this simultaneously kills citation drift (Pitfall 2) and compaction loss.
- Bound the working set with **escalating compaction** (Claude-Code pattern) but log what was compacted so a lost-evidence miss is diagnosable.

**Warning signs:**
- A finding present with small context disappears when the same doc is reviewed inside a large corpus run (compaction/position loss).
- The `lossy=True` fallback rate spikes on the DOCX path or on dense tables.
- Findings degrade for sections that happen to land mid-context in the assembled window.
- The agent references a value that *was* in its history but is no longer in the compacted state.

**Phase to address:**
Retrieval + context-compaction phase. The fidelity guard and re-open-don't-recall rules are acceptance criteria there; carry the single-doc guard forward rather than reinventing it.

---

### Pitfall 9: The adversarial verifier is gamed — self-verification & correlated errors

**What goes wrong:**
The design leans on an adversarial verifier that must "refute-or-confirm each candidate against the source." If that verifier is the *same model family* judging its own (or a sibling's) output, it exhibits self-enhancement bias and sycophancy: it over-accepts, rubber-stamps invented evidence, and its errors are *correlated* with the generator's — so it fails to catch exactly the mistakes the generator makes. Research is blunt: full self-critique setups can *degrade* output quality, and iterative self-correction without sound external verification consistently makes things worse. A verifier that "confirms" a finding by citing a passage that isn't in the document has added confident noise, not safety.

**Why it happens:**
Teams add a "verifier agent" and assume adversariality is free. But a model asked to critique its own reasoning shares its blind spots (correlated error renders self-evaluation non-identifying), and RLHF'd models are sycophantic toward plausible-looking claims. Confirmation is cheaper than refutation, so an under-constrained verifier drifts toward agreeing.

**How to avoid:**
- **Ground the verifier in code, not vibes** — the existing `challenge.py` already does the right thing and must be preserved/extended: a refutation only counts when it (a) **quotes a passage verbatim-anchored in the document**, or (b) is a **code recomputation** over the two cited cells (`_arithmetic_refutation`), with *both cells required to appear verbatim* so an invented number cannot clear a real fault. The model reports cells; **code decides**.
- **Make the verifier's job asymmetric and evidence-forced:** it must produce a *grounded* refutation to drop a finding; an ungrounded challenge only lowers confidence, never vetoes (existing gate semantics). This resists the "confirm everything" drift.
- **Prefer cross-family / different-model verification** where feasible (cross-family verifiers beat self-verification), or at minimum a different prompt persona + temperature 0 + no access to the generator's reasoning, only the claim + source.
- **Never let the verifier confirm using evidence it authored** — confirmation evidence must anchor in the corpus, same rule as findings.

**Warning signs:**
- Verifier "confirmations" whose cited evidence fails the anchor check.
- Refutation rate near 0 % or near 100 % (either it never refutes → sycophantic, or it nukes everything → miscalibrated).
- Adding verification iterations lowers eval F1 (self-correction degradation) — measure it.
- Verifier and generator miss the *same* eval items (correlated error).

**Phase to address:**
Grounding & adversarial-verification phase. Keep the code-grounded refutation gate as the non-negotiable core; measure verifier precision/recall independently on eval.

---

### Pitfall 10: Overfitting to document structure, folder names, or the eval document

**What goes wrong:**
The system latches onto superficial cues — folder names ("M3", "3.2.S.4.1"), a fixed module layout, the section ordering of the one document it was tuned on — and silently fails when a real submission names folders arbitrarily, nests differently, or splits content across files. Shortcut learning is well-documented: LLMs exploit spurious correlations and non-generalizing patterns, with large accuracy drops on out-of-distribution inputs (e.g., 52 % drop on shortcut-laden variants). The core requirement is *generalize to any directory*; hardcoding structure is the fastest way to a demo that works on `Sample Data/` and nowhere else.

**Why it happens:**
The team has one richly-understood test document and a 500-file sample that lives inside a single module's subfolders. It is enormously tempting to encode "impurities live under 3.2.S.3.2" or to route by folder name because it *works right now*. PROJECT.md explicitly puts "hardcoding M3/3.2.S.4.1 paths" and "overfitting to folder names" in Out-of-Scope — because the pull toward it is strong and the failure is invisible until a differently-organized corpus arrives.

**How to avoid:**
- **Classify documents by content, never by path.** A CMC drug-substance spec is identified by what it contains, not by living in a folder called "S". Folder names may be *hints* fed as weak evidence, never *controls* that gate logic.
- **No hardcoded CTD section numbers as answer-keys.** Guidelines are *retrievable reference*, consulted like a reviewer reading the rulebook — a decision already made in PROJECT.md; enforce it (don't let ICH section numbers creep into code as routing keys).
- **Test on held-out corpora with different organization:** renamed folders, different nesting, mixed PDF/DOCX, content split across files. If renaming a folder changes the findings, you've overfit.
- Keep the **planner/open-reviewer split** (`workers.py`): the open-review pass sweeps *every* section mechanically, independent of the planner's structural assumptions, so a bad structural guess can't create a blind spot. Preserve this at corpus scale.

**Warning signs:**
- Any `if "M3" in path` / section-number literal in routing or detection code.
- Findings change when folders are renamed or files are moved (structure-dependence test).
- The system works on `Sample Data/` and degrades sharply on any re-organized copy.
- Precision/recall drop steeply on a document type or layout not represented in the tuning doc (OOD cliff).

**Phase to address:**
Corpus-ingestion phase (content-driven classification) and every reasoning phase (no structural hardcoding). Add a "rename-the-folders" regression test as a standing generalization guard.

---

### Pitfall 11: Weak evals — measuring on n=1, no ground truth, or a gameable target

**What goes wrong:**
The team declares "reliable" without measuring, or measures on a **single document** and generalizes. The existing (excellent) `MEASUREMENT.md` is built on *one* estradiol method-validation PDF with a 28-item hand-built reference. That is the right *method* but n=1 *coverage*: a system tuned until it scores well on one document has learned that document, not the domain (Goodhart: once a benchmark becomes the optimization target, it stops measuring capability). Worse failure: shipping the agentic milestone with **no** ground-truth precision/recall at all, so recall regressions (Pitfall 1) are invisible and every "improvement" is faith-based.

**Why it happens:**
Ground truth is expensive — the 28-item set took *four independent blind reviewers* verifying arithmetic and excluding intentional N/A. Building that for a diverse corpus is real work, so teams reuse the one set and quietly overfit to it, or skip evals under deadline and assert reliability from spot-checks (which are precision-biased — you notice wrong findings, never missing ones).

**How to avoid:**
- **Scaffold the eval harness FIRST**, before the agentic loop — it is the instrument that tells you whether the loop helps. Every capability change reports precision *and* recall-by-failure-family against ground truth (PROJECT.md already lists this; sequence it early).
- **Grow ground truth beyond one document:** multiple document types (specs, method validation, stability, impurities), multiple layouts, PDF *and* DOCX, and at least one *held-out* corpus never used during tuning. Keep the blind-multi-reviewer methodology — it's the strong part.
- **Separate metrics** so you can localize failure: retrieval recall@k (Pitfall 6), parse fidelity (Pitfall 7), grounding/anchor rate (Pitfall 2), verifier precision/recall (Pitfall 9), end-to-end P/R by family (Pitfall 1).
- **Guard against Goodhart:** rotate/hold out eval documents, use multiple corpora, and treat a metric that only moves on the tuning doc as suspect. If the LLM is also the judge, validate the judge against human labels first (LLM-as-judge has its own precision/recall to measure).
- **Every filter/gate change must report "true positives lost = 0"** on ground truth — already the discipline; make it a CI-style gate.

**Warning signs:**
- "Reliable"/"accurate" asserted with no P/R numbers, or numbers from a single document.
- Recall isn't reported (only precision / only qualitative spot-checks).
- Scores improve on the tuning doc but a fresh document regresses (overfit signal).
- No held-out corpus exists; the eval set == the tuning set.

**Phase to address:**
Eval-harness phase, sequenced **first** and run continuously as the gate on every other phase. This is the measurement backbone for the whole milestone (ties directly to Pitfall 1).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Route/detect by folder name or hardcoded CTD section numbers | Works instantly on `Sample Data/` | Total generalization failure on real corpora; violates the core requirement | **Never** as a control; only as a weak, overridable hint |
| Enforce a rule in the prompt instead of code | One-line "fix," no plumbing | Silently ignored under load (measured 15–18× here); false confidence | Only for genuinely soft stylistic preferences, never for grounding/budget/coverage |
| Ship precision filters, defer recall work | Demo looks clean fast | Rebuilds the 7 %-recall ceiling; product doesn't do its job | Only *within* a phase already gated on recall-by-family |
| One-document eval set | Fast to iterate | Overfits to that doc; recall regressions invisible on new inputs | Bootstrapping only; must expand before claiming generalization |
| LLM-OCR / single vision call for tables | Less parsing code | Silent cell corruption (<40 % on complex docs); breaks the anchor + oracle wins | Only for triage/classification, never for evidence tables |
| Unbounded agent stop condition ("model decides") | Simple loop | Runaway cost ($2k–8k incidents), latency blowup at scale | Never without hard code ceilings + circuit breaker |
| Verifier confirms from model-authored evidence | Easy to wire | Sycophantic rubber-stamp; correlated errors add confident noise | Never — confirmation evidence must anchor in corpus |
| Compact agent memory with a plain summary | Fits the window | Drops the deciding number/entity → invisible false negatives | Only with the fidelity-guard (verbatim-or-spill) discipline |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Databricks/OpenAI strict structured output | Assume schema always validates; leak raw text on failure | Keep the L1–L6 defense-in-depth (`structured.py`): truncation retry → json-repair → pydantic → moderator rescue → typed `ParseFailed`; never leak raw text |
| Model picker (Llama 3.3 70B / Qwen MoE) | Hardcode a "strong" model in a sub-stage (challenge/repair once hardcoded 70B) | Honor the analyst's model choice through the *entire* run, gate included (already fixed — keep it) |
| FAISS / Databricks Vector Search | Dense-only retrieval; assume top-k = coverage | Hybrid (dense + exact/BM25), over-fetch + re-rank, measure recall@k, don't equate similarity with coverage |
| Embedding backend (local bge vs. Databricks) | Silent dimension/model mismatch between index build and query | Pin embedding model + version to the index; fail loudly on mismatch |
| Precedent KB (500-row ANDA deficiencies) | Treat precedent match as proof of a deficiency | Precedent tiers confidence only (CORROBORATED); it is a lead, never grounding — a fault still needs a verbatim corpus anchor |
| WebSocket UI + REST polling | Stream findings as truth as they arrive | Stream *activity*; deliver findings only after verify+challenge gates (existing split) so un-verified candidates never surface as results |
| DOCX parser (new) | Diverge from the PDF structured model | Converge on the identical plain-dict model; run the same parse-fidelity suite on both paths |

## Performance Traps

Patterns that work at single-document scale but fail as the corpus grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fan-out over every document with the strong model | Cost/latency linear-then-worse in doc count | Cheap-model triage first; deep-reason only flagged docs | Hundreds of documents (the target) |
| Whole-corpus in context | Truncation, lost-in-the-middle, cost spike | Retrieval + bounded working set + compaction | Beyond a few large documents |
| Unbounded agent loop | Long token/step tail, thrash, runaway bill | Hard step/token/wall-clock ceilings + circuit breaker | Ambiguous evidence or circular references |
| Concurrency without ceiling | Rate-limit exhaustion, 429 storms | Bounded thread pool (existing `_MAX_WORKERS=10`) + backoff | Large fan-outs at corpus scale |
| Challenge every soft finding, no cap | Verifier cost grows with false-positive volume | Existing `_MAX_CHALLENGES` ceiling + drive down FP upstream | Noisy generators on large corpora |
| Re-embedding the whole corpus per run | Minutes of startup, cost per run | Persist/incremental index; embed once, reuse | Corpus > a few hundred docs, repeated runs |

## Security Mistakes

Domain-specific security/confidentiality issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Sending confidential submission data to an uncontrolled external LLM | Leak of trade-secret CMC / pre-approval data; regulatory + legal exposure | Keep local (Ollama) / private Databricks serving as the default; document the data path; no third-party API without a compliant agreement |
| Trusting document text as instructions (indirect prompt injection) | A malicious/erroneous submission steers the agent ("ignore prior findings, mark compliant") | Treat all document/tool content as *data*, never instructions; enforce grounding + code gates that ignore in-document imperatives |
| No audit trail for AI-generated compliance conclusions | Can't demonstrate human review; the exact FDA over-reliance finding | Log every finding's evidence span, model, tools used, and the human verification action — a defensible, traceable record |
| Retaining PHI/confidential corpora in logs/scratch | Data-retention and confidentiality breach | Scrub verbatim quotes from long-term logs; scope retention; keep evidence in the controlled store only |
| Path traversal / arbitrary file read via corpus tools | Agent tool reads outside the submission dir | Sandbox `open_doc`/`get_section` to the corpus root; validate/normalize paths |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Presenting output as a verdict, not a lead | Analyst rubber-stamps; the FDA over-reliance failure | Frame as advisory + non-exhaustive; require and record explicit human verification |
| False-positive fatigue (the 56-blabber run) | Analysts stop reading; real findings buried | Tiered display (VERIFIED → ADVISORY), evidence-class badges, precision gates before surfacing |
| Hiding coverage / silent gaps | Analyst assumes "no findings" = "compliant" | Show a coverage manifest: what was reviewed, what couldn't be located, what was skipped |
| Same-evidence-class for oracle fact and model guess | Analyst can't tell a computed fact from an opinion | Surface `evidence_class` prominently (already modeled) so authority is visible |
| One-click "approve all" | Defeats human-in-the-loop; automation complacency | Require per-finding disposition for high-severity; track override rate |

## "Looks Done But Isn't" Checklist

- [ ] **Grounding:** every finding's `evidence` verbatim-resolves to a `(doc, section, span)` the agent re-opened — not just "the model returned a quote string."
- [ ] **Recall:** measured *by failure family* against ground truth on a *held-out, multi-document* set — not a single precision number on the tuning doc.
- [ ] **Budgets:** hard token/step/wall-clock ceilings + circuit breaker are *code*, verified by a runaway load test — not prompt instructions.
- [ ] **Coverage:** every document/section is *seen* by a mechanical sweep, not only what retrieval ranked highly; renaming folders doesn't change findings.
- [ ] **Tables:** merged-cell / multi-page / borderless / DOCX fixtures parse with structure intact; parse-fidelity gates emit `ParseFailed` instead of corrupt cells.
- [ ] **Verifier:** refutations/confirmations anchor in the corpus; adding verification iterations does *not* lower eval F1.
- [ ] **Compaction:** a finding provable in small context is still found inside a large-corpus run (no lost-in-the-middle / summary-drop regression).
- [ ] **Advisory framing:** no unqualified "compliant" verdict anywhere; coverage manifest + human-verification record present.
- [ ] **Cross-document:** at least one contradiction-across-files case is caught end-to-end (proves retrieval + reference-following actually link documents).
- [ ] **Cost:** per-run token/cost/step recorded; a synthetic large corpus stays within budget.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Recall stuck / precision theater (1) | HIGH | Stop adding filters; add the missing *check kinds* (assertion-sweep, integrity oracles, regulatory-premise); re-baseline recall-by-family |
| Citation drift (2) | LOW–MEDIUM | Enforce corpus-wide substring anchor; downgrade unanchored to ADVISORY; switch generators to `span_id` selection not free-text quotes |
| Regulatory over-trust / false negative (3) | HIGH (external) | Add required-elements/coverage output; re-frame all outputs advisory; document human-review workflow; audit past runs for missed absences |
| Prompt-not-code rule (4) | LOW | Move the rule into a `verify.py`/orchestrator gate; add a before/after measurement |
| Runaway loop / cost (5) | MEDIUM | Add hard ceilings + circuit breaker + kill switch; add cheap-triage stage; load-test |
| Retrieval miss (6) | MEDIUM | Add hybrid + re-rank + reference-following; add mechanical coverage sweep; measure recall@k |
| Parse/table corruption (7) | MEDIUM–HIGH | Add parse-fidelity gates; adversarial table fixtures; converge DOCX to shared model; reprocess affected corpora |
| Compaction evidence loss (8) | MEDIUM | Apply fidelity-guard to agent memory; re-open-don't-recall for anchors; position evidence at context extremes |
| Verifier gamed (9) | MEDIUM | Require code-grounded refutation; cross-family/persona verifier; measure verifier P/R and iteration effect |
| Structural overfit (10) | MEDIUM–HIGH | Strip path/section literals; content-driven classification; rename-folders regression test |
| Weak eval (11) | HIGH (foundational) | Build eval harness first; expand ground truth to multi-doc + held-out; separate per-stage metrics |

## Pitfall-to-Phase Mapping

Phase names are *topical* (the roadmap isn't built yet) and map to PROJECT.md's Active requirements. Key ordering recommendation: **the eval harness is sequenced first and runs continuously as the gate on every later phase.**

| Pitfall | Prevention Phase (topical) | Verification |
|---------|----------------------------|--------------|
| 11 Weak evals | **Eval harness (FIRST, continuous)** | Multi-doc + held-out ground truth; per-stage metrics exist and run in CI |
| 1 Recall / precision theater | Every capability phase, gated on eval | Recall-by-failure-family improves; zero-TP-lost on every filter |
| 7 Parse/table failures | Corpus ingestion & parsing (incl. DOCX) | Adversarial table fixtures pass; DOCX == PDF model; `ParseFailed` on corruption |
| 10 Structural overfit | Corpus ingestion + all reasoning phases | Rename-folders regression test; no path/section literals in code |
| 6 Retrieval misses | Retrieval & reference corpus | recall@k on known spans; cross-document case caught; coverage sweep present |
| 2 Citation drift | Retrieval (span-ID tools) + Grounding | Anchor resolves to `(doc,section,span)`; unanchored → ADVISORY |
| 8 Compaction loss | Retrieval + context compaction | Small-context finding survives large-corpus run; fidelity guard on memory |
| 5 Runaway loop / cost | Agentic loop & cost controls | Load test stays in budget; ceilings + circuit breaker are code |
| 4 Prompt≠enforcement | Architectural, every phase | Each safety rule shown to be a code gate with before/after numbers |
| 9 Verifier gamed | Grounding & adversarial verification | Verifier P/R measured; iterations don't lower F1; refutations anchored |
| 3 Regulatory over-trust | Required-elements capability + UX/reporting | No unqualified "compliant"; coverage manifest + human-review record |

## Sources

Internal (highest authority — this system's own measured behavior and code gates):
- `docs/eval/MEASUREMENT.md` — measured precision 2.4 %→24 %, recall 7 % (2/28), "every fix was a filter," "prompt instructions are not enforcement (measured twice)," missed-family taxonomy.
- `src/agents/detection/verify.py`, `challenge.py`, `summarise.py`, `planning.py`, `workers.py` — existing code gates (verbatim anchor, arithmetic refutation, fidelity guard, coverage repair, downgrade-never-drop).
- `src/llm/structured.py` — L1–L6 structured-output defense-in-depth. `.planning/PROJECT.md` — requirements, decisions, cost lessons.

Regulatory / liability (current enforcement — HIGH):
- FDA first AI-over-reliance warning letter, April 2026 (Purolea): [DLA Piper](https://www.dlapiper.com/en-us/insights/publications/2026/04/fda-warning-letter-highlights-risks-of-using-ai-in-drug-manufacturing) · [RAPS](https://www.raps.org/resource/fda-warns-firm-for-inappropriate-use-of-ai-in-drug-manufacturing.html) · [Epstein Becker Green](https://www.healthlawadvisor.com/fda-warns-against-over-reliance-on-ai-pharmaceutical-manufacturing-but-how-much-reliance-is-too-much) · [ECA/GMP](https://www.gmp-compliance.org/gmp-news/use-of-ai-agents-leads-to-the-first-fda-warning-letter-relating-to-ai)

Grounding & citation hallucination:
- [Deterministic Quoting for healthcare LLMs](https://mattyyeung.github.io/deterministic-quoting) · [CiteCheck: retrieval-grounded citation-hallucination detection](https://arxiv.org/html/2605.27700v1) · [Non-existent citations at scale](https://arxiv.org/pdf/2605.07723)

Agent cost / runaway loops:
- [Agent runaway costs & budget limits](https://relayplane.com/blog/agent-runaway-costs-2026) · [Agentic cost runaway / token budgets](https://leanopstech.com/blog/agentic-ai-cost-runaway-token-budget-2026/) · [Rate-limiting AI agents (3-layer gateway)](https://www.truefoundry.com/blog/rate-limiting-ai-agents-preventing-llm-api-exhaustion) · [Token Budgets: 63 budget-overrun incidents](https://arxiv.org/pdf/2606.04056)

Retrieval / chunking / tables on regulatory & long documents:
- [Stop chunking tables — agentic GraphRAG for financial disclosures (Red Hat)](https://developers.redhat.com/articles/2026/07/22/how-we-built-agentic-graphrag-financial-disclosures) · [Decomposing retrieval failures in long-document financial QA](https://arxiv.org/html/2602.17981v1) · [Why RAG fails on PDF tables](https://optyxstack.com/rag-reliability/why-your-rag-fails-on-pdf-tables-ocr-header-loss-row-boundary-fixes) · [RegGuard: retrieval assistant for pharma regulatory compliance](https://arxiv.org/pdf/2601.17826)

Table / document parsing:
- [Why PDF→Markdown OCR fails for AI document processing](https://unstract.com/blog/why-pdf-to-markdown-ocr-fails-for-ai-document-processing/) · [OCR vs layout-aware models: hard limits](https://www.bestaiweb.ai/from-ocr-to-layout-aware-models-prerequisites-and-hard-limits-of-document-extraction/)

Long-context / compaction:
- [Lost in the Middle (emergent property)](https://arxiv.org/pdf/2510.10276) · [Context rot](https://redis.io/blog/context-rot/)

Shortcut learning / OOD generalization:
- [Shortcut learning of LLMs in NLU (CACM)](https://cacm.acm.org/research/shortcut-learning-of-large-language-models-in-natural-language-understanding/) · [Exploring & mitigating shortcut learning (LREC 2024)](https://aclanthology.org/2024.lrec-main.602/) · [Shortcut learning hinders medical-AI generalization (npj Digital Medicine)](https://www.nature.com/articles/s41746-024-01118-4)

Self-verification / verifier limits:
- [Self-verification limitations of LLMs (reasoning & planning)](https://arxiv.org/pdf/2402.08115) · [OpenReview discussion](https://openreview.net/forum?id=4O0v4s3IzY)

Eval methodology / Goodhart / LLM-as-judge:
- [Goodhart's law comes for every benchmark (CACM)](https://cacm.acm.org/blogcacm/goodharts-law-comes-for-every-benchmark-you-trust/) · [Evaluating agentic AI: generalizability & benchmark overfitting](https://huggingface.co/blog/royswastik/evaluating-agentic-ai-part-6-generalizability) · [LLM-as-a-judge guide](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)

Multi-agent orchestration / consolidation:
- [Multi-agent orchestration architecture (Augment)](https://www.augmentcode.com/guides/multi-agent-orchestration-architecture-guide)

---
*Pitfalls research for: agentic FDA/ICH compliance reviewer over arbitrary PDF+DOCX corpora*
*Researched: 2026-07-30*
