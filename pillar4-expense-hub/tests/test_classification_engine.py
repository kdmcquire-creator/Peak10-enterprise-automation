"""
Tests for the deterministic transaction classification engine.

Covers:
  - Peak 10 business expenses (airlines, hotels, rideshare, oilfield, software)
  - Moonsmoke LLC transactions
  - Personal transactions (groceries, streaming, fast food)
  - Unknown transactions
  - Batch classification
  - Rule priority ordering
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from expense_hub.classification_engine import ClassificationEngine
from expense_hub.models import BankTransaction, ExpenseBucket, TransactionStatus


def make_txn(merchant: str, amount: str = "50.00", category: list[str] | None = None) -> BankTransaction:
    return BankTransaction(
        merchant_name=merchant,
        amount=Decimal(amount),
        category=category or [],
    )


engine = ClassificationEngine()


# ---------------------------------------------------------------------------
# Peak 10 classifications
# ---------------------------------------------------------------------------

class TestPeak10Classification:
    @pytest.mark.parametrize("merchant", [
        "American Airlines", "AMERICAN AIRLINES", "United Airlines",
        "Delta Air Lines", "Southwest Airlines",
    ])
    def test_airlines(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "450.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    @pytest.mark.parametrize("merchant", [
        "Marriott Midland", "Courtyard by Marriott", "Hampton Inn",
        "Hilton Garden Inn", "Hyatt Place",
    ])
    def test_hotels(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "189.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    @pytest.mark.parametrize("merchant", ["Uber", "UBER TRIP", "Lyft"])
    def test_rideshare(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "35.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    @pytest.mark.parametrize("merchant", [
        "Hertz", "Enterprise Rent-A-Car", "National Car Rental",
    ])
    def test_car_rental(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "120.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    @pytest.mark.parametrize("merchant", [
        "Halliburton", "Schlumberger", "SLB", "Baker Hughes", "Weatherford",
    ])
    def test_oilfield_services(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "15000.00"))
        assert txn.bucket == ExpenseBucket.PEAK10
        assert txn.classification_confidence >= 0.95

    @pytest.mark.parametrize("merchant", [
        "Microsoft", "MSFT", "Adobe", "Zoom Video",
    ])
    def test_software(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "29.99"))
        assert txn.bucket == ExpenseBucket.PEAK10

    def test_office_supplies(self):
        txn = engine.classify(make_txn("Office Depot", "45.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    def test_shipping(self):
        txn = engine.classify(make_txn("FedEx", "25.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    def test_business_dinner(self):
        txn = engine.classify(make_txn("Ruth's Chris Steak House", "280.00"))
        assert txn.bucket == ExpenseBucket.PEAK10

    def test_fuel_by_category(self):
        txn = engine.classify(make_txn("Shell Station", "65.00", ["Gas Station", "Fuel"]))
        assert txn.bucket == ExpenseBucket.PEAK10

    def test_legal_by_category(self):
        txn = engine.classify(make_txn("Smith & Jones LLP", "5000.00", ["Legal Services"]))
        assert txn.bucket == ExpenseBucket.PEAK10


# ---------------------------------------------------------------------------
# Moonsmoke LLC classifications
# ---------------------------------------------------------------------------

class TestMoonsmokeClassification:
    def test_moonsmoke_vendor(self):
        txn = engine.classify(make_txn("Moonsmoke Productions"))
        assert txn.bucket == ExpenseBucket.MOONSMOKE_LLC

    def test_distrokid(self):
        txn = engine.classify(make_txn("DistroKid", "19.99"))
        assert txn.bucket == ExpenseBucket.MOONSMOKE_LLC

    def test_music_category(self):
        txn = engine.classify(make_txn("Guitar Center", "200.00", ["Music", "Instruments"]))
        assert txn.bucket == ExpenseBucket.MOONSMOKE_LLC


# ---------------------------------------------------------------------------
# Personal classifications
# ---------------------------------------------------------------------------

class TestPersonalClassification:
    @pytest.mark.parametrize("merchant", [
        "H-E-B", "HEB", "Kroger", "Walmart", "Costco", "Target",
    ])
    def test_groceries(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "120.00"))
        assert txn.bucket == ExpenseBucket.PERSONAL

    @pytest.mark.parametrize("merchant", [
        "Netflix", "Hulu", "Disney+", "DisneyPlus",
    ])
    def test_streaming(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "15.99"))
        assert txn.bucket == ExpenseBucket.PERSONAL

    @pytest.mark.parametrize("merchant", [
        "McDonald's", "Chick-fil-A", "Whataburger", "Chipotle",
        "Starbucks", "Dunkin",
    ])
    def test_fast_food(self, merchant: str):
        txn = engine.classify(make_txn(merchant, "12.50"))
        assert txn.bucket == ExpenseBucket.PERSONAL

    def test_gym_by_category(self):
        txn = engine.classify(make_txn("Planet Fitness", "25.00", ["Gym", "Fitness"]))
        assert txn.bucket == ExpenseBucket.PERSONAL

    def test_medical_by_category(self):
        txn = engine.classify(make_txn("Dr. Smith", "150.00", ["Doctor", "Medical"]))
        assert txn.bucket == ExpenseBucket.PERSONAL


# ---------------------------------------------------------------------------
# Unknown / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_unknown_merchant(self):
        txn = engine.classify(make_txn("Random Unknown Store XYZ"))
        assert txn.bucket == ExpenseBucket.UNKNOWN
        assert txn.status == TransactionStatus.CLASSIFIED

    def test_batch_classification(self):
        txns = [
            make_txn("American Airlines", "450.00"),
            make_txn("Netflix", "15.99"),
            make_txn("Moonsmoke Productions", "500.00"),
            make_txn("Unknown Place", "30.00"),
        ]
        results = engine.classify_batch(txns)
        assert results[0].bucket == ExpenseBucket.PEAK10
        assert results[1].bucket == ExpenseBucket.PERSONAL
        assert results[2].bucket == ExpenseBucket.MOONSMOKE_LLC
        assert results[3].bucket == ExpenseBucket.UNKNOWN

    def test_all_classified_get_status(self):
        txn = engine.classify(make_txn("Uber", "25.00"))
        assert txn.status == TransactionStatus.CLASSIFIED
        assert txn.classification_rule != ""
