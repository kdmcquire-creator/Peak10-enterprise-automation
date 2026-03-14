"""JSON serialization for Email Intelligence models."""

from __future__ import annotations

from typing import Any

from .models import (
    AttachmentRouting,
    DealSignal,
    DraftResponse,
    EmailMessage,
    TriageResult,
)
from .document_models import (
    ClassificationResult,
    FilingRecommendation,
    CorrectionLog,
)


def serialize_email(e: EmailMessage) -> dict[str, Any]:
    return {
        "message_id": e.message_id,
        "subject": e.subject,
        "sender": e.sender,
        "sender_name": e.sender_name,
        "recipients": e.recipients,
        "received_at": e.received_at.isoformat(),
        "has_attachments": e.has_attachments,
        "attachment_names": e.attachment_names,
        "is_reply": e.is_reply,
    }


def serialize_deal_signal(s: DealSignal) -> dict[str, Any]:
    return {
        "signal_type": s.signal_type.value,
        "confidence": s.confidence,
        "evidence": s.evidence,
        "suggested_action": s.suggested_action,
    }


def serialize_triage_result(r: TriageResult) -> dict[str, Any]:
    return {
        "message_id": r.message_id,
        "category": r.category.value,
        "urgency": r.urgency.value,
        "urgency_label": r.urgency.name,
        "confidence": r.confidence,
        "summary": r.summary,
        "deal_signals": [serialize_deal_signal(s) for s in r.deal_signals],
        "recommended_actions": [a.value for a in r.recommended_actions],
        "routing": r.routing,
        "reasoning": r.reasoning,
    }


def serialize_draft_response(d: DraftResponse) -> dict[str, Any]:
    return {
        "draft_id": d.draft_id,
        "message_id": d.message_id,
        "subject": d.subject,
        "body": d.body,
        "tone": d.tone,
        "confidence": d.confidence,
        "needs_review": d.needs_review,
    }


def serialize_attachment_routing(r: AttachmentRouting) -> dict[str, Any]:
    return {
        "attachment_name": r.attachment_name,
        "detected_type": r.detected_type,
        "target_pillar": r.target_pillar,
        "target_endpoint": r.target_endpoint,
        "confidence": r.confidence,
    }


def serialize_classification_result(r: ClassificationResult) -> dict[str, Any]:
    return {
        "document_type": r.document_type.value,
        "confidence": r.confidence,
        "confidence_level": r.confidence_level.value,
        "reasoning": r.reasoning,
        "metadata": {
            "vendor_name": r.metadata.vendor_name,
            "counterparty": r.metadata.counterparty,
            "effective_date": r.metadata.effective_date,
            "expiration_date": r.metadata.expiration_date,
            "amount": r.metadata.amount,
            "well_name": r.metadata.well_name,
            "lease_name": r.metadata.lease_name,
            "county": r.metadata.county,
            "state": r.metadata.state,
            "reference_number": r.metadata.reference_number,
        },
    }


def serialize_filing_recommendation(r: FilingRecommendation) -> dict[str, Any]:
    return {
        "recommended_path": r.recommended_path,
        "standardized_name": r.standardized_name,
        "document_type": r.document_type.value,
        "confidence_level": r.confidence_level.value,
        "requires_review": r.requires_review,
        "alternative_paths": r.alternative_paths,
    }


def serialize_correction_log(c: CorrectionLog) -> dict[str, Any]:
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
