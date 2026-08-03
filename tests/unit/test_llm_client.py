from __future__ import annotations

from types import SimpleNamespace

from llm.client import _request_safe_message


def test_request_safe_message_drops_response_only_fields_but_keeps_tool_calls():
    message = SimpleNamespace(
        model_dump=lambda **kw: {
            "role": "assistant",
            "content": None,
            "annotations": [],
            "refusal": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "open_doc", "arguments": '{"doc_id":"d1"}'},
                }
            ],
        }
    )

    payload = _request_safe_message(message)

    assert "annotations" not in payload
    assert "refusal" not in payload
    assert payload["tool_calls"][0]["id"] == "call_1"
