from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from config import Settings
from parse.pdf import extract_pdf
from parse.section_splitter import split_document


def _real_mvr_sections() -> list[dict]:
    with patch("parse.ocr.get_settings", return_value=Settings(databricks_host="", databricks_token="")):
        return split_document(extract_pdf(Path("data/32s43-validation-related-compounds-method.pdf")))


def _summaries(sections: list[dict]) -> list[dict]:
    return [
        {
            "section_index": i,
            "heading": s["heading"],
            "summary": f"SUM{i}",
            "tables": s["tables"],
            "page_start": s.get("page_start", 0),
            "page_end": s.get("page_end", 0),
        }
        for i, s in enumerate(sections)
    ]


def test_planner_to_workers_on_real_tp_sections_emits_candidate_finding(monkeypatch):
    """Guard the planner -> workers boundary over real Table 19/Table 20 TP-bearing sections."""
    import agents.detection.workers as worker_mod
    from agents.detection.planning import ReviewPlan, WorkerAssignment, _seed_table_suspicions

    sections = _real_mvr_sections()
    assert sections[16]["heading"].startswith("1.4.8")
    assert sections[17]["heading"].startswith("1.4.9")

    plan = ReviewPlan(workers=[
        WorkerAssignment(
            focused_section_indices=[16, 17],
            instruction="Review equivalency and system-suitability table contradictions.",
        )
    ])
    plan = _seed_table_suspicions(plan, sections)
    claims = " ".join(s.claim for w in plan.workers for s in w.suspicions)
    assert "0.15%" in claims
    assert "11477" in claims and "12601" in claims

    specialist_payloads: list[str] = []

    def fake_structured_call(messages, model_cls, **kwargs):
        user = messages[1]["content"]
        if kwargs.get("repair_context") == "worker:specialist":
            specialist_payloads.append(user)
            assert "Table 19" in user
            assert "Any Unspecified Impurity" in user
            assert "0.15" in user
            assert "NMT 0.10%" in user
            assert "Table 20" in user
            assert "Maximum" in user
            assert "11477" in user
            assert "12601" in user
            return (
                model_cls(findings=[
                    worker_mod.WorkerFinding(
                        title="",
                        detail="Table 20 Maximum theoretical plates 11477 contradicts the 12601 row.",
                        evidence="Maximum 11477; In-house Equivalency Study 12601",
                        section="1.4.9 System Suitability",
                        table_ref="Table 20",
                        rule_cited="Table 20 Maximum summary cell",
                        cited_section_indices=[17],
                    )
                ]),
                None,
            )
        return model_cls(), None

    monkeypatch.setattr(worker_mod, "_precedents_for", lambda assignment, sections: [])
    monkeypatch.setattr(worker_mod, "structured_call", fake_structured_call)

    faults, failures = worker_mod.run_workers(
        sections,
        _summaries(sections),
        plan,
        "MVR-1381 related-compounds validation report",
        model="fake-model",
    )

    assert failures == []
    assert specialist_payloads
    assert any("12601" in f.evidence for f in faults)
    assert all(f.title for f in faults)
