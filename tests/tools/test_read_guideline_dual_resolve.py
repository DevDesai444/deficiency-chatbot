"""R1 (03-19 remediation) composition test the suite lacked.

The 03-19 NO-GO root cause: an enumerate row's `citation` is a rich display string that
resolved 0/15 in fetch mode, so the model's `read_guideline(citation=row['citation'])`
calls returned `not_found`, cascading to breaker/DR early stops. R1 adds a third resolve
leg (the requirement-index citation-display -> provenance doc_id map). This test rounds
BOTH identifiers each enumerate row advertises -- `row['citation']` AND `row['rule_doc_id']`
-- through fetch mode for ALL 15 real requirement-index entries: **30/30 must resolve to
rule text carrying span-IDs, or the build is red.** Built from the real committed
`rulebook/**` snapshot (D-RB6), mirroring `tests/tools/test_enumerate_fetch_emit_e2e.py`.
"""
from __future__ import annotations

import re

import pytest

import rulebook.requirement_index as ri
from ingest.manifest import CoverageManifest, DocEntry
from schemas.documents import DocClassification
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.read_guideline import read_guideline

_SPAN_RE = re.compile(r"\[([^:\]]+):(\d+):(\d+)\]")


@pytest.fixture(scope="module")
def _self_contained_rulebook_store():
    from rulebook.build import build_ecfr, build_fda, build_ich

    for rows in (build_ecfr(update_manifest=False), build_ich(update_manifest=False),
                 build_fda(update_manifest=False)):
        errors = [r for r in rows if "error" in r]
        assert not errors, f"rulebook build fixture hit vendoring errors: {errors}"
    ri.load_requirement_index.cache_clear()
    ri.build_requirement_edges()
    yield
    ri.load_requirement_index.cache_clear()


def _doc(fam: str, did: str) -> DocEntry:
    return DocEntry(doc_id=did, filename=f"{did}.pdf", content_hash="deadbeef",
                    classification=DocClassification(family_guess=fam))


# Same 4-family manifest as the e2e test -> all 15 real entries fire.
_ALL_15_MANIFEST = CoverageManifest(documents=[
    _doc("3.2.S.4.3", "d1"), _doc("3.2.S.4.1", "d2"),
    _doc("3.2.S.5", "d3"), _doc("3.2.P.7", "d4"),
])


def test_all_15_rows_round_trip_both_citation_and_rule_doc_id_30_of_30(_self_contained_rulebook_store):
    rows = read_guideline(_ALL_15_MANIFEST, RetrievalLedger(), citation=None)
    assert isinstance(rows, list) and len(rows) == 15, f"expected 15 enumerate rows, got {rows}"

    resolved = 0
    failures: list[tuple[str, str, str]] = []
    for row in rows:
        for key in ("citation", "rule_doc_id"):
            # Fresh ledger per resolve so the COST-04 served-dedup never returns a
            # [STILL_CURRENT] stub (two entries share ecfr-211.194); we require rendered
            # rule text with span-IDs on every leg.
            res = read_guideline(_ALL_15_MANIFEST, RetrievalLedger(), citation=row[key], max_chars=200_000)
            if isinstance(res, ToolRejected):
                failures.append((row["requirement_id"], key, f"{res.reason_code}"))
                continue
            if not (isinstance(res, str) and _SPAN_RE.search(res)):
                failures.append((row["requirement_id"], key, "no span-ID in fetch result"))
                continue
            resolved += 1

    assert not failures, f"expected 30/30 to resolve; failures: {failures}"
    assert resolved == 30


def test_display_citation_leg_is_what_was_added(_self_contained_rulebook_store):
    """Direct proof of the R1 third leg: a rich display `citation` (which is neither a
    store citation key nor a doc_id) now resolves to rule text with a span-ID."""
    rows = read_guideline(_ALL_15_MANIFEST, RetrievalLedger(), citation=None)
    display = rows[0]["citation"]
    res = read_guideline(_ALL_15_MANIFEST, RetrievalLedger(), citation=display, max_chars=200_000)
    assert isinstance(res, str) and _SPAN_RE.search(res), f"display citation {display!r} did not resolve: {res}"


def test_unresolvable_citation_rejection_teaches_the_recovery_path():
    """The not_found message must redirect the model (run 2 retried the identical failing
    call 4x): enumerate first, then pass a rule_doc_id; and do not retry the same call."""
    res = read_guideline(_ALL_15_MANIFEST, RetrievalLedger(), citation="totally-not-a-real-citation-xyz")
    assert isinstance(res, ToolRejected) and res.reason_code == "not_found"
    hint = res.hint.lower()
    assert "read_guideline with no arguments" in hint
    assert "rule_doc_id" in hint
    assert "do not retry" in hint
