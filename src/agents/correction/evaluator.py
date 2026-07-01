from __future__ import annotations

import json

from config import get_settings
from llm.client import chat_completion
from llm.prompts import EVALUATOR
from schemas.corrections import Correction, Evaluation, Verdict


def evaluate_corrections(
    corrections: list[Correction],
    flaw_report_summary: str,
) -> Evaluation:
    s = get_settings()

    corrections_json = json.dumps(
        [c.model_dump() for c in corrections], indent=2, default=str
    )

    user_message = (
        f"## Original Flaw Summary\n\n{flaw_report_summary}\n\n"
        f"## Proposed Recommendations\n\n{corrections_json}\n\n"
        "Evaluate these recommendations. Respond with:\n"
        "1. VERDICT: PASS, MINOR_REVISION, or DEEPER_REVIEW\n"
        "2. FEEDBACK: specific issues to fix (if not PASS)\n"
    )

    response = chat_completion(
        messages=[
            {"role": "system", "content": EVALUATOR},
            {"role": "user", "content": user_message},
        ],
        model=s.evaluator_endpoint,
        max_tokens=2048,
    )

    return _parse_evaluation(response, len(corrections))


def _parse_evaluation(response: str, num_corrections: int) -> Evaluation:
    upper = response.upper()

    if "DEEPER_REVIEW" in upper:
        verdict = Verdict.DEEPER_REVIEW
    elif "MINOR_REVISION" in upper:
        verdict = Verdict.MINOR_REVISION
    else:
        verdict = Verdict.PASS

    feedback = response
    for marker in ["FEEDBACK:", "feedback:"]:
        idx = response.find(marker)
        if idx >= 0:
            feedback = response[idx + len(marker):].strip()
            break

    return Evaluation(
        verdict=verdict,
        feedback=feedback if verdict != Verdict.PASS else "",
        corrections_reviewed=num_corrections,
    )
