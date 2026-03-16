"""JSON serialization for Expense Hub models."""

from __future__ import annotations

from typing import Any

from .models import (
    BankTransaction,
    ExpenseBucket,
    ExpenseClaim,
    Pillar1InvoicePayload,
)


def serialize_transaction(t: BankTransaction) -> dict[str, Any]:
    """Serialize a transaction — for internal use only, NEVER sent outside the wall."""
    return {
        "transaction_id": t.transaction_id,
        "date": t.date.isoformat(),
        "merchant_name": t.merchant_name,
        "amount": str(t.amount),
        "category": t.category,
        "bucket": t.bucket.value,
        "classification_rule": t.classification_rule,
        "classification_confidence": t.classification_confidence,
        "status": t.status.value,
        "has_receipt": t.receipt_ref is not None,
    }


def serialize_expense_claim(c: ExpenseClaim) -> dict[str, Any]:
    """Serialize a claim — safe to send across the wall."""
    return {
        "claim_id": c.claim_id,
        "employee_name": c.employee_name,
        "vendor_name": c.vendor_name,
        "expense_date": c.expense_date.isoformat(),
        "amount": str(c.amount),
        "description": c.description,
        "receipt_ref": c.receipt_ref,
        "bucket": c.bucket.value,
        "status": c.status.value,
        "created_at": c.created_at.isoformat(),
    }


def serialize_pillar1_payload(p: Pillar1InvoicePayload) -> dict[str, Any]:
    return {
        "vendor_id": p.vendor_id,
        "vendor_name": p.vendor_name,
        "amount_due": p.amount_due,
        "due_date": p.due_date,
        "description": p.description,
        "receipt_ref": p.receipt_ref,
        "source": p.source,
    }
