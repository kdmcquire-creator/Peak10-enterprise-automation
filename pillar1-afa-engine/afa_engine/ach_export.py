"""
ACH / NACHA export utilities.

Generates a simplified NACHA-format file from an approved AllocationResult,
grouped by vendor for bank upload.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from .models import (
    ACHRecord,
    AllocationLineItem,
    AllocationResult,
    AllocationRunStatus,
    Vendor,
    currency,
)


class ACHExportError(Exception):
    pass


def build_ach_records(
    result: AllocationResult,
    vendors: dict[str, Vendor],
) -> list[ACHRecord]:
    """
    Build ACH payment records from an approved allocation run.

    Consolidates multiple invoices per vendor into a single ACH payment.
    """
    if result.status != AllocationRunStatus.APPROVED:
        raise ACHExportError(
            f"Cannot export: allocation run is '{result.status.value}', "
            f"must be 'approved'"
        )

    # Group line items by vendor
    by_vendor: dict[str, list[AllocationLineItem]] = defaultdict(list)
    for item in result.line_items:
        by_vendor[item.vendor_id].append(item)

    records: list[ACHRecord] = []
    for vendor_id, items in by_vendor.items():
        vendor = vendors.get(vendor_id)
        if vendor is None:
            raise ACHExportError(f"Vendor '{vendor_id}' not found in vendor registry")
        if not vendor.ach_routing_number or not vendor.ach_account_number:
            raise ACHExportError(
                f"Vendor '{vendor.name}' is missing ACH routing/account info"
            )

        total = sum((item.allocated_amount for item in items), Decimal("0.00"))
        records.append(ACHRecord(
            vendor_name=vendor.name,
            routing_number=vendor.ach_routing_number,
            account_number=vendor.ach_account_number,
            amount=currency(total),
            invoice_ids=[item.invoice_id for item in items],
            payment_date=date.today(),
        ))

    return records


def render_nacha_flat(records: list[ACHRecord], company_name: str = "PEAK 10 ENERGY") -> str:
    """
    Render ACH records as a simplified NACHA-like flat text file.

    This is a simplified format — production NACHA requires specific
    record types (1/5/6/8/9) with fixed-width fields. This produces
    a human-readable approximation suitable for bank upload portals
    that accept CSV-like formats.
    """
    lines: list[str] = []
    lines.append(f"COMPANY: {company_name}")
    lines.append(f"DATE: {date.today().isoformat()}")
    lines.append(f"RECORD_COUNT: {len(records)}")
    total = sum((r.amount for r in records), Decimal("0.00"))
    lines.append(f"TOTAL_AMOUNT: {total}")
    lines.append("---")
    lines.append("VENDOR|ROUTING|ACCOUNT|AMOUNT|INVOICE_COUNT")

    for r in records:
        masked_acct = "****" + r.account_number[-4:] if len(r.account_number) >= 4 else r.account_number
        lines.append(
            f"{r.vendor_name}|{r.routing_number}|{masked_acct}|{r.amount}|{len(r.invoice_ids)}"
        )

    return "\n".join(lines)
