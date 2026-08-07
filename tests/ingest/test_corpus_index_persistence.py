"""D-R5B: per-submission index persistence tests.

Verifies that ingest_corpus builds per-doc index sidecars at ingest time and that
search_corpus loads them at query time instead of re-embedding the whole corpus.

Tests:
  1. test_persisted_index_built_at_ingest — sidecars created after ingest_corpus
  2. test_npy_atomic_write_correct_path  — .npy sidecar at {key}.embeddings.npy, NOT
                                           {key}.embeddings.npy.npy (Ruling 9 npy fix)
  3. test_persisted_index_loads_at_query — search_corpus with sidecars present does NOT
                                           call embed_texts with corpus chunks (D-R5B)
  4. test_persisted_index_invalidated_on_content_change — new content_hash → new sidecar path
  5. test_sidecar_key_lookup             — _has_persisted_index locates sidecars via
                                           corpus.cache_key_for (Ruling 9 key exposure)
"""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import docx
import fitz
import numpy as np
import pytest

import ingest.classify as classify
from ingest.corpus import CorpusIndex, ingest_corpus
from ingest.store import cache_key, content_hash
from ingest.normalize import NORMALIZER_VERSION
from ingest.serialize import SERIALIZER_VERSION
from parse.pdf import PARSER_VERSION


@pytest.fixture(autouse=True)
def _no_creds(monkeypatch):
    """No Databricks creds -> deterministic, endpoint-free (no OCR, no LLM escalation)."""
    monkeypatch.setattr(
        classify, "get_settings",
        lambda: type("S", (), {"databricks_host": "", "databricks_token": ""})(),
    )


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(72, 200, 540, 720), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _docx_bytes(text: str) -> bytes:
    d = docx.Document()
    d.add_paragraph(text)
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def _write_pdf(path: Path, text: str) -> bytes:
    b = _pdf_bytes(text)
    path.write_bytes(b)
    return b


def _fake_embed_texts(texts, batch_size=8):
    """Deterministic fake embeddings: random fixed vectors keyed by text."""
    rng = np.random.default_rng(seed=42)
    vecs = rng.standard_normal((len(texts), 4)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    return vecs / norms


def _fake_embed_query(text: str) -> np.ndarray:
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)


# ---------------------------------------------------------------------------
# Test 1: sidecars are built at ingest time
# ---------------------------------------------------------------------------

def test_persisted_index_built_at_ingest(tmp_path, monkeypatch):
    """D-R5B: after ingest_corpus completes, each parsed doc has .chunks.json,
    .embeddings.npy, and .bm25.json sidecars at data/ingest_cache/{key}.*"""
    import tools.search_corpus as sc_module
    monkeypatch.setattr(sc_module, "embed_texts", _fake_embed_texts)

    corpus_root = tmp_path / "submission"
    corpus_root.mkdir()
    file_bytes = _write_pdf(corpus_root / "doc.pdf", "Stability protocol requires 40C storage.")

    cache_dir = str(tmp_path / "cache")
    corpus = ingest_corpus(corpus_root, cache_dir=cache_dir)

    # Find the key for the parsed doc
    parsed_entries = [e for e in corpus.manifest.documents if e.status in ("parsed", "parsed_partial")]
    assert len(parsed_entries) == 1, f"Expected 1 parsed doc, got {len(parsed_entries)}"

    entry = parsed_entries[0]
    key = corpus.cache_key_for(entry.doc_id)
    assert key is not None, "cache_key_for should return a key for a parsed doc"

    from tools.search_corpus import _index_sidecar_paths
    paths = _index_sidecar_paths(cache_dir, key)

    assert paths["chunks"].exists(), f".chunks.json sidecar missing at {paths['chunks']}"
    assert paths["embeddings"].exists(), f".embeddings.npy sidecar missing at {paths['embeddings']}"
    assert paths["bm25"].exists(), f".bm25.json sidecar missing at {paths['bm25']}"

    # Validate chunks.json shape
    chunks = json.loads(paths["chunks"].read_text(encoding="utf-8"))
    assert isinstance(chunks, list) and len(chunks) >= 1
    for c in chunks:
        assert {"doc_id", "start", "end", "text", "normalizer_version"} <= set(c)

    # Validate embeddings.npy shape
    emb = np.load(str(paths["embeddings"]), allow_pickle=False)
    assert emb.ndim == 2
    assert emb.shape[0] == len(chunks), f"Embedding rows {emb.shape[0]} != chunk count {len(chunks)}"


