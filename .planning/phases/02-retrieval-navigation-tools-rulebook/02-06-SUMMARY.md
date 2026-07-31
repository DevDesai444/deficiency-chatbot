# 02-06 SUMMARY — Requirement Index (RULES-05)

**One-liner:** Built the requirement index — the absence-of-evidence mechanism (RULES-05): a code loader gate (byte-exact provenance re-open), content-derived submission-profile applicability (D-RB4), `enumerate_requirements` server-side resolver (D-RI2), a committed reproducible edge-build, and a self-contained **14/14** ground-truth traceability test — over **15 senior-reviewer-verified entries**; plus a reviewer-ordered Phase-1 substrate fix and honest CFR/FDA re-coverage.

**Requirements:** RULES-05 ✓ (with COST-04/TOOLS-01 read_guideline enumerate contract landing in 02-09).

## What was built
- `src/rulebook/requirement_index.py` — `RequirementEntry`, **loader gate** `load_requirement_index` (family in D-05 registry + provenance span re-opens byte-exact via `open_span`, else raises), `submission_profile` (content-derived, D-09 discipline), `enumerate_requirements` (D-RI2 union: `family_requires_requirement` ∪ `profile_requires_family`), committed reproducible `build_requirement_edges()`, `REQUIREMENT_INDEX_VERSION="2"` (D-24).
- `src/rulebook/requirement_index.yaml` — **15 entries**, each with a byte-exact provenance span over the real vendored rulebook (eCFR/ICH/FDA).
- `tests/rulebook/test_requirement_index.py` — 23 tests incl. the **self-contained, offline** D-RI1(2) traceability test (fixture builds chunks + edges from the committed snapshot; verified from a fresh `data/`-moved-aside state, zero network).
- `src/ingest/normalize.py` — `canon_range_to_raw` END-boundary interpolation fix (read-path only; D-22 raw-citation correctness) + tightness property test + regression fixture.

## Senior-reviewer sign-off (D-RI1(3))
The senior reviewer re-opened every cited span and read the rule text. Verdict: **10 approved as-is**; **3 revised** — Q2-LINEARITY (no change; the apparent breadth was the normalize.py substrate bug, not authoring), Q6A→`Q6A-WATER-CONTENT-TEST` (narrow to water-content-test-presence, re-tag 3.2.S.5→3.2.S.4.1, tighten span), `Q2-SOLUTION-STABILITY`→`FDA-SOLUTION-STABILITY` (re-cited from the ICH-Q2 NMR-example fragment to FDA Analytical Procedures §VII.F, a clean supporting clause); **2 new honest re-coverage entries** — `CFR-211160B-SOUND-BASIS` (21 CFR 211.160(b)) and `CFR-211194-CALCULATIONS` (21 CFR 211.194(a)(5)) — re-covering A-01/A-10/H-03 at general-clause generality rather than stretching a specific clause.

## Commits
- `94ade36` requirement_index.py (loader gate, submission_profile, enumerate_requirements)
- `0e5d6f0` draft requirement_index.yaml + edges + traceability test
- `145e575` **fix(ingest):** canon_range_to_raw END interpolation + tightness test (D-22)
- `924725f` **fix(02):** reviewer revisions + honest CFR/FDA re-coverage + reproducible edge-build
- `ac79460` **refactor(02):** rename Q2-SOLUTION-STABILITY → FDA-SOLUTION-STABILITY (id honesty; travels on findings per D-EF1(5))

## Verification
Offline (Databricks unset): `tests/rulebook/` + `tests/ingest/` + `tests/evals/` = **196 passed, 0 failed**. 14/14 traceability reproducible from a fresh checkout. Loader gate re-validates all 15 provenance spans byte-exact. Redesign import-only files untouched throughout.

## Deviations
- Phase-1 substrate fix (`normalize.py`) folded in as a reviewer-ordered separate commit — read-path only, zero span invalidation / zero baseline impact (evals unmoved at 196 passed).
- `FDA-SOLUTION-STABILITY` id keeps the source-prefix convention (honest: the entry cites FDA, and the id rides on every finding as metadata).

## Next-phase readiness / carried items
- Phase-verification queue: see `02-PHASE-VERIFICATION-QUEUE.md` (5 items, none block 02-06 or Wave 4; item 5 — citation↔store granularity — found in 02-09 and MATERIAL for Phase 3).
- 02-09 `read_guideline` (Wave 4) consumes this index (enumerate mode, D-RI2) — stable requirement ids feed `emit_finding`'s rule-citation field.
