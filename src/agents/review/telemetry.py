"""Spike run telemetry artifacts for the review loop.

The JSONL turn log is append-only by design: each row is flushed as soon as the
turn happens so an aborted run still leaves evidence. Summary artifacts use an
atomic temp-to-rename write in later tasks; the append stream cannot use that
pattern, so readers tolerate a truncated final row.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from config import resolve_detector_model
from evals import HARNESS_VERSION, MATCHER_VERSION
from ingest.normalize import NORMALIZER_VERSION
from ingest.serialize import SERIALIZER_VERSION
from parse.pdf import PARSER_VERSION
from tools.errors import KNOWN_REASON_CODES

_DEFAULT_PREREG_PATH = ".planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION.md"
_DEFAULT_MATCHER_PATH = "src/evals/match.py"
_DEFAULT_BASELINE_PATH = "src/evals/baseline/recall_by_family.json"


def _sha256_file(path: str | Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return ""


# D-TEL1(i)/D-GO5: record the pre-registration file's commit SHA, but never let
# unavailable git state crash a telemetry-producing run.
def _git_sha_of(path: str) -> str:
    # except below returns "", preserving telemetry even when git is unavailable.
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", path],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except Exception:
        return ""
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""


def capture_provenance(
    *,
    run_index: int,
    model_id: str | None = None,
    corpus_content_hash: str,
    run_completed: bool,
    abort_reason: str = "",
    prereg_path: str = _DEFAULT_PREREG_PATH,
    matcher_path: str = _DEFAULT_MATCHER_PATH,
    baseline_path: str = _DEFAULT_BASELINE_PATH,
) -> dict[str, Any]:
    """Build the full D-TEL1(i) provenance block for a run summary."""
    resolved_model = resolve_detector_model(model_id)
    return {
        "run_index": run_index,
        "model_id": resolved_model,
        "prereg_commit_sha": _git_sha_of(prereg_path),
        "harness_version": HARNESS_VERSION,
        "matcher_version": MATCHER_VERSION,
        "matcher_content_sha256": _sha256_file(matcher_path),
        "baseline_path": baseline_path,
        "baseline_sha256": _sha256_file(baseline_path),
        "normalizer_version": NORMALIZER_VERSION,
        "serializer_version": SERIALIZER_VERSION,
        "parser_version": PARSER_VERSION,
        "corpus_content_hash": corpus_content_hash,
        "run_completed": run_completed,
        "abort_reason": abort_reason,
    }


def read_turns(path: str | Path) -> tuple[list[dict[str, Any]], int]:
    """Read a JSONL turn stream, skipping malformed rows instead of raising.

    The expected aborted-run failure mode is a truncated final line. Returning the
    malformed count makes that visible to the summary writer and reviewer.
    """
    records: list[dict[str, Any]] = []
    malformed = 0
    try:
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    malformed += 1
    except FileNotFoundError:
        return [], 0
    return records, malformed


@dataclass
class TurnLog:
    """D-TEL1: typed per-turn JSONL, written as the turn happens.

    Constructor-injected, one instance per run. Every row carries a turn index
    and monotonic timestamp, and each write is flushed before returning.
    """

    path: Path
    _turn_index: int = field(default=0, init=False, repr=False)

    def turn(self, **fields: Any) -> None:
        self._append("turn", fields)

    def continuation(self, tokens_at_stop: int, findings_before: int) -> None:
        self._append(
            "continuation",
            {
                "tokens_at_stop": tokens_at_stop,
                "findings_before": findings_before,
            },
        )

    def rejection(self, tool: str, reason_code: str, half: str) -> None:
        self._append(
            "rejection",
            {
                "tool": tool,
                "reason_code": reason_code,
                "half": half,
                "reason_code_known": reason_code in KNOWN_REASON_CODES,
            },
        )

    def repair(self, layer: Literal["pre", "post"], tool: str) -> None:
        self._append("repair", {"layer": layer, "tool": tool})

    def oracle_leads(self, surfaced: int) -> None:
        self._append("oracle_leads", {"surfaced": surfaced})

    def _append(self, record_type: str, fields: dict[str, Any]) -> None:
        self._turn_index += 1
        record = {
            "record_type": record_type,
            "turn_index": self._turn_index,
            "timestamp_monotonic": time.monotonic(),
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
            fh.flush()


def ledger_dedup_hit_rate(ledger: Any) -> float:
    """Read RetrievalLedger's existing signal rather than recomputing it."""
    dedup_hit_rate = getattr(ledger, "dedup_hit_rate", None)
    return float(dedup_hit_rate()) if callable(dedup_hit_rate) else 0.0
