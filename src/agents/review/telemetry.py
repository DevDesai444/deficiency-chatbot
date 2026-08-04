"""Spike run telemetry artifacts for the review loop.

The JSONL turn log is append-only by design: each row is flushed as soon as the
turn happens so an aborted run still leaves evidence. Summary artifacts use an
atomic temp-to-rename write in later tasks; the append stream cannot use that
pattern, so readers tolerate a truncated final row.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from config import resolve_detector_model
from evals import HARNESS_VERSION, MATCHER_VERSION
from ingest.normalize import NORMALIZER_VERSION
from ingest.serialize import SERIALIZER_VERSION
from parse.pdf import PARSER_VERSION
from tools.errors import KNOWN_REASON_CODES

_DEFAULT_PREREG_PATH = ".planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION.md"
_DEFAULT_MATCHER_PATH = "src/evals/match.py"
_DEFAULT_BASELINE_PATH = "src/evals/baseline/recall_by_family.json"
_PROVENANCE_FIELDS = {
    "run_index",
    "model_id",
    "prereg_commit_sha",
    "code_head_sha",
    "working_tree_dirty",
    "harness_version",
    "matcher_version",
    "matcher_content_sha256",
    "baseline_path",
    "baseline_sha256",
    "normalizer_version",
    "serializer_version",
    "parser_version",
    "corpus_content_hash",
    "found_set",
    "run_completed",
    "abort_reason",
}
_CONTENT_KEYS = {
    "authorization",
    "body",
    "content",
    "document_text",
    "raw_output",
    "text",
    "tool_result",
    "tool_result_body",
}


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


# A1 (03-19 prereg v2): record the exact code HEAD each scored run executed at, plus whether
# the working tree was dirty, so all 3 runs are provably at one identical, clean HEAD.
def _git_head_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2, check=False,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def _git_working_tree_dirty() -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5, check=False,
        )
    except Exception:
        return False
    return bool(result.stdout.strip())


def capture_provenance(
    *,
    run_index: int,
    model_id: str | None = None,
    corpus_content_hash: str,
    run_completed: bool,
    abort_reason: str = "",
    found_set: list[str] | set[str] | tuple[str, ...] | None = None,
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
        "code_head_sha": _git_head_sha(),
        "working_tree_dirty": _git_working_tree_dirty(),
        "harness_version": HARNESS_VERSION,
        "matcher_version": MATCHER_VERSION,
        "matcher_content_sha256": _sha256_file(matcher_path),
        "baseline_path": baseline_path,
        "baseline_sha256": _sha256_file(baseline_path),
        "normalizer_version": NORMALIZER_VERSION,
        "serializer_version": SERIALIZER_VERSION,
        "parser_version": PARSER_VERSION,
        "corpus_content_hash": corpus_content_hash,
        "found_set": sorted(str(item) for item in (found_set or [])),
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


def _forbidden_needles() -> list[str]:
    needles = ["Authorization"]
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if token:
        needles.append(token)
    return needles


def _scrub_string(key: str, value: str) -> Any:
    lowered = key.lower()
    if any(needle and needle in value for needle in _forbidden_needles()):
        return "[redacted]"
    if lowered in _CONTENT_KEYS or any(part in lowered for part in ("authorization", "token")):
        encoded = value.encode("utf-8")
        return {
            "omitted": True,
            "length": len(value),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }
    return value


def _scrub_for_artifact(value: Any, key: str = "") -> Any:
    if isinstance(value, str):
        return _scrub_string(key, value)
    if isinstance(value, dict):
        return {str(k): _scrub_for_artifact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_for_artifact(v, key) for v in value]
    if isinstance(value, tuple):
        return tuple(_scrub_for_artifact(v, key) for v in value)
    return value


def _assert_clean_artifact(value: Any) -> None:
    payload = json.dumps(value, sort_keys=True, default=str)
    leaked = [needle for needle in _forbidden_needles() if needle and needle in payload]
    if leaked:
        raise ValueError("telemetry artifact contains a forbidden secret/header value")


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

    def continuation(self, tokens_at_stop: int, findings_before: int, findings_after: int | None = None) -> None:
        fields = {
            "tokens_at_stop": tokens_at_stop,
            "findings_before": findings_before,
        }
        if findings_after is not None:
            fields["findings_after"] = findings_after
        self._append("continuation", fields)

    def tool_call(self, tool: str) -> None:
        """One row per NON-rejected dispatch. Paired with rejection() rows so that
        (tool_call rows + rejection rows) reconciles with BudgetLedger.total_tool_calls."""
        self._append("tool_call", {"tool": tool})

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
        record = _scrub_for_artifact(record)
        _assert_clean_artifact(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
            fh.flush()


def ledger_dedup_hit_rate(ledger: Any) -> float:
    """Read RetrievalLedger's existing signal rather than recomputing it."""
    dedup_hit_rate = getattr(ledger, "dedup_hit_rate", None)
    return float(dedup_hit_rate()) if callable(dedup_hit_rate) else 0.0