# ---------------------------------------------------------------------------
# Test 2: Ruling 9 .npy atomic-write correctness — no double-.npy extension
# ---------------------------------------------------------------------------

def test_npy_atomic_write_correct_path(tmp_path, monkeypatch):
    """Ruling 9 (npy fix): the .npy sidecar must be at {key}.embeddings.npy,
    NOT at {key}.embeddings.npy.npy (which np.save would create when using a .tmp
    suffix that doesn't end in .npy).

    Also verifies no leftover .tmp file from an interrupted atomic write.
    """
    import tools.search_corpus as sc_module
    monkeypatch.setattr(sc_module, "embed_texts", _fake_embed_texts)

    corpus_root = tmp_path / "submission"
    corpus_root.mkdir()
    _write_pdf(corpus_root / "doc.pdf", "Stability protocol requires 40C storage.")

    cache_dir = str(tmp_path / "cache")
    corpus = ingest_corpus(corpus_root, cache_dir=cache_dir)

    parsed_entries = [e for e in corpus.manifest.documents if e.status in ("parsed", "parsed_partial")]
    assert len(parsed_entries) == 1
    key = corpus.cache_key_for(parsed_entries[0].doc_id)
    assert key is not None

    from tools.search_corpus import _index_sidecar_paths
    paths = _index_sidecar_paths(cache_dir, key)

    # CORRECT: sidecar at exactly {key}.embeddings.npy
    assert paths["embeddings"].exists(), f"Missing: {paths['embeddings']}"

    # WRONG (Ruling 9 bug): {key}.embeddings.npy.npy must NOT exist
    wrong_path = Path(str(paths["embeddings"]) + ".npy")
    assert not wrong_path.exists(), (
        f"Ruling 9 npy fix failure: double-.npy file exists at {wrong_path}. "
        "np.save appended .npy to a path that did not end in .npy — fix: use open() file handle."
    )

    # No leftover .tmp file (atomic write must have completed)
    tmp_path_check = Path(str(paths["embeddings"]) + ".tmp")
    assert not tmp_path_check.exists(), f"Leftover .tmp file at {tmp_path_check} — atomic replace failed?"


# ---------------------------------------------------------------------------
# Test 3: query does NOT re-embed corpus chunks when sidecars present
# ---------------------------------------------------------------------------

def test_persisted_index_loads_at_query(tmp_path, monkeypatch):
    """D-R5B: when sidecars are present, search_corpus must NOT call embed_texts
    with multiple texts (the corpus chunks) — only embed_query is called.

    This proves the O(corpus) → O(query) cost reduction is in effect.
    """
    import tools.search_corpus as sc_module
    from tools.ledger import RetrievalLedger

    embed_texts_call_counts = []

    def counting_embed_texts(texts, batch_size=8):
        embed_texts_call_counts.append(len(texts))
        return _fake_embed_texts(texts, batch_size)

    monkeypatch.setattr(sc_module, "embed_texts", counting_embed_texts)
    monkeypatch.setattr(sc_module, "embed_query", _fake_embed_query)

    corpus_root = tmp_path / "submission"
    corpus_root.mkdir()
    _write_pdf(corpus_root / "doc.pdf", "The stability protocol requires storage at 40C and 75% RH.")

    cache_dir = str(tmp_path / "cache")
    # Ingest: embed_texts is called here to build sidecars
    corpus = ingest_corpus(corpus_root, cache_dir=cache_dir)
    # How many embed_texts calls during ingest (for building sidecars)?
    ingest_calls = list(embed_texts_call_counts)
    embed_texts_call_counts.clear()

    # Confirm sidecars exist
    assert sc_module._has_persisted_index(corpus), "Sidecars should exist after ingest"

    # Query: with sidecars present, embed_texts should NOT be called (only embed_query)
    ledger = RetrievalLedger()
    results = sc_module.search_corpus(corpus, "stability protocol", ledger, top_k=5)

    assert len(results) >= 1, "search_corpus with persisted index returned no results"
    assert embed_texts_call_counts == [], (
        f"D-R5B failure: embed_texts was called at query time ({embed_texts_call_counts}) "
        "even though sidecars exist. The persisted index path should only call embed_query."
    )


# ---------------------------------------------------------------------------
# Test 4: content change → new content_hash → new sidecar path (D-CON2)
# ---------------------------------------------------------------------------

