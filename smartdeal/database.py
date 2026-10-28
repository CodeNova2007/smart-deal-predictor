"""SQLite persistence for products, observed prices, offers, and watchlists."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .seed import seed_database, seed_missing_demo_products


SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    brand TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'Other',
    description TEXT NOT NULL DEFAULT '',
    emoji TEXT NOT NULL DEFAULT '🛍️',
    current_price REAL NOT NULL,
    list_price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    data_origin TEXT NOT NULL DEFAULT 'demo',
    source_url TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT NOT NULL DEFAULT '',
    last_success_at TEXT NOT NULL DEFAULT '',
    live_status TEXT NOT NULL DEFAULT '',
    live_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    observed_on TEXT NOT NULL,
    price REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'Demo catalog scan'
);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    seller TEXT NOT NULL,
    price REAL NOT NULL,
    list_price REAL NOT NULL DEFAULT 0,
    delivery_fee REAL NOT NULL DEFAULT 0,
    coupon_code TEXT NOT NULL DEFAULT '',
    coupon_amount REAL NOT NULL DEFAULT 0,
    in_stock INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    retailer TEXT NOT NULL DEFAULT '',
    availability TEXT NOT NULL DEFAULT '',
    is_live INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    target_price REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    price_paid REAL NOT NULL,
    purchased_on TEXT NOT NULL,
    retailer TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    read_at TEXT NOT NULL DEFAULT '',
    dismissed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    retailer TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT NOT NULL DEFAULT '',
    last_success_at TEXT NOT NULL DEFAULT '',
    last_status TEXT NOT NULL DEFAULT '',
    last_error TEXT NOT NULL DEFAULT '',
    last_title TEXT NOT NULL DEFAULT '',
    last_price REAL,
    last_list_price REAL,
    last_currency TEXT NOT NULL DEFAULT 'INR',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(product_id, url)
);

CREATE INDEX IF NOT EXISTS idx_history_product_date
    ON price_history(product_id, observed_on);
CREATE INDEX IF NOT EXISTS idx_offers_product
    ON offers(product_id);
CREATE INDEX IF NOT EXISTS idx_sources_product
    ON product_sources(product_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date
    ON purchases(purchased_on DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_created
    ON alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_product
    ON alerts(product_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe
    ON alerts(dedupe_key) WHERE dedupe_key <> '';
"""


