"""Orchestration for importing and refreshing live marketplace quotes.

The service is the only place that combines a scraped quote with database
writes. It deliberately keeps three things separate:

* the marketplace's last successful quote (possibly stale);
* the latest failed check and its user-safe error;
* the app's derived "current price" (lowest in-stock quote across sources).

A refresh failure never deletes the last good quote and never invents a price.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..alerts import record_import_alert, record_refresh_alerts
from ..config import Settings, load_settings
from ..database import Database
from .scraper import (
    DEFAULT_USER_AGENT,
    LiveQuote,
    ScrapeError,
    normalise_url,
    scrape_product,
)
from .status import DEFAULT_STALE_HOURS, is_stale, source_view

_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "Headphones": (
        "headphone",
        "earphone",
        "earbud",
        "headset",
        "speaker",
        "soundbar",
        "audio",
    ),
    "Computers": (
        "laptop",
        "notebook",
        "monitor",
        "keyboard",
        "mouse",
        "printer",
        "desktop",
        "ssd",
    ),
    "Phones": ("smartphone", "mobile", "phone", "tablet"),
    "Wearables": ("smartwatch", "watch", "fitness band", "tracker"),
    "Home": (
        "vacuum",
        "purifier",
        "mattress",
        "coffee",
        "kitchen",
        "mixer",
        "home",
    ),
    "Fitness": ("treadmill", "dumbbell", "fitness", "gym", "yoga"),
    "Cameras": ("camera", "lens", "gopro", "dslr"),
    "Appliances": (
        "refrigerator",
        "washing machine",
        "air conditioner",
        "microwave",
        "television",
        " tv ",
    ),
}

_CATEGORY_EMOJI = {
    "Headphones": "🎧",
    "Computers": "💻",
    "Phones": "📱",
    "Wearables": "⌚",
    "Home": "🏠",
    "Fitness": "🏋️",
    "Cameras": "📷",
    "Appliances": "🔌",
    "Other": "🛍️",
}

_STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "from",
    "this",
    "that",
    "buy",
    "online",
    "best",
    "price",
    "india",
    "amazon",
    "flipkart",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token_set(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def title_similarity(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def infer_category(title: str, description: str = "") -> str:
    haystack = f" {title} {description} ".lower()
    for category, hints in _CATEGORY_HINTS.items():
        if any(hint in haystack for hint in hints):
            return category
    return "Other"


class LiveService:
    """Import, refresh, and recompute live marketplace quotes."""

    def __init__(self, db: Database, settings: Settings | None = None):
        self.db = db
        self.settings = settings or load_settings()
        self.stale_hours = max(1, int(self.settings.live_stale_hours))

    # ------------------------------------------------------------------
    # Scraping helpers
    # ------------------------------------------------------------------
    def _scrape(self, url: str) -> LiveQuote:
        return scrape_product(
            url,
            timeout=self.settings.live_timeout_seconds,
            user_agent=self.settings.live_user_agent or DEFAULT_USER_AGENT,
            min_interval=self.settings.live_min_interval_seconds,
            max_bytes=self.settings.live_max_bytes,
            check_robots=self.settings.live_check_robots,
        )

    @staticmethod
    def _require_inr(quote: LiveQuote) -> None:
        if str(quote.currency or "").upper() != "INR":
            raise ScrapeError(
                f"The page quotes prices in {quote.currency or 'an unknown currency'}. "
                "This app's analytics are INR-only, so the quote was not imported. "
                "Use an India marketplace page that shows INR.",
                code="unsupported_currency",
                url=quote.url,
                retailer=quote.retailer,
            )

    def _record_quote(
        self, product_id: int, quote: LiveQuote, label: str = ""
    ) -> dict[str, Any]:
        now = _now_iso()
        source = self.db.upsert_live_source(
            product_id,
            url=quote.url,
            retailer=quote.retailer,
            label=label,
            checked_at=now,
            success_at=now,
            status="ok",
            error="",
            title=quote.title,
            price=quote.price,
            list_price=quote.list_price,
            currency=quote.currency,
        )
        self.db.upsert_live_offer(
            product_id,
            source_url=quote.url,
            retailer=quote.retailer,
            seller=quote.seller,
            price=quote.price,
            list_price=quote.list_price,
            in_stock=quote.in_stock,
            availability=quote.availability,
        )
        return source

    def _record_failure(self, source: dict[str, Any], error: ScrapeError) -> None:
        self.db.upsert_live_source(
            int(source["product_id"]),
            url=str(source["url"]),
            retailer=str(source["retailer"]),
            label=str(source.get("label") or ""),
            checked_at=_now_iso(),
            success_at="",
            status=error.code or "error",
            error=error.message,
            currency=str(source.get("last_currency") or "INR"),
        )

    def _snapshot_for_alerts(self, product_id: int) -> dict[str, Any] | None:
        """Build a read-only snapshot for before/after alert comparison."""

        from ..analytics import build_product_snapshot

        bundle = self.db.get_bundle(product_id)
        if bundle is None:
            return None
        return build_product_snapshot(bundle, stale_hours=self.stale_hours)

    def _product_needs_refresh(self, product: dict[str, Any]) -> bool:
        """Return True when any part of a live product is stale or failed."""

        status = str(product.get("live_status") or "").strip().lower()
        if status in {"stale", "error", "no_sources", "partial", "unknown", ""}:
            return True
        if is_stale(product.get("last_success_at"), self.stale_hours):
            return True
        sources = self.db.get_live_sources(int(product["id"]))
        if not sources:
            return True
        now = datetime.now(timezone.utc)
        return any(
            str(source.get("last_status") or "") != "ok"
            or source.get("last_price") is None
            or is_stale(
                source.get("last_success_at"), self.stale_hours, now=now
            )
            for source in sources
        )

    # ------------------------------------------------------------------
    # Recomputation
    # ------------------------------------------------------------------
    def _recompute_product(
        self, product_id: int, *, record_history: bool = True
    ) -> dict[str, Any]:
        product = self.db.get_product(product_id)
        if product is None:
            raise ValueError("Product not found.")
        if str(product.get("data_origin") or "demo") != "live":
            raise ValueError("Only live-imported products can be recomputed as live.")

        sources = self.db.get_live_sources(product_id)
        now = datetime.now(timezone.utc)
        now_text = now.isoformat(timespec="seconds")
        summary: dict[str, Any] = {
            "product_id": product_id,
            "name": product["name"],
            "status": "unknown",
            "current_price": float(product["current_price"]),
            "list_price": float(product["list_price"] or 0),
            "source_url": str(product.get("source_url") or ""),
            "in_stock": False,
            "fresh_count": 0,
            "source_count": len(sources),
            "errors": [],
            "history_recorded": False,
            "last_checked_at": now_text,
            "last_success_at": str(product.get("last_success_at") or ""),
        }

        if not sources:
            self.db.update_live_product(
                product_id,
                last_checked_at=now_text,
                live_status="no_sources",
                live_error="No live source URLs are attached to this product.",
            )
            summary["status"] = "no_sources"
            summary["errors"] = ["No live source URLs are attached to this product."]
            return summary

        fresh = [
            source
            for source in sources
            if str(source.get("last_status") or "") == "ok"
            and source.get("last_price") is not None
            and not is_stale(
                source.get("last_success_at"), self.stale_hours, now=now
            )
        ]
        summary["fresh_count"] = len(fresh)

        if not fresh:
            has_last_good = any(source.get("last_price") is not None for source in sources)
            status = "stale" if has_last_good else "error"
            errors = [
                f"{source.get('retailer') or 'Marketplace'}: "
                f"{source.get('last_error') or 'no recent successful quote'}"
                for source in sources
            ]
            message = (
                "No recent successful live quote. Showing the last successful "
                "price as stale data." if has_last_good else "Every live source failed."
            )
            self.db.update_live_product(
                product_id,
                last_checked_at=now_text,
                live_status=status,
                live_error="; ".join(errors)[:1000] or message,
            )
            summary.update(
                {
                    "status": status,
                    "errors": errors,
                    "last_checked_at": now_text,
                }
            )
            return summary

        offers = {
            str(offer.get("source_url") or ""): offer
            for offer in self.db.get_offers(product_id)
            if offer.get("is_live")
        }
        fresh_offers = [
            offers[str(source["url"])]
            for source in fresh
            if str(source["url"]) in offers
        ]
        in_stock = [offer for offer in fresh_offers if offer.get("in_stock")]
        all_ok = len(fresh) == len(sources)
        errors = [
            f"{source.get('retailer') or 'Marketplace'}: "
            f"{source.get('last_error') or 'quote is stale'}"
            for source in sources
            if source not in fresh
        ]
        last_success_at = max(
            (str(source.get("last_success_at") or "") for source in fresh),
            default="",
        )

        if in_stock:
            selected = min(
                in_stock,
                key=lambda offer: (
                    float(offer.get("price") or 0),
                    str(offer.get("seller") or ""),
                ),
            )
            price = round(float(selected["price"]), 2)
            list_price = round(float(selected.get("list_price") or 0), 2)
            if list_price <= price:
                list_price = 0
            status = "ok" if all_ok else "partial"
            self.db.update_live_product(
                product_id,
                current_price=price,
                list_price=list_price,
                source_url=str(selected.get("source_url") or ""),
                last_checked_at=now_text,
                last_success_at=last_success_at,
                live_status=status,
                live_error="; ".join(errors)[:1000],
            )
            summary.update(
                {
                    "status": status,
                    "current_price": price,
                    "list_price": list_price,
                    "source_url": str(selected.get("source_url") or ""),
                    "in_stock": True,
                    "errors": errors,
                    "last_success_at": last_success_at,
                }
            )
            if record_history:
                retailers = sorted(
                    {
                        str(offer.get("retailer") or "")
                        for offer in in_stock
                        if offer.get("retailer")
                    }
                )
                source_label = "Live quote"
                if retailers:
                    source_label += " · " + ", ".join(retailers)
                self.db.replace_live_observation(
                    product_id, price, source=source_label
                )
                summary["history_recorded"] = True
            return summary

        status = "out_of_stock" if all_ok else "partial"
        self.db.update_live_product(
            product_id,
            last_checked_at=now_text,
            last_success_at=last_success_at,
            live_status=status,
            live_error=(
                "All live sources currently show out of stock."
                if status == "out_of_stock"
                else "; ".join(errors)[:1000]
            ),
        )
        summary.update(
            {
                "status": status,
                "errors": errors,
                "last_success_at": last_success_at,
            }
        )
        return summary

    def recompute_product(self, product_id: int) -> dict[str, Any]:
        """Recalculate the product's current price from its recorded offers."""

        return self._recompute_product(product_id)

    # ------------------------------------------------------------------
    # Import and source management
    # ------------------------------------------------------------------
    def import_product(
        self,
        url: str,
        *,
        label: str = "",
        category: str = "Auto-detect",
    ) -> dict[str, Any]:
        """Create a live product from one public product-page URL."""

        url = normalise_url(url)
        existing = self.db.get_live_source_by_url(url)
        if existing is not None:
            product = self.db.get_product(int(existing["product_id"]))
            if product is None:
                raise ValueError("The URL points to a missing product record.")
            if str(product.get("data_origin") or "demo") != "live":
                raise ValueError(
                    "That URL is attached to a demo product. Remove the stale source "
                    "before importing it as a live product."
                )
            return {
                "ok": True,
                "created": False,
                "product_id": int(product["id"]),
                "product": product,
                "quote": None,
                "warnings": (),
                "message": (
                    f"This URL is already imported for {product['name']}. "
                    "Use Refresh to update the quote."
                ),
            }

        quote = self._scrape(url)
        self._require_inr(quote)
        chosen_category = (
            infer_category(quote.title, quote.description)
            if category.strip().lower() in {"", "auto-detect", "auto detect"}
            else category.strip()
        )
        emoji = _CATEGORY_EMOJI.get(chosen_category, "🛍️")
        now = _now_iso()
        product_id = self.db.create_product(
            name=quote.title,
            brand=quote.brand,
            category=chosen_category,
            description=quote.description,
            emoji=emoji,
            current_price=quote.price,
            list_price=quote.list_price or 0,
            currency="INR",
            data_origin="live",
            source_url=quote.url,
            last_checked_at=now,
            last_success_at=now,
            live_status="ok",
            live_error="",
        )
        try:
            self._record_quote(product_id, quote, label=label)
            summary = self._recompute_product(product_id)
            record_import_alert(
                self.db, self._snapshot_for_alerts(product_id)
            )
        except Exception:
            self.db.delete_product(product_id)
            raise

        warnings = list(quote.warnings)
        if quote.list_price is None:
            warnings.append(
                "No list/MRP price was detected, so the discount is not shown."
            )
        if not quote.in_stock:
            warnings.append(
                "The page currently shows this item as out of stock; no live "
                "history point was recorded."
            )
        return {
            "ok": True,
            "created": True,
            "product_id": product_id,
            "product": self.db.get_product(product_id),
            "quote": quote,
            "warnings": tuple(dict.fromkeys(warnings)),
            "summary": summary,
            "message": (
                f"Imported {quote.title} from {quote.retailer} at "
                f"₹{quote.price:,.2f}."
            ),
        }

    def add_source(
        self,
        product_id: int,
        url: str,
        *,
        label: str = "",
    ) -> dict[str, Any]:
        """Attach another marketplace product URL to a live product."""

        product = self.db.get_product(product_id)
        if product is None:
            raise ValueError("Product not found.")
        if str(product.get("data_origin") or "demo") != "live":
            raise ValueError(
                "Live sources can only be added to live-imported products. Demo "
                "products stay synthetic so live and demo data are never mixed."
            )

        url = normalise_url(url)
        existing = self.db.get_live_source_by_url(url)
        if existing is not None:
            if int(existing["product_id"]) == product_id:
                result = self.refresh_source(int(existing["id"]))
                result["message"] = (
                    "That URL was already attached; its quote was refreshed instead."
                )
                return result
            other = self.db.get_product(int(existing["product_id"]))
            other_name = other["name"] if other else "another product"
            raise ValueError(f"That URL is already attached to {other_name}.")

        quote = self._scrape(url)
        self._require_inr(quote)
        warnings = list(quote.warnings)
        similarity = title_similarity(str(product["name"]), quote.title)
        if similarity < 0.15:
            warnings.append(
                "The page title differs substantially from this product. Check "
                "that the URL points to the same item before trusting the comparison."
            )
        before = self._snapshot_for_alerts(product_id)
        source = self._record_quote(product_id, quote, label=label)
        summary = self._recompute_product(product_id)
        record_refresh_alerts(
            self.db, before, self._snapshot_for_alerts(product_id)
        )
        return {
            "ok": True,
            "created": False,
            "product_id": product_id,
            "product": self.db.get_product(product_id),
            "quote": quote,
            "source": source,
            "summary": summary,
            "warnings": tuple(dict.fromkeys(warnings)),
            "message": (
                f"Added {quote.retailer} at ₹{quote.price:,.2f} to "
                f"{product['name']}."
            ),
        }

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def _refresh_source_quote(self, source: dict[str, Any]) -> dict[str, Any]:
        try:
            quote = self._scrape(str(source["url"]))
            self._require_inr(quote)
            self._record_quote(
                int(source["product_id"]),
                quote,
                label=str(source.get("label") or ""),
            )
            return {
                "source_id": int(source["id"]),
                "url": str(source["url"]),
                "retailer": quote.retailer,
                "ok": True,
                "price": quote.price,
                "currency": quote.currency,
                "error": "",
                "code": "",
            }
        except ScrapeError as exc:
            self._record_failure(source, exc)
            return {
                "source_id": int(source["id"]),
                "url": str(source["url"]),
                "retailer": str(source.get("retailer") or ""),
                "ok": False,
                "price": None,
                "currency": str(source.get("last_currency") or "INR"),
                "error": exc.message,
                "code": exc.code,
            }

    def refresh_source(self, source_id: int) -> dict[str, Any]:
        source = self.db.get_live_source(source_id)
        if source is None:
            raise ValueError("Live source not found.")
        product = self.db.get_product(int(source["product_id"]))
        if product is None:
            raise ValueError("Product not found.")
        if str(product.get("data_origin") or "demo") != "live":
            raise ValueError("Only live-imported products can be refreshed as live.")

        before = self._snapshot_for_alerts(int(source["product_id"]))
        result = self._refresh_source_quote(source)
        summary = self._recompute_product(int(source["product_id"]))
        record_refresh_alerts(
            self.db,
            before,
            self._snapshot_for_alerts(int(source["product_id"])),
        )
        return {
            "ok": bool(result["ok"]),
            "source": result,
            "summary": summary,
            "product_id": int(source["product_id"]),
            "message": (
                f"Refreshed {result['retailer']} at ₹{result['price']:,.2f}."
                if result["ok"] and result["price"] is not None
                else result["error"]
            ),
        }

    def refresh_product(
        self, product_id: int, *, only_stale: bool = False
    ) -> dict[str, Any]:
        product = self.db.get_product(product_id)
        if product is None:
            raise ValueError("Product not found.")
        if str(product.get("data_origin") or "demo") != "live":
            raise ValueError("Only live-imported products can be refreshed as live.")

        if only_stale and not self._product_needs_refresh(product):
            return {
                "ok": True,
                "skipped": True,
                "product_id": product_id,
                "name": product["name"],
                "status": str(product.get("live_status") or "ok"),
                "current_price": float(product["current_price"]),
                "source_count": len(self.db.get_live_sources(product_id)),
                "sources": [],
                "errors": [],
                "checked_at": _now_iso(),
                "message": "This quote is already fresh; no check was needed.",
            }

        before = self._snapshot_for_alerts(product_id)
        sources = self.db.get_live_sources(product_id)
        results = [self._refresh_source_quote(source) for source in sources]
        summary = self._recompute_product(product_id)
        summary["sources"] = results
        summary["ok"] = any(result["ok"] for result in results) if results else False
        summary["skipped"] = False
        summary["checked_at"] = _now_iso()
        record_refresh_alerts(
            self.db, before, self._snapshot_for_alerts(product_id)
        )
        return summary

    def refresh_all(self, *, only_stale: bool = False) -> dict[str, Any]:
        products = self.db.get_live_products()
        results = [
            self.refresh_product(int(product["id"]), only_stale=only_stale)
            for product in products
        ]
        checked = [result for result in results if not result.get("skipped")]
        return {
            "products": results,
            "total": len(results),
            "refreshed": sum(1 for result in checked if result.get("ok")),
            "failed": sum(1 for result in checked if not result.get("ok")),
            "skipped": len(results) - len(checked),
            "checked_at": _now_iso(),
        }

    def refresh_stale(self) -> dict[str, Any]:
        """Refresh only live products whose quote is stale or failed."""

        return self.refresh_all(only_stale=True)

    def remove_source(self, source_id: int) -> dict[str, Any]:
        source = self.db.get_live_source(source_id)
        if source is None:
            return {
                "ok": False,
                "message": "That live source no longer exists.",
                "summary": None,
            }
        product_id = int(source["product_id"])
        removed = self.db.remove_live_source(source_id)
        summary = self._recompute_product(product_id)
        return {
            "ok": removed,
            "product_id": product_id,
            "summary": summary,
            "message": (
                "Removed the source URL and its last recorded quote."
                if removed
                else "The source URL could not be removed."
            ),
        }

    def remove_product(self, product_id: int) -> dict[str, Any]:
        """Remove a live-imported product and all of its recorded live data.

        Demo products are deliberately protected: they belong to the sample
        catalog and are not user imports. Dependent history, offers, sources, and
        watchlist rows are removed by the database's cascading foreign keys.
        """

        product = self.db.get_product(product_id)
        if product is None:
            raise ValueError("Product not found.")
        if str(product.get("data_origin") or "demo") != "live":
            raise ValueError(
                "Only live-imported products can be removed here. Demo products "
                "are part of the sample catalog."
            )

        name = str(product.get("name") or "Live product")
        if not self.db.delete_product(product_id):
            raise ValueError("The live product could not be removed.")
        return {
            "ok": True,
            "product_id": product_id,
            "name": name,
            "message": f"Removed {name} and its recorded live quotes.",
        }

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------
    def source_rows(self, product_id: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            source_view(source, self.stale_hours, now=now)
            for source in self.db.get_live_sources(product_id)
        ]

    @property
    def default_stale_hours(self) -> int:
        return int(self.settings.live_stale_hours or DEFAULT_STALE_HOURS)
