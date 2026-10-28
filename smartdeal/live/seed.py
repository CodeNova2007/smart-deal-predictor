"""Recorded live quotes that keep the public demo populated.

Every entry below is a real reading captured from the named public product
page at ``recorded_at``. Nothing here is synthesised: the price, seller,
availability, and timestamp are the values the page showed when it was read.

Community Cloud wipes local files when an app sleeps or redeploys, so a quote
imported through the UI would disappear before a presentation. Seeding the
recorded readings keeps the live workspace populated; the normal freshness
rules still mark them stale once they age out, and the user can refresh or
remove them at any time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ..database import Database

_AMAZON_ASIN = re.compile(r"/(?:dp|gp/aw/d)/([A-Z0-9]{10})(?:[/?]|$)", re.I)
_FLIPKART_ID = re.compile(r"/p/(itm[a-z0-9]+)", re.I)


@dataclass(frozen=True)
class RecordedQuote:
    """One real marketplace reading, kept with its original timestamp."""

    url: str
    retailer: str
    name: str
    brand: str
    category: str
    emoji: str
    price: float
    seller: str
    in_stock: bool
    availability: str
    recorded_at: str
    list_price: float | None = None


RECORDED_QUOTES: tuple[RecordedQuote, ...] = (
    RecordedQuote(
        url="https://www.amazon.in/dp/B0GZN2M7T7",
        retailer="Amazon.in",
        name="boAt Airdopes Joy v2 TWS Earbuds",
        brand="boAt",
        category="Audio",
        emoji="🎧",
        price=799.0,
        list_price=3490.0,
        seller="Clicktech Retail Private Ltd",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T01:06:17+00:00",
    ),
    RecordedQuote(
        url="https://www.amazon.in/gp/aw/d/B0H4ZB5NQV",
        retailer="Amazon.in",
        name="boAt Airdopes ProClip Open-Ear Earbuds",
        brand="boAt",
        category="Audio",
        emoji="🎧",
        price=1799.0,
        list_price=4999.0,
        seller="Clicktech Retail Private Ltd",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T01:06:19+00:00",
    ),
    RecordedQuote(
        url=(
            "https://www.flipkart.com/boat-rockerz-450-bluetooth-headset/"
            "p/itmfema4m9dvzgkz"
        ),
        retailer="Flipkart",
        name="boAt Rockerz 450 Bluetooth Headset",
        brand="boAt",
        category="Audio",
        emoji="🎧",
        price=1899.0,
        seller="Flipkart",
        in_stock=True,
        availability="Availability not confirmed",
        recorded_at="2026-10-28T01:05:42+00:00",
    ),
    RecordedQuote(
        url=(
            "https://www.flipkart.com/sony-wh-ch520-50-hrs-playtime-dsee-upscale-"
            "multipoint-connection-dual-pairing-bluetooth/p/itm29e4c2b8a0883"
        ),
        retailer="Flipkart",
        name="Sony WH-CH520 Wireless Headphones",
        brand="Sony",
        category="Audio",
        emoji="🎧",
        price=2990.0,
        seller="Flipkart",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T03:38:36+00:00",
    ),
)


def _recorded_day(quote: RecordedQuote) -> date:
    return date.fromisoformat(quote.recorded_at[:10])


def _product_key(url: str) -> tuple[str, str]:
    """Return a stable marketplace product id for duplicate detection.

    Amazon links come in several shapes (``/dp/ASIN``, ``/gp/aw/d/ASIN``, with
    or without referral parameters) and Flipkart links carry an ``itm…`` id.
    Matching on the id keeps the seed from re-adding a product the user has
    already imported under a different URL form.
    """

    amazon = _AMAZON_ASIN.search(url or "")
    if amazon:
        return "amazon", amazon.group(1).upper()
    flipkart = _FLIPKART_ID.search(url or "")
    if flipkart:
        return "flipkart", flipkart.group(1).lower()
    return "url", (url or "").strip().lower()


def seed_recorded_live_quotes(db: Database) -> int:
    """Attach the recorded quotes that are not already present.

    The seed is idempotent. It skips a URL that is already attached and a
    product whose name already exists, so a user's import or removal is not
    overwritten. Returns the number of products added.
    """

    existing_products = db.get_live_products()
    existing_names = {str(product.get("name") or "") for product in existing_products}
    existing_keys = {
        _product_key(str(source.get("url") or ""))
        for product in existing_products
        for source in db.get_live_sources(int(product["id"]))
    }
    added = 0
    for quote in RECORDED_QUOTES:
        if db.get_live_source_by_url(quote.url) is not None:
            continue
        if _product_key(quote.url) in existing_keys:
            continue
        if quote.name in existing_names:
            continue

        day = _recorded_day(quote)
        product_id = db.create_product(
            name=quote.name,
            brand=quote.brand,
            category=quote.category,
            description=(
                f"Recorded live quote from {quote.retailer} on "
                f"{quote.recorded_at[:10]}. Refresh the source to check the "
                "current price."
            ),
            emoji=quote.emoji,
            current_price=quote.price,
            list_price=quote.list_price or 0,
            currency="INR",
            data_origin="live",
            source_url=quote.url,
            last_checked_at=quote.recorded_at,
            last_success_at=quote.recorded_at,
            live_status="ok",
            live_error="",
        )
        try:
            db.upsert_live_source(
                product_id,
                url=quote.url,
                retailer=quote.retailer,
                checked_at=quote.recorded_at,
                success_at=quote.recorded_at,
                status="ok",
                error="",
                title=quote.name,
                price=quote.price,
                list_price=quote.list_price,
                currency="INR",
            )
            db.upsert_live_offer(
                product_id,
                source_url=quote.url,
                retailer=quote.retailer,
                seller=quote.seller,
                price=quote.price,
                list_price=quote.list_price,
                in_stock=quote.in_stock,
                availability=quote.availability,
                checked_on=day,
            )
            db.replace_live_observation(
                product_id,
                quote.price,
                observed_on=day,
                source=f"Live quote · {quote.retailer}",
            )
        except Exception:
            db.delete_product(product_id)
            raise

        existing_names.add(quote.name)
        existing_keys.add(_product_key(quote.url))
        added += 1
    return added
