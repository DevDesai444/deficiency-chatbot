---
phase: 1
slug: ingestion-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Generated from `01-RESEARCH.md` §Validation Architecture. Task IDs are assigned by the planner — rows below are keyed by requirement until plans exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2+ with pytest-asyncio (`asyncio_mode=auto`) — `[VERIFIED: pyproject.toml:38,54-57]` |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`, `pythonpath=["src"]`, `testpaths=["tests"]`) |
| **Quick run command** | `pytest tests/ingest/ -x -q` |
| **Full suite command** | `pytest` then `python -m evals.run gate` then `python -m evals.run run --gate` |
| **Estimated runtime** | ~15–30 s quick (endpoint-free, no creds); ~1–2 min full |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ingest/ -x -q` (fast, endpoint-free — all substrate/DOCX/classification units run offline)
- **After every plan wave:** Run `pytest` (full unit + integration) + `python -m evals.run gate`
- **Before `/gsd-verify-work`:** Full suite green **and** `python -m evals.run run --gate` shows `mini_spec.docx` parsing (no longer a `parse_failure`) with **zero true positives lost** and no drop in PDF `parse_fidelity`/`anchor_rate` (SC4)
- **Max feedback latency:** ~30 seconds (quick suite)

---

## Per-Requirement Verification Map

> Task IDs are `TBD` until the planner assigns them; each row's automated command is the acceptance anchor a plan task must satisfy.

