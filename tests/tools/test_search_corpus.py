"""search_corpus -- chunk, embed, fuse, annotate, record (D-RB5/D-RB6/D-GRAN/SC4).

Every test here mocks the dense (embed_texts/embed_query) leg deterministically -- patching the
names as IMPORTED into tools.search_corpus's own namespace, not retrieval.vector_search's -- so
the suite stays fast/offline (no sentence-transformers model load) while still exercising the
REAL BM25 lexical leg and the REAL reciprocal_rank_fusion combiner. This mirrors the same
monkeypatch discipline tests/rulebook/test_store.py already established for the rulebook's own
hybrid search (patch the module the function is imported INTO, not its origin module).
"""
from __future__ import annotations

import numpy as np

from ingest.anchors import open_span
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from schemas.documents import SpanID
from tests.tools.conftest import build_corpus_index
from tools.search_corpus import _nt_from_cache_entry, search_corpus


def _blk(text: str):
    return {"text": text, "page": 1, "reading_order": 0, "lines": []}


def _merge_corpora(*indices: CorpusIndex) -> CorpusIndex:
    """Combine several single-document CorpusIndex fixtures (same tmp_path/cache_dir) into one
    multi-document CorpusIndex, preserving the given ORDER in manifest.documents (the order
    _build_chunks iterates, which this file's BM25 tie-break test depends on)."""
    docs = [idx.manifest.documents[0] for idx in indices]
    return CorpusIndex(
        root=indices[0].root, cache_dir=indices[0].cache_dir,
        manifest=CoverageManifest(documents=docs),
    )


def _fixed_embed_query(_text: str) -> np.ndarray:
    return np.array([1.0, 0.0], dtype=np.float32)


# --- TOOLS-01/02/D-GRAN: shape, span-grounding, ledger recording, byte-exact reopen -----------

def test_search_corpus_returns_bounded_span_grounded_ledger_recorded_results(
    tmp_path, fresh_ledger, monkeypatch,
):
    import tools.search_corpus as sc_module

    corpus = build_corpus_index(
        tmp_path, "doc-x",
        [_blk("The stability protocol requires storage at 40C and 75% relative humidity.")],
    )
    monkeypatch.setattr(sc_module, "embed_texts", lambda texts, batch_size=8: np.array(
        [[1.0, 0.0]] * len(texts), dtype=np.float32,
    ))
    monkeypatch.setattr(sc_module, "embed_query", _fixed_embed_query)

    results = search_corpus(corpus, "stability protocol", fresh_ledger, top_k=5)

    assert isinstance(results, list)
    assert len(results) >= 1
    for r in results:
        assert set(r) == {"doc_id", "span_id", "score", "snippet"}
        assert r["doc_id"] == "doc-x"
        span = SpanID.model_validate(r["span_id"])
        # every returned span-ID is ledger.record_span-ed BEFORE being returned (D-GRAN)
        assert fresh_ledger.was_issued(span)
        # span.start/span.end are ABSOLUTE offsets into the doc's OWN canonical text: re-opening
        # via ingest.anchors.open_span against the doc's real NormalizedText reproduces exactly
        # the un-annotated portion of the snippet (TOOLS-02 byte-exact grounding).
        cache = corpus.cached_entry(r["doc_id"])
        nt = _nt_from_cache_entry(cache)
        _raw, canonical = open_span(span, nt, r["doc_id"])
        assert r["snippet"] == f"[{r['doc_id']}:{span.start}:{span.end}] {canonical}"


# --- SC4 hard subset: exact-identifier query carried by the lexical (BM25) leg ----------------

