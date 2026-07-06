from __future__ import annotations

import json

from config import get_settings
from llm.prompts import SUGGESTOR
from llm.structured import structured_call
from schemas.corrections import Correction, CorrectionList, ParseFailed
from schemas.flaws import FlawReport


def generate_corrections(
    flaw_report: FlawReport,
    previous_feedback: str = "",
) -> tuple[list[Correction], list[ParseFailed]]:
    s = get_settings()

    report_json = json.dumps(flaw_report.model_dump(), indent=2, default=str)

    user_message = f"## Flaw Report\n\n{report_json}"
    if previous_feedback:
        user_message += f"\n\n## Evaluator Feedback (revise based on this)\n\n{previous_feedback}"

    user_message += (
        "\n\nProduce a JSON object with a `corrections` array. "
        "Each item must have flaw_category (see valid enum values in schema), "
        "suggestion, explanation, priority (high|medium|low), and references."
    )

    result, failure = structured_call(
        messages=[
            {"role": "system", "content": SUGGESTOR},
            {"role": "user", "content": user_message},
        ],
        model_cls=CorrectionList,
        model=s.suggestor_endpoint,
        max_tokens=4096,
        repair_context="Suggestor generating regulatory deficiency recommendations for a CMC submission review.",
    )

    if result is not None:
        return result.corrections, []
    return [], [failure] if failure else []
