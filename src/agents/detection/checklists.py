"""Stage 2 — checklist / absence / coverage oracles.

Expected-set (per document type) minus present-set (searched in the structured doc) =
missing. This turns absence into a verifiable search rather than something an LLM has to
"notice". Covers:
  * analytical-method-validation parameters (ICH Q2)
  * E&L reports: USP <88> component coverage, and a leachable-monitoring commitment
Add more keyed by document type.
"""
from __future__ import annotations

import re

from schemas.documents import CTDSection
from schemas.faults import EvidenceClass, Fault, Tier
from schemas.flaws import FlawCategory, Severity

# --- analytical method validation ------------------------------------------------
_VALIDATION_REQUIRED: dict[str, list[str]] = {
    "specificity": ["specificity"],
    "linearity": ["linearity"],
    "limit of detection (LOD)": ["limit of detection", "lod"],
    "limit of quantitation (LOQ)": ["limit of quantitation", "loq"],
    "precision": ["precision", "repeatability"],
    "accuracy / recovery": ["accuracy", "recovery"],
    "robustness / ruggedness": ["robustness", "ruggedness"],
    "system suitability": ["system suitability"],
    "solution stability": ["solution stability", "stability of standard", "stability of sample", "stability of analytical"],
}

# DETECT-03 / S10: reference-standard qualification. Built in Phase 3 -- grep for
# "reference standard" across src/ returned NOTHING before this (RESEARCH.md D6).
# ICH Q6A and 21 CFR 211.194 require the identity, source, lot/batch, purity/assigned
# potency and expiry/re-test date of the reference standard used, plus qualification basis.
_REFERENCE_STANDARD_REQUIRED: dict[str, list[str]] = {
    "reference standard": ["reference standard", "reference material", "reference substance"],
    "lot number": ["lot number", "batch number"],
    "purity": ["purity", "assigned potency"],
    "expiry": ["expiry", "re-test date", "retest date"],
    "qualification": ["qualification", "certificate of analysis", "coa"],
}

# These CTDSection values equal registry family ids (D-05, ingest.registry is the single
# source of truth for the CTD-family vocabulary). Kept as enum members here so membership
# resolution is unchanged; do NOT renumber the enum or these ids drift from the registry.
_VALIDATION_SECTIONS = {
    CTDSection.S_4_3_VALIDATION,
    CTDSection.P_4_3_VALIDATION,
    CTDSection.S_4_2_ANALYTICAL_PROCEDURES,
    CTDSection.P_4_2_ANALYTICAL_PROCEDURES,
}

# --- E&L reports -----------------------------------------------------------------
_USP88_RE = re.compile(r"<\s*88\s*>")
_CCS_COMPONENTS = ["backing film", "release liner", "pouch"]
_COMMITMENT_RE = re.compile(
    r"commit|continue\s+to\s+monitor|ongoing\s+monitor|monitor[a-z ]{0,30}shelf\s*life"
    r"|monitor[a-z ]{0,30}through\s+the\s+proposed",
    re.I,
)

# DETECT-03 / P10: stability commitment. RESEARCH.md D6: the only analogue in the codebase was
# `leachable_commitment`, an E&L LEACHABLE-monitoring commitment gated on is_el_report -- not a
# general stability commitment. This is the general form. ICH Q1A(R2) requires a commitment to
# continue/complete long-term studies and to place production batches on stability.
_STABILITY_COMMITMENT_PATTERNS = (
    r"stability\s+commitment",
    r"commit(?:s|ment|ted)?\s+to\s+(?:place|continue|complete)\b[^.]{0,120}stability",
    r"long[- ]term\s+stability\s+stud(?:y|ies)\b[^.]{0,120}(?:continue|complete|commit)",
    r"first\s+(?:three|3)\s+production\s+batches\b[^.]{0,120}stability",
)
_STABILITY_COMMITMENT_RE = re.compile("|".join(_STABILITY_COMMITMENT_PATTERNS), re.I)
_STABILITY_DISCUSSION_RE = re.compile(
    r"stability\s+(?:data|study|studies|protocol|condition|results?|batch|batches)"
    r"|long[- ]term\s+stability|accelerated\s+stability",
    re.I,
)


