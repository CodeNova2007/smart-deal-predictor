"""Offline tests for live quote parsing, provenance, and refresh behaviour."""

from __future__ import annotations

import json

import pytest

from smartdeal.analytics import build_product_snapshot
from smartdeal.config import Settings
from smartdeal.database import Database
from smartdeal.live import LiveQuote, LiveService, ScrapeError
from smartdeal.live.seed import (
    RECORDED_QUOTES,
    _RETIRED_QUOTES,
    seed_recorded_live_quotes,
)
from smartdeal.live.scraper import (
    is_product_page_url,
    parse_product_page,
    validate_product_page_url,
    validate_public_url,
)
from smartdeal.live.status import is_stale, source_view


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


def test_product_page_validation_rejects_search_and_category_pages():
    assert is_product_page_url("https://www.amazon.in/dp/B0TEST1234")
    assert is_product_page_url("https://www.flipkart.com/acme-headphones/p/itm123")
    assert not is_product_page_url("https://www.amazon.in/s?k=headphones")
    assert not is_product_page_url("https://www.flipkart.com/search?q=headphones")
    assert not is_product_page_url("https://shop.example.com/category/audio")
    assert not is_product_page_url("https://shop.example.com/products")

    with pytest.raises(ScrapeError) as error:
        validate_product_page_url("https://www.amazon.in/s?k=headphones")
    assert error.value.code == "not_product_page"
    assert "product" in error.value.message.lower()


def test_public_url_validation_blocks_local_addresses():
    with pytest.raises(ScrapeError) as error:
        validate_public_url("http://localhost:8501/dp/B0TEST")
    assert error.value.code == "blocked_address"
    with pytest.raises(ScrapeError):
        validate_public_url("file:///etc/passwd")
    with pytest.raises(ScrapeError):
        validate_public_url("https://user:pass@example.com/dp/B0TEST")


def test_generic_json_ld_product_is_parsed_without_network():
    payload = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Acme Wireless Headphones",
        "brand": {"@type": "Brand", "name": "Acme"},
        "description": "Noise-cancelling headphones.",
        "offers": {
            "@type": "Offer",
            "price": "1,999.00",
            "priceCurrency": "INR",
            "listPrice": "2,499.00",
            "availability": "https://schema.org/InStock",
            "seller": {"@type": "Organization", "name": "Acme Store"},
        },
    }
    html = (
        "<html><head><title>Acme</title>"
        f'<script type="application/ld+json">{json.dumps(payload)}</script>'
        "</head><body></body></html>"
    )
    quote = parse_product_page(
        html, "https://shop.example.com/products/acme-headphones"
    )
    assert quote.title == "Acme Wireless Headphones"
    assert quote.price == 1_999.0
    assert quote.list_price == 2_499.0
    assert quote.currency == "INR"
    assert quote.seller == "Acme Store"
    assert quote.in_stock is True
    assert quote.extraction_method == "json-ld"


def test_amazon_selectors_extract_price_mrp_seller_and_stock():
    html = """
    <html><body>
      <span id="productTitle">Acme Wireless Headphones</span>
      <div id="corePrice_feature_div">
        <span class="a-price"><span class="a-offscreen">₹1,999.00</span></span>
      </div>
      <span class="a-price a-text-price"><span class="a-offscreen">₹2,499.00</span></span>
      <div id="availability">In stock</div>
      <span id="sellerProfileTriggerId">Acme Store</span>
      <span id="bylineInfo">Visit the Acme Store</span>
    </body></html>
    """
    quote = parse_product_page(html, "https://www.amazon.in/dp/B0TEST1234")
    assert quote.title == "Acme Wireless Headphones"
    assert quote.price == 1_999.0
    assert quote.list_price == 2_499.0
    assert quote.retailer == "Amazon.in"
    assert quote.seller == "Acme Store"
    assert quote.in_stock is True
    assert quote.extraction_method == "amazon"


