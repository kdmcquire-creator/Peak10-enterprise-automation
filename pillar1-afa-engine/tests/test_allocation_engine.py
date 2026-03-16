"""
Comprehensive tests for the 4-pass deterministic allocation engine.

Tests cover:
  - Each pass in isolation
  - Full 4-pass runs with mixed priorities
  - Edge cases: zero budget, single invoice, exact-fit budget
  - Partial allocation threshold logic
  - Budget exhaustion across passes
  - Deterministic ordering (same inputs → same outputs)
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from afa_engine.allocation_engine import AllocationEngine
from afa_engine.models import (
    AllocationRunStatus,
    BudgetConstraint,
    Invoice,
    InvoiceStatus,
    VendorPriority,
    currency,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_invoice(
    vendor_name: str = "Test Vendor",
    amount: str = "1000.00",
    priority: VendorPriority = VendorPriority.STANDARD,
    due_date: date | None = None,
    source: str = "manual",
) -> Invoice:
    return Invoice(
        vendor_id=f"v-{vendor_name.lower().replace(' ', '-')}",
        vendor_name=vendor_name,
        vendor_priority=priority,
        amount_due=Decimal(amount),
        due_date=due_date or date.today(),
        source=source,
    )


def make_budget(total: str = "100000.00", reserved: str = "0.00") -> BudgetConstraint:
    return BudgetConstraint(
        total_budget=Decimal(total),
        reserved_amount=Decimal(reserved),
    )


# ---------------------------------------------------------------------------
# Pass 1 — Critical obligations
# ---------------------------------------------------------------------------

class TestPass1Critical:
    def test_critical_invoices_fully_funded(self):
        budget = make_budget("50000.00")
        invoices = [
            make_invoice("Royalty Owner A", "15000.00", VendorPriority.CRITICAL),
            make_invoice("Tax Authority", "10000.00", VendorPriority.CRITICAL),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("25000.00")
        assert len(result.line_items) == 2
        assert all(i.allocation_pass == 1 for i in result.line_items)

    def test_critical_shortfall_partial(self):
        budget = make_budget("8000.00")
        invoices = [
            make_invoice("Royalty Owner A", "5000.00", VendorPriority.CRITICAL),
            make_invoice("Tax Authority", "10000.00", VendorPriority.CRITICAL),
        ]
        result = AllocationEngine(budget, invoices).run()

        # First critical is fully funded (5000), second gets remaining 3000
        critical_items = [i for i in result.line_items if i.allocation_pass == 1]
        assert len(critical_items) == 2
        assert critical_items[0].allocated_amount == Decimal("5000.00")
        assert critical_items[1].allocated_amount == Decimal("3000.00")
        assert critical_items[1].is_partial is True

    def test_critical_ordered_by_due_date(self):
        budget = make_budget("10000.00")
        invoices = [
            make_invoice("Later", "5000.00", VendorPriority.CRITICAL,
                         due_date=date.today() + timedelta(days=30)),
            make_invoice("Sooner", "5000.00", VendorPriority.CRITICAL,
                         due_date=date.today() + timedelta(days=5)),
        ]
        result = AllocationEngine(budget, invoices).run()

        pass1 = [i for i in result.line_items if i.allocation_pass == 1]
        assert pass1[0].vendor_name == "Sooner"
        assert pass1[1].vendor_name == "Later"


# ---------------------------------------------------------------------------
# Pass 2 — High-priority due soon
# ---------------------------------------------------------------------------

class TestPass2HighDueSoon:
    def test_high_due_within_window_allocated(self):
        budget = make_budget("50000.00")
        invoices = [
            make_invoice("Rig Contractor", "10000.00", VendorPriority.HIGH,
                         due_date=date.today() + timedelta(days=7)),
        ]
        result = AllocationEngine(budget, invoices).run()

        pass2 = [i for i in result.line_items if i.allocation_pass == 2]
        assert len(pass2) == 1
        assert pass2[0].allocated_amount == Decimal("10000.00")

    def test_high_due_beyond_window_skipped_in_pass2(self):
        budget = make_budget("50000.00")
        invoices = [
            make_invoice("Rig Contractor", "10000.00", VendorPriority.HIGH,
                         due_date=date.today() + timedelta(days=30)),
        ]
        result = AllocationEngine(budget, invoices).run()

        pass2 = [i for i in result.line_items if i.allocation_pass == 2]
        assert len(pass2) == 0  # should be picked up in pass 3 instead


# ---------------------------------------------------------------------------
# Pass 3 — Standard fill
# ---------------------------------------------------------------------------

class TestPass3StandardFill:
    def test_standard_invoices_funded_after_critical(self):
        budget = make_budget("30000.00")
        invoices = [
            make_invoice("Critical Co", "10000.00", VendorPriority.CRITICAL),
            make_invoice("Standard Co", "15000.00", VendorPriority.STANDARD),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("25000.00")
        pass3 = [i for i in result.line_items if i.allocation_pass == 3]
        assert len(pass3) == 1
        assert pass3[0].vendor_name == "Standard Co"

    def test_high_not_due_soon_picked_up_in_pass3(self):
        budget = make_budget("50000.00")
        invoices = [
            make_invoice("Rig Contractor", "10000.00", VendorPriority.HIGH,
                         due_date=date.today() + timedelta(days=60)),
        ]
        result = AllocationEngine(budget, invoices).run()

        pass3 = [i for i in result.line_items if i.allocation_pass == 3]
        assert len(pass3) == 1


# ---------------------------------------------------------------------------
# Pass 4 — Partial & deferral
# ---------------------------------------------------------------------------

class TestPass4PartialAndDefer:
    def test_partial_allocation_above_threshold(self):
        budget = make_budget("12000.00")
        invoices = [
            make_invoice("Critical Co", "10000.00", VendorPriority.CRITICAL),
            # After critical: 2000 remaining. Deferrable invoice = 4000.
            # 25% of 4000 = 1000 <= 2000, so partial is allowed.
            make_invoice("Low Co", "4000.00", VendorPriority.DEFERRABLE),
        ]
        result = AllocationEngine(budget, invoices).run()

        pass4 = [i for i in result.line_items if i.allocation_pass == 4]
        assert len(pass4) == 1
        assert pass4[0].is_partial is True
        assert pass4[0].allocated_amount == Decimal("2000.00")

    def test_deferral_when_below_threshold(self):
        budget = make_budget("10500.00")
        invoices = [
            make_invoice("Critical Co", "10000.00", VendorPriority.CRITICAL),
            # After critical: 500 remaining. 25% of 10000 = 2500 > 500.
            make_invoice("Defer Me", "10000.00", VendorPriority.DEFERRABLE),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert len(result.deferred_items) == 1
        assert result.deferred_items[0].vendor_name == "Defer Me"

    def test_deferrable_invoices_not_in_earlier_passes(self):
        budget = make_budget("50000.00")
        invoices = [
            make_invoice("Low Priority", "5000.00", VendorPriority.DEFERRABLE),
        ]
        result = AllocationEngine(budget, invoices).run()

        # Deferrable invoices only get picked up in pass 4
        pass4 = [i for i in result.line_items if i.allocation_pass == 4]
        assert len(pass4) == 1


# ---------------------------------------------------------------------------
# Full run scenarios
# ---------------------------------------------------------------------------

class TestFullRun:
    def test_mixed_priorities_full_budget(self):
        budget = make_budget("100000.00")
        invoices = [
            make_invoice("Royalty Owner", "20000.00", VendorPriority.CRITICAL),
            make_invoice("Rig Co", "15000.00", VendorPriority.HIGH,
                         due_date=date.today() + timedelta(days=5)),
            make_invoice("Supplier A", "25000.00", VendorPriority.STANDARD),
            make_invoice("Supplier B", "10000.00", VendorPriority.STANDARD),
            make_invoice("Misc Vendor", "5000.00", VendorPriority.DEFERRABLE),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("75000.00")
        assert result.budget_remaining == Decimal("25000.00")
        assert result.status == AllocationRunStatus.PENDING_APPROVAL
        assert len(result.deferred_items) == 0
        assert len(result.pass_summaries) == 4

    def test_zero_budget(self):
        budget = make_budget("0.00")
        invoices = [
            make_invoice("Critical Co", "5000.00", VendorPriority.CRITICAL),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("0.00")
        assert len(result.deferred_items) == 1

    def test_exact_fit_budget(self):
        budget = make_budget("10000.00")
        invoices = [
            make_invoice("Vendor A", "5000.00", VendorPriority.CRITICAL),
            make_invoice("Vendor B", "5000.00", VendorPriority.HIGH,
                         due_date=date.today() + timedelta(days=3)),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("10000.00")
        assert result.budget_remaining == Decimal("0.00")
        assert len(result.deferred_items) == 0

    def test_single_invoice(self):
        budget = make_budget("50000.00")
        invoices = [make_invoice("Solo Vendor", "30000.00", VendorPriority.STANDARD)]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("30000.00")
        assert len(result.line_items) == 1

    def test_reserved_amount_reduces_allocatable(self):
        budget = make_budget("50000.00", reserved="45000.00")
        invoices = [
            make_invoice("Vendor", "10000.00", VendorPriority.STANDARD),
        ]
        result = AllocationEngine(budget, invoices).run()

        # Only 5000 allocatable, so 10000 invoice gets partial or deferred
        assert result.total_allocated <= Decimal("5000.00")

    def test_pillar4_expense_source_accepted(self):
        budget = make_budget("50000.00")
        invoices = [
            make_invoice("Employee Expense", "500.00", VendorPriority.STANDARD,
                         source="pillar4_expense"),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.total_allocated == Decimal("500.00")
        assert result.line_items[0].vendor_name == "Employee Expense"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self):
        budget = make_budget("30000.00")
        invoices = [
            make_invoice("Vendor A", "10000.00", VendorPriority.CRITICAL),
            make_invoice("Vendor B", "8000.00", VendorPriority.HIGH,
                         due_date=date.today() + timedelta(days=5)),
            make_invoice("Vendor C", "15000.00", VendorPriority.STANDARD),
            make_invoice("Vendor D", "12000.00", VendorPriority.DEFERRABLE),
        ]

        r1 = AllocationEngine(budget, invoices).run()
        r2 = AllocationEngine(budget, invoices).run()

        assert r1.total_allocated == r2.total_allocated
        assert r1.budget_remaining == r2.budget_remaining
        assert len(r1.line_items) == len(r2.line_items)
        assert len(r1.deferred_items) == len(r2.deferred_items)

        for a, b in zip(r1.line_items, r2.line_items):
            assert a.vendor_name == b.vendor_name
            assert a.allocated_amount == b.allocated_amount
            assert a.allocation_pass == b.allocation_pass


# ---------------------------------------------------------------------------
# Utilization
# ---------------------------------------------------------------------------

class TestUtilization:
    def test_utilization_pct(self):
        budget = make_budget("10000.00")
        invoices = [
            make_invoice("Vendor", "7500.00", VendorPriority.STANDARD),
        ]
        result = AllocationEngine(budget, invoices).run()

        assert result.utilization_pct == Decimal("75.00")
