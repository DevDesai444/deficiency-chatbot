"""D-16 ADDENDUM: Structural invariant — OpenAI( construction is ONLY in src/llm/client.py.

This test scans src/ for raw OpenAI( construction calls and asserts they appear in
src/llm/client.py ONLY. Any future module that constructs its own OpenAI client will
fail this test, forcing the author to route through the guarded singleton instead.

Scan rules:
  - Grep src/ recursively for lines matching OpenAI(
  - Exclude: import lines (``from openai import OpenAI``)
  - Exclude: AsyncOpenAI( (different class; not in scope)
  - Exclude: comment-only lines (stripped line starts with ``#``)
  - Exclude: docstring/triple-quote lines containing OpenAI( as literal text
    (heuristic: lines whose stripped form starts with ``"`` ``'`` ``*`` ``#`` or ``>``)
  - Exclude: lines in test files (this test suite scans src/ only)
  - Any surviving hit in a file other than src/llm/client.py is a FAILURE.

This is a PERMANENT test. Do not add exceptions or allow-lists — if a new module
needs an OpenAI client, it MUST call ``from llm.client import get_client`` instead.
"""
from __future__ import annotations

import re
from pathlib import Path


def _is_construction_line(line: str) -> bool:
    """Return True if this source line contains a real OpenAI( construction call.

    Excludes:
      - import statements
      - AsyncOpenAI( calls
      - pure comment lines (stripped line starts with #)
      - docstring / documentation lines (stripped starts with ''', \"\"\", or
        common docstring continuation characters that carry literal "OpenAI(" text)
    """
    stripped = line.strip()

    # Skip pure comment lines
    if stripped.startswith("#"):
        return False

    # Skip import lines
    if "from openai import" in line or "import openai" in line:
        return False

    # Skip AsyncOpenAI — different class, not in scope for this guard
    # (There are no AsyncOpenAI usages in src/ today; this exclusion is future-proofing
    # for the async client which has its own API surface.)
    if "AsyncOpenAI(" in line and "OpenAI(" not in line.replace("AsyncOpenAI(", ""):
        return False

    # Remove AsyncOpenAI( occurrences to avoid false positives when both appear
    line_no_async = line.replace("AsyncOpenAI(", "")

    # Must contain OpenAI( after removing AsyncOpenAI
    if "OpenAI(" not in line_no_async:
        return False

    # Skip docstring / string-literal lines that mention OpenAI( as documentation text.
    # Heuristic: stripped line starts with a quote character, or is a triple-quote marker,
    # or is a raw docstring continuation (starts with * - > for markdown-style docs).
    doc_prefixes = ('"""', "'''", '"', "'", "*", ">", "-")
    if any(stripped.startswith(p) for p in doc_prefixes):
        return False

    return True


def test_openai_construction_only_in_client_py():
    """Assert raw OpenAI( construction appears ONLY in src/llm/client.py.

    This is the structural proof that SC1 ("no external LLM endpoint is ever
    configured or called — holds BY CONSTRUCTION") is a grep-verifiable invariant.
    All OpenAI client instantiation MUST flow through the guarded singleton in
    src/llm/client.py, which applies deny-first + allow-list checks before
    constructing the underlying HTTP client.

    Failure means a new module has bypassed the on-prem guard — fix it by
    replacing the raw OpenAI(...) call with ``from llm.client import get_client``.
    """
    src_root = Path(__file__).parent.parent.parent / "src"
    assert src_root.is_dir(), f"src/ directory not found at {src_root}"

    allowed_file = src_root / "llm" / "client.py"
    assert allowed_file.is_file(), f"Expected guarded client at {allowed_file}"

    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        # client.py is the ONLY allowed site
        if py_file.resolve() == allowed_file.resolve():
            continue

        for lineno, raw_line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), start=1):
            if _is_construction_line(raw_line):
                violations.append(
                    f"{py_file.relative_to(src_root.parent)}:{lineno}: {raw_line.rstrip()}"
                )

    assert not violations, (
        "Raw OpenAI( construction found outside src/llm/client.py.\n"
        "These files bypass the on-prem guard (D-16, 21 CFR Part 11).\n"
        "Replace each with `from llm.client import get_client`:\n\n"
        + "\n".join(violations)
    )
