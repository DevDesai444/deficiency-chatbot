"""The 4-op canonical-text normalizer + reversible run-based canonical<->raw offset map.

This is the load-bearing correctness core (RISK-1). The offset map is what makes the cited
"verbatim quote = RAW source substring" (D-22) always renderable from a canonical span-ID
(D-23). Corrupt it and every stored finding silently drifts; it is irreversible to redesign
after Plans 06/07/08 consume it, which is why the round-trip property test gates this module.

Ops, applied in order (D-25): NFC -> guarded dehyphenation -> whitespace-collapse -> explicit
ligature fold. NOTE the ordering: dehyphenation runs BEFORE whitespace-collapse because the
guarded rule keys on the literal "-\n" line-break; collapsing whitespace first would turn the
newline into a space and the four LOCKED D-26 fixtures could never match. Ligatures are
COMPATIBILITY chars that NFC does NOT fold (Pitfall 1); the compatibility normal form would
fold them but also corrupts micro-sign/superscript (Pitfall 2, D-25), so they are folded by an
explicit map and the compatibility form is never used -- NFC is the only unicodedata form here.

The alignment is a list of runs `(canon_start, canon_len, raw_start, raw_len, kind)`; unchanged
spans coalesce into one big "equal" run, and each edit is its own run. Lookups bisect over run
starts -> O(log n); memory is O(edits), not O(chars) -- the 500-doc-scale requirement.
"""
from __future__ import annotations

import bisect
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from schemas.documents import NormalizedText, OffsetRun

# The lexicon version is IN the normalizer version: the lexicon decides which hyphens rejoin ->
# changes canonical text -> shifts every offset. Editing dehyphen_lexicon.txt without bumping
# LEXICON_VERSION is a correctness bug the sha256-pin test catches (D-24). A version bump is the
# D-24 migration path: the content-hash makes drift FAIL LOUDLY, the version distinguishes an
# intentional normalization change from corpus tampering.
LEXICON_VERSION = "1"
NORMALIZER_VERSION = f"nfc-wscollapse-gdehyph-lig/1-lex{LEXICON_VERSION}"

# Latin ligatures are COMPATIBILITY chars: NFC leaves them, NFKC folds them but also destroys
# µ->μ and ²->2 (unit-corrupting). Fold exactly these, explicitly, with offset tracking.
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}

_LEXICON_PATH = Path(__file__).parent / "dehyphen_lexicon.txt"


@lru_cache(maxsize=1)
def _lexicon() -> frozenset[str]:
    """The COMMITTED dehyphenation plausibility word list -- the ONLY word source consulted.

    Any OS/environment word list is FORBIDDEN (that is the whole reason the lexicon is a
    committed repo file): an environment source would make hyphen-rejoin decisions
    machine-dependent, so the same document would produce different canonical text / offsets /
    content-hashes on a laptop vs Databricks, silently breaking the span-ID determinism (D-19)
    the whole re-open contract rests on.
    """
    with open(_LEXICON_PATH, encoding="utf-8") as f:
        return frozenset(line.strip().lower() for line in f if line.strip())


def _default_is_plausible(token: str) -> bool:
    return token.lower() in _lexicon()


# --- record model ------------------------------------------------------------
# A record is [canon:str, raw_start:int, raw_end:int]: `canon` currently occupies canonical
# space and derives from raw[raw_start:raw_end]. Deletions have canon="" (raw preserved).


def _nfc_records(raw: str) -> list[list]:
    """Op 1 -- NFC per combining-cluster (equivalent to global NFC; it never crosses a base)."""
    records: list[list] = []
    n = len(raw)
    i = 0
    while i < n:
        j = i + 1
        while j < n and unicodedata.combining(raw[j]):
            j += 1
        records.append([unicodedata.normalize("NFC", raw[i:j]), i, j])
        i = j
    return records


def guarded_dehyphenate(text: str, is_plausible_word) -> str:
    """Op 2 (string form, D-26) -- verified against the four locked fixtures (RESEARCH:411-420).

    (a) never drop the hyphen after a digit (spec ranges: 95.0-\\n105.0%);
    (b) rejoin only when the merged token is more plausible than the hyphenated one;
    (c) otherwise keep the hyphen and drop only the line break (uncertain).
    """
    def repl(m: re.Match) -> str:
        left, right = m.group(1), m.group(2)
        if left and left[-1].isdigit():
            return f"{left}-{right}"                 # (a)
        if is_plausible_word((left + right).lower()):
            return f"{left}{right}"                  # (b)
        return f"{left}-{right}"                     # (c)

    return re.sub(r"(\S*?)-\n(\S+)", repl, text)