def test_flipkart_selectors_extract_price_and_seller():
    html = """
    <html><body>
      <span class="B_NuCI">Acme Wireless Headphones</span>
      <div class="_30jeq3 _16Jk6d">₹12,499</div>
      <div class="_3I9_wc _2p6lqe">₹15,999</div>
      <div id="sellerName"><span>Seller: RetailCo</span></div>
      <div>In stock</div>
    </body></html>
    """
    quote = parse_product_page(
        html, "https://www.flipkart.com/acme-headphones/p/itm123"
    )
    assert quote.title == "Acme Wireless Headphones"
    assert quote.price == 12_499.0
    assert quote.list_price == 15_999.0
    assert quote.retailer == "Flipkart"
    assert quote.seller == "RetailCo"
    assert quote.in_stock is True


def test_blocked_and_priceless_pages_are_reported_not_guessed():
    blocked = "<html><body>Please complete the CAPTCHA to continue</body></html>"
    with pytest.raises(ScrapeError) as error:
        parse_product_page(blocked, "https://www.amazon.in/dp/B0TEST1234")
    assert error.value.code == "blocked"

    no_price = "<html><body><h1>Acme Headphones</h1></body></html>"
    with pytest.raises(ScrapeError) as error:
        parse_product_page(no_price, "https://www.amazon.in/dp/B0TEST1234")
    assert error.value.code == "price_not_found"


def test_stale_helpers_label_missing_and_old_quotes():
    assert is_stale("", 24) is True
    assert is_stale("2020-01-01T00:00:00+00:00", 24) is True
    view = source_view(
        {
            "last_status": "ok",
            "last_success_at": "2020-01-01T00:00:00+00:00",
            "last_price": 100,
        }
    )
    assert view["status"] == "stale"
    assert view["stale"] is True
    assert view["status_label"] == "Stale quote"


