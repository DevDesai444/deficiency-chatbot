from __future__ import annotations

import json
import re
from pathlib import Path

import agents.detection.prompts as prompts


_NUMERIC_RE = re.compile(r"\d+(?:[.,/]\d+)*")
_TABLE_RE = re.compile(r"\btable\s+(\d+)\b", re.I)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z-]{5,}")
_GENERIC_WORDS = {
    "acceptance",
    "absorptivity",
    "analysis",
    "analytical",
    "coefficient",
    "control",
    "current",
    "entire",
    "established",
    "factor",
    "impurities",
    "impurity",
    "maximum",
    "method",
    "report",
    "response",
    "sample",
    "specified",
    "specification",
    "standard",
    "study",
    "temperature",
    "unspecified",
    "verification",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text.lower()).replace("%", "").replace(",", "")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _eval_leak_tokens() -> dict[str, set[str]]:
    tokens: dict[str, set[str]] = {"numeric": set(), "phrase": set(), "word": set()}
    for path in Path("src/evals/dataset").glob("*.deficiencies.json"):
        rows = json.loads(path.read_text())
        for text in _strings(rows):
            for match in _NUMERIC_RE.findall(text):
                token = _norm(match)
                if len(token) > 1:
                    tokens["numeric"].add(token)
            for match in _TABLE_RE.findall(text):
                tokens["phrase"].add(_norm(f"table {match}"))

        for row in rows:
            anchor = row.get("evidence_anchor", "")
            for word in _WORD_RE.findall(anchor):
                token = word.lower().replace("-", "")
                if token not in _GENERIC_WORDS:
                    tokens["word"].add(token)
    return {kind: {token for token in values if token} for kind, values in tokens.items()}


def _prompt_strings() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(prompts).items()
        if name.isupper() and isinstance(value, str)
    }


def test_detection_prompts_do_not_contain_eval_anchor_tokens():
    prompt_blob = "\n".join(_prompt_strings().values())
    prompt_norm = _norm(prompt_blob)
    leak_tokens = _eval_leak_tokens()
    leaks: list[str] = []
    for token in leak_tokens["numeric"]:
        if re.search(rf"(?<![0-9./]){re.escape(token)}(?![0-9./])", prompt_norm):
            leaks.append(token)
    for token in leak_tokens["phrase"]:
        if token in prompt_norm:
            leaks.append(token)
    for token in leak_tokens["word"]:
        if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", prompt_norm):
            leaks.append(token)

    assert sorted(leaks) == []
