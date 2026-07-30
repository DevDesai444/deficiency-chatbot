"""Load a captured detector run (a serialized `FaultReport`) as a deterministic, no-LLM input
for the scoring engine.

The golden fixture under `dataset/golden/` is a real detector run (run 3 on the estradiol
document, see docs/eval/MEASUREMENT.md) transcribed verbatim into JSON once, then committed. Every
downstream metric can replay it in CI without a model call -- the harness is reproducible by
construction, not by convention.
"""
from __future__ import annotations

from pathlib import Path

from schemas.faults import FaultReport


def load_captured(path: str | Path) -> FaultReport:
    """Load and validate a captured `FaultReport` JSON file from `path`."""
    return FaultReport.model_validate_json(Path(path).read_text())


def golden_report(doc_id: str = "mvr1381") -> FaultReport:
    """Load the committed golden fixture for `doc_id` from `dataset/golden/{doc_id}_run3.json`.

    Default path is resolved relative to this module, not the caller's cwd, so `golden_report()`
    works identically whether invoked from a test, a CLI, or another package.
    """
    golden_path = Path(__file__).parent / "dataset" / "golden" / f"{doc_id}_run3.json"
    return load_captured(golden_path)
