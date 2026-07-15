# DefPredict — Implementation Plan

Line references verified against `main` @ `f0c285c`.

> **Steps 1 and 2 have shipped.** The BEFORE/AFTER blocks below are the design record,
> not the current code — read them for the reasoning, not the line numbers. See
> `PHASES.md` for what is merged and what is still open.

## The only goal

An analyst uploads a PDF. They read the findings and recommendations. They judge
them against their own expertise. **The output has to be worth their time.**

Nothing else is in scope. Not metrics, not scaling, not auth, not eval harnesses.
The test is: does a regulatory analyst read this and find it useful?

## What "worth their time" means, concretely

Today, on the 29-page Combipatch E&L report, the system produced this after 478
seconds:

> **1. Spec Incomplete** — medium
> Elemental analysis is incomplete.

An analyst reads that and learns nothing. They cannot verify it without re-reading
29 pages. They cannot act on it. It is worse than no output, because it consumed
eight minutes and produced a false sense that the document was checked.

What the same document should produce:

> **Cross-reference inconsistency** — medium
> The AET value is stated inconsistently across the report.
> - Page 7: *"22.727 µg/g"*
> - Page 9: *"8.72 µg/g"*
> - Page 23: *"8.72 µg/g"*
>
> **Recommendation:** Confirm which AET value is correct and correct the outlier.

An analyst reads that, flips to page 7, and confirms or dismisses it in thirty
seconds. That is the bar.

Four properties separate the two:

1. **Grounded** — every claim quotes the document, with a page number. The analyst
   verifies by looking, not by re-reading.
2. **Specific** — actual values, actual table names, actual pages. "Elemental
   analysis is incomplete" is not a finding; it is a category label.
3. **Distinct** — five findings means five different problems. An earlier run
   produced five rewrites of "provide justification for the specification." That
   is one finding padded to five, and it teaches the analyst to skim.
4. **Not fabricated** — one invented finding costs more trust than nine good ones
   earn. If the system claims a leachables study is missing when the document has
   one, the analyst stops believing the other nine.

Everything below serves those four properties.

## The no-hardcoding rule, stated precisely

The LLM decides what is salient and what is a deficiency. Code is permitted
exactly one job: **verify that a quote the LLM emitted actually exists in the
document.** Substring-matching a model's own output against the text it was shown
is verification, not knowledge.

If a change requires code to know a limit, a required test, or a route→class
mapping, it is wrong. Every step below states which part is LLM and which is
verification.

---

## Why the output is bad today

### The findings cannot be specific, because detection never sees the document

`src/agents/extraction/group.py:106-127`:

```python
summaries: list[SectionSummary] = []
for group in groups:
    for section in group.sections:
        summaries.append(
            SectionSummary(
                section_id=section.section_id,
                summary=section.heading,        # ← the heading string. Not the content.
            )
        )
...
return IntermediateReport(
    document_name=document_name,
    document_type=document_type,
    sections=summaries,
    findings=[],                                # ← hardcoded empty
    consensus_notes=consensus_notes,
)
```

`section.text` and `section.tables` are read **nowhere** in this loop.
`key_values` (`src/schemas/documents.py:70`) has one repo-wide hit — its own
declaration. `ExtractionFinding` (`documents.py:60-64`) is defined and never
constructed.

`src/agents/detection/group.py:166` is the only channel into detection:
```python
report_text = json.dumps(intermediate_report.model_dump(), indent=2, default=str)
```

So the detection agents receive a list of heading strings and one prose blob. The
number `22.727` is not in there. Neither is `Table 16`. **The agents cannot report
what they were never shown.** A generic finding is the only thing they *can*
produce.

The extraction agents *do* read the content — `src/agents/extraction/agent.py:38-51`
passes `section.text[:4000]` and table rows into the prompt. They see `22.727`.
Then `group.py:106` discards it sixty lines later.

**What already works — do not rebuild it.** `ExtractedTable` (`documents.py:38-43`)
preserves `headers`, `rows: list[list[str]]`, and `page` verbatim. `pdf.py:26-55`
populates it correctly, including `page=page.number + 1`. `section_splitter.py`
sets `page_start`/`page_end`. The data is captured correctly and thrown away at
consolidation. There is no need for a new table extractor.

