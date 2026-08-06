"""Tests for the `absence-gate` CLI subcommand skip-vs-fail semantics (WR-03, Plan 04-03).

`cmd_absence_gate` is LIVE against the real eval set + real `ingest_corpus` + the real
`enumerate_absences` pass by design (see `evals.run`'s module docstring). Re-ingesting the real
absence PDFs and re-building the rulebook edge store on every pytest run would make this file
multi-minutes slow, so -- mirroring `tests/evals/test_retrieval_gate.py`'s established "patch where
it's imported TO" discipline -- these tests monkeypatch the gate's own imported call sites
(`evals.run.load_eval_set`, `ingest.corpus.ingest_corpus`, and the lazily-imported rulebook edge
builders / absence pass) to small deterministic fixtures. This exercises the SAME real
`cmd_absence_gate` control flow (skip accounting, measured-doc accounting, exit codes) fast and
offline. The real full live measurement is validated via `python -m evals.run absence-gate`.

WR-03: the gate must distinguish "no local corpus to measure" (every absence doc skipped ->
exit 0 with a SKIPPED message, mirroring cmd_retrieval_gate's missing-corpus tolerance) from a
genuine recall regression (>=1 doc measured but aggregate <= 0.0 / below floor -> exit 1). A clean
checkout where `data/` is gitignored must NOT fail-close the build.
"""
from __future__ import annotations

import json

from evals.run import main
from evals.schema import EvalDocument, EvalSet, FailureFamily, GroundTruthDeficiency


def _absence_eval_set() -> EvalSet:
    """One non-held-out doc carrying a single absence_of_evidence GT item."""
    return EvalSet(
        documents=[
            EvalDocument(doc_id="ag-doc", path="fixtures/ag-doc.pdf", format="pdf", held_out=False),
        ],
        deficiencies=[
            GroundTruthDeficiency(
                id="AG-01",
                doc_id="ag-doc",
                title="Required item not addressed",
                evidence_anchor="",
                failure_family=FailureFamily.ABSENCE_OF_EVIDENCE,
            ),
        ],
    )


def _write_baseline(tmp_path, *, threshold: float = 0.04, floor: float = 0.0):
    path = tmp_path / "absence_baseline.json"
    path.write_text(
        json.dumps(
            {
                "threshold": threshold,
                "non_held_out_aggregate": {"absence_recall": floor},
                "generated_from": "fixture",
            }
        )
    )
    return path


def _patch_rulebook_noops(monkeypatch):
    """Neutralize the gate's lazily-imported rulebook edge build + index load. Their real work
    (vendoring the rulebook store, validating provenance spans against it) is irrelevant to the
    skip/fail accounting under test, and requires a local store this offline unit test never builds.
    `load_requirement_index` must retain a `.cache_clear` attribute (the gate calls it)."""
    def _fake_load(*a, **k):
        return []

    _fake_load.cache_clear = lambda: None  # the gate calls load_requirement_index.cache_clear()
    monkeypatch.setattr("rulebook.requirement_index.build_requirement_edges", lambda *a, **k: None)
    monkeypatch.setattr("rulebook.requirement_index.load_requirement_index", _fake_load)


def test_all_absence_docs_skipped_returns_skipped_exit_zero(tmp_path, monkeypatch, capsys):
    """WR-03: on a clean checkout every absence doc fails to ingest -> nothing measured. The gate
    must return 0 with a distinct SKIPPED message, NOT a false-negative 'gap not recovered'."""
    _patch_rulebook_noops(monkeypatch)
    monkeypatch.setattr("evals.run.load_eval_set", lambda: _absence_eval_set())

    def _raising_ingest(root, **kw):
        raise FileNotFoundError("data/ is gitignored on a clean checkout")

    monkeypatch.setattr("ingest.corpus.ingest_corpus", _raising_ingest)
    baseline_path = _write_baseline(tmp_path)

    code = main(["absence-gate", "--baseline", str(baseline_path)])

    out = capsys.readouterr().out
    assert code == 0, f"missing-corpus must not fail the build; out={out}"
    assert "ABSENCE-GATE SKIPPED (no local corpus)" in out
    assert "ABSENCE-GATE FAILED" not in out


def test_measured_doc_with_zero_recall_still_fails_exit_one(tmp_path, monkeypatch, capsys):
    """The real-failure path is intact: a doc that DID ingest (measured) but recovered nothing
    (enumerate_absences emitted 0 candidates) yields aggregate 0.000 -> exit 1 FAILED. The WR-03
    skip guard must not swallow a genuine recall regression."""
    _patch_rulebook_noops(monkeypatch)
    monkeypatch.setattr("evals.run.load_eval_set", lambda: _absence_eval_set())

    class _FakeCorpus:
        manifest = object()

    monkeypatch.setattr("ingest.corpus.ingest_corpus", lambda root, **kw: _FakeCorpus())
    monkeypatch.setattr("evals.run._relabel_corpus_doc_id", lambda corpus, doc: corpus)
    # the absence pass runs but recovers nothing -> emitted == 0 -> matched == 0 -> aggregate 0.0
    monkeypatch.setattr("rulebook.absence.enumerate_absences", lambda *a, **k: [])
    baseline_path = _write_baseline(tmp_path)

    code = main(["absence-gate", "--baseline", str(baseline_path)])

    out = capsys.readouterr().out
    assert code == 1, f"a measured-but-unrecovered doc must fail; out={out}"
    assert "ABSENCE-GATE FAILED" in out
    assert "SKIPPED" not in out


def test_measured_doc_recovered_passes_exit_zero(tmp_path, monkeypatch, capsys):
    """A doc that ingested AND recovered (>=1 grounded candidate) lifts the aggregate above 0.000
    and meets the floor -> exit 0 OK. Confirms the SKIPPED short-circuit does not shadow the
    normal success path."""
    _patch_rulebook_noops(monkeypatch)
    monkeypatch.setattr("evals.run.load_eval_set", lambda: _absence_eval_set())

    class _FakeCorpus:
        manifest = object()

    monkeypatch.setattr("ingest.corpus.ingest_corpus", lambda root, **kw: _FakeCorpus())
    monkeypatch.setattr("evals.run._relabel_corpus_doc_id", lambda corpus, doc: corpus)
    # one grounded candidate -> emitted == 1 -> the doc's single required absence item is recovered
    monkeypatch.setattr("rulebook.absence.enumerate_absences", lambda *a, **k: [object()])
    baseline_path = _write_baseline(tmp_path)

    code = main(["absence-gate", "--baseline", str(baseline_path)])

    out = capsys.readouterr().out
    assert code == 0, f"a measured-and-recovered doc must pass; out={out}"
    assert "ABSENCE-GATE OK" in out
    assert "SKIPPED" not in out
