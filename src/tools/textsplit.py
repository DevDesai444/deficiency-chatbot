"""Char-offset text chunkers used for inline span annotation (D-GRAN cat -n pattern).

`split_sentences` finds sentence-boundary offsets over a string WITHOUT ever mutating or
re-indexing the text -- every returned (start, end) is a direct slice into the caller's own
string, so a caller that then mints a span-ID over `canonical[start:end]` gets an identity that
re-opens byte-exact. `split_windows` greedily groups those same sentence spans into
`get_section`-sized windows so a window boundary can never fall mid-sentence.
"""
from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[tuple[int, int]]:
    """Split `text` into non-empty (start, end) sentence spans.

    Boundary = punctuation in `.!?` immediately followed by whitespace (the whitespace run
    itself is consumed by the boundary, never returned as its own span). Empty/whitespace-only
    text returns `[]`; text with no such boundary returns one whole-text span.
    """
    if not text or not text.strip():
        return []
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in _SENTENCE_BOUNDARY.finditer(text):
        end = m.start()
        if end > pos and text[pos:end].strip():
            spans.append((pos, end))
        pos = m.end()
    if pos < len(text) and text[pos:].strip():
        spans.append((pos, len(text)))
    return spans or [(0, len(text))]


def split_windows(text: str, window_chars: int = 800) -> list[tuple[int, int]]:
    """Greedily accumulate `split_sentences` spans into windows of up to `window_chars`.

    A window's (start, end) is always taken directly from some sentence's own start/end --
    never computed by arithmetic mid-sentence -- so a window boundary NEVER splits a sentence.
    A single sentence longer than `window_chars` still becomes its own (oversized) window;
    splitting it further would violate the no-mid-sentence-split guarantee.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    windows: list[tuple[int, int]] = []
    win_start, win_end = sentences[0]
    for s_start, s_end in sentences[1:]:
        if s_end - win_start > window_chars:
            windows.append((win_start, win_end))
            win_start = s_start
        win_end = s_end
    windows.append((win_start, win_end))
    return windows
