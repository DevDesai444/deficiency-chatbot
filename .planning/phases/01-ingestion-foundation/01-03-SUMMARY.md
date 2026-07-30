---
phase: 01-ingestion-foundation
plan: 03
subsystem: api
tags: [normalization, offset-map, unicode, nfc, dehyphenation, risk-1, pyyaml]

requires:
  - phase: 01-ingestion-foundation
    provides: "NormalizedText/OffsetRun types (Plan 02); ingest.registry (whose pyyaml this declares)"
provides:
  - "ingest.normalize: normalize() -> NormalizedText (NFC + guarded dehyphenation + whitespace-collapse + explicit ligature fold)"
  - "canon_range_to_raw / raw_range_to_canon — the reversible run-based canonical<->raw offset map (O(log n), D-23)"
  - "committed dehyphen_lexicon.txt (170 words) — the ONLY, machine-independent dehyphenation word source"
  - "NORMALIZER_VERSION with the lexicon version folded in (D-24 migration path)"
affects: [01-06, 01-07, 01-08]

tech-stack:
  added: ["pyyaml>=6.0 (declared in pyproject; registry imported it undeclared in wave 2)"]
  patterns:
    - "Record->run offset model: each normalization edit is a run (equal/collapse/expand/delete); consecutive 1:1 runs coalesce (O(edits) memory)"
    - "RISK-1 gate: the offset-map round-trip property test is written first and must be green before any consumer depends on the map"

key-files:
  created:
    - src/ingest/normalize.py
    - src/ingest/dehyphen_lexicon.txt
    - tests/ingest/test_normalize.py
  modified:
    - pyproject.toml

key-decisions:
  - "OP ORDER: NFC -> guarded-dehyphenate -> whitespace-collapse -> ligature. The plan's literal order (whitespace-collapse BEFORE dehyphenate) would turn the '-\\n' line-break into a space, so the four LOCKED D-26 fixtures could never match. Dehyphenation must see the literal newline; this is the fixture-driven, correctness-preserving order (documented in the module docstring)."
  - "canon_range_to_raw uses proportional offset ONLY inside 'equal' runs; edit runs (compose/collapse/expand/delete) clamp to run boundaries, and middle + trailing deletions are absorbed so a canonical range spanning a dropped hyphen returns the hyphen+newline in the raw slice (D-22 renderability)."
  - "Lexicon is a COMMITTED repo file (the only word source); LEXICON_VERSION is inside NORMALIZER_VERSION and a sha256 pin test forces the two to move together (D-24)."

patterns-established:
  - "Boundary law: normalization lives ONLY in ingest.normalize; parsers emit raw text (never normalize)."

requirements-completed: []  # INGEST-04 advanced (the correctness core); the re-open/verify primitive that completes it lands in Plan 06.

duration: ~50min
completed: 2026-07-30
---

# Phase 1 · Plan 03: 4-Op Normalizer + Reversible Offset Map (RISK-1) — Summary

**Built the load-bearing correctness core: a 4-op canonical-text normalizer and a reversible run-based canonical↔raw offset map, gated by a property test that proves every canonical range renders back to its exact raw source substring — the mechanism the "verbatim quote = raw source" citation contract (D-22/D-23) depends on.**

## Performance
- **Duration:** ~50 min
- **Tasks:** 3 completed (TDD RED→GREEN)
- **Files:** 3 created, 1 modified

## RED→GREEN (TDD)
- **RED confirmed** (recorded per Task 1 acceptance): before `normalize.py` existed, `pytest tests/ingest/test_normalize.py -x -q` failed at import — `ModuleNotFoundError: No module named 'ingest.normalize'`, exit 2.
- **GREEN**: after Task 2, all 6 tests pass, including `test_offset_roundtrip` (**RISK-1 GREEN — the gate is open for Plans 06/07/08**).

## Task Commits
1. **Task 1: RISK-1 gate test (RED-first)** — `f0b88fa` (test)
2. **Task 2: normalizer + committed lexicon (GREEN)** — `4e29707` (feat)
3. **Task 3: declare pyyaml** — `0dda6e1` (build)

## Verification (every acceptance command run via `.venv/bin/python`)
- `grep -c "def test_"` → 6 (≥3). RED recorded above.
- `test_offset_roundtrip` / `test_guarded_dehyphenation` / `test_normalization_invariants` / `test_lexicon_version_pin` → each **passed**.
- 4 LOCKED D-26 fixtures: `95.0-\n105.0%`→`95.0-105.0%`, `2-\nethylhexanoic acid`→`2-ethylhexanoic acid`, `specifi-\ncation`→`specification`, `well-\nknown`→`well-known` — plus negatives (`95.0105.0`, `2ethylhexanoic` absent).
- `grep -v '^#' … | grep -c NFKC` → **0**; `grep -Ec 'usr/share/dict|nltk|wordnet'` → **0** (reworded the docstrings that had tripped these; NFC is the only unicodedata form used).
- `NORMALIZER_VERSION` / `raw_range_to_canon` / `dehyphen_lexicon.txt` greps pass; lexicon present, **170 lines** (≥100); `'lex' in NORMALIZER_VERSION` → `nfc-wscollapse-gdehyph-lig/1-lex1`.
- Task 3: `pyyaml` in pyproject; `from ingest.registry import load_families` → **26**.
- Full `pytest tests/ingest/` → **27 passed** (no regression across serialize/limits/registry/normalize).

## Extra hardening (RISK-1 is irreversible-to-redesign)
- Ran a scratchpad adversarial stress (NOT in the repo): **20,000 random cases + 20 pathological edges** (empty, all-whitespace, nested `-\n-\n`, standalone combining marks, ligature-adjacent, digit-hyphen) — **zero offset-map holes** against per-char explanation, full-range exactness, monotonic coverage, and raw↔canon inverse invariants.

## Deviations / flags for the reviewer
- **Op order** (above): NFC → dehyphenate → whitespace-collapse → ligature, not the plan's literal wscollapse-before-dehyphenate (which would break the locked fixtures). Fixtures are the D-26 authority.
- **requirements.txt / uv.lock NOT modified.** They are outside this plan's `files_modified` (only `pyproject.toml` is), and the non-negotiable git rule is stage-only-files_modified. `requirements.txt` exists and `uv` is available — **flag:** if `requirements.txt` is used for installs or a lockfile is regenerated, `pyyaml>=6.0` should be propagated there / `uv lock` run in a follow-up. I did not run `uv lock` (would touch `uv.lock`, out of scope, side effects).

## Files
- `src/ingest/normalize.py` — the 4-op normalizer + offset map.
- `src/ingest/dehyphen_lexicon.txt` — committed 170-word plausibility lexicon (sha256-pinned).
- `tests/ingest/test_normalize.py` — RISK-1 gate.
- `pyproject.toml` — `pyyaml>=6.0`.
