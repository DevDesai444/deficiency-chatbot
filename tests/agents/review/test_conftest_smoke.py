from tests.agents.review.conftest import build_multi_corpus_index
from tests.ingest.conftest import _block


def test_build_multi_corpus_index_persists_three_real_entries(tmp_path):
    docs = [
        ("doc_a", [_block("Doc A validation section")], ["Doc A"]),
        ("doc_b", [_block("Doc B impurity section")], ["Doc B"]),
        ("doc_c", [_block("Doc C stability section")], ["Doc C"]),
    ]

    corpus = build_multi_corpus_index(tmp_path, docs)

    assert len(corpus.manifest.documents) == 3
    for doc_id, _blocks, _outline in docs:
        assert corpus.cached_entry(doc_id) is not None
