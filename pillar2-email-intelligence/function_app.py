"""
Azure Functions HTTP triggers for the Email Intelligence system.

Endpoints:
  POST /api/email/triage         — Triage an inbound email
  POST /api/email/draft-reply    — Generate a draft reply (AI)
  GET  /api/health               — Health check
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import azure.functions as func

from email_intel.models import EmailMessage
from email_intel.triage import (
    build_triage_prompt,
    route_attachments,
    triage_email,
)
from email_intel.serialization import (
    serialize_attachment_routing,
    serialize_triage_result,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger("email-intel")


# ---------------------------------------------------------------------------
# POST /api/email/triage
# ---------------------------------------------------------------------------

@app.route(route="email/triage", methods=["POST"])
def triage(req: func.HttpRequest) -> func.HttpResponse:
    """
    Triage an inbound email.

    Request body:
    {
      "subject": "...",
      "sender": "john@example.com",
      "sender_name": "John Doe",
      "body_preview": "...",
      "body_text": "...",
      "has_attachments": true,
      "attachment_names": ["invoice.pdf"],
      "ai_response": {<optional>}
    }
    """
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

    ai_response = body.get("ai_response")
    result = triage_email(email, ai_response=ai_response)

    # Attachment routing details
    att_routing = []
    if email.has_attachments:
        att_routing = [
            serialize_attachment_routing(r)
            for r in route_attachments(email.attachment_names)
        ]

    # If AI is needed, provide the prompt
    needs_ai = result.confidence < 0.85 and not ai_response
    ai_prompt = build_triage_prompt(email) if needs_ai else None

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
# GET /api/health
# ---------------------------------------------------------------------------

@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps({
            "status": "healthy",
            "service": "email-intelligence",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
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