### Findings have nowhere to put evidence

`FINDING_EXTRACTOR` (`src/llm/prompts.py:88-108`) defines five keys: `category`,
`section_id`, `description`, `evidence`, `severity`. `FlawFinding`
(`src/schemas/flaws.py:61-68`) matches. No field for a quote. No field for a page.
No field for a value. Even if a number survived the firewall, there is nowhere to
report it.

### Silence and failure look identical

`src/agents/detection/group.py:69-86`:
```python
response = chat_completion(          # ← not structured_call
    ...
)
try:
    start = response.index("[")
    end = response.rindex("]") + 1
    raw_findings = json.loads(response[start:end])
except (ValueError, json.JSONDecodeError):
    return []                        # ← "clean document" and "parser died" are the same value
```

`grep -rn "structured_call" src/agents/detection/` returns zero hits. The
defense-in-depth stack in `src/llm/structured.py` guards only the correction loop.
When `rindex("]")` grabs a bracket from prose — *"see also [ICH Q3D(R2)]"* — the
slice spans JSON plus trailing text, `json.loads` throws, and the analyst is told
the document is clean.

### The wrong specialists get spawned

`src/agents/detection/classifier.py:53-62`:
```python
        if isinstance(selected, list) and all(isinstance(s, str) for s in selected):
            return selected                                # ← `[]` passes: all() is vacuously true
    except (ValueError, json.JSONDecodeError):
        pass
    return list(FLAW_TYPE_DEFINITIONS.keys())[:4]          # ← dict-insertion-order arbitrary
```

Dict order in `flaw_types.py:8-22` makes `[:4]` = Specification/CoA,
Method/Validation, Impurities, Stability. On an **extractables & leachables
report** that excludes Container/Closure (`:14`) and Elemental Impurities (`:21`)
— the only two categories that matter for the document. And an empty selection
passes validation, spawning zero specialists.

---

## Step 1 — Findings about real content, every claim quoted

**Branch:** `fix/extraction-handoff-fidelity`
**Why first:** every other improvement is downstream of this. Better prompts,
better models, better UI — none of it matters while detection reads a heading list.

### 1a. Evidence schemas — `src/schemas/documents.py`

Insert before `SectionSummary`:

```python
class Evidence(BaseModel):
    """A verbatim span from the source document. `quote` MUST appear in the section
    text or a table cell — this is verified in code, never trusted."""
    quote: str = Field(description="Exact text copied from the document. Do not paraphrase.")
    page: int = Field(default=0, description="Page number the quote appears on.")
    locator: str = Field(default="", description="Where it sits, e.g. 'Table 16' or 'Section 1.8'.")


class KeyValue(BaseModel):
    """A labeled quantity or acceptance criterion the model judged salient."""
    label: str = Field(description="What this value is, e.g. 'AET' or 'Assay lower limit'.")
    value: str = Field(description="The value as written, including units, e.g. '22.727 ug/g'.")
    evidence: Evidence
```

Replace `SectionSummary` (`documents.py:67-70`):

```python
# BEFORE
class SectionSummary(BaseModel):
    section_id: CTDSection
    summary: str
    key_values: dict[str, str] = Field(default_factory=dict)

# AFTER
class SectionSummary(BaseModel):
    section_id: CTDSection
    heading: str = ""
    summary: str = Field(default="", description="Prose summary of the section's actual content.")
    key_values: list[KeyValue] = Field(default_factory=list)
    page_start: int = 0
    page_end: int = 0
```

Safe — `key_values` has no reader. `s.summary` is read at `classifier.py:38` and
now receives real prose instead of a heading, which improves specialist selection
as a side effect.

Replace `ExtractionFinding` (`documents.py:60-64`):

```python
class ExtractionFinding(BaseModel):
    """A neutral observation from extraction. NOT a deficiency judgment — that is
    Layer 2's job (see EXTRACTION_AGENT, prompts.py:15)."""
    section_id: CTDSection
    finding: str = Field(description="What was observed. State facts, not judgments.")
    evidence: str = ""
    evidence_spans: list[Evidence] = Field(default_factory=list)
    agent_name: str = ""
```

### 1b. Anchoring — new `src/agents/extraction/anchor.py`

