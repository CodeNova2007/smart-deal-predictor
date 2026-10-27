"""Public product-page scraping for live marketplace quotes.

The scraper is deliberately conservative:

* it only fetches public ``http(s)`` product pages;
* it rejects localhost/private addresses to avoid SSRF;
* it checks ``robots.txt`` by default and rate-limits requests per host;
* it never bypasses logins, CAPTCHAs, paywalls, or anti-bot controls;
* it fails loudly instead of guessing a price when the page cannot be parsed.

Amazon.in and Flipkart have dedicated selectors. Other retailers fall back to
JSON-LD, microdata, and OpenGraph metadata, which many product pages expose.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36 AI-Smart-Deal-Predictor/1.0"
)

_BLOCK_MARKERS = (
    "captcha",
    "robot check",
    "enter the characters you see",
    "not a robot",
    "access denied",
    "unusual traffic",
    "verify you are a human",
    "request blocked",
    "bot detection",
    "click the button below to continue shopping",
    "automated access",
)

_OUT_OF_STOCK_MARKERS = (
    "outofstock",
    "out of stock",
    "sold out",
    "currently unavailable",
    "temporarily unavailable",
    "discontinued",
)
_IN_STOCK_MARKERS = (
    "instock",
    "in stock",
    "available",
    "add to cart",
    "buy now",
)

_CURRENCY_SYMBOLS = {
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}


@dataclass(frozen=True)
class Retailer:
    slug: str
    name: str
    domains: tuple[str, ...] = ()


RETAILERS: tuple[Retailer, ...] = (
    Retailer("amazon_in", "Amazon.in", ("amazon.in",)),
    Retailer("flipkart", "Flipkart", ("flipkart.com",)),
    Retailer("croma", "Croma", ("croma.com",)),
    Retailer("reliance_digital", "Reliance Digital", ("reliancedigital.in",)),
    Retailer("vijay_sales", "Vijay Sales", ("vijaysales.com",)),
    Retailer("tata_cliq", "Tata CLiQ", ("tatacliq.com",)),
    Retailer("jiomart", "JioMart", ("jiomart.com",)),
    Retailer("snapdeal", "Snapdeal", ("snapdeal.com",)),
    Retailer("meesho", "Meesho", ("meesho.com",)),
    Retailer("nykaa", "Nykaa", ("nykaa.com",)),
    Retailer("myntra", "Myntra", ("myntra.com",)),
    Retailer("ajio", "AJIO", ("ajio.com",)),
)


@dataclass(frozen=True)
class LiveQuote:
    url: str
    retailer: str
    title: str
    price: float
    currency: str
    seller: str
    in_stock: bool
    availability: str
    brand: str = ""
    description: str = ""
    list_price: float | None = None
    image_url: str = ""
    extraction_method: str = "json-ld"
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    warnings: tuple[str, ...] = ()


class ScrapeError(Exception):
    """A user-safe scraping failure.

    ``message`` is suitable for display in the Streamlit UI. It never contains
    raw HTML, stack traces, or secrets.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "scrape_failed",
        url: str = "",
        retailer: str = "",
        status_code: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.url = url
        self.retailer = retailer
        self.status_code = status_code
        self.retryable = retryable


_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST: dict[str, float] = {}


def normalise_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ScrapeError("Paste a product URL first.", code="invalid_url")
    if "://" not in value:
        value = "https://" + value.lstrip("/")
    return value


def detect_retailer(url: str) -> Retailer:
    host = (urlparse(url).hostname or "").lower().strip(".")
    for retailer in RETAILERS:
        if any(host == domain or host.endswith("." + domain) for domain in retailer.domains):
            return retailer
    return Retailer("generic", host.removeprefix("www.") or "Marketplace")


_BLOCKED_PATH_SEGMENTS = {
    "search",
    "category",
    "categories",
    "collection",
    "collections",
    "browse",
    "results",
    "list",
    "store",
    "stores",
    "brand",
    "brands",
    "seller",
    "sellers",
    "wishlist",
    "cart",
    "account",
    "login",
    "signin",
}
_BLOCKED_QUERY_KEYS = {
    "k",
    "q",
    "search",
    "query",
    "keyword",
    "keywords",
    "searchterm",
}
# A single generic path segment is usually a listing or landing page rather than
# one item. Detail pages normally include an identifier or a second segment.
_LISTING_ONLY_SEGMENTS = {
    "products",
    "product",
    "shop",
    "catalog",
    "catalogue",
    "deals",
    "offers",
    "new",
    "bestsellers",
}


