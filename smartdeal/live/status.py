"""Provenance and freshness labels shared by analytics, the service, and the UI."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

DEFAULT_STALE_HOURS = 24

STATUS_LABELS = {
    "ok": "Live",
    "partial": "Partial live",
    "stale": "Stale quote",
    "error": "Live fetch failed",
    "out_of_stock": "Out of stock",
    "no_sources": "No live sources",
    "demo": "Demo data",
    "unknown": "Not checked",
}

STATUS_TONES = {
    "ok": "green",
    "partial": "amber",
    "stale": "amber",
    "error": "rose",
    "out_of_stock": "rose",
    "no_sources": "amber",
    "demo": "amber",
    "unknown": "amber",
}


def parse_timestamp(value: Any) -> datetime | None:
    """Parse the ISO timestamps stored by the live service.

    Older rows may contain a plain date, so ``datetime.fromisoformat`` is used
    after normalising a trailing ``Z``.
    """

    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_stale(
    last_success_at: Any,
    stale_hours: int | float = DEFAULT_STALE_HOURS,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when a quote is missing or older than the stale window."""

    parsed = parse_timestamp(last_success_at)
    if parsed is None:
        return True
    reference = now or datetime.now(timezone.utc)
    try:
        window = max(1.0, float(stale_hours))
    except (TypeError, ValueError):
        window = float(DEFAULT_STALE_HOURS)
    return (reference - parsed) > timedelta(hours=window)


def source_view(
    source: dict[str, Any],
    stale_hours: int | float = DEFAULT_STALE_HOURS,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Add freshness and display labels to one marketplace source row."""

    last_success_at = str(source.get("last_success_at") or "")
    stale = is_stale(last_success_at, stale_hours, now=now)
    raw_status = str(source.get("last_status") or "").strip().lower()
    if raw_status == "ok":
        status = "stale" if stale else "ok"
    elif raw_status:
        status = "error"
    else:
        status = "unknown"
    return {
        **source,
        "stale": stale,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status.title()),
        "status_tone": STATUS_TONES.get(status, "amber"),
    }


def live_product_view(
    product: dict[str, Any],
    sources: list[dict[str, Any]] | None = None,
    stale_hours: int | float = DEFAULT_STALE_HOURS,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the provenance block attached to every product snapshot."""

    origin = str(product.get("data_origin") or "demo").lower()
    source_views = [
        source_view(source, stale_hours, now=now) for source in (sources or [])
    ]
    if origin != "live":
        return {
            "is_live": False,
            "data_origin": "demo",
            "status": "demo",
            "status_label": STATUS_LABELS["demo"],
            "status_tone": STATUS_TONES["demo"],
            "stale": False,
            "error": "",
            "last_checked_at": "",
            "last_success_at": "",
            "source_count": 0,
            "sources": [],
            "stale_source_count": 0,
            "failed_source_count": 0,
        }

    status = str(product.get("live_status") or "unknown").strip().lower()
    last_success_at = str(product.get("last_success_at") or "")
    stale = is_stale(last_success_at, stale_hours, now=now)
    if stale and status in {"ok", "partial", "out_of_stock"}:
        status = "stale"
    if status not in STATUS_LABELS:
        status = "unknown"

    stale_sources = sum(1 for source in source_views if source["stale"])
    failed_sources = sum(1 for source in source_views if source["status"] == "error")
    return {
        "is_live": True,
        "data_origin": "live",
        "status": status,
        "status_label": STATUS_LABELS.get(status, status.title()),
        "status_tone": STATUS_TONES.get(status, "amber"),
        "stale": stale or status == "stale",
        "error": str(product.get("live_error") or ""),
        "last_checked_at": str(product.get("last_checked_at") or ""),
        "last_success_at": last_success_at,
        "source_count": len(source_views),
        "sources": source_views,
        "stale_source_count": stale_sources,
        "failed_source_count": failed_sources,
    }
