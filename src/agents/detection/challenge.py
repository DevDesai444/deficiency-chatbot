"""Stage 4 — the grounded challenge, now a GATE that drops confirmed false positives.

Every soft (non-oracle) finding is challenged by the strong model: it tries to REFUTE the finding
using only the document. A refutation is grounded when it quotes a passage, verbatim in the
document, that resolves the concern. A grounded refutation DROPS the finding — including the common
"these two values are inconsistent" claim when the values are actually different measurements
(different analysts, studies, replicates, methods, or timepoints, which are EXPECTED to differ). An
ungrounded challenge leaves the finding in place with a small confidence bump. Oracle/checklist
(hard) findings are never challenged and never dropped.
"""
from __future__ import annotations

import concurrent.futures
import re

import structlog
from pydantic import BaseModel, Field

from agents.detection.oracles import parse_limit, parse_number, satisfies
from agents.detection.prompts import CHALLENGE
from agents.detection.render import render_sections
from agents.detection.verify import _anchored, _doc_corpus, _norm
from config import get_settings
from llm.structured import structured_call
from schemas.faults import EvidenceClass, Fault, Tier

log = structlog.get_logger()

_MAX_CHALLENGES = 150   # safety ceiling only — every soft finding is challenged; real docs stay well under
_MAX_WORKERS = 10

_TIER_ORDER = {Tier.VERIFIED: 0, Tier.CORROBORATED: 1, Tier.ADVISORY: 2}
_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


class ChallengeVerdict(BaseModel):
    refuted: bool = Field(description="True only if a resolving passage was found in the document.")
    counter_evidence: str = Field(default="", description="The exact passage that resolves the concern; empty if none.")
    reasoning: str = Field(default="", description="One sentence.")

    # --- arithmetic refutation -----------------------------------------------------------
    # The model does NOT judge compliance; it only reports the two cells verbatim and WE compute.
    claims_limit_violation: bool = Field(
        default=False,
        description="True if the finding asserts a measured value violates an acceptance criterion.",
    )
    criterion_quote: str = Field(
        default="", description="The acceptance criterion exactly as written, e.g. '0.9 - 1.5' or 'NMT 33.0%'."
    )
    observed_quote: str = Field(
        default="", description="The measured value exactly as written in the document, e.g. '1.2'."
    )


_TABLE_NUM = re.compile(r"table\s*(\d+)", re.I)


def _table_num(text: str) -> str:
    m = _TABLE_NUM.search(text or "")
    return m.group(1) if m else ""


def _sections_for(fault: Fault, sections: list[dict]) -> list[dict]:
    """The sections the challenger needs: the one holding the referenced table, plus any whose
    heading matches the fault's section. Resolving table_ref is what lets the challenger see the
    evidence a reviewer's vague `section` field would otherwise hide (e.g. the N/A cell and the
    prose that explains it)."""
    picked: list[dict] = []
    ref_num = _table_num(fault.table_ref)
    if ref_num:
        for s in sections:
            if any(_table_num(t.get("title", "")) == ref_num for t in s.get("tables", [])):
                picked.append(s)
    if fault.section:
        needle = fault.section.lower()
        for s in sections:
            heading = (s.get("heading", "") or "").lower()
            if s not in picked and heading and (needle in heading or heading in needle):
                picked.append(s)
    # A cross-section finding names the section indices it spans — the challenger must see all of
    # them, or (seeing only one half) it would wrongly "refute" a real intersection fault.
    for idx in fault.cited_section_indices or []:
        if 0 <= idx < len(sections) and sections[idx] not in picked:
            picked.append(sections[idx])
    return picked


def _context_for(fault: Fault, sections: list[dict]) -> str:
    picked = _sections_for(fault, sections)
    if picked:
        return render_sections(picked, char_budget=16_000)
    # No anchor to a section/table -> give the challenger broad access; its job is to refute,
    # so wide context here (unlike at detection) is correct.
    return render_sections(sections, char_budget=30_000)


def _cell_in_corpus(text: str, corpus: str) -> bool:
    """Anchor a single cell (a criterion or a measured value) in the document.

    Separate from `_anchored`, which requires >=4 chars to stop trivial matches: real measured
    values are routinely shorter ("1.2", "9.1"), and rejecting them would make every numeric
    refutation impossible — the exact gap that let the false positives through.
    """
    n = _norm(text)
    return bool(n) and n in corpus


