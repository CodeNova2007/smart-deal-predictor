"""Deterministic tests for the app's shopping calculations."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from smartdeal.analytics import (
    build_product_snapshot,
    calculate_deal_score,
    calculate_price_stats,
    decorate_offers,
    effective_offer_total,
    forecast_prices,
    format_inr,
    suggested_target_price,
)
from smartdeal.database import Database


def _history(prices: list[float]) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {
            "observed_on": (start + timedelta(days=index)).isoformat(),
            "price": price,
            "source": "test",
        }
        for index, price in enumerate(prices)
    ]


def test_effective_offer_total_handles_coupon_and_delivery():
    offer = {"price": 10_000, "coupon_amount": 1_500, "delivery_fee": 99}
    assert effective_offer_total(offer) == 8_599

    assert (
        effective_offer_total(
            {"price": 1_000, "coupon_amount": 5_000, "delivery_fee": 0}
        )
        == 0
    )


def test_decorate_offers_marks_cheapest_in_stock_offer():
    offers = [
        {
            "seller": "OutOfStock",
            "price": 100,
            "delivery_fee": 0,
            "coupon_amount": 0,
            "in_stock": 0,
        },
        {
            "seller": "Better",
            "price": 500,
            "delivery_fee": 0,
            "coupon_amount": 50,
            "in_stock": 1,
        },
        {
            "seller": "Costly",
            "price": 600,
            "delivery_fee": 0,
            "coupon_amount": 0,
            "in_stock": 1,
        },
    ]
    decorated = decorate_offers(offers)
    assert decorated[0]["seller"] == "Better"
    assert decorated[0]["is_best"] is True
    assert decorated[0]["total_price"] == 450
    assert sum(1 for item in decorated if item["is_best"]) == 1


def test_price_stats_are_derived_from_recorded_observations():
    stats = calculate_price_stats(
        _history([100, 90, 80, 110, 80]), current_price=80
    )
    assert stats["available"] is True
    assert stats["observations"] == 5
    assert stats["minimum_price"] == 80
    assert stats["maximum_price"] == 110
    assert stats["average_price"] == 92
    assert stats["median_price"] == 90
    assert stats["current_vs_min_pct"] == 0
    assert stats["first_date"] == "2026-01-01"
    assert stats["last_date"] == "2026-01-05"


def test_price_stats_report_missing_data_instead_of_guessing():
    stats = calculate_price_stats([])
    assert stats["available"] is False
    assert stats["observations"] == 0
    assert "No recorded price observations" in stats["reason"]


def test_forecast_uses_linear_trend_and_uncertainty_band():
    prices = [1_000 + index * 10 for index in range(30)]
    forecast = forecast_prices(_history(prices))
    assert forecast["available"] is True
    assert forecast["slope_per_day"] == pytest.approx(10, abs=0.01)
    assert forecast["predicted_price_7d"] > prices[-1]
    assert forecast["lower_bound_7d"] <= forecast["predicted_price_7d"]
    assert forecast["upper_bound_7d"] >= forecast["predicted_price_7d"]
    assert forecast["confidence"] in {"high", "medium", "low"}
    assert "not a guarantee" in forecast["disclaimer"]
    assert len(forecast["predictions"]) == 7


def test_forecast_requires_at_least_seven_observations():
    forecast = forecast_prices(_history([100, 101, 102]))
    assert forecast["available"] is False
    assert "At least 7" in forecast["reason"]


def test_deal_score_rewards_a_low_price_and_penalises_a_high_price():
    strong = calculate_deal_score(
        current_price=80,
        minimum_price=80,
        maximum_price=120,
        list_price=130,
        trend_weekly_pct=-2,
        best_total_price=75,
    )
    weak = calculate_deal_score(
        current_price=120,
        minimum_price=80,
        maximum_price=120,
        list_price=130,
        trend_weekly_pct=2,
        best_total_price=None,
    )
    assert strong["score"] > weak["score"]
    assert 0 <= weak["score"] <= strong["score"] <= 100
    assert sum(strong["weights"].values()) == pytest.approx(1.0)
    assert strong["label"] == "Excellent deal"
    assert strong["summary"]


def test_suggested_target_is_positive_and_anchored_below_current():
    stats = calculate_price_stats(
        _history([100] * 10 + [80] * 10 + [90] * 10), current_price=90
    )
    target = suggested_target_price(90, stats)
    assert target["target_price"] > 0
    assert target["target_price"] < 90
    assert "not a guaranteed" in target["note"]


def test_build_product_snapshot_combines_db_and_calculations(db: Database):
    product = next(item for item in db.list_products() if item["name"] == "EchoBuds Pro")
    snapshot = build_product_snapshot(db.get_bundle(int(product["id"])))

    assert snapshot["name"] == "EchoBuds Pro"
    assert snapshot["current_price"] == 8_999
    assert snapshot["stats"]["observations"] == 120
    assert len(snapshot["offers"]) == 4
    assert snapshot["best_offer"]["is_best"] is True
    assert snapshot["deal"]["score"] > 0
    assert snapshot["forecast"]["available"] is True
    assert len(snapshot["recent_observations"]) == 14
    assert snapshot["suggested_target"]["target_price"] > 0


def test_format_inr_uses_indian_grouping_and_handles_missing_values():
    assert format_inr(1234567) == "₹1,234,567"
    assert format_inr(None) == "—"
