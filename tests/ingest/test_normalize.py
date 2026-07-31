"""RISK-1 gate: the offset-map round-trip property test + D-26 dehyphenation fixtures +
NFC/ligature invariants + the committed-lexicon sha256 pin (Plan 03 / INGEST-04).

Written BEFORE ingest/normalize.py exists (intended RED at import). The property test is the
gate every later consumer (Plan 06 anchors, 07 store, 08 classify) depends on: a corrupt or
lossy offset map silently drifts every stored citation, and is irreversible to redesign after
consumers ship.
"""
from __future__ import annotations

import hashlib
import random
import unicodedata
from pathlib import Path

from ingest.normalize import (  # noqa: E402  (import is the intended RED before Task 2)
    LEXICON_VERSION,
    NORMALIZER_VERSION,
    canon_range_to_raw,
    normalize,
    raw_range_to_canon,
)

_LEXICON_PATH = Path("src/ingest/dehyphen_lexicon.txt")

# --- alphabet the property test draws from (D-26 + NFC edge cases) -----------
_TOKENS = [
    "assay", "impurity", "method", "spec", "limit", "ﬁle", "ﬂow", "eﬀect", "ﬃn", "waﬄe",
    "  ", "   ", "\t", "\n", " ",
    "95.0-\n105.0", "2-\nethyl", "specifi-\ncation", "well-\nknown", "cross-\nlinked",
    "é", "à", "ñ",   # combining sequences (NFC composes)
    "µg", "cm²", "ABC", "xyz", "0.15%", "-", "\n\n", "co-\nvalent",
]


def _random_raw(rng: random.Random) -> str:
    return "".join(rng.choice(_TOKENS) for _ in range(rng.randint(1, 12)))


def test_offset_roundtrip():
    """For every canonical sub-range, canon_range_to_raw returns a raw span that EXPLAINS it.

    Strong invariants (hold for ALL ranges under the run-based map):
      * raw_serialized == the untouched input.
      * full canonical range maps to the full raw range.
      * every single canonical char c at [i,i+1) maps to a raw span [rs,re) such that
        re-normalizing r[rs:re] CONTAINS c (equal / compose / collapse / ligature-expand all
        satisfy this) -- boundary-robust, unlike naive substring equality.
      * a canonical range spanning a DROPPED hyphen returns the hyphen+newline in the raw slice.
      * raw_range_to_canon inverts canon_range_to_raw on a pure-equal (ASCII) string.
    """
    rng = random.Random(20260730)  # fixed seed -> reproducible
    for _ in range(500):
        r = _random_raw(rng)
        nt = normalize(r)
        assert nt.raw_serialized == r
        canon = nt.canonical
        if not canon:
            continue
        # full-range exactness
        assert canon_range_to_raw(nt.offset_map, 0, len(canon)) == (0, len(r))
        # per-char explanation
        for _ in range(8):
            i = rng.randint(0, len(canon) - 1)
            rs, re = canon_range_to_raw(nt.offset_map, i, i + 1)
            assert 0 <= rs <= re <= len(r), (r, i, rs, re)
            assert canon[i] in normalize(r[rs:re]).canonical, (repr(r), i, repr(canon[i]), rs, re)
        # monotonic: a wider canonical range never yields a narrower raw range
        a = rng.randint(0, len(canon))
        b = rng.randint(a, len(canon))
        rs1, re1 = canon_range_to_raw(nt.offset_map, a, b)
        rs2, re2 = canon_range_to_raw(nt.offset_map, max(0, a - 1), min(len(canon), b + 1))
        assert rs2 <= rs1 and re2 >= re1


def test_offset_roundtrip_dropped_hyphen_returns_hyphen():
    r = "specifi-\ncation"
    nt = normalize(r)
    assert "specification" in nt.canonical
    start = nt.canonical.index("specification")
    rs, re = canon_range_to_raw(nt.offset_map, start, start + len("specification"))
    assert "-" in r[rs:re] and "\n" in r[rs:re], (repr(r[rs:re]),)


def test_canon_range_to_raw_tightness_inside_equal_run():
    """TIGHTNESS (D-22 END-boundary bugfix): a probe range fully inside one `equal` run must
    give raw_len == canon_len -- i.e. the raw span is exactly as wide as the canonical span,
    never wider. Containment alone (rs<=re<=len(raw)) let a END-boundary bug through Phase 1:
    the trailing-deletion-absorption loop in canon_range_to_raw walked forward past run_j
    whenever ANY zero-canon run followed it in the run list, even when the probe's end sat deep
    inside a large equal run far from that run's own boundary -- silently snapping the raw end
    out to wherever the next unrelated deletion happened to be instead of interpolating.
    """
    rng = random.Random(20260731)
    for _ in range(200):
        r = _random_raw(rng)
        nt = normalize(r)
        canon = nt.canonical
        if not canon:
            continue
        for run in nt.offset_map:
            if run.kind != "equal" or run.canon_len < 2:
                continue
            # probe a sub-range strictly inside this equal run (never touching its boundary)
            lo = rng.randint(0, run.canon_len - 2)
            hi = rng.randint(lo + 1, run.canon_len - 1)
            cs, ce = run.canon_start + lo, run.canon_start + hi
            rs, re = canon_range_to_raw(nt.offset_map, cs, ce)
            assert re - rs == ce - cs, (repr(r), run, cs, ce, rs, re)


