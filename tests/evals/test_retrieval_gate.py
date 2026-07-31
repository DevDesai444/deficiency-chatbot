"""Tests for the `retrieval-gate` CLI subcommand (SC4, D-SC4, Plan 02-07).

`cmd_retrieval_gate` is LIVE against the real eval set + real `ingest_corpus`/`search_corpus` by
design (see `evals.run`'s own module docstring, `python -m evals.run retrieval-gate`) -- re-
measuring the real ~6MB `mvr1381` PDF from scratch on every pytest run (`_search_corpus_recall_at_k`
re-embeds every chunk per GT item, with no cross-call cache) would make this file multi-minutes
slow. Instead these tests monkeypatch `evals.run.load_eval_set` + `ingest.corpus.ingest_corpus`
(patched at the names AS IMPORTED into `evals.run`'s own call sites -- the same "patch where it's
imported TO" discipline `tests/tools/test_search_corpus.py` already established for this codebase)
to a small, deterministic, offline fixture `EvalSet`/`CorpusIndex`, so the SAME real
`cmd_retrieval_gate` -> `_search_corpus_recall_at_k` -> `search_corpus` -> BM25/RRF code path is
exercised fast and reproducibly. The real, full live measurement against the real committed
baseline is validated directly via `python -m evals.run retrieval-gate` (Task 2's own acceptance
criteria; the measured numbers are recorded in `02-07-SUMMARY.md`), not duplicated here as a
slow pytest test -- mirroring `tests/evals/test_cli.py`'s own established precedent that a LIVE
mode is "exercised manually ... so it has no test here" for the true end-to-end cost.
"""
from __future__ import annotations

import inspect
import json

import numpy as np

from evals.run import _relabel_corpus_doc_id, cmd_retrieval_gate, main
from evals.schema import EvalDocument, EvalSet, FailureFamily, GroundTruthDeficiency
from tests.tools.conftest import build_corpus_index


def _blk(text: str) -> dict:
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _fixture_eval_set(doc_id: str = "rg-doc") -> EvalSet:
    return EvalSet(
        documents=[EvalDocument(doc_id=doc_id, path=f"fixtures/{doc_id}.pdf", format="pdf", held_out=False)],
        deficiencies=[
            GroundTruthDeficiency(
                id="RG-01",
                doc_id=doc_id,
                title="Table value disagreement",
                evidence_anchor="11477",
                failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
            ),
        ],
    )


def _mock_dense(monkeypatch):
    import tools.search_corpus as sc_module

    monkeypatch.setattr(
        sc_module,
        "embed_texts",
        lambda texts, batch_size=8: np.array([[1.0, 0.0]] * len(texts), dtype=np.float32),
    )
    monkeypatch.setattr(sc_module, "embed_query", lambda text: np.array([1.0, 0.0], dtype=np.float32))


def _write_baseline(tmp_path, overall_recall_at_k: float):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"overall_recall_at_k": overall_recall_at_k, "generated_from": "fixture"}))
    return path