def test_service_imports_quote_and_records_one_daily_observation(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    url = "https://www.amazon.in/dp/B0TEST1234"
    quote = _quote(url)
    monkeypatch.setattr(service, "_scrape", lambda target: quote)

    result = service.import_product(url, label="Test source")
    assert result["created"] is True
    product_id = int(result["product_id"])
    product = db.get_product(product_id)
    assert product is not None
    assert product["data_origin"] == "live"
    assert product["current_price"] == 1_999.0
    assert product["list_price"] == 2_499.0
    assert product["source_url"] == url
    assert len(db.get_price_history(product_id)) == 1
    sources = db.get_live_sources(product_id)
    assert len(sources) == 1
    assert sources[0]["last_price"] == 1_999.0
    assert len(db.get_offers(product_id)) == 1

    snapshot = build_product_snapshot(db.get_bundle(product_id))
    assert snapshot["is_live"] is True
    assert snapshot["live"]["status"] == "ok"
    assert snapshot["has_list_price"] is True
    assert snapshot["offers"][0]["is_live"] is True
    assert snapshot["offers"][0]["retailer"] == "Amazon.in"


def test_service_keeps_last_quote_on_refresh_failure(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    url = "https://www.amazon.in/dp/B0TEST1234"
    monkeypatch.setattr(service, "_scrape", lambda target: _quote(url))
    product_id = int(service.import_product(url)["product_id"])

    def fail(target: str) -> LiveQuote:
        raise ScrapeError("The retailer blocked the request.", code="blocked")

    monkeypatch.setattr(service, "_scrape", fail)
    result = service.refresh_product(product_id)
    assert result["ok"] is False

    product = db.get_product(product_id)
    assert product is not None
    assert product["current_price"] == 1_999.0
    assert product["live_status"] == "stale"
    assert "blocked" in product["live_error"].lower()
    assert len(db.get_price_history(product_id)) == 1
    source = db.get_live_sources(product_id)[0]
    assert source["last_status"] == "blocked"
    assert source["last_price"] == 1_999.0
    assert source["last_success_at"]


def test_service_refreshes_a_live_product_with_no_sources(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    url = "https://www.amazon.in/dp/B0TEST1234"
    monkeypatch.setattr(service, "_scrape", lambda target: _quote(url))
    product_id = int(service.import_product(url)["product_id"])

    # Simulate the user detaching every source URL from the live product.
    for source in db.get_live_sources(product_id):
        assert db.remove_live_source(int(source["id"])) is True
    assert db.get_live_sources(product_id) == []

    result = service.refresh_product(product_id)
    assert result["ok"] is False
    assert result["status"] == "no_sources"
    assert result["source_count"] == 0
    assert result["errors"] == ["No live source URLs are attached to this product."]

    product = db.get_product(product_id)
    assert product is not None
    assert product["live_status"] == "no_sources"
    # The last successful quote and its history are kept.
    assert product["current_price"] == 1_999.0
    assert len(db.get_price_history(product_id)) == 1

    stale = service.refresh_stale()
    assert stale["total"] == 1
    assert stale["failed"] == 1
    assert stale["products"][0]["status"] == "no_sources"


def test_recorded_live_quote_seed_covers_another_marketplace():
    others = [
        quote
        for quote in RECORDED_QUOTES
        if quote.retailer not in {"Amazon.in", "Flipkart"}
    ]
    assert len(others) >= 15
    assert {quote.retailer for quote in others} == {"Reliance Digital", "Myntra"}
    assert all(quote.price > 0 and quote.in_stock for quote in others)
    assert len({quote.url for quote in others}) == len(others)
    assert len({quote.name for quote in others}) == len(others)


def test_recorded_live_quote_seed_contains_fashion_dresses():
    dresses = [quote for quote in RECORDED_QUOTES if quote.category == "Fashion"]
    assert len(dresses) >= 10
    assert all(quote.retailer == "Myntra" for quote in dresses)
    assert all(quote.price > 0 and quote.in_stock for quote in dresses)
    assert all(quote.emoji == "👗" for quote in dresses)
    assert len({quote.url for quote in dresses}) == len(dresses)


def test_recorded_live_quote_seed_is_idempotent_and_keeps_original_times(db: Database):
    assert seed_recorded_live_quotes(db) == len(RECORDED_QUOTES)
    assert seed_recorded_live_quotes(db) == 0

    live = db.get_live_products()
    assert len(live) == len(RECORDED_QUOTES)
    for quote in RECORDED_QUOTES:
        source = db.get_live_source_by_url(quote.url)
        assert source is not None
        product = db.get_product(int(source["product_id"]))
        assert product is not None
        assert product["data_origin"] == "live"
        assert product["current_price"] == quote.price
        assert product["last_checked_at"] == quote.recorded_at
        assert product["last_success_at"] == quote.recorded_at
        assert source["last_price"] == quote.price
        assert source["last_success_at"] == quote.recorded_at
        assert source["last_status"] == "ok"

        history = db.get_price_history(int(product["id"]))
        assert len(history) == 1
        assert history[0]["observed_on"] == quote.recorded_at[:10]
        assert history[0]["price"] == quote.price


def test_recorded_live_quote_seed_runs_once_and_respects_removal(db: Database):
    assert seed_recorded_live_quotes(db) == len(RECORDED_QUOTES)
    product = db.get_live_products()[0]
    assert db.delete_product(int(product["id"])) is True

    assert seed_recorded_live_quotes(db) == 0
    assert len(db.get_live_products()) == len(RECORDED_QUOTES) - 1


def test_recorded_live_quote_seed_skips_an_already_imported_url(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    # The same Amazon product can be imported with referral parameters; the
    # seed must recognise the ASIN and not create a second copy.
    url = (
        "https://www.amazon.in/boAt-Airdopes-Pocketable-Controls-Bluetooth/"
        "dp/B0GZN2M7T7/ref=sr_1_7?keywords=earpods"
    )
    monkeypatch.setattr(service, "_scrape", lambda target: _quote(url))
    imported = service.import_product(url)
    assert imported["created"] is True

    assert seed_recorded_live_quotes(db) == len(RECORDED_QUOTES) - 1
    assert seed_recorded_live_quotes(db) == 0


def test_seed_cleanup_drops_retired_quote_during_marker_bump(db: Database):
    url, recorded_at = _RETIRED_QUOTES[0]
    product_id = db.create_product(
        name="Retired Seed Product",
        brand="Asus",
        category="Laptops",
        description="",
        emoji="💻",
        current_price=70990.0,
        list_price=0,
        currency="INR",
        data_origin="live",
        source_url=url,
        last_checked_at=recorded_at,
        last_success_at=recorded_at,
        live_status="ok",
        live_error="",
    )
    db.upsert_live_source(
        product_id,
        url=url,
        retailer="Reliance Digital",
        checked_at=recorded_at,
        success_at=recorded_at,
        status="ok",
        error="",
        title="Retired Seed Product",
        price=70990.0,
        list_price=None,
        currency="INR",
    )
    # Simulate a database seeded by the previous seed version.
    with db.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES "
            "('recorded_live_quotes_v2', '1')"
        )
        connection.commit()

    assert seed_recorded_live_quotes(db) == len(RECORDED_QUOTES)
    assert db.get_live_source_by_url(url) is None
    assert db.get_product(product_id) is None


def test_seed_cleanup_spares_a_refreshed_retired_product(db: Database):
    url, recorded_at = _RETIRED_QUOTES[0]
    product_id = db.create_product(
        name="Retired Seed Product",
        brand="Asus",
        category="Laptops",
        description="",
        emoji="💻",
        current_price=69990.0,
        list_price=0,
        currency="INR",
        data_origin="live",
        source_url=url,
        last_checked_at="2026-10-28T12:00:00+00:00",
        last_success_at="2026-10-28T12:00:00+00:00",
        live_status="ok",
        live_error="",
    )
    db.upsert_live_source(
        product_id,
        url=url,
        retailer="Reliance Digital",
        checked_at="2026-10-28T12:00:00+00:00",
        success_at="2026-10-28T12:00:00+00:00",
        status="ok",
        error="",
        title="Retired Seed Product",
        price=69990.0,
        list_price=None,
        currency="INR",
    )
    with db.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES "
            "('recorded_live_quotes_v2', '1')"
        )
        connection.commit()

    assert seed_recorded_live_quotes(db) == len(RECORDED_QUOTES)
    # The product was refreshed, so the cleanup must not touch it.
    assert db.get_product(product_id) is not None
    assert db.get_live_source_by_url(url) is not None
    assert len(db.get_live_products()) == len(RECORDED_QUOTES) + 1


def test_recorded_live_quote_can_be_refreshed(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    seed_recorded_live_quotes(db)
    quote = RECORDED_QUOTES[0]
    source = db.get_live_source_by_url(quote.url)
    assert source is not None
    service = LiveService(db, settings)
    monkeypatch.setattr(
        service,
        "_scrape",
        lambda target: _quote(
            quote.url, title=quote.name, price=749.0, list_price=quote.list_price
        ),
    )

    result = service.refresh_source(int(source["id"]))
    assert result["ok"] is True
    product = db.get_product(int(source["product_id"]))
    assert product is not None
    assert product["current_price"] == 749.0
    assert product["live_status"] in {"ok", "partial"}


def test_service_adds_a_second_source_and_uses_lowest_in_stock_quote(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    amazon = "https://www.amazon.in/dp/B0TEST1234"
    flipkart = "https://www.flipkart.com/acme-headphones/p/itm123"
    first = _quote(amazon)
    second = _quote(
        flipkart,
        retailer="Flipkart",
        seller="RetailCo",
        price=1_799.0,
        list_price=2_299.0,
    )
    monkeypatch.setattr(service, "_scrape", lambda target: first)
    product_id = int(service.import_product(amazon)["product_id"])

    monkeypatch.setattr(service, "_scrape", lambda target: second)
    result = service.add_source(product_id, flipkart)
    assert result["ok"] is True

    product = db.get_product(product_id)
    assert product is not None
    assert product["current_price"] == 1_799.0
    assert len(db.get_live_sources(product_id)) == 2
    assert len(db.get_offers(product_id)) == 2
    # Both quotes land on the same day, so live history keeps one point.
    assert len(db.get_price_history(product_id)) == 1
    assert db.get_price_history(product_id)[0]["price"] == 1_799.0


def test_service_rejects_non_inr_quotes_without_saving(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    url = "https://www.amazon.in/dp/B0TEST1234"
    monkeypatch.setattr(
        service, "_scrape", lambda target: _quote(url, currency="USD")
    )
    before = len(db.list_products())
    with pytest.raises(ScrapeError) as error:
        service.import_product(url)
    assert error.value.code == "unsupported_currency"
    assert len(db.list_products()) == before
    assert db.get_live_source_by_url(url) is None


def test_service_removes_a_source_and_recomputes_from_remaining_quotes(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    amazon = "https://www.amazon.in/dp/B0TEST1234"
    flipkart = "https://www.flipkart.com/acme-headphones/p/itm123"
    monkeypatch.setattr(service, "_scrape", lambda target: _quote(amazon))
    product_id = int(service.import_product(amazon)["product_id"])
    monkeypatch.setattr(
        service,
        "_scrape",
        lambda target: _quote(
            flipkart,
            retailer="Flipkart",
            seller="RetailCo",
            price=1_799.0,
            list_price=2_299.0,
        ),
    )
    service.add_source(product_id, flipkart)

    source = next(
        item
        for item in db.get_live_sources(product_id)
        if item["url"] == flipkart
    )
    result = service.remove_source(int(source["id"]))
    assert result["ok"] is True
    product = db.get_product(product_id)
    assert product is not None
    assert product["current_price"] == 1_999.0
    assert len(db.get_live_sources(product_id)) == 1
    assert len(db.get_offers(product_id)) == 1


def test_service_removes_a_live_product_and_its_records(
    db: Database, settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    service = LiveService(db, settings)
    url = "https://www.amazon.in/dp/B0TEST1234"
    monkeypatch.setattr(service, "_scrape", lambda target: _quote(url))
    product_id = int(service.import_product(url)["product_id"])
    db.upsert_watchlist(product_id, 1_500.0)
    assert db.get_watchlist_item(product_id) is not None

    result = service.remove_product(product_id)

    assert result["ok"] is True
    assert "Removed" in result["message"]
    assert db.get_product(product_id) is None
    assert db.get_price_history(product_id) == []
    assert db.get_offers(product_id) == []
    assert db.get_live_sources(product_id) == []
    assert db.get_watchlist_item(product_id) is None
    assert len(db.list_products()) == 40


def test_service_refuses_to_remove_a_demo_product(
    db: Database, settings: Settings
):
    demo = next(
        item for item in db.list_products() if item["data_origin"] == "demo"
    )
    with pytest.raises(ValueError, match="(?i)only live-imported products"):
        LiveService(db, settings).remove_product(int(demo["id"]))
    assert db.get_product(int(demo["id"])) is not None


def test_service_reports_a_missing_product_on_remove(
    db: Database, settings: Settings
):
    with pytest.raises(ValueError, match="not found"):
        LiveService(db, settings).remove_product(999_999)


def test_service_does_not_attach_live_sources_to_demo_products(
    db: Database, settings: Settings
):
    demo = next(
        item for item in db.list_products() if item["data_origin"] == "demo"
    )
    service = LiveService(db, settings)
    with pytest.raises(ValueError, match="(?i)demo products"):
        service.add_source(
            int(demo["id"]),
            "https://www.amazon.in/dp/B0TEST1234",
        )
