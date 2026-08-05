"""Boundary-crossing composition test -- Phase-2 verification-queue item 5 (MATERIAL).

Every other test in this suite proves ONE tool's own contract in isolation (green unit tests on
each side of `read_guideline`/`emit_finding`). That is exactly the class of test whose absence
let the real citation<->store granularity mismatch ship undetected in 02-09: `read_guideline`'s
fetch mode was proven correct against a CONTROLLED entry, and `enumerate_requirements` was proven
correct against the real index -- but nothing drove the REAL, committed
`rulebook/requirement_index.yaml`'s 15 entries all the way through
`enumerate_requirements -> read_guideline(rule_doc_id) -> emit_finding` in one composed test.

This module is that missing boundary-crossing test: fully offline (D-RB6), built from the real
committed `rulebook/**` snapshot (mirroring `tests/rulebook/test_requirement_index.py`'s
`_self_contained_rulebook_store` fixture), asserting the FULL chain resolves 25/25 (Phase 4
grew the real committed index 15 -> 25 entries; RULES-06).
"""
from __future__ import annotations

import re

import pytest

import rulebook.requirement_index as ri
from ingest.anchors import mint_span
from ingest.manifest import CoverageManifest, DocEntry
from rulebook.store import rulebook_nt_for
from schemas.documents import DocClassification
from tests.tools.conftest import build_corpus_index
from tools.emit_finding import emit_finding
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.read_guideline import read_guideline

_SPAN_RE = re.compile(r"^\[([^:\]]+):(\d+):(\d+)\]")


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


def _doc_entry(family_guess: str, doc_id: str) -> DocEntry:
    return DocEntry(
        doc_id=doc_id, filename=f"{doc_id}.pdf", content_hash="deadbeef",
        classification=DocClassification(family_guess=family_guess),
    )


# The real requirement_index.yaml's 25 entries span exactly 6 families (verified directly against
# the committed file after the Phase-4 RULES-06 enrichment): 3.2.S.4.3 (10), 3.2.S.4.1 (5),
# 3.2.P.5 (4), 3.2.P.7 (3), 3.2.S.5 (2), 3.2.S.7 (1). A manifest classifying one document into each
# of the 6 families makes all 25 fire via DIRECT family match (D-RB4) -- no profile-closure edge
# needed for this particular set.
_ALL_ENTRIES_MANIFEST = CoverageManifest(
    documents=[
        _doc_entry("3.2.S.4.3", "d1"),
        _doc_entry("3.2.S.4.1", "d2"),
        _doc_entry("3.2.S.5", "d3"),
        _doc_entry("3.2.P.7", "d4"),
        _doc_entry("3.2.P.5", "d5"),
        _doc_entry("3.2.S.7", "d6"),
    ]
)


