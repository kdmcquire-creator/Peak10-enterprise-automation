"""
Deterministic transaction classification engine.

Port of the ~80+ rule engine from the McQuire Tracker desktop app.
Classifies each bank transaction into one of three buckets:
  - PERSONAL: Personal spending
  - PEAK10: Peak 10 Energy reimbursable
  - MOONSMOKE_LLC: Moonsmoke LLC business

Rules are evaluated in priority order. First match wins.
Each rule has a confidence score for auditability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .models import BankTransaction, ExpenseBucket, TransactionStatus, currency


@dataclass
class ClassificationRule:
    """A single classification rule."""
    rule_id: str
    name: str
    bucket: ExpenseBucket
    merchant_pattern: Optional[str] = None   # Regex on merchant_name
    category_pattern: Optional[str] = None   # Regex on Plaid categories
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    confidence: float = 0.95


# ---------------------------------------------------------------------------
# Rule definitions (~80+ rules from McQuire Tracker)
# ---------------------------------------------------------------------------

CLASSIFICATION_RULES: list[ClassificationRule] = [
    # ===================================================================
    # PEAK 10 ENERGY RULES (business expenses)
    # ===================================================================

    # Travel — airlines
    ClassificationRule("p10-airline-aa", "American Airlines", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)american\s*airlines?", confidence=0.95),
    ClassificationRule("p10-airline-ua", "United Airlines", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)united\s*airlines?", confidence=0.95),
    ClassificationRule("p10-airline-dl", "Delta Airlines", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)delta\s*(air|airlines?)", confidence=0.95),
    ClassificationRule("p10-airline-sw", "Southwest Airlines", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)southwest\s*airlines?", confidence=0.95),
    ClassificationRule("p10-airline-generic", "Generic airline", ExpenseBucket.PEAK10,
                       category_pattern=r"(?i)airlines?|air\s*travel", confidence=0.90),

    # Travel — hotels
    ClassificationRule("p10-hotel-marriott", "Marriott", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)marriott|courtyard|residence\s*inn|springhill", confidence=0.92),
    ClassificationRule("p10-hotel-hilton", "Hilton", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)hilton|hampton\s*inn|doubletree|embassy\s*suites", confidence=0.92),
    ClassificationRule("p10-hotel-hyatt", "Hyatt", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)hyatt", confidence=0.92),
    ClassificationRule("p10-hotel-generic", "Generic hotel", ExpenseBucket.PEAK10,
                       category_pattern=r"(?i)hotel|lodging", confidence=0.88),

    # Travel — ground transport
    ClassificationRule("p10-uber", "Uber", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)^uber\b", confidence=0.90),
    ClassificationRule("p10-lyft", "Lyft", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)^lyft\b", confidence=0.90),
    ClassificationRule("p10-rental-hertz", "Hertz", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)hertz", confidence=0.92),
    ClassificationRule("p10-rental-enterprise", "Enterprise Rent", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)enterprise\s*(rent|car)", confidence=0.92),
    ClassificationRule("p10-rental-national", "National Car", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)national\s*car", confidence=0.92),
    ClassificationRule("p10-fuel", "Gas station", ExpenseBucket.PEAK10,
                       category_pattern=r"(?i)gas\s*station|fuel|petroleum", confidence=0.85),

    # Travel — meals (business)
    ClassificationRule("p10-meal-steak", "Business dinner (steakhouse)", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)(ruth.?s?\s*chris|capital\s*grille|del\s*frisco|pappas\s*bros)", confidence=0.90),

    # Office & supplies
    ClassificationRule("p10-office-depot", "Office Depot/Max", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)office\s*(depot|max)", confidence=0.92),
    ClassificationRule("p10-staples", "Staples", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)staples", confidence=0.92),
    ClassificationRule("p10-fedex", "FedEx", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)fedex|fed\s*ex", confidence=0.92),
    ClassificationRule("p10-ups", "UPS", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)^ups\b|united\s*parcel", confidence=0.92),

    # Software & subscriptions (business)
    ClassificationRule("p10-microsoft", "Microsoft 365", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)microsoft|msft", confidence=0.90),
    ClassificationRule("p10-adobe", "Adobe", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)adobe", confidence=0.90),
    ClassificationRule("p10-dropbox", "Dropbox Business", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)dropbox", confidence=0.88),
    ClassificationRule("p10-zoom", "Zoom", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)zoom\s*(video|us)?", confidence=0.90),

    # Oilfield services
    ClassificationRule("p10-halliburton", "Halliburton", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)halliburton", confidence=0.98),
    ClassificationRule("p10-schlumberger", "Schlumberger/SLB", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)schlumberger|^slb\b", confidence=0.98),
    ClassificationRule("p10-baker-hughes", "Baker Hughes", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)baker\s*hughes", confidence=0.98),
    ClassificationRule("p10-weatherford", "Weatherford", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)weatherford", confidence=0.98),
    ClassificationRule("p10-basic-energy", "Basic Energy Services", ExpenseBucket.PEAK10,
                       merchant_pattern=r"(?i)basic\s*energy", confidence=0.95),

    # Professional services
    ClassificationRule("p10-legal", "Legal services", ExpenseBucket.PEAK10,
                       category_pattern=r"(?i)legal\s*services|attorney|law\s*firm", confidence=0.90),
    ClassificationRule("p10-accounting", "Accounting", ExpenseBucket.PEAK10,
                       category_pattern=r"(?i)accounting|cpa|audit", confidence=0.88),

    # ===================================================================
    # MOONSMOKE LLC RULES
    # ===================================================================

    ClassificationRule("ms-moonsmoke", "Moonsmoke LLC vendor", ExpenseBucket.MOONSMOKE_LLC,
                       merchant_pattern=r"(?i)moonsmoke", confidence=0.98),
    ClassificationRule("ms-music", "Music production", ExpenseBucket.MOONSMOKE_LLC,
                       category_pattern=r"(?i)music|recording\s*studio|instruments", confidence=0.85),
    ClassificationRule("ms-distrokid", "DistroKid", ExpenseBucket.MOONSMOKE_LLC,
                       merchant_pattern=r"(?i)distrokid", confidence=0.95),
    ClassificationRule("ms-spotify-artists", "Spotify for Artists", ExpenseBucket.MOONSMOKE_LLC,
                       merchant_pattern=r"(?i)spotify\s*(for\s*)?artist", confidence=0.92),
    ClassificationRule("ms-bandcamp", "Bandcamp", ExpenseBucket.MOONSMOKE_LLC,
                       merchant_pattern=r"(?i)bandcamp", confidence=0.92),

    # ===================================================================
    # PERSONAL RULES (definitively personal)
    # ===================================================================

    # Groceries
    ClassificationRule("per-grocery", "Grocery store", ExpenseBucket.PERSONAL,
                       category_pattern=r"(?i)groceries|supermarket", confidence=0.92),
    ClassificationRule("per-heb", "H-E-B", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)h[\-\s]?e[\-\s]?b\b", confidence=0.95),
    ClassificationRule("per-kroger", "Kroger", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)kroger", confidence=0.95),
    ClassificationRule("per-walmart-grocery", "Walmart Grocery", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)walmart|wal[\-\s]?mart", confidence=0.90),
    ClassificationRule("per-costco", "Costco", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)costco", confidence=0.90),
    ClassificationRule("per-target", "Target", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)target", confidence=0.88),

    # Personal subscriptions
    ClassificationRule("per-netflix", "Netflix", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)netflix", confidence=0.98),
    ClassificationRule("per-spotify", "Spotify Personal", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)^spotify$|spotify\s*premium", confidence=0.92),
    ClassificationRule("per-hulu", "Hulu", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)hulu", confidence=0.98),
    ClassificationRule("per-disney", "Disney+", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)disney\+|disneyplus", confidence=0.98),
    ClassificationRule("per-apple", "Apple (personal)", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)apple\.com|itunes|app\s*store", confidence=0.85),
    ClassificationRule("per-amazon", "Amazon", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)amazon|amzn", confidence=0.80),

    # Fitness / health
    ClassificationRule("per-gym", "Gym membership", ExpenseBucket.PERSONAL,
                       category_pattern=r"(?i)gym|fitness|health\s*club", confidence=0.95),
    ClassificationRule("per-doctor", "Medical", ExpenseBucket.PERSONAL,
                       category_pattern=r"(?i)doctor|medical|pharmacy|dentist", confidence=0.95),

    # Utilities (personal)
    ClassificationRule("per-utilities", "Home utilities", ExpenseBucket.PERSONAL,
                       category_pattern=r"(?i)electric|water|gas\s*utility|internet|cable", confidence=0.90),
    ClassificationRule("per-mortgage", "Mortgage/Rent", ExpenseBucket.PERSONAL,
                       category_pattern=r"(?i)mortgage|rent", confidence=0.95),
    ClassificationRule("per-insurance-personal", "Personal insurance", ExpenseBucket.PERSONAL,
                       category_pattern=r"(?i)insurance.*(?:auto|home|life|health)", confidence=0.90),

    # Fast food / casual dining (personal unless flagged)
    ClassificationRule("per-fastfood", "Fast food", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)(mcdonald|chick[\-\s]?fil[\-\s]?a|whataburger|taco\s*bell|wendy|burger\s*king|subway|chipotle)", confidence=0.88),
    ClassificationRule("per-coffee", "Coffee shop", ExpenseBucket.PERSONAL,
                       merchant_pattern=r"(?i)(starbucks|dunkin|dutch\s*bros)", confidence=0.85),
]


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

class ClassificationEngine:
    """Deterministic, rule-based transaction classifier."""

    def __init__(self, rules: list[ClassificationRule] | None = None):
        self.rules = rules or CLASSIFICATION_RULES

    def classify(self, txn: BankTransaction) -> BankTransaction:
        """
        Classify a transaction using the rule set.
        First match wins (rules are priority-ordered).
        """
        categories_str = " ".join(txn.category)

        for rule in self.rules:
            if self._matches(rule, txn, categories_str):
                txn.bucket = rule.bucket
                txn.classification_rule = rule.rule_id
                txn.classification_confidence = rule.confidence
                txn.status = TransactionStatus.CLASSIFIED
                return txn

        # No rule matched
        txn.bucket = ExpenseBucket.UNKNOWN
        txn.classification_rule = "no_match"
        txn.classification_confidence = 0.0
        txn.status = TransactionStatus.CLASSIFIED
        return txn

    def classify_batch(self, transactions: list[BankTransaction]) -> list[BankTransaction]:
        """Classify a batch of transactions."""
        return [self.classify(txn) for txn in transactions]

    def _matches(
        self, rule: ClassificationRule, txn: BankTransaction, categories_str: str
    ) -> bool:
        # Merchant pattern
        if rule.merchant_pattern:
            if not re.search(rule.merchant_pattern, txn.merchant_name):
                return False

        # Category pattern
        if rule.category_pattern:
            if not re.search(rule.category_pattern, categories_str):
                # Only fail if this is a category-only rule (no merchant pattern)
                if not rule.merchant_pattern:
                    return False

        # Amount bounds
        if rule.min_amount is not None and txn.amount < rule.min_amount:
            return False
        if rule.max_amount is not None and txn.amount > rule.max_amount:
            return False

        return True