def _read_number(obj: Any, name: str, default: int | float = 0) -> int | float:
    value = getattr(obj, name, default)
    if callable(value):
        value = value()
    return value if isinstance(value, int | float) else default


def _read_string(obj: Any, name: str, default: str = "") -> str:
    value = getattr(obj, name, default)
    if callable(value):
        value = value()
    return value if isinstance(value, str) else default


class RunSummary(BaseModel):
    """D-TEL1 run summary with all five pre-registered diagnostic groups."""

    provenance: dict[str, Any]

    rejections_by_code_half: dict[str, int] = Field(default_factory=dict)
    unrecognized_reason_codes: dict[str, int] = Field(default_factory=dict)
    has_unrecognized_reason_codes: bool = False
    span_invention_count: int = 0
    rule_never_read_count: int = 0

    pre_repair_malformed: int = 0
    post_repair_malformed: int = 0
    total_tool_calls: int = 0
    pre_repair_malformed_rate: float = 0.0
    post_repair_malformed_rate: float = 0.0
    first_malformed_turn_index: int = 0

    continuation_count: int = 0
    max_continuations_permitted: int = 0
    tokens_at_each_attempted_stop: list[int] = Field(default_factory=list)
    findings_before_after_each_nudge: list[tuple[int, int]] = Field(default_factory=list)
    which_bound_ended_nudging: str = ""
    stop_reason: str = ""

    oracle_leads_surfaced: int = 0
    oracle_leads_reopened: int = 0
    oracle_leads_emitted: int = 0

    billed_tokens: int = 0
    cached_tokens: int = 0
    turns: int = 0
    wall_clock_s: float = 0.0
    model_time_s: float = 0.0
    tool_execution_time_s: float = 0.0
    embedding_time_s: float = 0.0
    usage_missing_turns: int = 0
    dedup_hit_rate: float = 0.0
    malformed_trailing_turn_lines: int = 0

    @model_validator(mode="after")
    def _validate_provenance(self) -> "RunSummary":
        missing = sorted(field for field in _PROVENANCE_FIELDS if field not in self.provenance)
        if missing:
            raise ValueError(f"missing provenance fields: {', '.join(missing)}")
        if self.provenance.get("run_completed") and self.provenance.get("abort_reason"):
            raise ValueError("completed runs must not carry an abort_reason")
        if not self.provenance.get("run_completed") and not self.provenance.get("abort_reason"):
            raise ValueError("aborted runs must carry an abort_reason")
        return self

    @classmethod
    def from_turns(
        cls,
        *,
        provenance: dict[str, Any],
        records: list[dict[str, Any]],
        malformed_trailing_turn_lines: int = 0,
        budget_ledger: Any | None = None,
        retrieval_ledger: Any | None = None,
        max_continuations_permitted: int = 0,
        which_bound_ended_nudging: str = "",
        stop_reason: str = "",
        wall_clock_s: float = 0.0,
    ) -> "RunSummary":
        rejections: dict[str, int] = {}
        unrecognized: dict[str, int] = {}
        pre_repair = 0
        post_repair = 0
        first_malformed = 0
        continuation_rows: list[dict[str, Any]] = []
        oracle_leads_surfaced = 0
        oracle_leads_reopened = 0
        oracle_leads_emitted = 0
        dispatched_tool_calls = 0

        for record in records:
            record_type = record.get("record_type")
            if record_type == "rejection":
                dispatched_tool_calls += 1
                reason_code = str(record.get("reason_code", ""))
                half = str(record.get("half", ""))
                key = f"{reason_code}|{half}"
                rejections[key] = rejections.get(key, 0) + 1
                if reason_code not in KNOWN_REASON_CODES:
                    unrecognized[reason_code] = unrecognized.get(reason_code, 0) + 1
            elif record_type == "repair":
                layer = record.get("layer")
                if layer == "pre":
                    pre_repair += 1
                elif layer == "post":
                    post_repair += 1
                    dispatched_tool_calls += 1
                if layer in {"pre", "post"} and not first_malformed:
                    first_malformed = int(record.get("turn_index") or 0)
            elif record_type == "tool_call":
                dispatched_tool_calls += 1
            elif record_type == "continuation":
                continuation_rows.append(record)
            elif record_type == "oracle_leads":
                oracle_leads_surfaced += int(record.get("surfaced") or 0)
                oracle_leads_reopened += int(record.get("reopened") or 0)
                oracle_leads_emitted += int(record.get("emitted") or 0)

        budget_ledger = budget_ledger or object()
        total_tool_calls = int(_read_number(budget_ledger, "total_tool_calls", dispatched_tool_calls))
        if not total_tool_calls:
            total_tool_calls = dispatched_tool_calls
        continuation_count = int(_read_number(budget_ledger, "continuations", len(continuation_rows)))
        if not continuation_count:
            continuation_count = len(continuation_rows)
        derived_stop_reason = stop_reason or _read_string(budget_ledger, "stop_reason", "")
        derived_bound = which_bound_ended_nudging or _read_string(budget_ledger, "which_bound", "")

        return cls(
            provenance=provenance,
            rejections_by_code_half=rejections,
            unrecognized_reason_codes=unrecognized,
            has_unrecognized_reason_codes=bool(unrecognized),
            span_invention_count=rejections.get("not_byte_exact|submission", 0),
            rule_never_read_count=rejections.get("not_retrieved_this_session|rule", 0),
            pre_repair_malformed=pre_repair,
            post_repair_malformed=post_repair,
            total_tool_calls=total_tool_calls,
            pre_repair_malformed_rate=pre_repair / (pre_repair + total_tool_calls) if pre_repair + total_tool_calls else 0.0,
            post_repair_malformed_rate=post_repair / total_tool_calls if total_tool_calls else 0.0,
            first_malformed_turn_index=first_malformed,
            continuation_count=continuation_count,
            max_continuations_permitted=max_continuations_permitted,
            tokens_at_each_attempted_stop=[int(r.get("tokens_at_stop") or 0) for r in continuation_rows],
            findings_before_after_each_nudge=[
                (int(r.get("findings_before") or 0), int(r.get("findings_after", r.get("findings_before") or 0)))
                for r in continuation_rows
            ],
            which_bound_ended_nudging=derived_bound,
            stop_reason=derived_stop_reason,
            oracle_leads_surfaced=oracle_leads_surfaced,
            oracle_leads_reopened=oracle_leads_reopened,
            oracle_leads_emitted=oracle_leads_emitted,
            billed_tokens=int(_read_number(budget_ledger, "billed_tokens", 0)),
            cached_tokens=int(_read_number(budget_ledger, "cached_tokens", 0)),
            turns=int(_read_number(budget_ledger, "turns", 0)),
            wall_clock_s=float(_read_number(budget_ledger, "wall_clock_s", wall_clock_s)),
            model_time_s=float(_read_number(budget_ledger, "model_time_s", 0.0)),
            tool_execution_time_s=float(_read_number(budget_ledger, "tool_execution_time_s", 0.0)),
            embedding_time_s=float(_read_number(retrieval_ledger, "embedding_time_s", 0.0)),
            usage_missing_turns=int(_read_number(budget_ledger, "usage_missing_turns", 0)),
            dedup_hit_rate=ledger_dedup_hit_rate(retrieval_ledger),
            malformed_trailing_turn_lines=malformed_trailing_turn_lines,
        )

    def write_json(self, path: str | Path) -> None:
        """Atomically write the summary JSON (temp file -> os.replace)."""
        final = Path(path)
        final.parent.mkdir(parents=True, exist_ok=True)
        payload = _scrub_for_artifact(self.model_dump(mode="json"))
        _assert_clean_artifact(payload)
        tmp = final.with_suffix(final.suffix + ".tmp")
        encoded = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        with tmp.open("wb") as fh:
            fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
