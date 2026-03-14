"""Tests for the correction logging and learning loop."""

from __future__ import annotations

from document_ai.corrections import CorrectionStore
from document_ai.models import DocumentType


class TestCorrectionStore:
    def test_log_and_retrieve(self):
        store = CorrectionStore()
        correction = store.log_correction(
            document_id="doc-1",
            original_type=DocumentType.CORRESPONDENCE,
            corrected_type=DocumentType.CONTRACT,
            original_path="01_CORPORATE/Legal",
            corrected_path="01_CORPORATE/Legal/Contracts",
            notes="Was actually an MSA",
        )
        assert store.total_corrections == 1
        assert correction.original_type == DocumentType.CORRESPONDENCE
        assert correction.corrected_type == DocumentType.CONTRACT

    def test_get_corrections_for_type(self):
        store = CorrectionStore()
        store.log_correction("d1", DocumentType.CORRESPONDENCE, DocumentType.CONTRACT, "", "")
        store.log_correction("d2", DocumentType.CORRESPONDENCE, DocumentType.NDA, "", "")
        store.log_correction("d3", DocumentType.INVOICE, DocumentType.RECEIPT, "", "")

        corr = store.get_corrections_for_type(DocumentType.CORRESPONDENCE)
        assert len(corr) == 2

    def test_most_common_correction_needs_minimum(self):
        store = CorrectionStore()
        store.log_correction("d1", DocumentType.CORRESPONDENCE, DocumentType.CONTRACT, "", "")
        # Only 1 correction — not enough for pattern
        assert store.get_most_common_correction(DocumentType.CORRESPONDENCE) is None

    def test_most_common_correction_with_clear_pattern(self):
        store = CorrectionStore()
        for i in range(5):
            store.log_correction(
                f"d{i}", DocumentType.CORRESPONDENCE, DocumentType.CONTRACT, "", ""
            )
        store.log_correction("d5", DocumentType.CORRESPONDENCE, DocumentType.NDA, "", "")

        result = store.get_most_common_correction(DocumentType.CORRESPONDENCE)
        assert result == DocumentType.CONTRACT

    def test_no_pattern_when_corrections_are_spread(self):
        store = CorrectionStore()
        store.log_correction("d1", DocumentType.UNKNOWN, DocumentType.CONTRACT, "", "")
        store.log_correction("d2", DocumentType.UNKNOWN, DocumentType.INVOICE, "", "")
        store.log_correction("d3", DocumentType.UNKNOWN, DocumentType.NDA, "", "")
        store.log_correction("d4", DocumentType.UNKNOWN, DocumentType.AFE, "", "")

        result = store.get_most_common_correction(DocumentType.UNKNOWN)
        assert result is None  # no clear >50% pattern
