---
phase: 04-rulebook-enrichment-absence-enumeration
reviewed: 2026-08-05T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - pyproject.toml
  - rulebook/manifest.yaml
  - src/evals/baseline/absence_threshold.json
  - src/evals/baseline/coverage_baseline.json
  - src/evals/run.py
  - src/rulebook/absence.py
  - src/rulebook/build.py
  - src/rulebook/requirement_index.py
  - src/rulebook/requirement_index.yaml
  - src/schemas/faults.py
  - src/tools/__init__.py
  - src/tools/emit_finding.py
  - src/tools/errors.py
  - tests/evals/test_generality_guard.py
  - tests/rulebook/test_absence.py
  - tests/rulebook/test_ich_ingest.py
  - tests/rulebook/test_metadata.py
  - tests/rulebook/test_requirement_index.py
  - tests/tools/test_emit_absence_finding.py
  - tests/tools/test_enumerate_fetch_emit_e2e.py
  - tests/tools/test_read_guideline_dual_resolve.py
findings:
  critical: 1
  warning: 7
  info: 4
  total: 12
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-08-05
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

This phase adds the deterministic absence pass (`rulebook.absence.enumerate_absences`), the
absence-typed grounding gate (`emit_absence_finding`), rulebook enrichment (5 ICH guidelines,
25-entry requirement index), and four new eval-harness gates (`coverage-gate`, `absence-gate`,
plus supporting baselines). The grounding contract is generally well-defended: the absence gate
re-opens the rule half byte-exact, validates it was ledger-issued this session, and rejects
un-re-derivable anchors — a fabricated/never-issued claim span is provably unemittable
(`test_absence_fabricated_claim_span_not_byte_exact_cannot_be_emitted`). The generality guard's
NO-CONSTANT and RENAME-INVARIANCE tripwires run on every build.

However, the review surfaced one BLOCKER and several WARNINGs that undermine the project's stated
priorities:

- **The whole-section absence path silently drops recall** for requirements that apply to a family
  through the supplemental edge links rather than their own `.family` field (BLOCKER — a real,
  required-but-absent family will not surface the CFR entries it should).
- **The most substantive generality invariants (SAME-LOGIC / THRESHOLD TRANSFER) are `@pytest.mark.slow`
  and deselected by default**, so the "always-on" enforcement the priorities demand is actually only
  two of four invariants (WARNING). The NO-CONSTANT tripwire is also trivially bypassable.
- **The `absence-gate` conflates "no absence docs available" with "recall recovered above floor"**
  in a way that either fails-closed on a clean checkout or can pass on an empty aggregate depending
  on eval-set composition (WARNING).
- The absence pass attaches an arbitrary top sub-threshold hit as the "narrative-claim span,"
  mislabeling unrelated text (WARNING).

## Critical Issues

### CR-01: Whole-section absence path misses supplementally-linked requirements — recall gap

**File:** `src/rulebook/absence.py:169`
**Issue:**
In the whole-section (D-SEC1) pass, candidate requirements for an absent, profile-required family
are selected by filtering on the entry's OWN `.family` attribute:

```python
for entry in (e for e in entries_by_id.values() if e.family == dst_family):
```

But applicability in `enumerate_requirements` (requirement_index.py:220-231) is edge-driven, not
`.family`-driven. `_SUPPLEMENTAL_FAMILY_REQUIREMENT_LINKS` (requirement_index.py:69-72) deliberately
links `CFR-211160B-SOUND-BASIS` and `CFR-211194-CALCULATIONS` to families `3.2.S.4.1` / `3.2.S.4.2`
via `family_requires_requirement` edges, while those entries' own `.family` is `3.2.S.5`. The new
Phase-4 spec-clause closure edges make `3.2.S.4.1` a profile-required family (build.py /
requirement_index.py:169-174), so a `drug_substance` submission that OMITS `3.2.S.4.1` entirely will
reach the whole-section branch with `dst_family == "3.2.S.4.1"`.

At that point the generator `e.family == dst_family` matches only entries natively tagged `3.2.S.4.1`
(e.g. `Q3A-IDENTIFICATION-THRESHOLD`, `Q6A-DESCRIPTION`) and **silently skips**
`CFR-211160B-SOUND-BASIS` / `CFR-211194-CALCULATIONS`, even though `enumerate_requirements` would fire
them for that same absent family. A known-required deficiency class therefore fails to surface on the
one path (whole-section, zero-document family) that exists specifically to catch a fully-omitted
required section — the exact recall failure the D-SEC1 mechanism was built to prevent. This is a
correctness gap in the recall layer, not a downgrade: the "over-emit, verifier prunes" contract
(D-ABS2) cannot prune something that was never emitted.