| Task ID | Requirement | Threat Ref | Test Type | Automated Command | File Exists | Status |
|---------|-------------|------------|-----------|-------------------|-------------|--------|
| TBD | INGEST-01 (SC1 rename-folders invariant; proves D-09 path-exclusion) | — | unit | `pytest tests/ingest/test_corpus.py::test_rename_folders_invariant -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-01 (uncapped depth + mixed PDF/DOCX; unsupported ext → `unsupported` row, no crash) | T-INGEST-walk | unit | `pytest tests/ingest/test_corpus.py::test_walk_uncapped_and_unsupported -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-01/03 (never-crash batch D-16: corrupt PDF + `.doc`/`.xlsx` → `parse_failed`/`unsupported`, good docs still ingest) | T-INGEST-malformed | unit | `pytest tests/ingest/test_corpus.py::test_one_bad_file_never_aborts -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-02 (`mini_spec.docx` → unified dict; impurities table reconstructs so 3 planted deficiencies findable) | — | unit + eval | `pytest tests/ingest/test_docx_parse.py -x` then `python -m evals.run run` | ❌ W0 | ⬜ pending |
| TBD | INGEST-02 (SC2 merged-cell fidelity: `gridSpan` + `vMerge` → every spanned coord → one origin span-ID) | — | unit | `pytest tests/ingest/test_docx_parse.py::test_merged_cells_resolve_to_origin -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-02 (SC2 multi-row/borderless/nested; complex-merge → typed `ParseFailed`, not crash) | T-INGEST-malformed | unit | `pytest tests/ingest/test_docx_parse.py::test_table_edge_cases -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-02/SC4 (no parse-fidelity regression on existing PDF `parse_fidelity`/`anchor_rate`) | — | eval gate | `python -m evals.run run --gate` | ✅ (add DOCX rows) | ⬜ pending |
| TBD | INGEST-04 (RISK-1 offset-map round-trip: random raw incl. ligatures/double-space/wrapped-hyphen/composables → byte-exact) | — | property (unit) | `pytest tests/ingest/test_normalize.py::test_offset_roundtrip -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-04 (D-26 guarded dehyphenation: 4 locked fixtures map to expected canonical) | — | unit | `pytest tests/ingest/test_normalize.py::test_guarded_dehyphenation -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-04 (NFC/ligature/unit invariants: ﬁ→fi via explicit map not NFKC; `µ`/`²`/case preserved; version stamped) | — | unit | `pytest tests/ingest/test_normalize.py::test_normalization_invariants -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-04 (span re-open byte-exactness + hash fail: tampered stream / wrong version → `HashMismatch`) | T-INGEST-tamper | unit | `pytest tests/ingest/test_anchors.py::test_reopen_and_hash_mismatch -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-05 (D-31 merged-cell identical resolution: every `(row,col)` a merge spans → SAME span-ID) | — | unit | `pytest tests/ingest/test_tables.py::test_merged_resolves_identically -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-05 (deterministic serialization: same doc twice → identical `(table_id,row,col)→span` + offsets) | — | unit | `pytest tests/ingest/test_tables.py::test_serialization_deterministic -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-03 (manifest availability tiers up front D-30: flat doc → `structure: flat` still grounds; scanned-table-lost → `tables: unavailable`) | — | unit | `pytest tests/ingest/test_store.py::test_manifest_availability_tiers -x` | ❌ W0 | ⬜ pending |
| TBD | INGEST-03 (cache resume/invalidate: crash-sim mid-corpus resumes w/o reparse; normalizer-version bump invalidates D-14/D-24) | — | unit | `pytest tests/ingest/test_store.py::test_cache_resume_and_invalidate -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/ingest/conftest.py` — shared fixtures: a merged-cell DOCX builder (extend `make_docx_fixture.py` style), a synthetic document-dict factory, `offline` OCR monkeypatch reused from `test_section_splitter.py:20-26`
- [ ] `tests/ingest/test_normalize.py` — offset round-trip property test + guarded-dehyphenation fixtures + NFC/ligature invariants (**RISK-1 gate — write FIRST, before any consumer depends on the offset map**)
- [ ] `tests/ingest/test_anchors.py` — span mint + re-open byte-exactness + hash-mismatch
- [ ] `tests/ingest/test_docx_parse.py` — DOCX→dict fidelity, merged/nested/borderless, `ParseFailed`
- [ ] `tests/ingest/test_tables.py` — `(table_id,row,col)`→span, merged identical-resolution, determinism
- [ ] `tests/ingest/test_corpus.py` — rename-folders invariant, uncapped walk, never-crash batch
- [ ] `tests/ingest/test_store.py` — manifest tiers, cache resume/invalidate
- [ ] A committed **merged-cell DOCX fixture** (new; `mini_spec.docx` has no merges) — required for SC2
- [ ] Extend the eval set / `evals/run.py` so DOCX has a live parse path (removes the `format != "pdf"` skip at `evals/run.py:174`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scanned-table addressing via the box-returning RapidOCR endpoint | INGEST-05 (best-effort per D-30) | Depends on live Databricks endpoint deployment state (RISK-2) — unverifiable in CI/no-creds; automated suite runs endpoint-free | With creds + box-returning endpoint deployed (`notebooks/deploy_rapidocr_endpoint.py`), ingest a scanned spec PDF and confirm reconstructed cells carry `(table_id,row,col)` span-IDs; without it, confirm the page reports `parsed_partial` / `tables: unavailable` |

---

## Security Domain (ASVS L1)

Ingestion parses **untrusted** drug-submission files. The planner MUST include a `<threat_model>` block and a small `ingest/limits.py` (byte/page/entry/time caps) consumed by both parse paths **before** the heavy parse call — these caps also serve D-16 "never abort" and 500-doc scale.

| Threat | STRIDE | Mitigation | Threat Ref |
|--------|--------|-----------|------------|
| DOCX zip / decompression bomb | DoS | Inspect with `zipfile` before `docx.Document()`: cap uncompressed size + entry count, reject absurd ratios; per-file byte ceiling | T-INGEST-zipbomb |
| Malformed / adversarial PDF (crash, memory blowup) | DoS / Tampering | Per-file try/except → `parse_failed` (D-16, never aborts); wall-clock/memory + page-count cap | T-INGEST-malformed |
| Path traversal / symlink escape on the walk | Elevation / Info Disclosure | Resolve real paths; refuse symlinks escaping `root`; cache keyed by content-hash, never attacker filename | T-INGEST-walk |
| Filename/path as classification attack vector | Tampering | Already mitigated by D-09 (path excluded from classification signals) | T-INGEST-path (covered by SC1 test) |
| XXE / external entity in DOCX XML | Info Disclosure | python-docx uses `lxml`; confirm external-entity resolution disabled for untrusted XML parts | T-INGEST-xxe |
| Zip-slip in DOCX part names | Path traversal | Never extract parts to disk by internal names; sanitize any custom part handling | T-INGEST-zipslip |
| Content-hash tamper (span integrity) | Tampering | `hashlib` blake2b/sha256 substring hash; re-open fails on mismatch (INGEST-04) | T-INGEST-tamper |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (7 test files + merged-cell DOCX fixture + DOCX eval path)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
