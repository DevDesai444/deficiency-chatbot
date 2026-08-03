from __future__ import annotations

from pathlib import Path

from agents.detection.verify import verify_and_tier
from agents.review.budget import BudgetLedger
from agents.review.loop import run_review
from agents.review.registry import ToolRegistry
from agents.review.telemetry import TurnLog
from schemas.documents import SpanID
from schemas.faults import ComplianceVerdict, EvidenceClass, Fault, Tier
from tests.agents.review.conftest import ScriptedChatClient, make_tool_call
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _doc() -> dict:
    return {"pages": [{"blocks": [{"text": "Section 3 omits LOD. Section 4 omits LOQ."}], "tables": []}]}


def _agent_fault(title: str, detail: str) -> Fault:
    return Fault(
        title=title or "Deficiency",
        detail=detail,
        evidence="Section 3 omits LOD.",
        tier=Tier.CORROBORATED,
        evidence_class=EvidenceClass.QUOTE_ANCHORED,
        confidence=0.7,
        verdict=ComplianceVerdict.GAP,
        source="tool:emit_finding",
    )


def _turn(*calls):
    raw_calls = [
        {
            "id": call.id,
            "type": "function",
            "function": {"name": call.function.name, "arguments": call.function.arguments},
        }
        for call in calls
    ]
    from llm.client import ChatTurn

    return ChatTurn(
        content="",
        finish_reason="tool_calls",
        tool_calls=list(calls),
        raw_message={"role": "assistant", "content": None, "tool_calls": raw_calls},
        prompt_tokens=10,
        completion_tokens=1,
        usage_present=True,
    )


def _stop_turn():
    from llm.client import ChatTurn

    return ChatTurn(
        content="done",
        finish_reason="stop",
        tool_calls=[],
        raw_message={"role": "assistant", "content": "done"},
        prompt_tokens=10,
        completion_tokens=1,
        usage_present=True,
    )


def test_legacy_verify_would_drop_agent_findings():
    faults = [
        _agent_fault(title="", detail="Section 3 omits LOD."),
        _agent_fault(title="", detail="Section 4 omits LOQ."),
    ]

    assert len(verify_and_tier(faults, _doc())) < len(faults)


def test_legacy_verify_would_drop_self_negating_agent_findings():
    faults = [_agent_fault(title="Not a deficiency", detail="This is not a finding.")]

    assert verify_and_tier(faults, _doc()) == []


def test_nothing_between_the_emit_gate_and_the_report_removes_a_finding(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        doc_id="d1",
        blocks=[
            {"text": "Alpha criterion missing.", "page": 1, "reading_order": 0, "lines": []},
            {"text": "Beta criterion missing.", "page": 1, "reading_order": 1, "lines": []},
        ],
        outline_headings=["Findings"],
    )
    ledger = RetrievalLedger()
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)

    rule_span = SpanID(doc_id="rule", start=0, end=4, hash="rulehash")
    sub_span_a = SpanID(doc_id="d1", start=0, end=24, hash="subhasha")
    sub_span_b = SpanID(doc_id="d1", start=25, end=48, hash="subhashb")
    emitted_faults = [
        Fault(
            title="Alpha gap",
            detail="Alpha detail [verdict: gap]",
            evidence="Alpha criterion missing.",
            tier=Tier.CORROBORATED,
            evidence_class=EvidenceClass.QUOTE_ANCHORED,
            confidence=0.7,
            verdict=ComplianceVerdict.GAP,
            rule_span_id=rule_span,
            submission_span_id=sub_span_a,
            source="tool:emit_finding",
        ),
        Fault(
            title="Beta gap",
            detail="Beta detail [verdict: gap]",
            evidence="Beta criterion missing.",
            tier=Tier.CORROBORATED,
            evidence_class=EvidenceClass.QUOTE_ANCHORED,
            confidence=0.7,
            verdict=ComplianceVerdict.GAP,
            rule_span_id=rule_span,
            submission_span_id=sub_span_b,
            source="tool:emit_finding",
        ),
    ]

    def scripted_dispatch(name: str, raw_args: str):
        from agents.review.registry import DispatchResult

        fault = emitted_faults.pop(0)
        return DispatchResult(
            result=fault.model_dump_json(),
            turn_consumed=True,
            repair_layer="none",
            tool=name,
            raw_result=fault,
        )

    registry.dispatch = scripted_dispatch  # type: ignore[method-assign]
    client = ScriptedChatClient(
        [
            _turn(make_tool_call("emit_finding", {"title": "Alpha gap"})),
            _turn(make_tool_call("emit_finding", {"title": "Beta gap"})),
            _stop_turn(),
        ]
    )

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)

    assert len(result.report.faults) == 2
    assert [f.title for f in result.report.faults] == ["Alpha gap", "Beta gap"]


def test_agent_path_preserves_emit_finding_identity(tmp_path):
    corpus = build_corpus_index(
        tmp_path,
        doc_id="d1",
        blocks=[{"text": "Identity evidence.", "page": 1, "reading_order": 0, "lines": []}],
        outline_headings=["Identity"],
    )
    ledger = RetrievalLedger()
    budget = BudgetLedger(max_tokens=1_000_000, max_wall_clock_s=999)
    telemetry = TurnLog(tmp_path / "turns.jsonl")
    registry = ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=ledger, budget=budget)
    rule_span = SpanID(doc_id="rule", start=0, end=4, hash="rulehash")
    sub_span = SpanID(doc_id="d1", start=0, end=18, hash="subhash")
    emitted = Fault(
        title="Identity gap",
        detail="Identity detail [verdict: violation]",
        evidence="Identity evidence.",
        tier=Tier.CORROBORATED,
        evidence_class=EvidenceClass.QUOTE_ANCHORED,
        confidence=0.7,
        verdict=ComplianceVerdict.VIOLATION,
        rule_span_id=rule_span,
        submission_span_id=sub_span,
        source="tool:emit_finding",
    )

    def scripted_dispatch(name: str, raw_args: str):
        from agents.review.registry import DispatchResult

        return DispatchResult(
            result=emitted.model_dump_json(),
            turn_consumed=True,
            repair_layer="none",
            tool=name,
            raw_result=emitted,
        )

    registry.dispatch = scripted_dispatch  # type: ignore[method-assign]
    client = ScriptedChatClient([_turn(make_tool_call("emit_finding", {"title": "Identity gap"})), _stop_turn()])

    result = run_review(corpus, corpus.manifest, ledger, budget, telemetry, client, registry)
    fault = result.report.faults[0]

    assert fault.tier == Tier.CORROBORATED
    assert fault.evidence_class == EvidenceClass.QUOTE_ANCHORED
    assert fault.confidence == 0.7
    assert fault.verdict == ComplianceVerdict.VIOLATION
    assert fault.rule_span_id == rule_span
    assert fault.submission_span_id == sub_span


def test_agent_path_never_imports_the_dropping_passes():
    review_dir = Path("src/agents/review")
    offenders = []
    for path in review_dir.rglob("*.py"):
        text = path.read_text()
        if "verify_and_tier" in text or "challenge_faults" in text:
            offenders.append(path)

    assert offenders == []
