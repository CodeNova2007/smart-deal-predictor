"""Persistent, user-facing shopping alerts.

Alerts are deliberately generated from recorded state changes rather than from
model guesses. Every alert has a stable dedupe key so a refresh cannot spam the
same event, and every message explains whether it came from live data or the
demo catalog.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from .database import Database

ALERT_KIND_LABELS = {
    "target_reached": "Target reached",
    "price_drop": "Price drop",
    "back_in_stock": "Back in stock",
    "out_of_stock": "Out of stock",
    "quote_attention": "Quote needs attention",
    "quote_recovered": "Quote recovered",
}

ALERT_KIND_TONES = {
    "target_reached": "green",
    "price_drop": "green",
    "back_in_stock": "green",
    "out_of_stock": "rose",
    "quote_attention": "amber",
    "quote_recovered": "blue",
}

ALERT_KIND_GROUPS = {
    "target_reached": "target",
    "price_drop": "price",
    "back_in_stock": "price",
    "out_of_stock": "price",
    "quote_attention": "quote",
    "quote_recovered": "quote",
}

_ATTENTION_STATUSES = {"stale", "error", "no_sources", "partial"}


def _inr(value: Any) -> str:
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _today() -> str:
    return date.today().isoformat()


def alert_kind_label(kind: str) -> str:
    return ALERT_KIND_LABELS.get(kind, str(kind).replace("_", " ").title())


def alert_kind_tone(kind: str) -> str:
    return ALERT_KIND_TONES.get(kind, "amber")


def alert_kind_group(kind: str) -> str:
    return ALERT_KIND_GROUPS.get(kind, "other")


def _has_in_stock_offer(snapshot: dict[str, Any] | None) -> bool:
    if not snapshot:
        return False
    return any(
        bool(offer.get("in_stock"))
        for offer in snapshot.get("offers") or []
        if offer.get("is_live")
    )


def _status(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return ""
    return str((snapshot.get("live") or {}).get("status") or "")


def _create(
    db: Database,
    *,
    kind: str,
    title: str,
    message: str,
    product_id: int | None,
    dedupe_key: str,
) -> bool:
    return db.create_alert(
        kind=kind,
        title=title,
        message=message,
        product_id=product_id,
        dedupe_key=dedupe_key,
    )


def _target_alert(db: Database, snapshot: dict[str, Any]) -> bool:
    watchlist = snapshot.get("watchlist") or {}
    if not watchlist.get("reached"):
        return False
    product_id = int(snapshot["id"])
    target = float(watchlist["target_price"])
    price = float(snapshot["current_price"])
    if snapshot.get("is_live"):
        message = (
            f"The latest recorded live quote is {_inr(price)}, at or below your "
            f"{_inr(target)} target."
        )
        live = snapshot.get("live") or {}
        if live.get("status") in {"stale", "error", "partial"}:
            message += " The quote needs a refresh before you rely on it."
    else:
        message = (
            f"The demo catalog price is {_inr(price)}, at or below your "
            f"{_inr(target)} target. This is synthetic sample data, not a live "
            "marketplace quote."
        )
    return _create(
        db,
        kind="target_reached",
        title=f"Target reached: {snapshot['name']}",
        message=message,
        product_id=product_id,
        dedupe_key=f"target:{product_id}:{target:.2f}",
    )


def sync_target_alerts(
    db: Database, snapshots: Iterable[dict[str, Any]]
) -> int:
    """Create one persistent alert for every reached watch level.

    The dedupe key is tied to the product and target value, so a target only
    alerts once until the user changes it.
    """

    created = 0
    for snapshot in snapshots:
        if _target_alert(db, snapshot):
            created += 1
    return created


def record_refresh_alerts(
    db: Database,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> int:
    """Compare two live snapshots and persist meaningful changes."""

    if not after or not after.get("is_live"):
        return 0

    created = 0
    product_id = int(after["id"])
    name = str(after.get("name") or "Live product")
    day = _today()
    before_status = _status(before)
    after_status = _status(after)
    before_price = (
        float(before["current_price"]) if before and before.get("current_price") else None
    )
    after_price = float(after.get("current_price") or 0)

    if before_price is not None and after_price and after_price < before_price - 0.005:
        drop = before_price - after_price
        drop_pct = (drop / before_price * 100) if before_price else 0.0
        if _create(
            db,
            kind="price_drop",
            title=f"Price dropped: {name}",
            message=(
                f"The latest live quote is {_inr(after_price)}, down "
                f"{_inr(drop)} ({drop_pct:.1f}%) from {_inr(before_price)}."
            ),
            product_id=product_id,
            dedupe_key=f"price_drop:{product_id}:{after_price:.2f}:{day}",
        ):
            created += 1

    before_stock = _has_in_stock_offer(before)
    after_stock = _has_in_stock_offer(after)
    if before_stock and not after_stock:
        if _create(
            db,
            kind="out_of_stock",
            title=f"Out of stock: {name}",
            message=(
                "The attached live sources no longer show this item in stock. "
                "The last successful price is kept for reference."
            ),
            product_id=product_id,
            dedupe_key=f"out_of_stock:{product_id}:{day}",
        ):
            created += 1
    elif not before_stock and after_stock and before_status == "out_of_stock":
        if _create(
            db,
            kind="back_in_stock",
            title=f"Back in stock: {name}",
            message=(
                f"A live source is showing this item in stock again at "
                f"{_inr(after_price)}."
            ),
            product_id=product_id,
            dedupe_key=f"back_in_stock:{product_id}:{day}",
        ):
            created += 1

    if after_status in _ATTENTION_STATUSES and before_status != after_status:
        message = (
            "Some attached sources need attention; the available quote is still "
            "shown and the affected source is labelled."
            if after_status == "partial"
            else (
                "The latest check could not confirm a fresh quote. The last "
                "successful price is kept and labelled stale or failed."
            )
        )
        if _create(
            db,
            kind="quote_attention",
            title=f"Quote needs attention: {name}",
            message=message,
            product_id=product_id,
            dedupe_key=f"quote_attention:{product_id}:{after_status}:{day}",
        ):
            created += 1
    elif before_status in _ATTENTION_STATUSES and after_status == "ok":
        if _create(
            db,
            kind="quote_recovered",
            title=f"Quote recovered: {name}",
            message=(
                f"A fresh live quote is available again at {_inr(after_price)}."
            ),
            product_id=product_id,
            dedupe_key=f"quote_recovered:{product_id}:{day}",
        ):
            created += 1

    if _target_alert(db, after):
        created += 1
    return created


def record_import_alert(
    db: Database, snapshot: dict[str, Any] | None
) -> int:
    """Alert once when a newly imported live product is already out of stock."""

    if not snapshot or not snapshot.get("is_live"):
        return 0
    created = 0
    if _status(snapshot) == "out_of_stock":
        product_id = int(snapshot["id"])
        if _create(
            db,
            kind="out_of_stock",
            title=f"Out of stock: {snapshot['name']}",
            message=(
                "This live product is currently shown as out of stock, so no "
                "live price history point was recorded."
            ),
            product_id=product_id,
            dedupe_key=f"out_of_stock:{product_id}:{_today()}",
        ):
            created += 1
    if _target_alert(db, snapshot):
        created += 1
    return created
