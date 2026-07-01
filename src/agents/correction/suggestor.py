from __future__ import annotations

import json

from config import get_settings
from llm.client import chat_completion
from llm.prompts import SUGGESTOR
from schemas.corrections import Correction
from schemas.flaws import FlawReport, Severity


def generate_corrections(
    flaw_report: FlawReport,
    previous_feedback: str = "",
) -> list[Correction]:
    s = get_settings()

    report_json = json.dumps(flaw_report.model_dump(), indent=2, default=str)

    user_message = f"## Flaw Report\n\n{report_json}"
    if previous_feedback:
        user_message += f"\n\n## Evaluator Feedback (revise based on this)\n\n{previous_feedback}"

    user_message += (
        "\n\nFor each confirmed flaw, provide a recommendation in this JSON format:\n"
        '```json\n[\n  {\n    "flaw_category": "...",\n    "suggestion": "...",\n'
        '    "explanation": "...",\n    "priority": "high|medium|low",\n'
        '    "references": ["..."]\n  }\n]\n```'
    )

    response = chat_completion(
        messages=[
            {"role": "system", "content": SUGGESTOR},
            {"role": "user", "content": user_message},
        ],
        model=s.suggestor_endpoint,
        max_tokens=4096,
    )

    return _parse_corrections(response)


def _parse_corrections(response: str) -> list[Correction]:
    """Extract JSON corrections from LLM response, with fallback."""
    start = response.find("[")
    end = response.rfind("]") + 1

    if start >= 0 and end > start:
        try:
            raw = json.loads(response[start:end])
            corrections = []
            for item in raw:
                corrections.append(Correction(
                    flaw_category=item.get("flaw_category", "general_cmc"),
                    suggestion=item.get("suggestion", ""),
                    explanation=item.get("explanation", ""),
                    priority=_parse_severity(item.get("priority", "medium")),
                    references=item.get("references", []),
                ))
            return corrections
        except (json.JSONDecodeError, KeyError):
            pass

    return [Correction(
        flaw_category="general_cmc",
        suggestion=response[:500],
        explanation="Raw LLM response — structured parsing failed",
        priority=Severity.MEDIUM,
    )]


def _parse_severity(val: str) -> Severity:
    val = val.lower().strip()
    if val == "high":
        return Severity.HIGH
    if val == "low":
        return Severity.LOW
    return Severity.MEDIUM
