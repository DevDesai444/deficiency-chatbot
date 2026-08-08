"""CI-style command-line entry point for the eval harness (EVAL-03).

`python -m evals.run <score|gate|run|retrieval-gate>` -- a single, repeatable command every
later phase is graded against (ROADMAP Phase 0 success criteria 3 and 4; Phase 2 SC4).

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
  retrieval-gate -- LIVE but LLM-free: SC4's real `search_corpus`-driven recall@k gate (D-SC4).
            Ingests each non-held-out eval document via `ingest.corpus.ingest_corpus`, measures
            `evals.metrics._search_corpus_recall_at_k` per document, enforces the exact-identifier
            subset at 100% (hard functional gate) and the overall recall@k as a no-regress floor
            against the committed `src/evals/baseline/retrieval_recall.json`. Never touches
            Databricks or an LLM (D-RB6 offline contract).

`score` and `gate` are LLM-free and fast: this module only imports `evals.*` (pure data/string
modules -- see their own docstrings) and `schemas.faults` at top level. The detection stack
(`parse.pdf.extract_pdf`, `parse.section_splitter`, `agents.detection.pipeline.run_detection`)
is imported LAZILY, inside the function bodies that actually need it, so `--help` and the base
`score`/`gate` paths never pull in the heavier, optional, LLM-calling detection dependencies.
`retrieval-gate` similarly lazy-imports `ingest.corpus`/`evals.metrics`'s corpus-aware path so
`--help` stays light.

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
import hashlib
import json
import shutil
import tempfile
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
RETRIEVAL_BASELINE_PATH = Path(__file__).parent / "baseline" / "retrieval_recall.json"
COVERAGE_BASELINE_PATH = Path(__file__).parent / "baseline" / "coverage_baseline.json"
ABSENCE_BASELINE_PATH = Path(__file__).parent / "baseline" / "absence_threshold.json"


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


def _relabel_corpus_doc_id(corpus, doc):
    """Bridge `ingest_corpus`'s content-hash doc_id identity to the eval set's logical `doc_id`.

    `ingest.corpus.ingest_corpus` mints each `DocEntry.doc_id` as `content_hash(file_bytes)` --
    ITS OWN identity convention, unrelated to the eval set's registered logical id ("mvr1381",
    "minispec", ...). `_search_corpus_recall_at_k`'s per-GT-item `r["doc_id"] != doc_id` check
    (correctly, per its own contract) compares `search_corpus` results against the `doc_id`
    passed in -- which must be the eval set's logical id, since that is what every
    `GroundTruthDeficiency.doc_id` uses. Without this bridge every single result is silently
    discarded by that check (a doc-id NAMESPACE mismatch, not a retrieval-quality miss) --
    measured empirically as a uniform 0.0 overall/hard-subset recall on the real committed
    baseline run before this fix. Re-labels ONLY the manifest entry whose filename matches
    `doc.path`'s own basename (never a blanket rename), so a directory with unrelated OTHER
    parsed documents is left untouched; span-IDs/search results for the target doc then carry
    the SAME doc_id the eval set's rows use, closing the mismatch without touching
    `_search_corpus_recall_at_k`'s own (separately committed, separately tested) contract.
    """
    from ingest.corpus import CorpusIndex
    from ingest.store import cache_key, read_doc_cache
    from ingest.normalize import NORMALIZER_VERSION
    from ingest.serialize import SERIALIZER_VERSION
    from parse.pdf import PARSER_VERSION

    class _RelabeledCorpusIndex(CorpusIndex):
        """5R-R2 bridge: cached_entry ALSO resolves the ORIGINAL content-hash doc_id.

        Relabeling only the manifest doc_id (content-hash -> eval id) left the table_index /
        outline spans — minted at ingest under the content-hash doc_id and stored in the cache —
        pointing at a doc_id no manifest entry carries anymore. Emit gates then re-look-up
        `cached_entry(claim_span_id.doc_id)` by that content-hash id and got None
        (reason_code=wrong_store), silently dropping the STRUCTURAL leg from scored runs (the
        reference/absence legs happen to build spans under the manifest id and survived). This
        alias resolves the original content-hash back to the same on-disk cache so structural
        candidates survive emit into the scored report. Harness/bridge infra only — the frozen
        score/match/gate machinery is untouched; the alias is strictly additive (super() wins).
        """

        def cached_entry(self, doc_id: str) -> dict | None:
            entry = super().cached_entry(doc_id)
            if entry is not None:
                return entry
            for d in self.manifest.documents:
                if d.content_hash and d.content_hash == doc_id:
                    key = cache_key(d.content_hash, NORMALIZER_VERSION, SERIALIZER_VERSION, PARSER_VERSION)
                    return read_doc_cache(self.cache_dir, key)
            return None

    target_name = Path(doc.path).name
    relabeled = [
        (d.model_copy(update={"doc_id": doc.doc_id}) if d.filename == target_name else d)
        for d in corpus.manifest.documents
    ]
    manifest = corpus.manifest.model_copy(update={"documents": relabeled})
    return _RelabeledCorpusIndex(root=corpus.root, cache_dir=corpus.cache_dir, manifest=manifest)


def cmd_retrieval_gate(args: argparse.Namespace) -> int:
    """`retrieval-gate`: SC4's real search_corpus-driven recall@k gate (D-SC4, measure -> record
    -> ratchet). LIVE but LLM-free and Databricks-free -- ingests each non-held-out eval-set
    document's own directory via `ingest.corpus.ingest_corpus` (local substrate only), computes
    `evals.metrics._search_corpus_recall_at_k` per document, and enforces two independent checks:
    (a) the exact-identifier subset must be 100% -- a HARD functional gate (D-SC4(i)), never a
    soft ratchet, checked regardless of the baseline file's content; (b) the mean overall
    recall@k across documents must not regress below the committed baseline's recorded value
    (D-SC4(ii), the no-regress floor). One bad document's ingest failure is recorded and skipped,
    never crashes the gate (mirrors `cmd_run`'s per-document try/except discipline).
    """
    from evals.metrics import _search_corpus_recall_at_k
    from ingest.corpus import ingest_corpus

    eval_set = load_eval_set()
    baseline = json.loads(Path(args.baseline).read_text())

    per_doc: dict[str, dict | str] = {}
    for doc in eval_set.documents:
        if doc.held_out:
            continue
        try:
            corpus = ingest_corpus(Path(doc.path).parent)  # ingest the doc's own (small) directory
            corpus = _relabel_corpus_doc_id(corpus, doc)  # bridge content-hash id -> eval-set doc_id
        except Exception as exc:  # noqa: BLE001 -- one bad doc must never crash the gate
            print(f"retrieval-gate: could not ingest {doc.doc_id}: {exc}")
            continue
        per_doc[doc.doc_id] = _search_corpus_recall_at_k(eval_set, doc.doc_id, corpus)

    hard_subsets = [
        v["exact_identifier_subset"]
        for v in per_doc.values()
        if isinstance(v, dict) and isinstance(v.get("exact_identifier_subset"), float)
    ]
    if hard_subsets and min(hard_subsets) < 1.0:
        print(f"RETRIEVAL-GATE FAILED: exact-identifier subset not 100% -- {per_doc}")
        return 1

    overalls = [v["overall"] for v in per_doc.values() if isinstance(v, dict)]
    measured = sum(overalls) / len(overalls) if overalls else 0.0
    if measured < baseline.get("overall_recall_at_k", 0.0):
        print(
            f"RETRIEVAL-GATE FAILED: measured {measured:.3f} < "
            f"committed baseline {baseline['overall_recall_at_k']:.3f}"
        )
        return 1

    print(f"RETRIEVAL-GATE OK: overall={measured:.3f} per_document={per_doc}")
    return 0


def cmd_coverage_gate(args: argparse.Namespace) -> int:
    """`coverage-gate`: RULES-06's coverage no-regress floor + the D-ENR1 traceability floor
    (D-ENR3 measure -> record -> ratchet, mirrors cmd_retrieval_gate). LIVE but LLM-free and
    Databricks-free (D-RB6): it re-measures the local rulebook store + requirement index and runs
    two independent checks:

    (a) NO-REGRESS FLOOR (D-ENR3): every per-source chunk count and per-family requirement-entry
        count must be >= the committed baseline's recorded value. A source/family that regresses
        below the baseline fails the gate. (Baseline entries whose measured source/family is absent
        count as 0 -> a regression, correctly caught.)
    (b) TRACEABILITY FLOOR (D-ENR1 / D-RI1(2), the MS-04 hard gate): for EVERY eval-set deficiency
        in the ABSENCE_OF_EVIDENCE family, ingest that submission's own directory, resolve its
        content-derived profile, and assert `enumerate_requirements(manifest)` fires >= 1 applicable
        requirement entry. If any absence deficiency has zero firing entries, the gate fails -- the
        index the Plan-03 absence enumerator walks would be blind to that submission.

    One submission that fails to ingest is recorded and treated as a traceability failure for its
    doc_id (never a silent skip -- a blind submission is exactly what this floor exists to catch).
    Lazy-imports rulebook.store / rulebook.requirement_index / ingest.corpus inside the body per the
    module's import-light discipline so `--help` stays cheap.
    """
    import collections

    from evals.schema import FailureFamily, load_eval_set
    from ingest.corpus import ingest_corpus
    from rulebook.requirement_index import (
        build_requirement_edges,
        enumerate_requirements,
        load_requirement_index,
    )
    from rulebook.store import all_chunks

    baseline = json.loads(Path(args.baseline).read_text())

    # (a) no-regress floor -- re-measure from the live local store + index.
    load_requirement_index.cache_clear()
    build_requirement_edges()  # idempotent upsert -- makes the gate self-contained on a fresh store
    chunks = all_chunks()
    entries = load_requirement_index()
    measured_sources = collections.Counter(c.source for c in chunks)
    measured_families = collections.Counter(e.family for e in entries)

    regressions: list[str] = []
    for source, want in baseline.get("chunks_per_source", {}).items():
        got = measured_sources.get(source, 0)
        if got < want:
            regressions.append(f"chunks_per_source[{source}] {got} < baseline {want}")
    for family, want in baseline.get("entries_per_family", {}).items():
        got = measured_families.get(family, 0)
        if got < want:
            regressions.append(f"entries_per_family[{family}] {got} < baseline {want}")
    total_want = baseline.get("total_entries", 0)
    if len(entries) < total_want:
        regressions.append(f"total_entries {len(entries)} < baseline {total_want}")
    if regressions:
        print(f"COVERAGE-GATE FAILED: coverage regressed below committed baseline -- {regressions}")
        return 1

    # (b) traceability floor -- every absence_of_evidence eval deficiency must fire >= 1 entry.
    eval_set = load_eval_set()
    absence_doc_ids = sorted(
        {d.doc_id for d in eval_set.deficiencies if d.failure_family == FailureFamily.ABSENCE_OF_EVIDENCE}
    )
    firing: dict[str, int] = {}
    for doc_id in absence_doc_ids:
        doc = next((d for d in eval_set.documents if d.doc_id == doc_id), None)
        if doc is None:
            print(f"COVERAGE-GATE FAILED: absence deficiency doc_id {doc_id!r} not registered in the eval set")
            return 1
        try:
            corpus = ingest_corpus(Path(doc.path).parent)
        except Exception as exc:  # noqa: BLE001 -- a blind submission is a traceability failure, not a skip
            print(f"COVERAGE-GATE FAILED: could not ingest {doc_id} for the traceability floor: {exc}")
            return 1
        result = enumerate_requirements(corpus.manifest)
        n = len(result) if isinstance(result, list) else 0
        firing[doc_id] = n
        if n < 1:
            print(f"COVERAGE-GATE FAILED: no firing index entry for {doc_id} absence (traceability floor)")
            return 1

    print(
        "COVERAGE-GATE OK: "
        f"chunks_per_source={dict(sorted(measured_sources.items()))} "
        f"total_entries={len(entries)} "
        f"traceability_firing_per_absence_doc={firing}"
    )
    return 0


def cmd_absence_gate(args: argparse.Namespace) -> int:
    """`absence-gate`: RECALL-01's absence_of_evidence recovery gate (D-THR measure -> record ->
    ratchet, SC2). LIVE but LLM-free and Databricks-free (D-RB6): it runs the deterministic
    `rulebook.absence.enumerate_absences` pass over every NON-HELD-OUT absence submission and
    proves absence_of_evidence is recovered above the 0.000 floor.

    Processes ONLY non-held-out documents (mirrors cmd_retrieval_gate's `if doc.held_out: continue`
    idiom, run.py): the non-held-out ABSENCE sources are mvr1381 (11) + minispec (1). The held-out
    spec32s41 (the D-GEN1 generality WITNESS) is deliberately EXCLUDED from this recall floor --
    it is proven separately, and unchanged, by the THRESHOLD-TRANSFER invariant in
    tests/evals/test_generality_guard.py (anti-circularity: never witness generality on the recall
    floor). A submission that fails to ingest is recorded and SKIPPED (mirrors cmd_retrieval_gate),
    never crashes the gate -- a missing local corpus file must not fail the build.

    When EVERY non-held-out absence doc is skipped (clean checkout / CI where `data/` is gitignored,
    so nothing could be measured), the gate emits a distinct `ABSENCE-GATE SKIPPED (no local corpus)`
    and returns 0 (WR-03): "nothing to measure" is NOT a recall regression, and must not fail-close
    the build. The real recall-failure checks below are only reached once >=1 doc was measured.

    Two independent checks (only when at least one doc was actually measured):
    (i) HARD (SC2, W3): the measured absence_of_evidence recall on the NON-HELD-OUT EVAL-SET
        AGGREGATE (mvr1381 + minispec -- every doc with held_out=False) must be strictly > 0.000.
        The recall is matched-vs-required absence items accumulated across all processed non-held-out
        docs; a GT absence item is RECOVERED when the pass emitted >=1 grounded candidate for its
        document (doc-level recovery is the honest floor -- GT items carry no requirement_id, and the
        pass over-emits per applicable requirement; Phase 7 does the precise per-item verification).
    (ii) NO-REGRESS: the measured aggregate must not fall below the committed baseline's recorded
        `non_held_out_aggregate.absence_recall` (D-THR ratchet).

    The retrieval threshold is READ FROM the committed `src/evals/baseline/absence_threshold.json`
    (never a code constant, D-THR). Lazy-imports rulebook + ingest inside the body per the module's
    import-light discipline so `--help` stays cheap.
    """
    from evals.schema import FailureFamily, load_eval_set
    from ingest.corpus import ingest_corpus
    from rulebook.absence import enumerate_absences
    from rulebook.requirement_index import build_requirement_edges, load_requirement_index
    from tools.ledger import RetrievalLedger

    baseline = json.loads(Path(args.baseline).read_text())
    threshold = baseline["threshold"]

    load_requirement_index.cache_clear()
    build_requirement_edges()  # idempotent upsert -- self-contained on a fresh store

    eval_set = load_eval_set()
    # absence GT items grouped by the NON-HELD-OUT document they belong to.
    held_out_ids = {d.doc_id for d in eval_set.documents if d.held_out}
    absence_required: dict[str, int] = {}
    for gt in eval_set.deficiencies:
        if gt.failure_family != FailureFamily.ABSENCE_OF_EVIDENCE:
            continue
        if gt.doc_id in held_out_ids:
            continue  # D-GEN1: the held-out witness is never part of the recall floor.
        absence_required[gt.doc_id] = absence_required.get(gt.doc_id, 0) + 1

    per_doc: dict[str, dict | str] = {}
    matched_total = 0
    required_total = 0
    measured_docs = 0  # docs that actually ran the pass (ingested), vs. skipped for missing corpus
    for doc in eval_set.documents:
        if doc.held_out:
            continue
        required = absence_required.get(doc.doc_id, 0)
        if required == 0:
            continue  # this non-held-out doc has no absence GT items to recover.
        try:
            corpus = ingest_corpus(Path(doc.path).parent)
            corpus = _relabel_corpus_doc_id(corpus, doc)  # bridge content-hash id -> eval-set doc_id
        except Exception as exc:  # noqa: BLE001 -- a missing local corpus file must never crash the gate
            print(f"absence-gate: could not ingest {doc.doc_id}: {exc}")
            per_doc[doc.doc_id] = f"skipped: {exc}"
            continue
        ledger = RetrievalLedger()
        faults = enumerate_absences(corpus, corpus.manifest, ledger, threshold=threshold)
        emitted = len(faults)
        # Doc-level recovery: any grounded candidate lifts this doc's absence family off the 0.000
        # floor. Recall for the doc = min(1.0, ...) of its required items recovered -- with >=1
        # candidate, every required absence item for the doc counts as recovered (over-emit, D-ABS2).
        matched = required if emitted > 0 else 0
        matched_total += matched
        required_total += required
        measured_docs += 1
        per_doc[doc.doc_id] = {
            "absence_recall": (matched / required) if required else 0.0,
            "emitted": emitted,
            "required": required,
        }

    # WR-03: distinguish "nothing to measure" from "measured and not recovered". On a clean checkout /
    # CI where `data/` is gitignored, every absence doc fails to ingest and is skipped -> measured_docs
    # == 0 and required_total == 0. That is a MISSING-CORPUS condition, not a recall regression --
    # mirror cmd_retrieval_gate's tolerance ("a missing local corpus file must not fail the build") and
    # return 0 with a distinct SKIPPED message, rather than a false-negative "gap not recovered".
    if measured_docs == 0 or required_total == 0:
        print(
            "ABSENCE-GATE SKIPPED (no local corpus): no non-held-out absence document could be "
            f"measured ({measured_docs} measured) -- per_document={per_doc}"
        )
        return 0

    aggregate = matched_total / required_total

    if aggregate <= 0.0:
        print(
            "ABSENCE-GATE FAILED: non-held-out absence recall 0.000 (mvr1381+minispec), "
            f"the #1 gap not recovered -- per_document={per_doc}"
        )
        return 1

    floor = baseline.get("non_held_out_aggregate", {}).get("absence_recall", 0.0)
    if aggregate < floor:
        print(
            f"ABSENCE-GATE FAILED: measured aggregate {aggregate:.3f} < "
            f"committed baseline {floor:.3f} (D-THR ratchet) -- per_document={per_doc}"
        )
        return 1

    print(
        f"ABSENCE-GATE OK: non_held_out_aggregate={aggregate:.3f} (>0.000, SC2) "
        f"threshold={threshold} per_document={per_doc}"
    )
    return 0


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


def cmd_agent_run(args: argparse.Namespace) -> int:
    """`agent-run`: LIVE model-driven tool loop (AGENT-01) over the whole non-held-out corpus.

    Sibling of cmd_run, NOT a branch inside it: run_detection is PER-DOCUMENT (pipeline.py:37-39)
    while D-BUD5's budget is PER-RUN. Forcing the flag inside run_detection would either smuggle a
    per-document budget back in -- "2/28 by a different route" -- or corrupt the legacy arm, which
    D-LOOP1 requires stay byte-identical so the baseline is re-derivable at gate time.
    """
    from agents.review import run_review
    from agents.review.budget import BudgetLedger
    from agents.review.registry import ToolRegistry
    from agents.review.telemetry import RunSummary, TurnLog, capture_provenance, read_turns
    from config import resolve_detector_model
    from evals.match import score
    from ingest.corpus import ingest_corpus
    from llm.client import chat_completion_tools
    from tools.ledger import RetrievalLedger

    out_dir = Path(args.out_dir)
    run_prefix = args.run_prefix
    artifact_stem = f"{run_prefix}{args.run_index}"
    report_path = out_dir / f"{artifact_stem}.json"
    turn_log_path = out_dir / f"{artifact_stem}.jsonl"
    summary_path = out_dir / f"{artifact_stem}-summary.json"

    resolved_model = resolve_detector_model(args.model)
    budget = BudgetLedger(
        max_tokens=args.max_tokens,
        max_wall_clock_s=args.max_wall_clock,
        max_turns=args.max_turns,
    )
    ledger = RetrievalLedger()
    telemetry = TurnLog(turn_log_path)
    report = FaultReport()
    result = None
    abort_reason = ""
    corpus_hash = ""
    found_set: set[str] = set()
    turn_log_path.parent.mkdir(parents=True, exist_ok=True)
    turn_log_path.write_text("")

    try:
        eval_set = load_eval_set()
        with tempfile.TemporaryDirectory(prefix="eval-agent-corpus-") as tmp:
            corpus_root = Path(tmp)
            for doc in eval_set.documents:
                if args.document_split == "scored" and doc.held_out:
                    continue
                if args.document_split == "held-out" and not doc.held_out:
                    continue
                source = Path(doc.path)
                target = corpus_root / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

            corpus = ingest_corpus(corpus_root)
            relabeled = []
            for entry in corpus.manifest.documents:
                matching_doc = next(
                    (
                        doc
                        for doc in eval_set.documents
                        if (
                            (args.document_split == "scored" and not doc.held_out)
                            or (args.document_split == "held-out" and doc.held_out)
                        )
                        and Path(doc.path).name == entry.filename
                    ),
                    None,
                )
                relabeled.append(entry.model_copy(update={"doc_id": matching_doc.doc_id}) if matching_doc else entry)
            manifest = corpus.manifest.model_copy(update={"documents": relabeled})
            corpus = corpus.model_copy(update={"manifest": manifest})
            corpus_hash = hashlib.sha256(
                json.dumps(manifest.model_dump(mode="json"), sort_keys=True).encode("utf-8")
            ).hexdigest()

            registry = ToolRegistry(corpus=corpus, manifest=manifest, ledger=ledger, budget=budget)

            def complete(messages: list[dict], tools: list[dict]):
                return chat_completion_tools(messages, tools, model=resolved_model, temperature=0.0)

            result = run_review(corpus, manifest, ledger, budget, telemetry, complete, registry, job_id="")
            report = result.report
            for doc in eval_set.documents:
                if args.document_split == "scored" and doc.held_out:
                    continue
                if args.document_split == "held-out" and not doc.held_out:
                    continue
                found_set.update(score([f.model_dump() for f in report.faults], eval_set.deficiencies, doc.doc_id).matched_gt_ids)
    except Exception as exc:  # noqa: BLE001 -- an aborted run must still leave artifacts.
        abort_reason = f"{type(exc).__name__}: {exc}"
        report = report.model_copy(update={"stop_reason": "aborted", "budget_exhausted": False})

    run_completed = result is not None and not result.aborted and not abort_reason
    if result is not None and result.aborted:
        abort_reason = result.error or result.stop_reason or "aborted"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.model_dump_json(indent=2))
    records, malformed = read_turns(turn_log_path)
    provenance = capture_provenance(
        run_index=args.run_index,
        model_id=resolved_model,
        corpus_content_hash=corpus_hash,
        run_completed=run_completed,
        abort_reason="" if run_completed else (abort_reason or "aborted"),
        found_set=found_set,
        prereg_path=args.prereg,
    )
    summary = RunSummary.from_turns(
        provenance=provenance,
        records=records,
        malformed_trailing_turn_lines=malformed,
        budget_ledger=budget,
        retrieval_ledger=ledger,
        max_continuations_permitted=budget.max_continuations,
        which_bound_ended_nudging=budget.which_bound,
        stop_reason=report.stop_reason,
        wall_clock_s=budget.wall_clock_s(),
    )
    summary.write_json(summary_path)
    return 0 if run_completed else 1


# =============================================================================
# Phase 5 gate CLI commands (Plan 06, Wave 4 — Ruling 4: ALL Phase 5 gate wiring here)
# Plans 03/04/05 removed run.py from their files_modified; this is the ONLY plan
# that writes run.py for Phase 5. Additive-only: existing cmd_* functions untouched.
# =============================================================================


def cmd_structural_gate(args: argparse.Namespace) -> int:
    """`structural-gate`: RECALL-02 structural-inconsistency gate (Plan 06, Ruling 4).

    Runs detect_structural_inconsistencies on the committed synthetic fixture_a and
    hard-fails (return 1) when 0 structural findings are produced. PASS when >= 1 Fault
    with a structural_anchor is found. LIVE but LLM-free and Databricks-free (D-RB6).
    """
    import pathlib
    import tempfile

    from ingest.corpus import ingest_corpus
    from rulebook.structural import detect_structural_inconsistencies
    from tools.ledger import RetrievalLedger

    fixture = pathlib.Path("src/evals/dataset/synthetic_fixture")
    if not fixture.exists():
        print("ERROR: structural-gate — synthetic fixture missing at src/evals/dataset/synthetic_fixture")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        corpus = ingest_corpus(fixture, cache_dir=tmp + "/cache")
        ledger = RetrievalLedger()
        faults = detect_structural_inconsistencies(corpus, corpus.manifest, ledger)

    struct_faults = [f for f in faults if f.structural_anchor is not None]
    print(f"  structural: {len(struct_faults)} finding(s) with structural_anchor")
    if not struct_faults:
        print("FAIL: structural-gate — 0 structural findings on synthetic fixture")
        return 1
    print("PASS: structural-gate")
    return 0


def cmd_reference_gate(args: argparse.Namespace) -> int:
    """`reference-gate`: RECALL-03 reference-anomaly gate (Plan 06, Ruling 4).

    Degraded behavior per binding_reviewer_addition_SC2 (PATH B):
    Runs extract_references + detect_reference_anomalies on the committed synthetic fixture_a.
    Hard-fails (return 1) when 0 reference findings are produced. Currently yields ~22
    UNRESOLVED_REF / 0 VALUE_CONTRADICTION (VALUE_CONTRADICTION deferred to Wave 5 when
    follow_reference is wired). PASS when >= 1 Fault with a reference_anchor is found.
    LIVE but LLM-free and Databricks-free (D-RB6).
    """
    import pathlib
    import tempfile

    from ingest.corpus import ingest_corpus
    from rulebook.references import detect_reference_anomalies, extract_references
    from tools.ledger import RetrievalLedger

    fixture = pathlib.Path("src/evals/dataset/synthetic_fixture")
    if not fixture.exists():
        print("ERROR: reference-gate — synthetic fixture missing at src/evals/dataset/synthetic_fixture")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        corpus = ingest_corpus(fixture, cache_dir=tmp + "/cache")
        edges_db = tmp + "/edges.db"
        extract_references(corpus, corpus.manifest, db_path=edges_db)
        ledger = RetrievalLedger()
        faults = detect_reference_anomalies(corpus, corpus.manifest, ledger, db_path=edges_db)

    ref_faults = [f for f in faults if f.reference_anchor is not None]
    print(f"  reference: {len(ref_faults)} finding(s) with reference_anchor")
    if not ref_faults:
        print("FAIL: reference-gate — 0 reference findings on synthetic fixture")
        return 1
    print("PASS: reference-gate")
    return 0


def cmd_precedent_gate(args: argparse.Namespace) -> int:
    """`precedent-gate`: RECALL-04 precedent-similarity gate (Plan 06, Ruling 4 + Ruling 8).

    Hard-fail/skip behavior (Ruling 8 sentinel check):
    - data/rulebook.faiss ABSENT: structured skip (exit 0 + SKIP message). Fast CI still
      gates on structural + reference legs which have no FAISS dependency. Not an error.
    - data/rulebook.faiss PRESENT: hard-fail (return 1) when 0 precedent findings are found.
      A live FAISS asset that produces nothing is a real failure, not a dependency gap.

    LIVE but LLM-free and Databricks-free when FAISS is local (D-PIX3 / D-RB6).
    """
    import pathlib
    import tempfile

    faiss_path = pathlib.Path("data/rulebook.faiss")
    if not faiss_path.exists():
        print("SKIP: data/rulebook.faiss not present — precedent leg not yet indexed.")
        print("(Structured skip, not an error. Build rulebook.faiss to enable hard-fail mode.)")
        return 0  # Exit 0: structured skip so fast CI still passes

    # FAISS asset present — hard-fail on 0 findings (real failure)
    from ingest.corpus import ingest_corpus
    from rulebook.precedent_search import detect_precedent_candidates
    from tools.ledger import RetrievalLedger

    fixture = pathlib.Path("src/evals/dataset/synthetic_fixture")
    if not fixture.exists():
        print("ERROR: precedent-gate — synthetic fixture missing at src/evals/dataset/synthetic_fixture")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        corpus = ingest_corpus(fixture, cache_dir=tmp + "/cache")
        ledger = RetrievalLedger()
        faults = detect_precedent_candidates(corpus, corpus.manifest, ledger)

    print(f"  precedent: {len(faults)} candidate(s) with precedent_anchor")
    if not faults:
        print("FAIL: precedent-gate — rulebook.faiss present but 0 precedent candidates found")
        return 1
    print(f"PASS: precedent-gate ({len(faults)} candidate(s))")
    return 0


def cmd_phase5_gate(args: argparse.Namespace) -> int:
    """`phase5-gate`: combined Phase 5 gate — runs all four legs in sequence (Plan 06, Ruling 4).

    Dispatches internally (no subprocess) to:
      - absence-gate  (RECALL-01, existing Phase 4 gate)
      - structural-gate (RECALL-02, Phase 5 new)
      - reference-gate  (RECALL-03, Phase 5 new, degraded per SC2 PATH B)
      - precedent-gate  (RECALL-04, Phase 5 new, hard-fail/skip per Ruling 8)

    Includes SC2/X1 state-aware assertion (binding_reviewer_addition_SC2):
      - Probes follow_reference on the 3-doc fixture cross-doc reference.
      - If follow_reference still stubbed (_CROSS_DOC_PENDING): emit LOUD WARN and
        continue degraded (exit 0 from this sub-check). Wave 5 will wire the hard path.
      - If follow_reference resolves cross-doc: HARD-ASSERT >= 1 VALUE_CONTRADICTION
        with Compound-B numbers (0.18 and 0.15). Return 1 if absent.

    PASS only when ALL hard-fail gates return 0 (precedent-gate may return 0 via
    structured-skip when FAISS absent). Prints per-gate summary.
    """
    import pathlib
    import tempfile

    gates: list[tuple[str, object]] = [
        ("absence-gate", cmd_absence_gate),
        ("structural-gate", cmd_structural_gate),
        ("reference-gate", cmd_reference_gate),
        ("precedent-gate", cmd_precedent_gate),
    ]

    results: dict[str, str] = {}
    for name, fn in gates:
        print(f"\n--- {name} ---")
        rc = fn(args)  # type: ignore[call-arg]
        results[name] = "PASS" if rc == 0 else "FAIL"

    # --- SC2/X1 state-aware assertion (binding_reviewer_addition_SC2, PATH B) ---
    print("\n--- SC2/X1 value-contradiction probe ---")
    sc2_rc = 0
    sc2_deferred = False
    fixture = pathlib.Path("src/evals/dataset/synthetic_fixture")

    if fixture.exists():
        from ingest.corpus import ingest_corpus
        from tools.follow_reference import _CROSS_DOC_PENDING, follow_reference
        from tools.ledger import RetrievalLedger

        with tempfile.TemporaryDirectory() as tmp:
            corpus = ingest_corpus(fixture, cache_dir=tmp + "/cache")
            ledger = RetrievalLedger()
            doc_ids = [d.doc_id for d in corpus.manifest.documents]

            if doc_ids:
                probe_result = follow_reference(corpus, doc_ids[0], "doc_b", ledger)
                probe_status = probe_result.get("status", "")

                if probe_status == _CROSS_DOC_PENDING:
                    # DEFERRED path: stubbed — emit LOUD WARN, continue degraded
                    print(
                        "WARN: SC2 X1 value-contradiction catch DEFERRED to Wave 5 — "
                        "follow_reference cross-doc resolution not yet wired; "
                        "reference-gate running DEGRADED (findings>0 only)."
                    )
                    sc2_deferred = True  # sc2_rc = 0 (pass degraded)
                else:
                    # HARD path: follow_reference resolved cross-doc — enforce full X1 catch
                    from rulebook.references import detect_reference_anomalies, extract_references
                    with tempfile.TemporaryDirectory() as tmp2:
                        corpus2 = ingest_corpus(fixture, cache_dir=tmp2 + "/cache")
                        edges_db = tmp2 + "/edges.db"
                        extract_references(corpus2, corpus2.manifest, db_path=edges_db)
                        ledger2 = RetrievalLedger()
                        faults = detect_reference_anomalies(
                            corpus2, corpus2.manifest, ledger2, db_path=edges_db
                        )
                    vc_faults = [
                        f for f in faults
                        if f.reference_anchor is not None
                        and f.reference_anchor.anomaly == "VALUE_CONTRADICTION"
                    ]
                    all_details = " ".join((f.detail or "") for f in vc_faults)
                    if not vc_faults or ("0.18" not in all_details or "0.15" not in all_details):
                        print(
                            "FAIL: SC2 X1 — follow_reference resolved cross-doc but "
                            f"found {len(vc_faults)} VALUE_CONTRADICTION fault(s) without "
                            "Compound-B numbers (0.18 and 0.15). "
                            "X1 value-contradiction catch must be active post-Wave-5."
                        )
                        sc2_rc = 1
                    else:
                        print(
                            f"PASS: SC2 X1 — {len(vc_faults)} VALUE_CONTRADICTION fault(s) "
                            "with Compound-B numbers detected."
                        )
    else:
        print("SKIP: SC2 probe — synthetic fixture absent")

    # --- Summary ---
    print("\nPhase5 gate summary:")
    for name, status in results.items():
        print(f"  {name}: {status}")
    if sc2_rc != 0:
        print("  SC2/X1 probe: FAIL")
    elif sc2_deferred:
        print("  SC2/X1 probe: DEFERRED (follow_reference not wired — reference-gate degraded)")
    else:
        print("  SC2/X1 probe: PASS (hard — X1 Compound-B value-contradiction caught)")

    failed = [n for n, s in results.items() if s == "FAIL"]
    if failed or sc2_rc != 0:
        failures = failed + (["SC2/X1"] if sc2_rc != 0 else [])
        print(f"FAIL: phase5-gate ({len(failures)} gate(s) failed: {', '.join(failures)})")
        return 1
    print("PASS: phase5-gate (all gates passed)")
    return 0


def cmd_deterministic_recall_gate(args: argparse.Namespace) -> int:
    """`deterministic-recall-gate`: combined three-leg recall report (Plan 06, Ruling 4).

    Runs all three deterministic recall legs (structural, reference, precedent) on the
    committed synthetic fixture_a, reports per-family counts, hard-fails on structural or
    reference legs producing 0 findings. Precedent is reported but not hard-failed (FAISS
    dependency — see cmd_precedent_gate for the hard-fail/skip logic).

    LIVE but LLM-free and Databricks-free (D-RB6). Distinct from phase5-gate in that it
    focuses on the three RECALL-02/03/04 legs only (no absence-gate or SC2 probe).
    """
    import pathlib
    import tempfile

    fixture = pathlib.Path("src/evals/dataset/synthetic_fixture")
    if not fixture.exists():
        print("ERROR: deterministic-recall-gate — synthetic fixture missing at "
              "src/evals/dataset/synthetic_fixture")
        return 1

    from ingest.corpus import ingest_corpus
    from rulebook.references import detect_reference_anomalies, extract_references
    from rulebook.structural import detect_structural_inconsistencies
    from tools.ledger import RetrievalLedger

    exit_code = 0

    with tempfile.TemporaryDirectory() as tmp:
        corpus = ingest_corpus(fixture, cache_dir=tmp + "/cache")

        # Structural leg (RECALL-02)
        ledger_struct = RetrievalLedger()
        struct_faults = [
            f for f in detect_structural_inconsistencies(corpus, corpus.manifest, ledger_struct)
            if f.structural_anchor is not None
        ]
        print(f"  structural (RECALL-02): {len(struct_faults)} finding(s)")
        if not struct_faults:
            print("  FAIL: structural leg — 0 findings on synthetic fixture")
            exit_code = 1

        # Reference leg (RECALL-03)
        edges_db = tmp + "/edges.db"
        extract_references(corpus, corpus.manifest, db_path=edges_db)
        ledger_ref = RetrievalLedger()
        ref_faults = [
            f for f in detect_reference_anomalies(corpus, corpus.manifest, ledger_ref,
                                                   db_path=edges_db)
            if f.reference_anchor is not None
        ]
        print(f"  reference (RECALL-03): {len(ref_faults)} finding(s)")
        if not ref_faults:
            print("  FAIL: reference leg — 0 findings on synthetic fixture")
            exit_code = 1

        # Precedent leg (RECALL-04) — report only, no hard-fail (FAISS dependency)
        faiss_path = pathlib.Path("data/rulebook.faiss")
        if faiss_path.exists():
            from rulebook.precedent_search import detect_precedent_candidates
            ledger_prec = RetrievalLedger()
            prec_faults = detect_precedent_candidates(corpus, corpus.manifest, ledger_prec)
            print(f"  precedent (RECALL-04): {len(prec_faults)} candidate(s)")
        else:
            print("  precedent (RECALL-04): SKIP (data/rulebook.faiss absent)")

    if exit_code != 0:
        print("FAIL: deterministic-recall-gate")
        return 1

    print("PASS: deterministic-recall-gate")
    return 0


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

    agent_run_p = subparsers.add_parser("agent-run", help="LIVE: model-driven review loop over the non-held-out corpus.")
    agent_run_p.add_argument("--model", default=None, help="Detector model id (validated by resolve_detector_model).")
    agent_run_p.add_argument("--run-index", type=int, required=True, help="Run index recorded in provenance.")
    agent_run_p.add_argument("--run-prefix", default="agent-run", help="Artifact filename prefix (default: agent-run).")
    agent_run_p.add_argument("--max-tokens", type=int, required=True, help="Per-run token ceiling.")
    agent_run_p.add_argument("--max-wall-clock", type=float, required=True, help="Per-run wall-clock ceiling in seconds.")
    agent_run_p.add_argument("--max-turns", type=int, default=50, help="Per-run turn ceiling.")
    agent_run_p.add_argument(
        "--document-split",
        choices=("scored", "held-out"),
        default="scored",
        help="Eval document split to assemble (default: scored). Use held-out only for calibration.",
    )
    agent_run_p.add_argument("--out-dir", required=True, help="Directory for FaultReport, JSONL, and RunSummary artifacts.")
    agent_run_p.add_argument(
        "--prereg",
        default=".planning/phases/03-drive-loop-spike-go-no-go/03-GO-NOGO-PREREGISTRATION.md",
        help="Pre-registration path whose commit SHA is captured.",
    )
    agent_run_p.set_defaults(func=cmd_agent_run)

    retrieval_gate_p = subparsers.add_parser(
        "retrieval-gate", help="SC4 retrieval recall@k gate (measure -> record -> ratchet, D-SC4)."
    )
    retrieval_gate_p.add_argument("--baseline", default=str(RETRIEVAL_BASELINE_PATH))
    retrieval_gate_p.set_defaults(func=cmd_retrieval_gate)

    coverage_gate_p = subparsers.add_parser(
        "coverage-gate",
        help="RULES-06 coverage no-regress floor + D-ENR1 traceability floor (measure -> record -> ratchet).",
    )
    coverage_gate_p.add_argument("--baseline", default=str(COVERAGE_BASELINE_PATH))
    coverage_gate_p.set_defaults(func=cmd_coverage_gate)

    absence_gate_p = subparsers.add_parser(
        "absence-gate",
        help="RECALL-01 absence_of_evidence recovery gate (recover >0.000 on the non-held-out aggregate, D-THR).",
    )
    absence_gate_p.add_argument("--baseline", default=str(ABSENCE_BASELINE_PATH))
    absence_gate_p.set_defaults(func=cmd_absence_gate)

    # --- Phase 5 gates (Plan 06, Wave 4 — Ruling 4: ALL Phase 5 gate wiring here) ---

    subparsers.add_parser(
        "structural-gate",
        help="RECALL-02 structural-inconsistency gate: hard-fail on 0 findings on synthetic fixture.",
    ).set_defaults(func=cmd_structural_gate)

    subparsers.add_parser(
        "reference-gate",
        help="RECALL-03 reference-anomaly gate (degraded per SC2 PATH B): hard-fail on 0 findings.",
    ).set_defaults(func=cmd_reference_gate)

    subparsers.add_parser(
        "precedent-gate",
        help="RECALL-04 precedent gate: hard-fail when data/rulebook.faiss present + 0 findings; "
             "structured-skip (exit 0) when absent (Ruling 8).",
    ).set_defaults(func=cmd_precedent_gate)

    phase5_p = subparsers.add_parser(
        "phase5-gate",
        help="Combined Phase 5 gate: absence + structural + reference + precedent + SC2 probe. "
             "PASS only when all hard-fail gates return 0.",
    )
    phase5_p.add_argument("--baseline", default=str(ABSENCE_BASELINE_PATH))
    phase5_p.set_defaults(func=cmd_phase5_gate)

    subparsers.add_parser(
        "deterministic-recall-gate",
        help="RECALL-02/03/04 combined recall report on synthetic fixture. Hard-fails on structural "
             "or reference 0 findings; reports precedent without hard-fail (FAISS dependency).",
    ).set_defaults(func=cmd_deterministic_recall_gate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
