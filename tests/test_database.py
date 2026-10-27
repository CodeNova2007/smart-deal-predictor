"""Tests for SQLite schema, seed data, and watchlist writes."""

from __future__ import annotations

from datetime import date

import pytest

from smartdeal.database import Database
from smartdeal.seed import PRODUCTS, _insert_demo_product, seed_missing_demo_products


def test_initialize_seeds_the_demo_catalog_once(db: Database):
    products = db.list_products()
    assert len(products) == 40
    assert all(item["currency"] == "INR" for item in products)
    assert {item["name"] for item in products} >= {
        "EchoBuds Pro",
        "Aurora X5 ANC Headphones",
        "Lumen 4K Monitor",
        "NovaBook Air 13",
        "StudioMax ANC Headphones",
        "AirStep Running Shoes",
    }

    for product in products:
        history = db.get_price_history(int(product["id"]))
        offers = db.get_offers(int(product["id"]))
        assert len(history) == 120
        assert len(offers) == 4
        assert history[-1]["price"] == product["current_price"]
        assert {offer["seller"] for offer in offers} == {
            "MegaMart",
            "TechNest",
            "UrbanCart",
            "PrimeStore",
        }

    watchlist = db.get_watchlist_details()
    assert len(watchlist) == 4
    assert {item["name"] for item in watchlist} == {
        "Aurora X5 ANC Headphones",
        "Lumen 4K Monitor",
        "StudioMax ANC Headphones",
        "Orbit Pro Smartwatch",
    }

    # Re-running initialization must not duplicate demo rows.
    db.initialize()
    assert len(db.list_products()) == 40
    assert len(db.get_price_history(1)) == 120


def test_watchlist_upsert_updates_existing_row(db: Database):
    product = next(item for item in db.list_products() if item["name"] == "EchoBuds Pro")
    product_id = int(product["id"])

    created = db.upsert_watchlist(product_id, 8_500, today=date(2026, 1, 1))
    assert created["target_price"] == 8_500
    assert created["created_at"] == "2026-01-01"

    updated = db.upsert_watchlist(product_id, 8_200, today=date(2026, 2, 2))
    assert updated["target_price"] == 8_200
    assert updated["created_at"] == "2026-01-01"
    assert updated["updated_at"] == "2026-02-02"
    assert len(db.get_watchlist_details()) == 5

    assert db.remove_watchlist(product_id) is True
    assert db.get_watchlist_item(product_id) is None
    assert db.remove_watchlist(product_id) is False


def test_watchlist_rejects_invalid_targets_and_unknown_products(db: Database):
    product = db.list_products()[0]
    with pytest.raises(ValueError, match="greater than zero"):
        db.upsert_watchlist(int(product["id"]), 0)
    with pytest.raises(ValueError, match="Product not found"):
        db.upsert_watchlist(999_999, 1_000)


def test_add_price_observation_updates_current_price_and_history(db: Database):
    product = next(item for item in db.list_products() if item["name"] == "EchoBuds Pro")
    product_id = int(product["id"])

    db.add_price_observation(
        product_id, 8_700, observed_on=date(2027, 3, 1), source="Test scan"
    )

    refreshed = db.get_product(product_id)
    assert refreshed is not None
    assert refreshed["current_price"] == 8_700
    history = db.get_price_history(product_id)
    assert len(history) == 121
    assert history[-1] == {
        "observed_on": "2027-03-01",
        "price": 8_700,
        "source": "Test scan",
    }

    with pytest.raises(ValueError, match="greater than zero"):
        db.add_price_observation(product_id, -1)


def test_get_bundle_returns_none_for_unknown_product(db: Database):
    assert db.get_bundle(999_999) is None


def test_seed_missing_demo_products_is_idempotent(db: Database):
    with db.connect() as connection:
        assert seed_missing_demo_products(connection) == 0
    assert len(db.list_products()) == 40


def test_insert_demo_product_ignores_a_duplicate_name(db: Database):
    with db.connect() as connection:
        assert _insert_demo_product(connection, PRODUCTS[0], date.today()) is None
        connection.commit()
    assert len(db.list_products()) == 40


def test_initialize_removes_duplicate_demo_rows_and_keeps_names_unique(db: Database):
    with db.connect() as connection:
        # Simulate a database created before the unique demo-name index.
        connection.execute("DROP INDEX IF EXISTS idx_products_demo_name")
        source = connection.execute(
            "SELECT * FROM products WHERE data_origin = 'demo' LIMIT 1"
        ).fetchone()
        connection.execute(
            """
            INSERT INTO products
                (name, brand, category, description, emoji, current_price,
                 list_price, currency, data_origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'INR', 'demo')
            """,
            (
                source["name"],
                source["brand"],
                source["category"],
                source["description"],
                source["emoji"],
                source["current_price"],
                source["list_price"],
            ),
        )
        connection.commit()

    assert len(db.list_products()) == 41

    db.initialize()

    products = db.list_products()
    assert len(products) == 40
    assert len({product["name"] for product in products}) == 40
