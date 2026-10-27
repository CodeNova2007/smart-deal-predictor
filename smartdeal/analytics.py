"""Pure shopping calculations used by both the UI and the AI copilot.

Keeping these functions deterministic and side-effect free means recommendations
can always be traced back to recorded observations instead of model guesses.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

import numpy as np

from .live.status import DEFAULT_STALE_HOURS, live_product_view


DEAL_WEIGHTS = {
    "price_position": 0.40,
    "discount": 0.25,
    "trend": 0.20,
    "offer": 0.15,
}


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def format_inr(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"₹{float(value):,.0f}"


def format_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}%"


def effective_offer_total(offer: dict[str, Any]) -> float:
    """Total paid after recorded coupon and delivery fee."""

    price = float(offer.get("price") or 0)
    coupon = max(0.0, float(offer.get("coupon_amount") or 0))
    delivery = max(0.0, float(offer.get("delivery_fee") or 0))
    return round(max(0.0, price - coupon) + delivery, 2)


def decorate_offers(
    offers: Iterable[dict[str, Any]],
    stale_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    stale_urls = stale_urls or set()
    decorated = []
    for offer in offers:
        row = dict(offer)
        row["in_stock"] = bool(row.get("in_stock"))
        row["is_live"] = bool(row.get("is_live"))
        row["retailer"] = str(row.get("retailer") or "")
        row["source_url"] = str(row.get("source_url") or "")
        row["availability"] = str(row.get("availability") or "")
        row["list_price"] = float(row.get("list_price") or 0)
        row["stale"] = bool(
            row["is_live"] and row["source_url"] in stale_urls
        )
        row["total_price"] = effective_offer_total(row)
        row["is_best"] = False
        decorated.append(row)

    decorated.sort(
        key=lambda item: (
            not item["in_stock"],
            item["total_price"],
            float(item.get("price") or 0),
            str(item.get("seller") or ""),
        )
    )

    best = next((item for item in decorated if item["in_stock"]), None)
    if best is not None:
        best["is_best"] = True
    return decorated


def best_available_offer(offers: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((offer for offer in offers if offer["is_best"]), None)


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def calculate_price_stats(
    history: list[dict[str, Any]], current_price: float | None = None
) -> dict[str, Any]:
    """Summarise recorded observations. All values are facts from the database."""

    rows = sorted(
        [row for row in history if row.get("price") is not None],
        key=lambda row: str(row.get("observed_on", "")),
    )
    if not rows:
        return {
            "available": False,
            "observations": 0,
            "reason": "No recorded price observations are available for this product.",
        }

    prices = np.asarray([float(row["price"]) for row in rows], dtype=float)
    dates = [str(row["observed_on"])[:10] for row in rows]
    current = float(current_price if current_price is not None else prices[-1])
    minimum = float(np.min(prices))
    maximum = float(np.max(prices))
    average = float(np.mean(prices))
    median = float(np.median(prices))
    p25 = float(np.percentile(prices, 25))
    p75 = float(np.percentile(prices, 75))
    std_dev = float(np.std(prices, ddof=1)) if len(prices) > 1 else 0.0

    min_index = int(np.argmin(prices))
    max_index = int(np.argmax(prices))
    last_day = _parse_date(dates[-1])
    reference_index = 0
    for index, observed in enumerate(dates):
        if _parse_date(observed) <= last_day - timedelta(days=30):
            reference_index = index
    reference_price = float(prices[reference_index])
    change_30d = (
        ((current - reference_price) / reference_price * 100)
        if reference_price
        else 0.0
    )

    recent = prices[-30:]
    if len(recent) >= 3:
        x = np.arange(len(recent), dtype=float)
        slope, _intercept = np.polyfit(x, recent, 1)
        weekly_pct = (float(slope) * 7 / current * 100) if current else 0.0
    else:
        weekly_pct = 0.0

    if weekly_pct <= -1.0:
        direction = "falling"
    elif weekly_pct >= 1.0:
        direction = "rising"
    else:
        direction = "stable"

    return {
        "available": True,
        "observations": int(len(prices)),
        "first_date": dates[0],
        "last_date": dates[-1],
        "current_price": round(current, 2),
        "average_price": round(average, 2),
        "minimum_price": round(minimum, 2),
        "minimum_date": dates[min_index],
        "maximum_price": round(maximum, 2),
        "maximum_date": dates[max_index],
        "median_price": round(median, 2),
        "p25_price": round(p25, 2),
        "p75_price": round(p75, 2),
        "std_dev": round(std_dev, 2),
        "volatility_pct": round((std_dev / average * 100) if average else 0.0, 2),
        "change_30d_pct": round(change_30d, 2),
        "trend_weekly_pct": round(weekly_pct, 2),
        "trend_direction": direction,
        "current_vs_min_pct": round(
            ((current - minimum) / minimum * 100) if minimum else 0.0, 2
        ),
        "current_vs_average_pct": round(
            ((current - average) / average * 100) if average else 0.0, 2
        ),
    }


def forecast_prices(
    history: list[dict[str, Any]], horizon: int = 7
) -> dict[str, Any]:
    """Fit a simple linear trend to recent observations and project it forward.

    The forecast is an estimate, not a promise. A widening residual-based band
    makes that uncertainty visible.
    """

    rows = sorted(history, key=lambda row: str(row.get("observed_on", "")))[-30:]
    points = [
        (str(row["observed_on"])[:10], float(row["price"]))
        for row in rows
        if row.get("price") is not None
    ]
    if len(points) < 7:
        return {
            "available": False,
            "reason": "At least 7 recorded observations are needed for a forecast.",
            "method": "Linear regression on recent price observations",
        }

    x = np.arange(len(points), dtype=float)
    y = np.asarray([price for _, price in points], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    residuals = y - fitted
    residual_std = float(np.std(residuals, ddof=1)) if len(y) > 2 else 0.0
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    r_squared = float(clamp(r_squared, -1.0, 1.0))

    x_mean = float(np.mean(x))
    sxx = float(np.sum((x - x_mean) ** 2))
    last_date = _parse_date(points[-1][0])
    current = float(y[-1])
    predictions: list[dict[str, Any]] = []

    for step in range(1, horizon + 1):
        future_x = float(len(points) - 1 + step)
        point = float(slope * future_x + intercept)
        point = max(0.0, point)
        leverage = 1 + (1 / len(points)) + (
            ((future_x - x_mean) ** 2) / sxx if sxx else 0.0
        )
        margin = 1.28 * residual_std * float(np.sqrt(max(leverage, 0.0)))
        predictions.append(
            {
                "date": (last_date + timedelta(days=step)).isoformat(),
                "predicted_price": round(point, 2),
                "lower_bound": round(max(0.0, point - margin), 2),
                "upper_bound": round(point + margin, 2),
            }
        )

    final = predictions[-1]
    predicted_change_pct = (
        ((final["predicted_price"] - current) / current * 100) if current else 0.0
    )
    if predicted_change_pct <= -1.0:
        direction = "falling"
    elif predicted_change_pct >= 1.0:
        direction = "rising"
    else:
        direction = "stable"

    relative_residual = (residual_std / float(np.mean(y))) if np.mean(y) else 0.0
    if len(points) >= 21 and r_squared >= 0.55 and relative_residual <= 0.035:
        confidence = "high"
    elif r_squared >= 0.25 and relative_residual <= 0.07:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "available": True,
        "method": "Linear regression on the latest 30 recorded observations",
        "horizon_days": horizon,
        "observations_used": len(points),
        "slope_per_day": round(float(slope), 2),
        "r_squared": round(r_squared, 3),
        "residual_std": round(residual_std, 2),
        "confidence": confidence,
        "direction": direction,
        "predicted_change_pct": round(predicted_change_pct, 2),
        "predicted_price_7d": final["predicted_price"],
        "lower_bound_7d": final["lower_bound"],
        "upper_bound_7d": final["upper_bound"],
        "predictions": predictions,
        "disclaimer": (
            "This is a statistical estimate with uncertainty, not a guarantee "
            "that the price will move in this direction."
        ),
    }


def calculate_deal_score(
    *,
    current_price: float,
    minimum_price: float,
    maximum_price: float,
    list_price: float,
    trend_weekly_pct: float = 0.0,
    best_total_price: float | None = None,
) -> dict[str, Any]:
    """Blend price position, discount, trend, and offers into a 0–100 score."""

    if maximum_price > minimum_price:
        price_score = clamp(
            (maximum_price - current_price) / (maximum_price - minimum_price) * 100
        )
    else:
        price_score = 50.0

    discount_pct = (
        ((list_price - current_price) / list_price * 100) if list_price else 0.0
    )
    discount_score = clamp(max(0.0, discount_pct) / 40 * 100)
    trend_score = clamp(50 - float(trend_weekly_pct) * 6)

    if best_total_price is not None and best_total_price < current_price:
        offer_savings_pct = (current_price - best_total_price) / current_price * 100
        offer_score = clamp(50 + (offer_savings_pct / 10) * 50)
    elif best_total_price is not None:
        offer_score = 40.0
    else:
        offer_score = 35.0

    components = {
        "price_position": round(price_score, 1),
        "discount": round(discount_score, 1),
        "trend": round(trend_score, 1),
        "offer": round(offer_score, 1),
    }
    weighted = {
        key: round(components[key] * DEAL_WEIGHTS[key], 1) for key in components
    }
    score = int(round(sum(weighted.values())))

    if score >= 78:
        label = "Excellent deal"
    elif score >= 62:
        label = "Good deal"
    elif score >= 45:
        label = "Fair deal"
    else:
        label = "Wait for a better price"

    if score >= 78:
        summary = "The recorded price is strong compared with this product's own history."
    elif score >= 62:
        summary = "This is better than the usual recorded price, though not the absolute low."
    elif score >= 45:
        summary = "The deal is average for this product's recorded price range."
    else:
        summary = "The current price is high relative to this product's recorded history."

    return {
        "score": score,
        "label": label,
        "summary": summary,
        "components": components,
        "weights": dict(DEAL_WEIGHTS),
        "weighted_components": weighted,
        "discount_pct": round(discount_pct, 2),
    }


def suggested_target_price(
    current_price: float,
    stats: dict[str, Any],
    forecast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Suggest a watchlist target anchored to recorded lower-price zones."""

    if not stats.get("available"):
        target = current_price * 0.95
        rationale = "Suggested as 5% below the current price because history is limited."
    else:
        p25 = float(stats["p25_price"])
        floor = float(stats["minimum_price"])
        if p25 < current_price * 0.995:
            raw_target = p25
            rationale = "Based on the lower quartile of recorded prices."
        else:
            raw_target = min(current_price * 0.97, float(stats["average_price"]) * 0.96)
            rationale = (
                "The recorded price is already near its lower range, so this is a "
                "more ambitious target."
            )
        if forecast and forecast.get("available"):
            expected = float(forecast["predicted_price_7d"])
            if expected < raw_target:
                raw_target = expected
                rationale = "Based on the lower end of the 7-day trend estimate."
        target = max(floor * 1.005, raw_target)

    rounded = int(round(target / 100) * 100) - 1
    rounded = min(rounded, max(1, int(current_price) - 1))
    return {
        "target_price": max(1, rounded),
        "rationale": rationale,
        "note": "A target price is a watch level, not a guaranteed future price.",
    }