The requirement-level pass (section 1) does not compensate: it iterates `applicable` and queries
`search_corpus`, but for a *zero-document* family there is nothing to retrieve and the whole-section
branch is the intended source — and the `emitted_keys` dedup only prevents double-counting, it does
not add the missing entries.

**Fix:** Select whole-section candidates by the same edge relation `enumerate_requirements` uses, not
the raw `.family` attribute. Build a family→requirement map from the applicable set once, mirroring
`families_by_requirement` in `enumerate_requirements`:

```python
# Map each applicable requirement to every family it applies to (native .family PLUS supplemental
# edge links), matching enumerate_requirements' edge-driven applicability.
families_by_requirement: dict[str, set[str]] = {}
for entry in applicable:
    families_by_requirement.setdefault(entry.id, set()).add(entry.family)
    for fam in _SUPPLEMENTAL_FAMILY_REQUIREMENT_LINKS.get(entry.id, ()):
        families_by_requirement.setdefault(entry.id, set()).add(fam)
...
for entry in (e for e in entries_by_id.values()
              if dst_family in families_by_requirement.get(e.id, set())):
```

Or, preferably, drive the whole-section pass off `enumerate_requirements(manifest, family=dst_family)`
so a single applicability resolver is the source of truth for both branches. Add a composition test
in `tests/rulebook/test_absence.py` that omits `3.2.S.4.1` under a `drug_substance` profile and
asserts the supplementally-linked CFR entries appear in `fired_families`/candidate ids.

## Warnings

### WR-01: The substantive generality invariants are deselected by default — "always-on" is only half-true

**File:** `tests/evals/test_generality_guard.py:101`, `pyproject.toml:66`
**Issue:**
The phase priorities require the generality guard to "actually enforce ... and not be trivially
passing," and the module docstring claims all four invariants are "enforced every run — never a
one-time audit." In fact `test_threshold_transfer_and_same_logic_on_heldout` — the only test that
proves SAME-LOGIC (invariant 3) and THRESHOLD TRANSFER (invariant 4), i.e. that the frozen
mvr1381-tuned threshold actually recovers held-out absences from shared index entries — is marked
`@pytest.mark.slow`, and `pyproject.toml:66` sets `addopts = "-m 'not slow'"`. So on a default
`pytest` run only invariants 1 (NO-CONSTANT) and 2 (RENAME-INVARIANCE) execute; the two invariants
that actually witness anti-overfitting on the held-out corpus do not. The remaining two are
weaker: RENAME-INVARIANCE also `pytest.skip`s entirely when the gitignored held-out PDF is absent
(line 59), which is the normal CI/clean-checkout state. The docstring's "always run" / "every run"
claims therefore overstate what the committed configuration enforces.

**Fix:** Either (a) drop the `slow` marker's default-deselect for this specific test (keep it fast by
reducing the query set) so the anti-circularity invariant runs every build, or (b) ensure the
`absence-gate` CLI — which the docstring points to as the every-run substitute — is wired into the CI
gate sequence and note explicitly that RENAME/SAME-LOGIC/THRESHOLD invariants degrade to skips
without the local corpus. At minimum, correct the module docstring so it does not claim enforcement
the committed config does not provide.

### WR-02: NO-CONSTANT tripwire is trivially bypassable (case/format-sensitive substring scan)