The only code that inspects document content. It answers exactly one question:
*does this quote exist in what the model was shown?* It never decides what matters.

```python
"""Deterministic verification that a model-emitted quote exists in the source.

This module makes no judgment about meaning. It answers 'does this string exist'
and nothing else. That boundary is what keeps domain knowledge out of the code.
"""
from __future__ import annotations

import re
import unicodedata

import structlog

from schemas.documents import ParsedSection

log = structlog.get_logger()

_WS = re.compile(r"\s+")

# Characters PDF extraction renders inconsistently. Folding them is a
# transcription-fidelity concern, not a domain rule.
_FOLD = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
    "μ": "µ",   # GREEK SMALL MU -> MICRO SIGN
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    for a, b in _FOLD.items():
        text = text.replace(a, b)
    return _WS.sub(" ", text).strip().casefold()


def _haystacks(section: ParsedSection) -> list[str]:
    out = [normalize(section.text)]
    for t in section.tables:
        out.append(normalize(" ".join(t.headers)))
        for row in t.rows:
            out.append(normalize(" ".join(row)))
    return out


def is_anchored(quote: str, sections: list[ParsedSection]) -> bool:
    q = normalize(quote)
    if len(q) < 3:
        return False
    return any(q in hay for section in sections for hay in _haystacks(section))


def filter_anchored(items: list, sections: list[ParsedSection], get_quote) -> tuple[list, int]:
    """Return (kept, dropped_count). Unanchored items are DROPPED, never repaired."""
    kept, dropped = [], 0
    for it in items:
        if is_anchored(get_quote(it), sections):
            kept.append(it)
        else:
            dropped += 1
            log.warning("anchor_rejected", quote=get_quote(it)[:120])
    return kept, dropped
```

**Why drop and not repair.** Repairing means code deciding what the model *meant*.
Dropping means code enforcing only "quote what you were shown." That is the line
between verification and knowledge. This is also the mechanism that makes property
4 — *not fabricated* — hold: a hallucinated quote does not exist in the document,
so it cannot pass, so the analyst never sees it.

### 1c. Structured extraction pass — new `src/agents/extraction/structured_pass.py`

The AutoGen conversation stays — it is good at cross-section consensus prose. A
separate structured pass re-reads the raw sections and tables. Re-reading raw
content beats parsing the agents' lossy prose restatement, and it is where a
schema can be enforced.

Cost: one `structured_call` per `ChunkGroup` (Combipatch ≈ 4-5 groups). Adds
roughly 60-120s to a 478s baseline.