def _reading_order_text(doc: dict) -> str:
    parts: list[str] = []
    for page in doc.get("pages", []):
        for block in page.get("blocks", []):
            if block.get("role") not in ("page_header", "page_footer"):
                parts.append(block.get("text") or "")
        for table in page.get("tables", []):
            if table.get("title"):
                parts.append(table["title"])
            if table.get("kind") == "key_value":
                for pair in table.get("pairs", []):
                    parts.append(f"{pair.get('label', '')} {pair.get('value', '')}")
            else:
                for row in table.get("rows") or []:
                    parts.append(" ".join(str(c or "") for c in row))
    return "\n".join(parts).lower()


def is_el_report(doc: dict) -> bool:
    head = _reading_order_text(doc)[:3000]
    return "extractable" in head and "leachable" in head


def _validation_checklist(doc: dict) -> list[Fault]:
    text = _reading_order_text(doc)
    faults: list[Fault] = []
    for element, keys in _VALIDATION_REQUIRED.items():
        if any(k in text for k in keys):
            continue
        faults.append(
            Fault(
                title=f"Validation parameter not addressed: {element}",
                detail=(
                    f"An analytical method validation report is expected to establish {element}; "
                    "no evidence of it was found in the document."
                ),
                category=FlawCategory.METHOD_NOT_VALIDATED,
                severity=Severity.MEDIUM,
                tier=Tier.CORROBORATED,
                evidence_class=EvidenceClass.CHECKLIST,
                confidence=0.6,
                evidence=f"No mention of {element} (searched for: {', '.join(keys)}).",
                source="checklist:validation",
            )
        )
    return faults


def reference_standard_checklist(doc: dict) -> list[Fault]:
    """DETECT-03 / S10: flag missing reference-standard qualification elements."""
    text = _reading_order_text(doc)
    faults: list[Fault] = []
    for element, keys in _REFERENCE_STANDARD_REQUIRED.items():
        if any(k in text for k in keys):
            continue
        faults.append(
            Fault(
                title=f"Reference standard element not addressed: {element}",
                detail=(
                    "Reference-standard use is expected to identify and qualify the material; "
                    f"no evidence of {element} was found in the document."
                ),
                category=FlawCategory.REFERENCE_STANDARD,
                severity=Severity.MEDIUM,
                tier=Tier.CORROBORATED,
                evidence_class=EvidenceClass.CHECKLIST,
                confidence=0.6,
                evidence=f"No mention of reference standard {element} (searched for: {', '.join(keys)}).",
                source="checklist:reference_standard",
            )
        )
    return faults


def stability_commitment(doc: dict) -> list[Fault]:
    """DETECT-03 / P10: flag stability data with no general stability commitment."""
    text = _reading_order_text(doc)
    if not _STABILITY_DISCUSSION_RE.search(text):
        return []
    if _STABILITY_COMMITMENT_RE.search(text):
        return []
    return [
        Fault(
            title="No commitment to continue or complete stability studies",
            detail=(
                "The document discusses stability data but includes no commitment to continue or "
                "complete long-term studies or place production batches on stability."
            ),
            category=FlawCategory.COMMITMENT_MISSING,
            severity=Severity.MEDIUM,
            tier=Tier.CORROBORATED,
            evidence_class=EvidenceClass.CHECKLIST,
            confidence=0.6,
            evidence=(
                "No stability commitment language found (searched for: "
                f"{', '.join(_STABILITY_COMMITMENT_PATTERNS)})."
            ),
            source="checklist:stability_commitment",
        )
    ]


