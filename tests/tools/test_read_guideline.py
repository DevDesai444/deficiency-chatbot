"""Tests for src/tools/read_guideline.py -- the 5th and final navigation tool (D-RI2 dual-mode
enumerate/fetch contract, TOOLS-01, TOOLS-04, RULES-05, COST-04). Phase 2 Plan 09.

Enumerate-mode tests build the SAME committed rulebook/** snapshot (ecfr + ich + fda) into the
local store + edges, mirroring tests/rulebook/test_requirement_index.py's
`_self_contained_rulebook_store` fixture exactly -- fully offline (D-RB6), zero network/Databricks.
Fetch-mode tests additionally resolve a REAL vendored citation ("21 CFR 211.166") end-to-end
(Plan 02-03's own vendored content) rather than a synthetic fixture, per this plan's own guidance.

RESOLVED (verification-queue item 5, requirement-index v2->v3): the REAL committed
`rulebook/requirement_index.yaml` uses subsection/topic-granular human-readable `citation`
strings (e.g. "21 CFR 211.166(a)", "ICH Q2(R2) -- Glossary: Specificity/Selectivity") that do NOT
exactly match `rulebook.store.lookup_citation`'s whole-document citation keys (e.g.
"21 CFR 211.166", "ICH Q2(R2)") -- so round-tripping a REAL enumerate row's `citation` into fetch
mode still 404s with `not_found`. The fix does NOT touch the reviewed `citation` strings; instead
each enumerate row now ALSO carries `rule_doc_id` (the entry's own `provenance_span_id.doc_id`,
already loader-gate-guaranteed to resolve), and fetch mode dual-resolves: `lookup_citation(arg)`
first (preserving the real whole-document citation path), then `rulebook_nt_for(arg)`-as-doc_id
as a fallback. `test_zero_translation_citation_round_trip` below still proves the CITATION path's
zero-translation contract with a controlled entry; the real-data 15/15 round trip via
`rule_doc_id` is proven end-to-end (through `emit_finding`) in
`tests/tools/test_enumerate_fetch_emit_e2e.py`.
"""
from __future__ import annotations

import functools

import pytest

import rulebook.requirement_index as ri
import tools.read_guideline as rg
from ingest.anchors import mint_span
from ingest.manifest import CoverageManifest, DocEntry
from rulebook.store import rulebook_nt_for
from schemas.documents import DocClassification
from tools import oversized
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.read_guideline import read_guideline

# --- shared fixtures ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _self_contained_rulebook_store():
    """Builds the real local rulebook store + edges once per test-module run (D-RB6), mirroring
    tests/rulebook/test_requirement_index.py's fixture of the same name. `update_manifest=False`
    on every build_* call: this fixture must NEVER rewrite the committed `rulebook/manifest.yaml`
    -- only `python -m rulebook.build` (a deliberate, reviewed vendoring step) may touch that file.
    """
    from rulebook.build import build_ecfr, build_fda, build_ich

    for rows in (
        build_ecfr(update_manifest=False),
        build_ich(update_manifest=False),
        build_fda(update_manifest=False),
    ):
        errors = [r for r in rows if "error" in r]
        assert not errors, f"rulebook build fixture hit vendoring errors: {errors}"
    ri.load_requirement_index.cache_clear()
    ri.build_requirement_edges()
    yield
    ri.load_requirement_index.cache_clear()


@pytest.fixture
def fresh_ledger() -> RetrievalLedger:
    return RetrievalLedger()


@pytest.fixture(autouse=True)
def _scratch_in_tmp(tmp_path, monkeypatch):
    """TOOLS-04 scratch descriptors must never leak into the real repo tree (mirrors
    tests/tools/test_oversized_results.py's discipline). `persist_range`/`load_range`/
    `advance_cursor`'s own `scratch_dir` default is bound into the function object at IMPORT
    time, so monkeypatching `tools.oversized.DEFAULT_SCRATCH_DIR` after the fact has no effect --
    and `monkeypatch.chdir` would ALSO relocate the rulebook store's own relative default paths
    (`data/rulebook_cache`, `data/defpredict.db`), breaking real-citation lookup. Instead,
    monkeypatch the THREE NAMES `read_guideline.py` itself imported, each bound to a
    tmp_path-scoped `scratch_dir` via `functools.partial`.
    """
    scratch_dir = str(tmp_path / "tool_scratch")
    monkeypatch.setattr(rg, "persist_range", functools.partial(oversized.persist_range, scratch_dir=scratch_dir))
    monkeypatch.setattr(rg, "load_range", functools.partial(oversized.load_range, scratch_dir=scratch_dir))
    monkeypatch.setattr(rg, "advance_cursor", functools.partial(oversized.advance_cursor, scratch_dir=scratch_dir))


def _doc_entry(family_guess: str, doc_id: str = "doc-1") -> DocEntry:
    return DocEntry(
        doc_id=doc_id, filename=f"{doc_id}.pdf", content_hash="deadbeef",
        classification=DocClassification(family_guess=family_guess),
    )


# --- Task 1: enumerate mode (citation=None) -----------------------------------------------------