**File:** `tests/evals/test_generality_guard.py:68-76`
**Issue:**
`test_absence_module_embeds_no_corpus_constant` guards against embedded submission-specific constants
by lower-casing `absence.py`'s source and checking for the literal substrings in `_DATASET_LITERALS =
("mvr1381", "spec32s41", "heldout32s41", "minispec")`. This is a fixed denylist of four known dataset
ids, not a structural guarantee. Any overfitting constant not on that list — a hardcoded family like
`"3.2.S.4.3"`, a magic threshold, a specific citation, or a differently-spelled doc id — passes the
tripwire untouched. The test's own docstring frames it as "references no dataset/doc/submission-ID
literal," but it only enforces "does not contain these four strings." An implementer overfitting via
a hardcoded family/citation would not be caught.

**Fix:** Strengthen toward a structural check: assert `absence.py` imports its threshold from the
caller (already true) and contains no numeric literal thresholds and no CTD-family string literals
(scan for `r"3\.2\.[SP]\."` and float literals), in addition to the dataset-id denylist. Document
the denylist as a backstop, not the primary guarantee.

### WR-03: `absence-gate` fails-closed on a clean checkout and treats an empty aggregate as failure

**File:** `src/evals/run.py:392-424`
**Issue:**
`cmd_absence_gate` skips any non-held-out absence doc that fails to ingest (line 398-401,
"never crashes the gate") but then computes `aggregate = matched_total / required_total if
required_total else 0.0` and fails when `aggregate <= 0.0` (line 419). On a clean checkout / CI where
`data/` is gitignored (confirmed by `_load_source_text`'s own comment about `data/README.md` and by
the generality guard `pytest.skip`), *both* `mvr1381` and `minispec` ingest attempts fail, every doc
is skipped, `required_total == 0`, `aggregate == 0.0`, and the gate returns exit 1 — reporting
"the #1 gap not recovered" when in reality no corpus was available to measure. This is a
false-negative gate result driven by environment, not code quality, and it contradicts the
docstring's stated "a missing local corpus file must not fail the build." Conversely, if the eval
set were ever edited so no non-held-out doc carries absence GT, the same `required_total == 0` path
would (correctly-by-accident) fail — but for the wrong reason (no items) rather than a real recall
loss.

**Fix:** Distinguish "measured and recovered above floor" from "nothing to measure." When every
absence doc was skipped (`required_total == 0` because all ingests failed, or `per_doc` values are
all `"skipped: ..."`), emit a distinct `ABSENCE-GATE SKIPPED (no local corpus)` and return 0 (or a
dedicated non-fail code), matching `cmd_retrieval_gate`'s tolerance. Only return 1 when at least one
doc was actually measured and the measured aggregate is `<= 0.0` or below the committed floor.

### WR-04: Absence pass mislabels an arbitrary top sub-threshold hit as the "narrative-claim span"

**File:** `src/rulebook/absence.py:138`
**Issue:**
For every sub-threshold requirement, the pass sets
`claim_span_id = SpanID(**hits[0]["span_id"]) if hits else None` and stores it on the anchor as the
D-ABS4 "unsupported narrative-claim CORPUS span." But `hits[0]` is simply the top-ranked retrieval
result that *fell below threshold* — i.e. the best near-miss, which by construction is weak/unrelated
evidence. The schema (`schemas/faults.py:84`) documents `claim_span_id` as "the unsupported
narrative-claim CORPUS span when one exists (mvr/MS-03)," implying a semantically-selected claim, not
"whatever the top sub-threshold hit happened to be." Attaching an arbitrary chunk here risks a
downstream verifier (Phase 7) or the analyst treating unrelated submission text as the claim the
finding rests on. It is byte-exact and ledger-issued (so it is not a grounding violation), but it is a
correctness/semantics defect: the anchor asserts more than the evidence supports.

**Fix:** Only populate `claim_span_id` when the top hit actually reads like a relevant narrative claim
(e.g. gate on a minimum score band, or on a lightweight relevance signal), otherwise leave it `None`.
The `sub_threshold_hits` list already preserves the near-miss evidence for re-derivation, so a `None`
claim span loses nothing. Document that `claim_span_id` is best-effort and may be `None`.

### WR-05: `_get_with_retry` does not retry transient 5xx and can loop-exhaust into an unreachable RuntimeError

**File:** `src/rulebook/build.py:41-49`
**Issue:**
The retry loop only special-cases `429`. A transient `500/502/503` from eCFR/ICH/FDA calls
`resp.raise_for_status()` immediately on the first attempt (no retry), so a flaky gateway aborts a
vendoring fetch that a single retry would have recovered. Separately, if every attempt returns `429`,
the loop exhausts without returning and falls through to `raise RuntimeError(f"unreachable: {url}")` —
which is not actually unreachable (it is the all-429 path), producing a misleading error message that
hides the real cause (persistent rate-limiting). Both matter only in "vendoring mode" (offline-first
path is the default), but that is exactly when the network is being exercised.

**Fix:** Retry on `429` and `>=500` alike, and on exhaustion raise a message that names the last
status (e.g. `f"{url}: exhausted {_MAX_RETRIES} retries, last status {resp.status_code}"`) instead of
`"unreachable"`.

### WR-06: `fetch_ecfr_part`'s `next(...)` over the titles list raises an opaque `StopIteration` on a schema change

**File:** `src/rulebook/build.py:57`
**Issue:**
`edition_date = next(t["up_to_date_as_of"] for t in titles["titles"] if t["number"] == int(title))`
raises a bare `StopIteration` (or `KeyError` on `titles["titles"]`/`t["number"]`) if the eCFR API
response shape changes or title 21 is momentarily absent. The surrounding `build_ecfr` catches
`Exception` and records a manifest error row (build.py:163), so the build does not crash — but the
recorded error string for a `StopIteration` is empty/uninformative (`str(StopIteration())` is `""`),
producing a manifest error row with an empty `error` value, which the metadata test only asserts is
truthy (`test_metadata.py:41`). A silently-empty error message defeats the D-16 "recorded skip"
diagnostic value.

**Fix:** Replace the bare `next(...)` with an explicit lookup that raises a descriptive error:
`match = [t for t in titles.get("titles", []) if t.get("number") == int(title)]; if not match: raise
RuntimeError(f"eCFR titles.json has no title {title}")`.

### WR-07: Baseline `emitted` counts and `generated_from` provenance are unverifiable frozen snapshots

**File:** `src/evals/baseline/absence_threshold.json:5-16`, `src/evals/baseline/coverage_baseline.json:2`
**Issue:**
The committed baselines record `per_document.mvr1381 = {emitted: 8, required: 11}` and
`minispec = {emitted: 8, required: 1}` with `generated_from:
"live:enumerate_absences(mvr1381+minispec)_2026-08-05"`. Nothing in the committed gate re-checks the
`emitted` counts — `cmd_absence_gate` only reads `threshold` and `non_held_out_aggregate.absence_recall`
(run.py:370, 426). The `emitted` numbers are therefore documentation that can silently drift from
reality (e.g. after CR-01 is fixed the whole-section counts change) with no test catching the
mismatch. The same is true of `coverage_baseline.json`'s `note` describing "ich=5, total_entries=25":
`coverage-gate` enforces `total_entries` and per-family/source floors, but the `entries_per_family`
map (`3.2.S.4.3: 10, 3.2.S.4.1: 5, ...`) can under-count relative to the actual index without failing
as long as the *measured* value is `>=` baseline — so a baseline that was recorded too low permanently
weakens the floor.

**Fix:** Either drop the unenforced `emitted`/`note` counts from the JSON to avoid stale
documentation, or add a lightweight assertion (in `test_absence.py` / a coverage test) that the
committed `per_document.*.emitted` and `entries_per_family` match a fresh live measurement, so the
baseline cannot silently rot.

## Info

### IN-01: `emit_finding`/`emit_absence_finding` duplicate the NormalizedText-from-cache construction

**File:** `src/tools/emit_finding.py:91-93`, `205-207`
**Issue:** The `NormalizedText(canonical=..., raw_serialized=..., offset_map=[OffsetRun.model_validate(r)
for r in ...], ...)` construction is copy-pasted in both functions (and again in
`tools/search_corpus.py:19-23` as `_nt_from_cache_entry`). Three copies invite divergence if the cache
shape changes.
**Fix:** Extract a shared `_nt_from_cache(cache: dict) -> NormalizedText` helper and reuse it in both
emit functions.

### IN-02: `_manifest_span_ids` docstring says empty lists are valid, but callers never assert non-empty — dead defensive branch

**File:** `src/rulebook/absence.py:41-57`
**Issue:** The function collects outline span-ids as "informational evidence of the search space" and
documents that an empty list is valid, but nothing downstream reads or validates these ids (the emit
gate "does not re-open them"). They are stored on the anchor and otherwise unused this phase. This is
acceptable as forward-looking metadata, but the comment "the emit gate does not re-open them" means
the field is currently unverified provenance — worth flagging so a later phase does not assume it was
validated.
**Fix:** No code change required; consider a `# TODO(phase-7): verifier should re-open these` marker so
the unverified status is explicit.

