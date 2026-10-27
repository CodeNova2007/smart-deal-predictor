"""Live marketplace quote ingestion.

The package is intentionally separate from the demo analytics layer. A live
product has ``data_origin = 'live'`` and its offers/history come from public
product pages fetched on demand. Demo products remain synthetic.
"""

from .scraper import (
    LiveQuote,
    ScrapeError,
    detect_retailer,
    is_product_page_url,
    parse_product_page,
    scrape_product,
    validate_product_page_url,
)
from .service import LiveService
from .status import DEFAULT_STALE_HOURS, is_stale, live_product_view, source_view

__all__ = [
    "DEFAULT_STALE_HOURS",
    "LiveQuote",
    "LiveService",
    "ScrapeError",
    "detect_retailer",
    "is_product_page_url",
    "is_stale",
    "live_product_view",
    "parse_product_page",
    "scrape_product",
    "source_view",
    "validate_product_page_url",
]
