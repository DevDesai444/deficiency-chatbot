# VERIFY-02 — CoverageReport states reviewed/could-not-locate; NEVER "compliant".
"""RED stub (Wave 0). Turns GREEN when src/verify/coverage.py lands.

`compliant` is deliberately unrepresentable (mirrors ComplianceVerdict). The coverage report must
expose reviewed_keep / reviewed_downgrade / could_not_locate and no "compliant" attribute or key.
"""
from __future__ import annotations

import pytest


def test_coverage_report_has_reviewed_fields_and_no_compliant():
    cov = pytest.importorskip(
        "verify.coverage",
        reason="src/verify/coverage.py lands in Wave 1/2; coverage-shape test flips on then.",
    )
    CoverageReport = cov.CoverageReport
    fields = set(CoverageReport.model_fields)

    assert {"reviewed_keep", "reviewed_downgrade", "could_not_locate"} <= fields
    assert not any("compliant" in f for f in fields), f"CoverageReport must not express compliance: {fields}"

    report = CoverageReport(reviewed_keep=[], reviewed_downgrade=[], could_not_locate=[])
    assert not hasattr(report, "compliant")
