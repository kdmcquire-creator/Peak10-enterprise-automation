"""Tests for the document naming and filing engine — merged from Pillar 3."""

from __future__ import annotations

from datetime import date

import pytest
from email_intel.naming import generate_standardized_name, recommend_filing
from email_intel.document_models import (
    ClassificationConfidence,
    ClassificationResult,
    DocumentType,
    ExtractedMetadata,
)


class TestStandardizedNaming:
    def test_invoice_with_vendor(self):
        result = ClassificationResult(
            document_type=DocumentType.INVOICE,
            confidence=0.90,
            confidence_level=ClassificationConfidence.HIGH,
            metadata=ExtractedMetadata(
                vendor_name="Halliburton",
                reference_number="INV-2026-0412",
            ),
        )
        name = generate_standardized_name(result, "pdf", effective_date=date(2026, 3, 14))
        assert name == "2026-03-14_Invoice_Halliburton_INV-2026-0412.pdf"

    def test_psa_with_county(self):
        result = ClassificationResult(
            document_type=DocumentType.PSA,
            confidence=0.90,
            confidence_level=ClassificationConfidence.HIGH,
            metadata=ExtractedMetadata(counterparty="AcmeResources", county="Loving"),
        )
        name = generate_standardized_name(result, "pdf", effective_date=date(2026, 3, 14))
        assert "PSA" in name
        assert "AcmeResources" in name
        assert "LovingCounty" in name

    def test_unknown_produces_unidentified(self):
        result = ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            confidence_level=ClassificationConfidence.LOW,
        )
        name = generate_standardized_name(result, "pdf", effective_date=date(2026, 3, 14))
        assert "Document_Unidentified" in name

    def test_extension_stripped(self):
        result = ClassificationResult(
            document_type=DocumentType.RECEIPT,
            confidence=0.88,
            confidence_level=ClassificationConfidence.HIGH,
        )
        name = generate_standardized_name(result, ".pdf", effective_date=date(2026, 3, 14))
        assert name.endswith(".pdf")
        assert not name.endswith("..pdf")


class TestFilingRecommendation:
    def test_invoice_goes_to_finance_ap(self):
        result = ClassificationResult(
            document_type=DocumentType.INVOICE,
            confidence=0.90,
            confidence_level=ClassificationConfidence.HIGH,
        )
        filing = recommend_filing(result, "invoice.pdf", "pdf")
        assert filing.recommended_path == "01_CORPORATE/Finance/AP"
        assert not filing.requires_review

    def test_low_confidence_requires_review(self):
        result = ClassificationResult(
            document_type=DocumentType.CONTRACT,
            confidence=0.55,
            confidence_level=ClassificationConfidence.LOW,
        )
        filing = recommend_filing(result, "doc.pdf", "pdf")
        assert filing.requires_review
        assert len(filing.alternative_paths) > 0

    def test_psa_goes_to_deals(self):
        result = ClassificationResult(
            document_type=DocumentType.PSA,
            confidence=0.92,
            confidence_level=ClassificationConfidence.HIGH,
        )
        filing = recommend_filing(result, "psa.pdf", "pdf")
        assert filing.recommended_path == "03_DEALS/Active/PSAs"

    def test_unknown_goes_to_staging(self):
        result = ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            confidence_level=ClassificationConfidence.LOW,
        )
        filing = recommend_filing(result, "random.pdf", "pdf")
        assert filing.recommended_path == "00_STAGING/Errors"