class Database:
    """Thin, testable data-access layer.

    Connections are short-lived so Streamlit reruns cannot share a stale SQLite
    connection across threads.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate(connection)
            connection.commit()
            count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if count == 0:
                seed_database(connection)
            else:
                seed_missing_demo_products(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        """Add columns introduced after the first demo database was created."""

        product_columns = {
            "data_origin": "TEXT NOT NULL DEFAULT 'demo'",
            "source_url": "TEXT NOT NULL DEFAULT ''",
            "last_checked_at": "TEXT NOT NULL DEFAULT ''",
            "last_success_at": "TEXT NOT NULL DEFAULT ''",
            "live_status": "TEXT NOT NULL DEFAULT ''",
            "live_error": "TEXT NOT NULL DEFAULT ''",
        }
        offer_columns = {
            "list_price": "REAL NOT NULL DEFAULT 0",
            "source_url": "TEXT NOT NULL DEFAULT ''",
            "retailer": "TEXT NOT NULL DEFAULT ''",
            "availability": "TEXT NOT NULL DEFAULT ''",
            "is_live": "INTEGER NOT NULL DEFAULT 0",
        }
        source_columns = {
            "last_success_at": "TEXT NOT NULL DEFAULT ''",
            "last_list_price": "REAL",
        }
        Database._ensure_columns(connection, "products", product_columns)
        Database._ensure_columns(connection, "offers", offer_columns)
        Database._ensure_columns(connection, "product_sources", source_columns)
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_url "
            "ON product_sources(url)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_offers_source "
            "ON offers(product_id, source_url)"
        )
        # Demo catalog names must be unique. Two app sessions starting at the
        # same time can both try to seed the same new products; the unique
        # index makes the loser's insert a no-op. Clean up any duplicates left
        # by older versions first, keeping the oldest row (children cascade).
        connection.execute(
            """
            DELETE FROM products
            WHERE data_origin = 'demo'
              AND id NOT IN (
                  SELECT MIN(id)
                  FROM products
                  WHERE data_origin = 'demo'
                  GROUP BY name
              )
            """
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_demo_name "
            "ON products(name) WHERE data_origin = 'demo'"
        )

    @staticmethod
    def _ensure_columns(
        connection: sqlite3.Connection, table: str, columns: dict[str, str]
    ) -> None:
        existing = {
            str(row["name"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {name} {definition}"
                )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_products(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM products ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_product(self, product_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_price_history(self, product_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT observed_on, price, source
                FROM price_history
                WHERE product_id = ?
                ORDER BY observed_on ASC, id ASC
                """,
                (product_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_offers(self, product_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, seller, price, list_price, delivery_fee, coupon_code,
                       coupon_amount, in_stock, last_seen, source_url,
                       retailer, availability, is_live
                FROM offers
                WHERE product_id = ?
                ORDER BY price ASC, seller ASC
                """,
                (product_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_watchlist_item(self, product_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM watchlist WHERE product_id = ?", (product_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_watchlist_map(self) -> dict[int, dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM watchlist").fetchall()
        return {int(row["product_id"]): dict(row) for row in rows}

    def get_watchlist_details(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT w.*, p.name, p.category, p.emoji, p.current_price,
                       p.list_price, p.currency
                FROM watchlist w
                JOIN products p ON p.id = w.product_id
                ORDER BY p.name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_purchase(self, product_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM purchases WHERE product_id = ?", (product_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_purchase_map(self) -> dict[int, dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM purchases").fetchall()
        return {int(row["product_id"]): dict(row) for row in rows}

    def get_all_purchases(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pu.*, p.name, p.category, p.emoji, p.current_price,
                       p.list_price, p.currency, p.data_origin, p.live_status,
                       p.last_success_at
                FROM purchases pu
                JOIN products p ON p.id = pu.product_id
                ORDER BY pu.purchased_on DESC, p.name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_alerts(
        self,
        *,
        include_dismissed: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where = "" if include_dismissed else "WHERE a.dismissed_at = ''"
        safe_limit = max(1, min(int(limit), 500))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT a.*, p.name AS product_name, p.emoji AS product_emoji,
                       p.data_origin AS product_origin,
                       p.current_price AS product_current_price
                FROM alerts a
                LEFT JOIN products p ON p.id = a.product_id
                {where}
                ORDER BY a.created_at DESC, a.id DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_alert_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN dismissed_at = '' THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN dismissed_at = '' AND read_at = ''
                             THEN 1 ELSE 0 END) AS unread,
                    SUM(CASE WHEN dismissed_at = '' AND read_at = ''
                             AND kind = 'target_reached' THEN 1 ELSE 0 END) AS target,
                    SUM(CASE WHEN dismissed_at = '' AND read_at = ''
                             AND kind IN ('price_drop', 'back_in_stock',
                                          'out_of_stock') THEN 1 ELSE 0 END) AS price,
                    SUM(CASE WHEN dismissed_at = '' AND read_at = ''
                             AND kind IN ('quote_attention', 'quote_recovered')
                             THEN 1 ELSE 0 END) AS quote,
                    SUM(CASE WHEN dismissed_at <> '' THEN 1 ELSE 0 END) AS dismissed
                FROM alerts
                """
            ).fetchone()
        values = dict(row) if row else {}
        return {
            key: int(values.get(key) or 0)
            for key in (
                "total",
                "active",
                "unread",
                "target",
                "price",
                "quote",
                "dismissed",
            )
        }

    def count_unread_alerts(self) -> int:
        return self.get_alert_counts()["unread"]

    def get_bundle(self, product_id: int) -> dict[str, Any] | None:
        """Fetch everything needed to analyse one product."""

        product = self.get_product(product_id)
        if product is None:
            return None
        return {
            "product": product,
            "history": self.get_price_history(product_id),
            "offers": self.get_offers(product_id),
            "watchlist": self.get_watchlist_item(product_id),
            "sources": self.get_live_sources(product_id),
            "purchase": self.get_purchase(product_id),
        }

    def get_all_bundles(self) -> list[dict[str, Any]]:
        watchlist_map = self.get_watchlist_map()
        purchase_map = self.get_purchase_map()
        bundles = []
        for product in self.list_products():
            product_id = int(product["id"])
            bundles.append(
                {
                    "product": product,
                    "history": self.get_price_history(product_id),
                    "offers": self.get_offers(product_id),
                    "watchlist": watchlist_map.get(product_id),
                    "sources": self.get_live_sources(product_id),
                    "purchase": purchase_map.get(product_id),
                }
            )
        return bundles

    def get_live_sources(self, product_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM product_sources
                WHERE product_id = ?
                ORDER BY id ASC
                """,
                (product_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_all_live_sources(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM product_sources ORDER BY product_id ASC, id ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_live_source(self, source_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM product_sources WHERE id = ?", (source_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_live_source_by_url(self, url: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM product_sources WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
        return dict(row) if row else None

    def get_live_products(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM products
                WHERE data_origin = 'live'
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def upsert_watchlist(
        self, product_id: int, target_price: float, today: date | None = None
    ) -> dict[str, Any]:
        if float(target_price) <= 0:
            raise ValueError("Target price must be greater than zero.")
        if self.get_product(product_id) is None:
            raise ValueError("Product not found.")

        today_iso = (today or date.today()).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO watchlist
                    (product_id, target_price, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    target_price = excluded.target_price,
                    updated_at = excluded.updated_at
                """,
                (product_id, round(float(target_price), 2), today_iso, today_iso),
            )
            connection.commit()
        item = self.get_watchlist_item(product_id)
        assert item is not None
        return item

    def remove_watchlist(self, product_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM watchlist WHERE product_id = ?", (product_id,)
            )
            connection.commit()
        return cursor.rowcount > 0

    def upsert_purchase(
        self,
        product_id: int,
        price_paid: float,
        purchased_on: date | None = None,
        retailer: str = "",
        notes: str = "",
        today: date | None = None,
    ) -> dict[str, Any]:
        """Record what the user paid for one product.

        This is user-provided data, not a marketplace quote. One purchase record
        is kept per product; saving again updates that record.
        """

        if float(price_paid) <= 0:
            raise ValueError("Purchase price must be greater than zero.")
        if self.get_product(product_id) is None:
            raise ValueError("Product not found.")
        day = purchased_on or date.today()
        current_day = today or date.today()
        if day > current_day:
            raise ValueError("Purchase date cannot be in the future.")

        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO purchases
                    (product_id, price_paid, purchased_on, retailer, notes,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    price_paid = excluded.price_paid,
                    purchased_on = excluded.purchased_on,
                    retailer = excluded.retailer,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    product_id,
                    round(float(price_paid), 2),
                    day.isoformat(),
                    retailer.strip()[:120],
                    notes.strip()[:500],
                    stamp,
                    stamp,
                ),
            )
            connection.commit()
        item = self.get_purchase(product_id)
        assert item is not None
        return item

    def remove_purchase(self, product_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM purchases WHERE product_id = ?", (product_id,)
            )
            connection.commit()
        return cursor.rowcount > 0

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
        """Insert one persistent alert, ignoring an already-seen event."""

        clean_kind = kind.strip()
        clean_title = title.strip()
        if not clean_kind or not clean_title:
            raise ValueError("Alert kind and title are required.")
        stamp = created_at or datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        key = dedupe_key.strip() or (
            f"{clean_kind}:{product_id or 0}:{stamp}:{clean_title}"
        )
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO alerts
                    (product_id, kind, title, message, dedupe_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    clean_kind,
                    clean_title[:200],
                    message.strip()[:1000],
                    key[:300],
                    stamp,
                ),
            )
            connection.commit()
        return cursor.rowcount > 0

    def mark_alert_read(self, alert_id: int, read: bool = True) -> bool:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as connection:
            if read:
                cursor = connection.execute(
                    "UPDATE alerts SET read_at = ? WHERE id = ? AND read_at = ''",
                    (stamp, alert_id),
                )
            else:
                cursor = connection.execute(
                    "UPDATE alerts SET read_at = '' WHERE id = ?", (alert_id,)
                )
            connection.commit()
        return cursor.rowcount > 0

    def mark_all_alerts_read(self) -> int:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE alerts SET read_at = ? WHERE read_at = '' "
                "AND dismissed_at = ''",
                (stamp,),
            )
            connection.commit()
        return cursor.rowcount

    def dismiss_alert(self, alert_id: int) -> bool:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE alerts
                SET dismissed_at = ?,
                    read_at = CASE WHEN read_at = '' THEN ? ELSE read_at END
                WHERE id = ? AND dismissed_at = ''
                """,
                (stamp, stamp, alert_id),
            )
            connection.commit()
        return cursor.rowcount > 0

    def clear_dismissed_alerts(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM alerts WHERE dismissed_at <> ''"
            )
            connection.commit()
        return cursor.rowcount

    def add_price_observation(
        self,
        product_id: int,
        price: float,
        observed_on: date | None = None,
        source: str = "Manual entry",
    ) -> None:
        """Keep the small history-entry API available for future scrapers."""

        if float(price) <= 0:
            raise ValueError("Price must be greater than zero.")
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO price_history (product_id, observed_on, price, source)
                VALUES (?, ?, ?, ?)
                """,
                (
                    product_id,
                    (observed_on or date.today()).isoformat(),
                    round(float(price), 2),
                    source,
                ),
            )
            connection.execute(
                "UPDATE products SET current_price = ? WHERE id = ?",
                (round(float(price), 2), product_id),
            )
            connection.commit()

    def delete_product(self, product_id: int) -> bool:
        """Delete a product and its dependent rows (used for import rollback)."""

        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM products WHERE id = ?", (product_id,)
            )
            connection.commit()
        return cursor.rowcount > 0

    def create_product(
        self,
        *,
        name: str,
        brand: str = "",
        category: str = "Other",
        description: str = "",
        emoji: str = "🛍️",
        current_price: float,
        list_price: float,
        currency: str = "INR",
        data_origin: str = "demo",
        source_url: str = "",
        last_checked_at: str = "",
        last_success_at: str = "",
        live_status: str = "",
        live_error: str = "",
    ) -> int:
        """Create a product imported from a live source or a manual entry."""

        if float(current_price) <= 0:
            raise ValueError("Price must be greater than zero.")
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO products
                    (name, brand, category, description, emoji, current_price,
                     list_price, currency, data_origin, source_url,
                     last_checked_at, last_success_at, live_status, live_error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip() or "Untitled product",
                    brand.strip(),
                    category.strip() or "Other",
                    description.strip(),
                    emoji.strip() or "🛍️",
                    round(float(current_price), 2),
                    round(float(list_price), 2),
                    currency.strip().upper() or "INR",
                    data_origin,
                    source_url.strip(),
                    last_checked_at,
                    last_success_at,
                    live_status,
                    live_error,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update_live_product(
        self,
        product_id: int,
        *,
        current_price: float | None = None,
        list_price: float | None = None,
        source_url: str | None = None,
        last_checked_at: str | None = None,
        last_success_at: str | None = None,
        live_status: str | None = None,
        live_error: str | None = None,
    ) -> None:
        """Update only the live-data fields that were supplied."""

        fields: list[str] = []
        values: list[Any] = []
        for name, value in (
            ("current_price", current_price),
            ("list_price", list_price),
            ("source_url", source_url),
            ("last_checked_at", last_checked_at),
            ("last_success_at", last_success_at),
            ("live_status", live_status),
            ("live_error", live_error),
        ):
            if value is not None:
                fields.append(f"{name} = ?")
                values.append(
                    round(float(value), 2)
                    if name in {"current_price", "list_price"}
                    else value
                )
        if not fields:
            return
        with self.connect() as connection:
            connection.execute(
                f"UPDATE products SET {', '.join(fields)} WHERE id = ?",
                (*values, product_id),
            )
            connection.commit()

    def upsert_live_source(
        self,
        product_id: int,
        *,
        url: str,
        retailer: str,
        label: str = "",
        checked_at: str,
        status: str,
        error: str = "",
        title: str = "",
        price: float | None = None,
        list_price: float | None = None,
        currency: str = "INR",
        success_at: str = "",
    ) -> dict[str, Any]:
        """Insert or update one marketplace URL attached to a product.

        A failed check updates the error fields but deliberately keeps the last
        successful price, title, and timestamp so the UI can label stale data
        instead of pretending it disappeared.
        """

        timestamp = checked_at or date.today().isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO product_sources
                    (product_id, url, retailer, label, last_checked_at,
                     last_success_at, last_status, last_error, last_title,
                     last_price, last_list_price, last_currency,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id, url) DO UPDATE SET
                    retailer = excluded.retailer,
                    label = excluded.label,
                    last_checked_at = excluded.last_checked_at,
                    last_success_at = CASE
                        WHEN excluded.last_success_at != ''
                            THEN excluded.last_success_at
                        ELSE product_sources.last_success_at
                    END,
                    last_status = excluded.last_status,
                    last_error = excluded.last_error,
                    last_title = CASE
                        WHEN excluded.last_success_at != ''
                            THEN excluded.last_title
                        ELSE product_sources.last_title
                    END,
                    last_price = CASE
                        WHEN excluded.last_success_at != ''
                            THEN excluded.last_price
                        ELSE product_sources.last_price
                    END,
                    last_list_price = CASE
                        WHEN excluded.last_success_at != ''
                            THEN excluded.last_list_price
                        ELSE product_sources.last_list_price
                    END,
                    last_currency = CASE
                        WHEN excluded.last_success_at != ''
                            THEN excluded.last_currency
                        ELSE product_sources.last_currency
                    END,
                    updated_at = excluded.updated_at
                """,
                (
                    product_id,
                    url.strip(),
                    retailer.strip() or "Marketplace",
                    label.strip(),
                    timestamp,
                    success_at,
                    status,
                    error[:1000],
                    title.strip(),
                    round(float(price), 2) if price is not None else None,
                    round(float(list_price), 2) if list_price is not None else None,
                    currency.strip().upper() or "INR",
                    timestamp,
                    timestamp,
                ),
            )
            connection.commit()
        source = self.get_live_source_by_url(url.strip())
        assert source is not None
        return source

    def remove_live_source(self, source_id: int) -> bool:
        source = self.get_live_source(source_id)
        if source is None:
            return False
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM offers WHERE product_id = ? AND source_url = ?",
                (int(source["product_id"]), str(source["url"])),
            )
            cursor = connection.execute(
                "DELETE FROM product_sources WHERE id = ?", (source_id,)
            )
            connection.commit()
        return cursor.rowcount > 0

    def upsert_live_offer(
        self,
        product_id: int,
        *,
        source_url: str,
        retailer: str,
        seller: str,
        price: float,
        in_stock: bool,
        availability: str,
        list_price: float | None = None,
        checked_on: date | None = None,
    ) -> None:
        """Replace the latest quote for one source URL."""

        if float(price) <= 0:
            raise ValueError("Price must be greater than zero.")
        seen = (checked_on or date.today()).isoformat()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM offers WHERE product_id = ? AND source_url = ?",
                (product_id, source_url),
            )
            connection.execute(
                """
                INSERT INTO offers
                    (product_id, seller, price, list_price, delivery_fee,
                     coupon_code, coupon_amount, in_stock, last_seen,
                     source_url, retailer, availability, is_live)
                VALUES (?, ?, ?, ?, 0, '', 0, ?, ?, ?, ?, ?, 1)
                """,
                (
                    product_id,
                    seller.strip() or retailer.strip() or "Marketplace",
                    round(float(price), 2),
                    round(float(list_price), 2) if list_price is not None else 0,
                    1 if in_stock else 0,
                    seen,
                    source_url,
                    retailer,
                    availability[:120],
                ),
            )
            connection.commit()

    def replace_live_observation(
        self,
        product_id: int,
        price: float,
        *,
        observed_on: date | None = None,
        source: str = "Live quote",
    ) -> None:
        """Keep one live observation per product per day.

        Refreshing twice on the same day updates that day's observation instead
        of adding a duplicate point to the history.
        """

        if float(price) <= 0:
            raise ValueError("Price must be greater than zero.")
        day = (observed_on or date.today()).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM price_history
                WHERE product_id = ? AND observed_on = ?
                  AND source LIKE 'Live quote%'
                """,
                (product_id, day),
            )
            connection.execute(
                """
                INSERT INTO price_history (product_id, observed_on, price, source)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, day, round(float(price), 2), source[:160]),
            )
            connection.commit()

