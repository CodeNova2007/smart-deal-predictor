"""Deterministic demo catalog and price-history seeding.

All rows are synthetic demo data. The UI and the copilot label them as recorded
demo observations so the assistant never presents them as live market prices.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from typing import Any

SELLERS = ("MegaMart", "TechNest", "UrbanCart", "PrimeStore")

PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "Aurora X5 ANC Headphones",
        "brand": "Aurora",
        "category": "Audio",
        "emoji": "🎧",
        "price": 24_990,
        "list_price": 29_990,
        "drift": 0.085,
        "wave": 0.030,
        "noise": 0.010,
        "description": "Over-ear noise-cancelling headphones with 40-hour battery life.",
    },
    {
        "name": "Pulse Watch S2",
        "brand": "Pulse",
        "category": "Wearables",
        "emoji": "⌚",
        "price": 12_999,
        "list_price": 15_999,
        "drift": -0.015,
        "wave": 0.025,
        "noise": 0.009,
        "description": "AMOLED fitness smartwatch with sleep and SpO2 tracking.",
    },
    {
        "name": "Vertex 14 Ultrabook",
        "brand": "Vertex",
        "category": "Laptops",
        "emoji": "💻",
        "price": 74_990,
        "list_price": 84_990,
        "drift": 0.070,
        "wave": 0.018,
        "noise": 0.006,
        "description": "14-inch lightweight laptop with 16 GB RAM and 1 TB SSD.",
    },
    {
        "name": "SnapShot Mini Camera",
        "brand": "SnapShot",
        "category": "Cameras",
        "emoji": "📷",
        "price": 45_990,
        "list_price": 52_990,
        "drift": 0.020,
        "wave": 0.032,
        "noise": 0.011,
        "description": "Pocket mirrorless camera with 4K video and a 24 MP sensor.",
    },
    {
        "name": "Breeze Air Purifier",
        "brand": "Breeze",
        "category": "Home",
        "emoji": "🌬️",
        "price": 18_999,
        "list_price": 22_999,
        "drift": -0.055,
        "wave": 0.020,
        "noise": 0.008,
        "description": "HEPA air purifier for rooms up to 500 sq ft with auto mode.",
    },
    {
        "name": "Titan Mechanical Keyboard",
        "brand": "Titan",
        "category": "Accessories",
        "emoji": "⌨️",
        "price": 7_499,
        "list_price": 9_999,
        "drift": 0.010,
        "wave": 0.055,
        "noise": 0.016,
        "description": "Hot-swappable wireless mechanical keyboard with RGB lighting.",
    },
    {
        "name": "EchoBuds Pro",
        "brand": "EchoBuds",
        "category": "Audio",
        "emoji": "🎵",
        "price": 8_999,
        "list_price": 11_999,
        "drift": 0.100,
        "wave": 0.038,
        "noise": 0.013,
        "description": "Compact ANC earbuds with wireless charging case.",
    },
    {
        "name": "Lumen 4K Monitor",
        "brand": "Lumen",
        "category": "Monitors",
        "emoji": "🖥️",
        "price": 32_999,
        "list_price": 39_999,
        "drift": -0.030,
        "wave": 0.022,
        "noise": 0.007,
        "description": "27-inch 4K IPS monitor with USB-C power delivery.",
    },
    {
        "name": "ZenPhone Nova",
        "brand": "ZenPhone",
        "category": "Smartphones",
        "emoji": "📱",
        "price": 42_999,
        "list_price": 49_999,
        "drift": -0.045,
        "wave": 0.018,
        "noise": 0.007,
        "description": "5G smartphone with a 6.7-inch OLED display and 50 MP camera.",
    },
    {
        "name": "BrewMaster Coffee Machine",
        "brand": "BrewMaster",
        "category": "Kitchen",
        "emoji": "☕",
        "price": 15_999,
        "list_price": 19_999,
        "drift": 0.060,
        "wave": 0.035,
        "noise": 0.012,
        "description": "Bean-to-cup espresso machine with built-in milk frother.",
    },
    {
        "name": "AeroFit Treadmill",
        "brand": "AeroFit",
        "category": "Fitness",
        "emoji": "🏃",
        "price": 39_999,
        "list_price": 47_999,
        "drift": 0.025,
        "wave": 0.024,
        "noise": 0.008,
        "description": "Foldable treadmill with 12 programs and heart-rate sensors.",
    },
    {
        "name": "CloudNine Mattress",
        "brand": "CloudNine",
        "category": "Home",
        "emoji": "🛏️",
        "price": 27_999,
        "list_price": 34_999,
        "drift": 0.075,
        "wave": 0.028,
        "noise": 0.009,
        "description": "Queen-size hybrid mattress with memory foam and pocket springs.",
    },
    {
        "name": "NovaBook Air 13",
        "brand": "Nova",
        "category": "Laptops",
        "emoji": "💻",
        "price": 58_990,
        "list_price": 69_990,
        "drift": 0.065,
        "wave": 0.020,
        "noise": 0.007,
        "description": "Thin 13-inch laptop with an OLED display, 16 GB RAM, and 512 GB SSD.",
    },
    {
        "name": "Orbit Pro Smartwatch",
        "brand": "Orbit",
        "category": "Wearables",
        "emoji": "⌚",
        "price": 9_499,
        "list_price": 12_999,
        "drift": -0.020,
        "wave": 0.028,
        "noise": 0.009,
        "description": "GPS smartwatch with AMOLED display, heart-rate alerts, and 10-day battery.",
    },
    {
        "name": "StudioMax ANC Headphones",
        "brand": "StudioMax",
        "category": "Audio",
        "emoji": "🎧",
        "price": 18_499,
        "list_price": 24_999,
        "drift": 0.090,
        "wave": 0.034,
        "noise": 0.011,
        "description": "Studio-tuned wireless headphones with adaptive noise cancelling.",
    },
    {
        "name": "PixelView 27 QHD Monitor",
        "brand": "PixelView",
        "category": "Monitors",
        "emoji": "🖥️",
        "price": 21_999,
        "list_price": 27_999,
        "drift": -0.035,
        "wave": 0.024,
        "noise": 0.008,
        "description": "27-inch QHD monitor with 165 Hz refresh rate and USB-C hub.",
    },
    {
        "name": "FreshMix Juicer",
        "brand": "FreshMix",
        "category": "Kitchen",
        "emoji": "🥤",
        "price": 4_299,
        "list_price": 5_999,
        "drift": 0.045,
        "wave": 0.040,
        "noise": 0.014,
        "description": "Cold-press juicer with a wide feed chute and easy-clean parts.",
    },
    {
        "name": "AirStep Running Shoes",
        "brand": "AirStep",
        "category": "Fitness",
        "emoji": "👟",
        "price": 3_999,
        "list_price": 5_499,
        "drift": 0.055,
        "wave": 0.045,
        "noise": 0.015,
        "description": "Lightweight daily running shoes with responsive foam cushioning.",
    },
    {
        "name": "HomeGuard Security Camera",
        "brand": "HomeGuard",
        "category": "Home",
        "emoji": "📹",
        "price": 6_499,
        "list_price": 8_999,
        "drift": -0.025,
        "wave": 0.030,
        "noise": 0.010,
        "description": "Indoor 2K security camera with two-way audio and night vision.",
    },
    {
        "name": "PowerCore 20K Charger",
        "brand": "PowerCore",
        "category": "Accessories",
        "emoji": "🔋",
        "price": 2_199,
        "list_price": 3_499,
        "drift": 0.030,
        "wave": 0.050,
        "noise": 0.016,
        "description": "20,000 mAh fast-charging power bank with dual USB-C ports.",
    },
    {
        "name": "NovaTab 11 Tablet",
        "brand": "Nova",
        "category": "Tablets",
        "emoji": "📲",
        "price": 34_990,
        "list_price": 41_990,
        "drift": 0.045,
        "wave": 0.022,
        "noise": 0.008,
        "description": "11-inch 2K tablet with stylus support and 12-hour battery life.",
    },
    {
        "name": "Vertex 15 Creator Laptop",
        "brand": "Vertex",
        "category": "Laptops",
        "emoji": "💻",
        "price": 96_990,
        "list_price": 1_09_990,
        "drift": 0.050,
        "wave": 0.016,
        "noise": 0.006,
        "description": "15-inch creator laptop with dedicated graphics, 32 GB RAM, and 1 TB SSD.",
    },
    {
        "name": "Rift Console X",
        "brand": "Rift",
        "category": "Gaming",
        "emoji": "🎮",
        "price": 49_990,
        "list_price": 54_990,
        "drift": -0.020,
        "wave": 0.020,
        "noise": 0.007,
        "description": "4K gaming console with 1 TB storage and a wireless controller.",
    },
    {
        "name": "EchoBuds Lite",
        "brand": "EchoBuds",
        "category": "Audio",
        "emoji": "🎵",
        "price": 3_999,
        "list_price": 5_499,
        "drift": 0.075,
        "wave": 0.045,
        "noise": 0.015,
        "description": "Everyday true-wireless earbuds with 28-hour total playback.",
    },
    {
        "name": "Pulse Band 5",
        "brand": "Pulse",
        "category": "Wearables",
        "emoji": "⌚",
        "price": 3_499,
        "list_price": 4_999,
        "drift": 0.040,
        "wave": 0.035,
        "noise": 0.012,
        "description": "Slim fitness band with heart-rate, sleep, and SpO2 tracking.",
    },
    {
        "name": "Lumen 32 Curved Monitor",
        "brand": "Lumen",
        "category": "Monitors",
        "emoji": "🖥️",
        "price": 44_999,
        "list_price": 52_999,
        "drift": -0.030,
        "wave": 0.020,
        "noise": 0.007,
        "description": "32-inch curved QHD monitor with 165 Hz refresh and HDR10.",
    },
    {
        "name": "BrewMaster Gooseneck Kettle",
        "brand": "BrewMaster",
        "category": "Kitchen",
        "emoji": "🫖",
        "price": 2_799,
        "list_price": 3_999,
        "drift": 0.035,
        "wave": 0.040,
        "noise": 0.013,
        "description": "Variable-temperature pour-over kettle with a 1 L capacity.",
    },
    {
        "name": "FreshMix Air Fryer 5L",
        "brand": "FreshMix",
        "category": "Kitchen",
        "emoji": "🍳",
        "price": 8_999,
        "list_price": 12_499,
        "drift": 0.065,
        "wave": 0.038,
        "noise": 0.013,
        "description": "5-litre digital air fryer with eight preset cooking modes.",
    },
    {
        "name": "AirStep Trail Runner",
        "brand": "AirStep",
        "category": "Fitness",
        "emoji": "👟",
        "price": 5_499,
        "list_price": 7_299,
        "drift": 0.045,
        "wave": 0.042,
        "noise": 0.014,
        "description": "Trail running shoes with a grippy outsole and protective rock plate.",
    },
    {
        "name": "Titan Silent Mouse",
        "brand": "Titan",
        "category": "Accessories",
        "emoji": "🖱️",
        "price": 1_899,
        "list_price": 2_799,
        "drift": 0.020,
        "wave": 0.048,
        "noise": 0.016,
        "description": "Wireless productivity mouse with silent switches and USB-C charging.",
    },
    {
        "name": "PowerCore 65W GaN Charger",
        "brand": "PowerCore",
        "category": "Accessories",
        "emoji": "🔌",
        "price": 2_499,
        "list_price": 3_499,
        "drift": 0.025,
        "wave": 0.044,
        "noise": 0.015,
        "description": "Compact 65 W GaN charger with two USB-C ports and one USB-A port.",
    },
    {
        "name": "HomeGuard Video Doorbell",
        "brand": "HomeGuard",
        "category": "Home",
        "emoji": "🔔",
        "price": 8_999,
        "list_price": 12_999,
        "drift": -0.015,
        "wave": 0.028,
        "noise": 0.010,
        "description": "2K video doorbell with motion alerts and two-way talk.",
    },
    {
        "name": "Breeze Smart Humidifier",
        "brand": "Breeze",
        "category": "Home",
        "emoji": "💧",
        "price": 4_999,
        "list_price": 6_999,
        "drift": 0.030,
        "wave": 0.033,
        "noise": 0.011,
        "description": "Ultrasonic humidifier with a 4 L tank and built-in humidity sensor.",
    },
    {
        "name": "SnapShot Action Cam 4K",
        "brand": "SnapShot",
        "category": "Cameras",
        "emoji": "🎥",
        "price": 28_990,
        "list_price": 34_990,
        "drift": 0.015,
        "wave": 0.030,
        "noise": 0.010,
        "description": "Waterproof 4K action camera with electronic image stabilisation.",
    },
    {
        "name": "ZenPhone Nova Lite",
        "brand": "ZenPhone",
        "category": "Smartphones",
        "emoji": "📱",
        "price": 21_999,
        "list_price": 26_999,
        "drift": -0.055,
        "wave": 0.020,
        "noise": 0.008,
        "description": "5G smartphone with a 6.5-inch AMOLED display and 5,000 mAh battery.",
    },
    {
        "name": "CloudNine Pillow Set",
        "brand": "CloudNine",
        "category": "Home",
        "emoji": "🛏️",
        "price": 2_499,
        "list_price": 3_499,
        "drift": 0.020,
        "wave": 0.036,
        "noise": 0.012,
        "description": "Set of two memory-foam pillows with breathable washable covers.",
    },
    {
        "name": "Orbit Pro Max Watch",
        "brand": "Orbit",
        "category": "Wearables",
        "emoji": "⌚",
        "price": 16_999,
        "list_price": 21_999,
        "drift": -0.010,
        "wave": 0.026,
        "noise": 0.009,
        "description": "Premium GPS smartwatch with a titanium case and 14-day battery.",
    },
    {
        "name": "Vertex 27 All-in-One",
        "brand": "Vertex",
        "category": "Desktops",
        "emoji": "🖥️",
        "price": 74_990,
        "list_price": 84_990,
        "drift": 0.040,
        "wave": 0.018,
        "noise": 0.006,
        "description": "27-inch all-in-one desktop with 16 GB RAM and a 1 TB SSD.",
    },
    {
        "name": "AeroFit Adjustable Dumbbells",
        "brand": "AeroFit",
        "category": "Fitness",
        "emoji": "🏋️",
        "price": 3_299,
        "list_price": 4_499,
        "drift": 0.030,
        "wave": 0.038,
        "noise": 0.013,
        "description": "Pair of adjustable dumbbells from 2.5 kg to 12.5 kg each.",
    },
    {
        "name": "StudioMax USB Microphone",
        "brand": "StudioMax",
        "category": "Audio",
        "emoji": "🎙️",
        "price": 6_999,
        "list_price": 9_499,
        "drift": 0.055,
        "wave": 0.040,
        "noise": 0.014,
        "description": "Cardioid USB condenser microphone for streaming and calls.",
    },
]

WATCHLIST_SEED = (
    ("Aurora X5 ANC Headphones", 23_990),
    ("Lumen 4K Monitor", 33_999),
    ("StudioMax ANC Headphones", 17_990),
    ("Orbit Pro Smartwatch", 8_999),
)

_HISTORY_DAYS = 120
_RNG_SEED = 73


def _round_price(value: float) -> int:
    """Round to a realistic whole-rupee price."""

    return max(1, int(round(value)))


def _generate_history(product: dict[str, Any], today: date) -> list[tuple[str, float]]:
    """Create a deterministic, slightly seasonal price path ending at the
    product's current price. This is demo data, not scraped market data."""

    rng = random.Random(f"{_RNG_SEED}:{product['name']}")
    current = float(product["price"])
    days = _HISTORY_DAYS
    raw: list[float] = []

    for index in range(days):
        progress = index / (days - 1)
        # Prices in the past are higher for products with a positive drift.
        trend = current * (1 + product["drift"] * (1 - progress))
        cycle = current * product["wave"] * math.sin(
            (2 * math.pi * index / 41) + (product["price"] % 17)
        )
        noise = current * rng.uniform(-product["noise"], product["noise"])
        raw.append(max(current * 0.68, trend + cycle + noise))

    # Normalise the series so the final observation equals the recorded price.
    offset = current - raw[-1]
    values = [value + offset for value in raw]

    # Two short promotional dips make the history more useful for analysis.
    for start in (days - 46, days - 19):
        length = rng.randint(2, 4)
        depth = current * rng.uniform(0.025, 0.050)
        for index in range(start, min(start + length, days - 1)):
            values[index] = max(current * 0.68, values[index] - depth)

    start_date = today - timedelta(days=days - 1)
    return [
        ((start_date + timedelta(days=index)).isoformat(), round(value, 2))
        for index, value in enumerate(values)
    ]


