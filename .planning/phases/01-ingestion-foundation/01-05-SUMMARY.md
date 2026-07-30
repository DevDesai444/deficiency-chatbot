---
phase: 01-ingestion-foundation
plan: 05
subsystem: api
tags: [registry, yaml, ctd, classification, pyyaml, migration]

requires:
  - phase: 01-ingestion-foundation
    provides: "CTDSection StrEnum (schemas.documents) whose values become the registry ids"
provides:
  - "ingest.registry package: load_families()/load_lexicon()/family_ids()/families_catalog_text()/as_ctd_section() over two YAML data files"
  - "ctd_families.yaml — 26 {id,label,applicability_trigger} entries (ids == CTDSection values, RULES-05 shape)"
  - "body_lexicon.yaml — per-family content keyword lists (D-06)"
  - "ctd.py detect_family(text)->str — doc-level registry-backed family id (deterministic tier for Plan 08)"
affects: [01-08]

tech-stack:
  added: ["PyYAML (USED but NOT yet declared in pyproject.toml — see Issues)"]
  patterns:
    - "Data-driven vocabulary: CTD families + lexicon live in version-controlled YAML; adding a family is a data edit (D-05)"
    - "Migration-safety: registry ids == CTDSection StrEnum values, so existing enum-keyed consumers keep matching with no renumber"

key-files:
  created:
    - src/ingest/registry/__init__.py
    - src/ingest/registry/ctd_families.yaml
    - src/ingest/registry/body_lexicon.yaml
    - tests/ingest/test_registry.py
  modified:
    - src/agents/detection/ctd.py
    - src/agents/detection/checklists.py

key-decisions:
  - "Registry is a PACKAGE src/ingest/registry/ (thin __init__ loader + 2 YAML files), NOT a registry.py next to a registry/ dir (name collision) — the resolved naming decision."
  - "detect_family reuses detect_ctd_section then maps UNKNOWN->'' and validates the id against family_ids(), so the deterministic tier and the registry stay in lockstep (D-05)."
  - "ctd.py and checklists.py both preserve their existing signatures/members — detect_ctd_section and describe_document are unchanged, so pipeline.py (read-only this plan) keeps working."

patterns-established:
  - "families_catalog_text() mirrors catalog.py domain_catalog_text() so Plan 08 can feed the family catalog to the LLM escalation tier."

requirements-completed: []  # INGEST-01 advanced (the classification vocabulary substrate) but not fully delivered — the walker + content classifier that USE this land in Plans 08/09.

duration: ~30min
completed: 2026-07-30
---

# Phase 1 · Plan 05: Data-Driven CTD-Family Registry + D-05 Migration — Summary

**Moved the CTD-family vocabulary out of the `CTDSection` Python enum into a version-controlled YAML registry (families + per-family body lexicon), with a compat shim keeping every existing enum-keyed consumer working — adding a family is now a data edit, not a code change.**

## Performance
- **Duration:** ~30 min
- **Tasks:** 2 completed
- **Files:** 4 created, 2 modified

## Accomplishments
- `ingest/registry/` package: `load_families`/`load_lexicon` (lru_cached YAML readers), `family_ids`, `families_catalog_text` (LLM-prompt renderer), and the D-05 `as_ctd_section` compat shim. 26 family entries; ids are exactly the `CTDSection` values (no renumber).
- `body_lexicon.yaml`: per-family keyword lists (D-06) seeded from `checklists._VALIDATION_REQUIRED` + `catalog.CANONICAL_DOMAINS`.
- `ctd.py`: added doc-level `detect_family(text) -> str` (registry-backed, `""` on no-match — the escalation trigger for Plan 08), preserving `detect_ctd_section`/`describe_document` unchanged.
- `checklists.py`: `_VALIDATION_SECTIONS` annotated to point at `ingest.registry` as the single source of truth; membership resolution unchanged.

## Task Commits
1. **Task 1: registry package (loader + 2 YAML)** — `bec79a3` (feat)
2. **Task 2: ctd.py detect_family + checklists note** — `4e60c1b` (feat)

## Verification (every acceptance command run via `.venv/bin/python`)
- `pytest tests/ingest/test_registry.py` → **7 passed**; `family_ids() <= CTDSection values` → `ids OK 26`; `applicability_trigger` grep passes.
- `detect_ctd_section('see 3.2.S.4.1')` is a `CTDSection`; `detect_family('3.2.S.4.1 Specification')` → `'3.2.S.4.1'`.
- `pytest tests/unit/test_detection.py` → **20 passed** (baseline was 20 passed → zero regression).
- Combined `pytest tests/ingest/ tests/unit/test_detection.py` → **41 passed**.

## pipeline.py (read-only — rule 3)
- **No edit made; `git diff --numstat src/agents/detection/pipeline.py` = 0 lines.** Verified by import that `pipeline`'s `detect_ctd_section(...)` / `describe_document(...)` call sites (pipeline.py:16,42-43) still resolve against the additive `ctd.py`. The staged, uncommitted redesign delta in `pipeline.py` was NOT touched or staged. (The plan's stale acceptance criterion #3 "small additive diff to pipeline.py" is superseded by the corrected scope: pipeline.py is read-only.)

## Deviations / Issues Encountered
- **PyYAML dependency not declared in pyproject.toml.** The registry imports `yaml`; PyYAML 6.0.3 is present in `.venv` so all tests pass, but `pyproject.toml` does NOT list it. **Action for the reviewer / a later plan:** add `pyyaml` to `pyproject.toml` dependencies — a fresh install would otherwise fail to import the registry. (Per the execution brief, the `pyyaml` dep is bundled into Plan 03's pending amendment.)
- Test import path uses `from tests.ingest.conftest import ...` where fixtures are needed (the package-path pattern established in Plan 02); `test_registry.py` imports only from `ingest.registry`/`schemas`, so it needs no conftest import.

## Files Created/Modified
- `src/ingest/registry/{__init__.py, ctd_families.yaml, body_lexicon.yaml}` — the registry.
- `src/agents/detection/ctd.py` — additive `detect_family`.
- `src/agents/detection/checklists.py` — source-of-truth comment.
- `tests/ingest/test_registry.py` — 7 tests.
