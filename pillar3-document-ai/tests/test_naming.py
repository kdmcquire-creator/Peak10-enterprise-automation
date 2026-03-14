"""Tests for the auto-naming and filing recommendation engine."""

from __future__ import annotations

from datetime import date

import pytest

from document_ai.models import (
    ClassificationConfidence,
    ClassificationResult,
    DocumentType,
    ExtractedMetadata,
)
from document_ai.naming import generate_standardized_name, recommend_filing


class TestStandardizedNaming:
    def test_invoice_with_vendor(self):
        classification = ClassificationResult(
            document_type=DocumentType.INVOICE,
            confidence=0.92,
            metadata=ExtractedMetadata(
                vendor_name="Halliburton Services",
                reference_number="INV-2026-0412",
            ),
        )
        name = generate_standardized_name(
            classification, "pdf", effective_date=date(2026, 3, 14)
        )
        assert name == "2026-03-14_Invoice_Halliburton_Services_INV-2026-0412.pdf"

    def test_psa_with_county(self):
        classification = ClassificationResult(
            document_type=DocumentType.PSA,
            confidence=0.88,
            metadata=ExtractedMetadata(
                counterparty="Acme Resources",
                county="Loving",
            ),
        )
        name = generate_standardized_name(
            classification, ".pdf", effective_date=date(2026, 3, 14)
        )
        assert name == "2026-03-14_PSA_Acme_Resources_LovingCounty.pdf"

    def test_unknown_no_metadata(self):
        classification = ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
        )
        name = generate_standardized_name(
            classification, "pdf", effective_date=date(2026, 3, 14)
        )
        assert name == "2026-03-14_Document_Unidentified.pdf"

    def test_payment_schedule(self):
        classification = ClassificationResult(
            document_type=DocumentType.PAYMENT_SCHEDULE,
            confidence=0.95,
            metadata=ExtractedMetadata(
                reference_number="Run-abc123",
            ),
        )
        name = generate_standardized_name(
            classification, "pdf", effective_date=date(2026, 3, 14)
        )
        assert name == "2026-03-14_AP_PaymentSchedule_Run-abc123.pdf"

    def test_field_report_with_well(self):
        classification = ClassificationResult(
            document_type=DocumentType.FIELD_REPORT,
            confidence=0.88,
            metadata=ExtractedMetadata(well_name="Peak 10 Well #7"),
        )
        name = generate_standardized_name(
            classification, "pdf", effective_date=date(2026, 3, 14)
        )
        assert "FieldReport" in name
        assert "Peak_10_Well_7" in name


class TestFilingRecommendation:
    def test_high_confidence_no_review(self):
        classification = ClassificationResult(
            document_type=DocumentType.INVOICE,
            confidence=0.92,
            confidence_level=ClassificationConfidence.HIGH,
        )
        rec = recommend_filing(classification, "invoice.pdf", "pdf")
        assert rec.recommended_path == "01_CORPORATE/Finance/AP"
        assert rec.requires_review is False
        assert len(rec.alternative_paths) == 0

    def test_medium_confidence_requires_review(self):
        classification = ClassificationResult(
            document_type=DocumentType.CONTRACT,
            confidence=0.70,
            confidence_level=ClassificationConfidence.MEDIUM,
        )
        rec = recommend_filing(classification, "doc.pdf", "pdf")
        assert rec.recommended_path == "01_CORPORATE/Legal/Contracts"
        assert rec.requires_review is True
        assert len(rec.alternative_paths) > 0

    def test_unknown_goes_to_staging_errors(self):
        classification = ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            confidence_level=ClassificationConfidence.LOW,
        )
        rec = recommend_filing(classification, "mystery.bin", "bin")
        assert rec.recommended_path == "00_STAGING/Errors"
        assert rec.requires_review is True

    def test_deals_filing(self):
        classification = ClassificationResult(
            document_type=DocumentType.LOI,
            confidence=0.90,
            confidence_level=ClassificationConfidence.HIGH,
        )
        rec = recommend_filing(classification, "loi.pdf", "pdf")
        assert rec.recommended_path == "03_DEALS/Active/LOIs"

    def test_governance_filing(self):
        classification = ClassificationResult(
            document_type=DocumentType.BOARD_MINUTES,
            confidence=0.90,
            confidence_level=ClassificationConfidence.HIGH,
        )
        rec = recommend_filing(classification, "minutes.pdf", "pdf")
        assert rec.recommended_path == "04_GOVERNANCE/Board_Minutes"
