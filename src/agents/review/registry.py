"""Review-loop tool registry: schemas, validation, dispatch, and rejection rendering.

# PITFALL 6 -- PRE-REGISTERED FALLBACK (must be written into 03-GO-NOGO-PREREGISTRATION.md).
# If the `optional_param_near_miss` counter DOMINATES the malformed-arg rate, the remedy is a
# SCHEMA SHAPE change, not a model verdict: split the multi-mode tools into single-mode schemas
# with all-required params over the SAME Python functions --
#   list_requirements(family) / read_rule(citation) / continue_rule(handle)
#   get_section_by_heading(doc_id, heading) / get_section_by_span(doc_id, start, end) /
#   continue_section(handle)
# That takes the tool count from 7 to 11, well under the documented 32. Declaring it in the
# pre-registration keeps it from being a mid-set configuration change, which D-GO2(ii) would
# void the entire run set for.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from agents.review.budget import BudgetLedger
from agents.review.spanref import parse_span_ref
from ingest.corpus import CorpusIndex
from ingest.manifest import CoverageManifest
from llm.structured import build_tool_schema, parse_structured
from rulebook.store import DEFAULT_RULEBOOK_CACHE_DIR
from schemas.faults import ComplianceVerdict
from tools.emit_finding import emit_finding
from tools.errors import ToolRejected
from tools.follow_reference import follow_reference
from tools.get_section import get_section
from tools.ledger import RetrievalLedger
from tools.open_doc import open_doc
from tools.read_guideline import read_guideline
from tools.search_corpus import search_corpus


SPAN_EXAMPLE = "[mvr1381:14820:14975]"

SEARCH_CORPUS_DESCRIPTION = (
    "Search the submission corpus for relevant passages. Results include snippets with "
    "visible span IDs; cite only IDs returned by tools."
)
OPEN_DOC_DESCRIPTION = (
    "Open one document's metadata and outline without reading full text. Use it to choose "
    "a section for get_section."
)
GET_SECTION_DESCRIPTION = (
    "Read a bounded submission section by heading, explicit span, or handle. The returned "
    "text contains citable span IDs."
)
READ_GUIDELINE_DESCRIPTION = (
    "Read FDA/ICH requirements. Omit citation to enumerate applicable requirements; pass "
    "citation, rule_doc_id, or handle to fetch rule text with citable span IDs."
)
FOLLOW_REFERENCE_DESCRIPTION = (
    "Resolve a same-document reference. If the result says "
    "cross_document_resolution_pending_phase_4, that reference cannot be resolved in this "
    "system yet -- do not retry it; continue with other evidence."
)
EMIT_FINDING_DESCRIPTION = (
    "Emit one grounded compliance finding. Use only span IDs already returned by get_section, "
    "search_corpus, open_doc, or read_guideline; never provide free-text evidence."
)
RUN_ORACLES_DESCRIPTION = (
    "Run deterministic S9/S10/P10 seed checks for one document. Leads are not citable until "
    "you re-open evidence with get_section, open_doc, or read_guideline."
)


class _ArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchCorpusArgs(_ArgsModel):
    query: str = Field(description="Search text, requirement, batch number, table label, or deficiency clue.")
    top_k: int = Field(default=10, description="Maximum number of retrieved corpus snippets to return.")


class OpenDocArgs(_ArgsModel):
    doc_id: str = Field(description="Document ID returned by search_corpus or the corpus manifest.")


class GetSectionArgs(_ArgsModel):
    doc_id: str = Field(description="Submission document ID to read.")
    heading: str | None = Field(default=None, description="Outline heading from open_doc, when reading by heading.")
    start: int | None = Field(default=None, description="Start offset when reading an explicit corpus range.")
    end: int | None = Field(default=None, description="End offset when reading an explicit corpus range.")
    handle: str | None = Field(default=None, description="Handle returned by a range_too_large rejection.")


class ReadGuidelineArgs(_ArgsModel):
    citation: str | None = Field(default=None, description="Omit to enumerate; pass citation or rule_doc_id to fetch rule text.")
    family: str | None = Field(default=None, description="Optional requirement-family filter for enumerate mode.")
    handle: str | None = Field(default=None, description="Handle returned by an oversized read_guideline response.")


class FollowReferenceArgs(_ArgsModel):
    doc_id: str = Field(description="Submission document ID containing the reference text.")
    ref_text: str = Field(description="The visible reference text or heading to resolve.")


class EmitFindingArgs(_ArgsModel):
    submission_span_id: str = Field(description="A submission span-ID exactly as shown, e.g. [mvr1381:14820:14975].")
    rule_span_id: str = Field(description="A rule span-ID exactly as shown by read_guideline, e.g. [ecfr-211:0:120].")
    verdict: ComplianceVerdict = Field(description="Compliance verdict: violation, gap, or ambiguous.")
    title: str = Field(description="Specific one-line deficiency title. Required to avoid dedup-key collapse.")
    detail: str = Field(description="Why the cited submission passage violates or fails the cited rule.")
    rule_citation: str = Field(default="", description="Human-readable rule citation or rule_doc_id.")
    requirement_id: str = Field(default="", description="Requirement index ID, when one was enumerated.")


class RunOraclesArgs(_ArgsModel):
    doc_id: str = Field(description="Submission document ID to run deterministic seed checks against.")


@dataclass(frozen=True)
class _ToolSpec:
    name: str
    model: type[_ArgsModel]
    description: str


@dataclass
class DispatchResult:
    """One model tool call outcome, ready to append as a tool message."""

    result: str
    turn_consumed: bool
    repair_layer: Literal["none", "pre", "post"]
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    breaker_key: tuple[str, str] = ("", "")
    raw_result: object | None = None


def render_rejection(r: ToolRejected) -> str:
    """D-LOOP5: rejections invisible to the model make the emit gate a wall, not a teacher."""
    parts = [f'REJECTED[{r.reason_code}] {r.reason}']
    if r.hint:
        parts.append(f'HINT: {r.hint}')
    if r.preview:
        parts.append(r.preview)
    if r.handle:
        parts.append(f'handle={r.handle}')
    return "\n".join(parts)


def _json_default(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[attr-defined]
    if hasattr(value, "value"):
        return value.value  # type: ignore[attr-defined]
    return str(value)


def _render_result(value: object) -> str:
    if isinstance(value, ToolRejected):
        return render_rejection(value)
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()  # type: ignore[attr-defined]
    return json.dumps(value, sort_keys=True, default=_json_default)


def _direct_validate(raw_args: str, model_cls: type[_ArgsModel]) -> bool:
    try:
        model_cls.model_validate_json(raw_args)
    except Exception:
        return False
    return True


@dataclass
class ToolRegistry:
    """D-LOOP3: shown schemas are derived from the same pydantic models that validate replies.

    Constructor-injected, one instance per run (Security Domain V3), holding the corpus,
    manifest and ledgers the tools are called with.
    """

    corpus: CorpusIndex
    manifest: CoverageManifest
    ledger: RetrievalLedger
    budget: BudgetLedger | None = None
    rulebook_cache_dir: str = DEFAULT_RULEBOOK_CACHE_DIR
    optional_param_near_miss: int = 0

    _optional_shapes: dict[tuple[str, str], set[frozenset[str]]] = field(default_factory=dict, init=False, repr=False)

    TOOL_SPECS: ClassVar[tuple[_ToolSpec, ...]] = (
        _ToolSpec("search_corpus", SearchCorpusArgs, SEARCH_CORPUS_DESCRIPTION),
        _ToolSpec("open_doc", OpenDocArgs, OPEN_DOC_DESCRIPTION),
        _ToolSpec("get_section", GetSectionArgs, GET_SECTION_DESCRIPTION),
        _ToolSpec("read_guideline", ReadGuidelineArgs, READ_GUIDELINE_DESCRIPTION),
        _ToolSpec("follow_reference", FollowReferenceArgs, FOLLOW_REFERENCE_DESCRIPTION),
        _ToolSpec("emit_finding", EmitFindingArgs, EMIT_FINDING_DESCRIPTION),
        _ToolSpec("run_oracles", RunOraclesArgs, RUN_ORACLES_DESCRIPTION),
    )
    OPTIONAL_FIELDS: ClassVar[dict[str, set[str]]] = {
        "get_section": {"heading", "start", "end", "handle"},
        "read_guideline": {"citation", "family", "handle"},
    }

    def schemas(self) -> list[dict]:
        """Return the seven tool schemas in a fixed order."""
        return [
            build_tool_schema(spec.model, name=spec.name, description=spec.description)
            for spec in self.TOOL_SPECS
        ]

    def dispatch(self, name: str, raw_args: str) -> DispatchResult:
        """D-LOOP5 corollary + D-TEL4: split pre-dispatch repair from post-repair failure."""
        spec = self._spec_for(name)
        if spec is None:
            rejected = ToolRejected(
                tool=name,
                reason_code="not_found",
                reason=f'unknown tool {name!r}',
                hint="use one of: search_corpus, open_doc, get_section, read_guideline, follow_reference, emit_finding, run_oracles",
            )
            return self._rejected(name, {}, rejected, "post")

        raw_text = raw_args if isinstance(raw_args, str) else str(raw_args)
        direct_ok = _direct_validate(raw_text, spec.model)
        parsed, error = parse_structured(raw_text, spec.model)
        if parsed is None:
            rejected = ToolRejected(
                tool=name,
                reason_code="post_repair_malformed",
                reason=error or "tool arguments could not be parsed or validated",
                hint="send a JSON object matching this tool's schema exactly",
            )
            return self._rejected(name, {}, rejected, "post")

        repair_layer: Literal["none", "pre"] = "none" if direct_ok else "pre"
        args = parsed.model_dump(mode="json")
        self._record_optional_shape(name, args)
        if self.budget is not None:
            self.budget.record_tool_call(name, args)

        raw_result = self._call_tool(name, parsed)
        if isinstance(raw_result, ToolRejected):
            return self._rejected(name, args, raw_result, repair_layer)
        if self.budget is not None:
            self.budget.record_tool_success()
        return DispatchResult(
            result=_render_result(raw_result),
            turn_consumed=True,
            repair_layer=repair_layer,
            tool=name,
            args=args,
            breaker_key=(name, json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)),
            raw_result=raw_result,
        )

    def optional_param_near_miss_count(self) -> int:
        return self.optional_param_near_miss

    def _spec_for(self, name: str) -> _ToolSpec | None:
        return next((spec for spec in self.TOOL_SPECS if spec.name == name), None)

    def _record_optional_shape(self, name: str, args: dict[str, Any]) -> None:
        optional = self.OPTIONAL_FIELDS.get(name)
        if not optional:
            return
        required_args = {k: v for k, v in args.items() if k not in optional}
        required_key = json.dumps(required_args, sort_keys=True, separators=(",", ":"), default=str)
        present = frozenset(k for k in optional if args.get(k) is not None)
        key = (name, required_key)
        previous = self._optional_shapes.setdefault(key, set())
        if any(present != seen and present.symmetric_difference(seen) for seen in previous):
            self.optional_param_near_miss += 1
        previous.add(present)

    def _rejected(
        self,
        name: str,
        args: dict[str, Any],
        rejected: ToolRejected,
        repair_layer: Literal["none", "pre", "post"],
    ) -> DispatchResult:
        if self.budget is not None:
            self.budget.record_rejection(rejected.reason_code, rejected.half)
        return DispatchResult(
            result=render_rejection(rejected),
            turn_consumed=True,
            repair_layer=repair_layer,
            tool=name,
            args=args,
            breaker_key=(name, json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)),
            raw_result=rejected,
        )

    def _call_tool(self, name: str, parsed: _ArgsModel) -> object:
        if isinstance(parsed, SearchCorpusArgs):
            return search_corpus(self.corpus, parsed.query, self.ledger, top_k=parsed.top_k)
        if isinstance(parsed, OpenDocArgs):
            return open_doc(self.corpus, parsed.doc_id, self.ledger)
        if isinstance(parsed, GetSectionArgs):
            return get_section(
                self.corpus,
                parsed.doc_id,
                self.ledger,
                start=parsed.start,
                end=parsed.end,
                heading=parsed.heading,
                handle=parsed.handle,
            )
        if isinstance(parsed, ReadGuidelineArgs):
            return read_guideline(
                self.manifest,
                self.ledger,
                citation=parsed.citation,
                family=parsed.family,
                handle=parsed.handle,
            )
        if isinstance(parsed, FollowReferenceArgs):
            return follow_reference(self.corpus, parsed.doc_id, parsed.ref_text, self.ledger)
        if isinstance(parsed, RunOraclesArgs):
            from agents.review.oracles_tool import run_oracles_tool

            return run_oracles_tool(self.corpus, parsed.doc_id, self.ledger)
        if isinstance(parsed, EmitFindingArgs):
            submission_span = parse_span_ref(
                parsed.submission_span_id,
                self.corpus,
                self.rulebook_cache_dir,
                expect="submission",
            )
            if isinstance(submission_span, ToolRejected):
                return submission_span
            rule_span = parse_span_ref(
                parsed.rule_span_id,
                self.corpus,
                self.rulebook_cache_dir,
                expect="rule",
            )
            if isinstance(rule_span, ToolRejected):
                return rule_span
            return emit_finding(
                self.corpus,
                submission_span,
                rule_span,
                self.ledger,
                verdict=parsed.verdict.value,
                requirement_id=parsed.requirement_id,
                rule_citation=parsed.rule_citation,
                title=parsed.title,
                detail=parsed.detail,
                rulebook_cache_dir=self.rulebook_cache_dir,
            )
        return ToolRejected(
            tool=name,
            reason_code="not_found",
            reason=f'tool {name!r} is not dispatchable',
            hint="use a registered review tool",
        )


__all__ = [
    "DispatchResult",
    "EmitFindingArgs",
    "FollowReferenceArgs",
    "GetSectionArgs",
    "OpenDocArgs",
    "ReadGuidelineArgs",
    "RunOraclesArgs",
    "SearchCorpusArgs",
    "ToolRegistry",
    "render_rejection",
]
