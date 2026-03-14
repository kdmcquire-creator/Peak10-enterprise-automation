"""Tests for the correction store — merged from Pillar 3."""

from __future__ import annotations

import pytest
from email_intel.corrections import CorrectionStore
from email_intel.document_models import DocumentType


@pytest.fixture
def store():
    return CorrectionStore()


class TestCorrectionStore:
    def test_log_correction(self, store):
        entry = store.log_correction(
            document_id="doc-1",
            original_type=DocumentType.CONTRACT,
            corrected_type=DocumentType.AMENDMENT,
            original_path="01_CORPORATE/Legal/Contracts",
            corrected_path="01_CORPORATE/Legal/Amendments",
        )
        assert entry.original_type == DocumentType.CONTRACT
        assert entry.corrected_type == DocumentType.AMENDMENT
        assert store.total_corrections == 1

    def test_get_corrections_for_type(self, store):
        store.log_correction("d1", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        store.log_correction("d2", DocumentType.CONTRACT, DocumentType.NDA, "", "")
        store.log_correction("d3", DocumentType.INVOICE, DocumentType.RECEIPT, "", "")
        assert len(store.get_corrections_for_type(DocumentType.CONTRACT)) == 2
        assert len(store.get_corrections_for_type(DocumentType.INVOICE)) == 1

    def test_most_common_correction_needs_minimum(self, store):
        store.log_correction("d1", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        store.log_correction("d2", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        # Only 2 corrections — below threshold of 3
        assert store.get_most_common_correction(DocumentType.CONTRACT) is None

    def test_most_common_correction_detects_pattern(self, store):
        store.log_correction("d1", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        store.log_correction("d2", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        store.log_correction("d3", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        assert store.get_most_common_correction(DocumentType.CONTRACT) == DocumentType.AMENDMENT

    def test_no_dominant_correction(self, store):
        store.log_correction("d1", DocumentType.CONTRACT, DocumentType.AMENDMENT, "", "")
        store.log_correction("d2", DocumentType.CONTRACT, DocumentType.NDA, "", "")
        store.log_correction("d3", DocumentType.CONTRACT, DocumentType.PSA, "", "")
        # No type has >50% of corrections
        assert store.get_most_common_correction(DocumentType.CONTRACT) is None
