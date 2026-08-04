"""T1+T2 (v3.1) boundary-crossing composition test S5 never had.

run_oracles_tool END-TO-END on the REAL scored corpus (mvr1381 + minispec, built through the
production ingest path) MUST surface at least one lead whose text names a protected TP the v2
runs lost: C-01's `11477`, C-02's `0.15`, or B-08's `Any Unspecified Impurity`. If it fires on
none, T1 (table reconstruction) + T2 (numeric_cross_reference / expected_row_absent) have not
solved the problem the scored runs are supposed to test.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from agents.review.oracles_tool import run_oracles_tool
from evals.schema import load_eval_set
from ingest.corpus import ingest_corpus
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger

_TARGETS = ("11477", "0.15", "Any Unspecified Impurity")


@pytest.fixture(scope="module")
def scored_corpus():
    eval_set = load_eval_set()
    tmp = tempfile.mkdtemp(prefix="oracle-real-corpus-")
    root = Path(tmp)
    try:
        for doc in eval_set.documents:
            if doc.held_out:
                continue
            shutil.copy2(Path(doc.path), root / Path(doc.path).name)
        yield ingest_corpus(root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _lead_text(lead: dict) -> str:
    return " ".join(
        str(lead.get(k, ""))
        for k in ("claim", "quoted_text", "expected_element", "scope_searched", "check", "next_call")
    )


def test_oracles_surface_all_three_protected_tp_leads_on_the_real_corpus(scored_corpus):
    leads: list[dict] = []
    for entry in scored_corpus.manifest.documents:
        result = run_oracles_tool(scored_corpus, entry.doc_id, RetrievalLedger())
        assert not isinstance(result, ToolRejected), result
        leads.extend(result["positive_leads"])
        leads.extend(result["absence_leads"])

    fired = {t.lower() for t in _TARGETS for lead in leads if t.lower() in _lead_text(lead).lower()}
    missing = {t.lower() for t in _TARGETS} - fired
    # v3.2: ALL THREE must appear across the two docs' leads (C-01 11477, C-02 0.15,
    # B-08 "Any Unspecified Impurity"), not just one.
    assert not missing, (
        f"oracle leads missing targets {sorted(missing)}; "
        f"{len(leads)} leads surfaced: {[_lead_text(l)[:90] for l in leads]}"
    )