class TestRetrievalGateSubcommand:
    """Fast, deterministic, offline exercise of `cmd_retrieval_gate`'s pass/fail branches over a
    small fixture corpus (see module docstring for why this substitutes for the real eval set)."""

    def test_help_lists_retrieval_gate(self, capsys):
        code = None
        try:
            main(["--help"])
        except SystemExit as exc:
            code = exc.code
        assert code == 0
        assert "retrieval-gate" in capsys.readouterr().out

    def test_passes_when_hard_subset_is_full_and_overall_meets_baseline(self, tmp_path, monkeypatch, capsys):
        _mock_dense(monkeypatch)
        eval_set = _fixture_eval_set()
        corpus = build_corpus_index(
            tmp_path, "rg-doc",
            [_blk("Table 20 Maximum theoretical plates recorded as 11477 in the summary row.")],
        )
        monkeypatch.setattr("evals.run.load_eval_set", lambda: eval_set)
        monkeypatch.setattr("ingest.corpus.ingest_corpus", lambda root, **kw: corpus)
        baseline_path = _write_baseline(tmp_path, 0.0)

        code = main(["retrieval-gate", "--baseline", str(baseline_path)])

        assert code == 0
        assert "RETRIEVAL-GATE OK" in capsys.readouterr().out

    def test_fails_when_measured_overall_drops_below_the_committed_baseline(self, tmp_path, monkeypatch, capsys):
        _mock_dense(monkeypatch)
        eval_set = _fixture_eval_set()
        corpus = build_corpus_index(
            tmp_path, "rg-doc",
            [_blk("Table 20 Maximum theoretical plates recorded as 11477 in the summary row.")],
        )
        monkeypatch.setattr("evals.run.load_eval_set", lambda: eval_set)
        monkeypatch.setattr("ingest.corpus.ingest_corpus", lambda root, **kw: corpus)
        # measured overall on this fixture is 1.0 (the sole GT item is covered) -- an
        # impossibly-high recorded baseline (>1.0, unreachable) forces the no-regress-floor
        # check to fail, independent of the (already-100%) hard-identifier-subset check.
        baseline_path = _write_baseline(tmp_path, 1.5)

        code = main(["retrieval-gate", "--baseline", str(baseline_path)])

        assert code == 1
        out = capsys.readouterr().out
        assert "RETRIEVAL-GATE FAILED" in out
        assert "measured" in out

    def test_fails_hard_when_exact_identifier_subset_is_not_full_regardless_of_overall_baseline(
        self, tmp_path, monkeypatch, capsys
    ):
        """D-SC4(i): the exact-identifier subset is a HARD gate, checked independent of the
        overall-recall no-regress floor -- an impossibly LOW (trivially-passing) baseline must
        NOT mask a real hard-subset miss."""
        _mock_dense(monkeypatch)
        eval_set = _fixture_eval_set()
        # corpus text deliberately does NOT contain "11477" anywhere -- the sole (hard, numeric)
        # GT item cannot be covered.
        corpus = build_corpus_index(
            tmp_path, "rg-doc", [_blk("This document mentions nothing relevant to any finding.")]
        )
        monkeypatch.setattr("evals.run.load_eval_set", lambda: eval_set)
        monkeypatch.setattr("ingest.corpus.ingest_corpus", lambda root, **kw: corpus)
        baseline_path = _write_baseline(tmp_path, 0.0)

        code = main(["retrieval-gate", "--baseline", str(baseline_path)])

        assert code == 1
        out = capsys.readouterr().out
        assert "RETRIEVAL-GATE FAILED" in out
        assert "exact-identifier subset not 100%" in out

    def test_held_out_documents_are_never_ingested_or_measured(self, tmp_path, monkeypatch, capsys):
        _mock_dense(monkeypatch)
        eval_set = EvalSet(
            documents=[
                EvalDocument(doc_id="rg-doc", path="fixtures/rg-doc.pdf", format="pdf", held_out=False),
                EvalDocument(doc_id="rg-held", path="fixtures_held/rg-held.pdf", format="pdf", held_out=True),
            ],
            deficiencies=[
                GroundTruthDeficiency(
                    id="RG-01", doc_id="rg-doc", title="Table value disagreement",
                    evidence_anchor="11477", failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
                ),
                GroundTruthDeficiency(
                    id="RG-02", doc_id="rg-held", title="Should never be measured",
                    evidence_anchor="99999", failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
                ),
            ],
        )
        corpus = build_corpus_index(
            tmp_path, "rg-doc",
            [_blk("Table 20 Maximum theoretical plates recorded as 11477 in the summary row.")],
        )
        ingested_roots: list[str] = []

        def _tracking_ingest(root, **kw):
            ingested_roots.append(str(root))
            return corpus

        monkeypatch.setattr("evals.run.load_eval_set", lambda: eval_set)
        monkeypatch.setattr("ingest.corpus.ingest_corpus", _tracking_ingest)
        baseline_path = _write_baseline(tmp_path, 0.0)

        code = main(["retrieval-gate", "--baseline", str(baseline_path)])

        assert code == 0
        # only the non-held-out doc's directory was ever ingested -- "fixtures_held" never appears
        assert ingested_roots == ["fixtures"]

    def test_a_bad_document_ingest_is_recorded_and_skipped_never_crashes_the_gate(
        self, tmp_path, monkeypatch, capsys
    ):
        eval_set = _fixture_eval_set()

        def _raising_ingest(root, **kw):
            raise RuntimeError("simulated ingest failure")

        monkeypatch.setattr("evals.run.load_eval_set", lambda: eval_set)
        monkeypatch.setattr("ingest.corpus.ingest_corpus", _raising_ingest)
        baseline_path = _write_baseline(tmp_path, 0.0)

        code = main(["retrieval-gate", "--baseline", str(baseline_path)])

        # no docs measured (empty per_doc) -> no hard subset failure, overall defaults to 0.0
        # which meets a 0.0 baseline -> exits 0, having printed the ingest failure, not crashed.
        assert code == 0
        assert "could not ingest" in capsys.readouterr().out


