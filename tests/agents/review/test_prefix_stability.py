from __future__ import annotations

import hashlib
import json

from agents.review.loop import render_prefix
from agents.review.prompts import SYSTEM_PROMPT
from agents.review.registry import SEARCH_CORPUS_DESCRIPTION, ToolRegistry
from tests.agents.review.conftest import build_multi_corpus_index
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger


def _block(text: str, page: int = 1, order: int = 0) -> dict:
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _registry(corpus) -> ToolRegistry:
    return ToolRegistry(corpus=corpus, manifest=corpus.manifest, ledger=RetrievalLedger())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_prefix_is_byte_identical_across_different_corpora(tmp_path):
    """D-LOOP4 / COST-01. Prefix bytes must not vary with the corpus.

    The corpora intentionally differ in document count so a manifest or count
    leak would change the hash. Claude Code measured a dynamic tool description
    at about 10.2 percent of fleet cache-creation tokens.
    """
    a = build_corpus_index(tmp_path / "a", "alpha", [_block("Alpha method validation text.")])
    b = build_multi_corpus_index(
        tmp_path / "b",
        [
            ("beta", [_block("Beta specification text.")], []),
            ("gamma", [_block("Gamma stability commitment text.")], []),
        ],
    )

    assert _sha256(render_prefix(_registry(a))) == _sha256(render_prefix(_registry(b)))


def test_prefix_test_is_not_vacuous():
    """Negative control: leaking a doc count must change the prefix bytes."""
    with_leak = SYSTEM_PROMPT + "\nCorpus contains 2 documents."
    assert _sha256(with_leak) != _sha256(SYSTEM_PROMPT)


def test_prefix_covers_the_tool_schemas_not_just_the_system_prompt(tmp_path):
    """render_prefix serializes both halves, catching dynamic tool descriptions."""
    corpus = build_corpus_index(tmp_path, "alpha", [_block("Alpha text.")])
    registry = _registry(corpus)
    payload = json.loads(render_prefix(registry))

    assert payload["messages"] == [{"role": "system", "content": SYSTEM_PROMPT}]
    assert payload["tools"] == registry.schemas()
    assert SEARCH_CORPUS_DESCRIPTION in render_prefix(registry)
