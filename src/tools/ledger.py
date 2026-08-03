"""Per-agent-run retrieval ledger (D-GRAN issuance tracking + COST-04 read-dedup).

Constructor-injected, never a module global (Security Domain V3 -- Pitfall 9): one instance
per agent run, threaded explicitly through every tool call. Two responsibilities: (1) which
span-IDs has this session actually SEEN (rendered inline in some tool result) -- emit_finding
refuses an ID the model never actually retrieved; (2) has this exact (doc_id,start,end) RANGE
already been fully served this session -- COST-04's "still current" stub short-circuits a
repeat request instead of re-rendering + re-transmitting the same text.
"""
from __future__ import annotations

from schemas.documents import SpanID


class RetrievalLedger:
    def __init__(self) -> None:
        self._issued: set[tuple[str, int, int]] = set()
        self._served: set[tuple[str, int, int]] = set()
        self._dedup_checks = 0
        self._dedup_hits = 0
        self.embedding_time_s = 0.0

    def record_span(self, span: SpanID) -> None:
        self._issued.add((span.doc_id, span.start, span.end))

    def was_issued(self, span: SpanID) -> bool:
        return (span.doc_id, span.start, span.end) in self._issued

    def check_and_mark_served(self, doc_id: str, start: int, end: int) -> bool:
        """Returns True on a DEDUP HIT (caller must return the stub, not full text); False
        on first request (caller renders full text; this call already marks it served)."""
        self._dedup_checks += 1
        key = (doc_id, start, end)
        if key in self._served:
            self._dedup_hits += 1
            return True
        self._served.add(key)
        return False

    def dedup_hit_rate(self) -> float:
        return self._dedup_hits / self._dedup_checks if self._dedup_checks else 0.0

    def record_embedding_time(self, seconds: float) -> None:
        self.embedding_time_s += max(0.0, seconds)
