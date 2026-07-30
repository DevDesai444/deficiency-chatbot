"""CI-style command-line entry point for the eval harness (EVAL-03).

`python -m evals.run <score|gate|run>` -- a single, repeatable command every later phase is
graded against (ROADMAP Phase 0 success criteria 3 and 4).

  score  -- load the eval set + a captured report (golden fixture by default), compute the
            full per-stage + by-family metrics, print a human-readable table, write metrics.json.
  gate   -- load the eval set + a captured report + the committed baseline, run the zero-
            true-positives-lost gate (`evals.gate.check_gate`); print `GATE OK` / exit 0 on pass,
            print `GATE FAILED: lost {ids}` / exit 1 on failure. This is the CI gate.
  run    -- LIVE: reuse parse -> detect headlessly (NOT the single-file pipeline entry -- no Databricks
            job-store write) for every non-held-out document in the eval set, score each,
            aggregate. A document with no parse path yet (DOCX at Phase 0) or that raises
            during parse/detect is recorded as a parse_failure and skipped, never crashes
            the run. `--gate` additionally applies the zero-TP-lost gate to each live report.

`score` and `gate` are LLM-free and fast: this module only imports `evals.*` (pure data/string
modules -- see their own docstrings) and `schemas.faults` at top level. The detection stack
(`parse.pdf.extract_pdf`, `parse.section_splitter`, `agents.detection.pipeline.run_detection`)
is imported LAZILY, inside the function bodies that actually need it, so `--help` and the base
`score`/`gate` paths never pull in the heavier, optional, LLM-calling detection dependencies.

Checker note W1: `score` (and baseline generation, see `src/evals/baseline/`) parse the
non-held-out source PDF once via `extract_pdf`, joining block text + table-cell text, and pass
it to `compute_metrics` as `source_text` -- so `anchor_rate` records a REAL number, not the
permanent `"n/a_no_source"` sentinel. `_load_source_text` below is a lazy-import wrapper so this
still does not cost `score` an eager, module-top `parse.pdf` import; it degrades to `""` (never
raises) if the local corpus file the eval set points at is unavailable -- `data/` is intentionally
gitignored (see `data/README.md`), so this keeps `score`/`gate` usable without it.
"""
from __future__ import annotations

import argparse
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from evals.capture import golden_report, load_captured
from evals.gate import baseline_found_ids, check_gate
from evals.metrics import compute_metrics, format_table
from evals.schema import EvalSet, load_eval_set
from schemas.faults import FaultReport

DEFAULT_DOC_ID = "mvr1381"
DEFAULT_SCORE_OUT = "docs/eval/last_metrics.json"
DEFAULT_RUN_OUT = "docs/eval/last_run_metrics.json"
BASELINE_PATH = Path(__file__).parent / "baseline" / "recall_by_family.json"


def _join_source_text(parsed_doc: dict) -> str:
    """Join `extract_pdf`'s block text + table-cell text into one plain-text blob (W1).

    Table cells live in `headers`/`rows`, not `blocks[].text` -- a purely block-text join would
    miss every deficiency anchored in a table cell (the common case for this corpus's tabular
    findings, e.g. C-01/C-02 both live in table rows).
    """
    parts: list[str] = []
    for page in parsed_doc.get("pages", []):
        for block in page.get("blocks", []):
            text = block.get("text") or ""
            if text:
                parts.append(text)
        for table in page.get("tables", []):
            for header in table.get("headers") or []:
                if header:
                    parts.append(str(header))
            for row in table.get("rows") or []:
                for cell in row:
                    if cell:
                        parts.append(str(cell))
    return " ".join(parts)


@contextmanager
def _no_network_ocr():
    """Force `parse.ocr.ocr_page` to skip straight to its documented no-creds fallback.

    Auto-fix (Rule 1/3): a real run of this corpus's non-held-out PDF showed `is_scanned_page`
    flags ~half its pages (scan-heavy appendices/chromatogram printouts); with real Databricks
    OCR creds configured (`.env`), `extract_pdf` fired one live network call per flagged page,
    each blocking up to its own 60s `httpx` timeout -- turning a "fast, LLM-free" `score` into a
    multi-minute, network-dependent one, contradicting this module's own threat model ("score/gate
    ... touch neither network nor LLM"). `ocr_page` already treats an empty
    `databricks_host`/`databricks_token` as "OCR unavailable, use the embedded text layer" (its
    documented local-dev-without-creds path) -- this just forces that path for the eval harness's
    own source-text pass specifically, without touching the shared parse/detect config anywhere
    else (e.g. the `run` subcommand's live parse below keeps full OCR fidelity, matching real
    detection input). Pydantic-settings init kwargs outrank the `.env` file, so this override is
    exact, not a guess.
    """
    from config import Settings

    with patch("parse.ocr.get_settings", return_value=Settings(databricks_host="", databricks_token="")):
        yield


def _load_source_text(eval_set: EvalSet, doc_id: str) -> str:
    """Parse `doc_id`'s own registered PDF once via `extract_pdf` for a real `anchor_rate` (W1).

    Never raises: an unregistered doc_id, a non-PDF format, a missing local corpus file (`data/`
    is gitignored, see `data/README.md`), or any parse error all degrade to `""` -- `score`/`gate`
    stay usable even without the optional local corpus, and `anchor_rate` then correctly reports
    its explicit `"n/a_no_source"` sentinel instead of crashing the CLI.
    """
    doc = next((d for d in eval_set.documents if d.doc_id == doc_id), None)
    if doc is None or doc.format != "pdf":
        return ""
    try:
        from parse.pdf import extract_pdf  # lazy: keep score/gate/--help import-light

        with _no_network_ocr():
            parsed = extract_pdf(doc.path)
    except Exception:
        return ""
    return _join_source_text(parsed)