def is_product_page_url(url: str, retailer: Retailer | None = None) -> bool:
    """Return whether a URL looks like one product page, not a listing.

    This is a structural check, not a guarantee. The page still has to expose a
    readable price before the importer will accept it.
    """

    retailer = retailer or detect_retailer(url)
    parsed = urlparse(url)
    path = (parsed.path or "/").lower()
    segments = [segment for segment in path.split("/") if segment]

    if retailer.slug == "amazon_in":
        return any(
            marker in path
            for marker in ("/dp/", "/gp/product/", "/gp/aw/d/", "/exec/obidos/asin/")
        )
    if retailer.slug == "flipkart":
        return "/p/" in path

    if not segments:
        return False
    if any(segment in _BLOCKED_PATH_SEGMENTS for segment in segments):
        return False
    if segments[0] in {"s", "c"}:
        return False
    if len(segments) == 1 and segments[0] in _LISTING_ONLY_SEGMENTS:
        return False
    query_keys = {key.lower() for key in parse_qs(parsed.query).keys()}
    if query_keys & _BLOCKED_QUERY_KEYS:
        return False
    return True


def validate_product_page_url(url: str, retailer: Retailer | None = None) -> str:
    retailer = retailer or detect_retailer(url)
    if not is_product_page_url(url, retailer):
        raise ScrapeError(
            "That URL looks like a search, category, or store page. Open one "
            "specific product and copy its address-bar URL. Amazon.in product "
            "URLs contain /dp/; Flipkart product URLs contain /p/.",
            code="not_product_page",
            url=url,
            retailer=retailer.name,
        )
    return url


