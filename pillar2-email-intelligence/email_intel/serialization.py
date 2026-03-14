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
