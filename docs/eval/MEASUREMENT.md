# Accuracy measurement — detection pipeline vs. gold-standard reference

**Test document:** `Sample Data/32s43-validation-related-compounds-method.pdf` — Estradiol USP related-compounds
HPLC method verification, MVR-1381-RC v02 (55 pages, 20 parsed sections, 0 parse failures).
**Measured:** 2026-07-29. **Branch:** `CLI_for_folders` (`/dev`). **Model:** Qwen3-Next 80B · A3B (MoE).

## Headline

| Axis | Run 1 (baseline) | Run 3 (after fixes) |
|---|---|---|
| Findings emitted | 85 | 31 |
| TRUE_POSITIVE | 2 | 5 |
| FALSE_POSITIVE | 56 | 20 |
| WEAK (not wrong, not a deficiency) | 27 | 6 |
| **Precision (raw)** | **2.4 %** | **16 %** |
| **Precision (with concession gate replayed)** | — | **24 %** (5/21, 0 true positives lost) |
| **Distinct real issues found** | 2 | 2 |
| **Recall vs. 28-item reference** | 7 % | **7 %** |
| Runtime | 1171 s | 320 s |

**Precision improved ~10x. Recall did not move.** Every fix this session was a filter (removes wrong
findings); none makes the system find more.

## Gold-standard reference set: 28 distinct real deficiencies

Built by four independent blind reviewers (no access to detector output), each required to verify
arithmetic and to exclude intentional N/A, different-measurement comparisons, and rounding. Raw totals
14 + 9 + 7 + 7 = 37, deduplicated to **28 distinct** (~11 CERTAIN-grade). Per-scope detail in
`gt_A_front.md`, `gt_B_precision.md`, `gt_C_equiv.md`, `gt_D_cross.md`; detector output in
`run3_detector_output.md`.

### Found by the detector (2 / 28)
1. **Table 20 "Maximum" theoretical plates = 11477, true max = 12601** (In-house Equivalency row). The
   stated Mean (11041 = 66246/6) only reconciles *with* 12601, proving it belongs to the set. Error is
   propagated into Table 1. — ranked #1 in run 3.
2. **Unspecified impurity 0.15 % reported as meeting a NMT 0.10 % limit** in the equivalency study, while
   the section concludes equivalency and the criterion demands all impurities be within specification.

### Missed (26 / 28) — selected, by failure family
**Absence-of-evidence (claim asserted, data absent):**
- Specificity: 3 of the 5 solution types the report says it analysed (individual impurity, impurity
  mixture, **control/unspiked sample**) have no result and no chromatogram anywhere; resolution half of
  the criterion never tabulated.
- Sensitivity solution stated as injected in §1.4.6.1 — no result, no acceptance criterion; its area
  (485) is *below* the LOD-level mean (629).
- No supporting data for the LOD/LOQ determination (no σ, no slope, no S/N, no dilution series).
- Estradiol RS water-content determination required by its CoA never performed.
- Protocol and governing SOP referenced but never identified.

**Method-vs-claim plausibility (numbers inconsistent with their stated derivation):**
- **LOD/LOQ were never experimentally determined**: LOQ = exactly 2.00 x LOD for all four analytes
  (σ/slope gives 3.03), values equal the 10 %/20 % specification-level dilutions, and the appendix
  chromatograms are named "10 % LOD-LOQ Level" / "20 % LOD-LOQ Level".
- **Absorptivity factors computed from only 3 of 7 linearity levels** (60/100/150 %), undisclosed;
  reproduces Table 11 to 6 significant figures. Using all seven shifts 17a-Estradiol AF 1.03 -> 0.99.
- AF varies up to 27 % across the range yet a single value is applied, with no acceptance criterion.
- Reported "Co-relation Coefficient" is r^2, not r, in Tables 3 and 6.

**Cross-reference / arithmetic integrity:**
- **Table 19: USP total impurities 0.14 % < single largest unspecified 0.15 %** — impossible for one
  sample; the footnote reveals the cells come from different samples.
- Table 17's notebook citation differs between the body (`8133/...56`) and Table 1 (`8133/...46`).
- Unexplained gross outlier retained in Table 8 (Estradiol injection #6 = 389 vs 660-707; Grubbs
  G = 2.023, outlier at 99 %); the entire reported 18.9 % RSD comes from it.
