"""Stage 4 — typed verification, evidence-class stamping, confidence tiering, dedup.

Reconciles findings from all stages. Oracle/checklist findings keep their authority.
Sub-agent findings get their evidence anchored against the document (verbatim → higher
confidence) and are tiered by whether real precedent backs them. Nothing is dropped here
except exact duplicates — suppression is reserved for oracle-disproof, which happens by an
oracle simply not emitting the fault. Recall lives in the ADVISORY tier.
"""
from __future__ import annotations

import re

import structlog

from schemas.faults import EvidenceClass, Fault, Tier
from schemas.flaws import Severity

log = structlog.get_logger()

# A model that concedes compliance in its own words has not found a deficiency. Prompt-level
# instructions to self-censor were measured as ineffective (the model wrote "This is not a finding."
# into the detail and shipped the finding anyway), so this is enforced in code and cannot be ignored.
# Deliberately limited to UNAMBIGUOUS self-negations: a real finding often quotes words like
# "compliant" or "within limit" while arguing the opposite, and must not be dropped for that.
_SELF_NEGATION_RE = re.compile(
    r"\bno deficienc(?:y|ies)\b"
    r"|\bnot a deficiency\b"
    r"|\bno findings?\b"                 # covers "No finding." and "not a finding"
    r"|\bnot a finding\b"
    r"|\bno violation\b"
    r"|\bis not a violation\b"
    r"|\bnot a contradiction\b"
    r"|\bno discrepanc(?:y|ies)\b"
    r"|\bno inconsistenc(?:y|ies)\b"
    r"|\bthis is correct\b"
    r"|\bintentional and correct\b"
    r"|\bis correctly reported\b"
    r"|→\s*compliant\b"
    r"|(?<!not )(?<!in)\bvalid\b\.",
    re.I,
)

# Softer concessions ("compliant", "which is met", "satisfies the criterion") appear inside genuine
# findings too — a real fault often notes every value passes and THEN shows the contradiction. So
# these only count when they sit at the very END of the text, where they are the verdict rather
# than a premise.
_TRAILING_CONCESSION_RE = re.compile(
    r"(?:\bcompliant\b"
    r"|\bwithin (?:the )?limits?\b"
    r"|\bwhich (?:is|are) met\b"
    r"|\bsatisfies the criterion\b"
    r"|\bmeets? the acceptance criteri\w+"
    r"|\bmeasure different things\b)"
    r"[\s.)\]—-]*$",
    re.I,
)


def _concedes_compliance(fault: Fault) -> bool:
    """True when the finding's own text says nothing is wrong.

    Measured need: a live run emitted 10 of 31 'faults' whose own title ended "compliant. No
    finding." Prompt instructions to self-suppress were ignored twice, so this is enforced here.
    """
    for text in (fault.title or "", fault.detail or ""):
        if _SELF_NEGATION_RE.search(text):
            return True
        if _TRAILING_CONCESSION_RE.search(text.strip()):
            return True
    return False


_AUTHORITY = {
    EvidenceClass.CODE_VERIFIED: 3,
    EvidenceClass.CHECKLIST: 2,
    EvidenceClass.QUOTE_ANCHORED: 1,
    EvidenceClass.MODEL_JUDGMENT: 0,
}
_TIER_ORDER = {Tier.VERIFIED: 0, Tier.CORROBORATED: 1, Tier.ADVISORY: 2}
_SEV_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


def _doc_corpus(doc: dict) -> str:
    """One space-stripped blob of every cell/pair/block, for verbatim anchoring."""
    parts: list[str] = []
    for page in doc.get("pages", []):
        for table in page.get("tables", []):
            if table.get("kind") == "key_value":
                parts.extend((p.get("value") or "") for p in table.get("pairs", []))
            else:
                for row in table.get("rows", []) or []:
                    parts.extend(str(c) for c in row)
        for block in page.get("blocks", []):
            parts.append(block.get("text") or "")
    return _norm(" ".join(parts))


def _anchored(evidence: str, corpus: str) -> bool:
    n = _norm(evidence)
    return len(n) >= 4 and n in corpus


def _dedup_key(f: Fault) -> tuple[str, str, str]:
    return (_norm(f.title)[:60], _norm(f.section), _norm(f.table_ref))


def verify_and_tier(faults: list[Fault], doc: dict) -> list[Fault]:
    corpus = _doc_corpus(doc)
    kept: dict[tuple[str, str, str], Fault] = {}

    dropped_self_negating = 0
    for f in faults:
        if f.evidence_class not in (EvidenceClass.CODE_VERIFIED, EvidenceClass.CHECKLIST):
            # A soft finding that concedes compliance in its own words is not a deficiency. Oracle
            # and checklist findings are exempt — they never narrate, and their authority stands.
            if _concedes_compliance(f):
                dropped_self_negating += 1
                continue
            # sub-agent finding: anchor + tier by precedent
            if f.evidence and _anchored(f.evidence, corpus):
                f.evidence_class = EvidenceClass.QUOTE_ANCHORED
            else:
                f.evidence_class = EvidenceClass.MODEL_JUDGMENT
            if f.precedents:
                f.tier = Tier.CORROBORATED
                f.confidence = 0.6 if f.evidence_class == EvidenceClass.QUOTE_ANCHORED else 0.5
            else:
                f.tier = Tier.ADVISORY
                f.novel = True
                f.confidence = 0.4 if f.evidence_class == EvidenceClass.QUOTE_ANCHORED else 0.3

        key = _dedup_key(f)
        existing = kept.get(key)
        if existing is None:
            kept[key] = f
        elif _AUTHORITY[f.evidence_class] > _AUTHORITY[existing.evidence_class]:
            f.precedents = f.precedents or existing.precedents
            kept[key] = f
        elif not existing.precedents and f.precedents:
            existing.precedents = f.precedents  # merge precedent onto the survivor

    if dropped_self_negating:
        log.info("dropped_self_negating_findings", count=dropped_self_negating)

    return sorted(
        kept.values(),
        key=lambda f: (_TIER_ORDER[f.tier], _SEV_ORDER[f.severity], -f.confidence),
    )
