"""
Generate fine-tuning datasets for Suggestor and Evaluator adapters
from the deficiency knowledge base.

Output:
    data/finetune/suggestor_train.jsonl
    data/finetune/suggestor_val.jsonl
    data/finetune/evaluator_train.jsonl
    data/finetune/evaluator_val.jsonl
"""
from __future__ import annotations

import json
import random
import sqlite3
import textwrap
from pathlib import Path

DB_PATH = Path("data/defpredict.db")
OUT_DIR = Path("data/finetune")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_SPLIT = 0.85
SEED = 42

SUGGESTOR_SYSTEM = textwrap.dedent("""\
    You are a regulatory affairs specialist reviewing CMC (Chemistry, Manufacturing,
    and Controls) submissions. Given a set of identified deficiency findings, produce
    a JSON array of correction objects. Each object must have: flaw_category, suggestion,
    explanation, priority (high/medium/low), and references (list of section IDs).""")

EVALUATOR_SYSTEM = textwrap.dedent("""\
    You are a quality evaluator for regulatory submission corrections. Given the original
    deficiency findings and proposed corrections, assess whether the corrections adequately
    address every finding. Return a JSON object with: verdict (pass, minor_revision, or
    deeper_review), feedback (string), and corrections_reviewed (int).""")


def load_records() -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT product_name, dosage_form, cmc_section, deficiency_type, "
        "deficiency_text, deficiency_response FROM deficiency_kb"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_suggestor_example(rec: dict) -> dict:
    section = rec.get("cmc_section") or "unknown"
    flaw_type = rec.get("deficiency_type") or "general"
    evidence = rec.get("deficiency_text") or ""
    response = rec.get("deficiency_response") or ""

    user_msg = (
        f"Analyze the following deficiency finding and provide a correction.\n\n"
        f"Section: {section}\n"
        f"Deficiency type: {flaw_type}\n"
        f"Evidence: {evidence}"
    )

    correction = {
        "flaw_category": flaw_type.lower().replace(" ", "_"),
        "suggestion": _summarize_response(response),
        "explanation": response[:500] if response else "No historical response available.",
        "priority": "medium",
        "references": [section] if section != "unknown" else [],
    }

    return {
        "messages": [
            {"role": "system", "content": SUGGESTOR_SYSTEM},
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": json.dumps([correction], indent=2)},
        ]
    }


def build_evaluator_examples(rec: dict) -> list[dict]:
    section = rec.get("cmc_section") or "unknown"
    flaw_type = rec.get("deficiency_type") or "general"
    evidence = rec.get("deficiency_text") or ""
    response = rec.get("deficiency_response") or ""

    flaw_block = (
        f"Section: {section}\n"
        f"Deficiency type: {flaw_type}\n"
        f"Evidence: {evidence}"
    )

    good_correction = json.dumps({
        "flaw_category": flaw_type.lower().replace(" ", "_"),
        "suggestion": _summarize_response(response),
        "explanation": response[:300] if response else "Addressed per guidance.",
        "priority": "medium",
    })

    examples = []

    # PASS — correction aligns with the known good response
    examples.append({
        "messages": [
            {"role": "system", "content": EVALUATOR_SYSTEM},
            {"role": "user", "content": f"Original finding:\n{flaw_block}\n\nProposed correction:\n{good_correction}"},
            {"role": "assistant", "content": json.dumps({
                "verdict": "pass",
                "feedback": "",
                "corrections_reviewed": 1,
            })},
        ]
    })

    # MINOR_REVISION — vague correction missing specifics
    vague_correction = json.dumps({
        "flaw_category": flaw_type.lower().replace(" ", "_"),
        "suggestion": "Review and update the relevant section.",
        "explanation": "Please address the identified gap.",
        "priority": "low",
    })
    examples.append({
        "messages": [
            {"role": "system", "content": EVALUATOR_SYSTEM},
            {"role": "user", "content": f"Original finding:\n{flaw_block}\n\nProposed correction:\n{vague_correction}"},
            {"role": "assistant", "content": json.dumps({
                "verdict": "minor_revision",
                "feedback": "Correction is too vague — needs specific regulatory references and actionable steps.",
                "corrections_reviewed": 1,
            })},
        ]
    })

    # DEEPER_REVIEW — wrong category entirely
    wrong_correction = json.dumps({
        "flaw_category": "stability_data",
        "suggestion": "Add 6-month accelerated stability data.",
        "explanation": "Stability studies are required.",
        "priority": "high",
    })
    examples.append({
        "messages": [
            {"role": "system", "content": EVALUATOR_SYSTEM},
            {"role": "user", "content": f"Original finding:\n{flaw_block}\n\nProposed correction:\n{wrong_correction}"},
            {"role": "assistant", "content": json.dumps({
                "verdict": "deeper_review",
                "feedback": f"Correction addresses stability but the original finding is about {flaw_type}. Re-extraction needed.",
                "corrections_reviewed": 1,
            })},
        ]
    })

    return examples


def _summarize_response(text: str) -> str:
    if not text:
        return "Address the identified deficiency per FDA guidance."
    sentences = text.replace("\n", " ").split(".")
    summary_parts = [s.strip() for s in sentences[:3] if s.strip()]
    return ". ".join(summary_parts) + "." if summary_parts else text[:200]


def write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def main() -> None:
    records = load_records()
    print(f"Loaded {len(records)} records from knowledge base")

    random.seed(SEED)
    random.shuffle(records)

    split_idx = int(len(records) * TRAIN_SPLIT)
    train_recs = records[:split_idx]
    val_recs = records[split_idx:]

    # Suggestor dataset
    suggestor_train = [build_suggestor_example(r) for r in train_recs]
    suggestor_val = [build_suggestor_example(r) for r in val_recs]
    write_jsonl(OUT_DIR / "suggestor_train.jsonl", suggestor_train)
    write_jsonl(OUT_DIR / "suggestor_val.jsonl", suggestor_val)
    print(f"Suggestor: {len(suggestor_train)} train, {len(suggestor_val)} val")

    # Evaluator dataset (3 examples per record)
    evaluator_train = []
    for r in train_recs:
        evaluator_train.extend(build_evaluator_examples(r))
    evaluator_val = []
    for r in val_recs:
        evaluator_val.extend(build_evaluator_examples(r))
    write_jsonl(OUT_DIR / "evaluator_train.jsonl", evaluator_train)
    write_jsonl(OUT_DIR / "evaluator_val.jsonl", evaluator_val)
    print(f"Evaluator: {len(evaluator_train)} train, {len(evaluator_val)} val")


if __name__ == "__main__":
    main()