```python
from __future__ import annotations

import structlog
from pydantic import BaseModel, Field

from agents.extraction.anchor import filter_anchored
from config import get_settings
from llm.structured import structured_call
from schemas.documents import ChunkGroup, ExtractionFinding, KeyValue, SectionSummary

log = structlog.get_logger()

STRUCTURED_EXTRACTOR = """You extract structured facts from a CMC document section.

For each section you are given, report:

1. summary — 2-4 sentences describing what this section actually contains. Not the
   heading restated. What tests, what data, what claims.

2. key_values — every labeled quantity, limit, acceptance criterion, or specification.
   Include the number AND its units exactly as written. Include values from tables.
   If a section states twenty numbers, report twenty.

3. observations — anything notable a reviewer would want to know: something applied
   to some items but not others, a value that appears different elsewhere, a table
   cell whose label does not match its row, a statement that is present or absent.
   State facts. Do NOT judge whether something is a deficiency — that is a later step.

EVIDENCE RULE — absolute:
Every key_value and every observation MUST carry a `quote` copied CHARACTER-FOR-CHARACTER
from the text you were given. Do not paraphrase. Do not clean up spacing. Do not fix what
looks like a typo — if a cell reads "Class 1 elements below PDE levels" you quote it
exactly, typo included, because the typo may be the point. Anything you cannot quote
verbatim is discarded automatically.

Report the `page` each quote came from, and a `locator` such as "Table 16" when the quote
came from a table."""


class SectionExtraction(BaseModel):
    section_heading: str = Field(description="Echo the section heading exactly as given.")
    summary: str
    key_values: list[KeyValue] = Field(default_factory=list)
    observations: list[ExtractionFinding] = Field(default_factory=list)


class GroupExtraction(BaseModel):
    """Object-rooted — Databricks strict json_schema requires an object at root."""
    sections: list[SectionExtraction] = Field(default_factory=list)


def _prompt_for_group(group: ChunkGroup) -> str:
    parts = []
    for section in group.sections:
        parts.append(f"## SECTION: {section.heading}")
        parts.append(f"(pages {section.page_start}-{section.page_end})")
        parts.append(section.text[:8000])
        for table in section.tables:
            parts.append(f"\n### TABLE: {table.title or '(untitled)'} [page {table.page}]")
            if table.headers:
                parts.append(" | ".join(table.headers))
            for row in table.rows:                      # all rows — NOT [:10]
                parts.append(" | ".join(row))
        parts.append("")
    return "\n".join(parts)


def extract_group(group: ChunkGroup) -> tuple[list[SectionSummary], list[ExtractionFinding]]:
    s = get_settings()
    result, failure = structured_call(
        messages=[
            {"role": "system", "content": STRUCTURED_EXTRACTOR},
            {"role": "user", "content": _prompt_for_group(group)},
        ],
        model_cls=GroupExtraction,
        model=s.resolved_llm_model,
        temperature=0.2,
        max_tokens=8000,
        repair_context="Structured extraction of CMC document sections.",
    )

    if result is None:
        log.error("structured_extraction_failed", group=group.group_id,
                  reason=failure.reason if failure else "unknown")
        return [], []

    by_heading = {sec.heading: sec for sec in group.sections}
    summaries: list[SectionSummary] = []
    findings: list[ExtractionFinding] = []

    for ext in result.sections:
        parsed = by_heading.get(ext.section_heading)
        if parsed is not None:
            scope = [parsed]
            section_id = parsed.section_id
            page_start, page_end = parsed.page_start, parsed.page_end
        elif group.sections:
            # Model echoed a heading we did not send. Anchor against the whole group
            # rather than discarding the content.
            scope = group.sections
            section_id = group.sections[0].section_id
            page_start = page_end = 0
        else:
            continue

        kvs, kv_dropped = filter_anchored(ext.key_values, scope, lambda k: k.evidence.quote)
        obs, obs_dropped = filter_anchored(
            [o for o in ext.observations if o.evidence_spans],
            scope,
            lambda o: o.evidence_spans[0].quote,
        )
        if kv_dropped or obs_dropped:
            log.warning("anchor_drops", section=ext.section_heading,
                        key_values=kv_dropped, observations=obs_dropped)

        summaries.append(
            SectionSummary(
                section_id=section_id,
                heading=ext.section_heading,
                summary=ext.summary,
                key_values=kvs,
                page_start=page_start,
                page_end=page_end,
            )
        )
        for o in obs:
            o.section_id = section_id
            findings.append(o)

    return summaries, findings
```

`for row in table.rows` — the existing prompt builder truncates at `rows[:10]`
(`agent.py:48`). Table 16's later rows are invisible today. The structured pass
must not inherit that cap.

### 1d. Rewire consolidation — `src/agents/extraction/group.py:106-127`

```python
# BEFORE
    summaries: list[SectionSummary] = []
    for group in groups:
        for section in group.sections:
            summaries.append(
                SectionSummary(
                    section_id=section.section_id,
                    summary=section.heading,
                )
            )

    emit_sync(
        job_id, "extraction", "layer_complete", "",
        f"Extracted {len(summaries)} sections in {msg_count} messages",
    )

    return IntermediateReport(
        document_name=document_name,
        document_type=document_type,
        sections=summaries,
        findings=[],
        consensus_notes=consensus_notes,
    )

# AFTER
    summaries: list[SectionSummary] = []
    findings: list[ExtractionFinding] = []
    for group in groups:
        emit_sync(
            job_id, "extraction", "agent_message", f"Extractor_{group.group_id}",
            f"Structured extraction over {len(group.sections)} sections",
        )
        group_summaries, group_findings = extract_group(group)
        summaries.extend(group_summaries)
        findings.extend(group_findings)

    n_kv = sum(len(s.key_values) for s in summaries)
    emit_sync(
        job_id, "extraction", "layer_complete", "",
        f"Extracted {len(summaries)} sections, {n_kv} anchored values, "
        f"{len(findings)} observations in {msg_count} messages",
    )

    return IntermediateReport(
        document_name=document_name,
        document_type=document_type,
        sections=summaries,
        findings=findings,
        consensus_notes=consensus_notes,
    )
```

