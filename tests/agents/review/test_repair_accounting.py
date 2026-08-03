from __future__ import annotations

from agents.review.telemetry import RunSummary, capture_provenance


def _provenance():
    return capture_provenance(
        run_index=1,
        model_id="databricks-meta-llama-3-3-70b-instruct",
        corpus_content_hash="corpus-sha",
        run_completed=True,
    )


def test_pre_and_post_repair_are_counted_separately():
    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[
            {"record_type": "repair", "turn_index": 1, "layer": "pre", "tool": "emit_finding"},
            {"record_type": "repair", "turn_index": 2, "layer": "post", "tool": "emit_finding"},
            {"record_type": "tool_call", "turn_index": 3, "tool": "search_corpus"},
            {"record_type": "tool_call", "turn_index": 4, "tool": "open_doc"},
        ],
    )

    assert summary.pre_repair_malformed == 1
    assert summary.post_repair_malformed == 1
    assert summary.pre_repair_malformed_rate != summary.post_repair_malformed_rate
    assert summary.pre_repair_malformed_rate == 0.25
    assert summary.post_repair_malformed_rate == 1 / 3


def test_a_pre_repair_fix_consumes_no_turn():
    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[
            {"record_type": "repair", "turn_index": 1, "layer": "pre", "tool": "emit_finding"},
        ],
    )

    assert summary.pre_repair_malformed == 1
    assert summary.total_tool_calls == 0


def test_a_dispatched_then_rejected_call_consumes_a_turn():
    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[
            {
                "record_type": "rejection",
                "turn_index": 1,
                "tool": "emit_finding",
                "reason_code": "not_byte_exact",
                "half": "submission",
            },
        ],
    )

    assert summary.total_tool_calls == 1
    assert summary.rejections_by_code_half == {"not_byte_exact|submission": 1}
    assert summary.span_invention_count == 1


def test_first_malformed_turn_index_is_recorded():
    summary = RunSummary.from_turns(
        provenance=_provenance(),
        records=[
            {"record_type": "tool_call", "turn_index": 1, "tool": "search_corpus"},
            {"record_type": "repair", "turn_index": 2, "layer": "pre", "tool": "emit_finding"},
            {"record_type": "repair", "turn_index": 3, "layer": "post", "tool": "emit_finding"},
        ],
    )

    assert summary.first_malformed_turn_index == 2
