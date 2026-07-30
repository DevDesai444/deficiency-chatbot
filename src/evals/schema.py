"""The ground-truth eval-set data model and loader.

Turns the human-readable gold-standard reference (docs/eval/gt_A..D.md) into a typed,
loadable dataset so recall-by-failure-family can be computed deterministically. This is
the contract every later harness plan scores against — defined first so the metrics
engine (Plan 03) and the breadth expansion (Plan 02) build against a fixed shape, not a
moving target.

Pure data module: no import of `agents.*`, no network access, no LLM calls.
"""
from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FailureFamily(StrEnum):
    """The four ground-truth failure families.

    Fixed by ROADMAP Phase 0 success criterion 2 — these are the exact section headers
    used in docs/eval/MEASUREMENT.md's "Missed (26/28) ... by failure family" breakdown.
    """

    ABSENCE_OF_EVIDENCE = "absence_of_evidence"
    DERIVATION_PLAUSIBILITY = "derivation_plausibility"
    CROSS_REFERENCE_INTEGRITY = "cross_reference_integrity"
    REGULATORY_FRAMING = "regulatory_framing"


class Confidence(StrEnum):
    """Confidence vocabulary reused verbatim from the gt_*.md ground-truth files."""

    CERTAIN = "certain"
    LIKELY = "likely"


class GroundTruthDeficiency(BaseModel):
    """One hand-verified real deficiency in a reference document."""

    id: str = Field(description='Source-prefixed identifier, e.g. "A-01", "C-01".')
    doc_id: str
    title: str = Field(description="One-line statement of the deficiency.")
    evidence_anchor: str = Field(
        description=(
            "A verbatim string copied from the source document — the token(s) a real "
            "finding must cite. Kept short so it can be substring-matched later."
        )
    )
    failure_family: FailureFamily
    confidence: Confidence = Confidence.LIKELY
    section_hint: str = ""
    tp_required: bool = Field(
        default=False,
        description=(
            "True == the detector already finds this; the zero-TP-lost gate must "
            "never lose it."
        ),
    )


class EvalDocument(BaseModel):
    """One source document registered in the eval corpus."""

    doc_id: str
    path: str = Field(description="Repo-relative path.")
    format: Literal["pdf", "docx"]
    held_out: bool = False


class EvalSet(BaseModel):
    """The full ground-truth eval set: registered documents + their labeled deficiencies."""

    documents: list[EvalDocument] = Field(default_factory=list)
    deficiencies: list[GroundTruthDeficiency] = Field(default_factory=list)

    def families(self) -> set[FailureFamily]:
        """Distinct failure families represented across all deficiencies."""
        return {d.failure_family for d in self.deficiencies}

    def tp_required(self) -> list[GroundTruthDeficiency]:
        """Deficiencies the detector already finds — the zero-TP-lost gate anchors."""
        return [d for d in self.deficiencies if d.tp_required]


def load_eval_set(dataset_dir: str | Path | None = None) -> EvalSet:
    """Load the eval set from `dataset_dir`.

    Reads `documents.json` (a JSON list of `EvalDocument` dicts) and globs ALL
    `*.deficiencies.json` files in the directory (each a JSON list of
    `GroundTruthDeficiency` dicts), concatenates them, and validates the result into an
    `EvalSet`. Globbing — not a hardcoded file list — means a later plan can add a new
    document's label file without editing this loader.

    Default `dataset_dir` is the `dataset/` folder next to this file.
    """
    resolved_dir = Path(dataset_dir) if dataset_dir is not None else Path(__file__).parent / "dataset"

    documents_raw = json.loads((resolved_dir / "documents.json").read_text())
    documents = [EvalDocument.model_validate(entry) for entry in documents_raw]

    deficiencies: list[GroundTruthDeficiency] = []
    for deficiencies_path in sorted(resolved_dir.glob("*.deficiencies.json")):
        raw = json.loads(deficiencies_path.read_text())
        deficiencies.extend(GroundTruthDeficiency.model_validate(entry) for entry in raw)

    return EvalSet(documents=documents, deficiencies=deficiencies)