Imports:
```python
from agents.extraction.structured_pass import extract_group
from schemas.documents import ExtractionFinding
```

### 1e. Somewhere to put evidence — `src/schemas/flaws.py:61-68`

```python
class FlawFinding(BaseModel):
    category: FlawCategory
    section_id: CTDSection
    description: str
    evidence: str = ""
    evidence_spans: list[Evidence] = Field(
        default_factory=list,
        description="Verbatim quotes from the report showing this deficiency. Required.",
    )
    numeric_claims: list[KeyValue] = Field(
        default_factory=list,
        description="Specific values this finding concerns, when it concerns values.",
    )
    severity: Severity = Severity.MEDIUM
    corroborations: list[Corroboration] = Field(default_factory=list)
    similar_deficiencies: list[SimilarDeficiency] = Field(default_factory=list)
```

Import `Evidence`, `KeyValue` from `schemas.documents`.

The same fields go on `Correction` (`src/schemas/corrections.py:16-27`) so the
quote survives to the analyst's screen:

```python
class Correction(BaseModel):
    flaw_category: FlawCategory
    suggestion: str = Field(...)      # existing
    explanation: str = Field(...)     # existing
    priority: Severity = Severity.MEDIUM
    references: list[str] = Field(default_factory=list)
    evidence_spans: list[Evidence] = Field(
        default_factory=list,
        description="The quotes from the document that show this problem. Carried from the finding.",
    )
```

### 1f. Detection uses the structured stack — `src/agents/detection/group.py:61-119`

Replace the body of `_extract_structured_findings`:

```python
class FlawFindingList(BaseModel):
    """Object-rooted wrapper for strict json_schema."""
    findings: list[FlawFinding] = Field(default_factory=list)


def _extract_structured_findings(
    consensus_summary: str,
    document_section: CTDSection,
    report: IntermediateReport,
) -> list[FlawFinding] | None:
    """Returns None on parse failure, [] when the discussion confirmed nothing."""
    s = get_settings()
    categories_str = ", ".join(c.value for c in FlawCategory)
    report_text = json.dumps(report.model_dump(), indent=2, default=str)

    result, failure = structured_call(
        messages=[
            {"role": "system", "content": FINDING_EXTRACTOR.format(categories=categories_str)},
            {
                "role": "user",
                "content": (
                    f"## Consensus discussion\n\n{consensus_summary}\n\n"
                    f"## Extraction report (the only source you may quote)\n\n{report_text}"
                ),
            },
        ],
        model_cls=FlawFindingList,
        model=s.moderator_model,
        temperature=0.0,
        max_tokens=8000,
        repair_context="Extracting confirmed regulatory findings from a consensus discussion.",
    )

    if result is None:
        log.error("finding_extraction_failed", reason=failure.reason if failure else "unknown")
        return None

    haystack = normalize(report_text)
    verified: list[FlawFinding] = []
    for f in result.findings:
        spans = [e for e in f.evidence_spans if normalize(e.quote) in haystack]
        if not spans:
            log.warning("finding_dropped_unanchored", description=f.description[:120])
            continue
        f.evidence_spans = spans
        if f.section_id == CTDSection.UNKNOWN:
            f.section_id = document_section
        verified.append(f)

    log.info("findings_verified", kept=len(verified),
             dropped=len(result.findings) - len(verified))
    return verified
```

Imports: `from agents.extraction.anchor import normalize`,
`from llm.structured import structured_call`,
`from schemas.documents import IntermediateReport`.

Pydantic coerces enums natively, so the manual `try/except ValueError` blocks at
`group.py:93-109` go away. Keep the `UNKNOWN → document_section` default — that is
provenance, not a domain rule.

Update the caller at `group.py:207` to pass the report and handle `None`:
```python
findings = _extract_structured_findings(consensus_summary, document_section, intermediate_report)

if findings is None:
    emit_sync(job_id, "detection", "error", "", "Finding extraction failed to parse")
    return FlawReport(
        flaws_found=False,
        findings=[],
        analysis_status=AnalysisStatus.PARSE_FAILED,   # from fix/analysis-status-and-verdicts
        consensus_summary=consensus_summary,
        agents_participated=[a.name for a, _ in agents],
        consensus_rounds=message_count,
    )
```

