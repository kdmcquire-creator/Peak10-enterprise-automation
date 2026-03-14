"""
Azure Functions HTTP triggers for the Email Intelligence system.

Endpoints:
  POST /api/email/triage           — Triage an inbound email
  POST /api/email/draft-reply      — Generate/save a draft reply
  GET  /api/email/drafts/{msg_id}  — Get drafts for a message
  PUT  /api/email/drafts/{draft_id} — Update a draft (approve/edit)
  DELETE /api/email/drafts/{draft_id} — Delete a draft

  POST /api/documents/classify     — Classify a document (attachment)
  POST /api/documents/correct      — Log a classification correction

  GET  /api/triage/history         — Query triage history from Cosmos DB

  GET  /api/health                 — Health check
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import azure.functions as func

from email_intel.models import EmailMessage, DraftResponse
from email_intel.triage import (
    build_triage_prompt,
    route_attachments,
    triage_email,
)
from email_intel.serialization import (
    serialize_attachment_routing,
    serialize_triage_result,
    serialize_draft_response,
    serialize_classification_result,
    serialize_filing_recommendation,
)
from email_intel.cosmos_client import get_store
from email_intel.openai_client import get_openai_client
from email_intel.classifier import classify_document, build_classification_prompt
from email_intel.naming import recommend_filing
from email_intel.corrections import CorrectionStore
from email_intel.document_models import DocumentType

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger("email-intel")

# Module-level correction store (backed by Cosmos in production)
_correction_store = CorrectionStore()


# ---------------------------------------------------------------------------
# POST /api/email/triage
# ---------------------------------------------------------------------------

@app.route(route="email/triage", methods=["POST"])
def triage(req: func.HttpRequest) -> func.HttpResponse:
    """Triage an inbound email with persistence and optional AI enhancement."""
    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON", 400)

    if not body.get("subject") and not body.get("sender"):
        return _error("'subject' or 'sender' is required", 400)

    email = EmailMessage(
        subject=body.get("subject", ""),
        sender=body.get("sender", ""),
        sender_name=body.get("sender_name", ""),
        recipients=body.get("recipients", []),
        body_preview=body.get("body_preview", ""),
        body_text=body.get("body_text", ""),
        has_attachments=body.get("has_attachments", False),
        attachment_names=body.get("attachment_names", []),
        is_reply=body.get("is_reply", False),
    )

    # Check if AI response was provided, or try to get one from OpenAI
    ai_response = body.get("ai_response")
    result = triage_email(email, ai_response=ai_response)

    # If low confidence and no AI response, try Azure OpenAI
    needs_ai = result.confidence < 0.85 and not ai_response
    ai_prompt = None
    if needs_ai:
        oai = get_openai_client()
        if oai.is_available:
            prompt = build_triage_prompt(email)
            ai_resp = oai.triage_email(prompt)
            if ai_resp:
                result = triage_email(email, ai_response=ai_resp)
                needs_ai = False
        if needs_ai:
            ai_prompt = build_triage_prompt(email)

    # Attachment routing details
    att_routing = []
    if email.has_attachments:
        att_routing = [
            serialize_attachment_routing(r)
            for r in route_attachments(email.attachment_names)
        ]

    # Persist to Cosmos DB
    triage_data = serialize_triage_result(result)
    triage_data["email_subject"] = email.subject
    triage_data["email_sender"] = email.sender
    store = get_store()
    store.save_triage_result(triage_data)

    return func.HttpResponse(
        body=json.dumps({
            "success": True,
            "triage": serialize_triage_result(result),
            "attachment_routing": att_routing,
            "needs_ai_triage": needs_ai,
            "ai_prompt": ai_prompt,
        }),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# POST /api/email/draft-reply
# ---------------------------------------------------------------------------

@app.route(route="email/draft-reply", methods=["POST"])
def draft_reply(req: func.HttpRequest) -> func.HttpResponse:
    """Generate a draft reply, optionally using Azure OpenAI."""
    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON", 400)

    message_id = body.get("message_id", "")
    subject = body.get("subject", "")
    email_body = body.get("body", "")
    sender_name = body.get("sender_name", "")
    tone = body.get("tone", "professional")

    if not message_id:
        return _error("'message_id' is required", 400)

    # Try Azure OpenAI for draft generation
    draft_data = None
    oai = get_openai_client()
    if oai.is_available:
        draft_data = oai.generate_draft_reply(
            email_subject=subject,
            email_body=email_body,
            sender_name=sender_name,
            tone=tone,
        )

    if draft_data:
        draft = DraftResponse(
            message_id=message_id,
            subject=draft_data.get("subject", f"Re: {subject}"),
            body=draft_data.get("body", ""),
            tone=tone,
            confidence=float(draft_data.get("confidence", 0.0)),
            needs_review=True,
        )
    else:
        # Return empty draft shell for manual composition
        draft = DraftResponse(
            message_id=message_id,
            subject=f"Re: {subject}",
            body="",
            tone=tone,
            confidence=0.0,
            needs_review=True,
        )

    # Persist draft
    draft_dict = serialize_draft_response(draft)
    store = get_store()
    store.save_draft(draft_dict)

    return func.HttpResponse(
        body=json.dumps({"success": True, "draft": draft_dict}),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# GET /api/email/drafts/{message_id}
# ---------------------------------------------------------------------------

@app.route(route="email/drafts/{message_id}", methods=["GET"])
def get_drafts(req: func.HttpRequest) -> func.HttpResponse:
    """Get all drafts for a given message."""
    message_id = req.route_params.get("message_id", "")
    if not message_id:
        return _error("message_id is required", 400)

    store = get_store()
    drafts = store.get_drafts_for_message(message_id)

    return func.HttpResponse(
        body=json.dumps({"success": True, "drafts": drafts}),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# PUT /api/email/drafts/{draft_id}
# ---------------------------------------------------------------------------

@app.route(route="email/drafts/{draft_id}", methods=["PUT"])
def update_draft(req: func.HttpRequest) -> func.HttpResponse:
    """Update a draft (edit body, approve for sending, etc.)."""
    draft_id = req.route_params.get("draft_id", "")
    if not draft_id:
        return _error("draft_id is required", 400)

    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON", 400)

    message_id = body.get("message_id", "")
    store = get_store()
    existing = store.get_draft(draft_id, message_id)

    if not existing:
        return _error("Draft not found", 404)

    # Update fields
    if "body" in body:
        existing["body"] = body["body"]
    if "subject" in body:
        existing["subject"] = body["subject"]
    if "tone" in body:
        existing["tone"] = body["tone"]
    if "approved" in body:
        existing["approved"] = body["approved"]
        existing["approved_at"] = datetime.utcnow().isoformat()
    existing["needs_review"] = not body.get("approved", False)

    store.save_draft(existing)

    return func.HttpResponse(
        body=json.dumps({"success": True, "draft": existing}),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# DELETE /api/email/drafts/{draft_id}
# ---------------------------------------------------------------------------

@app.route(route="email/drafts/{draft_id}", methods=["DELETE"])
def delete_draft(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a draft response."""
    draft_id = req.route_params.get("draft_id", "")
    message_id = req.params.get("message_id", "")
    if not draft_id:
        return _error("draft_id is required", 400)

    store = get_store()
    store.delete_draft(draft_id, message_id)

    return func.HttpResponse(
        body=json.dumps({"success": True}),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# POST /api/documents/classify
# ---------------------------------------------------------------------------

@app.route(route="documents/classify", methods=["POST"])
def classify_doc(req: func.HttpRequest) -> func.HttpResponse:
    """
    Classify a document attachment.

    Request body:
    {
      "filename": "Invoice_HES_March.pdf",
      "content_text": "<optional extracted text>",
      "source": "email",
      "source_detail": "msg-123"
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON", 400)

    filename = body.get("filename", "")
    if not filename:
        return _error("'filename' is required", 400)

    content_text = body.get("content_text")
    ai_response = body.get("ai_response")

    # Run classification
    classification = classify_document(filename, content_text, ai_response)

    # If low confidence and no AI response, try Azure OpenAI
    if classification.confidence < 0.85 and not ai_response:
        oai = get_openai_client()
        if oai.is_available:
            prompt = build_classification_prompt(filename, content_text or "")
            ai_resp = oai.classify_document(prompt)
            if ai_resp:
                classification = classify_document(filename, content_text, ai_resp)

    # Generate filing recommendation
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "pdf"
    filing = recommend_filing(classification, filename, ext)

    # Persist
    doc_data = {
        "document_id": body.get("document_id"),
        "filename": filename,
        "source": body.get("source", "upload"),
        "source_detail": body.get("source_detail", ""),
        "classification": serialize_classification_result(classification),
        "filing": serialize_filing_recommendation(filing),
    }
    store = get_store()
    store.save_document(doc_data)

    return func.HttpResponse(
        body=json.dumps({
            "success": True,
            "classification": serialize_classification_result(classification),
            "filing": serialize_filing_recommendation(filing),
        }),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# POST /api/documents/correct
# ---------------------------------------------------------------------------

@app.route(route="documents/correct", methods=["POST"])
def correct_classification(req: func.HttpRequest) -> func.HttpResponse:
    """
    Log a user correction to a document classification.

    Request body:
    {
      "document_id": "...",
      "original_type": "contract",
      "corrected_type": "amendment",
      "original_path": "01_CORPORATE/Legal/Contracts",
      "corrected_path": "01_CORPORATE/Legal/Amendments",
      "notes": "This was actually an amendment to the MSA"
    }
    """
    try:
        body = req.get_json()
    except ValueError:
        return _error("Invalid JSON", 400)

    document_id = body.get("document_id", "")
    if not document_id:
        return _error("'document_id' is required", 400)

    try:
        original_type = DocumentType(body.get("original_type", "unknown"))
        corrected_type = DocumentType(body.get("corrected_type", "unknown"))
    except ValueError:
        return _error("Invalid document type", 400)

    entry = _correction_store.log_correction(
        document_id=document_id,
        original_type=original_type,
        corrected_type=corrected_type,
        original_path=body.get("original_path", ""),
        corrected_path=body.get("corrected_path", ""),
        notes=body.get("notes", ""),
    )

    # Persist to Cosmos DB
    store = get_store()
    store.save_correction({
        "correction_id": entry.correction_id,
        "document_id": entry.document_id,
        "original_type": entry.original_type.value,
        "corrected_type": entry.corrected_type.value,
        "original_path": entry.original_path,
        "corrected_path": entry.corrected_path,
        "corrected_at": entry.corrected_at.isoformat(),
        "notes": entry.notes,
    })

    return func.HttpResponse(
        body=json.dumps({
            "success": True,
            "correction_id": entry.correction_id,
        }),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# GET /api/triage/history
# ---------------------------------------------------------------------------

@app.route(route="triage/history", methods=["GET"])
def triage_history(req: func.HttpRequest) -> func.HttpResponse:
    """Query triage result history from Cosmos DB."""
    date_filter = req.params.get("date")
    limit = int(req.params.get("limit", "50"))

    store = get_store()
    results = store.query_triage_results(partition_date=date_filter, limit=limit)

    return func.HttpResponse(
        body=json.dumps({"success": True, "results": results, "count": len(results)}),
        mimetype="application/json",
        status_code=200,
    )


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    store = get_store()
    oai = get_openai_client()

    return func.HttpResponse(
        body=json.dumps({
            "status": "healthy",
            "service": "email-intelligence",
            "version": "2.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "cosmos_connected": store.is_connected,
            "openai_available": oai.is_available,
        }),
        mimetype="application/json",
        status_code=200,
    )


def _error(message: str, status_code: int) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps({"success": False, "error": message}),
        mimetype="application/json",
        status_code=status_code,
    )
