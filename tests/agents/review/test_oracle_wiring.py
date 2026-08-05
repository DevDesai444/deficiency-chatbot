"""U1/U2/U3 (v3.3): fix the oracle-engagement wiring that made v3.2's summary read 0/0/0.

U1 - the tracker checked isinstance(raw_result, list) but run_oracles_tool returns a DICT.
U2 - the coverage reminder kept telling the model to CALL a tool it had already called.
U3 - the absence lead's next_call cited a nonsense 'read_guideline enumerate' string.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from agents.review.loop import _coverage_reminder, _record_dispatch_telemetry
from agents.review.oracles_tool import run_oracles_tool
from agents.review.registry import DispatchResult
from agents.review.telemetry import RunSummary, TurnLog, capture_provenance, read_turns
from evals.schema import load_eval_set
from ingest.corpus import ingest_corpus
from ingest.manifest import CoverageManifest, DocEntry
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.read_guideline import read_guideline


def test_u1_run_oracles_dict_return_is_tracked(tmp_path):
    telemetry = TurnLog(tmp_path / "t.jsonl")
    result = DispatchResult(
        result="", turn_consumed=True, repair_layer="none", tool="run_oracles",
        raw_result={"positive_leads": [{}, {}], "absence_leads": [{}], "leads_surfaced": 3},
    )
    _record_dispatch_telemetry(telemetry, result)
    records, _ = read_turns(tmp_path / "t.jsonl")
    summary = RunSummary.from_turns(
        provenance=capture_provenance(run_index=1, corpus_content_hash="x", run_completed=True),
        records=records,
    )
    assert summary.oracle_leads_surfaced == 3  # was 0 under the isinstance(list) bug


def test_u2_reminder_flags_called_but_none_reopened():
    manifest = CoverageManifest(documents=[DocEntry(doc_id="d1", filename="d1.pdf", content_hash="x")])

    class _Ledger:
        _issued = {("d1", 0, 5)}

    msg, _u, _c = _coverage_reminder(
        manifest, _Ledger(), [], oracle_called=True, oracle_leads_surfaced=3, oracle_reopens=0
    )
    assert "surfaced 3 leads, none re-opened" in msg
    assert "run_oracles has not been called" not in msg  # it WAS called


def test_u2_reminder_silent_on_oracle_once_a_lead_is_reopened():
    manifest = CoverageManifest(documents=[DocEntry(doc_id="d1", filename="d1.pdf", content_hash="x")])

    class _Ledger:
        _issued = {("d1", 0, 5)}

    result = _coverage_reminder(
        manifest, _Ledger(), [], oracle_called=True, oracle_leads_surfaced=3, oracle_reopens=1
    )
    # d1 opened, no finding still triggers a reminder, but NOT the oracle lines
    if result is not None:
        assert "none re-opened" not in result[0]
        assert "has not been called" not in result[0]


@pytest.fixture(scope="module")
def _mvr1381():
    es = load_eval_set()
    tmp = tempfile.mkdtemp(prefix="oracle-wiring-")
    root = Path(tmp)
    try:
        for d in es.documents:
            if not d.held_out:
                shutil.copy2(Path(d.path), root / Path(d.path).name)
        corpus = ingest_corpus(root)
        entry = next(e for e in corpus.manifest.documents if "32s43" in e.filename)
        yield corpus, entry.doc_id
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_u3_b08_absence_lead_next_call_cites_a_resolvable_rule(_mvr1381):
    corpus, doc_id = _mvr1381
    result = run_oracles_tool(corpus, doc_id, RetrievalLedger())
    b08 = [l for l in result["absence_leads"] if "unspecified impurity" in str(l).lower()]
    assert b08, f"expected an absence lead for 'Any Unspecified Impurity'; absence_leads={result['absence_leads']}"
    lead = b08[0]
    assert lead["kind"] == "absence"
    assert "read_guideline enumerate" not in lead["next_call"]  # the old nonsense citation
    assert "21 CFR 211.194" in lead["next_call"]
    # the cited rule actually resolves via the triple-resolve
    r = read_guideline(CoverageManifest(), RetrievalLedger(), citation="21 CFR 211.194")
    assert not isinstance(r, ToolRejected) and isinstance(r, str) and r.startswith("[ecfr-211.194:")
