"""P1 / D-PRE1 real-ingestion requirement-index integration proof."""
from __future__ import annotations

from pathlib import Path
import shutil

import pytest

import ingest.corpus as corpus_mod
import rulebook.requirement_index as ri
from tools.errors import ToolRejected
from tools.ledger import RetrievalLedger
from tools.read_guideline import read_guideline

_MVR1381 = Path("data/32s43-validation-related-compounds-method.pdf")
_SPEC32S41 = Path("data/32s41-Specification.pdf")
_TARGET_IDS = {"CFR-211160B-SOUND-BASIS", "CFR-211194-CALCULATIONS"}


@pytest.fixture(scope="module")
def _self_contained_rulebook_store():
    """Build the real local rulebook store + edges without rewriting rulebook/manifest.yaml."""
    from rulebook.build import build_ecfr, build_fda, build_ich

    for rows in (
        build_ecfr(update_manifest=False),
        build_ich(update_manifest=False),
        build_fda(update_manifest=False),
    ):
        errors = [r for r in rows if "error" in r]
        assert not errors, f"rulebook build fixture hit vendoring errors: {errors}"
    ri.load_requirement_index.cache_clear()
    ri.build_requirement_edges()
    yield
    ri.load_requirement_index.cache_clear()


def _copy_required_pdf(src: Path, dst_dir: Path) -> None:
    if not src.exists():
        pytest.skip(f"missing required real-ingest PDF: {src}")
    shutil.copy2(src, dst_dir / src.name)


def test_real_classification_makes_the_cfr_entries_enumerate(
    tmp_path, monkeypatch, _self_contained_rulebook_store
):
    """P1 / D-PRE1 step 2. The D-RI1(2) traceability test passes 14/14 against HARDCODED
    manifests that assume mvr1381 classifies to 3.2.S.5 -- it proves "IF the profile includes
    3.2.S.5, the entries fire", not that real ingestion tags the document that way. This is the
    composition test that closes the gap. absence_of_evidence (D-GO1(iii)'s named headline
    expectation) is downstream of it.
    """
    root = tmp_path / "real-corpus"
    root.mkdir()
    _copy_required_pdf(_MVR1381, root)
    _copy_required_pdf(_SPEC32S41, root)
    monkeypatch.setattr(corpus_mod, "save_manifest", lambda *args, **kwargs: None)

    index = corpus_mod.ingest_corpus(root, cache_dir=str(tmp_path / "ingest-cache"))
    docs_by_filename = {doc.filename: doc for doc in index.manifest.documents}
    assert set(docs_by_filename) == {_MVR1381.name, _SPEC32S41.name}

    mvr_family = docs_by_filename[_MVR1381.name].classification.family_guess
    spec_family = docs_by_filename[_SPEC32S41.name].classification.family_guess
    assert mvr_family == "3.2.S.4.2"
    assert spec_family == "3.2.S.4.1"

    for family in (mvr_family, spec_family):
        rows = read_guideline(index.manifest, RetrievalLedger(), citation=None, family=family)
        assert not isinstance(rows, ToolRejected), f"{family}: read_guideline rejected: {rows}"
        enumerated_requirement_ids = {row["requirement_id"] for row in rows}
        assert _TARGET_IDS <= enumerated_requirement_ids