def build_purchase_view(
    purchase: dict[str, Any] | None,
    current_price: float,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Describe a user-provided purchase without treating it as a quote."""

    if not purchase:
        return None
    try:
        paid = float(purchase.get("price_paid") or 0)
    except (TypeError, ValueError):
        return None
    if paid <= 0:
        return None
    current = float(current_price or 0)
    minimum = (stats or {}).get("minimum_price")
    difference = round(paid - current, 2)
    return {
        "product_id": int(purchase["product_id"]),
        "price_paid": round(paid, 2),
        "purchased_on": str(purchase.get("purchased_on") or ""),
        "retailer": str(purchase.get("retailer") or ""),
        "notes": str(purchase.get("notes") or ""),
        "current_price": round(current, 2),
        "difference_vs_current": difference,
        "difference_vs_current_pct": (
            round(difference / paid * 100, 2) if paid else 0.0
        ),
        "below_current": difference < -0.005,
        "at_current": abs(difference) < 0.005,
        "recorded_low": (
            round(float(minimum), 2) if minimum is not None else None
        ),
        "difference_vs_low": (
            round(paid - float(minimum), 2) if minimum is not None else None
        ),
        "at_or_below_low": bool(
            minimum is not None and paid <= float(minimum) + 0.005
        ),
    }


def summarise_purchases(snapshots: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate purchase records and current replacement values."""

    tracked = [item for item in snapshots if item.get("purchase")]
    total_paid = sum(float(item["purchase"]["price_paid"]) for item in tracked)
    current_value = sum(float(item["current_price"]) for item in tracked)
    difference = round(current_value - total_paid, 2)
    return {
        "count": len(tracked),
        "total_paid": round(total_paid, 2),
        "current_value": round(current_value, 2),
        "difference": difference,
        "difference_pct": (
            round(difference / total_paid * 100, 2) if total_paid else 0.0
        ),
        "cheaper_now": difference < -0.005,
        "products": tracked,
    }


def build_product_snapshot(
    bundle: dict[str, Any],
    *,
    stale_hours: int = DEFAULT_STALE_HOURS,
) -> dict[str, Any]:
    """Combine DB records with all deterministic calculations for one product."""

    product = dict(bundle["product"])
    sources = list(bundle.get("sources") or [])
    live = live_product_view(product, sources, stale_hours)
    stale_urls = {
        str(source.get("url") or "")
        for source in live.get("sources", [])
        if source.get("stale")
    }
    history = bundle.get("history") or []
    offers = decorate_offers(bundle.get("offers") or [], stale_urls=stale_urls)
    best = best_available_offer(offers)
    stats = calculate_price_stats(history, float(product["current_price"]))
    forecast = forecast_prices(history)
    watchlist = bundle.get("watchlist")
    current = float(product["current_price"])
    list_price = float(product["list_price"] or 0)
    has_list_price = list_price > 0
    comparison_list_price = list_price if has_list_price else current

    deal = calculate_deal_score(
        current_price=current,
        minimum_price=float(stats.get("minimum_price", current)),
        maximum_price=float(stats.get("maximum_price", current)),
        list_price=comparison_list_price,
        trend_weekly_pct=float(stats.get("trend_weekly_pct", 0.0)),
        best_total_price=float(best["total_price"]) if best else None,
    )

    savings = {
        "vs_list_price": (
            round(max(0.0, comparison_list_price - current), 2)
            if has_list_price
            else 0.0
        ),
        "vs_list_pct": round(
            (
                (comparison_list_price - current) / comparison_list_price * 100
            )
            if has_list_price and comparison_list_price
            else 0.0,
            2,
        ),
        "vs_average": round(float(stats.get("average_price", current)) - current, 2),
        "vs_average_pct": round(
            (
                (float(stats.get("average_price", current)) - current)
                / float(stats.get("average_price", current))
                * 100
            )
            if stats.get("average_price")
            else 0.0,
            2,
        ),
        "vs_minimum": round(current - float(stats.get("minimum_price", current)), 2),
        "vs_maximum": round(float(stats.get("maximum_price", current)) - current, 2),
        "vs_best_offer": round(current - float(best["total_price"]), 2) if best else None,
    }

    target = suggested_target_price(current, stats, forecast)
    watchlist_view = None
    if watchlist:
        target_price = float(watchlist["target_price"])
        watchlist_view = {
            "target_price": target_price,
            "gap_to_target": round(current - target_price, 2),
            "reached": current <= target_price,
            "updated_at": watchlist.get("updated_at"),
        }

    snapshot = {
        "id": int(product["id"]),
        "name": product["name"],
        "brand": product.get("brand", ""),
        "category": product.get("category", "Other"),
        "emoji": product.get("emoji", "🛍️"),
        "description": product.get("description", ""),
        "currency": product.get("currency", "INR"),
        "current_price": round(current, 2),
        "list_price": round(list_price, 2),
        "product": product,
        "data_origin": live["data_origin"],
        "is_live": live["is_live"],
        "live": live,
        "sources": live.get("sources", []),
        "provenance_label": (
            "Live marketplace quote" if live["is_live"] else "Demo catalog data"
        ),
        "provenance_tone": "green" if live["is_live"] else "amber",
        "has_list_price": has_list_price,
        "history": history,
        "stats": stats,
        "offers": offers,
        "best_offer": best,
        "deal": deal,
        "savings": savings,
        "forecast": forecast,
        "suggested_target": target,
        "watchlist": watchlist_view,
        "purchase": build_purchase_view(
            bundle.get("purchase"), current, stats
        ),
        "recent_observations": [
            {"date": str(row["observed_on"])[:10], "price": float(row["price"])}
            for row in history[-14:]
        ],
    }
    return snapshot


def build_all_snapshots(
    db: Any, *, stale_hours: int = DEFAULT_STALE_HOURS
) -> list[dict[str, Any]]:
    return [
        build_product_snapshot(bundle, stale_hours=stale_hours)
        for bundle in db.get_all_bundles()
    ]


def snapshot_sort_key(snapshot: dict[str, Any], sort_by: str) -> Any:
    if sort_by == "Lowest price":
        return (snapshot["current_price"], snapshot["name"])
    if sort_by == "Biggest discount":
        return (-snapshot["deal"]["discount_pct"], snapshot["name"])
    if sort_by == "Biggest saving":
        return (-snapshot["savings"]["vs_list_price"], snapshot["name"])
    if sort_by == "Price trend":
        order = {"falling": 0, "stable": 1, "rising": 2}
        return (
            order.get(snapshot["stats"].get("trend_direction", "stable"), 1),
            -snapshot["deal"]["score"],
        )
    return (-snapshot["deal"]["score"], snapshot["name"])
