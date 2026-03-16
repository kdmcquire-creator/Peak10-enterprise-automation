"""
4-Pass Deterministic Allocation Engine.

The algorithm allocates a finite AP budget across invoices in four
sequential passes, each with distinct rules:

  Pass 1 — Critical Obligations (Priority 1)
    Fully fund all CRITICAL invoices. These are non-negotiable (royalty
    owners, regulatory, lien holders). If the budget cannot cover them
    all, allocate by due-date (earliest first) and flag the shortfall.

  Pass 2 — High-Priority Due Soon (Priority 2, due within 15 days)
    Allocate remaining budget to HIGH-priority invoices due within
    15 days, ordered by due date ascending.

  Pass 3 — Standard Fill (Priority 2-3, all remaining)
    Allocate remaining budget across STANDARD and remaining HIGH
    invoices, ordered by priority then due date.

  Pass 4 — Partial & Deferral Sweep
    For any invoices that could not be fully funded in passes 1-3,
    attempt partial allocation (minimum 25% of invoice or skip).
    Everything else is deferred to next cycle.

All math uses Decimal to avoid floating-point drift in financial calcs.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Optional

from .models import (
    AllocationLineItem,
    AllocationResult,
    AllocationRunStatus,
    BudgetConstraint,
    Invoice,
    InvoiceStatus,
    VendorPriority,
    currency,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PARTIAL_ALLOCATION_MIN_PCT = Decimal("0.25")  # 25 %
HIGH_PRIORITY_DUE_WINDOW_DAYS = 15


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AllocationEngine:
    """Executes the 4-pass deterministic allocation algorithm."""

    def __init__(
        self,
        budget: BudgetConstraint,
        invoices: list[Invoice],
        *,
        partial_min_pct: Decimal = PARTIAL_ALLOCATION_MIN_PCT,
        high_due_window_days: int = HIGH_PRIORITY_DUE_WINDOW_DAYS,
    ):
        self.budget = deepcopy(budget)
        self.invoices = deepcopy(invoices)
        self.partial_min_pct = partial_min_pct
        self.high_due_window_days = high_due_window_days

        self._remaining_budget = self.budget.allocatable_budget
        self._allocated_items: list[AllocationLineItem] = []
        self._deferred_items: list[AllocationLineItem] = []
        self._pass_summaries: list[dict] = []

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self) -> AllocationResult:
        """Execute all four passes and return the result."""
        self._pass1_critical()
        self._pass2_high_due_soon()
        self._pass3_standard_fill()
        self._pass4_partial_and_defer()

        total_allocated = sum(
            (i.allocated_amount for i in self._allocated_items), Decimal("0.00")
        )
        total_deferred = sum(
            (i.invoice_amount - i.allocated_amount for i in self._deferred_items),
            Decimal("0.00"),
        )

        return AllocationResult(
            status=AllocationRunStatus.PENDING_APPROVAL,
            budget=self.budget,
            total_allocated=currency(total_allocated),
            total_deferred=currency(total_deferred),
            budget_remaining=currency(self._remaining_budget),
            line_items=self._allocated_items,
            deferred_items=self._deferred_items,
            pass_summaries=self._pass_summaries,
        )

    # ------------------------------------------------------------------
    # Pass 1 — Critical obligations
    # ------------------------------------------------------------------

    def _pass1_critical(self) -> None:
        candidates = self._pending_invoices(priority=VendorPriority.CRITICAL)
        candidates.sort(key=lambda inv: inv.due_date)

        pass_total = Decimal("0.00")
        shortfall = Decimal("0.00")

        for inv in candidates:
            needed = inv.amount_remaining
            if needed <= self._remaining_budget:
                self._allocate(inv, needed, pass_num=1)
                pass_total += needed
            else:
                # Allocate what we can, flag shortfall
                if self._remaining_budget > Decimal("0.00"):
                    allocated = self._remaining_budget
                    shortfall += needed - allocated
                    self._allocate(
                        inv, allocated, pass_num=1, partial=True,
                        notes=f"CRITICAL shortfall: {currency(needed - allocated)}"
                    )
                    pass_total += allocated
                else:
                    shortfall += needed
                    self._defer(inv, pass_num=1, notes="CRITICAL unfunded — budget exhausted")

        self._pass_summaries.append({
            "pass": 1,
            "name": "Critical Obligations",
            "allocated": str(currency(pass_total)),
            "shortfall": str(currency(shortfall)),
            "budget_remaining": str(currency(self._remaining_budget)),
        })

    # ------------------------------------------------------------------
    # Pass 2 — High-priority due soon
    # ------------------------------------------------------------------

    def _pass2_high_due_soon(self) -> None:
        candidates = [
            inv for inv in self._pending_invoices(priority=VendorPriority.HIGH)
            if inv.days_until_due <= self.high_due_window_days
        ]
        candidates.sort(key=lambda inv: inv.due_date)

        pass_total = Decimal("0.00")
        for inv in candidates:
            needed = inv.amount_remaining
            if needed <= self._remaining_budget:
                self._allocate(inv, needed, pass_num=2)
                pass_total += needed
            # else: leave for pass 3/4

        self._pass_summaries.append({
            "pass": 2,
            "name": "High-Priority Due Soon",
            "allocated": str(currency(pass_total)),
            "budget_remaining": str(currency(self._remaining_budget)),
        })

    # ------------------------------------------------------------------
    # Pass 3 — Standard fill
    # ------------------------------------------------------------------

    def _pass3_standard_fill(self) -> None:
        candidates = [
            inv for inv in self.invoices
            if inv.status == InvoiceStatus.PENDING
            and inv.vendor_priority in (VendorPriority.HIGH, VendorPriority.STANDARD)
        ]
        candidates.sort(key=lambda inv: (inv.vendor_priority, inv.due_date))

        pass_total = Decimal("0.00")
        for inv in candidates:
            needed = inv.amount_remaining
            if needed <= self._remaining_budget:
                self._allocate(inv, needed, pass_num=3)
                pass_total += needed

        self._pass_summaries.append({
            "pass": 3,
            "name": "Standard Fill",
            "allocated": str(currency(pass_total)),
            "budget_remaining": str(currency(self._remaining_budget)),
        })

    # ------------------------------------------------------------------
    # Pass 4 — Partial allocation & deferral sweep
    # ------------------------------------------------------------------

    def _pass4_partial_and_defer(self) -> None:
        remaining_invoices = [
            inv for inv in self.invoices
            if inv.status == InvoiceStatus.PENDING
        ]
        remaining_invoices.sort(key=lambda inv: (inv.vendor_priority, inv.due_date))

        pass_total = Decimal("0.00")
        for inv in remaining_invoices:
            needed = inv.amount_remaining
            min_partial = currency(inv.amount_due * self.partial_min_pct)

            if needed <= self._remaining_budget:
                # Can fully fund in sweep
                self._allocate(inv, needed, pass_num=4)
                pass_total += needed
            elif self._remaining_budget >= min_partial:
                # Partial allocation meets minimum threshold
                allocated = self._remaining_budget
                self._allocate(
                    inv, allocated, pass_num=4, partial=True,
                    notes=f"Partial: {allocated}/{needed}"
                )
                pass_total += allocated
            else:
                # Defer entirely
                self._defer(inv, pass_num=4, notes="Deferred to next cycle")

        self._pass_summaries.append({
            "pass": 4,
            "name": "Partial & Deferral Sweep",
            "allocated": str(currency(pass_total)),
            "deferred_count": len(self._deferred_items),
            "budget_remaining": str(currency(self._remaining_budget)),
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pending_invoices(
        self, priority: Optional[VendorPriority] = None
    ) -> list[Invoice]:
        return [
            inv for inv in self.invoices
            if inv.status == InvoiceStatus.PENDING
            and (priority is None or inv.vendor_priority == priority)
        ]

    def _allocate(
        self,
        inv: Invoice,
        amount: Decimal,
        pass_num: int,
        partial: bool = False,
        notes: str = "",
    ) -> None:
        amount = currency(amount)
        inv.amount_allocated = currency(inv.amount_allocated + amount)
        inv.status = (
            InvoiceStatus.PARTIALLY_ALLOCATED if partial
            else InvoiceStatus.ALLOCATED
        )
        self._remaining_budget = currency(self._remaining_budget - amount)

        self._allocated_items.append(AllocationLineItem(
            invoice_id=inv.invoice_id,
            vendor_id=inv.vendor_id,
            vendor_name=inv.vendor_name,
            vendor_priority=inv.vendor_priority,
            invoice_amount=inv.amount_due,
            allocated_amount=amount,
            allocation_pass=pass_num,
            is_partial=partial,
            notes=notes,
        ))

    def _defer(self, inv: Invoice, pass_num: int, notes: str = "") -> None:
        inv.status = InvoiceStatus.DEFERRED
        self._deferred_items.append(AllocationLineItem(
            invoice_id=inv.invoice_id,
            vendor_id=inv.vendor_id,
            vendor_name=inv.vendor_name,
            vendor_priority=inv.vendor_priority,
            invoice_amount=inv.amount_due,
            allocated_amount=inv.amount_allocated,
            allocation_pass=pass_num,
            is_partial=False,
            notes=notes,
        ))
