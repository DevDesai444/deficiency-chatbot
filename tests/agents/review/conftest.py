"""Offline review-agent fixtures for Phase 3.

These fixtures stand up the model boundary only. The loop tests inject a completion callable, then
run real tool code over a real persisted CorpusIndex and fresh per-test ledgers.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest, DocEntry
from llm.client import ChatTurn
from tests.tools.conftest import build_corpus_index
from tools.ledger import RetrievalLedger

_CALL_COUNTER = count(1)


@dataclass
class ScriptedChatClient:
    """Deterministic stand-in for llm.client.chat_completion_tools (RESEARCH.md Pattern 1).

    The loop receives a completion callable rather than importing the client, so offline tests
    can inject this object directly. `seen_messages` / `seen_tools` are deep copies, so a test can
    assert exactly what the loop sent on turn N even after the loop mutates its list.
    """

    script: list[ChatTurn]
    seen_messages: list[list[dict]] = field(default_factory=list)
    seen_tools: list[list[dict]] = field(default_factory=list)

    def __call__(self, messages: list[dict], tools: list[dict], **kw: Any) -> ChatTurn:
        self.seen_messages.append(copy.deepcopy(messages))
        self.seen_tools.append(copy.deepcopy(tools))
        return self.script[min(len(self.seen_messages) - 1, len(self.script) - 1)]


@dataclass
class ForcedRunaway:
    """D-BUD6's synthetic driver. Never stops; always requests more evidence.

    It varies the search query each turn so the identical-args breaker cannot be the gate that
    ends the run; budget tests using this driver must therefore prove the token ceiling.
    """

    prompt_tokens: int = 4000
    completion_tokens: int = 200
    i: int = 0

    def __call__(self, messages: list[dict], tools: list[dict], **kw: Any) -> ChatTurn:
        self.i += 1
        tool_call = make_tool_call("search_corpus", {"query": f"impurity {self.i}"})
        return ChatTurn(
            content="",
            finish_reason="tool_calls",
            tool_calls=[tool_call],
            raw_message={
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                ],
            },
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            usage_present=True,
        )


@dataclass
class ReplayClient:
    """Replay a committed JSONL transcript of ChatTurn rows, then return a natural stop turn."""

    transcript_path: str | Path
    seen_messages: list[list[dict]] = field(default_factory=list)
    seen_tools: list[list[dict]] = field(default_factory=list)
    _turns: list[ChatTurn] | None = None

    def __call__(self, messages: list[dict], tools: list[dict], **kw: Any) -> ChatTurn:
        self.seen_messages.append(copy.deepcopy(messages))
        self.seen_tools.append(copy.deepcopy(tools))
        turns = self._load_turns()
        idx = len(self.seen_messages) - 1
        if idx >= len(turns):
            return ChatTurn(
                content="",
                finish_reason="stop",
                tool_calls=[],
                raw_message={"role": "assistant", "content": ""},
                usage_present=True,
            )
        return turns[idx]

    def _load_turns(self) -> list[ChatTurn]:
        if self._turns is not None:
            return self._turns

        turns: list[ChatTurn] = []
        with Path(self.transcript_path).open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                turn = row.get("turn", row)
                raw_message = turn.get("raw_message") or turn.get("message") or {}
                turns.append(
                    ChatTurn(
                        content=turn.get("content") or raw_message.get("content") or "",
                        finish_reason=turn.get("finish_reason") or "stop",
                        tool_calls=turn.get("tool_calls") or raw_message.get("tool_calls") or [],
                        raw_message=raw_message,
                        prompt_tokens=turn.get("prompt_tokens", 0),
                        completion_tokens=turn.get("completion_tokens", 0),
                        cached_tokens=turn.get("cached_tokens", 0),
                        usage_present=turn.get("usage_present", True),
                    )
                )
        self._turns = turns
        return turns


def make_tool_call(name: str, args: dict) -> object:
    """Return the subset of OpenAI's tool-call object shape the loop consumes."""
    return SimpleNamespace(
        id=f"call_{next(_CALL_COUNTER):03d}",
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args, sort_keys=True)),
    )


def build_multi_corpus_index(tmp_path, docs: list[tuple[str, list[dict], list[str]]]) -> CorpusIndex:
    """Build + persist a real N-document CorpusIndex by extending the canonical single-doc helper.

    `docs` is a list of `(doc_id, blocks, outline_headings)` tuples. Each document is routed
    through `tests.tools.conftest.build_corpus_index`, which itself uses the real
    serialize_document -> normalize -> build_table_index -> write_doc_cache path.
    """
    entries: list[DocEntry] = []
    for doc_id, blocks, outline_headings in docs:
        single = build_corpus_index(
            tmp_path,
            doc_id=doc_id,
            blocks=blocks,
            outline_headings=outline_headings,
            filename=f"{doc_id}.pdf",
            title=f"Test Document {doc_id}",
        )
        entries.extend(single.manifest.documents)

    manifest = CoverageManifest(
        documents=entries,
        counts={"parsed": len(entries)} if entries else {},
    )
    return CorpusIndex(root=str(tmp_path), cache_dir=str(tmp_path / "cache"), manifest=manifest)


@pytest.fixture
def retrieval_ledger() -> RetrievalLedger:
    return RetrievalLedger()


@pytest.fixture
def budget_ledger():
    BudgetLedger = pytest.importorskip(
        "agents.review.budget",
        reason="BudgetLedger lands in plan 03-07; this fixture preserves the DI name now.",
    ).BudgetLedger
    return BudgetLedger()
