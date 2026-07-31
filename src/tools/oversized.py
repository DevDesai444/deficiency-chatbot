"""TOOLS-04 persist+preview+handle mechanism (plan-checker Blocker 2) -- D-GRAN-consistent
recovery from an oversized range: an oversized get_section/read_guideline-fetch request is
never silently truncated NOR does it force the agent to invent a new (start,end) by arithmetic
(D-GRAN: "the agent selects issued IDs, it never constructs ranges"). Instead the full
requested range is persisted to a scratch descriptor keyed by a HANDLE the agent can pass back
verbatim to page forward -- the only "offset math" happens here, in tool-owned code, never in
the calling model's head.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SCRATCH_DIR = "data/tool_scratch"


def make_handle(tool: str, doc_id: str, start: int, end: int) -> str:
    """Deterministic -- the SAME oversized request always yields the SAME handle, so a retried
    call is idempotent (mirrors this codebase's upsert-by-key discipline elsewhere)."""
    safe_doc = doc_id.replace("/", "_").replace(":", "_")
    return f"{tool}:{safe_doc}:{start}:{end}"


def _path_for(handle: str, scratch_dir: str) -> Path:
    return Path(scratch_dir) / f"{handle.replace(':', '_')}.json"


def persist_range(tool: str, doc_id: str, start: int, end: int, normalizer_version: str,
                   cursor: int, scratch_dir: str = DEFAULT_SCRATCH_DIR) -> str:
    """Persist a pending oversized-range descriptor (atomic write, mirrors ingest/store.py's
    temp -> os.replace convention). `cursor` is where the NEXT page-forward call should resume
    -- the caller has typically already served [start, cursor) as the immediate bounded preview.
    """
    handle = make_handle(tool, doc_id, start, end)
    Path(scratch_dir).mkdir(parents=True, exist_ok=True)
    final = _path_for(handle, scratch_dir)
    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "tool": tool, "doc_id": doc_id, "start": start, "end": end,
        "normalizer_version": normalizer_version, "cursor": cursor,
    }), encoding="utf-8")
    os.replace(tmp, final)
    return handle


def load_range(handle: str, scratch_dir: str = DEFAULT_SCRATCH_DIR) -> dict | None:
    final = _path_for(handle, scratch_dir)
    if not final.exists():
        return None
    return json.loads(final.read_text(encoding="utf-8"))


def advance_cursor(handle: str, new_cursor: int, scratch_dir: str = DEFAULT_SCRATCH_DIR) -> None:
    """Update the persisted cursor after a page has been served, so the NEXT handle call
    resumes past it rather than re-serving the same chunk. No-op if the handle is unknown."""
    descriptor = load_range(handle, scratch_dir)
    if descriptor is None:
        return
    descriptor["cursor"] = new_cursor
    final = _path_for(handle, scratch_dir)
    tmp = final.with_suffix(".tmp")
    tmp.write_text(json.dumps(descriptor), encoding="utf-8")
    os.replace(tmp, final)
