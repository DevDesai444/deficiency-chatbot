"""Deterministic seed-pass tool for the review loop.

D-ORC1: this module demotes deterministic checks from a primary finding source into a callable
seed pass. The return value contains leads to investigate, not `Fault` objects to report.

D-ORC2: this tool never issues citable ledger entries. The reviewer must re-open a lead with
`get_section` or `open_doc` before the grounding gate can accept it. That re-read cost is the
demotion: oracle output is evidence to investigate, not a finding to rubber-stamp.

Pitfall 9: absence evidence has no quoted missing text. An absence lead therefore names the
expected element, the scope searched, and the next calls that produce a real surrounding section
plus the requiring rule. The final finding cites that real re-opened surrounding section.
"""
from __future__ import annotations

from collections.abc import Callable

from agents.detection import checklists as checklist_module
from agents.detection import oracles as oracle_module
from ingest.corpus import CorpusIndex
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger


def _doc_from_cache(cache: dict) -> dict:
    """Rebuild the extract-style document shape deterministic checks consume."""
    text = cache.get("raw_serialized") or cache.get("canonical") or ""
    return {
        "pages": [
            {
                "page_number": 1,
                "blocks": [{"text": text, "role": "body", "reading_order": 0}],
                "tables": [],
            }
        ]
    }


def _heading_hint(corpus: CorpusIndex, doc_id: str) -> str:
    entry = next((d for d in corpus.manifest.documents if d.doc_id == doc_id), None)
    if entry is None or not entry.outline:
        return ""
    return entry.outline[0].label


def _scope_hint(corpus: CorpusIndex, doc_id: str) -> str:
    entry = next((d for d in corpus.manifest.documents if d.doc_id == doc_id), None)
    if entry is None:
        return f"doc_id {doc_id}"
    if entry.outline:
        labels = [o.label for o in entry.outline[:5] if o.label]
        if labels:
            return f"{entry.filename}: {', '.join(labels)}"
    return f"{entry.filename}: full cached reading-order text"


def _positive_lead(fault, corpus: CorpusIndex, doc_id: str) -> dict:
    heading = _heading_hint(corpus, doc_id)
    return {
        "kind": "positive",
        "check": fault.source.removeprefix("oracle:") or "deterministic_oracle",
        "claim": fault.title,
        "quoted_text": fault.evidence,
        "locate_with": "get_section",
        "heading_hint": heading,
        "next_call": (
            f"get_section(doc_id={doc_id!r}, heading={heading!r}) then cite the marker it returns"
            if heading
            else f"open_doc(doc_id={doc_id!r}) then get_section on the nearest relevant heading"
        ),
    }


def _absence_check(fault) -> str:
    if fault.source == "checklist:reference_standard":
        return "S10"
    if fault.source == "checklist:stability_commitment":
        return "P10"
    if "limit of detection" in fault.title.lower() or "limit of quantitation" in fault.title.lower():
        return "S9"
    return fault.source.removeprefix("checklist:") or "seed_check"


def _expected_element(fault) -> str:
    if ":" in fault.title:
        return fault.title.split(":", 1)[1].strip()
    if fault.source == "checklist:stability_commitment":
        return "stability commitment"
    return fault.title


def _rule_hint(check: str) -> str:
    return {
        "S9": "ICH Q2(R2)",
        "S10": "21 CFR 211.194",
        "P10": "ICH Q1A(R2)",
    }.get(check, "read_guideline enumerate")


def _absence_lead(fault, corpus: CorpusIndex, doc_id: str) -> dict:
    check = _absence_check(fault)
    expected = _expected_element(fault)
    return {
        "kind": "absence",
        "check": check,
        "expected_element": expected,
        "scope_searched": _scope_hint(corpus, doc_id),
        "requiring_rule_hint": _rule_hint(check),
        "next_call": (
            f"read_guideline(citation={_rule_hint(check)!r}) for the requiring rule, then "
            f"get_section(doc_id={doc_id!r}) on the section that should contain {expected!r} "
            "and cite that real surrounding section"
        ),
    }


def _run_check(name: str, check: Callable[[dict], list], doc: dict, errors: list[dict]) -> list:
    try:
        return check(doc)
    except Exception as exc:  # noqa: BLE001 - one bad check must not sink the battery
        errors.append({"check": name, "error": str(exc)[:200]})
        return []


def run_oracles_tool(
    corpus: CorpusIndex, doc_id: str, ledger: RetrievalLedger
) -> dict | ToolRejected:
    """The 7th tool: deterministic seeds, shaped like the other review tools.

    `ledger` is explicit for sibling-shape consistency and dedup-read parity, but this function
    only reads its presence; it does not make any lead citable. The reviewer must call
    `get_section`, `open_doc`, or `read_guideline` to turn leads into gate-acceptable evidence.
    """
    cache = corpus.cached_entry(doc_id)
    if cache is None:
        return ToolRejected(
            tool="run_oracles",
            reason_code="not_found",
            reason=f"doc_id {doc_id!r} has no cached substrate",
            half="",
            hint="call open_doc first",
        )

    _ = ledger
    doc = _doc_from_cache(cache)
    check_errors: list[dict] = []
    positive_faults = []
    for check in oracle_module.ORACLES:
        positive_faults.extend(_run_check(check.__name__, check, doc, check_errors))

    absence_faults = _run_check(
        "run_seed_checks", checklist_module.run_seed_checks, doc, check_errors
    )
    positive_leads = [_positive_lead(f, corpus, doc_id) for f in positive_faults]
    absence_leads = [_absence_lead(f, corpus, doc_id) for f in absence_faults]

    return {
        "doc_id": doc_id,
        "positive_leads": positive_leads,
        "absence_leads": absence_leads,
        "leads_surfaced": len(positive_leads) + len(absence_leads),
        "check_errors": check_errors,
    }
