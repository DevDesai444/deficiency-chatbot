from __future__ import annotations

import json
from pathlib import Path

from agents.review.loop import ReviewResult
from agents.review.telemetry import TurnLog
from evals.capture import load_captured
from evals.run import build_parser, main
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest, DocEntry
from schemas.events import AgentEvent
from schemas.faults import Fault, FaultReport
from evals.schema import Confidence, EvalDocument, EvalSet, FailureFamily, GroundTruthDeficiency


def _eval_set(tmp_path: Path) -> EvalSet:
    scored_pdf = tmp_path / "scored.pdf"
    scored_docx = tmp_path / "scored.docx"
    held_out = tmp_path / "heldout.pdf"
    scored_pdf.write_bytes(b"%PDF scored")
    scored_docx.write_bytes(b"docx scored")
    held_out.write_bytes(b"%PDF held out")
    return EvalSet(
        documents=[
            EvalDocument(doc_id="d1", path=str(scored_pdf), format="pdf", held_out=False),
            EvalDocument(doc_id="d2", path=str(scored_docx), format="docx", held_out=False),
            EvalDocument(doc_id="held", path=str(held_out), format="pdf", held_out=True),
        ],
        deficiencies=[
            GroundTruthDeficiency(
                id="T-01",
                doc_id="d1",
                title="Synthetic scored issue",
                evidence_anchor="12345",
                failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
                confidence=Confidence.CERTAIN,
            ),
            GroundTruthDeficiency(
                id="H-01",
                doc_id="held",
                title="Held-out issue",
                evidence_anchor="12345",
                failure_family=FailureFamily.ABSENCE_OF_EVIDENCE,
                confidence=Confidence.CERTAIN,
            ),
        ],
    )


def _install_offline_agent_run(monkeypatch, tmp_path: Path, *, fail: bool = False) -> dict:
    import agents.review
    import agents.review.budget
    import agents.review.registry
    import agents.review.telemetry
    import config
    import evals.run
    import ingest.corpus
    import llm.client
    import tools.ledger

    state: dict = {
        "budget_ids": [],
        "ledger_ids": [],
        "telemetry_ids": [],
        "ingested_files": [],
        "models": [],
        "run_review_calls": [],
    }
    eval_set = _eval_set(tmp_path)
    monkeypatch.setattr(evals.run, "load_eval_set", lambda: eval_set)

    def resolve(model):
        state["models"].append(model)
        return "resolved-detector"

    monkeypatch.setattr(config, "resolve_detector_model", resolve)
    monkeypatch.setattr(agents.review.telemetry, "resolve_detector_model", lambda model: model or "resolved-detector")
    monkeypatch.setattr(llm.client, "chat_completion_tools", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("LLM reached")))

    class TrackingBudget(agents.review.budget.BudgetLedger):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            state["budget_ids"].append(id(self))

    class TrackingLedger(tools.ledger.RetrievalLedger):
        def __init__(self):
            super().__init__()
            state["ledger_ids"].append(id(self))

    class TrackingTurnLog(TurnLog):
        def __init__(self, path):
            super().__init__(path)
            state["telemetry_ids"].append(id(self))

    def fake_ingest(root):
        state["ingested_files"] = sorted(p.name for p in Path(root).iterdir())
        entries = [
            DocEntry(doc_id=f"raw{i}", filename=name, content_hash=f"hash{i}")
            for i, name in enumerate(state["ingested_files"], start=1)
        ]
        return CorpusIndex(
            root=str(root),
            cache_dir=str(tmp_path / "cache"),
            manifest=CoverageManifest(documents=entries, counts={"parsed": len(entries)}),
        )

    def fake_run_review(corpus, manifest, ledger, budget, telemetry, complete, registry, job_id=""):
        state["run_review_calls"].append(
            {
                "corpus": corpus,
                "manifest": manifest,
                "ledger": ledger,
                "budget": budget,
                "telemetry": telemetry,
                "registry": registry,
                "job_id": job_id,
            }
        )
        if fail:
            raise RuntimeError("scripted mid-run failure")
        report = FaultReport(
            faults=[Fault(title="Synthetic", evidence="12345")],
            faults_found=True,
            stop_reason="completed",
        )
        return ReviewResult(findings=report.faults, stop_reason="completed", report=report)

    monkeypatch.setattr(agents.review.budget, "BudgetLedger", TrackingBudget)
    monkeypatch.setattr(tools.ledger, "RetrievalLedger", TrackingLedger)
    monkeypatch.setattr(agents.review.telemetry, "TurnLog", TrackingTurnLog)
    monkeypatch.setattr(ingest.corpus, "ingest_corpus", fake_ingest)
    monkeypatch.setattr(agents.review, "run_review", fake_run_review)
    return state


def test_agent_run_is_registered_in_help():
    help_text = build_parser().format_help()
    assert "agent-run" in help_text


