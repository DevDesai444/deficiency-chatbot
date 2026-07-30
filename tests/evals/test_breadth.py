"""Tests for the multi-document, multi-format, held-out breadth expansion (Plan 00-02).

NOTE: the DOCX document (doc_id="minispec") is a labeled ground-truth target only --
no DOCX parser exists yet at Phase 0, so the harness records it as a parse-fidelity
miss until Phase 1's DOCX parse path (INGEST-02) lands.
"""
from __future__ import annotations

from evals.schema import load_eval_set


class TestBreadthExpansion:
    def test_at_least_three_documents_registered(self):
        eval_set = load_eval_set()
        assert len(eval_set.documents) >= 3

    def test_formats_include_both_pdf_and_docx(self):
        eval_set = load_eval_set()
        formats = {doc.format for doc in eval_set.documents}
        assert "pdf" in formats
        assert "docx" in formats

    def test_at_least_one_held_out_document(self):
        eval_set = load_eval_set()
        assert any(doc.held_out for doc in eval_set.documents)

    def test_every_deficiency_doc_id_is_registered(self):
        eval_set = load_eval_set()
        doc_ids = {doc.doc_id for doc in eval_set.documents}
        deficiency_doc_ids = {d.doc_id for d in eval_set.deficiencies}
        assert deficiency_doc_ids <= doc_ids, deficiency_doc_ids - doc_ids

    def test_total_deficiencies_at_least_34(self):
        eval_set = load_eval_set()
        assert len(eval_set.deficiencies) >= 34

    def test_tuning_set_tp_required_count_is_unchanged_at_two(self):
        """The estradiol tuning set's 2 tp_required anchors (11477, 0.15) are
        untouched -- breadth docs (minispec, spec32s41) add zero tp_required
        anchors, since tp_required is reserved for the detector's existing hits.
        """
        eval_set = load_eval_set()
        assert len(eval_set.tp_required()) == 2