def _arithmetic_refutation(verdict: ChallengeVerdict, corpus: str) -> str:
    """Recompute a claimed limit violation from the document's own cells. Returns a note when the
    value provably SATISFIES its criterion (i.e. the finding is false), else "".

    This is the precision counterpart to the oracle battery: no fault pattern is hardcoded, we only
    verify the model's own arithmetic. It exists because a quote can never refute "1.2 violates
    0.9-1.5" — the refutation is a computation, not a passage, so the quote-only gate let every
    false numeric claim through. The model supplies the two cells; the comparison is done in code.
    Both cells must appear verbatim in the document, so an invented number cannot clear a finding.
    """
    if not verdict.claims_limit_violation:
        return ""
    criterion_text = (verdict.criterion_quote or "").strip()
    observed_text = (verdict.observed_quote or "").strip()
    if not criterion_text or not observed_text:
        return ""
    if not (_cell_in_corpus(criterion_text, corpus) and _cell_in_corpus(observed_text, corpus)):
        return ""

    limit = parse_limit(criterion_text)
    value = parse_number(observed_text)
    if limit is None or value is None:
        return ""
    if not satisfies(value, limit):
        return ""   # the violation is real — the finding stands
    return f"Recomputed: observed {observed_text} satisfies the criterion {criterion_text}."


def _apply_verdict(fault: Fault, verdict: ChallengeVerdict, corpus: str) -> bool:
    """Gate. Returns True when the finding is grounded-refuted and should be DROPPED as a confirmed
    false positive; otherwise the finding survives with a small confidence bump.

    A refutation is grounded two ways: a verbatim passage that resolves the concern, OR a
    recomputation over the cited cells showing the claimed limit violation does not exist.
    """
    quoted = (
        verdict.refuted
        and verdict.counter_evidence.strip()
        and _anchored(verdict.counter_evidence, corpus)
    )
    if quoted:
        fault.challenge_note = verdict.counter_evidence.strip()[:300]
        return True

    computed = _arithmetic_refutation(verdict, corpus)
    if computed:
        fault.challenge_note = computed[:300]
        log.info("arithmetic_refutation", title=fault.title[:80], note=computed[:120])
        return True

    fault.confidence = min(round(fault.confidence + 0.1, 2), 0.9)
    return False


def _challenge_one(fault: Fault, sections: list[dict], model: str) -> ChallengeVerdict | None:
    context = _context_for(fault, sections)
    user = (
        "Proposed deficiency:\n"
        f"Title: {fault.title}\n"
        f"Detail: {fault.detail}\n"
        f"Evidence cited: {fault.evidence}\n\n"
        f"Document excerpt:\n{context}"
    )
    inst, _failure = structured_call(
        messages=[{"role": "system", "content": CHALLENGE}, {"role": "user", "content": user}],
        model_cls=ChallengeVerdict,
        model=model,
        temperature=0.0,
        max_tokens=512,
        repair_context="challenge",
    )
    return inst


def challenge_faults(faults: list[Fault], sections: list[dict], doc: dict, model: str | None = None) -> list[Fault]:
    """Challenge EVERY soft finding and DROP the grounded-refuted ones."""
    # The analyst's model choice governs the whole run — the gate included. Falling back to a
    # different "strong" model here would silently review on a model the analyst did not pick.
    gate_model = model or get_settings().detector_model
    corpus = _doc_corpus(doc)
    soft = [
        f for f in faults
        if f.evidence_class in (EvidenceClass.MODEL_JUDGMENT, EvidenceClass.QUOTE_ANCHORED)
    ]
    if len(soft) > _MAX_CHALLENGES:
        log.warning("challenge_ceiling_hit", soft=len(soft), challenged=_MAX_CHALLENGES)
    targets = soft[:_MAX_CHALLENGES]

    refuted_ids: set[int] = set()
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            future_to_fault = {pool.submit(_challenge_one, f, sections, gate_model): f for f in targets}
            for future in concurrent.futures.as_completed(future_to_fault):
                fault = future_to_fault[future]
                try:
                    verdict = future.result()
                    if verdict is not None and _apply_verdict(fault, verdict, corpus):
                        refuted_ids.add(id(fault))
                except Exception as exc:  # noqa: BLE001 - a failed challenge must not drop the finding
                    log.warning("challenge_failed", error=str(exc)[:200])

    kept = [f for f in faults if id(f) not in refuted_ids]
    log.info("challenge_gate", total=len(faults), refuted=len(refuted_ids), kept=len(kept))
    return sorted(
        kept,
        key=lambda f: (_TIER_ORDER[f.tier], _SEV_ORDER.get(f.severity.value, 1), -f.confidence),
    )