def validate_public_url(url: str, *, allow_private: bool = False) -> str:
    """Reject malformed URLs and addresses that could reach the local network."""

    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ScrapeError("That URL could not be parsed.", code="invalid_url") from exc

    if parsed.scheme not in {"http", "https"}:
        raise ScrapeError("Only http and https product URLs are supported.", code="invalid_url")
    if not parsed.hostname:
        raise ScrapeError("The URL is missing a hostname.", code="invalid_url")
    if parsed.username or parsed.password:
        raise ScrapeError(
            "URLs containing usernames or passwords are not supported.",
            code="invalid_url",
        )

    host = parsed.hostname.lower().strip(".")
    if (
        host == "localhost"
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
        or host.endswith(".home.arpa")
    ):
        raise ScrapeError(
            "Local and private addresses cannot be scraped.", code="blocked_address"
        )
    if allow_private:
        return url
    if "." not in host:
        raise ScrapeError(
            "Use a public product URL with a normal domain name.",
            code="blocked_address",
        )

    try:
        addresses = socket.getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise ScrapeError(
            f"The hostname {host} could not be resolved. Check the URL and your connection.",
            code="invalid_url",
        ) from exc

    for address in addresses:
        raw_ip = address[4][0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if not ip.is_global:
            raise ScrapeError(
                "Local, private, or reserved addresses cannot be scraped.",
                code="blocked_address",
            )
    return url


def _headers(user_agent: str, *, accept: str = "text/html,application/xhtml+xml") -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": accept,
        "Accept-Language": "en-IN,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _throttle(host: str, min_interval: float) -> None:
    if min_interval <= 0:
        return
    wait = 0.0
    with _THROTTLE_LOCK:
        now = time.monotonic()
        available_at = _LAST_REQUEST.get(host, 0.0) + min_interval
        if available_at > now:
            wait = available_at - now
        _LAST_REQUEST[host] = max(now, available_at)
    if wait > 0:
        time.sleep(wait)


def _robots_allowed(
    url: str,
    *,
    session: requests.Session,
    user_agent: str,
    timeout: float,
) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = session.get(
            robots_url,
            headers=_headers(user_agent, accept="text/plain,*/*"),
            timeout=timeout,
            allow_redirects=True,
        )
    except requests.Timeout as exc:
        raise ScrapeError(
            "The retailer's robots.txt check timed out. Try again later.",
            code="robots_unavailable",
            retryable=True,
        ) from exc
    except requests.RequestException as exc:
        raise ScrapeError(
            "Could not verify the retailer's robots.txt rules. Try again later.",
            code="robots_unavailable",
            retryable=True,
        ) from exc

    status = int(getattr(response, "status_code", 0) or 0)
    if status in {401, 403}:
        return False
    if status >= 500:
        raise ScrapeError(
            "The retailer's robots.txt is temporarily unavailable. Try again later.",
            code="robots_unavailable",
            status_code=status,
            retryable=True,
        )
    if status >= 400:
        return True

    parser = RobotFileParser()
    parser.parse((getattr(response, "text", "") or "").splitlines())
    return parser.can_fetch(user_agent, url)


def _fetch_html(
    url: str,
    *,
    session: requests.Session,
    timeout: float,
    user_agent: str,
    max_bytes: int,
) -> tuple[str, str]:
    try:
        response = session.get(
            url,
            headers=_headers(user_agent),
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
    except requests.Timeout as exc:
        raise ScrapeError(
            "The retailer took too long to respond. Try again in a moment.",
            code="timeout",
            retryable=True,
        ) from exc
    except requests.RequestException as exc:
        raise ScrapeError(
            "The retailer could not be reached. Check your connection and the URL.",
            code="network_error",
            retryable=True,
        ) from exc

    try:
        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429:
            raise ScrapeError(
                "The retailer is rate-limiting requests. Wait a little and try again.",
                code="rate_limited",
                status_code=status,
                retryable=True,
            )
        if status in {401, 403}:
            raise ScrapeError(
                "The retailer refused the request. The page may require a login "
                "or may block automated access.",
                code="forbidden",
                status_code=status,
            )
        if status >= 500:
            raise ScrapeError(
                "The retailer returned a server error. Try again later.",
                code="server_error",
                status_code=status,
                retryable=True,
            )
        if status >= 400:
            raise ScrapeError(
                f"The product page returned HTTP {status}. Check that the URL is correct.",
                code="http_error",
                status_code=status,
            )

        content_type = (response.headers.get("Content-Type") or "").lower()
        if content_type and "html" not in content_type and "text/" not in content_type:
            raise ScrapeError(
                "That URL did not return an HTML product page.",
                code="not_html",
                status_code=status,
            )

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65_536):
            if not chunk:
                continue
            total += len(chunk)
            if max_bytes and total > max_bytes:
                raise ScrapeError(
                    "The product page is too large to process safely.",
                    code="too_large",
                )
            chunks.append(chunk)
        raw = b"".join(chunks)
        if not raw.strip():
            raise ScrapeError(
                "The retailer returned an empty page.", code="empty_page", retryable=True
            )
        encoding = getattr(response, "encoding", None) or "utf-8"
        html = raw.decode(encoding, errors="replace")
        final_url = str(getattr(response, "url", url) or url)
        return html, final_url
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("name") or value.get("@value") or value.get("value") or ""
    if isinstance(value, (list, tuple)):
        value = " ".join(_clean_text(item) for item in value if item is not None)
    return re.sub(r"\s+", " ", str(value)).strip()


def _walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for key in ("@graph", "mainEntity", "hasVariant", "isSimilarTo", "itemListElement"):
            if key in value:
                yield from _walk_json(value[key])
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _node_types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return {raw.lower()}
    if isinstance(raw, (list, tuple)):
        return {str(item).lower() for item in raw}
    return set()


def _iter_json_ld(soup: BeautifulSoup) -> Iterable[dict[str, Any]]:
    for script in soup.find_all("script"):
        script_type = str(script.get("type") or "").lower()
        if "ld+json" not in script_type:
            continue
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            parsed = json.loads(raw.strip())
        except (TypeError, ValueError):
            continue
        yield from _walk_json(parsed)


def _parse_price_text(
    value: Any, *, currency_hint: str = ""
) -> tuple[float | None, str]:
    if value is None:
        return None, currency_hint.upper()
    if isinstance(value, dict):
        value = value.get("@value") or value.get("value") or value.get("price")
    text = _clean_text(value)
    if not text:
        return None, currency_hint.upper()

    currency = currency_hint.upper().strip()
    lowered = text.lower()
    for token, code in _CURRENCY_SYMBOLS.items():
        if token in lowered:
            currency = code
            break
    if any(symbol in text for symbol in ("$", "€", "£", "¥")):
        # The app only supports INR quotes, but report the detected currency so
        # the service can explain why the import was rejected.
        for symbol, code in (("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("¥", "JPY")):
            if symbol in text:
                currency = code
                break

    match = re.search(r"(\d[\d,]*(?:\.\d{1,2})?)", text)
    if not match:
        return None, currency
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None, currency
    if amount <= 0 or amount > 100_000_000:
        return None, currency
    return round(amount, 2), currency


def _availability_state(value: Any, extra_text: str = "") -> tuple[bool, str]:
    haystack = f"{_clean_text(value)} {extra_text}".lower()
    if any(marker in haystack for marker in _OUT_OF_STOCK_MARKERS):
        return False, "Out of stock"
    if any(marker in haystack for marker in _IN_STOCK_MARKERS):
        return True, "In stock"
    return True, "Availability not confirmed"


def _seller_name(value: Any) -> str:
    if isinstance(value, dict):
        return _clean_text(value.get("name") or value.get("@id"))
    return _clean_text(value)


def _list_price_from_specs(offer: dict[str, Any]) -> float | None:
    specs = offer.get("priceSpecification")
    if isinstance(specs, dict):
        specs = [specs]
    if not isinstance(specs, list):
        return None
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        price_type = _clean_text(spec.get("priceType")).lower()
        if any(word in price_type for word in ("list", "msrp", "strikethrough", "mrp")):
            amount, _ = _parse_price_text(spec.get("price"))
            if amount:
                return amount
    return None


def _offer_fields(offer: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(offer, dict):
        return {}
    price, currency = _parse_price_text(
        offer.get("price") or offer.get("lowPrice"),
        currency_hint=_clean_text(offer.get("priceCurrency")),
    )
    list_price, list_currency = _parse_price_text(
        offer.get("listPrice") or offer.get("highPrice"),
        currency_hint=_clean_text(offer.get("priceCurrency")),
    )
    spec_list = _list_price_from_specs(offer)
    if spec_list:
        list_price = spec_list
    in_stock, availability = _availability_state(
        offer.get("availability"), _clean_text(offer.get("itemCondition"))
    )
    return {
        "price": price,
        "currency": currency or list_currency,
        "list_price": list_price,
        "seller": _seller_name(offer.get("seller")),
        "in_stock": in_stock,
        "availability": availability,
    }


def _json_ld_fields(soup: BeautifulSoup) -> dict[str, Any]:
    nodes = list(_iter_json_ld(soup))
    candidates = [
        node for node in nodes if _node_types(node) & {"product", "productgroup"}
    ]
    if not candidates:
        candidates = [node for node in nodes if node.get("offers")]

    best: dict[str, Any] = {}
    for node in candidates:
        offers = node.get("offers")
        variants = node.get("hasVariant")
        if isinstance(variants, list):
            for variant in variants:
                if not isinstance(variant, dict):
                    continue
                offer = _offer_fields(variant.get("offers") or {})
                if offer.get("price"):
                    offers = variant.get("offers")
                    node = {**node, **variant}
                    break
        if isinstance(offers, list):
            parsed_offers = [
                _offer_fields(offer) for offer in offers if isinstance(offer, dict)
            ]
            parsed_offers = [item for item in parsed_offers if item.get("price")]
            parsed_offers.sort(key=lambda item: (not item["in_stock"], item["price"]))
            offer = parsed_offers[0] if parsed_offers else {}
        elif isinstance(offers, dict):
            offer = _offer_fields(offers)
        else:
            offer = {}
        if not offer.get("price"):
            continue
        brand = node.get("brand")
        image = node.get("image")
        if isinstance(image, list):
            image = image[0] if image else ""
        if isinstance(image, dict):
            image = image.get("url") or image.get("contentUrl") or ""
        fields = {
            "title": _clean_text(node.get("name")),
            "brand": _clean_text(brand),
            "description": _clean_text(node.get("description"))[:1200],
            "image_url": _clean_text(image),
            **offer,
        }
        if not best or (fields.get("price") and not best.get("price")):
            best = fields
        if best.get("price"):
            break
    if best:
        best["extraction_method"] = "json-ld"
    return best


def _select_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = _clean_text(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _select_attr(soup: BeautifulSoup, selectors: Iterable[str], attr: str) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            value = node.get(attr)
            if value:
                return _clean_text(value)
    return ""


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        node = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if node and node.get("content"):
            return _clean_text(node.get("content"))
    return ""


def _amazon_fields(soup: BeautifulSoup) -> dict[str, Any]:
    title = _select_text(soup, ("#productTitle", "#title"))
    price_text = _select_text(
        soup,
        (
            "#corePrice_feature_div .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#priceblock_saleprice",
            "#tp_price_block_total_price_ww .a-offscreen",
            ".a-price .a-offscreen",
        ),
    )
    price, currency = _parse_price_text(price_text, currency_hint="INR")
    list_text = _select_text(
        soup,
        (
            "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
            "#corePrice_feature_div .basisPrice .a-offscreen",
            "#listPrice",
            "#priceblock_listprice",
            "span.a-price.a-text-price .a-offscreen",
        ),
    )
    list_price, _ = _parse_price_text(list_text, currency_hint="INR")
    availability_text = _select_text(soup, ("#availability", "#outOfStock"))
    in_stock, availability = _availability_state(availability_text)
    seller = _select_text(soup, ("#sellerProfileTriggerId", "#merchant-info", "#tabular-buybox"))
    seller_match = re.search(
        r"(?:Sold by|Ships from and sold by)\s+(.+?)(?:\.|$)", seller, re.IGNORECASE
    )
    if seller_match:
        seller = seller_match.group(1).strip()
    brand_text = _select_text(soup, ("#bylineInfo", "a#bylineInfo"))
    brand_match = re.search(r"(?:Visit the|Brand:)\s*(.+?)(?:\s+Store)?$", brand_text, re.IGNORECASE)
    if brand_match:
        brand_text = brand_match.group(1).strip()
    description = _select_text(soup, ("#feature-bullets", "#productDescription"))
    image_url = _select_attr(
        soup, ("#landingImage", "#imgTagWrapperId img"), "data-old-hires"
    ) or _select_attr(soup, ("#landingImage", "#imgTagWrapperId img"), "src")
    fields: dict[str, Any] = {
        "title": title,
        "brand": brand_text,
        "description": description[:1200],
        "image_url": image_url,
        "price": price,
        "currency": currency,
        "list_price": list_price,
        "seller": seller,
        "in_stock": in_stock,
        "availability": availability,
        "extraction_method": "amazon",
    }
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _flipkart_fields(soup: BeautifulSoup) -> dict[str, Any]:
    title = _select_text(soup, ("span.B_NuCI", "h1 span", "h1"))
    price_text = _select_text(
        soup,
        (
            "div._30jeq3._16Jk6d",
            "div._30jeq3",
            "div.Nx9bqj",
            "div._16Jk6d",
        ),
    )
    price, currency = _parse_price_text(price_text, currency_hint="INR")
    list_text = _select_text(
        soup,
        (
            "div._3I9_wc._2p6lqe",
            "div._3I9_wc",
            "div.yRaY8j",
        ),
    )
    list_price, _ = _parse_price_text(list_text, currency_hint="INR")
    seller = _select_text(soup, ("#sellerName span", "#sellerName", "div._1RLviY"))
    seller_match = re.search(r"Seller:\s*(.+?)(?:\s|$)", seller, re.IGNORECASE)
    if seller_match:
        seller = seller_match.group(1).strip()
    page_text = soup.get_text(" ", strip=True)
    in_stock, availability = _availability_state("", page_text[:5000])
    description = _select_text(soup, ("div._1mXcCf", "div._1AN-Df"))
    image_url = _select_attr(
        soup, ("img._396cs4", "img.q6DClP", "img._2r_T1I"), "src"
    )
    fields: dict[str, Any] = {
        "title": title,
        "description": description[:1200],
        "image_url": image_url,
        "price": price,
        "currency": currency,
        "list_price": list_price,
        "seller": seller,
        "in_stock": in_stock,
        "availability": availability,
        "extraction_method": "flipkart",
    }
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _generic_fields(soup: BeautifulSoup) -> dict[str, Any]:
    price_text = (
        _select_attr(soup, ('[itemprop="price"]',), "content")
        or _select_text(soup, ('[itemprop="price"]',))
        or _meta(soup, "product:price:amount", "og:price:amount")
    )
    currency_hint = (
        _select_attr(soup, ('[itemprop="priceCurrency"]',), "content")
        or _meta(soup, "product:price:currency", "og:price:currency")
    )
    price, currency = _parse_price_text(price_text, currency_hint=currency_hint)

    list_text = (
        _select_attr(soup, ('[itemprop="listPrice"]',), "content")
        or _select_text(soup, ('[itemprop="listPrice"]',))
        or _meta(soup, "product:list_price:amount")
    )
    list_price, _ = _parse_price_text(list_text, currency_hint=currency)

    availability_text = (
        _select_attr(soup, ('[itemprop="availability"]',), "href")
        or _select_attr(soup, ('[itemprop="availability"]',), "content")
        or _meta(soup, "product:availability", "og:availability")
    )
    in_stock, availability = _availability_state(availability_text)

    title = (
        _select_text(soup, ('[itemprop="name"]',))
        or _meta(soup, "og:title", "twitter:title")
        or _clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
    )
    description = (
        _select_text(soup, ('[itemprop="description"]',))
        or _meta(soup, "og:description", "description")
    )
    brand = (
        _select_text(soup, ('[itemprop="brand"]',))
        or _meta(soup, "product:brand")
    )
    image_url = _meta(soup, "og:image", "twitter:image") or _select_attr(
        soup, ('[itemprop="image"]',), "src"
    )
    fields: dict[str, Any] = {
        "title": title,
        "brand": brand,
        "description": description[:1200],
        "image_url": image_url,
        "price": price,
        "currency": currency,
        "list_price": list_price,
        "seller": _meta(soup, "product:seller"),
        "in_stock": in_stock,
        "availability": availability,
        "extraction_method": "metadata",
    }
    return {key: value for key, value in fields.items() if value not in (None, "")}


def _is_block_page(soup: BeautifulSoup) -> bool:
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    visible = soup.get_text(" ", strip=True)[:6000]
    haystack = f"{title} {visible}".lower()
    return any(marker in haystack for marker in _BLOCK_MARKERS)


def _clean_title(title: str, retailer: Retailer) -> str:
    text = _clean_text(title)
    suffixes = (
        f" : {retailer.name}",
        f" | {retailer.name}",
        f" - {retailer.name}",
        " : Amazon.in",
        " | Flipkart.com",
        " - Buy Online at Best Price",
    )
    for suffix in suffixes:
        if text.lower().endswith(suffix.lower()):
            text = text[: -len(suffix)].strip()
    return text[:300]


def _parse_page(html: str, url: str, retailer: Retailer) -> LiveQuote:
    soup = BeautifulSoup(html, "html.parser")
    if _is_block_page(soup):
        raise ScrapeError(
            "The retailer returned a bot-check or access-denied page. This app does "
            "not bypass CAPTCHAs or anti-bot controls. Try again later or use an "
            "official API/affiliate feed.",
            code="blocked",
            url=url,
            retailer=retailer.name,
        )

    structured = _json_ld_fields(soup)
    if retailer.slug == "amazon_in":
        adapter = _amazon_fields(soup)
    elif retailer.slug == "flipkart":
        adapter = _flipkart_fields(soup)
    else:
        adapter = _generic_fields(soup)

    if retailer.slug in {"amazon_in", "flipkart"}:
        # Marketplace selectors are more specific than generic metadata, so the
        # adapter wins and structured data fills any gaps.
        fields = dict(structured)
        for key, value in adapter.items():
            if value not in (None, "", []):
                fields[key] = value
    else:
        # For other retailers, structured JSON-LD is the most reliable source;
        # page metadata is only a fallback (e.g. a bare <title> tag).
        fields = dict(adapter)
        fields.update(
            {key: value for key, value in structured.items() if value not in (None, "", [])}
        )
    if not fields.get("price"):
        fields.update(_generic_fields(soup))
    if not fields.get("title"):
        fields["title"] = _meta(soup, "og:title", "twitter:title") or (
            soup.title.get_text(" ", strip=True) if soup.title else ""
        )
    if not fields.get("description"):
        fields["description"] = _meta(soup, "og:description", "description")
    if not fields.get("image_url"):
        fields["image_url"] = _meta(soup, "og:image", "twitter:image")

    price = fields.get("price")
    if not price:
        raise ScrapeError(
            "No product price could be read from that page. The retailer may be "
            "showing an out-of-stock, login, or JavaScript-only page. The app does "
            "not guess a price.",
            code="price_not_found",
            url=url,
            retailer=retailer.name,
        )
    title = _clean_title(str(fields.get("title") or ""), retailer)
    if not title:
        raise ScrapeError(
            "The product title could not be read from that page.",
            code="title_not_found",
            url=url,
            retailer=retailer.name,
        )

    currency = str(fields.get("currency") or "INR").upper()
    list_price = fields.get("list_price")
    try:
        list_price_value = float(list_price) if list_price else None
    except (TypeError, ValueError):
        list_price_value = None
    if list_price_value is not None and list_price_value <= float(price):
        list_price_value = None

    warnings: list[str] = []
    if list_price_value is None:
        warnings.append("No list/MRP price was found, so no discount is shown.")
    warnings.append(
        "Coupon and delivery details are not inferred; only the listed price is recorded."
    )

    return LiveQuote(
        url=url,
        retailer=retailer.name,
        title=title,
        price=round(float(price), 2),
        currency=currency,
        seller=_clean_text(fields.get("seller")) or retailer.name,
        in_stock=bool(fields.get("in_stock", True)),
        availability=_clean_text(fields.get("availability")) or "Availability not confirmed",
        brand=_clean_text(fields.get("brand")),
        description=_clean_text(fields.get("description"))[:1200],
        list_price=round(list_price_value, 2) if list_price_value else None,
        image_url=_clean_text(fields.get("image_url")),
        extraction_method=_clean_text(fields.get("extraction_method")) or "metadata",
        warnings=tuple(warnings),
    )


def parse_product_page(
    html: str, url: str, *, validate_structure: bool = True
) -> LiveQuote:
    """Parse an already-downloaded product page.

    This is exposed for deterministic offline tests and for future ingestion
    adapters. It never fetches anything.
    """

    url = normalise_url(url)
    retailer = detect_retailer(url)
    if validate_structure:
        validate_product_page_url(url, retailer)
    return _parse_page(html, url, retailer)


def scrape_product(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: float = 15,
    user_agent: str = DEFAULT_USER_AGENT,
    min_interval: float = 2.0,
    max_bytes: int = 3_000_000,
    check_robots: bool = True,
    validate_url: bool = True,
    allow_private: bool = False,
) -> LiveQuote:
    """Fetch and parse one public product page.

    Tests can inject a fake session and disable robots/URL validation. Production
    callers should keep both checks enabled.
    """

    url = normalise_url(url)
    retailer = detect_retailer(url)
    validate_product_page_url(url, retailer)
    if validate_url:
        validate_public_url(url, allow_private=allow_private)
    session = session or requests.Session()
    if check_robots:
        if not _robots_allowed(
            url, session=session, user_agent=user_agent, timeout=timeout
        ):
            raise ScrapeError(
                "The retailer's robots.txt disallows automated access to this page.",
                code="robots_disallowed",
                url=url,
                retailer=retailer.name,
            )
    _throttle(urlparse(url).hostname or "", min_interval)
    html, final_url = _fetch_html(
        url,
        session=session,
        timeout=timeout,
        user_agent=user_agent,
        max_bytes=max_bytes,
    )
    final_retailer = detect_retailer(final_url)
    quote = _parse_page(html, final_url, final_retailer)
    return quote