def test_enumerate_mode_returns_compact_rows_without_rule_text(_self_contained_rulebook_store, fresh_ledger):
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3")])

    result = read_guideline(manifest, fresh_ledger, citation=None)

    assert isinstance(result, list)
    assert result, "expected at least one applicable requirement row for family 3.2.S.4.3"
    for row in result:
        assert set(row.keys()) == {"requirement_id", "citation", "rule_doc_id", "trigger"}
        assert isinstance(row["requirement_id"], str) and row["requirement_id"]
        assert isinstance(row["citation"], str) and row["citation"]
        assert isinstance(row["rule_doc_id"], str) and row["rule_doc_id"]
        assert isinstance(row["trigger"], str) and row["trigger"]
        # rule_doc_id (requirement-index v3, verification-queue item 5) must ITSELF resolve in
        # the rulebook store -- the whole point of adding it is a guaranteed-resolvable key.
        assert rulebook_nt_for(row["rule_doc_id"]) is not None


def test_enumerate_mode_family_filter_narrows_results(_self_contained_rulebook_store, fresh_ledger):
    # d1 -> direct family match (3.2.S.4.3's 10 entries); d2 (3.2.P.1) -> drug_product profile
    # closure -> 3.2.P.7 required -> CFR-211166-STABILITY-PROGRAM also fires (D-RB4 UNION).
    manifest = CoverageManifest(documents=[_doc_entry("3.2.S.4.3", "d1"), _doc_entry("3.2.P.1", "d2")])

    unfiltered = read_guideline(manifest, fresh_ledger, citation=None)
    filtered = read_guideline(manifest, fresh_ledger, citation=None, family="3.2.S.4.3")

    assert isinstance(unfiltered, list) and isinstance(filtered, list)
    assert len(filtered) < len(unfiltered)
    assert filtered, "expected at least one 3.2.S.4.3 entry"
    filtered_ids = {row["requirement_id"] for row in filtered}
    unfiltered_ids = {row["requirement_id"] for row in unfiltered}
    assert filtered_ids <= unfiltered_ids
    assert "CFR-211166-STABILITY-PROGRAM" not in filtered_ids  # that entry's family is 3.2.P.7


def test_enumerate_mode_rejects_invalid_family_filter(fresh_ledger):
    """The SAME rejection enumerate_requirements already produces (D-RI2(2)) -- no store build
    needed since the family-registry check runs before any rulebook-store access."""
    manifest = CoverageManifest()

    result = read_guideline(manifest, fresh_ledger, citation=None, family="not-a-real-family")

    assert isinstance(result, ToolRejected)
    assert result.tool == "read_guideline"
    assert result.reason_code == "family_not_in_registry"


def test_zero_translation_citation_round_trip(monkeypatch, fresh_ledger):
    """D-RI2(3)/D-EF1(5): read_guideline's OWN code performs zero translation -- an enumerate
    row's `citation` value flows into a fetch-mode call completely unmodified. Proven with a
    controlled entry (monkeypatched enumerate_requirements) whose citation format aligns with a
    real rulebook-store key ("21 CFR 211.166", Plan 02-03's vendored content) -- isolating
    read_guideline's own round-trip mechanics from the real requirement_index.yaml's current
    citation-granularity mismatch (see this module's docstring)."""
    from rulebook.build import build_ecfr

    errors = [r for r in build_ecfr(update_manifest=False) if "error" in r]
    assert not errors, f"ecfr build fixture hit vendoring errors: {errors}"

    dummy_span = mint_span("Written stability testing procedures.", 0, 10, "ecfr-211.166", "v1")
    fake_entry = ri.RequirementEntry(
        id="TEST-ROUNDTRIP", family="3.2.P.7", citation="21 CFR 211.166",
        trigger="test trigger", provenance_span_id=dummy_span,
    )
    monkeypatch.setattr(rg, "enumerate_requirements", lambda manifest, family=None: [fake_entry])

    rows = read_guideline(CoverageManifest(), fresh_ledger, citation=None)
    assert rows == [{
        "requirement_id": "TEST-ROUNDTRIP", "citation": "21 CFR 211.166",
        "rule_doc_id": "ecfr-211.166", "trigger": "test trigger",
    }]

    fetch_result = read_guideline(CoverageManifest(), fresh_ledger, citation=rows[0]["citation"])
    assert isinstance(fetch_result, str)  # NOT a ToolRejected -- zero translation held
    assert not fetch_result.startswith("[STILL_CURRENT]")


