# VERIFY-03 — the tail candidate panel excludes the producer family (qwen).
"""RED stub (Wave 0). Turns GREEN when src/verify/panel.py lands.

For a tail candidate produced by the qwen family, panel_for("qwen") contains no model whose
config.MODEL_LINEAGE is "qwen" (cross-family decorrelation via config.MODEL_LINEAGE).
"""
from __future__ import annotations

import pytest


def test_panel_for_qwen_excludes_qwen_lineage():
    panel_mod = pytest.importorskip(
        "verify.panel",
        reason="src/verify/panel.py lands in Wave 1/3; panel-family test flips on then.",
    )
    from config import MODEL_LINEAGE

    panel = panel_mod.panel_for("qwen")

    assert panel, "panel_for('qwen') must return at least one decorrelated verifier"
    assert all(MODEL_LINEAGE.get(m) != "qwen" for m in panel), (
        f"panel for a qwen producer must contain no qwen-lineage model: {panel}"
    )


def test_panel_for_none_producer_allows_any_fleet_mix():
    panel_mod = pytest.importorskip(
        "verify.panel",
        reason="src/verify/panel.py lands in Wave 1/3; panel-family test flips on then.",
    )
    from config import VERIFIER_FLEET

    # deterministic candidate (no model producer) -> any fleet mix is valid
    panel = panel_mod.panel_for(None)
    assert set(panel) <= set(VERIFIER_FLEET)
    assert panel, "deterministic candidate must still get a non-empty verifier panel"
