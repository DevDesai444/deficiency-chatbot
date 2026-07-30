"""Tests for the deterministic (no-LLM) Fault<->GroundTruthDeficiency matcher."""
from __future__ import annotations

from evals.match import _anchor_tokens, _norm, finding_text, matches, score
from evals.schema import FailureFamily, GroundTruthDeficiency


def _gt(
    id_: str,
    anchor: str,
    family: FailureFamily = FailureFamily.CROSS_REFERENCE_INTEGRITY,
    doc_id: str = "mvr1381",
) -> GroundTruthDeficiency:
    return GroundTruthDeficiency(
        id=id_, doc_id=doc_id, title=f"gt-{id_}", evidence_anchor=anchor, failure_family=family
    )


C01 = _gt("C-01", "11477")
C02 = _gt("C-02", "0.15")
REGULATORY_ITEM = _gt(
    "A-09", "<1226>", family=FailureFamily.REGULATORY_FRAMING
)


class TestNorm:
    def test_strips_whitespace_and_percent_identically(self):
        assert _norm("0.15 %") == _norm("0.15%") == "0.15"

    def test_lowercases(self):
        assert _norm("ABC") == "abc"

    def test_handles_none_and_empty(self):
        assert _norm("") == ""


class TestAnchorTokens:
    def test_single_numeric_token(self):
        assert _anchor_tokens("11477") == ["11477"]

    def test_percent_sign_excluded_from_captured_token(self):
        assert _anchor_tokens("0.15%") == ["0.15"]

    def test_space_separated_anchor_yields_two_distinct_tokens(self):
        # Regression guard: whitespace-stripping normalization must NOT run on the whole
        # anchor before tokenizing, or "11477 12601" would collapse into one merged digit run.
        assert _anchor_tokens("11477 12601") == ["11477", "12601"]

    def test_three_char_numeric_anchor_yields_no_token(self):
        # Regression guard (found scoring the golden fixture against the real 28-item GT set):
        # a bare 3-char number like "0.5" is a generic RSD/limit value reused for unrelated
        # measurements throughout the document. The floor is 4 chars, matching
        # agents.detection.verify._anchored's own `len(n) >= 4` convention, so an anchor built
        # entirely from a sub-4-char number yields zero tokens (never deterministically
        # matchable) instead of false-matching on every unrelated occurrence of that number.
        assert _anchor_tokens("0.5%") == []

    def test_four_char_numeric_anchor_is_still_a_token(self):
        # The real pinned C-02 anchor sits exactly at the floor and must remain matchable.
        assert _anchor_tokens("0.15") == ["0.15"]

    def test_short_common_word_is_not_a_token(self):
        assert _anchor_tokens("data table") == []

    def test_long_word_is_a_token(self):
        assert _anchor_tokens("degradants") == ["degradants"]


