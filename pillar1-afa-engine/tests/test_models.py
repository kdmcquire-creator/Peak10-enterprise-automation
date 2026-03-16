"""Tests for data models."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from afa_engine.models import (
    BudgetConstraint,
    Invoice,
    InvoiceStatus,
    VendorPriority,
    currency,
)


class TestCurrency:
    def test_rounds_half_up(self):
        assert currency("10.005") == Decimal("10.01")
        assert currency("10.004") == Decimal("10.00")
        assert currency(10.1) == Decimal("10.10")

    def test_from_float(self):
        assert currency(99.99) == Decimal("99.99")


class TestInvoice:
    def test_amount_remaining(self):
        inv = Invoice(amount_due=Decimal("1000.00"), amount_allocated=Decimal("300.00"))
        assert inv.amount_remaining == Decimal("700.00")

    def test_is_fully_allocated(self):
        inv = Invoice(amount_due=Decimal("500.00"), amount_allocated=Decimal("500.00"))
        assert inv.is_fully_allocated is True

    def test_days_until_due(self):
        inv = Invoice(due_date=date.today() + timedelta(days=10))
        assert inv.days_until_due == 10


class TestBudgetConstraint:
    def test_allocatable_budget(self):
        b = BudgetConstraint(
            total_budget=Decimal("100000.00"),
            reserved_amount=Decimal("15000.00"),
        )
        assert b.allocatable_budget == Decimal("85000.00")