def _dehyphenate_records(records: list[list], is_plausible) -> list[list]:
    """Op 2 (record form) -- apply the guarded rule to adjacent '-' , '\\n' records.

    After NFC, '-' and '\\n' are always their own single-char ASCII records, so the string-level
    guarded rule maps cleanly onto record edits (set the dropped char's canon to '').
    """
    n = len(records)
    for k in range(n - 1):
        if records[k][0] == "-" and records[k + 1][0] == "\n":
            left = ""
            idx = k - 1
            while idx >= 0 and records[idx][0] and not records[idx][0].isspace():
                left = records[idx][0] + left
                idx -= 1
            right = ""
            idx = k + 2
            while idx < n and records[idx][0] and not records[idx][0].isspace():
                right += records[idx][0]
                idx += 1
            if not right:
                # regex `(\S+)` requires a right word; no rejoin, keep hyphen + drop line break.
                records[k + 1][0] = ""
            elif left and left[-1].isdigit():
                records[k + 1][0] = ""                       # (a) keep hyphen, drop \n
            elif is_plausible((left + right).lower()):
                records[k][0] = ""                           # (b) rejoin: drop hyphen
                records[k + 1][0] = ""                       #     and \n
            else:
                records[k + 1][0] = ""                       # (c) keep hyphen, drop \n
    return records


def _collapse_ws_records(records: list[list]) -> list[list]:
    """Op 3 -- collapse each maximal run of whitespace records to a single space."""
    out: list[list] = []
    i = 0
    n = len(records)
    while i < n:
        rec = records[i]
        if rec[0] and rec[0].isspace():
            raw_lo, raw_hi = rec[1], rec[2]
            j = i + 1
            while j < n and records[j][0] and records[j][0].isspace():
                raw_hi = records[j][2]
                j += 1
            out.append([" ", raw_lo, raw_hi])
            i = j
        else:
            out.append(rec)
            i += 1
    return out


def _ligature_records(records: list[list]) -> list[list]:
    """Op 4 -- fold the explicit Latin ligatures (expansion: 1 raw char -> 2-3 canon chars)."""
    for rec in records:
        if rec[0] in LIGATURES:
            rec[0] = LIGATURES[rec[0]]
    return records


def _records_to_runs(records: list[list]) -> tuple[str, list[OffsetRun]]:
    """Flatten records to canonical text + a coalesced run list."""
    runs: list[OffsetRun] = []
    parts: list[str] = []
    canon_pos = 0
    for canon, raw_lo, raw_hi in records:
        clen = len(canon)
        rlen = raw_hi - raw_lo
        if clen == 0 and rlen == 0:
            continue
        if clen == 0:
            kind = "delete"
        elif rlen == 0:
            kind = "insert"
        elif clen == rlen:
            kind = "equal"
        elif clen < rlen:
            kind = "collapse"      # many raw -> fewer canon (NFC compose / whitespace collapse)
        else:
            kind = "expand"        # one raw -> more canon (ligature)
        # coalesce consecutive 1:1 equal runs that are contiguous in canon AND raw
        if (
            kind == "equal"
            and runs
            and runs[-1].kind == "equal"
            and runs[-1].canon_start + runs[-1].canon_len == canon_pos
            and runs[-1].raw_start + runs[-1].raw_len == raw_lo
        ):
            prev = runs[-1]
            runs[-1] = OffsetRun(
                canon_start=prev.canon_start, canon_len=prev.canon_len + clen,
                raw_start=prev.raw_start, raw_len=prev.raw_len + rlen, kind="equal",
            )
        else:
            runs.append(OffsetRun(canon_start=canon_pos, canon_len=clen,
                                  raw_start=raw_lo, raw_len=rlen, kind=kind))
        parts.append(canon)
        canon_pos += clen
    return "".join(parts), runs


# --- range conversion (O(log n) via bisect over run starts) ------------------
def _owner_by_canon(runs: list[OffsetRun], c: int) -> int:
    """Index of the run (canon_len>0) that owns canonical char c."""
    starts = [r.canon_start for r in runs]
    i = bisect.bisect_right(starts, c) - 1
    # skip back/forward over zero-canon (deletion) runs to the run actually covering c
    while i >= 0 and not (runs[i].canon_len > 0 and runs[i].canon_start <= c < runs[i].canon_start + runs[i].canon_len):
        if i + 1 < len(runs) and runs[i + 1].canon_start <= c:
            i += 1
        else:
            i -= 1
    return max(0, i)


def _owner_by_raw(runs: list[OffsetRun], rpos: int) -> int:
    """Index of the run (raw_len>0) that owns raw char rpos."""
    starts = [r.raw_start for r in runs]
    i = bisect.bisect_right(starts, rpos) - 1
    while i >= 0 and not (runs[i].raw_len > 0 and runs[i].raw_start <= rpos < runs[i].raw_start + runs[i].raw_len):
        if i + 1 < len(runs) and runs[i + 1].raw_start <= rpos:
            i += 1
        else:
            i -= 1
    return max(0, i)


