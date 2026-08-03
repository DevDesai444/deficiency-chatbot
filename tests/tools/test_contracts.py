"""Contract tests for open_doc / get_section (Phase 2 Plan 01 Task 2, TOOLS-01/02)."""
from __future__ import annotations

from pathlib import Path
import re

from ingest.anchors import mint_span, open_span
from schemas.documents import NormalizedText, OffsetRun, SpanID
from tests.tools.conftest import build_corpus_index
from tools.errors import KNOWN_REASON_CODES, ToolRejected
from tools.get_section import get_section
from tools.open_doc import open_doc

_SPAN_MARKER = re.compile(r"\[d1:(\d+):(\d+)\] (.*)", re.DOTALL)


def _block(text, page=1, order=0):
    return {"text": text, "page": page, "reading_order": order, "lines": []}


def _nt_from_cache(cache: dict) -> NormalizedText:
    return NormalizedText(
        canonical=cache["canonical"], raw_serialized=cache["raw_serialized"],
        offset_map=[OffsetRun.model_validate(r) for r in cache["offset_map"]],
        normalizer_version=cache["normalizer_version"], serializer_version=cache["serializer_version"],
    )


def test_tools_return_bounded_results(tmp_path, fresh_ledger):
    marker = "UNIQUE_MARKER_NOT_IN_ANY_HEADING"
    body = f"Intro heading text. {marker} filler content here. Next heading text. more filler."
    corpus = build_corpus_index(
        tmp_path, "d1", [_block(body)],
        outline_headings=["Intro heading text.", "Next heading text."],
    )
    canonical = corpus.cached_entry("d1")["canonical"]
    assert marker in canonical   # sanity: the marker really is inside the document

    doc = open_doc(corpus, "d1", fresh_ledger)
    assert isinstance(doc, dict)
    assert marker not in repr(doc)       # open_doc NEVER returns the doc's canonical text
    assert canonical not in repr(doc)
    for outline_row in doc["outline"]:
        assert "span_id" in outline_row  # outline rows carry identifiers, not raw text ranges

    section = get_section(corpus, "d1", fresh_ledger, start=0, end=len(canonical))
    assert isinstance(section, str)
    assert marker in section             # get_section DOES return real, bounded text
    assert section.startswith("[d1:")    # every result is span-ID-annotated inline (D-GRAN)


def test_open_doc_unknown_doc_id_returns_rejection(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "d1", [_block("Some text.")])
    result = open_doc(corpus, "nonexistent", fresh_ledger)
    assert isinstance(result, ToolRejected)
    assert result.reason_code == "not_found"


def test_get_section_unknown_doc_id_returns_rejection(tmp_path, fresh_ledger):
    corpus = build_corpus_index(tmp_path, "d1", [_block("Some text.")])
    result = get_section(corpus, "nonexistent", fresh_ledger, start=0, end=5)
    assert isinstance(result, ToolRejected)
    assert result.reason_code == "not_found"


def test_get_section_heading_resolves_via_outline(tmp_path, fresh_ledger):
    body = (
        "Intro Heading text here. Filler Alpha words padding one two three. "
        "Second Heading text here. Filler Bravo words padding four five six."
    )
    corpus = build_corpus_index(
        tmp_path, "d1", [_block(body)],
        outline_headings=["Intro Heading text here.", "Second Heading text here."],
    )
    section = get_section(corpus, "d1", fresh_ledger, heading="Intro Heading")
    assert isinstance(section, str)
    assert "Filler Alpha" in section
    assert "Filler Bravo" not in section
    assert "Second Heading" not in section


def test_get_section_span_ids_reopen_byte_exact(tmp_path, fresh_ledger):
    body = "Only one sentence here."
    corpus = build_corpus_index(tmp_path, "d1", [_block(body)])
    cache = corpus.cached_entry("d1")
    nt = _nt_from_cache(cache)

    section = get_section(corpus, "d1", fresh_ledger, start=0, end=len(nt.canonical))
    assert isinstance(section, str)

    m = _SPAN_MARKER.match(section)
    assert m is not None
    start, end, printed_text = int(m.group(1)), int(m.group(2)), m.group(3)

    span = mint_span(nt.canonical, start, end, "d1", nt.normalizer_version)
    _raw, reopened_canonical = open_span(span, nt, "d1")
    assert reopened_canonical == printed_text
    assert reopened_canonical == nt.canonical[start:end]


def test_open_doc_outline_spans_are_issued_in_ledger(tmp_path, fresh_ledger):
    body = "Heading One text. Some content follows after the heading."
    corpus = build_corpus_index(
        tmp_path, "d1", [_block(body)], outline_headings=["Heading One text."],
    )
    doc = open_doc(corpus, "d1", fresh_ledger)
    assert isinstance(doc, dict)
    assert len(doc["outline"]) == 1
    span = SpanID.model_validate(doc["outline"][0]["span_id"])
    assert fresh_ledger.was_issued(span) is True


def test_every_emitted_reason_codes_are_in_the_registry():
    """D-TEL2: a code absent from KNOWN_REASON_CODES lands in telemetry's `unrecognized` bucket.
    That bucket is a loud flag, not a silent absorb -- so this test keeps it empty by construction."""
    tools_dir = Path(__file__).parents[2] / "src" / "tools"
    source = "\n".join(path.read_text() for path in tools_dir.glob("*.py"))
    emitted = set(re.findall(r'ToolRejected\([^)]*?reason_code="([a-z_]+)"', source, re.DOTALL))
    assert emitted <= set(KNOWN_REASON_CODES), sorted(emitted - set(KNOWN_REASON_CODES))
    assert "not_unique" not in emitted
