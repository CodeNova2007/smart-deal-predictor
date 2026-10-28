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
_SEED_MARKER = "recorded_live_quotes_v2"


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
        url="https://www.reliancedigital.in/product/noise-three-wireless-headphone-jet-black-lpm6ze-7534896",
        retailer="Reliance Digital",
        name="Noise Three Wireless Headphones",
        brand="Noise",
        category="Audio",
        emoji="🎧",
        price=1799.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:12+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/hp-200-wireless-over-ear-active-noise-cancellation-headphone-with-mic-mi2xqo-9580001",
        retailer="Reliance Digital",
        name="HP 200 ANC Wireless Headphones",
        brand="HP",
        category="Audio",
        emoji="🎧",
        price=999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:15+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/noise-airwave-max-5-overhead-wireless-headphone-carbon-black-m6uox5-8881059",
        retailer="Reliance Digital",
        name="Noise Airwave Max 5 Headphones",
        brand="Noise",
        category="Audio",
        emoji="🎧",
        price=4999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:18+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/jbl-tune-770nc-over-ear-wireless-headphone-with-mic-blue-ljimat",
        retailer="Reliance Digital",
        name="JBL Tune 770NC Wireless Headphones",
        brand="JBL",
        category="Audio",
        emoji="🎧",
        price=4999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:21+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/boat-rockerz-425-bluetooth-wireless-on-ear-headphones-signature-sound-enx-tech-asap-charge-25-h-playtime-bluetooth-v52-dual-pairing-with-mic-active-black-m0dwey-8536583",
        retailer="Reliance Digital",
        name="boAt Rockerz 425 Wireless Headphones",
        brand="boAt",
        category="Audio",
        emoji="🎧",
        price=1399.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:30+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/vivo-y19e-5g-64-gb-4-gb-ram-titanium-silver-mobile-phone-m8sfo3-9045979",
        retailer="Reliance Digital",
        name="Vivo Y19e 5G Smartphone",
        brand="Vivo",
        category="Smartphones",
        emoji="📱",
        price=9999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:33+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/realme-narzo-70-turbo-5g-128-gb-6-gb-ram-turbo-green-mobile-phone-m6uoqt-8881056",
        retailer="Reliance Digital",
        name="Realme Narzo 70 Turbo 5G",
        brand="Realme",
        category="Smartphones",
        emoji="📱",
        price=16999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:34+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/poco-x7-5g-256-gb-8-gb-ram-yellow-mobile-phone-m5qo3h-8834062",
        retailer="Reliance Digital",
        name="POCO X7 5G Smartphone",
        brand="POCO",
        category="Smartphones",
        emoji="📱",
        price=19999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:37+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/samsung-galaxy-f17-5g-128-gb-8-gb-ram-lavender-mobile-phone-mg4xb8-9490110",
        retailer="Reliance Digital",
        name="Samsung Galaxy F17 5G",
        brand="Samsung",
        category="Smartphones",
        emoji="📱",
        price=20999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:38+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/oppo-k14-5g-128-gb-6-gb-ram-icy-blue-mobile-phone-mmyf4x-9989643",
        retailer="Reliance Digital",
        name="OPPO K14 5G Smartphone",
        brand="OPPO",
        category="Smartphones",
        emoji="📱",
        price=25999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:42+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/asus-tuf-a15-fa506ncg-hn200ws-gaming-laptop-amd-ryzen-7-7445hs16-gb512-gb-ssd4-gb-nvidia-geforce-rtxwindows-11microsoft-office-home-2024full-hd-3962-cm-156-inch-graphite-black-mel0pj-9345133",
        retailer="Reliance Digital",
        name="Asus TUF A15 Gaming Laptop",
        brand="Asus",
        category="Laptops",
        emoji="💻",
        price=70990.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:15:55+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/lenovo-ideapad-slim3-8hin-standard-laptop-intel-core-i5-12450h16-gb512-gb-ssdintel-uhd-graphicswindows-11-homemsofficefull-hd-396-cm-156-inch-arctic-grey-m6q2t6-8866348",
        retailer="Reliance Digital",
        name="Lenovo IdeaPad Slim 3 Laptop",
        brand="Lenovo",
        category="Laptops",
        emoji="💻",
        price=58990.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:00+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/asus-vivobook-15-x1504vap-bq1321ws-standard-laptop-intel-core-3-processor-100u8-gb512-gb-ssdintel-uhd-graphicswindows-11-homemicrosoft-office-home-2024wuxga-396-cm-156-inch-cool-silver-mnd3ts-9996309",
        retailer="Reliance Digital",
        name="Asus VivoBook 15 Laptop",
        brand="Asus",
        category="Laptops",
        emoji="💻",
        price=52990.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:02+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/xiaomi-fx-series-1397-cm-55-inch-4k-ultra-hd-led-smart-fire-tv-2025-edition-with-alexa-built-in-l55mb-fin-mc4h8d-9266565",
        retailer="Reliance Digital",
        name="Xiaomi FX Series 55-inch 4K TV",
        brand="Xiaomi",
        category="Home",
        emoji="📺",
        price=35999.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:08+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/samsung-108-cm-43-inches-crystal-4k-ultra-hd-smart-led-tv-black-ua43ue81afulxl-mcxaxq-9285129",
        retailer="Reliance Digital",
        name="Samsung Crystal 43-inch 4K TV",
        brand="Samsung",
        category="Home",
        emoji="📺",
        price=30490.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:13+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/lg-650-l-3-star-convertible-side-by-side-refrigerator-with-multi-air-flow-and-smart-diagnosis-dazzle-steel-gl-b257jds3-m8pu8g-9027110",
        retailer="Reliance Digital",
        name="LG 650L Side-by-Side Refrigerator",
        brand="LG",
        category="Home",
        emoji="🧊",
        price=87090.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:38+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/bosch-243l-top-freezer-frost-free-double-door-refrigerator-ctn27s21ei-fine-steel-moibb6-10047582",
        retailer="Reliance Digital",
        name="Bosch 243L Double-Door Refrigerator",
        brand="Bosch",
        category="Home",
        emoji="🧊",
        price=25500.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:45+00:00",
    ),
    RecordedQuote(
        url="https://www.reliancedigital.in/product/godrej-244-l-3-star-frost-free-refrigerator-with-nano-shield-technology-fossil-steel-valor-280cnrcif-mmtbgp-9987199",
        retailer="Reliance Digital",
        name="Godrej 244L Frost-Free Refrigerator",
        brand="Godrej",
        category="Home",
        emoji="🧊",
        price=27490.0,
        seller="Reliance Digital",
        in_stock=True,
        availability="In stock",
        recorded_at="2026-10-28T07:16:48+00:00",
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

    The seed runs once per database. It skips a URL that is already attached
    and a product whose name already exists, so a user's import or removal is
    not overwritten. Returns the number of products added.
    """

    with db.connect() as connection:
        already_seeded = connection.execute(
            "SELECT 1 FROM app_meta WHERE key = ?", (_SEED_MARKER,)
        ).fetchone()
    if already_seeded is not None:
        return 0

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

    with db.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, '1')",
            (_SEED_MARKER,),
        )
        connection.commit()
    return added