- Diluent chromatogram is **not peak-free**: a 13439-area peak at RT 2.1 is 2.02x the 100 %-level
  Estradiol response (~0.20 %, twice the NMT 0.10 % unspecified limit), reported as "No Interference"
  with no disregard limit defined.

**Regulatory framing / document control:**
- **USP <1226> (verification of *compendial* procedures) is invoked for a method the report itself says
  is "adopted from the vendor's DMF"** and treats as distinct from the USP method. This mis-framing is
  the root cause of the omitted accuracy, range and robustness studies. Arguably the most consequential
  deficiency in the document.
- Accuracy/range/robustness absent as parameters; recovery only at one concentration level.
- Report issue date (May 02 2016) precedes author (05/06) and QA approval (05/10) signatures.

## What this says about the architecture

The 2 hits are both **"compare a number against a limit / against another cell"** — precisely the
oracle-shaped task. The 26 misses need reasoning the pipeline has no mechanism for:

| Missing capability | Would catch |
|---|---|
| Assertion-vs-evidence sweep ("the report says it did X — is X anywhere?") | ~6 findings |
| Derivation plausibility (does the number match its stated method?) | ~4 findings |
| Summary/total integrity oracle (`stated max == max(rows)`, `total >= max(component)`) | 2 findings, both CERTAIN |
| Statistical outlier check over replicate sets | 1 finding |
| Document-control / regulatory-premise review | ~4 findings |

Note the pipeline produced **six** findings about Table 20 (4 restating the one real Max error) while
missing the Table 19 total-vs-largest impossibility in a table it also reviewed. Depth of attention is
not the constraint; the *kinds* of check are.

## Fixes landed this session (all test-locked, 94 tests passing)

1. **Arithmetic refutation in the challenge** (`challenge.py::_arithmetic_refutation`) — the challenger
   reports the criterion and observed cells verbatim; **code** recomputes with the oracle parsers and
   drops the finding when the value provably satisfies its limit. Both cells must anchor in the
   document, so invented numbers cannot clear a real fault.
2. **Non-deficiency / concession gate** (`verify.py::_concedes_compliance`) — drops soft findings whose
   own title or detail concedes compliance. Measured: 15 of 35 in run 2, 10 of 31 in run 3, with zero
   true positives lost. Oracle/checklist findings exempt.
3. **`deficiency_exists` on `SuspicionVerdict`** (`workers.py`) — `verdict: "confirmed"` only meant *the
   claim is true*, and a neutral planner claim being true means the document is COMPLIANT. Suspicion-
   derived faults fell 7 -> 1.
4. **Model selection honoured everywhere** — `challenge.py` hardcoded the 70B "regardless of the
   detector choice"; `structured.py` L5 repair likewise. Both now use the analyst's choice.
5. **Concurrency 2 -> 10** across summarise/workers/challenge — 1171 s -> 320 s.
6. **Planner sees the whole document** — removed the 40 000-char truncation.
7. **Summariser fidelity guard** extended from numbers-only to numbers + named entities.

## Prompt instructions are not enforcement — measured twice

- "N/A cells are usually intentional" — ignored 15x in run 1.
- An explicit pre-report check "if your detail concedes compliance, DELETE the finding" — ignored 18x
  in run 2; the model wrote *"This is not a finding."* into the detail and shipped it anyway.

Every reliable improvement this session came from a **code gate**, not a prompt. Treat prompt rules as
advisory and enforce anything that matters in `verify.py` / `challenge.py`.

## Recommended next steps (highest value first)

1. **Summary/total integrity oracle** — `stated max/min/mean == recomputed`, `total >= max(component)`,
   `total == sum(components)`. Deterministic, generalises to any table, catches 2 CERTAIN findings
   including one currently missed.
2. **Assertion-vs-evidence pass** — extract every "we analysed/injected/determined X" claim, verify a
   result for X exists. Largest single missed family (~6).
3. **Dedup by `cited_section_indices` + category** — collapses run 3's 5 true positives to 2 distinct.
4. **Outlier check** over replicate sets (Grubbs or a simple ratio test).
5. Widen the concession gate for mid-text concessions (findings 11, 19, 21 still leak).