def test_search_corpus_exact_identifier_ranks_home_document_via_bm25_leg(tmp_path, fresh_ledger, monkeypatch):
    """(a) doc-a contains a distinctive numeric identifier ("11477"); (b) doc-b is an unrelated
    document with SIMILAR prose but a DIFFERENT number ("20038"). The dense leg is mocked to
    rank doc-b's chunk ABOVE doc-a's (the semantically-nearest-chunk failure mode SC4 targets) --
    proving a real dense-only search would get this wrong. search_corpus's FUSED result must
    still surface doc-a on top, because BM25 uniquely matches the "11477" token doc-a contains.
    """
    import tools.search_corpus as sc_module

    idx_c = build_corpus_index(
        tmp_path, "doc-c", [_blk("Facility calibration records are maintained quarterly per SOP-004.")],
    )
    idx_d = build_corpus_index(
        tmp_path, "doc-d", [_blk("Personnel training logs are archived in the quality management system.")],
    )
    idx_b = build_corpus_index(
        tmp_path, "doc-b", [_blk("Batch 20038 showed 0.3% degradation after six months of stability testing.")],
    )
    idx_a = build_corpus_index(
        tmp_path, "doc-a", [_blk("Batch 11477 showed 0.3% degradation after six months of stability testing.")],
    )
    # order matters for the lexical tie-break among the three zero-BM25-score docs (c, d, b) --
    # see the module docstring's hand-computed RRF trace in the plan for the full derivation.
    corpus = _merge_corpora(idx_c, idx_d, idx_b, idx_a)

    def fake_embed_texts(texts, batch_size=8):
        vecs = []
        for t in texts:
            if "11477" in t:
                vecs.append([0.7, 0.7141])       # doc-a: dense RUNNER-UP, not top
            elif "20038" in t:
                vecs.append([0.99, 0.1411])      # doc-b: dense TOP match (wrong answer alone)
            elif "calibration" in t:
                vecs.append([0.5, 0.8660])       # doc-c: dense 3rd
            else:
                vecs.append([0.1, 0.9950])       # doc-d: dense last
        return np.array(vecs, dtype=np.float32)

    monkeypatch.setattr(sc_module, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(sc_module, "embed_query", _fixed_embed_query)

    # sanity: prove dense-ALONE would get this wrong (doc-b's cosine to q=(1,0) beats doc-a's)
    assert 0.99 > 0.7  # doc-b's mocked cosine > doc-a's mocked cosine

    results = search_corpus(corpus, "11477", fresh_ledger, top_k=5)

    assert len(results) >= 1
    assert results[0]["doc_id"] == "doc-a"


# --- empty corpus: never raises ----------------------------------------------------------------

def test_search_corpus_empty_corpus_returns_empty_list_never_raises(tmp_path, fresh_ledger):
    corpus = CorpusIndex(root=str(tmp_path), cache_dir=str(tmp_path / "cache"), manifest=CoverageManifest(documents=[]))
    assert search_corpus(corpus, "anything at all", fresh_ledger, top_k=5) == []


# --- D-RB5/T-02-16: zero Databricks coupling ----------------------------------------------------

def test_search_corpus_source_has_no_databricks_symbol():
    import inspect

    import tools.search_corpus as sc_module

    source = inspect.getsource(sc_module)
    assert "is_databricks" not in source
    assert "from databricks" not in source
    assert "import databricks" not in source


# --- T-02-14: per-run index never leaks across a DIFFERENT CorpusIndex instance ----------------

def test_search_corpus_does_not_leak_index_across_different_corpus_instances(tmp_path, fresh_ledger, monkeypatch):
    import tools.search_corpus as sc_module

    monkeypatch.setattr(sc_module, "embed_texts", lambda texts, batch_size=8: np.array(
        [[1.0, 0.0]] * len(texts), dtype=np.float32,
    ))
    monkeypatch.setattr(sc_module, "embed_query", _fixed_embed_query)

    corpus_1 = build_corpus_index(tmp_path, "onlyA", [_blk("Alpha content appears only in the first corpus run.")])
    corpus_2 = build_corpus_index(tmp_path, "onlyB", [_blk("Beta content appears only in the second corpus run.")])

    results_1 = search_corpus(corpus_1, "alpha", fresh_ledger, top_k=5)
    assert {r["doc_id"] for r in results_1} == {"onlyA"}

    # querying a SECOND, DIFFERENT CorpusIndex must never surface the FIRST corpus's doc_id --
    # a module-global index leaking across calls is exactly what this guards against (D-RB5).
    results_2 = search_corpus(corpus_2, "alpha", fresh_ledger, top_k=5)
    assert {r["doc_id"] for r in results_2} <= {"onlyB"}


# --- Claude's Discretion: top_k is honored when more chunks exist than requested --------------

def test_search_corpus_respects_top_k(tmp_path, fresh_ledger, monkeypatch):
    import tools.search_corpus as sc_module

    monkeypatch.setattr(sc_module, "embed_texts", lambda texts, batch_size=8: np.array(
        [[1.0, 0.0]] * len(texts), dtype=np.float32,
    ))
    monkeypatch.setattr(sc_module, "embed_query", _fixed_embed_query)

    idx_1 = build_corpus_index(tmp_path, "d1", [_blk("First document about stability testing protocols.")])
    idx_2 = build_corpus_index(tmp_path, "d2", [_blk("Second document about stability testing protocols.")])
    idx_3 = build_corpus_index(tmp_path, "d3", [_blk("Third document about stability testing protocols.")])
    corpus = _merge_corpora(idx_1, idx_2, idx_3)

    results = search_corpus(corpus, "stability testing", fresh_ledger, top_k=2)
    assert len(results) == 2
