# grounding — grounding_span re-resolves byte-exact or the finding is not "grounded" (not dropped).
"""RED stub (Wave 0). Turns GREEN when src/verify/grounding.py lands.

A candidate whose submission_span_id re-opens byte-exact AND whose grounding_span is a substring of
the re-opened source -> grounded True. A HashMismatch (tampered stream) or an absent substring ->
grounded False, and the candidate is STILL not dropped. Includes an ABSENCE-anchor case that
re-resolves against claim_span_id (Assumption A1 branch).
"""
from __future__ import annotations

import pytest

from tests.verify.conftest import (
    absence_candidate,
    deterministic_candidate,
    make_normalized_text,
)


def test_byte_exact_reresolution_grounded_true_and_tamper_grounded_false():
    grounding = pytest.importorskip(
        "verify.grounding",
        reason="src/verify/grounding.py lands in Wave 1/3; grounding gate flips on then.",
    )
    candidate = deterministic_candidate()
    nt = make_normalized_text("Total is 0.14 percent though the largest single value is 0.15.")

    # correct grounding_span is a substring of the re-opened source -> grounded True
    assert grounding.is_grounded(candidate, nt, grounding_span="Total is 0.14 percent") is True

    # a grounding_span absent from the source -> grounded False (candidate not dropped)
    assert grounding.is_grounded(candidate, nt, grounding_span="this text is nowhere") is False

    # a tampered stream (span no longer hashes) -> grounded False, no exception escapes
    tampered = make_normalized_text("Completely different canonical content that will not hash.")
    assert grounding.is_grounded(candidate, tampered, grounding_span="Total is 0.14 percent") is False


def test_absence_anchor_reresolves_against_claim_span():
    grounding = pytest.importorskip(
        "verify.grounding",
        reason="src/verify/grounding.py lands in Wave 1/3; absence-branch gate flips on then.",
    )
    candidate = absence_candidate()  # no submission_span_id; absence_anchor.claim_span_id set
    nt = make_normalized_text("The submission states full method validation was performed.")

    # A1 branch: absence candidates re-resolve against the claim span, not submission_span_id
    assert grounding.is_grounded(candidate, nt, grounding_span="full method validation was performed") is True