### 1g. The prompt contract — `src/llm/prompts.py:88-108`

```python
FINDING_EXTRACTOR = """You are a structured data extractor. Given a consensus discussion about
regulatory deficiencies in a CMC submission, extract each confirmed finding.

For each confirmed finding (NOT dropped ones):
- category: closest match from this list: {categories}. Use "general_cmc" only if nothing fits.
- section_id: the CTD section code (e.g. "3.2.S.4.1"). Use "unknown" if unclear.
- description: one sentence stating the specific problem. Name the value, the table, or the
  section it concerns. "Elemental analysis is incomplete" is not a finding — it is a category.
  "Table 16 lists Class 3 elements but the result column reports on Class 1" is a finding.
- evidence: brief prose context.
- evidence_spans: REQUIRED. One or more quotes copied character-for-character from the
  extraction report, with page numbers. A finding with no quote that appears in the report is
  discarded. Quote exactly — including any typo, since the typo may be the deficiency.
- numeric_claims: when the finding concerns specific values, list them with their labels and
  the quote each came from.
- severity: "high", "medium", or "low".

Each finding must be a DIFFERENT problem. Do not restate one problem several ways.

If no findings were confirmed, return {{"findings": []}}. An empty list is a valid and useful
answer — do not invent findings to fill space."""
```

The last two paragraphs carry properties 3 (distinct) and the clean-document case.

### Tests — `tests/unit/test_anchor.py`

```python
from schemas.documents import CTDSection, ExtractedTable, ParsedSection
from agents.extraction.anchor import is_anchored


def _section() -> ParsedSection:
    return ParsedSection(
        section_id=CTDSection.S_4_1_SPECIFICATION,
        heading="1.8 Related Compounds",
        text="The AET was calculated as 22.727 µg/g based on the SCT.",
        tables=[
            ExtractedTable(
                title="Table 16",
                headers=["Class", "Elements", "Result"],
                rows=[["Class 3", "Li, Sb, Cu", "Class 1 elements below PDE levels"]],
                page=17,
            )
        ],
        page_start=7,
        page_end=7,
    )


def test_anchors_quote_from_body_text():
    assert is_anchored("22.727 µg/g", [_section()])


def test_anchors_quote_from_table_cell():
    assert is_anchored("Class 1 elements below PDE levels", [_section()])


def test_rejects_fabricated_quote():
    assert not is_anchored("leachables and extractables study", [_section()])


def test_normalizes_mu_variants():
    assert is_anchored("22.727 μg/g", [_section()])   # GREEK MU vs MICRO SIGN


def test_normalizes_whitespace():
    assert is_anchored("AET  was   calculated", [_section()])


def test_rejects_trivially_short_quote():
    assert not is_anchored("a", [_section()])
```

### How you check Step 1 worked

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_anchor.py -v
```

Then upload the Combipatch PDF and read the output. You are looking for findings
that name specific values, tables, and pages, each with a quote you can check
against the document in seconds. If they are still generic, the step failed.

**Risk:** the 8B may not hold the verbatim-quote discipline. The anchor drops its
output rather than passing fabrications through, so the failure mode is *fewer
findings*, not *wrong findings*. If the logs show heavy `anchor_rejected`, route
the structured pass to `s.moderator_model` (70B) — a one-line change.

---

## Step 2 — Stop losing findings to plumbing

Small, independent, ships alongside Step 1.

### 2a. Merge the two branches already tested and waiting

```bash
git merge --no-ff fix/json-extractor-consolidation    # 9c3ea6a — merge first, 2b edits the same lines
git merge --no-ff fix/analysis-status-and-verdicts    # 27bb4e5
```

`fix/json-extractor-consolidation` fixes the prose-bracket slice that silently
returns `[]`. `fix/analysis-status-and-verdicts` makes "the document is clean"
distinguishable from "the parser died" — the analyst needs to know which one they
are looking at.

### 2b. The right specialists — `src/agents/detection/classifier.py:33-62`

```python
# BEFORE
    try:
        start = response.index("[")
        end = response.rindex("]") + 1
        selected = json.loads(response[start:end])
        if isinstance(selected, list) and all(isinstance(s, str) for s in selected):
            return selected
    except (ValueError, json.JSONDecodeError):
        pass
    return list(FLAW_TYPE_DEFINITIONS.keys())[:4]

