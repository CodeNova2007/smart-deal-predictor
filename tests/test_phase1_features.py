"""Offline tests for Phase 1: alerts, purchases, deep links, and stale refresh."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from smartdeal.alerts import (
    record_import_alert,
    record_refresh_alerts,
    sync_target_alerts,
)
from smartdeal.analytics import (
    build_all_snapshots,
    build_purchase_view,
    summarise_purchases,
)
from smartdeal.config import Settings
from smartdeal.database import Database
from smartdeal.live import LiveQuote, LiveService
from smartdeal.live.scraper import ScrapeError
from smartdeal.ui.deep_links import (
    PAGE_SLUGS,
    build_query,
    build_share_url,
    page_from_slug,
    page_slug,
    parse_compare,
)


# ----------------------------------------------------------------------
# Fixtures and helpers
# ----------------------------------------------------------------------


def _quote(url: str, **overrides) -> LiveQuote:
    values = {
        "url": url,
        "retailer": "Amazon.in",
        "title": "Acme Wireless Headphones",
        "price": 1_999.0,
        "currency": "INR",
        "seller": "Acme Store",
        "in_stock": True,
        "availability": "In stock",
        "brand": "Acme",
        "description": "A test product.",
        "list_price": 2_499.0,
    }
    values.update(overrides)
    return LiveQuote(**values)


def _import_live(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> tuple[LiveService, int]:
    service = LiveService(db, settings)
    url = "https://www.amazon.in/dp/B0TEST1234"
    monkeypatch.setattr(service, "_scrape", lambda target: _quote(url))
    product_id = int(service.import_product(url)["product_id"])
    return service, product_id


def _snapshot_for(db: Database, product_id: int) -> dict:
    snapshots = build_all_snapshots(db)
    return next(item for item in snapshots if int(item["id"]) == product_id)


# ----------------------------------------------------------------------
# Deep links
# ----------------------------------------------------------------------


def test_page_slug_round_trips_every_page():
    for page, slug in PAGE_SLUGS.items():
        assert page_slug(page) == slug
        assert page_from_slug(slug) == page


def test_page_from_slug_accepts_underscores_and_spaces():
    assert page_from_slug("live_quotes") == "Live quotes"
    assert page_from_slug("Live Quotes") == "Live quotes"
    assert page_from_slug("not-a-page") is None


def test_build_query_only_includes_supplied_parts():
    assert build_query(page="Dashboard") == {"page": "dashboard"}
    assert build_query(page="Products", product_id=42) == {
        "page": "products",
        "product": "42",
    }
    assert build_query(compare_ids=[3, 1, 2]) == {"compare": "3,1,2"}
    assert build_query() == {}


def test_build_query_ignores_invalid_and_excess_ids():
    query = build_query(compare_ids=["x", 0, -4, 1, 2, 3, 4])
    assert query["compare"] == "1,2,3"


def test_parse_compare_filters_invalid_and_dedupes():
    assert parse_compare("1,2,2,abc,0,-3", valid_ids={1, 2, 3}) == [1, 2]
    assert parse_compare(None) == []
    assert parse_compare(["5", "6", "7", "8"]) == [5, 6, 7]


def test_build_share_url_preserves_base_and_encodes_query():
    url = build_share_url(
        "http://localhost:8501/", build_query(page="Alerts", product_id=7)
    )
    assert url.startswith("http://localhost:8501/")
    assert "page=alerts" in url
    assert "product=7" in url


def test_build_share_url_defaults_when_base_is_blank():
    url = build_share_url("", build_query(page="Purchases"))
    assert url.startswith("http://localhost:8501/")
    assert "page=purchases" in url


# ----------------------------------------------------------------------
# Purchases
# ----------------------------------------------------------------------


def test_upsert_purchase_stores_and_updates_one_record(db: Database):
    product = db.list_products()[0]
    product_id = int(product["id"])

    created = db.upsert_purchase(
        product_id,
        1_234.5,
        purchased_on=date(2026, 1, 15),
        retailer="MegaMart",
        notes="Festive sale",
    )
    assert created["price_paid"] == 1_234.5
    assert created["purchased_on"] == "2026-01-15"
    assert created["retailer"] == "MegaMart"
    assert created["notes"] == "Festive sale"

    # Upsert replaces the stored fields, so an omitted retailer clears it.
    updated = db.upsert_purchase(
        product_id, 1_199.0, purchased_on=date(2026, 2, 1)
    )
    assert updated["price_paid"] == 1_199.0
    assert updated["purchased_on"] == "2026-02-01"
    assert updated["retailer"] == ""
    assert updated["notes"] == ""

    # Passing values again restores them on the same single record.
    restored = db.upsert_purchase(
        product_id,
        1_199.0,
        purchased_on=date(2026, 2, 1),
        retailer="MegaMart",
        notes="Price match",
    )
    assert restored["retailer"] == "MegaMart"
    assert restored["notes"] == "Price match"

    assert len(db.get_all_purchases()) == 1
    assert db.get_purchase(product_id)["price_paid"] == 1_199.0
    assert db.get_purchase_map()[product_id]["price_paid"] == 1_199.0


def test_upsert_purchase_rejects_invalid_inputs(db: Database):
    product_id = int(db.list_products()[0]["id"])
    with pytest.raises(ValueError, match="greater than zero"):
        db.upsert_purchase(product_id, 0)
    with pytest.raises(ValueError, match="Product not found"):
        db.upsert_purchase(999_999, 100.0)
    with pytest.raises(ValueError, match="future"):
        db.upsert_purchase(
            product_id, 100.0, purchased_on=date.today() + timedelta(days=2)
        )


def test_remove_purchase_returns_true_only_once(db: Database):
    product_id = int(db.list_products()[0]["id"])
    db.upsert_purchase(product_id, 500.0)
    assert db.remove_purchase(product_id) is True
    assert db.remove_purchase(product_id) is False


def test_build_purchase_view_flags_below_and_at_current():
    below = build_purchase_view(
        {
            "product_id": 1,
            "price_paid": 900.0,
            "purchased_on": "2026-01-01",
            "retailer": "MegaMart",
            "notes": "",
        },
        1_000.0,
        {"minimum_price": 850.0},
    )
    assert below is not None
    assert below["difference_vs_current"] == -100.0
    assert below["below_current"] is True
    assert below["at_current"] is False
    assert below["at_or_below_low"] is False

    at_current = build_purchase_view(
        {
            "product_id": 2,
            "price_paid": 1_000.0,
            "purchased_on": "2026-01-01",
            "retailer": "",
            "notes": "",
        },
        1_000.0,
    )
    assert at_current["at_current"] is True

    assert build_purchase_view(None, 1_000.0) is None
    assert build_purchase_view({"price_paid": 0}, 1_000.0) is None


def test_summarise_purchases_aggregates_tracked_snapshots(db: Database):
    products = db.list_products()[:2]
    first_id, second_id = int(products[0]["id"]), int(products[1]["id"])
    db.upsert_purchase(first_id, 1_000.0, purchased_on=date(2026, 1, 1))
    db.upsert_purchase(second_id, 2_000.0, purchased_on=date(2026, 1, 2))

    summary = summarise_purchases(build_all_snapshots(db))
    assert summary["count"] == 2
    assert summary["total_paid"] == 3_000.0
    assert summary["products"]
    assert all(item.get("purchase") for item in summary["products"])
    assert summary["current_value"] > 0
    assert summary["difference"] == round(
        summary["current_value"] - summary["total_paid"], 2
    )

    empty = summarise_purchases([{"id": 1, "purchase": None}])
    assert empty["count"] == 0
    assert empty["total_paid"] == 0
    assert empty["difference"] == 0


# ----------------------------------------------------------------------
# Alerts
# ----------------------------------------------------------------------


def test_sync_target_alerts_creates_one_alert_and_dedupes(db: Database):
    # Start from an empty watchlist so only the target set here can alert.
    # remove_watchlist takes the product id, not the watchlist row id.
    for item in db.get_watchlist_details():
        db.remove_watchlist(int(item["product_id"]))
    assert db.get_watchlist_details() == []

    product = db.list_products()[0]
    product_id = int(product["id"])
    current = float(product["current_price"])
    # A target at or above the current price counts as reached.
    db.upsert_watchlist(product_id, current + 500.0)

    snapshots = build_all_snapshots(db)
    assert sync_target_alerts(db, snapshots) == 1

    alerts = db.get_alerts()
    target_alerts = [a for a in alerts if a["kind"] == "target_reached"]
    assert len(target_alerts) == 1
    assert target_alerts[0]["product_id"] == product_id
    assert "synthetic" in target_alerts[0]["message"].lower()

    # Re-running must not duplicate the same event.
    assert sync_target_alerts(db, snapshots) == 0
    assert len(db.get_alerts()) == 1

    counts = db.get_alert_counts()
    assert counts["unread"] == 1
    assert counts["target"] == 1
    assert counts["active"] == 1


def test_alert_read_dismiss_and_clear_flows(db: Database):
    product_id = int(db.list_products()[0]["id"])
    assert db.create_alert(
        kind="price_drop",
        title="Price dropped",
        message="A test price drop.",
        product_id=product_id,
        dedupe_key="price_drop:test:1",
    )
    # Duplicate dedupe key is ignored.
    assert not db.create_alert(
        kind="price_drop",
        title="Price dropped again",
        product_id=product_id,
        dedupe_key="price_drop:test:1",
    )

    alert = db.get_alerts()[0]
    alert_id = int(alert["id"])

    assert db.mark_alert_read(alert_id) is True
    assert db.mark_alert_read(alert_id) is False
    assert db.count_unread_alerts() == 0

    assert db.mark_alert_read(alert_id, read=False) is True
    assert db.count_unread_alerts() == 1
    assert db.mark_all_alerts_read() == 1
    assert db.count_unread_alerts() == 0

    assert db.dismiss_alert(alert_id) is True
    assert db.dismiss_alert(alert_id) is False
    assert db.get_alerts() == []
    assert len(db.get_alerts(include_dismissed=True)) == 1

    counts = db.get_alert_counts()
    assert counts["dismissed"] == 1
    assert db.clear_dismissed_alerts() == 1
    assert db.get_alert_counts()["total"] == 0


def test_record_refresh_alerts_detects_price_drop_and_stock_change():
    db = _FakeAlertDb()
    before = {
        "id": 1,
        "name": "Acme Headphones",
        "is_live": True,
        "current_price": 2_000.0,
        "live": {"status": "ok"},
        "offers": [
            {"is_live": True, "in_stock": True, "total_price": 2_000.0}
        ],
    }
    after = {
        "id": 1,
        "name": "Acme Headphones",
        "is_live": True,
        "current_price": 1_700.0,
        "live": {"status": "ok"},
        "offers": [
            {"is_live": True, "in_stock": False, "total_price": 1_700.0}
        ],
        "watchlist": None,
    }
    created = record_refresh_alerts(db, before, after)
    kinds = {alert["kind"] for alert in db.alerts}
    assert created >= 2
    assert "price_drop" in kinds
    assert "out_of_stock" in kinds
    # Dedupe: a second identical comparison creates nothing new.
    assert record_refresh_alerts(db, before, after) == 0


def test_record_refresh_alerts_marks_quote_attention_and_recovery():
    db = _FakeAlertDb()
    ok = {
        "id": 2,
        "name": "Acme Monitor",
        "is_live": True,
        "current_price": 5_000.0,
        "live": {"status": "ok"},
        "offers": [{"is_live": True, "in_stock": True}],
    }
    stale = {
        "id": 2,
        "name": "Acme Monitor",
        "is_live": True,
        "current_price": 5_000.0,
        "live": {"status": "stale"},
        "offers": [{"is_live": True, "in_stock": True}],
        "watchlist": None,
    }
    assert record_refresh_alerts(db, ok, stale) == 1
    assert db.alerts[0]["kind"] == "quote_attention"
    assert record_refresh_alerts(db, stale, ok) == 1
    assert {alert["kind"] for alert in db.alerts} == {
        "quote_attention",
        "quote_recovered",
    }


def test_record_import_alert_for_out_of_stock_and_non_live():
    db = _FakeAlertDb()
    out_of_stock = {
        "id": 3,
        "name": "Acme Camera",
        "is_live": True,
        "current_price": 9_000.0,
        "live": {"status": "out_of_stock"},
        "offers": [{"is_live": True, "in_stock": False}],
        "watchlist": None,
    }
    assert record_import_alert(db, out_of_stock) == 1
    assert db.alerts[0]["kind"] == "out_of_stock"
    # Re-importing the same product must not duplicate the alert.
    assert record_import_alert(db, out_of_stock) == 0
    # Demo products never create import alerts.
    demo = {"id": 4, "name": "Demo Widget", "is_live": False, "offers": []}
    assert record_import_alert(db, demo) == 0


class _FakeAlertDb:
    """Minimal Database stand-in that records alerts in memory."""

    def __init__(self) -> None:
        self.alerts: list[dict] = []
        self._keys: set[str] = set()

    def create_alert(
        self,
        *,
        kind: str,
        title: str,
        message: str = "",
        product_id: int | None = None,
        dedupe_key: str = "",
        created_at: str | None = None,
    ) -> bool:
        key = dedupe_key.strip() or f"{kind}:{product_id or 0}:{title}"
        if key in self._keys:
            return False
        self._keys.add(key)
        self.alerts.append(
            {
                "id": len(self.alerts) + 1,
                "kind": kind,
                "title": title,
                "message": message,
                "product_id": product_id,
                "dedupe_key": key,
            }
        )
        return True


# ----------------------------------------------------------------------
# Stale-only refresh
# ----------------------------------------------------------------------


def test_refresh_stale_skips_fresh_products(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service, product_id = _import_live(db, settings, monkeypatch)

    calls: list[str] = []

    def track(target: str) -> LiveQuote:
        calls.append(target)
        return _quote("https://www.amazon.in/dp/B0TEST1234")

    monkeypatch.setattr(service, "_scrape", track)

    result = service.refresh_stale()
    assert result["total"] == 1
    assert result["skipped"] == 1
    assert result["refreshed"] == 0
    assert calls == []
    assert result["products"][0]["skipped"] is True


def test_refresh_stale_refreshes_stale_products(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service, product_id = _import_live(db, settings, monkeypatch)

    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(
        timespec="seconds"
    )
    db.update_live_product(
        product_id, live_status="stale", last_success_at=old
    )
    # Sources must also look stale so the product needs a refresh.
    source = db.get_live_sources(product_id)[0]
    db.upsert_live_source(
        product_id,
        url=str(source["url"]),
        retailer=str(source["retailer"]),
        label=str(source.get("label") or ""),
        checked_at=old,
        status="stale",
        error="",
        title=str(source.get("last_title") or ""),
        price=float(source.get("last_price") or 0),
        list_price=None,
        currency=str(source.get("last_currency") or "INR"),
        success_at="",
    )

    calls: list[str] = []

    def track(target: str) -> LiveQuote:
        calls.append(target)
        return _quote("https://www.amazon.in/dp/B0TEST1234", price=1_799.0)

    monkeypatch.setattr(service, "_scrape", track)

    result = service.refresh_stale()
    assert result["total"] == 1
    assert result["skipped"] == 0
    assert result["refreshed"] == 1
    assert calls  # the scraper was actually invoked
    refreshed = db.get_product(product_id)
    assert refreshed["current_price"] == 1_799.0
    assert refreshed["live_status"] == "ok"


def test_refresh_all_only_stale_flag_is_respected(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service, product_id = _import_live(db, settings, monkeypatch)

    calls: list[str] = []
    monkeypatch.setattr(
        service, "_scrape", lambda target: calls.append(target) or _quote(target)
    )

    # Fresh product: refresh_all without only_stale still checks it.
    plain = service.refresh_all()
    assert plain["total"] == 1
    assert plain["refreshed"] == 1
    assert len(calls) == 1

    # Now stale again, only_stale should check it once.
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(
        timespec="seconds"
    )
    db.update_live_product(product_id, last_success_at=old, live_status="stale")
    calls.clear()
    stale_only = service.refresh_all(only_stale=True)
    assert stale_only["total"] == 1
    assert stale_only["skipped"] == 0
    assert len(calls) == 1


def test_refresh_stale_with_no_live_products_returns_zero(db: Database, settings: Settings):
    service = LiveService(db, settings)
    result = service.refresh_stale()
    assert result["total"] == 0
    assert result["refreshed"] == 0
    assert result["skipped"] == 0