def canon_range_to_raw(offset_map: list[OffsetRun], cs: int, ce: int) -> tuple[int, int]:
    """Map a canonical [cs,ce) range to the raw range that produced it (D-23).

    A canonical range spanning a DROPPED hyphen returns the hyphen+newline in the raw span
    (deletions between the endpoints, and trailing deletions, are absorbed). O(log n).
    """
    if not offset_map:
        return (0, 0)
    total_canon = sum(r.canon_len for r in offset_map)
    total_raw = sum(r.raw_len for r in offset_map)
    cs = max(0, min(cs, total_canon))
    ce = max(cs, min(ce, total_canon))
    if ce <= cs:
        if cs >= total_canon:
            return (total_raw, total_raw)
        i = _owner_by_canon(offset_map, cs)
        run = offset_map[i]
        rs = run.raw_start + (cs - run.canon_start if run.kind == "equal" else 0)
        return (rs, rs)
    i = _owner_by_canon(offset_map, cs)
    run_i = offset_map[i]
    rs = run_i.raw_start + (cs - run_i.canon_start if run_i.kind == "equal" else 0)
    j = _owner_by_canon(offset_map, ce - 1)
    run_j = offset_map[j]
    if run_j.kind == "equal":
        re_ = run_j.raw_start + (ce - run_j.canon_start)
    else:
        re_ = run_j.raw_start + run_j.raw_len
    # Absorb trailing deletion runs (raw-contiguous) that follow run j -- but ONLY when ce lands
    # exactly on run_j's canonical right edge. Without this guard the loop unconditionally walks
    # forward whenever ANY zero-canon run happens to follow run_j in the run list, even when ce
    # sits deep inside a large equal run far from its own boundary -- silently snapping the end
    # of the raw span out to wherever the run's next deletion (and beyond) happens to be, instead
    # of interpolating (the END-boundary bug, D-22). Interpolation for a probe strictly inside a
    # run (any kind) never needs to see past run_j at all.
    if ce == run_j.canon_start + run_j.canon_len:
        k = j + 1
        while k < len(offset_map) and offset_map[k].canon_len == 0:
            re_ = offset_map[k].raw_start + offset_map[k].raw_len
            k += 1
    return (rs, re_)


def raw_range_to_canon(offset_map: list[OffsetRun], rs: int, re_: int) -> tuple[int, int]:
    """Map a raw [rs,re) range to the canonical range covering it (inverse of the above).

    Used by Plan 06 to convert serializer raw cell ranges into canonical span-IDs.
    """
    if not offset_map:
        return (0, 0)
    total_canon = sum(r.canon_len for r in offset_map)
    total_raw = sum(r.raw_len for r in offset_map)
    rs = max(0, min(rs, total_raw))
    re_ = max(rs, min(re_, total_raw))
    if re_ <= rs:
        if rs >= total_raw:
            return (total_canon, total_canon)
        i = _owner_by_raw(offset_map, rs)
        run = offset_map[i]
        cs = run.canon_start + (rs - run.raw_start if run.kind == "equal" else 0)
        return (cs, cs)
    i = _owner_by_raw(offset_map, rs)
    run_i = offset_map[i]
    cs = run_i.canon_start + (rs - run_i.raw_start if run_i.kind == "equal" else 0)
    j = _owner_by_raw(offset_map, re_ - 1)
    run_j = offset_map[j]
    if run_j.kind == "equal":
        ce = run_j.canon_start + (re_ - run_j.raw_start)
    else:
        ce = run_j.canon_start + run_j.canon_len
    k = j + 1
    while k < len(offset_map) and offset_map[k].raw_len == 0:
        ce = offset_map[k].canon_start + offset_map[k].canon_len
        k += 1
    return (cs, ce)


def normalize(raw_serialized: str, is_plausible_word=None, serializer_version: str = "") -> NormalizedText:
    """Normalize raw serialized text -> canonical text + retained canonical<->raw map (D-22..D-25).

    NEVER normalize anywhere else (the boundary law): parsers emit raw text only; this is the
    single place canonical text and its offset map are produced.
    """
    is_plausible = is_plausible_word or _default_is_plausible
    records = _nfc_records(raw_serialized)
    records = _dehyphenate_records(records, is_plausible)
    records = _collapse_ws_records(records)
    records = _ligature_records(records)
    canonical, runs = _records_to_runs(records)
    return NormalizedText(
        canonical=canonical,
        raw_serialized=raw_serialized,
        offset_map=runs,
        normalizer_version=NORMALIZER_VERSION,
        serializer_version=serializer_version,
    )