def _build_offers(product: dict[str, Any], current: float) -> list[dict[str, Any]]:
    rng = random.Random(f"offers:{product['name']}")
    offers: list[dict[str, Any]] = []

    base_specs = [
        ("MegaMart", 1.000, 0.0, 0.0, True),
        ("TechNest", 1.008, 49.0, 750.0 if current >= 20_000 else 300.0, True),
        ("UrbanCart", 1.025, 0.0, 0.0, True),
        ("PrimeStore", 0.997, 99.0, 500.0 if current >= 10_000 else 0.0, True),
    ]

    for seller, factor, delivery, coupon, in_stock in base_specs:
        # Vary availability, but keep enough in-stock offers for comparison.
        if seller == "UrbanCart" and product["category"] in {"Laptops", "Monitors"}:
            in_stock = False
        price = _round_price(current * factor + rng.uniform(-35, 35))
        coupon_code = ""
        if coupon > 0:
            coupon_code = f"SAVE{int(coupon)}"
        offers.append(
            {
                "seller": seller,
                "price": price,
                "delivery_fee": delivery,
                "coupon_code": coupon_code,
                "coupon_amount": coupon,
                "in_stock": 1 if in_stock else 0,
            }
        )

    return offers


def _insert_demo_product(
    connection: Any, product: dict[str, Any], day: date
) -> int | None:
    # OR IGNORE plus the unique demo-name index makes seeding safe when two
    # app sessions start concurrently. A duplicate insert returns None and
    # writes no history or offers.
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO products
            (name, brand, category, description, emoji, current_price,
             list_price, currency, data_origin)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'INR', 'demo')
        """,
        (
            product["name"],
            product["brand"],
            product["category"],
            product["description"],
            product["emoji"],
            product["price"],
            product["list_price"],
        ),
    )
    if cursor.rowcount == 0:
        return None
    product_id = int(cursor.lastrowid)

    history = _generate_history(product, day)
    connection.executemany(
        """
        INSERT INTO price_history (product_id, observed_on, price, source)
        VALUES (?, ?, ?, 'Demo catalog scan')
        """,
        [(product_id, observed_on, price) for observed_on, price in history],
    )

    for offer in _build_offers(product, float(product["price"])):
        connection.execute(
            """
            INSERT INTO offers
                (product_id, seller, price, delivery_fee, coupon_code,
                 coupon_amount, in_stock, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                offer["seller"],
                offer["price"],
                offer["delivery_fee"],
                offer["coupon_code"],
                offer["coupon_amount"],
                offer["in_stock"],
                day.isoformat(),
            ),
        )
    return product_id


def seed_database(connection: Any, today: date | None = None) -> None:
    """Insert the full demo catalog, history, offers, and starter watchlist.

    The caller must check that the products table is empty first.
    """

    day = today or date.today()
    product_ids: dict[str, int] = {}

    for product in PRODUCTS:
        product_id = _insert_demo_product(connection, product, day)
        if product_id is not None:
            product_ids[product["name"]] = product_id

    for name, target in WATCHLIST_SEED:
        product_id = product_ids.get(name)
        if product_id is not None:
            connection.execute(
                """
                INSERT INTO watchlist (product_id, target_price, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, target, day.isoformat(), day.isoformat()),
            )

    connection.commit()


def seed_missing_demo_products(
    connection: Any, today: date | None = None
) -> int:
    """Add demo products introduced after the database was first created.

    Existing product rows, watchlist targets, and live imports are left alone.
    """

    day = today or date.today()
    existing = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM products WHERE data_origin = 'demo'"
        ).fetchall()
    }
    added = 0
    for product in PRODUCTS:
        if product["name"] in existing:
            continue
        if _insert_demo_product(connection, product, day) is not None:
            added += 1
    connection.commit()
    return added