def usp88_component_coverage(doc: dict) -> list[Fault]:
    """Flag a CCS component that got USP <88> while others did — read from the compendia
    table (authoritative), not the prose summary (which may over-claim).

    Same-title grid fragments are grouped and read as one logical table, so a component whose
    label sits on one page and whose <88> rows spill onto the next is still linked correctly.
    """
    groups: dict[str, dict] = {}
    for page in doc.get("pages", []):
        for table in page.get("tables", []):
            if table.get("kind") != "grid":
                continue
            title = re.sub(r"\s+", " ", (table.get("title") or "")).strip().lower()
            key = title or f"__page_{page.get('page_number', 0)}"
            g = groups.setdefault(key, {"rows": [], "page": page.get("page_number", 0), "title": table.get("title", "")})
            g["rows"].extend(table.get("rows") or [])

    faults: list[Fault] = []
    for g in groups.values():
        rows = g["rows"]
        blob = " ".join(str(c or "") for row in rows for c in row)
        if not _USP88_RE.search(blob):
            continue
        covered: dict[str, bool] = {}
        seen: dict[str, bool] = {}
        current: str | None = None
        for row in rows:
            row_text = " ".join(str(c or "") for c in row)
            low = row_text.lower()
            for comp in _CCS_COMPONENTS:
                if comp in low:
                    current = comp
                    seen[comp] = True
            if current and _USP88_RE.search(row_text):
                covered[current] = True
        have = [c for c in _CCS_COMPONENTS if seen.get(c) and covered.get(c)]
        missing = [c for c in _CCS_COMPONENTS if seen.get(c) and not covered.get(c)]
        if not (have and missing):
            continue
        for comp in missing:
            faults.append(
                Fault(
                    title=f"USP <88> not performed for {comp.title()}",
                    detail=(
                        f"USP <88> (biological reactivity, in vivo) is reported for "
                        f"{', '.join(x.title() for x in have)} but not for {comp.title()}. "
                        f"Provide the <88> data for {comp.title()} or a justification for its omission."
                    ),
                    category=FlawCategory.CONTAINER_CLOSURE_INADEQUATE,
                    severity=Severity.HIGH,
                    tier=Tier.CORROBORATED,
                    evidence_class=EvidenceClass.CHECKLIST,
                    confidence=0.7,
                    evidence=f"USP <88> present for {', '.join(have)}; absent for {comp}.",
                    page=g["page"],
                    table_ref=(g["title"] or "")[:80],
                    source="checklist:usp88_coverage",
                )
            )
    return faults


def leachable_commitment(doc: dict) -> list[Fault]:
    """Flag an E&L report that never commits to continued leachable monitoring."""
    if _COMMITMENT_RE.search(_reading_order_text(doc)):
        return []
    return [
        Fault(
            title="No commitment to continue leachable monitoring",
            detail=(
                "The report concludes leachable risk is low but includes no commitment to continue "
                "leachable monitoring through the proposed shelf life. Add a commitment to monitor and "
                "report any new or increasing leachables."
            ),
            category=FlawCategory.COMMITMENT_MISSING,
            severity=Severity.MEDIUM,
            tier=Tier.CORROBORATED,
            evidence_class=EvidenceClass.CHECKLIST,
            confidence=0.6,
            evidence="No 'commitment' / 'continue monitoring' / 'shelf life' language found in the report.",
            source="checklist:leachable_commitment",
        )
    ]


def run_checklists(doc: dict, ctd: CTDSection) -> list[Fault]:
    faults: list[Fault] = []
    if ctd in _VALIDATION_SECTIONS:
        faults.extend(_validation_checklist(doc))
    if is_el_report(doc):
        faults.extend(usp88_component_coverage(doc))
        faults.extend(leachable_commitment(doc))
    return faults


def run_seed_checks(doc: dict) -> list[Fault]:
    """DETECT-03 seed pass (S9 LOD/LOQ, S10 reference standards, P10 stability commitment).

    Invokable on demand regardless of the CTD/E&L gating that run_checklists applies. D-ORC1:
    the agent decides when to run the seed, so the gate belongs to the agent, not to a section
    guess. Per-check try/except like oracles.py:221 -- one bad check never sinks the battery.
    """
    faults: list[Fault] = []
    seed_checks = (
        _validation_checklist,
        reference_standard_checklist,
        stability_commitment,
    )
    for check in seed_checks:
        try:
            faults.extend(check(doc))
        except Exception:  # noqa: BLE001 - one bad check must not sink the seed battery
            continue
    return faults