def _write_metrics(metrics: dict, out_path: str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2, default=str))


def cmd_score(args: argparse.Namespace) -> int:
    """`score`: compute + print + persist the full per-stage/by-family metrics. Always exits 0."""
    eval_set = load_eval_set()
    report = load_captured(args.captured) if args.captured else golden_report(args.doc_id)
    source_text = _load_source_text(eval_set, args.doc_id)  # W1
    metrics = compute_metrics(report, eval_set, args.doc_id, source_text=source_text)

    print(format_table(metrics))
    _write_metrics(metrics, args.out)
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    """`gate`: the zero-true-positives-lost CI check. Exit 0 on pass, 1 on loss."""
    eval_set = load_eval_set()
    report = load_captured(args.captured) if args.captured else golden_report(args.doc_id)
    baseline = json.loads(Path(args.baseline).read_text())
    baseline_ids = baseline_found_ids(eval_set, extra=set(baseline.get("found_set", [])))

    result = check_gate(report, eval_set, args.doc_id, baseline_ids)
    if result.ok:
        print("GATE OK")
        return 0
    print(f"GATE FAILED: lost {sorted(result.lost)}")
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    """`run`: LIVE parse -> detect over every non-held-out eval-set document.

    Headless reuse of the orchestrator's parse->detect sequence (`parse.pdf.extract_pdf` ->
    `parse.section_splitter` -> `agents.detection.pipeline.run_detection`), NOT the single-file pipeline entry
    (which writes the Databricks job store; `job_id=""` here, which `emit_sync` tolerates).
    A document whose format has no parse path yet (DOCX at Phase 0) or that raises anywhere in
    parse/detect is recorded as a `parse_failure` and skipped -- one bad document never crashes
    the whole run.
    """
    from agents.detection.pipeline import run_detection
    from parse.pdf import extract_pdf
    from parse.section_splitter import group_sections, split_document

    eval_set = load_eval_set()
    reports: dict[str, FaultReport] = {}
    per_doc_metrics: dict[str, dict] = {}
    parse_failures: dict[str, str] = {}

    for doc in eval_set.documents:
        if doc.held_out:
            continue
        try:
            if doc.format == "pdf":
                parsed = extract_pdf(doc.path)
            elif doc.format == "docx":
                from parse.docx import extract_docx  # lazy import (Phase 1 DOCX seam; matches the lazy-import style)
                parsed = extract_docx(doc.path)
            else:
                parse_failures[doc.doc_id] = f"no parse path for format={doc.format!r}"
                continue
            sections = split_document(parsed)
            groups = group_sections(sections)
            report = run_detection(parsed, sections, groups, job_id="", model=args.model)
        except Exception as exc:  # noqa: BLE001 -- one bad document must never crash the run
            parse_failures[doc.doc_id] = str(exc)
            continue

        reports[doc.doc_id] = report
        source_text = _join_source_text(parsed)
        metrics = compute_metrics(report, eval_set, doc.doc_id, source_text=source_text)
        per_doc_metrics[doc.doc_id] = metrics
        print(f"=== {doc.doc_id} ===")
        print(format_table(metrics))

    if parse_failures:
        print(f"parse_failures: {parse_failures}")
    _write_metrics({"per_document": per_doc_metrics, "parse_failures": parse_failures}, args.out)

    if not args.gate:
        return 0

    baseline = json.loads(BASELINE_PATH.read_text())
    baseline_ids = baseline_found_ids(eval_set, extra=set(baseline.get("found_set", [])))
    exit_code = 0
    for doc_id, report in reports.items():
        result = check_gate(report, eval_set, doc_id, baseline_ids)
        if result.ok:
            print(f"GATE OK ({doc_id})")
        else:
            print(f"GATE FAILED ({doc_id}): lost {sorted(result.lost)}")
            exit_code = 1
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evals.run", description="DefPredict eval harness CI-style CLI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_p = subparsers.add_parser("score", help="Score a captured/golden report (LLM-free).")
    score_p.add_argument("--captured", default=None, help="Path to a captured FaultReport JSON.")
    score_p.add_argument("--doc-id", dest="doc_id", default=DEFAULT_DOC_ID)
    score_p.add_argument("--out", default=DEFAULT_SCORE_OUT)
    score_p.set_defaults(func=cmd_score)

    gate_p = subparsers.add_parser("gate", help="Zero-true-positives-lost CI gate (LLM-free).")
    gate_p.add_argument("--captured", default=None, help="Path to a captured FaultReport JSON.")
    gate_p.add_argument("--doc-id", dest="doc_id", default=DEFAULT_DOC_ID)
    gate_p.add_argument("--baseline", default=str(BASELINE_PATH))
    gate_p.set_defaults(func=cmd_gate)

    run_p = subparsers.add_parser("run", help="LIVE: parse+detect every non-held-out document.")
    run_p.add_argument("--model", default=None, help="Detector model id (validated by resolve_detector_model).")
    run_p.add_argument("--gate", action="store_true", help="Also apply the zero-TP-lost gate.")
    run_p.add_argument("--out", default=DEFAULT_RUN_OUT)
    run_p.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