def test_unknown_model_routes_through_resolver_and_artifacts_round_trip(monkeypatch, tmp_path):
    state = _install_offline_agent_run(monkeypatch, tmp_path)
    out_dir = tmp_path / "out"

    code = main(
        [
            "agent-run",
            "--model",
            "not-a-real-model",
            "--run-index",
            "1",
            "--max-tokens",
            "1000",
            "--max-wall-clock",
            "60",
            "--out-dir",
            str(out_dir),
        ]
    )

    assert code == 0
    assert state["models"] == ["not-a-real-model"]
    assert state["ingested_files"] == ["scored.docx", "scored.pdf"]
    assert len(set(state["budget_ids"])) == 1
    assert len(set(state["ledger_ids"])) == 1
    assert len(set(state["telemetry_ids"])) == 1
    assert {doc.doc_id for doc in state["run_review_calls"][0]["manifest"].documents} == {"d1", "d2"}

    assert sorted(p.name for p in out_dir.iterdir()) == [
        "agent-run1-summary.json",
        "agent-run1.json",
        "agent-run1.jsonl",
    ]
    assert isinstance(load_captured(out_dir / "agent-run1.json"), FaultReport)
    summary = json.loads((out_dir / "agent-run1-summary.json").read_text())
    assert summary["provenance"]["run_completed"] is True
    assert summary["provenance"]["found_set"] == ["T-01"]
    assert "model_time_s" in summary
    assert "tool_execution_time_s" in summary
    assert "embedding_time_s" in summary


def test_non_default_prefix_never_writes_agent_run_files(monkeypatch, tmp_path):
    _install_offline_agent_run(monkeypatch, tmp_path)
    out_dir = tmp_path / "out"

    code = main(
        [
            "agent-run",
            "--run-index",
            "1",
            "--run-prefix",
            "probe-",
            "--max-tokens",
            "1000",
            "--max-wall-clock",
            "60",
            "--out-dir",
            str(out_dir),
        ]
    )

    assert code == 0
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "probe-1-summary.json",
        "probe-1.json",
        "probe-1.jsonl",
    ]
    assert not list(out_dir.glob("agent-run*"))


def test_held_out_split_assembles_only_held_out_documents(monkeypatch, tmp_path):
    state = _install_offline_agent_run(monkeypatch, tmp_path)
    out_dir = tmp_path / "out"

    code = main(
        [
            "agent-run",
            "--run-index",
            "1",
            "--run-prefix",
            "calibration-run",
            "--document-split",
            "held-out",
            "--max-tokens",
            "1000",
            "--max-wall-clock",
            "60",
            "--out-dir",
            str(out_dir),
        ]
    )

    assert code == 0
    assert state["ingested_files"] == ["heldout.pdf"]
    assert [doc.doc_id for doc in state["run_review_calls"][0]["manifest"].documents] == ["held"]
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "calibration-run1-summary.json",
        "calibration-run1.json",
        "calibration-run1.jsonl",
    ]


def test_agent_run_failure_still_writes_aborted_artifacts(monkeypatch, tmp_path):
    _install_offline_agent_run(monkeypatch, tmp_path, fail=True)
    out_dir = tmp_path / "out"

    code = main(
        [
            "agent-run",
            "--run-index",
            "2",
            "--max-tokens",
            "1000",
            "--max-wall-clock",
            "60",
            "--out-dir",
            str(out_dir),
        ]
    )

    assert code == 1
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "agent-run2-summary.json",
        "agent-run2.json",
        "agent-run2.jsonl",
    ]
    summary = json.loads((out_dir / "agent-run2-summary.json").read_text())
    assert summary["provenance"]["run_completed"] is False
    assert "scripted mid-run failure" in summary["provenance"]["abort_reason"]


def test_agent_run_source_never_routes_through_dropping_passes():
    source = Path("src/evals/run.py").read_text()
    body = source.split("def cmd_agent_run", 1)[1].split("def build_parser", 1)[0]
    assert "verify_and_tier" not in body
    assert "challenge_faults" not in body


def test_review_event_schema_is_additive_and_payloads_are_metadata_only():
    existing = [
        "pipeline_start",
        "layer_start",
        "agent_spawned",
        "agent_message",
        "selection",
        "oracle_complete",
        "layer_complete",
        "pipeline_complete",
        "error",
    ]
    added = ["agent_turn", "tool_call", "budget_update", "continuation"]
    for event_type in existing:
        AgentEvent(job_id="", layer="detection", event_type=event_type)
    for event_type in added:
        AgentEvent(job_id="", layer="review", event_type=event_type, metadata={"turn": 1})

    event = AgentEvent(
        job_id="",
        layer="review",
        event_type="tool_call",
        message="Tool call dispatched",
        metadata={"tool": "search_corpus"},
    )
    payload = event.model_dump_json()
    assert "document text" not in payload
    assert "arguments" not in payload
    assert "results" not in payload
