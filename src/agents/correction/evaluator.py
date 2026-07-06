from __future__ import annotations

import json

from config import get_settings
from llm.prompts import EVALUATOR
from llm.structured import structured_call
from schemas.corrections import Correction, Evaluation, EvaluationOutput, Verdict


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
        "Return a JSON object with two fields:\n"
        "  verdict: one of `pass`, `minor_revision`, `deeper_review`\n"
        "  feedback: specific issues to fix (empty string if verdict is pass)"
    )

    result, failure = structured_call(
        messages=[
            {"role": "system", "content": EVALUATOR},
            {"role": "user", "content": user_message},
        ],
        model_cls=EvaluationOutput,
        model=s.evaluator_endpoint,
        max_tokens=2048,
        repair_context="Evaluator judging whether regulatory-deficiency recommendations pass, need minor revision, or need deeper review.",
    )

    if result is not None:
        return Evaluation(
            verdict=result.verdict,
            feedback=result.feedback if result.verdict != Verdict.PASS else "",
            corrections_reviewed=len(corrections),
        )

    # Even after L5, the moderator couldn't produce valid output — default to MINOR_REVISION
    # so the correction loop retries rather than accepting untrusted output as PASS.
    return Evaluation(
        verdict=Verdict.MINOR_REVISION,
        feedback=f"Evaluator parse failure: {failure.validation_error if failure else 'unknown'}. Please regenerate cleanly.",
        corrections_reviewed=len(corrections),
    )
