"""Tests for the tool rejection reason-code registry."""
from __future__ import annotations

from tools.errors import KNOWN_REASON_CODES, ToolRejected


def test_known_reason_codes_is_dict_with_one_line_meanings():
    assert isinstance(KNOWN_REASON_CODES, dict)
    assert KNOWN_REASON_CODES
    for code, meaning in KNOWN_REASON_CODES.items():
        assert isinstance(code, str)
        assert isinstance(meaning, str)
        assert code
        assert meaning.strip()
        assert "\n" not in meaning


def test_tool_rejected_half_defaults_to_empty_string():
    rejected = ToolRejected(tool="open_doc", reason_code="not_found", reason="missing")
    assert rejected.half == ""
