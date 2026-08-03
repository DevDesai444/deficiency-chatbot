from __future__ import annotations

import json

from agents.review.telemetry import TurnLog, _git_sha_of, capture_provenance, read_turns


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
    )

    assert provenance["run_index"] == 1
    assert provenance["model_id"] == "databricks-meta-llama-3-3-70b-instruct"
    assert "prereg_commit_sha" in provenance
    assert provenance["matcher_content_sha256"]
    assert provenance["baseline_sha256"]


def test_git_sha_degrades_to_empty_string():
    assert _git_sha_of("/definitely/not/a/path") == ""


def test_turn_records_are_json_objects(tmp_path):
    path = tmp_path / "turns.jsonl"
    TurnLog(path).repair("pre", "emit_finding")

    row = json.loads(path.read_text(encoding="utf-8"))

    assert row["record_type"] == "repair"
    assert row["turn_index"] == 1
    assert "timestamp_monotonic" in row