def test_canon_range_to_raw_front_edit_probe_middle_regression():
    """Regression fixture (RESEARCH: containment let this through Phase 1): one dehyphenation
    edit at the FRONT of a long string produces a small equal run followed by one large
    coalesced equal run; if the run list ALSO has a later edit further down (e.g. another
    dehyphenation near the tail), probing a range fully inside the MIDDLE of the large equal
    run must stay tight -- it must not "absorb" the far-away trailing edit.
    """
    raw = "co-\nvalent bond " + ("X" * 40000) + "y-\nz"
    nt = normalize(raw)
    big_run = max((r for r in nt.offset_map if r.kind == "equal"), key=lambda r: r.canon_len)
    assert big_run.canon_len > 39000, big_run  # sanity: this IS the big front-coalesced run
    cs, ce = big_run.canon_start + 1000, big_run.canon_start + 1130
    rs, re = canon_range_to_raw(nt.offset_map, cs, ce)
    assert (re - rs) == (ce - cs) == 130, (rs, re)
    assert re < big_run.raw_start + big_run.raw_len, (
        "raw end leaked past the probe into the tail of the run / beyond it", rs, re
    )


def test_raw_range_to_canon_inverse_on_equal_runs():
    r = "hello world assay"
    nt = normalize(r)
    assert nt.canonical == r  # pure ASCII, single spaces -> all equal runs
    for s, e in [(0, 5), (6, 11), (0, len(r)), (12, 17)]:
        rs, re = canon_range_to_raw(nt.offset_map, s, e)
        assert (rs, re) == (s, e)
        assert raw_range_to_canon(nt.offset_map, rs, re) == (s, e)


def test_guarded_dehyphenation():
    """The 4 LOCKED D-26 fixtures map to their exact canonical forms (RESEARCH:406-410)."""
    assert "95.0-105.0%" in normalize("95.0-\n105.0%").canonical          # D-26a keep (digit)
    assert "2-ethylhexanoic acid" in normalize("2-\nethylhexanoic acid").canonical  # D-26a keep
    assert "specification" in normalize("specifi-\ncation").canonical      # D-26b rejoin (plausible)
    assert "well-known" in normalize("well-\nknown").canonical             # D-26c keep hyphen, drop \n
    # and the must-NOT-corrupt negatives:
    assert "95.0105.0" not in normalize("95.0-\n105.0%").canonical
    assert "2ethylhexanoic" not in normalize("2-\nethylhexanoic acid").canonical


def test_normalization_invariants():
    # ligature folds via explicit map (NOT NFKC), length grows
    assert normalize("ﬁle").canonical == "file"
    assert normalize("waﬄe").canonical == "waffle"
    # NFC composes combining sequence
    assert normalize("é").canonical == "é"  # é
    # unit-critical chars PRESERVED (NFKC would corrupt these)
    assert normalize("µg").canonical == "µg"           # U+00B5 micro sign, not Greek mu
    assert "µ" in normalize("µg").canonical and "μ" not in normalize("µg").canonical
    assert normalize("cm²").canonical == "cm²"          # superscript two preserved, not "2"
    # case preserved
    assert normalize("ABCdef").canonical == "ABCdef"
    # version stamped
    assert isinstance(NORMALIZER_VERSION, str) and NORMALIZER_VERSION
    assert normalize("x").normalizer_version == NORMALIZER_VERSION


def test_lexicon_version_pin():
    """The committed lexicon's sha256 is pinned; an un-versioned edit fails this test (D-24).

    Editing dehyphen_lexicon.txt changes which hyphens rejoin -> changes canonical text ->
    shifts every offset. The pin forces a LEXICON_VERSION bump alongside any lexicon edit.
    """
    assert _LEXICON_PATH.exists(), _LEXICON_PATH
    actual = hashlib.sha256(_LEXICON_PATH.read_bytes()).hexdigest()
    # Bump LEXICON_VERSION and update EXPECTED below together whenever the lexicon changes.
    expected = {
        "1": EXPECTED_LEXICON_SHA256,
    }
    assert LEXICON_VERSION in expected, f"unknown LEXICON_VERSION {LEXICON_VERSION}"
    assert actual == expected[LEXICON_VERSION], (
        f"lexicon changed: bump LEXICON_VERSION and update this pin (got {actual})"
    )


# Pin of the committed dehyphen_lexicon.txt (LEXICON_VERSION "1"). Regenerate + bump both together.
EXPECTED_LEXICON_SHA256 = "c77e8bad9ee348e455fbbe947acf43c2608e959d0a8cc2cbb17830ce740c76c8"