class TestRelabelCorpusDocId:
    """Direct coverage for the content-hash -> eval-set-logical-doc_id bridge -- a bug found
    empirically during Task 2's own live baseline run: `ingest.corpus.ingest_corpus` mints each
    `DocEntry.doc_id` as `content_hash(file_bytes)`, unrelated to the eval set's registered
    logical `doc_id` ("mvr1381", ...), which silently zeroed EVERY `_search_corpus_recall_at_k`
    result via its `r["doc_id"] != doc_id` check (a namespace mismatch, not a retrieval miss;
    confirmed by inspecting the ingested canonical text, which DID contain the anchors)."""

    def test_relabels_the_entry_matching_the_registered_filename(self, tmp_path):
        corpus = build_corpus_index(
            tmp_path, "content-hash-abc123", [_blk("Some content.")], filename="rg-doc.pdf",
        )
        doc = EvalDocument(doc_id="rg-doc", path="fixtures/rg-doc.pdf", format="pdf", held_out=False)

        relabeled = _relabel_corpus_doc_id(corpus, doc)

        assert relabeled.manifest.documents[0].doc_id == "rg-doc"
        # cache lookup still resolves -- keyed by content_hash, untouched by the doc_id relabel
        assert relabeled.cached_entry("rg-doc") is not None

    def test_leaves_non_matching_filenames_untouched(self, tmp_path):
        corpus = build_corpus_index(
            tmp_path, "content-hash-xyz789", [_blk("Unrelated content.")], filename="other.pdf",
        )
        doc = EvalDocument(doc_id="rg-doc", path="fixtures/rg-doc.pdf", format="pdf", held_out=False)

        relabeled = _relabel_corpus_doc_id(corpus, doc)

        assert relabeled.manifest.documents[0].doc_id == "content-hash-xyz789"

    def test_end_to_end_coverage_survives_a_content_hash_style_internal_doc_id(
        self, tmp_path, monkeypatch, capsys
    ):
        """Reproduces the real-world shape: an ingest_corpus-style internal doc_id
        ("content-hash-abc123") differs from the eval set's registered doc_id ("rg-doc") --
        cmd_retrieval_gate must still measure real coverage, not silently zero it."""
        _mock_dense(monkeypatch)
        eval_set = _fixture_eval_set("rg-doc")
        corpus = build_corpus_index(
            tmp_path, "content-hash-abc123",
            [_blk("Table 20 Maximum theoretical plates recorded as 11477 in the summary row.")],
            filename="rg-doc.pdf",
        )
        monkeypatch.setattr("evals.run.load_eval_set", lambda: eval_set)
        monkeypatch.setattr("ingest.corpus.ingest_corpus", lambda root, **kw: corpus)
        baseline_path = _write_baseline(tmp_path, 0.0)

        code = main(["retrieval-gate", "--baseline", str(baseline_path)])

        assert code == 0
        assert "RETRIEVAL-GATE OK" in capsys.readouterr().out


class TestRetrievalGateOffline:
    def test_cmd_retrieval_gate_source_has_no_databricks_symbol(self):
        source = inspect.getsource(cmd_retrieval_gate)
        assert "is_databricks" not in source
        assert "from databricks" not in source
        assert "import databricks" not in source