### IN-03: Magic threshold literal duplicated between test and baseline

**File:** `tests/rulebook/test_absence.py:26`, `src/evals/baseline/absence_threshold.json:4`
**Issue:** `_OVER_EMIT_THRESHOLD = 0.04` is hardcoded in the test with a comment that the committed
`absence_threshold.json` holds "the tuned/recorded value" (also `0.04`). If the baseline is ratcheted,
the test's fixed `0.04` no longer tracks it, so the composition tests silently test a stale bar.
**Fix:** Have the behavior tests read the threshold from `absence_threshold.json` (as the generality
guard already does at line 115) rather than duplicating the literal, or clearly document that the test
bar is intentionally decoupled from the tunable baseline.

### IN-04: `ECFR_PARTS`/manifest section_counts are unenforced documentation

**File:** `rulebook/manifest.yaml:17,25,33,41,49,57,65`
**Issue:** Each eCFR row records a `section_count` (e.g. `part-211.xml` → 60) written at vendoring time.
No committed test re-parses the XML to confirm the count still matches the file, so a re-vendored XML
with a different section count would leave a stale `section_count` unnoticed. The `sha256` check in
`test_metadata.py` does guard the file bytes, so this is low-risk, but the derived count is not
independently verified.
**Fix:** Optional — add `assert len(parse_ecfr_sections(xml, part)) == row["section_count"]` to the
metadata test for rows that carry the field.

---

_Reviewed: 2026-08-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
