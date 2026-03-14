"""Tests for the document classifier — merged from Pillar 3."""

from __future__ import annotations

import pytest
from email_intel.classifier import (
    classify_by_filename,
    classify_by_content,
    classify_document,
    build_classification_prompt,
    parse_ai_classification,
)
from email_intel.document_models import (
    ClassificationConfidence,
    DocumentType,
)


class TestFilenameClassification:
    def test_invoice(self):
        r = classify_by_filename("Invoice_HES_March2026.pdf")
        assert r is not None
        assert r.document_type == DocumentType.INVOICE

    def test_amendment_before_contract(self):
        r = classify_by_filename("Amendment_3_DrillCo_MSA.pdf")
        assert r is not None
        assert r.document_type == DocumentType.AMENDMENT

    def test_nda(self):
        r = classify_by_filename("NDA_AcmeResources_2026.pdf")
        assert r is not None
        assert r.document_type == DocumentType.NDA

    def test_operating_agreement(self):
        r = classify_by_filename("Operating_Agreement_Peak10.pdf")
        assert r is not None
        assert r.document_type == DocumentType.OPERATING_AGREEMENT

    def test_psa(self):
        r = classify_by_filename("PSA_LovingCounty_Draft.pdf")
        assert r is not None
        assert r.document_type == DocumentType.PSA

    def test_contract_generic(self):
        r = classify_by_filename("Contract_VendorServices.pdf")
        assert r is not None
        assert r.document_type == DocumentType.CONTRACT

    def test_msa(self):
        r = classify_by_filename("MSA_DrillCo_2026.pdf")
        assert r is not None
        assert r.document_type == DocumentType.CONTRACT

    def test_receipt(self):
        r = classify_by_filename("receipt_uber_20260314.pdf")
        assert r is not None
        assert r.document_type == DocumentType.RECEIPT

    def test_afe(self):
        r = classify_by_filename("AFE_Well7_Completion.pdf")
        assert r is not None
        assert r.document_type == DocumentType.AFE

    def test_field_report(self):
        r = classify_by_filename("daily_report_20260314.pdf")
        assert r is not None
        assert r.document_type == DocumentType.FIELD_REPORT

    def test_unknown_filename(self):
        r = classify_by_filename("random_notes.txt")
        assert r is None


class TestContentClassification:
    def test_invoice_content(self):
        r = classify_by_content("Invoice Number: INV-2026-0412\nTotal Due: $5,000")
        assert r is not None
        assert r.document_type == DocumentType.INVOICE

    def test_nda_content(self):
        r = classify_by_content("This non-disclosure agreement is entered into by...")
        assert r is not None
        assert r.document_type == DocumentType.NDA

    def test_title_opinion(self):
        r = classify_by_content("This title opinion covers the mineral interests in...")
        assert r is not None
        assert r.document_type == DocumentType.TITLE_OPINION


class TestUnifiedPipeline:
    def test_high_confidence_filename_wins(self):
        r = classify_document("Invoice_HES.pdf", content_text="random text")
        assert r.document_type == DocumentType.INVOICE
        assert r.confidence >= 0.85

    def test_content_augments_filename(self):
        r = classify_document(
            "document.pdf",
            content_text="Invoice Number: 12345",
        )
        assert r.document_type == DocumentType.INVOICE

    def test_ai_response_used(self):
        r = classify_document(
            "mystery.pdf",
            ai_response={
                "document_type": "psa",
                "confidence": 0.92,
                "reasoning": "AI detected PSA content",
                "metadata": {"counterparty": "AcmeResources"},
            },
        )
        assert r.document_type == DocumentType.PSA
        assert r.metadata.counterparty == "AcmeResources"

    def test_unknown_fallback(self):
        r = classify_document("notes.txt")
        assert r.document_type == DocumentType.UNKNOWN


class TestAIClassificationParsing:
    def test_valid_response(self):
        r = parse_ai_classification({
            "document_type": "amendment",
            "confidence": 0.88,
            "reasoning": "Document amends existing MSA",
            "metadata": {"counterparty": "DrillCo"},
        })
        assert r.document_type == DocumentType.AMENDMENT
        assert r.confidence == 0.88
        assert r.metadata.counterparty == "DrillCo"

    def test_unknown_type_fallback(self):
        r = parse_ai_classification({"document_type": "alien_doc"})
        assert r.document_type == DocumentType.UNKNOWN


class TestPromptBuilder:
    def test_prompt_includes_filename(self):
        prompt = build_classification_prompt("test.pdf", "some text content")
        assert "test.pdf" in prompt
        assert "some text content" in prompt
        assert "document_type" in prompt
