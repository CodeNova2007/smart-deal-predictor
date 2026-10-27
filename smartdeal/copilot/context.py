"""Assemble grounded shopping context for the copilot.

Only facts read from SQLite and calculations from :mod:`smartdeal.analytics` are
included. The model receives no raw secrets and no unverified market data.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..analytics import build_product_snapshot
from ..database import Database

_STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "pro",
    "max",
    "mini",
    "smart",
    "wireless",
    "headphones",
    "camera",
    "monitor",
    "machine",
    "keyboard",
    "watch",
    "phone",
    "ultrabook",
    "purifier",
    "treadmill",
    "mattress",
    "earbuds",
    "coffee",
    "product",
    "products",
    "price",
    "deal",
}


def _compact_product(snapshot: dict[str, Any]) -> dict[str, Any]:
    stats = snapshot["stats"]
    forecast = snapshot["forecast"]
    best = snapshot.get("best_offer")
    deal = snapshot["deal"]
    watchlist = snapshot.get("watchlist")
    live = snapshot.get("live") or {}
    return {
        "product_id": snapshot["id"],
        "name": snapshot["name"],
        "brand": snapshot["brand"],
        "category": snapshot["category"],
        "data_origin": snapshot.get("data_origin", "demo"),
        "data_provenance": (
            "live marketplace quote recorded by the app"
            if snapshot.get("is_live")
            else "synthetic demo catalog data"
        ),
        "live_status": live.get("status_label") if snapshot.get("is_live") else None,
        "live_checked_at": live.get("last_checked_at") if snapshot.get("is_live") else None,
        "live_source_count": live.get("source_count") if snapshot.get("is_live") else 0,
        "current_price": snapshot["current_price"],
        "list_price": snapshot["list_price"],
        "has_detected_mrp": snapshot.get("has_list_price", False),
        "discount_pct": snapshot["savings"]["vs_list_pct"],
        "deal_score": deal["score"],
        "deal_label": deal["label"],
        "average_recorded_price": stats.get("average_price"),
        "minimum_recorded_price": stats.get("minimum_price"),
        "maximum_recorded_price": stats.get("maximum_price"),
        "trend": stats.get("trend_direction"),
        "trend_30d_pct": stats.get("change_30d_pct"),
        "trend_weekly_pct": stats.get("trend_weekly_pct"),
        "forecast_7d": (
            {
                "available": True,
                "estimated_price": forecast.get("predicted_price_7d"),
                "range": [
                    forecast.get("lower_bound_7d"),
                    forecast.get("upper_bound_7d"),
                ],
                "confidence": forecast.get("confidence"),
                "direction": forecast.get("direction"),
            }
            if forecast.get("available")
            else {"available": False, "reason": forecast.get("reason")}
        ),
        "best_offer": (
            {
                "seller": best["seller"],
                "retailer": best.get("retailer") or "",
                "total_price": best["total_price"],
                "in_stock": best["in_stock"],
                "availability": best.get("availability") or "",
                "coupon_code": best.get("coupon_code") or None,
                "is_live": bool(best.get("is_live")),
                "stale": bool(best.get("stale")),
            }
            if best
            else None
        ),
        "watchlist_target": watchlist["target_price"] if watchlist else None,
        "purchase_record": snapshot.get("purchase"),
    }


def _detailed_product(snapshot: dict[str, Any]) -> dict[str, Any]:
    detail = _compact_product(snapshot)
    stats = snapshot["stats"]
    forecast = snapshot["forecast"]
    detail.update(
        {
            "recorded_facts": {
                "data_origin": snapshot.get("data_origin", "demo"),
                "live_status": (snapshot.get("live") or {}).get("status_label")
                if snapshot.get("is_live")
                else None,
                "live_checked_at": (snapshot.get("live") or {}).get("last_checked_at")
                if snapshot.get("is_live")
                else None,
                "live_source_count": len(snapshot.get("sources") or []),
                "observations": stats.get("observations"),
                "first_observation": stats.get("first_date"),
                "last_observation": stats.get("last_date"),
                "minimum_price": stats.get("minimum_price"),
                "minimum_date": stats.get("minimum_date"),
                "maximum_price": stats.get("maximum_price"),
                "maximum_date": stats.get("maximum_date"),
                "median_price": stats.get("median_price"),
                "lower_quartile": stats.get("p25_price"),
                "standard_deviation": stats.get("std_dev"),
                "volatility_pct": stats.get("volatility_pct"),
                "current_vs_minimum_pct": stats.get("current_vs_min_pct"),
                "current_vs_average_pct": stats.get("current_vs_average_pct"),
                "recent_observations": snapshot["recent_observations"],
            },
            "deal_analysis": {
                "score": snapshot["deal"]["score"],
                "label": snapshot["deal"]["label"],
                "summary": snapshot["deal"]["summary"],
                "discount_pct_vs_list": snapshot["deal"]["discount_pct"],
                "component_scores": snapshot["deal"]["components"],
                "weights": snapshot["deal"]["weights"],
                "savings_vs_list": snapshot["savings"]["vs_list_price"],
                "savings_vs_average": snapshot["savings"]["vs_average"],
                "savings_vs_best_offer": snapshot["savings"]["vs_best_offer"],
            },
            "forecast": (
                {
                    "available": True,
                    "method": forecast.get("method"),
                    "horizon_days": forecast.get("horizon_days"),
                    "estimated_price_7d": forecast.get("predicted_price_7d"),
                    "uncertainty_range_7d": [
                        forecast.get("lower_bound_7d"),
                        forecast.get("upper_bound_7d"),
                    ],
                    "predicted_change_pct": forecast.get("predicted_change_pct"),
                    "direction": forecast.get("direction"),
                    "confidence": forecast.get("confidence"),
                    "r_squared": forecast.get("r_squared"),
                    "disclaimer": forecast.get("disclaimer"),
                }
                if forecast.get("available")
                else {
                    "available": False,
                    "reason": forecast.get("reason"),
                    "method": forecast.get("method"),
                }
            ),
            "seller_offers": [
                {
                    "seller": offer["seller"],
                    "retailer": offer.get("retailer") or "",
                    "listed_price": offer["price"],
                    "mrp": offer.get("list_price") or None,
                    "delivery_fee": offer["delivery_fee"],
                    "coupon_code": offer.get("coupon_code") or None,
                    "coupon_amount": offer.get("coupon_amount") or 0,
                    "effective_total": offer["total_price"],
                    "in_stock": offer["in_stock"],
                    "availability": offer.get("availability") or "",
                    "is_live": bool(offer.get("is_live")),
                    "stale": bool(offer.get("stale")),
                    "source_url": offer.get("source_url") or "",
                    "best_available": offer["is_best"],
                }
                for offer in snapshot["offers"]
            ],
            "watchlist": snapshot.get("watchlist"),
            "suggested_target": snapshot.get("suggested_target"),
            "purchase_record": snapshot.get("purchase"),
        }
    )
    return detail


def _matches_product(query: str, snapshot: dict[str, Any]) -> bool:
    normalized = query.lower()
    name = snapshot["name"].lower()
    brand = str(snapshot["brand"]).lower()
    if name in normalized or (brand and len(brand) >= 4 and brand in normalized):
        return True
    keywords = [
        token
        for token in re.findall(r"[a-z0-9]+", name)
        if len(token) >= 4 and token not in _STOPWORDS
    ]
    matches = sum(1 for token in keywords if re.search(rf"\b{re.escape(token)}\b", normalized))
    return matches >= 2


def find_mentioned_snapshots(
    query: str, snapshots: list[dict[str, Any]], exclude_id: int | None = None
) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    matches = [
        snapshot
        for snapshot in snapshots
        if snapshot["id"] != exclude_id and _matches_product(query, snapshot)
    ]
    if matches:
        normalized = query.lower()
        # Rank explicit product names above brand-only or keyword matches, so a
        # named product always beats a same-brand sibling in comparisons.
        matches.sort(
            key=lambda item: (
                0 if item["name"].lower() in normalized else 1,
                -item["deal"]["score"],
            )
        )
    return matches[:2]


def build_shopping_context(
    db: Database,
    selected_product_id: int | None = None,
    query: str = "",
) -> dict[str, Any]:
    """Build a compact JSON-safe context, always including the catalog overview."""

    snapshots = [build_product_snapshot(bundle) for bundle in db.get_all_bundles()]
    snapshots.sort(key=lambda item: (-item["deal"]["score"], item["name"]))

    selected = None
    if selected_product_id is not None:
        selected = next(
            (item for item in snapshots if item["id"] == int(selected_product_id)), None
        )

    mentioned = find_mentioned_snapshots(
        query, snapshots, exclude_id=selected["id"] if selected else None
    )

    top_deals = sorted(snapshots, key=lambda item: -item["deal"]["score"])[:5]
    live_products = [item for item in snapshots if item.get("is_live")]
    demo_products = [item for item in snapshots if not item.get("is_live")]
    provenance_parts = [
        f"The catalog contains {len(demo_products)} demo products with synthetic "
        "prices and history and "
        f"{len(live_products)} live-imported products with quotes recorded from "
        "specific public product pages."
    ]
    if live_products:
        provenance_parts.append(
            "Live quotes may be stale, partial, out of stock, or failed. Use the "
            "live_status and live_checked_at fields and never describe a stale or "
            "failed quote as current."
        )
    provenance_parts.append(
        "Demo rows are never live marketplace prices. Do not invent a missing MRP, "
        "seller, coupon, delivery fee, availability, or history."
    )
    context = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "currency": "INR",
        "data_provenance": " ".join(provenance_parts),
        "selected_product": _detailed_product(selected) if selected else None,
        "mentioned_products_from_question": [
            _detailed_product(item) for item in mentioned
        ],
        "catalog_overview": [_compact_product(item) for item in snapshots],
        "top_deals_by_score": [
            {
                "name": item["name"],
                "current_price": item["current_price"],
                "deal_score": item["deal"]["score"],
                "deal_label": item["deal"]["label"],
                "discount_pct": item["savings"]["vs_list_pct"],
                "data_origin": item.get("data_origin", "demo"),
            }
            for item in top_deals
        ],
        "application": {
            "pages": {
                "Dashboard": "Overview metrics, alerts, featured deal, market pulse, and live quote health.",
                "Deals": "Filter by budget, category, source, and deal score.",
                "Products": "Search/filter products and open a product detail page.",
                "Compare": "Put two or three products side by side.",
                "Live quotes": "Import a product-page URL, refresh quotes, and manage sources.",
                "Watchlist": "Set or update target prices and see whether targets are met.",
                "Alerts": "Persistent inbox for targets, price drops, stock changes, and quote checks.",
                "Purchases": "Record what you paid and compare it with the latest recorded quote.",
                "Insights": "Category strength, price movement, budget map, and forecast outlook.",
                "How it works": "Explains deal scores, forecasts, data labels, and live quote rules.",
            },
            "product_detail": (
                "Shows recorded price history, a 7-day forecast with uncertainty, "
                "deal-score components, live marketplace quotes or demo offers, "
                "marketplace sources, a target-price form, a user-provided purchase "
                "record, and a shareable product link."
            ),
            "ai_copilot": (
                "Floating button at the bottom-right opens a right-side chat panel. "
                "Product context is attached automatically when a product is open."
            ),
        },
    }
    return context
