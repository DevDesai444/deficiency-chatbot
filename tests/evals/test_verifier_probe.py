"""Phase 6 gate: D-06 two-dimensional verifier probe suite.

D-06a: >=98% machine-parsable VERDICT post-repair (ConformanceRateMetric).
D-06b (amended 2026-08-09): Per-class KEEP-recall AND DOWNGRADE-rate floors,
  scored over the DEFENSIBLE LABELED SUBSET only (FIX 1+2):
  - KEEP-recall floor: keep_correct / 6 >= 0.80
  - DOWNGRADE-rate floor: downgrade_correct / |known_planted_bad| >= 0.80
  - Two-sided tripwire: downgrade_ratio >= 0.90 OR keep_ratio >= 0.95
D-18: Both thinking modes tested separately.
D-12: VERDICT XOR ParseFailed invariant enforced per-iteration.
D-13/FIX 6: grounding_span PRESENT in parsed verdicts; byte-exact re-resolution
  is a Phase-7 gate, not Phase 6.

Run with:
  deepeval test run tests/evals/test_verifier_probe.py \\
    --identifier "phase6-verifier-conformance-discrimination"
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
import structlog

log = structlog.get_logger()

# NOTE: Only the live-endpoint test (test_verifier_conformance_and_discrimination)
# is marked @pytest.mark.integration. The invariant tests (test_matched_gt_ids_loaded_from_json,
# test_all_downgrade_stub_fails) run in standard CI — they do NOT require the live endpoint.

BETA_SUMMARY_PATH = Path(
    ".planning/phases/05-deterministic-structural-cross-document-recall"
    "/beta-measurement/beta-measurement-summary.json"
)
BETA_MVR_REPORT_PATH = Path(
    ".planning/phases/05-deterministic-structural-cross-document-recall"
    "/beta-measurement/beta-mvr1381.report.json"
)
BETA_MINI_REPORT_PATH = Path(
    ".planning/phases/05-deterministic-structural-cross-document-recall"
    "/beta-measurement/beta-minispec.report.json"
)

# D-18: Thinking-mode strings (verified in Plan 05 probes)
from tests.integration.test_nemotron_probe import THINKING_ON_SYSTEM, THINKING_OFF_SYSTEM  # noqa: E402


def _load_matched_gt_ids() -> frozenset[str]:
    """Load KEEP-expected IDs from the canonical JSON source.

    Do NOT duplicate this as a hardcoded literal — changing matched_gt_ids in
    the JSON must automatically propagate to the probe scoring.

    The JSON has matched_gt_ids at per-doc level (docs.mvr1381.matched_gt_ids,
    docs.minispec.matched_gt_ids). The summary-level key does not aggregate them.
    """
    summary = json.loads(BETA_SUMMARY_PATH.read_text())
    ids: set[str] = set()
    # Per-doc matched_gt_ids (primary source — Phase 5 format)
    for doc_data in summary.get("docs", {}).values():
        ids.update(doc_data.get("matched_gt_ids", []))
    # Also check top-level matched_gt_ids if present
    ids.update(summary.get("matched_gt_ids", []))
    return frozenset(ids)


MATCHED_GT_IDS: frozenset[str] = _load_matched_gt_ids()


def _fault_id(fault: dict, idx: int, report_prefix: str) -> str:
    """Derive a stable finding identifier from a fault entry.

    The Phase-5 report faults do NOT have a 'finding_id' or 'id' field.
    We use dedup_key when present (it is a stable content-addressed key),
    and fall back to 'report_prefix:idx:title_hash' for absence/unkeyed faults.
    This is the identifier used throughout the probe (including KNOWN_PLANTED_BAD).
    """
    dk = fault.get("dedup_key")
    if dk:
        return dk
    # Absence faults (sub_threshold emission) have no dedup_key.
    # Use a deterministic fallback so the ID is stable across runs.
    title_slug = fault.get("requirement_id", "") or fault.get("title", "")[:20].replace(" ", "_")
    aa = fault.get("absence_anchor") or {}
    req_id = aa.get("requirement_id", title_slug)
    return f"{report_prefix}:absence:{req_id}"


# ---------------------------------------------------------------------------
# FIX 2: KNOWN_PLANTED_BAD — hand-verified confirmed-false finding identifiers.
# ---------------------------------------------------------------------------
# These are the ONLY candidates scored as DOWNGRADE-expected in the discrimination
# metric. All other unmatched candidates (97 UNRESOLVED_REF + fn_gt_ids tail) are
# logged as telemetry but EXCLUDED from scoring.
#
# Designation process — Step 0 of Task 1 (hand-audited from beta-mvr1381.report.json):
#
# Identifiers are dedup_key values from beta-mvr1381.report.json STRUCTURAL faults.
# Two faults from the same table (Theoretical Plates, NLT 7000) were confirmed false
# positives by reading the evidence column:
#
#   Fault evidence: "9792 | basis: Theoretical plates (NLT 7000) ; 11400 ; 11477 ;
#   9816 ; 12601 ; 11160 ; 9792 ; HPLC # LB-1013 ; Date: 12/10/14 ; Reference:
#   Notebook # 8135, Page # 39, 46, 47, 48 ; 11477 ; 24 hours ; 1.3 ; 1.0 ; 2.0"
#
# The structural algorithm collected 15 basis spans including NON-NUMERIC rows
# (header text "Theoretical plates (NLT 7000)", notebook reference cells "HPLC # LB-1013",
# date strings "12/10/14", and cross-measurement values "1.3", "1.0", "2.0" from different
# rows). The MIN and MEAN calculations are therefore FALSE because they include mixed-unit
# non-column values in the basis set.
#
# Confirmed false positives:
#
# 1. ae0ca3bc994c6a3fe32f0593fabed6a6:37632:null
#    Title: "Labeled-aggregate MIN mismatch: stated '9792' != recomputed '1.0'"
#    Reason: The recomputed MIN of 1.0 comes from "1.0" in a different measurement row
#    included erroneously in the basis. The MIN of the actual plate-count column
#    [11400, 11477, 9816, 12601, 11160, 9792] is indeed 9792, matching the table cell.
#    The algorithm included heterogeneous rows (non-plate-count values from adjacent
#    cells) in the basis set — structural boundary detection error, not a real deficiency.
#
# 2. ae0ca3bc994c6a3fe32f0593fabed6a6:37680:null
#    Title: "Labeled-aggregate MEAN mismatch: stated '11041' != recomputed '6260.75'"
#    Reason: The recomputed MEAN of ~6261 includes the same contaminating non-plate-count
#    values (1.3, 1.0, 2.0) from adjacent rows. The MEAN of the actual plate-count column
#    [11400, 11477, 9816, 12601, 11160, 9792] is ~11041, matching the table cell exactly.
#    Same structural boundary detection error as the MIN fault above.
#
# NOTE: The MAX fault (ae0ca3bc994c6a3fe32f0593fabed6a6:37657:null, "11477 != 12601")
# is a TRUE POSITIVE — it corresponds to matched GT ID C-01 (Phase 5 caught this real
# deficiency). It is NOT in KNOWN_PLANTED_BAD.
#
# fn_gt_ids and UNRESOLVED_REF candidates are NOT included — those are unverified
# unmatched candidates. "Unmatched != false" — Phase 5 missed 23 real GT deficiencies;
# some UNRESOLVED_REF candidates may be genuine cross-references.
KNOWN_PLANTED_BAD: frozenset[str] = frozenset({
    "ae0ca3bc994c6a3fe32f0593fabed6a6:37632:null",  # reason: MIN mismatch is FP — basis included heterogeneous non-plate-count rows; MIN of plate-count column = 9792 matches table
    "ae0ca3bc994c6a3fe32f0593fabed6a6:37680:null",  # reason: MEAN mismatch is FP — same contaminated basis; MEAN of plate-count column ≈ 11041 matches table cell exactly
})


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------

@dataclass
class ProbeSample:
    finding_id: str
    evidence: str          # verbatim source span (<=500 chars)
    rule_citation: str     # the rule the finding cites (<=200 chars)
    failure_family: str
    expected_verdict: Literal["KEEP", "DOWNGRADE", "UNSCORED"]
    # UNSCORED = unverified middle (excluded from discrimination denominator)
    scored: bool           # True iff in MATCHED_GT_IDS or KNOWN_PLANTED_BAD


def load_probe_samples() -> list[ProbeSample]:
    """Load the real beta candidates from committed report JSONs.

    KEEP-expected:      finding_ids in MATCHED_GT_IDS (6 total; from JSON, not hardcoded)
    DOWNGRADE-expected: finding_ids in KNOWN_PLANTED_BAD (hand-verified confirmed-false)
    UNSCORED:           all others (unverified middle; logged but excluded from scoring)

    The split is scored over the DEFENSIBLE LABELED SUBSET only (D-06b amended 2026-08-09).
    "Unmatched != false" — Phase 5 missed 23 real GT deficiencies (fn_gt_ids);
    some unmatched candidates (UNRESOLVED_REF) may be genuine cross-references.
    """
    # FIX 2: Invariant — MATCHED_GT_IDS must have exactly 6 items (per beta-summary)
    keep_expected = MATCHED_GT_IDS
    assert len(keep_expected) == 6, (
        f"Expected 6 KEEP-expected items from matched_gt_ids, got {len(keep_expected)}. "
        f"Check that beta-measurement-summary.json has not been modified. "
        f"Current set: {sorted(keep_expected)}"
    )

    samples: list[ProbeSample] = []

    # Load from mvr1381 report
    if BETA_MVR_REPORT_PATH.exists():
        report = json.loads(BETA_MVR_REPORT_PATH.read_text())
        for idx, fault in enumerate(report.get("faults", [])):
            fid = _fault_id(fault, idx, "mvr1381")
            evidence = (
                fault.get("evidence", "")
                or fault.get("grounding_span", "")
                or "(no evidence available)"
            )
            # Derive rule citation from guidance_refs or rule_span_id
            guidance = fault.get("guidance_refs", [])
            rule = ", ".join(guidance[:2]) if guidance else fault.get("title", "Rule not cited")
            # Derive failure_family from reference_anchor anomaly, structural, absence, or leg_tag
            ra = fault.get("reference_anchor") or {}
            aa = fault.get("absence_anchor") or {}
            family = (
                ra.get("anomaly")
                or ("STRUCTURAL" if fault.get("structural_anchor") else None)
                or ("ABSENCE" if aa else None)
                or fault.get("leg_tag")
                or "unknown"
            )

            if fid in keep_expected:
                expected: Literal["KEEP", "DOWNGRADE", "UNSCORED"] = "KEEP"
                scored = True
            elif fid in KNOWN_PLANTED_BAD:
                expected = "DOWNGRADE"
                scored = True
            else:
                # Unverified middle: log as telemetry, exclude from discrimination scoring.
                # These include fn_gt_ids tail (may be genuine missed deficiencies)
                # and UNRESOLVED_REF tail (may be genuine or false — not hand-verified).
                expected = "UNSCORED"
                scored = False

            samples.append(
                ProbeSample(
                    finding_id=fid,
                    evidence=str(evidence)[:500],
                    rule_citation=str(rule)[:200],
                    failure_family=str(family),
                    expected_verdict=expected,
                    scored=scored,
                )
            )

    # Load from minispec report
    if BETA_MINI_REPORT_PATH.exists():
        report = json.loads(BETA_MINI_REPORT_PATH.read_text())
        for idx, fault in enumerate(report.get("faults", [])):
            fid = _fault_id(fault, idx, "minispec")
            evidence = (
                fault.get("evidence", "")
                or fault.get("grounding_span", "")
                or "(no evidence available)"
            )
            guidance = fault.get("guidance_refs", [])
            rule = ", ".join(guidance[:2]) if guidance else fault.get("title", "Rule not cited")
            ra = fault.get("reference_anchor") or {}
            aa = fault.get("absence_anchor") or {}
            family = (
                ra.get("anomaly")
                or ("STRUCTURAL" if fault.get("structural_anchor") else None)
                or ("ABSENCE" if aa else None)
                or fault.get("leg_tag")
                or "unknown"
            )

            if fid in keep_expected:
                expected = "KEEP"
                scored = True
            elif fid in KNOWN_PLANTED_BAD:
                expected = "DOWNGRADE"
                scored = True
            else:
                expected = "UNSCORED"
                scored = False

            samples.append(
                ProbeSample(
                    finding_id=fid,
                    evidence=str(evidence)[:500],
                    rule_citation=str(rule)[:200],
                    failure_family=str(family),
                    expected_verdict=expected,
                    scored=scored,
                )
            )

    return samples


# ---------------------------------------------------------------------------
# DeepEval metrics
# ---------------------------------------------------------------------------

class ConformanceRateMetric:
    """D-06a: >=98% machine-parsable VERDICT post-repair, per thinking mode.

    Denominator = ALL candidates (not scored-only). A model that fails to
    parse its output on any candidate fails conformance.
    """
    threshold = 0.98
    name = "conformance_rate"

    def __init__(self, counters: dict):
        self._counters = counters
        self.score = 0.0

    def measure(self, test_case) -> float:
        total = self._counters["total"]
        parsed = self._counters["parsed"]
        self.score = parsed / total if total > 0 else 0.0
        log.info("conformance_rate", score=self.score, parsed=parsed, total=total)
        return self.score

    def is_successful(self) -> bool:
        return self.score >= self.threshold


class DiscriminationAccuracyMetric:
    """D-06b (amended 2026-08-09): TWO SEPARATE hard assertions over the defensible labeled subset.

    FIX 1: Per-class floors (NOT pooled correct/total).
    FIX 2: Scored over defensible labeled subset ONLY (MATCHED_GT_IDS + KNOWN_PLANTED_BAD).
           Unverified middle (97 UNRESOLVED_REF + fn_gt_ids) excluded from denominator.

    Two independent hard assertions (both must pass):
      - KEEP-recall floor: keep_correct / keep_scored >= 0.80 (recall-critical)
        Catches the near-constant-DOWNGRADE attack: a verifier that always answers
        DOWNGRADE scores keep_correct/6 = 0/6 = 0.00 < 0.80 -> FAIL.
      - DOWNGRADE-rate floor: downgrade_correct / downgrade_scored >= 0.80 (precision)
        Only measured if KNOWN_PLANTED_BAD is non-empty; if empty, deferred to domain expert.

    Two-sided constant-verdict tripwire (scored over ALL candidates, not just labeled subset):
      - downgrade_ratio >= 0.90 -> blanket-DOWNGRADE attack -> score=0.0
      - keep_ratio >= 0.95 -> blanket-KEEP attack -> score=0.0
    Tripwire uses all-candidate ratios to catch the attack regardless of labeled subset size.

    is_successful():
      True iff BOTH floors pass (keep_recall_pass AND downgrade_rate_pass)
           AND neither tripwire fired.
    """
    threshold = 0.80  # applies independently to EACH floor
    name = "discrimination_accuracy"

    def __init__(self, counters: dict):
        self._counters = counters
        self.score = 0.0
        # Track each floor separately for is_successful()
        self._keep_recall_pass = False
        self._downgrade_rate_pass = False
        self._tripwire_fired = False

    def measure(self, test_case) -> float:
        total_all = self._counters["total"]
        keep_count_all = self._counters["keep_count_all"]
        downgrade_count_all = self._counters["downgrade_count_all"]

        # Constant-verdict tripwire (all candidates; catches attack regardless of labeled subset)
        keep_ratio = keep_count_all / total_all if total_all > 0 else 0.0
        downgrade_ratio = downgrade_count_all / total_all if total_all > 0 else 0.0
        if keep_ratio >= 0.95 or downgrade_ratio >= 0.90:
            self._tripwire_fired = True
            self.score = 0.0
            log.warning(
                "constant_verdict_tripwire_fired",
                keep_ratio=keep_ratio,
                downgrade_ratio=downgrade_ratio,
                blanket_keep=(keep_ratio >= 0.95),
                blanket_downgrade=(downgrade_ratio >= 0.90),
            )
            return self.score

        # FIX 1+2: Per-class floors over SCORED (defensible labeled subset) only
        keep_scored = self._counters["keep_scored"]      # should == 6 (len(MATCHED_GT_IDS))
        downgrade_scored = self._counters["downgrade_scored"]  # == len(KNOWN_PLANTED_BAD)
        keep_correct = self._counters["keep_correct"]
        downgrade_correct = self._counters["downgrade_correct"]

        # KEEP-recall floor: keep_correct / keep_scored >= 0.80
        keep_recall = keep_correct / keep_scored if keep_scored > 0 else 0.0
        self._keep_recall_pass = keep_recall >= self.threshold

        # DOWNGRADE-rate floor: downgrade_correct / downgrade_scored >= 0.80
        # If KNOWN_PLANTED_BAD is empty, DOWNGRADE-rate floor is not measurable — pass by default
        # (but log a warning; this indicates the labeled subset needs domain-expert annotation).
        if downgrade_scored > 0:
            downgrade_rate = downgrade_correct / downgrade_scored
            self._downgrade_rate_pass = downgrade_rate >= self.threshold
        else:
            downgrade_rate = None
            self._downgrade_rate_pass = True  # deferred — no confirmed-false subset available
            log.warning(
                "d06b_downgrade_rate_floor_not_measurable",
                reason="KNOWN_PLANTED_BAD is empty; DOWNGRADE-rate floor deferred to domain expert",
            )

        # score is the MINIMUM of the two floors (strict: both must meet the bar)
        if downgrade_rate is not None:
            self.score = min(keep_recall, downgrade_rate)
        else:
            self.score = keep_recall  # only KEEP-recall measurable

        log.info(
            "discrimination_accuracy",
            score=self.score,
            keep_recall=keep_recall,
            keep_recall_pass=self._keep_recall_pass,
            downgrade_rate=downgrade_rate,
            downgrade_rate_pass=self._downgrade_rate_pass,
            keep_scored=keep_scored,
            downgrade_scored=downgrade_scored,
            keep_correct=keep_correct,
            downgrade_correct=downgrade_correct,
            tripwire_fired=self._tripwire_fired,
        )
        return self.score

    def is_successful(self) -> bool:
        # Both floors must pass AND tripwire must not have fired
        return (
            not self._tripwire_fired
            and self._keep_recall_pass
            and self._downgrade_rate_pass
        )


# ---------------------------------------------------------------------------
# run_probe_batch (live endpoint — requires Nemotron)
# ---------------------------------------------------------------------------

def run_probe_batch(
    samples: list[ProbeSample],
    thinking_mode: Literal["on", "off"],
) -> dict[str, int | float]:
    """Run the probe batch; return counters for ConformanceRate + DiscriminationAccuracy.

    Discrimination is computed over scored=True samples ONLY (defensible labeled subset).
    Unscored samples (unverified middle: fn_gt_ids and UNRESOLVED_REF candidates) are run
    through the model and logged via structlog but do NOT count toward discrimination
    numerator or denominator.
    """
    import sys
    import os
    # Ensure src/ is in path for the live endpoint imports
    src_path = str(Path(__file__).parent.parent.parent / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from llm.client import get_client, chat_completion_tools  # type: ignore[import]
    from llm.reliability import coerce_and_validate, supports_guided_json, build_guided_extra_body  # type: ignore[import]
    from schemas.llm import VERDICT  # type: ignore[import]

    client = get_client()
    from config import get_settings  # type: ignore[import]
    model = get_settings().verifier_model
    system_prompt = THINKING_ON_SYSTEM if thinking_mode == "on" else THINKING_OFF_SYSTEM
    temperature = 0.6 if thinking_mode == "on" else 0.0
    max_tokens = 2048 if thinking_mode == "on" else 256

    extra = build_guided_extra_body(VERDICT) if supports_guided_json(client, model) else {}

    VERDICT_TOOL = {
        "type": "function",
        "function": {
            "name": "emit_verdict",
            "description": "Emit VERDICT on a candidate deficiency",
            "parameters": {
                "type": "object",
                "properties": {
                    "verdict": {"type": "string", "enum": ["KEEP", "DOWNGRADE"]},
                    "confidence": {"type": "number"},
                    "rationale": {"type": "string"},
                    "grounding_span": {"type": "string"},
                },
                "required": ["verdict", "confidence", "rationale", "grounding_span"],
                "additionalProperties": False,
            },
        },
    }

    counters: dict[str, int | float] = {
        # D-06a: conformance over ALL candidates
        "total": 0, "parsed": 0, "parse_failed": 0,
        # D-06b: discrimination over SCORED (defensible labeled subset) only
        "scored_total": 0,
        "keep_scored": 0, "downgrade_scored": 0,
        "keep_correct": 0, "downgrade_correct": 0,
        # Constant-verdict ratio computed over ALL candidates (for tripwire)
        "keep_count_all": 0, "downgrade_count_all": 0,
        # Unscored telemetry (logged only, not in discrimination)
        "unscored_keep": 0, "unscored_downgrade": 0, "unscored_parse_failed": 0,
    }

    for sample in samples:
        counters["total"] += 1
        user_msg = (
            f"Candidate finding: {sample.finding_id}\n"
            f"Failure family: {sample.failure_family}\n"
            f"Evidence span: {sample.evidence}\n"
            f"Rule violated: {sample.rule_citation}\n\n"
            f"Emit VERDICT: KEEP if this is a real deficiency, DOWNGRADE if it is a false positive."
        )
        turn = chat_completion_tools(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            tools=[VERDICT_TOOL],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra or None,
        )

        raw_args: dict = {}
        if turn.tool_calls:
            try:
                raw_args = json.loads(turn.tool_calls[0].function.arguments)
            except Exception:
                pass

        verdict_instance, failure = coerce_and_validate(raw_args, VERDICT)
        # D-12: VERDICT XOR ParseFailed invariant
        assert not (verdict_instance is not None and failure is not None), (
            f"D-12 XOR violated on {sample.finding_id}: "
            f"coerce_and_validate returned both non-None. "
            f"verdict={verdict_instance}, failure={failure}"
        )
        # D-06/FIX 6: grounding_span must be non-empty on parsed verdicts (present check only)
        # Byte-exact re-resolution against the source corpus is a Phase-7 gate — not Phase 6.
        if verdict_instance is not None:
            assert verdict_instance.grounding_span, (
                f"grounding_span is empty on VERDICT for {sample.finding_id}. "
                f"Schema requires grounding_span to be non-empty. "
                f"Phase-7 gate enforces byte-exact corpus re-resolution — "
                f"Phase 6 only checks the field is present and non-empty."
            )

        if verdict_instance is not None:
            counters["parsed"] += 1
            emitted = verdict_instance.verdict.value
            counters["keep_count_all"] += int(emitted == "KEEP")
            counters["downgrade_count_all"] += int(emitted == "DOWNGRADE")

            if sample.scored:
                counters["scored_total"] += 1
                if sample.expected_verdict == "KEEP":
                    counters["keep_scored"] += 1
                    counters["keep_correct"] += int(emitted == "KEEP")
                elif sample.expected_verdict == "DOWNGRADE":
                    counters["downgrade_scored"] += 1
                    counters["downgrade_correct"] += int(emitted == "DOWNGRADE")
            else:
                # Unscored telemetry: UNRESOLVED_REF / fn_gt_ids tail — not in discrimination
                counters["unscored_keep"] += int(emitted == "KEEP")
                counters["unscored_downgrade"] += int(emitted == "DOWNGRADE")
        else:
            counters["parse_failed"] += 1
            if sample.scored:
                counters["scored_total"] += 1
                if sample.expected_verdict == "KEEP":
                    counters["keep_scored"] += 1
                    # ParseFailed on a KEEP-expected = incorrect (strict: miss = failure)
                elif sample.expected_verdict == "DOWNGRADE":
                    counters["downgrade_scored"] += 1
                    # ParseFailed on DOWNGRADE-expected = incorrect
            else:
                counters["unscored_parse_failed"] += 1

        log.debug(
            "probe_result",
            finding_id=sample.finding_id,
            expected=sample.expected_verdict,
            scored=sample.scored,
            parsed=(verdict_instance is not None),
            verdict=(verdict_instance.verdict.value if verdict_instance else None),
            mode=thinking_mode,
        )

    return counters


# ---------------------------------------------------------------------------
# Invariant test: MATCHED_GT_IDS loaded from JSON, not hardcoded
# ---------------------------------------------------------------------------

def test_matched_gt_ids_loaded_from_json():
    """Invariant: MATCHED_GT_IDS is loaded from the JSON source and has exactly 6 entries.

    FIX 2: MATCHED_GT_IDS must NOT be a hardcoded literal — the JSON file is the
    single source of truth. If beta-measurement-summary.json changes, this test
    immediately detects the mismatch.

    The 6 matched_gt_ids (5 mvr1381 + 1 minispec) are the DEFENSIBLE KNOWN-GOOD set
    scored as KEEP-expected in the D-06b discrimination metric.
    """
    assert len(MATCHED_GT_IDS) == 6, (
        f"Expected 6 matched-GT IDs (5 mvr1381 + 1 minispec); got {len(MATCHED_GT_IDS)}: "
        f"{sorted(MATCHED_GT_IDS)}. If Phase 5 re-ran with more matches, update D-05 in "
        "06-CONTEXT.md and re-confirm the known-planted-bad subset."
    )
    assert "MS-01" in MATCHED_GT_IDS, "minispec MS-01 must be in KEEP-expected"
    assert "A-09" in MATCHED_GT_IDS, "mvr1381 A-09 must be in KEEP-expected"


# ---------------------------------------------------------------------------
# Anti-gaming test: test_all_downgrade_stub_fails (FIX 1 — two-sided tripwire proof)
# ---------------------------------------------------------------------------

def test_all_downgrade_stub_fails():
    """FIX 1: A stub verifier that ALWAYS returns DOWNGRADE MUST FAIL the discrimination gate.

    This proves the two-sided tripwire (downgrade_ratio >= 0.90 fires) AND the
    KEEP-recall floor (keep_correct/keep_scored = 0/6 = 0.00 < 0.80).

    The near-constant-DOWNGRADE attack: under the OLD pooled metric (correct/total over
    115 candidates with 6 KEEP vs 109 DOWNGRADE), a blanket-DOWNGRADE verifier scored
    109/115 = 0.948 > 0.80 while getting 0/6 real deficiencies right — a recall-
    destroying verifier that would have been certified as Phase-6 complete.

    Under the AMENDED metric (per-class floors + two-sided tripwire):
      - downgrade_ratio (blanket-DOWNGRADE) >= 0.90 -> tripwire fires -> score=0.0
      - Even without the tripwire: keep_correct/keep_scored = 0/6 = 0.00 < 0.80 -> FAIL

    This test is a REAL assertion with real assertions — no skip guards of any kind.
    If the DiscriminationAccuracyMetric implementation is correct, this test PASSES
    (asserts that the stub verifier fails the suite). If the metric still uses the
    pooled denominator, this test FAILS — which is the correct failure signal.
    """
    # Construct counters representing a blanket-DOWNGRADE verifier over the labeled subset:
    # - 6 KEEP-expected candidates all received DOWNGRADE -> keep_correct = 0
    # - KNOWN_PLANTED_BAD candidates all received DOWNGRADE -> downgrade_correct = |KNOWN_PLANTED_BAD|
    # - All 115 candidates received DOWNGRADE -> downgrade_ratio = 1.0 (tripwire: >= 0.90)
    n_known_planted = len(KNOWN_PLANTED_BAD)
    stub_counters = {
        "total": 115,
        "parsed": 115,
        "parse_failed": 0,
        "scored_total": 6 + n_known_planted,
        "keep_scored": 6,
        "downgrade_scored": n_known_planted,
        "keep_correct": 0,           # stub always returns DOWNGRADE -> 0/6 KEEP correct
        "downgrade_correct": n_known_planted,  # stub returns DOWNGRADE -> all known-bad correct
        "keep_count_all": 0,         # blanket-DOWNGRADE: 0 KEEP emitted
        "downgrade_count_all": 115,  # blanket-DOWNGRADE: 115 DOWNGRADE emitted
        "unscored_keep": 0,
        "unscored_downgrade": 115 - 6 - n_known_planted,
        "unscored_parse_failed": 0,
    }

    metric = DiscriminationAccuracyMetric(stub_counters)
    # Build a minimal test_case-like object (no deepeval import needed for this test)
    test_case = type("MinimalTestCase", (), {
        "input": "stub: blanket-DOWNGRADE verifier over 115 candidates",
        "actual_output": f"keep_correct=0/6, downgrade_ratio=1.0",
    })()
    metric.measure(test_case)

    # Assert: the stub verifier MUST FAIL (score=0.0 due to tripwire firing)
    assert metric.score == 0.0, (
        f"CRITICAL DESIGN FAILURE: A blanket-DOWNGRADE verifier produced score={metric.score} "
        f"(expected 0.0). The discrimination metric is still gameable by a near-constant-"
        f"DOWNGRADE verifier. Check that: (1) two-sided tripwire fires on downgrade_ratio >= 0.90, "
        f"(2) KEEP-recall floor is computed as keep_correct/keep_scored (not pooled correct/total). "
        f"The near-constant-DOWNGRADE attack would have certified a recall-destroying verifier as "
        f"Phase-6-complete — this test exists to prevent that."
    )
    assert not metric.is_successful(), (
        f"is_successful() returned True for a blanket-DOWNGRADE verifier. "
        f"Either the tripwire or the KEEP-recall floor must catch this."
    )


# ---------------------------------------------------------------------------
# Main D-06 gate test (live endpoint required)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def probe_samples():
    return load_probe_samples()


def _is_databricks_env() -> bool:
    """Return True if the environment is configured for Databricks / live endpoint.

    Called at test runtime (not at collection) to guard the live-endpoint probe.
    Returns False (does not skip) when called outside a Databricks environment —
    the test will be xfailed or will fail naturally with a connection error.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    try:
        from config import get_settings  # type: ignore[import]
        return get_settings().is_databricks
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.parametrize("thinking_mode", ["on", "off"])
def test_verifier_conformance_and_discrimination(thinking_mode, probe_samples):
    """D-06 gate (amended 2026-08-09): conformance >=98% AND per-class discrimination floors,
    both thinking modes separately.

    D-06b failure modes caught by the amended metric (FIX 1+2):
    1. Near-constant-DOWNGRADE verifier: keep_recall floor catches it (0/6 KEEP correct)
    2. Near-constant-KEEP verifier: keep_ratio tripwire catches it (keep_ratio >= 0.95)
    3. Pooled-accuracy gaming (OLD metric failure): impossible — denominator is per-class
    4. All-parse-failed attack: conformance metric catches it (0/total parsed < 0.98)

    FIX 2: Discrimination scored over DEFENSIBLE LABELED SUBSET ONLY:
    - KEEP-expected: 6 matched GT IDs (loaded from JSON, not hardcoded)
    - DOWNGRADE-expected: hand-verified KNOWN_PLANTED_BAD (2 confirmed structural FPs)
    - UNSCORED (logged only): 97 UNRESOLVED_REF + fn_gt_ids (unverified middle)

    FIX 6: grounding_span field is present in VERDICT schema (required) and Phase 6
    asserts it is non-empty on parsed instances. Byte-exact re-resolution against the
    source corpus is a Phase-7 gate — NOT asserted in Phase 6.

    Endpoint: This test requires a live Nemotron endpoint (ENVIRONMENT=databricks).
    It is @pytest.mark.integration and deselected in default CI addopts.
    Run explicitly via `deepeval test run ...` or `pytest -m integration` on Databricks.
    """
    counters = run_probe_batch(probe_samples, thinking_mode)

    conformance_metric = ConformanceRateMetric(counters)
    discrimination_metric = DiscriminationAccuracyMetric(counters)

    test_case = type("MinimalTestCase", (), {
        "input": f"beta candidates, thinking_mode={thinking_mode}",
        "actual_output": (
            f"parsed={counters['parsed']}/{counters['total']}, "
            f"keep_correct={counters['keep_correct']}/{counters['keep_scored']}, "
            f"downgrade_correct={counters['downgrade_correct']}/{counters['downgrade_scored']}"
        ),
    })()

    conformance_metric.measure(test_case)
    discrimination_metric.measure(test_case)

    # Use deepeval assert_test if available; otherwise assert manually.
    try:
        from deepeval import assert_test
        from deepeval.test_case import LLMTestCase
        deepeval_case = LLMTestCase(
            input=test_case.input,
            actual_output=test_case.actual_output,
        )
        assert_test(deepeval_case, [conformance_metric, discrimination_metric])
    except ImportError:
        # deepeval not installed — assert manually (no skip; test still runs and asserts)
        assert conformance_metric.is_successful(), (
            f"D-06a FAILED (thinking_mode={thinking_mode}): conformance_rate="
            f"{conformance_metric.score:.3f} < {conformance_metric.threshold}"
        )
        assert discrimination_metric.is_successful(), (
            f"D-06b FAILED (thinking_mode={thinking_mode}): discrimination not satisfied. "
            f"score={discrimination_metric.score:.3f}. "
            f"keep_recall_pass={discrimination_metric._keep_recall_pass}, "
            f"downgrade_rate_pass={discrimination_metric._downgrade_rate_pass}, "
            f"tripwire_fired={discrimination_metric._tripwire_fired}"
        )