def test_enumerate_fetch_emit_25_of_25_resolve_end_to_end(_self_contained_rulebook_store, tmp_path):
    """The mandatory composition test: enumerate_requirements -> for EACH of the 25 real,
    applicable requirement-index entries -> read_guideline(rule_doc_id) resolves (not
    ToolRejected) and returns >=1 issued span-ID -> that span-ID passes emit_finding's
    retrieval-ledger + store-membership checks. Asserts 25/25 end-to-end."""
    ledger = RetrievalLedger()

    entries = ri.enumerate_requirements(_ALL_ENTRIES_MANIFEST)
    assert not isinstance(entries, ToolRejected)
    assert len(entries) == 25, (
        f"expected all 25 real requirement-index entries to fire for this manifest, "
        f"got {len(entries)}: {sorted(e.id for e in entries)}"
    )

    rows = read_guideline(_ALL_ENTRIES_MANIFEST, ledger, citation=None)
    assert isinstance(rows, list)
    assert len(rows) == 25
    for row in rows:
        assert set(row.keys()) == {"requirement_id", "citation", "rule_doc_id", "trigger"}

    # A real, persisted single-document submission corpus (Phase-1 substrate, via the shared
    # tests/tools/conftest.py builder) -- emit_finding validates BOTH the submission span and the
    # rule span, so a genuine submission-side span is needed even though this test's focus is the
    # RULE side of the gate.
    submission_text = "The laboratory's written stability testing program covers all conditions."
    corpus = build_corpus_index(
        tmp_path, "sub-doc",
        [{"text": submission_text, "page": 1, "reading_order": 0, "lines": []}],
    )
    sub_cache = corpus.cached_entry("sub-doc")
    sub_start = sub_cache["canonical"].index("stability testing program")
    sub_end = sub_start + len("stability testing program")
    submission_span = mint_span(
        sub_cache["canonical"], sub_start, sub_end, "sub-doc", sub_cache["normalizer_version"],
    )
    ledger.record_span(submission_span)

    resolved: list[str] = []
    rejected: list[tuple[str, str, str]] = []
    # Two real entries (CFR-211194-METHOD-IDENTIFICATION, CFR-211194-CALCULATIONS) share the SAME
    # rule_doc_id (ecfr-211.194) -- a whole-document fetch is the SAME (doc_id,0,len) range both
    # times, so the SECOND fetch legitimately hits COST-04's read-dedup and returns a
    # "[STILL_CURRENT]" stub instead of re-rendering. That is correct tool behavior, not a
    # resolution failure -- the span from the FIRST fetch is still present in the ledger, so this
    # test reuses it for any later entry sharing the same rule_doc_id.
    span_by_doc_id: dict[str, tuple[str, int, int]] = {}
    for row in rows:
        requirement_id, rule_doc_id = row["requirement_id"], row["rule_doc_id"]

        # max_chars set generously large: several real rulebook chunks (ich-Q2-R2, ich-Q6A,
        # fda-analytical-procedures) exceed the default 8000-char bound -- this test asserts
        # RESOLUTION, not pagination behavior (that's test_oversized_citation_... elsewhere).
        fetch_result = read_guideline(_ALL_ENTRIES_MANIFEST, ledger, citation=rule_doc_id, max_chars=200_000)
        if isinstance(fetch_result, ToolRejected):
            rejected.append((requirement_id, rule_doc_id, f"read_guideline: {fetch_result.reason_code}"))
            continue
        assert isinstance(fetch_result, str)

        if fetch_result.startswith("[STILL_CURRENT]"):
            assert rule_doc_id in span_by_doc_id, f"{rule_doc_id}: STILL_CURRENT with no prior span recorded"
            span_doc_id, span_start, span_end = span_by_doc_id[rule_doc_id]
        else:
            m = _SPAN_RE.search(fetch_result)
            assert m, f"{rule_doc_id}: no annotated [doc_id:start:end] span found in fetch result"
            span_doc_id, span_start, span_end = m.group(1), int(m.group(2)), int(m.group(3))
            span_by_doc_id[rule_doc_id] = (span_doc_id, span_start, span_end)

        nt = rulebook_nt_for(span_doc_id)
        assert nt is not None, f"{rule_doc_id}: rulebook_nt_for({span_doc_id!r}) unexpectedly None"
        rule_span = mint_span(nt.canonical, span_start, span_end, span_doc_id, nt.normalizer_version)
        assert ledger.was_issued(rule_span), f"{rule_doc_id}: span not recorded in the ledger by read_guideline"

        result = emit_finding(
            corpus=corpus, submission_span_id=submission_span, rule_span_id=rule_span,
            ledger=ledger, verdict="violation",
            requirement_id=requirement_id, rule_citation=row["citation"],
        )
        if isinstance(result, ToolRejected):
            rejected.append((requirement_id, rule_doc_id, f"emit_finding: {result.reason_code}"))
        else:
            resolved.append(requirement_id)

    assert not rejected, f"expected 25/25 to resolve end-to-end, but these did not: {rejected}"
    assert len(resolved) == 25
    assert set(resolved) == {row["requirement_id"] for row in rows}


def test_real_store_citation_path_still_resolves_via_lookup_citation(_self_contained_rulebook_store):
    """Regression guard (fix priority item 2): the pre-existing whole-document `lookup_citation`
    path must still work after the dual-resolve fix -- `lookup_citation(arg)` is tried FIRST, so
    a real store citation like "21 CFR 211.166" is never routed through the rule_doc_id
    fallback."""
    ledger = RetrievalLedger()

    result = read_guideline(CoverageManifest(), ledger, citation="21 CFR 211.166")

    assert isinstance(result, str)
    assert not result.startswith("[STILL_CURRENT]")
    assert result.startswith("[ecfr-211.166:")
    assert "stability" in result.lower()