# AFTER
    result, failure = structured_call(
        messages=[
            {"role": "system", "content": FLAW_TYPE_SELECTOR.format(flaw_catalog=format_flaw_catalog())},
            {"role": "user", "content": report_summary},
        ],
        model_cls=FlawTypeSelection,
        model=s.moderator_model,
        temperature=0.2,
        max_tokens=600,
    )
    if result is not None and result.flaw_types:
        return result.flaw_types

    # The model could not tell us what to check. Declining to guess means checking
    # everything, not picking four by dict order.
    log.warning("flaw_type_selection_failed_using_full_catalog",
                reason=failure.reason if failure else "empty selection")
    return list(FLAW_TYPE_DEFINITIONS.keys())
```

```python
class FlawTypeSelection(BaseModel):
    flaw_types: list[str] = Field(default_factory=list)
```

Two bugs closed: the arbitrary `[:4]`, and `[]` passing `all()` vacuously
(`and result.flaw_types` rejects it). This **removes** an accidental hard-coded
rule — no document-type→category mapping is introduced, and the LLM still selects
freely.

**Check the Combipatch event log first.** `detection/group.py:132-135` emits
`LLM selected {n} flaw categories: {...}`. If it names exactly Specification/CoA,
Method/Validation, Impurities, Stability, this fallback fired live on an E&L
report and this is urgent rather than insurance.

### 2c. Vocabulary for absence — `src/agents/detection/flaw_types.py`

The module docstring already says *"this catalog provides the vocabulary, not the
routing logic."* All 13 entries describe defects in content that is *present*.
Nothing gives an agent the words to report that something expected is missing.

Append:
```python
    "Commitments/Undertakings": "Absent or vague forward commitments — no undertaking to continue monitoring or report new results through the proposed period, no post-approval commitment where the data package is time-limited",
    "Justification Gaps": "A test, control, or study applied to some components, batches, or timepoints but omitted for others, with no stated justification for the omission",
    "Cross-Reference Consistency": "The same quantity, limit, or claim stated differently in different sections, tables, or annexures; a conclusion that does not account for a caveat stated elsewhere",
```

Matching `FlawCategory` values (`src/schemas/flaws.py:10-39`):
```python
    MISSING_COMMITMENT = "missing_commitment"
    JUSTIFICATION_GAP = "justification_gap"
    CROSS_REFERENCE_INCONSISTENCY = "cross_reference_inconsistency"