def test_persisted_index_invalidated_on_content_change(tmp_path, monkeypatch):
    """D-CON2: changing file bytes → new content_hash → new cache_key → new sidecar path.

    The old sidecar (from the original file) is NOT picked up for the new content,
    because the cache_key changes with content_hash.
    """
    import tools.search_corpus as sc_module
    monkeypatch.setattr(sc_module, "embed_texts", _fake_embed_texts)

    corpus_root = tmp_path / "submission"
    corpus_root.mkdir()
    doc_path = corpus_root / "doc.pdf"

    # First ingest
    _write_pdf(doc_path, "Original stability protocol content at 40C.")
    cache_dir = str(tmp_path / "cache")
    corpus_v1 = ingest_corpus(corpus_root, cache_dir=cache_dir)
    parsed_v1 = [e for e in corpus_v1.manifest.documents if e.status in ("parsed", "parsed_partial")]
    assert len(parsed_v1) == 1
    key_v1 = corpus_v1.cache_key_for(parsed_v1[0].doc_id)
    assert key_v1 is not None

    # Second ingest with DIFFERENT content
    _write_pdf(doc_path, "Modified stability protocol content at 25C — a different document.")
    corpus_v2 = ingest_corpus(corpus_root, cache_dir=cache_dir)
    parsed_v2 = [e for e in corpus_v2.manifest.documents if e.status in ("parsed", "parsed_partial")]
    assert len(parsed_v2) == 1
    key_v2 = corpus_v2.cache_key_for(parsed_v2[0].doc_id)
    assert key_v2 is not None

    # Different content → different content_hash → different cache_key
    assert key_v1 != key_v2, (
        f"D-CON2: same cache_key for different content! key_v1={key_v1!r}, key_v2={key_v2!r}"
    )

    # Both sets of sidecars exist independently
    from tools.search_corpus import _index_sidecar_paths
    paths_v1 = _index_sidecar_paths(cache_dir, key_v1)
    paths_v2 = _index_sidecar_paths(cache_dir, key_v2)
    assert paths_v1["embeddings"].exists(), "v1 sidecar should still exist"
    assert paths_v2["embeddings"].exists(), "v2 sidecar should exist after second ingest"
    assert paths_v1["embeddings"] != paths_v2["embeddings"], "v1 and v2 should be at different paths"


# ---------------------------------------------------------------------------
# Test 5: Ruling 9 (key exposure) — _has_persisted_index uses cache_key_for
# ---------------------------------------------------------------------------

def test_sidecar_key_lookup(tmp_path, monkeypatch):
    """Ruling 9 (key exposure): _has_persisted_index must locate sidecars via
    corpus.cache_key_for(doc_id), NOT by re-hashing file bytes.

    Verifies: (a) _has_persisted_index returns True after ingest,
              (b) it returns False for a fresh CorpusIndex with same manifest but no sidecars,
              (c) corpus.cache_key_for returns a non-None key for parsed docs.
    """
    import tools.search_corpus as sc_module
    monkeypatch.setattr(sc_module, "embed_texts", _fake_embed_texts)

    corpus_root = tmp_path / "submission"
    corpus_root.mkdir()
    _write_pdf(corpus_root / "doc.pdf", "Stability protocol requires 40C storage conditions.")

    cache_dir = str(tmp_path / "cache")
    corpus = ingest_corpus(corpus_root, cache_dir=cache_dir)

    # (a) After ingest, _has_persisted_index is True
    assert sc_module._has_persisted_index(corpus), (
        "_has_persisted_index should return True after ingest with sidecars built"
    )

    # (b) A fresh CorpusIndex with same manifest but a DIFFERENT cache_dir (no sidecars) → False
    import copy
    corpus_no_sidecars = CorpusIndex(
        root=corpus.root,
        cache_dir=str(tmp_path / "empty_cache"),  # no sidecars here
        manifest=copy.deepcopy(corpus.manifest),
    )
    assert not sc_module._has_persisted_index(corpus_no_sidecars), (
        "_has_persisted_index should return False when sidecars are absent"
    )

    # (c) cache_key_for returns a valid key for parsed docs
    parsed_entries = [e for e in corpus.manifest.documents if e.status in ("parsed", "parsed_partial")]
    for entry in parsed_entries:
        key = corpus.cache_key_for(entry.doc_id)
        assert key is not None, f"cache_key_for({entry.doc_id!r}) returned None"
        assert isinstance(key, str) and len(key) > 0, "cache_key_for must return a non-empty string"
        # Key must not contain path-unsafe characters (D-CON2 / store._UNSAFE)
        import re
        assert re.fullmatch(r"[A-Za-z0-9._-]+", key), (
            f"cache_key contains unsafe chars: {key!r}"
        )

    # (d) cache_key_for returns None for unknown doc_id
    assert corpus.cache_key_for("nonexistent-doc-id") is None