class TestMatches:
    def test_table20_finding_matches_c01(self):
        fault = {
            "evidence": (
                "Maximum: Theoretical plates: 11477 (Table 20, Section 17); "
                "In-house Equivalency Study: Theoretical plates: 12601 (Table 20, Section 17)"
            ),
            "title": (
                "Table 20's Maximum theoretical plates (11477) contradicts higher value "
                "reported in In-house Equivalency Study row (12601)"
            ),
            "detail": "",
        }
        assert matches(fault, C01)

    def test_table20_finding_does_not_match_unrelated_regulatory_item(self):
        fault = {
            "evidence": "Maximum: Theoretical plates: 11477; In-house Equivalency Study: 12601",
            "title": "Table 20's Maximum theoretical plates contradicts the equivalency row",
            "detail": "",
        }
        assert matches(fault, C01)
        assert not matches(fault, REGULATORY_ITEM)

    def test_impurity_finding_matches_c02(self):
        fault = {
            "evidence": "0.15",
            "title": "unspecified impurity 0.15% ... NMT 0.10%",
            "detail": "",
        }
        assert matches(fault, C02)

    def test_anchor_token_present_only_in_title_or_detail_does_not_match(self):
        # Regression guard (found scoring the golden fixture): matching must be scoped to
        # `evidence` alone, mirroring agents.detection.verify's real `_anchored(f.evidence,
        # corpus)` precedent. Title/detail are narrative prose that routinely restates a
        # document's own recurring vocabulary across many *different* findings on the same
        # general topic -- crediting a match off title/detail let unrelated findings that merely
        # *discuss* Absorptivity Factor / Any Unspecified Impurity false-match GT items that were
        # really about a different specific claim.
        word_anchor_gt = _gt("C-06x", "Absorptivity Factor")
        fault = {
            "evidence": "Table 11: AFs = 0.40, 1.03, 0.96",
            "title": "Absorptivity Factors in Table 11 are not derived from the linearity slopes",
            "detail": "The text states AF is calculated from Absorptivity Factor tables.",
        }
        assert not matches(fault, word_anchor_gt)

    def test_paraphrase_with_no_anchor_tokens_does_not_match(self):
        fault = {
            "evidence": "the theoretical plates figure is internally contradictory",
            "title": "Contradiction found in system suitability table",
            "detail": "The table's stated maximum does not reconcile with a row value.",
        }
        assert not matches(fault, C01)
        assert not matches(fault, C02)

    def test_two_token_anchor_requires_all_tokens_present(self):
        two_token_gt = _gt("C-01x", "11477 12601")
        assert matches(
            {"evidence": "Maximum plates 11477 vs 12601", "title": "", "detail": ""}, two_token_gt
        )
        assert not matches(
            {"evidence": "Maximum plates 11477 only", "title": "", "detail": ""}, two_token_gt
        )

    def test_acceptance_criteria_example(self):
        g = GroundTruthDeficiency(
            id="C-01",
            doc_id="mvr1381",
            title="t",
            evidence_anchor="11477 12601",
            failure_family=FailureFamily.CROSS_REFERENCE_INTEGRITY,
        )
        assert matches({"evidence": "Maximum plates 11477 vs 12601", "title": "", "detail": ""}, g)
        assert g.doc_id == "mvr1381"


class TestFindingText:
    def test_concatenates_and_normalizes_all_three_fields(self):
        fault = {"evidence": "0.15 %", "title": "Foo", "detail": "Bar"}
        text = finding_text(fault)
        assert "0.15" in text
        assert "foo" in text
        assert "bar" in text

    def test_missing_fields_default_to_empty(self):
        assert finding_text({}) == ""


class TestScore:
    def test_many_to_one_collapse_and_fp_fn(self):
        faults = [
            {"evidence": "11477 vs 12601", "title": "", "detail": ""},  # -> C-01
            {"evidence": "duplicate mention of 11477 and 12601 again", "title": "", "detail": ""},  # -> C-01 (dup)
            {"evidence": "0.15 exceeds NMT 0.10", "title": "", "detail": ""},  # -> C-02
            {"evidence": "unrelated paraphrase, no anchors here", "title": "", "detail": ""},  # FP
        ]
        result = score(faults, [C01, C02, REGULATORY_ITEM], doc_id="mvr1381")

        assert result.matched_gt_ids == {"C-01", "C-02"}
        assert result.tp_findings == [0, 1, 2]
        assert result.fp_findings == [3]
        assert result.fn_gt_ids == {"A-09"}

    def test_doc_id_scoping_excludes_other_documents_gts(self):
        other_doc_gt = _gt("Z-01", "99999", doc_id="other-doc")
        faults = [{"evidence": "11477", "title": "", "detail": ""}]
        result = score(faults, [C01, other_doc_gt], doc_id="mvr1381")
        assert result.matched_gt_ids == {"C-01"}
        # other_doc_gt is out of scope for this doc_id -- never counted as FN either.
        assert result.fn_gt_ids == set()

    def test_empty_faults_yields_all_fn_and_no_tp(self):
        result = score([], [C01, C02], doc_id="mvr1381")
        assert result.matched_gt_ids == set()
        assert result.fn_gt_ids == {"C-01", "C-02"}
        assert result.tp_findings == []
        assert result.fp_findings == []