```

**Not hardcoding:** these are one-line natural-language descriptions the LLM reads
and interprets. No rule says "E&L reports require a shelf-life commitment." The
specialist decides whether an omission matters in context.

`FLAW_DETECTION_AGENT` (`prompts.py:32-54`) is framed entirely around present
content. Add after the "Compare the extracted information against" block:

```
Deficiencies are not only defects in what is written. If your domain concerns what a
document should commit to, justify, or apply consistently, then a thing that is absent
may itself be the finding. When you report an absence, quote the passage where it should
have appeared, or the passage that creates the expectation — an absence claim still
requires evidence.
```

This keeps absence claims inside the evidence contract: you cannot quote what is
not there, so you quote what creates the expectation.

---

## Step 3 — The analyst can read it

Findings can be perfect and still be useless on screen. Today the frontend shows
a suggestion and an explanation. After Step 1 there is a quote and a page number
to show, and they are the whole point — they are what lets the analyst verify in
thirty seconds instead of thirty minutes.

`feat/frontend-evidence-display`:
- Under each finding, render every `evidence_spans` entry as a blockquote with its
  page number.
- Show `analysis_status` plainly. A clean document should read *"Analysis complete
  — no deficiencies identified"*, not an ambiguous empty list. A parse failure
  should say so.
- Group findings by severity. High first.

Nothing clever. The analyst needs to see the quote, the page, and the
recommendation, in that order.

---

## Later, once the output is good

Not now. Listed so they are not forgotten:

- **Guidance retrieval** (`feat/guidance-corpus-and-framework-retrieval`) — RAG over
  ICH/USP/PQRI *source text*, so specialists reason from the guidance rather than
  from the 8B's priors. The existing hook is `_build_context_for_flaw_type`
  (`detection/group.py:48-58`, called at `:170`). The corpus is source text
  retrieved semantically — no `if route == "transdermal"` anywhere.
- **Model routing** — `detection/group.py:128` runs specialists on the 8B; only the
  moderator gets the 70B. Multi-hop reasoning on an 8B is the capability ceiling.
  Add `detection_specialist_model` to config and point it at the 70B, which is
  already deployed.
- **Evaluator sees findings** — `loop.py:70` passes only prose; the evaluator cannot
  tell that six findings produced one recommendation.
- **Deferred hardening** — `fix/faiss-globals-lock`, `fix/health-check-import`,
  `fix/section-page-metadata` (every section currently claims `page_start`=first,
  `page_end`=last — **this matters now**, since Step 1 makes page numbers analyst-
  facing; fix it inside Step 1 if the pages come out wrong),
  `refactor/dedupe-model-client`.
- **RC-3 latent bug** — `_extract_json_blob`'s `rfind("}")` chops a truncated array
  at the last complete element, `json_repair` closes it, Pydantic validates a
  shorter list with no error and no log (3 intended → 2 returned). Only fires past
  ~25 corrections. Separate ticket.

---

## Order

| # | Branch | Why |
|---|---|---|
| 1 | `fix/extraction-handoff-fidelity` | Findings can be about real content, every claim quoted. Nothing else matters until this lands. |
| 2a | merge `fix/json-extractor-consolidation`, `fix/analysis-status-and-verdicts` | Stop losing findings to a bracket slice. Distinguish clean from broken. |
| 2b | `fix/classifier-coverage-floor` | Right specialists get spawned. Independent — ship any time. |
| 2c | `feat/absence-vocabulary` | Agents get the words to report what is missing. |
| 3 | `feat/frontend-evidence-display` | The analyst sees the quote and the page. |

Steps 2b, 2c, and 3 are independent of Step 1 and of each other. Step 1 is the
one that decides whether any of it is worth doing.

## How we know it is working

Your senior uploads a PDF and reads the output. If the findings name real values
with quotes they can check, and the recommendations tell them what to do, it
works. If they are generic, it does not.

That is the whole test. There is no metric to compute and no score to report.

## What this will not fix

- **Reasoning that needs more model than an 8B has.** Chains like *transdermal ⇒
  cutaneous route ⇒ only Class 1 and 2A required ⇒ Class 3 was tested ⇒ the risk
  assessment was not route-scoped* are four hops. The 8B will not reliably chain
  them, with or without better inputs. Guidance retrieval and 70B routing are the
  levers, and both are "later."
- **Scanned pages.** `pdf.py:66` — `page.get_text("text")` returns `""` for
  image-only pages and nothing notices. Those pages are invisible and the analyst
  is not told. Worth surfacing in Step 3 as a warning.
- **A structural contradiction in the prompts.** `prompts.py:64` says *"A finding
  needs at least one corroboration from another agent to survive"*; `prompts.py:54`
  says *"Only report and discuss findings in YOUR specific domain."* Line 64 demands
  corroboration from agents line 54 forbids from speaking. The gate is prompt-only,
  never enforced in code, and self-neutralizes at `prompts.py:65,69` (DROPPED needs
  a *successful* challenge; silence is abstention). So an uncorroborated,
  unchallenged finding has no defined disposition. Leave it until Step 1 lands and
  we can see real findings — then decide whether it is costing us.

---

## Hard rules

- No hard-coded regulatory rules, checklists, or thresholds. The LLM decides what
  is a deficiency; code only verifies the LLM's own quotes exist in the source.
- Zero findings stays a legitimate outcome. The system must never invent a finding
  to avoid an empty result.
- Determinism is verification-only. `anchor.py` is the only module that inspects
  content, and it answers only "does this string exist."
- No AI-tool metadata in commits or files.
- Never touch the `amn_dev_databricks` catalog. Use `defpredict` only.
