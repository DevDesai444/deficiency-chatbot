---
phase: 01-ingestion-foundation
plan: 08
subsystem: ai
tags: [classification, deterministic-first, llm-escalation, structured-output, escalation-rate]

requires:
  - phase: 01-ingestion-foundation
    provides: "registry + detect_family (Plan 05); anchors.mint_span (Plan 06); normalize (Plan 03); llm.structured.structured_call (existing, protected)"
provides:
  - "ingest.classify.classify_document(nt, outline, doc_id, model, stats) -> DocClassification"
  - "deterministic tiers: regex -> title-block (D-28) -> body lexicon; LLM escalation via structured_call only on no deterministic signal"
  - "EscalationStats: measured per-tier escalation_rate (D-27)"
affects: [01-09]

tech-stack:
  added: []
  patterns:
    - "Deterministic-first, LLM-as-escalation; reuse the hardened structured_call verbatim (instance XOR ParseFailed)"
    - "Path-exclusion by construction: classify_document takes canonical text + outline + doc_id only (D-09)"

key-files:
  created:
    - src/ingest/classify.py
    - tests/ingest/test_classify.py
  modified: []

key-decisions:
  - "D-09 enforced by signature: no path/filename/folder parameter, proven by test_signature_has_no_path_or_filename (and Plan 09's rename-folders SC1)."
  - "No-creds guard mirrors ocr.py:78 (skip the LLM tier when Databricks host+token are empty). Tests set an autouse no-creds default so they are env-independent and make NO real network calls; the two escalation tests opt into creds + a monkeypatched structured_call."
  - "Tier provenance (D-29): each result records its resolving tier (regex/lexicon/llm/none) and a triggering span-ID; confidence scales are per-tier and left uncalibrated (D-03, no threshold)."

patterns-established:
  - "A non-CTD / no-signal doc still returns a first-class free-form label (tier='none'), never dropped (D-02)."

requirements-completed: []  # INGEST-01 classifier landed; the uncapped walker that applies it + proves the rename-folders invariant is Plan 09.

duration: ~35min
completed: 2026-07-30
---

# Phase 1 · Plan 08: Content Classifier — Summary

**Built the deterministic-first content classifier — regex → first-N-lines title block (D-28) → body lexicon, escalating to a cheap LLM via the hardened `structured_call` only when no deterministic signal fires — emitting `{label, family_guess, confidence, tier, triggering_span}`, taking no path/filename (D-09), applying no threshold (D-03), and reporting a measured per-tier escalation rate (D-27).**

## Performance
- **Duration:** ~35 min · **Tasks:** 2 (both in classify.py) · **Files:** 2 created

## Task Commits
1. **Tasks 1+2: classifier (deterministic tiers + LLM escalation + EscalationStats)** — `cb4c21e` (feat)

## Verification (every acceptance command run via `.venv/bin/python`)
- `pytest tests/ingest/test_classify.py` → **9 passed** (regex/lexicon/title-block tiers; no-threshold free-form fallback; LLM escalation → tier="llm"; ParseFailed → deterministic fallback without raising; offline → LLM NOT invoked; EscalationStats fractions sum to 1.0).
- no-path signature: `classify_document` params exclude `{path,filename,folder}` → **no-path OK** (D-09).
- greps `tier` + `triggering_span` (D-29) and `structured_call` + `escalation_rate` (D-07/D-27) pass.
- Full `pytest tests/ingest/` → **47 passed** (no regression).

## Protected-file discipline
- Imports `llm.structured.structured_call` and `config.get_settings` (both among the 13 staged redesign files) **read-only** — `git diff --numstat` shows **0 unstaged lines** on `structured.py`/`client.py`; neither was edited or staged.

## Env-independence fix
- The dev env has Databricks creds, so tests reaching the LLM tier were making real (slow, non-deterministic) network calls. Added an **autouse no-creds default** so the suite is deterministic and endpoint-free (0.46s); the two escalation tests explicitly opt into creds + a monkeypatched `structured_call`.

## Files
- `src/ingest/classify.py`, `tests/ingest/test_classify.py`.
