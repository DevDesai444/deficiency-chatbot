from __future__ import annotations

import json

import pytest

from agents.review.telemetry import RunSummary, TurnLog, _git_sha_of, capture_provenance, read_turns


def _provenance(**overrides):
    data = capture_provenance(
        run_index=1,
        model_id="databricks-meta-llama-3-3-70b-instruct",
        corpus_content_hash="corpus-sha",
        run_completed=True,
    )
    data.update(overrides)
    return data


def test_turn_jsonl_survives_a_truncated_final_line(tmp_path):
    path = tmp_path / "turns.jsonl"
    log = TurnLog(path)
    log.turn(tool="search_corpus")
    log.rejection("emit_finding", "not_byte_exact", "submission")
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"record_type":"turn"')

    records, malformed = read_turns(path)

    assert [r["turn_index"] for r in records] == [1, 2]
    assert malformed == 1


def test_capture_provenance_has_required_keys():
    provenance = capture_provenance(
        run_index=1,
        model_id="databricks-meta-llama-3-3-70b-instruct",
        corpus_content_hash="corpus-sha",
        run_completed=True,
        found_set={"C-02", "B-08", "C-01"},
    )

    assert provenance["run_index"] == 1
    assert provenance["model_id"] == "databricks-meta-llama-3-3-70b-instruct"
    assert provenance["found_set"] == ["B-08", "C-01", "C-02"]
    assert "prereg_commit_sha" in provenance
    assert provenance["matcher_content_sha256"]
    assert provenance["baseline_sha256"]


def test_summary_carries_every_provenance_field(tmp_path):
    expected = [
        "run_index",
        "model_id",
        "prereg_commit_sha",
        "harness_version",
        "matcher_version",
        "matcher_content_sha256",
        "baseline_path",
        "baseline_sha256",
        "normalizer_version",
        "serializer_version",
        "parser_version",
        "corpus_content_hash",
        "found_set",
        "run_completed",
        "abort_reason",
    ]
    path = tmp_path / "summary.json"

    RunSummary(provenance=_provenance()).write_json(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    for field in expected:
        assert field in data["provenance"]
        if field not in {"prereg_commit_sha", "abort_reason"}:
            assert data["provenance"][field] != ""


def test_git_sha_degrades_to_empty_string():
    assert _git_sha_of("/definitely/not/a/path") == ""


def test_turn_records_are_json_objects(tmp_path):
    path = tmp_path / "turns.jsonl"
    TurnLog(path).repair("pre", "emit_finding")

    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["record_type"] == "repair"
    assert row["turn_index"] == 1
    assert "timestamp_monotonic" in row


def test_summary_missing_a_provenance_field_fails_loudly():
    provenance = _provenance()
    provenance.pop("matcher_content_sha256")

    with pytest.raises(ValueError, match="missing provenance fields"):
        RunSummary(provenance=provenance)


def test_aborted_run_is_self_evidently_distinguishable_from_completed(tmp_path):
    completed = RunSummary(provenance=_provenance(run_completed=True, abort_reason=""))
    aborted = RunSummary(provenance=_provenance(run_completed=False, abort_reason="provider 5xx"))
    completed_path = tmp_path / "completed.json"
    aborted_path = tmp_path / "aborted.json"

    completed.write_json(completed_path)
    aborted.write_json(aborted_path)

    completed_data = json.loads(completed_path.read_text(encoding="utf-8"))
    aborted_data = json.loads(aborted_path.read_text(encoding="utf-8"))
    assert completed_data["provenance"]["run_completed"] is True
    assert completed_data["provenance"]["abort_reason"] == ""
    assert aborted_data["provenance"]["run_completed"] is False
    assert aborted_data["provenance"]["abort_reason"] == "provider 5xx"


def test_summary_write_is_atomic(tmp_path):
    """Unlike evals/run.py's direct write, the destination is complete JSON after success."""
    path = tmp_path / "summary.json"

    RunSummary(provenance=_provenance()).write_json(path)

    assert json.loads(path.read_text(encoding="utf-8"))["provenance"]["run_index"] == 1
    assert list(tmp_path.glob("*.tmp")) == []


def test_two_halves_are_never_summed():
    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[
            {"record_type": "rejection", "turn_index": 1, "reason_code": "not_byte_exact", "half": "submission"},
            {"record_type": "rejection", "turn_index": 2, "reason_code": "not_retrieved_this_session", "half": "rule"},
            {"record_type": "tool_call", "turn_index": 3},
        ],
    )

    assert summary.span_invention_count == 1
    assert summary.rule_never_read_count == 1
    assert "not_byte_exact|submission" in summary.rejections_by_code_half
    assert "not_retrieved_this_session|rule" in summary.rejections_by_code_half
    assert "total_rejections" not in RunSummary.model_fields
    assert "rejections_total" not in RunSummary.model_fields


def test_unrecognized_reason_code_is_flagged_loudly():
    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[
            {"record_type": "rejection", "turn_index": 1, "reason_code": "new_gate_code", "half": "rule"},
        ],
    )

    assert summary.unrecognized_reason_codes == {"new_gate_code": 1}
    assert summary.has_unrecognized_reason_codes is True


def test_no_secret_or_document_text_reaches_the_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token-value")
    turn_path = tmp_path / "turns.jsonl"
    summary_path = tmp_path / "summary.json"

    TurnLog(turn_path).turn(
        tool_result_body="full document body should never be serialized",
        header="Authorization: Bearer secret-token-value",
    )
    RunSummary(provenance=_provenance()).write_json(summary_path)

    combined = turn_path.read_text(encoding="utf-8") + summary_path.read_text(encoding="utf-8")
    assert "secret-token-value" not in combined
    assert "Authorization" not in combined
    assert "full document body should never be serialized" not in combined


def test_summary_carries_consumption_time_splits():
    class Budget:
        billed_tokens = 100
        cached_tokens = 25
        turns = 3
        usage_missing_turns = 0
        model_time_s = 4.5
        tool_execution_time_s = 2.25

        def wall_clock_s(self):
            return 9.0

    class Ledger:
        embedding_time_s = 1.5

        def dedup_hit_rate(self):
            return 0.0

    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[],
        budget_ledger=Budget(),
        retrieval_ledger=Ledger(),
    )

    assert summary.wall_clock_s == 9.0
    assert summary.model_time_s == 4.5
    assert summary.tool_execution_time_s == 2.25
    assert summary.embedding_time_s == 1.5
