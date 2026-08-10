"""Pytest wiring for the evals suite.

Activates the session-only token observer (see ``token_observer.py``) ONLY when
``TOKEN_OBSERVER_JSONL`` is set in the environment. When the env var is absent this
is a complete no-op, so normal (non-metered) test runs are byte-identical to before
this file existed. The observer itself is fail-open by construction (reviewer ruling
2026-08-10) — it can never raise into or alter the probe path.
"""
from __future__ import annotations

import os


def pytest_configure(config):  # noqa: ARG001 — pytest hook signature
    if not os.environ.get("TOKEN_OBSERVER_JSONL"):
        return
    try:
        from tests.evals.token_observer import install

        install()
    except Exception:
        # Fail-open: never let observer wiring break collection or the gate.
        pass
