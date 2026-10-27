"""Shareable page, product, and comparison links.

The URL is the source of truth when a link is opened in a new browser session.
Query parameters are applied once per distinct URL and then kept in sync with
the app's navigation state.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping
from urllib.parse import urlencode, urlparse, urlunparse

import streamlit as st

PAGE_SLUGS = {
    "Dashboard": "dashboard",
    "Deals": "deals",
    "Products": "products",
    "Compare": "compare",
    "Live quotes": "live-quotes",
    "Watchlist": "watchlist",
    "Alerts": "alerts",
    "Purchases": "purchases",
    "Insights": "insights",
    "How it works": "how-it-works",
}
SLUG_PAGES = {slug: page for page, slug in PAGE_SLUGS.items()}
_MANAGED_KEYS = ("page", "product", "compare")


def _normalise_slug(value: str) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split()).replace(" ", "-")


def page_slug(page: str) -> str:
    return PAGE_SLUGS.get(page, "dashboard")


def page_from_slug(value: str) -> str | None:
    slug = _normalise_slug(value)
    if slug in SLUG_PAGES:
        return SLUG_PAGES[slug]
    normalised = slug.replace("-", " ")
    for page in PAGE_SLUGS:
        if page.lower() == normalised:
            return page
    return None


def build_query(
    page: str | None = None,
    product_id: int | None = None,
    compare_ids: Iterable[int] | None = None,
) -> dict[str, str]:
    query: dict[str, str] = {}
    if page:
        query["page"] = page_slug(page)
    if product_id is not None:
        try:
            query["product"] = str(int(product_id))
        except (TypeError, ValueError):
            pass
    ids: list[str] = []
    for value in compare_ids or []:
        try:
            product = int(value)
        except (TypeError, ValueError):
            continue
        if product > 0 and str(product) not in ids:
            ids.append(str(product))
        if len(ids) == 3:
            break
    if ids:
        query["compare"] = ",".join(ids)
    return query


def parse_compare(
    value: str | Iterable[str] | None,
    valid_ids: Iterable[int] | None = None,
) -> list[int]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = value.split(",")
    else:
        raw_values = list(value)
    valid = {int(item) for item in valid_ids} if valid_ids is not None else None
    result: list[int] = []
    for raw in raw_values:
        try:
            product = int(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if product <= 0 or product in result:
            continue
        if valid is not None and product not in valid:
            continue
        result.append(product)
        if len(result) == 3:
            break
    return result


def build_share_url(base_url: str, query: Mapping[str, str]) -> str:
    parsed = urlparse(str(base_url or ""))
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc or "localhost:8501"
    path = parsed.path or "/"
    return urlunparse(
        (scheme, netloc, path, "", urlencode(dict(query)), "")
    )


def _signature(params: Mapping[str, str]) -> str:
    return "&".join(f"{key}={params.get(key, '')}" for key in _MANAGED_KEYS)


def _current_base_url() -> str:
    try:
        url = str(st.context.url or "")
    except Exception:
        url = ""
    return url or "http://localhost:8501/"


def share_url(
    page: str,
    product_id: int | None = None,
    compare_ids: Iterable[int] | None = None,
) -> str:
    return build_share_url(
        _current_base_url(),
        build_query(page=page, product_id=product_id, compare_ids=compare_ids),
    )


def apply_deep_link(snapshots: list[dict[str, Any]]) -> None:
    """Apply URL state once for each distinct set of managed parameters."""

    params = st.query_params.to_dict()
    signature = _signature(params)
    if st.session_state.get("_deep_link_signature") == signature:
        return
    st.session_state["_deep_link_signature"] = signature

    valid_ids = {int(item["id"]) for item in snapshots}
    page = page_from_slug(str(params.get("page") or ""))
    product_id = None
    try:
        candidate = int(str(params.get("product") or ""))
    except (TypeError, ValueError):
        candidate = 0
    if candidate in valid_ids:
        product_id = candidate
    compare_ids = parse_compare(params.get("compare"), valid_ids)

    if page:
        st.session_state["pending_nav_page"] = page
    if product_id is not None:
        st.session_state["selected_product_id"] = product_id
        st.session_state["view"] = "detail"
        st.session_state["pending_nav_page"] = "Products"
    elif compare_ids:
        st.session_state["compare_selection"] = compare_ids
        st.session_state["pending_nav_page"] = "Compare"


def sync_deep_link(page: str, snapshots: list[dict[str, Any]]) -> None:
    """Keep the address bar in step with the current in-app state."""

    valid_ids = {int(item["id"]) for item in snapshots}
    params = build_query(page=page)
    selected_id = st.session_state.get("selected_product_id")
    if (
        page == "Products"
        and st.session_state.get("view") == "detail"
        and selected_id is not None
        and int(selected_id) in valid_ids
    ):
        params["product"] = str(int(selected_id))
    if page == "Compare":
        compare_ids = parse_compare(
            st.session_state.get("compare_selection"), valid_ids
        )
        if compare_ids:
            params["compare"] = ",".join(str(item) for item in compare_ids)

    current = {
        key: value
        for key, value in st.query_params.to_dict().items()
        if key in _MANAGED_KEYS
    }
    if current == params:
        return
    st.session_state["_deep_link_signature"] = _signature(params)
    st.query_params.from_dict(params)