def test_rule_doc_id_fallback_resolves_when_citation_has_no_store_match(monkeypatch, fresh_ledger):
    """The verification-queue item 5 fix's OTHER half: an enumerate row whose `citation` is
    subsection-granular (does NOT match any `lookup_citation` key -- exactly the real
    requirement_index.yaml's shape) still resolves in fetch mode via its `rule_doc_id`."""
    from rulebook.build import build_ecfr

    errors = [r for r in build_ecfr(update_manifest=False) if "error" in r]
    assert not errors, f"ecfr build fixture hit vendoring errors: {errors}"

    dummy_span = mint_span("Written stability testing procedures.", 0, 10, "ecfr-211.166", "v1")
    fake_entry = ri.RequirementEntry(
        id="TEST-SUBSECTION", family="3.2.P.7",
        citation="21 CFR 211.166(a)",  # subsection-granular -- NOT a real lookup_citation key
        trigger="test trigger", provenance_span_id=dummy_span,
    )
    monkeypatch.setattr(rg, "enumerate_requirements", lambda manifest, family=None: [fake_entry])

    rows = read_guideline(CoverageManifest(), fresh_ledger, citation=None)
    assert rows == [{
        "requirement_id": "TEST-SUBSECTION", "citation": "21 CFR 211.166(a)",
        "rule_doc_id": "ecfr-211.166", "trigger": "test trigger",
    }]

    # round-tripping the display `citation` still 404s (subsection granularity, unchanged data) --
    # this is the honest, still-true half of the pre-fix behavior.
    citation_result = read_guideline(CoverageManifest(), fresh_ledger, citation=rows[0]["citation"])
    assert isinstance(citation_result, ToolRejected)
    assert citation_result.reason_code == "not_found"

    # but the NEW `rule_doc_id` field resolves -- this is the fix.
    doc_id_result = read_guideline(CoverageManifest(), fresh_ledger, citation=rows[0]["rule_doc_id"])
    assert isinstance(doc_id_result, str)
    assert doc_id_result.startswith("[ecfr-211.166:")


# --- Task 2: fetch mode (citation=<string>) -----------------------------------------------------


@pytest.fixture(scope="module")
def _ecfr_store():
    """Fetch-mode tests only need the eCFR half of the vendored snapshot ("21 CFR 211.166")."""
    from rulebook.build import build_ecfr

    errors = [r for r in build_ecfr(update_manifest=False) if "error" in r]
    assert not errors, f"ecfr build fixture hit vendoring errors: {errors}"
    yield


def test_fetch_mode_resolves_real_citation_and_annotates_with_span_ids(_ecfr_store, fresh_ledger):
    result = read_guideline(CoverageManifest(), fresh_ledger, citation="21 CFR 211.166")

    assert isinstance(result, str)
    assert not result.startswith("[STILL_CURRENT]")
    assert result.startswith("[ecfr-211.166:")
    assert "stability" in result.lower()


def test_fetch_mode_unresolvable_citation_returns_not_found(_ecfr_store, fresh_ledger):
    result = read_guideline(CoverageManifest(), fresh_ledger, citation="not a real citation")

    assert isinstance(result, ToolRejected)
    assert result.tool == "read_guideline"
    assert result.reason_code == "not_found"


def test_fetch_mode_repeat_read_returns_still_current_stub(_ecfr_store, fresh_ledger):
    first = read_guideline(CoverageManifest(), fresh_ledger, citation="21 CFR 211.166")
    assert isinstance(first, str)
    assert not first.startswith("[STILL_CURRENT]")

    second = read_guideline(CoverageManifest(), fresh_ledger, citation="21 CFR 211.166")
    assert isinstance(second, str)
    assert second.startswith("[STILL_CURRENT]")
    assert fresh_ledger.dedup_hit_rate() > 0


def test_oversized_citation_persist_preview_handle_pages_forward(_ecfr_store, fresh_ledger):
    """plan-checker Blocker 2: an oversized citation-mode fetch is NEVER truncated -- it persists
    the full range under a handle and hands back a bounded, annotated preview, exactly like
    get_section's own oversized branch."""
    rejected = read_guideline(CoverageManifest(), fresh_ledger, citation="21 CFR 211.166", max_chars=200)

    assert isinstance(rejected, ToolRejected)
    assert rejected.reason_code == "range_too_large"
    assert rejected.preview != ""
    assert rejected.handle != ""
    assert len(rejected.preview) < 2213  # bounded -- less than the whole section's canonical length

    continued = read_guideline(CoverageManifest(), fresh_ledger, handle=rejected.handle, max_chars=200)
    assert isinstance(continued, str)          # a NEW bounded chunk -- not a re-served preview
    assert continued != rejected.preview
    assert continued.startswith("[ecfr-211.166:")  # still span-ID-annotated (D-GRAN)

    unknown = read_guideline(CoverageManifest(), fresh_ledger, handle="read_guideline:no-such-doc:0:1")
    assert isinstance(unknown, ToolRejected)
    assert unknown.reason_code == "not_found"


def test_oversized_citation_and_handle_kwarg_together_pages_forward(_ecfr_store, fresh_ledger):
    """Calling with BOTH the same oversized citation AND the handle also pages forward (behavior
    spec's alternate call shape) -- handle short-circuits dispatch regardless of citation."""
    rejected = read_guideline(CoverageManifest(), fresh_ledger, citation="21 CFR 211.166", max_chars=200)
    assert isinstance(rejected, ToolRejected)

    continued = read_guideline(
        CoverageManifest(), fresh_ledger, citation="21 CFR 211.166", handle=rejected.handle, max_chars=200,
    )
    assert isinstance(continued, str)
    assert continued != rejected.preview
