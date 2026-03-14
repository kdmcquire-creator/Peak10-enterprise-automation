"""Tests for ACH export and NACHA rendering."""

from __future__ import annotations

from decimal import Decimal

import pytest

from afa_engine.ach_export import build_ach_records, render_nacha_flat, ACHExportError
from afa_engine.models import (
    AllocationLineItem,
    AllocationResult,
    AllocationRunStatus,
    BudgetConstraint,
    Vendor,
    VendorPriority,
)


def make_approved_result(line_items: list[AllocationLineItem]) -> AllocationResult:
    return AllocationResult(
        status=AllocationRunStatus.APPROVED,
        budget=BudgetConstraint(total_budget=Decimal("50000.00")),
        total_allocated=sum(
            (i.allocated_amount for i in line_items), Decimal("0.00")
        ),
        line_items=line_items,
    )


def make_vendor(
    vendor_id: str, name: str,
    routing: str = "021000021", account: str = "123456789"
) -> Vendor:
    return Vendor(
        vendor_id=vendor_id,
        name=name,
        ach_routing_number=routing,
        ach_account_number=account,
    )


class TestBuildACHRecords:
    def test_consolidates_invoices_per_vendor(self):
        items = [
            AllocationLineItem(
                invoice_id="inv-1", vendor_id="v1", vendor_name="Vendor A",
                allocated_amount=Decimal("5000.00"),
            ),
            AllocationLineItem(
                invoice_id="inv-2", vendor_id="v1", vendor_name="Vendor A",
                allocated_amount=Decimal("3000.00"),
            ),
        ]
        result = make_approved_result(items)
        vendors = {"v1": make_vendor("v1", "Vendor A")}

        records = build_ach_records(result, vendors)
        assert len(records) == 1
        assert records[0].amount == Decimal("8000.00")
        assert len(records[0].invoice_ids) == 2

    def test_rejects_non_approved_run(self):
        result = AllocationResult(status=AllocationRunStatus.DRAFT)
        with pytest.raises(ACHExportError, match="must be 'approved'"):
            build_ach_records(result, {})

    def test_rejects_missing_vendor(self):
        items = [
            AllocationLineItem(
                invoice_id="inv-1", vendor_id="v-missing",
                allocated_amount=Decimal("1000.00"),
            ),
        ]
        result = make_approved_result(items)
        with pytest.raises(ACHExportError, match="not found"):
            build_ach_records(result, {})

    def test_rejects_vendor_without_ach_info(self):
        items = [
            AllocationLineItem(
                invoice_id="inv-1", vendor_id="v1",
                allocated_amount=Decimal("1000.00"),
            ),
        ]
        result = make_approved_result(items)
        vendors = {"v1": Vendor(vendor_id="v1", name="No ACH")}

        with pytest.raises(ACHExportError, match="missing ACH"):
            build_ach_records(result, vendors)


class TestNACHARender:
    def test_renders_flat_file(self):
        items = [
            AllocationLineItem(
                invoice_id="inv-1", vendor_id="v1", vendor_name="Vendor A",
                allocated_amount=Decimal("5000.00"),
            ),
        ]
        result = make_approved_result(items)
        vendors = {"v1": make_vendor("v1", "Vendor A")}
        records = build_ach_records(result, vendors)

        text = render_nacha_flat(records)
        assert "PEAK 10 ENERGY" in text
        assert "Vendor A" in text
        assert "****6789" in text  # masked account
        assert "5000.00" in text
