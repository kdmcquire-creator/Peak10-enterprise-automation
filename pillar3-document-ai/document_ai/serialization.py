"""JSON serialization for Document AI models."""

from __future__ import annotations

from typing import Any

from .models import (
    ClassificationResult,
    CorrectionLog,
    DocumentType,
    ExtractedMetadata,
    FilingRecommendation,
    StagedDocument,
)


def serialize_metadata(m: ExtractedMetadata) -> dict[str, Any]:
    return {
        "vendor_name": m.vendor_name,
        "counterparty": m.counterparty,
        "effective_date": m.effective_date,
        "expiration_date": m.expiration_date,
        "amount": m.amount,
        "well_name": m.well_name,
        "lease_name": m.lease_name,
        "county": m.county,
        "state": m.state,
        "reference_number": m.reference_number,
        "custom_fields": m.custom_fields,
    }


def serialize_classification(c: ClassificationResult) -> dict[str, Any]:
    return {
        "document_type": c.document_type.value,
        "confidence": c.confidence,
        "confidence_level": c.confidence_level.value,
        "metadata": serialize_metadata(c.metadata),
        "reasoning": c.reasoning,
    }


def serialize_filing(f: FilingRecommendation) -> dict[str, Any]:
    return {
        "recommended_path": f.recommended_path,
        "standardized_name": f.standardized_name,
        "document_type": f.document_type.value,
        "confidence_level": f.confidence_level.value,
        "requires_review": f.requires_review,
        "alternative_paths": f.alternative_paths,
    }


def serialize_staged_document(d: StagedDocument) -> dict[str, Any]:
    result: dict[str, Any] = {
        "document_id": d.document_id,
        "original_filename": d.original_filename,
        "file_extension": d.file_extension,
        "source": d.source,
        "source_detail": d.source_detail,
        "staged_at": d.staged_at.isoformat(),
        "file_size_bytes": d.file_size_bytes,
        "status": d.status,
    }
    if d.classification:
        result["classification"] = serialize_classification(d.classification)
    if d.filing:
        result["filing"] = serialize_filing(d.filing)
    return result


def serialize_correction(c: CorrectionLog) -> dict[str, Any]:
    return {
        "correction_id": c.correction_id,
        "document_id": c.document_id,
        "original_type": c.original_type.value,
        "corrected_type": c.corrected_type.value,
        "original_path": c.original_path,
        "corrected_path": c.corrected_path,
        "corrected_by": c.corrected_by,
        "corrected_at": c.corrected_at.isoformat(),
        "notes": c.notes,
    }
