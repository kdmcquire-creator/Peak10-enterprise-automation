"""Tests for Pillar 3 data models."""

from __future__ import annotations

from document_ai.models import (
    DOCUMENT_FILING_MAP,
    FOLDER_HIERARCHY,
    DocumentType,
    TopLevelFolder,
)


class TestFolderHierarchy:
    def test_all_top_level_folders_defined(self):
        for folder in TopLevelFolder:
            assert folder in FOLDER_HIERARCHY

    def test_staging_has_inbox(self):
        assert "Inbox" in FOLDER_HIERARCHY[TopLevelFolder.STAGING]

    def test_corporate_has_finance_ap(self):
        assert "Finance/AP" in FOLDER_HIERARCHY[TopLevelFolder.CORPORATE]

    def test_operations_has_well_files(self):
        assert "Well_Files" in FOLDER_HIERARCHY[TopLevelFolder.OPERATIONS]

    def test_deals_has_active_pipeline(self):
        subs = FOLDER_HIERARCHY[TopLevelFolder.DEALS]
        assert "Active" in subs
        assert "Pipeline" in subs


class TestDocumentFilingMap:
    def test_all_document_types_mapped(self):
        for doc_type in DocumentType:
            assert doc_type in DOCUMENT_FILING_MAP, (
                f"DocumentType.{doc_type.name} has no filing destination"
            )

    def test_invoice_goes_to_finance_ap(self):
        assert DOCUMENT_FILING_MAP[DocumentType.INVOICE] == "01_CORPORATE/Finance/AP"

    def test_loi_goes_to_deals(self):
        assert DOCUMENT_FILING_MAP[DocumentType.LOI] == "03_DEALS/Active/LOIs"

    def test_unknown_goes_to_staging(self):
        assert DOCUMENT_FILING_MAP[DocumentType.UNKNOWN] == "00_STAGING/Errors"
