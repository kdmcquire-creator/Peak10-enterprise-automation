"""
Document auto-naming and filing recommendation engine.

Generates standardized filenames following Peak 10's naming convention:
  YYYY-MM-DD_<DocumentType>_<Identifier>.<ext>

Examples:
  2026-03-14_Invoice_HalliburtonServices_INV-2026-0412.pdf
  2026-03-14_PSA_AcmeResources_LovinCounty.pdf
  2026-03-14_AP_PaymentSchedule_Run-abc123.pdf
"""

from __future__ import annotations

import re
from datetime import date

from .models import (
    ClassificationConfidence,
    ClassificationResult,
    DocumentType,
    DOCUMENT_FILING_MAP,
    FilingRecommendation,
    ExtractedMetadata,
)


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def _sanitize(text: str) -> str:
    """Remove characters unsafe for filenames, collapse whitespace."""
    sanitized = re.sub(r"[^\w\s\-]", "", text)
    sanitized = re.sub(r"\s+", "_", sanitized.strip())
    return sanitized[:60]  # cap length


def _type_label(doc_type: DocumentType) -> str:
    """Human-readable label for the document type in filenames."""
    labels = {
        DocumentType.CONTRACT: "Contract",
        DocumentType.AMENDMENT: "Amendment",
        DocumentType.NDA: "NDA",
        DocumentType.INSURANCE_POLICY: "InsurancePolicy",
        DocumentType.INVOICE: "Invoice",
        DocumentType.PAYMENT_SCHEDULE: "AP_PaymentSchedule",
        DocumentType.ACH_EXPORT: "AP_ACH_Export",
        DocumentType.TAX_FORM: "TaxForm",
        DocumentType.AUDIT_REPORT: "AuditReport",
        DocumentType.FIELD_REPORT: "FieldReport",
        DocumentType.AFE: "AFE",
        DocumentType.RUN_TICKET: "RunTicket",
        DocumentType.DECLINE_CURVE: "DeclineCurve",
        DocumentType.REGULATORY_FILING: "RegulatoryFiling",
        DocumentType.SAFETY_REPORT: "SafetyReport",
        DocumentType.LOI: "LOI",
        DocumentType.PSA: "PSA",
        DocumentType.TITLE_OPINION: "TitleOpinion",
        DocumentType.DUE_DILIGENCE: "DueDiligence",
        DocumentType.BOARD_MINUTES: "BoardMinutes",
        DocumentType.OPERATING_AGREEMENT: "OperatingAgreement",
        DocumentType.RESOLUTION: "Resolution",
        DocumentType.RECEIPT: "Receipt",
        DocumentType.EXPENSE_REPORT: "ExpenseReport",
        DocumentType.CORRESPONDENCE: "Correspondence",
        DocumentType.UNKNOWN: "Document",
    }
    return labels.get(doc_type, "Document")


def _build_identifier(metadata: ExtractedMetadata, doc_type: DocumentType) -> str:
    """Build the identifier segment from extracted metadata."""
    parts: list[str] = []

    # Vendor or counterparty name
    name = metadata.vendor_name or metadata.counterparty
    if name:
        parts.append(_sanitize(name))

    # Reference number if available
    if metadata.reference_number:
        parts.append(_sanitize(metadata.reference_number))

    # For deals/operations, use well or lease name
    if not parts:
        if metadata.well_name:
            parts.append(_sanitize(metadata.well_name))
        elif metadata.lease_name:
            parts.append(_sanitize(metadata.lease_name))

    # County for deal documents
    if doc_type in (DocumentType.PSA, DocumentType.LOI, DocumentType.TITLE_OPINION,
                    DocumentType.DUE_DILIGENCE):
        if metadata.county:
            parts.append(_sanitize(metadata.county) + "County")

    return "_".join(parts) if parts else "Unidentified"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_standardized_name(
    classification: ClassificationResult,
    file_extension: str,
    effective_date: date | None = None,
) -> str:
    """
    Generate a standardized filename based on classification and metadata.

    Format: YYYY-MM-DD_<TypeLabel>_<Identifier>.<ext>
    """
    dt = effective_date or date.today()
    date_str = dt.isoformat()
    type_label = _type_label(classification.document_type)
    identifier = _build_identifier(classification.metadata, classification.document_type)

    ext = file_extension.lstrip(".")
    return f"{date_str}_{type_label}_{identifier}.{ext}"


def recommend_filing(
    classification: ClassificationResult,
    original_filename: str,
    file_extension: str,
) -> FilingRecommendation:
    """
    Generate a complete filing recommendation: path + standardized name.
    """
    doc_type = classification.document_type
    recommended_path = DOCUMENT_FILING_MAP.get(doc_type, "00_STAGING/Errors")

    standardized_name = generate_standardized_name(
        classification, file_extension
    )

    requires_review = classification.confidence_level != ClassificationConfidence.HIGH

    # Build alternative paths for medium/low confidence
    alternative_paths: list[str] = []
    if requires_review:
        # Suggest the parent folder as an alternative
        parent = "/".join(recommended_path.split("/")[:-1])
        if parent and parent != recommended_path:
            alternative_paths.append(parent)
        # Always offer staging/errors as fallback
        alternative_paths.append("00_STAGING/Errors")

    return FilingRecommendation(
        recommended_path=recommended_path,
        standardized_name=standardized_name,
        document_type=doc_type,
        confidence_level=classification.confidence_level,
        requires_review=requires_review,
        alternative_paths=alternative_paths,
    )
