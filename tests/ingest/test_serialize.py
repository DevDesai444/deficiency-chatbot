"""Tests for the reading-order serializer (Plan 02, Task 2 / INGEST-05, D-31)."""
from __future__ import annotations

from tests.ingest.conftest import _block, make_doc_dict, merged_table

from ingest.serialize import SERIALIZER_VERSION, serialize_document


def test_flattens_blocks_and_cells_in_reading_order():
    grid = merged_table(headers=["A", "B"], rows=[["1", "2"]], merged_origins={})
    text, ranges = serialize_document(make_doc_dict([_block("Intro")], [grid]))
    # every block + cell text appears, in reading order
    assert "Intro" in text
    for token in ("A", "B", "1", "2"):
        assert token in text
    assert text.index("Intro") < text.index("A") < text.index("1")


def test_ranges_are_exact_cell_text():
    grid = merged_table(headers=["Alpha", "Beta"], rows=[["10", "20"]], merged_origins={})
    text, ranges = serialize_document(make_doc_dict([_block("Hdr")], [grid]))
    # raw[start:end] reproduces exactly the origin cell's text for every recorded range
    for key, (start, end) in ranges.items():
        assert text[start:end] in ("Alpha", "Beta", "10", "20")
    # spot-check a specific cell
    assert text[ranges["0,0,0"][0]:ranges["0,0,0"][1]] == "Alpha"
    assert text[ranges["0,1,1"][0]:ranges["0,1,1"][1]] == "20"


def test_merged_cell_serialized_once_covered_coord_skipped():
    # (0,1) is covered by origin (0,0); it must not be serialized separately.
    grid = merged_table(headers=["Merged", "COVERED"], rows=[["x", "y"]],
                        merged_origins={"0,1": [0, 0]})
    text, ranges = serialize_document(make_doc_dict([], [grid]))
    assert "0,0,0" in ranges          # origin recorded
    assert "0,0,1" not in ranges      # covered coord NOT recorded
    assert text.count("COVERED") == 0  # covered cell text never emitted
    assert text.count("Merged") == 1   # origin emitted exactly once


def test_deterministic_two_calls_equal():
    grid = merged_table(headers=["A", "B"], rows=[["1", "2"]], merged_origins={"1,1": [1, 0]})
    doc = make_doc_dict([_block("Intro")], [grid])
    first = serialize_document(doc)
    second = serialize_document(doc)
    assert first == second  # identical (text, cell_ranges) -- deterministic (D-31)


def test_serializer_version_stamped():
    assert SERIALIZER_VERSION == "reading-order-cells/1"
