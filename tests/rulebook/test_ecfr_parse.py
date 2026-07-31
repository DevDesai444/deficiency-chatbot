"""Tests for src/rulebook/ecfr_parse.py -- eCFR DIV8/SECTION XML -> the unified document-dict
contract (Task 1, RULES-01).

Fully offline: a small embedded XML fixture string reproduces the live-verified eCFR structure
(DIV5/DIV6/DIV8, single-escaped hierarchy_metadata, itertext()-requiring child markup) -- no
network call. The round trip proves ecfr_parse.py's output flows through the UNCHANGED Phase-1
substrate (serialize_document -> normalize -> mint_span -> open_span) byte-exact, exactly like a
submission PDF/DOCX.
"""
from __future__ import annotations

from ingest.anchors import mint_span, open_span
from ingest.normalize import normalize
from ingest.serialize import serialize_document
from rulebook.ecfr_parse import parse_ecfr_sections

# Reproduces the live-verified structure from this plan's <interfaces> block: DIV5 (PART) ->
# DIV6 (SUBPART) -> DIV8 (SECTION, TYPE="SECTION") with a single-escaped hierarchy_metadata
# attribute and 2 <P> tags, one containing a child <E> element with tail text (proves itertext()
# is used, not p.text alone).
_FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DIV5 N="211" TYPE="PART">
  <HEAD>PART 211&#x2014;CURRENT GOOD MANUFACTURING PRACTICE FOR FINISHED PHARMACEUTICALS</HEAD>
  <DIV6 N="F" TYPE="SUBPART">
    <HEAD>Subpart F&#x2014;Production and Process Controls</HEAD>
    <DIV8 N="211.166" TYPE="SECTION" hierarchy_metadata="{&quot;path&quot;:&quot;/on/_SUBSTITUTE_DATE_/title-21/section-211.166&quot;,&quot;citation&quot;:&quot;21 CFR 211.166&quot;}">
      <HEAD>&#xA7; 211.166 Stability testing.</HEAD>
      <P>(a) There shall be a written testing program designed to assess the stability characteristics of drug products, as published in the <E T="04">Federal Register</E> from time to time.</P>
      <P>(b) An adequate number of batches shall be tested to determine an appropriate expiration date.</P>
    </DIV8>
  </DIV6>
</DIV5>"""


def test_ecfr_part_ingests_and_reopens():
    results = parse_ecfr_sections(_FIXTURE_XML, "211")

    assert len(results) == 1
    doc_dict, citation = results[0]

    # citation resolves from hierarchy_metadata's JSON `citation` key, never the placeholder path.
    assert citation == "21 CFR 211.166"
    assert "_SUBSTITUTE_DATE_" not in citation

    # itertext() proof: the child <E> element's own text AND its tail text both survive --
    # p.text alone would silently drop "Federal Register" and " from time to time.".
    para_texts = [b["text"] for b in doc_dict["pages"][0]["blocks"]]
    assert any("Federal Register" in t and "from time to time" in t for t in para_texts)

    # end-to-end round trip through the UNCHANGED Phase-1 substrate -- no network call.
    raw, _cell_ranges = serialize_document(doc_dict)
    assert "211.166" in raw  # the HEAD block carries the section number

    nt = normalize(raw)
    assert "211.166" in nt.canonical

    doc_id = "ecfr-211.166"
    span = mint_span(nt.canonical, 0, len(nt.canonical), doc_id, nt.normalizer_version)
    raw_reopened, canonical_reopened = open_span(span, nt, doc_id)

    assert canonical_reopened == nt.canonical
    assert raw_reopened == nt.raw_serialized
