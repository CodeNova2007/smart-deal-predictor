"""Feature-focused pages for shopping intelligence and live quote tracking."""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

import altair as alt
import pandas as pd
import streamlit as st

from ..alerts import alert_kind_group, alert_kind_label, alert_kind_tone
from ..analytics import (
    format_inr,
    snapshot_sort_key,
    summarise_purchases,
)
from ..config import Settings
from ..database import Database
from ..live import LiveService, ScrapeError
from .components import (
    compact_html,
    e,
    empty_state,
    forecast_panel_html,
    hero,
    live_sources_html,
    offers_table_html,
    product_card_html,
    product_detail_header,
    provenance_pill,
    render_price_chart,
    score_breakdown_html,
    score_tone,
    section_title,
    short_timestamp,
    watchlist_panel_html,
)
from .copilot import open_copilot
from .deep_links import share_url


NAV_OPTIONS = [
    "Dashboard",
    "Deals",
    "Products",
    "Compare",
    "Live quotes",
    "Watchlist",
    "Alerts",
    "Purchases",
    "Insights",
    "How it works",
]
NAV_LABELS = {
    "Dashboard": "◈  Dashboard",
    "Deals": "◆  Deal finder",
    "Products": "▦  Products",
    "Compare": "⇄  Compare",
    "Live quotes": "◉  Live quotes",
    "Watchlist": "◎  Watchlist",
    "Alerts": "◉  Alerts",
    "Purchases": "▣  Purchases",
    "Insights": "◇  Insights",
    "How it works": "✦  How it works",
}

BUDGET_BANDS = {
    "Any budget": (0.0, float("inf")),
    "Under ₹5,000": (0.0, 5_000.0),
    "₹5,000 – ₹15,000": (5_000.0, 15_000.0),
    "₹15,000 – ₹30,000": (15_000.0, 30_000.0),
    "₹30,000 – ₹60,000": (30_000.0, 60_000.0),
    "Above ₹60,000": (60_000.0, float("inf")),
}

LIVE_CATEGORIES = [
    "Auto-detect",
    "Audio",
    "Wearables",
    "Laptops",
    "Desktops",
    "Monitors",
    "Tablets",
    "Smartphones",
    "Cameras",
    "Gaming",
    "Kitchen",
    "Home",
    "Fitness",
    "Accessories",
    "Other",
]


def _flash(message: str, warnings: Iterable[str] = ()) -> None:
    st.session_state["flash_message"] = message
    st.session_state["flash_warnings"] = list(warnings)


def show_flash() -> None:
    message = st.session_state.pop("flash_message", None)
    warnings = st.session_state.pop("flash_warnings", [])
    if message:
        st.success(message, icon="✅")
    for warning in warnings:
        st.warning(warning, icon="⚠️")


def _go_to_page(page: str) -> None:
    st.session_state.pending_nav_page = page
    st.rerun()


def _open_product(product_id: int) -> None:
    st.session_state.selected_product_id = int(product_id)
    st.session_state.view = "detail"
    st.session_state.pending_nav_page = "Products"
    st.rerun()


def _live_count(snapshots: list[dict[str, Any]]) -> int:
    return sum(1 for item in snapshots if item.get("is_live"))


def _average(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _provenance_text(snapshot: dict[str, Any]) -> str:
    if snapshot.get("is_live"):
        live = snapshot.get("live") or {}
        return f"Live quote · {live.get('status_label', 'recorded')}"
    return "Demo catalog"


def _status_pill(snapshot: dict[str, Any]) -> str:
    return provenance_pill(snapshot)


def _render_alert_center(db: Database) -> None:
    counts = db.get_alert_counts()
    alerts = db.get_alerts(limit=3)
    if not alerts:
        st.markdown(
            """
            <div class="sd-panel" style="border-color:rgba(52,211,153,.22);background:rgba(52,211,153,.05)">
              <span class="sd-pill green">All clear</span>
              <span class="sd-muted" style="font-size:.8rem;margin-left:.45rem">
                No saved alerts yet. Target levels, price drops, stock changes,
                and quote checks will appear here.
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    items: list[str] = []
    for alert in alerts:
        label = alert_kind_label(str(alert.get("kind") or ""))
        tone = alert_kind_tone(str(alert.get("kind") or ""))
        product = str(alert.get("product_name") or "Catalog")
        unread = "" if alert.get("read_at") else (
            ' <span class="sd-pill blue" style="font-size:.55rem">New</span>'
        )
        items.append(
            compact_html(
                f"""
            <div style="margin-bottom:.5rem">
              <span class="sd-pill {e(tone)}">{e(label)}</span>{unread}
              <strong style="font-size:.8rem;margin-left:.35rem">{e(alert.get('title') or '')}</strong>
              <span class="sd-muted" style="font-size:.72rem;margin-left:.3rem">{e(product)}</span>
            </div>
            """
            )
        )
    st.markdown(
        compact_html(
            f'<div class="sd-panel"><div class="sd-panel-title">Alert inbox</div>{"".join(items)}</div>'
        ),
        unsafe_allow_html=True,
    )
    if counts["unread"]:
        if st.button(
            f"Open alert inbox · {counts['unread']} unread",
            key="dashboard_open_alerts",
            width="stretch",
        ):
            _go_to_page("Alerts")


def _render_live_health(snapshots: list[dict[str, Any]]) -> None:
    live = [item for item in snapshots if item.get("is_live")]
    if not live:
        return
    rows = []
    for item in live:
        meta = item.get("live") or {}
        rows.append(
            compact_html(
                f"""
            <tr>
              <td><strong>{e(item['name'])}</strong></td>
              <td>{e(format_inr(item['current_price']))}</td>
              <td><span class="sd-pill {e(meta.get('status_tone') or 'amber')}">{e(meta.get('status_label') or 'Unknown')}</span></td>
              <td>{int(meta.get('source_count') or 0)}</td>
              <td>{e(short_timestamp(meta.get('last_checked_at')))}</td>
            </tr>
            """
            )
        )
    st.markdown(
        compact_html(
            f"""
        <div class="sd-panel">
          <div class="sd-panel-title">Live quote health</div>
          <div class="sd-muted sd-small" style="margin-bottom:.45rem">
            A failed check keeps the last successful price and labels it stale. It never creates a new price.
          </div>
          <div style="overflow-x:auto">
            <table class="offer-table">
              <thead><tr><th>Product</th><th>Last quote</th><th>Status</th><th>Sources</th><th>Last checked</th></tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
          </div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def render_sidebar(
    db: Database,
    settings: Settings,
    product_count: int,
    live_count: int = 0,
) -> str:
    st.sidebar.markdown(
        """
        <div class="sd-brand">
          <div class="sd-brand-mark">✦</div>
          <div>
            <div class="sd-brand-name">Smart Deal<br>Predictor</div>
            <div class="sd-brand-sub">Shopping intelligence</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pending_page = st.session_state.pop("pending_nav_page", None)
    if pending_page in NAV_OPTIONS:
        st.session_state.nav_page = pending_page

    unread_alerts = db.count_unread_alerts()

    def _nav_label(option: str) -> str:
        label = NAV_LABELS.get(option, option)
        if option == "Alerts" and unread_alerts:
            return f"{label}  ·  {unread_alerts}"
        return label

    page = st.sidebar.radio(
        "Navigation",
        NAV_OPTIONS,
        format_func=_nav_label,
        label_visibility="collapsed",
        key="nav_page",
    )

    if st.sidebar.button(
        "✦  Ask the copilot", key="sidebar_copilot", width="stretch"
    ):
        open_copilot()

    st.sidebar.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)

    if settings.ai_configured:
        status_html = (
            '<div class="sd-sidebar-status">'
            '<span class="sd-status-dot"></span><strong style="color:#A7F3D0">Smart explanations on</strong><br>'
            "<span style='font-size:.66rem'>Answers are written for this app</span>"
            "<br><span style='font-size:.65rem;color:#6F7898'>Grounded in your tracked products</span>"
            "</div>"
        )
    else:
        status_html = (
            '<div class="sd-sidebar-status">'
            '<span class="sd-status-dot local"></span><strong style="color:#FDE68A">Guided analysis on</strong><br>'
            "<span style='font-size:.66rem'>Built-in answers, no external service</span>"
            "<br><span style='font-size:.65rem;color:#6F7898'>Every answer still uses your data</span>"
            "</div>"
        )
    st.sidebar.markdown(status_html, unsafe_allow_html=True)

    demo_count = max(0, product_count - live_count)
    if live_count:
        data_line = (
            f"{product_count} products · {live_count} live · {demo_count} demo"
        )
        data_pill = '<span class="sd-pill green">Live quotes + demo catalog</span>'
    else:
        data_line = f"{product_count} products with synthetic recorded history."
        data_pill = '<span class="sd-pill amber">Demo catalog</span>'
    st.sidebar.markdown(
        f"""
        <div style="margin-top:1rem;padding:0 .15rem">
          {data_pill}
          <div class="sd-muted" style="font-size:.66rem;line-height:1.55;margin-top:.65rem">
            {e(data_line)}
            <br><br>Live quotes are the last successful reading of a product page.
            Demo rows are sample data and stay clearly labelled.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return page


def render_dashboard(
    db: Database,
    snapshots: list[dict[str, Any]],
    settings: Settings,
) -> None:
    if not snapshots:
        empty_state(
            "🛍️",
            "No products are available yet",
            "Add a live product page or restart the app to load the demo catalog.",
        )
        return

    hero(
        "Shopping intelligence",
        "Track the drop. <span class='gradient-text'>Buy at the right time.</span>",
        "One view for deal strength, live marketplace quotes, recorded price paths, "
        "seller offers, watch targets, and short-term estimates. Live and demo data "
        "are always labelled separately.",
    )

    watched = [item for item in snapshots if item.get("watchlist")]
    live_products = [item for item in snapshots if item.get("is_live")]
    priced = [item for item in snapshots if item.get("has_list_price")]
    best = max(snapshots, key=lambda item: item["deal"]["score"])
    average_discount = _average(
        item["savings"]["vs_list_pct"] for item in priced
    )

    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric(
            "Products tracked",
            str(len(snapshots)),
            f"{len(live_products)} live · {len(snapshots) - len(live_products)} demo",
        )
    with metric_columns[1]:
        st.metric("Best deal score", f"{best['deal']['score']}/100", best["deal"]["label"])
    with metric_columns[2]:
        st.metric("Average discount", f"{average_discount:.1f}%", "vs detected MRP")
    with metric_columns[3]:
        alert_counts = db.get_alert_counts()
        st.metric(
            "Unread alerts",
            str(alert_counts["unread"]),
            f"{len(watched)} active targets",
        )

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    _render_alert_center(db)

    purchase_summary = summarise_purchases(snapshots)
    if purchase_summary["count"]:
        difference = purchase_summary["difference"]
        difference_text = (
            f"{format_inr(abs(difference))} less than the latest quotes"
            if difference < 0
            else f"{format_inr(difference)} more than the latest quotes"
        )
        st.markdown(
            compact_html(
                f"""
            <div class="sd-panel" style="margin-top:.65rem">
              <div class="sd-panel-title">Purchase tracker</div>
              <div class="sd-muted" style="font-size:.78rem;line-height:1.6">
                You recorded <strong>{purchase_summary['count']}</strong> purchase(s)
                totalling <strong>{e(format_inr(purchase_summary['total_paid']))}</strong>.
                The latest recorded quotes for those products total
                <strong>{e(format_inr(purchase_summary['current_value']))}</strong>,
                which is {e(difference_text)}. Purchase records are what you paid,
                not marketplace quotes.
              </div>
            </div>
            """
            ),
            unsafe_allow_html=True,
        )
        if st.button(
            "Open purchase tracker",
            key="dashboard_open_purchases",
            width="stretch",
        ):
            _go_to_page("Purchases")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.18, 1], gap="large")
    with left:
        list_price_html = (
            f'<span class="sd-muted" style="text-decoration:line-through;font-size:.8rem">'
            f'{e(format_inr(best["list_price"]))}</span>'
            if best.get("has_list_price")
            else '<span class="sd-muted" style="font-size:.74rem">MRP not detected</span>'
        )
        savings_html = (
            f'<span class="sd-pill green">Save {e(format_inr(best["savings"]["vs_list_price"]))}</span>'
            if best.get("has_list_price")
            else '<span class="sd-pill amber">No MRP-based discount</span>'
        )
        st.markdown(
            f"""
            <div class="sd-panel" style="padding:1.2rem 1.25rem">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:.5rem">
                <div>
                  <div class="sd-eyebrow">Featured deal</div>
                  <div style="font-size:2rem;line-height:1;margin-bottom:.55rem">{e(best['emoji'])}</div>
                  <div style="font-family:'Space Grotesk';font-size:1.35rem;font-weight:700;letter-spacing:-.03em">{e(best['name'])}</div>
                  <div class="sd-muted" style="font-size:.77rem;margin:.3rem 0 .7rem">{e(best['category'])} · {e(best['stats'].get('trend_direction', 'stable'))} trend</div>
                </div>
                {_status_pill(best)}
              </div>
              <div style="display:flex;align-items:baseline;gap:.6rem">
                <span class="sd-detail-price" style="font-size:2.1rem">{e(format_inr(best['current_price']))}</span>
                {list_price_html}
              </div>
              <div style="margin:.75rem 0 .85rem;display:flex;gap:.4rem;flex-wrap:wrap">
                <span class="sd-pill {score_tone(best['deal']['score'])}">{best['deal']['score']}/100 · {e(best['deal']['label'])}</span>
                {savings_html}
                <span class="sd-pill blue">{best['stats'].get('observations', 0)} observations</span>
              </div>
              <div class="sd-muted" style="font-size:.79rem;line-height:1.55">{e(best['deal']['summary'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        button_columns = st.columns(2)
        with button_columns[0]:
            if st.button(
                "View full analysis",
                key="featured_open",
                width="stretch",
                type="primary",
            ):
                _open_product(best["id"])
        with button_columns[1]:
            if st.button("Ask about this deal", key="featured_ask", width="stretch"):
                st.session_state.selected_product_id = best["id"]
                open_copilot("Is this a good deal?")

    with right:
        section_title(
            "Recorded price path",
            "Violet line = recorded observations · dashed blue = 7-day estimate",
        )
        with st.container(border=True):
            render_price_chart(best, height=245, compact=False)

    st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
    section_title(
        "Market pulse",
        "Average deal strength across the catalog categories",
    )
    category_rows = _category_summary(snapshots)
    category_columns = st.columns(min(4, max(1, len(category_rows))))
    for index, row in enumerate(category_rows[:4]):
        with category_columns[index]:
            st.markdown(
                f"""
                <div class="sd-panel" style="min-height:112px">
                  <div class="sd-panel-title" style="margin-bottom:.2rem">{e(row['category'])}</div>
                  <div class="sd-detail-price" style="font-size:1.35rem">{row['average_score']:.0f}/100</div>
                  <div class="sd-muted" style="font-size:.7rem;line-height:1.5">
                    {row['count']} products · {row['average_discount']:.1f}% average discount<br>
                    Best: {e(row['best_name'])}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    section_title(
        "Price drop radar",
        "Products currently below their own recorded average, not a prediction",
    )
    drops = sorted(
        snapshots,
        key=lambda item: (-item["savings"]["vs_average_pct"], item["name"]),
    )[:3]
    drop_columns = st.columns(3)
    for index, snapshot in enumerate(drops):
        with drop_columns[index]:
            with st.container(border=True):
                st.markdown(product_card_html(snapshot), unsafe_allow_html=True)
                if st.button(
                    "View deal →",
                    key=f"radar_view_{snapshot['id']}",
                    width="stretch",
                ):
                    _open_product(snapshot["id"])

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    top = sorted(snapshots, key=lambda item: -item["deal"]["score"])[:3]
    section_title(
        "Today's strongest deals",
        "Ranked by the app's deal score, not by discount alone",
    )
    columns = st.columns(3)
    for index, snapshot in enumerate(top):
        with columns[index]:
            with st.container(border=True):
                st.markdown(product_card_html(snapshot), unsafe_allow_html=True)
                if st.button(
                    "View analysis →",
                    key=f"dashboard_view_{snapshot['id']}",
                    width="stretch",
                ):
                    _open_product(snapshot["id"])

    if live_products:
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        _render_live_health(snapshots)
    else:
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="sd-panel" style="border-color:rgba(139,92,246,.20)">
              <div class="sd-panel-title">Bring in a real product page</div>
              <div class="sd-muted" style="font-size:.8rem;line-height:1.6">
                Open <strong>Live quotes</strong> and paste one product-detail URL from
                Amazon.in or Flipkart. The app records the listed price, retailer, and
                availability that the page shows. It does not invent missing details.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Open live quotes", key="dashboard_live_cta", type="primary"):
            _go_to_page("Live quotes")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.expander("How is the deal score calculated?"):
        st.markdown(
            """
            The score blends four signals into **0–100**:

            - **40% price position** — where the current price sits between its recorded low and high
            - **25% discount** — the saving against the product's detected MRP
            - **20% recent trend** — whether the latest 30 observations are falling, flat, or rising
            - **15% best seller offer** — the effective total after recorded coupons and delivery

            It is a comparison tool for this product's own history. It is not a
            prediction and not financial advice. A product with no detected MRP gets
            no discount credit rather than an invented saving.
            """
        )


def _category_summary(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in snapshots:
        groups.setdefault(item["category"], []).append(item)
    rows = []
    for category, items in groups.items():
        best = max(items, key=lambda item: item["deal"]["score"])
        priced = [item for item in items if item.get("has_list_price")]
        rows.append(
            {
                "category": category,
                "count": len(items),
                "average_score": _average(item["deal"]["score"] for item in items),
                "average_discount": _average(
                    item["savings"]["vs_list_pct"] for item in priced
                ),
                "best_name": best["name"],
                "best_score": best["deal"]["score"],
            }
        )
    rows.sort(key=lambda row: (-row["average_score"], row["category"]))
    return rows


def _filter_by_budget(
    snapshots: list[dict[str, Any]], budget: str
) -> list[dict[str, Any]]:
    low, high = BUDGET_BANDS.get(budget, (0.0, float("inf")))
    return [item for item in snapshots if low <= item["current_price"] < high]


def render_deals(db: Database, snapshots: list[dict[str, Any]]) -> None:
    hero(
        "Deal finder",
        "Find the strongest deal. <span class='gradient-text'>Not just the biggest number.</span>",
        "Filter by budget, category, deal strength, and data source. Every result "
        "keeps its recorded history and its live-or-demo label.",
    )

    categories = sorted({item["category"] for item in snapshots})
    filter_columns = st.columns([1.05, 1.0, 0.95, 1.0])
    with filter_columns[0]:
        budget = st.selectbox("Budget", list(BUDGET_BANDS), key="deals_budget")
    with filter_columns[1]:
        category = st.selectbox(
            "Category", ["All categories", *categories], key="deals_category"
        )
    with filter_columns[2]:
        origin = st.selectbox(
            "Data source",
            ["All products", "Live quotes", "Demo catalog"],
            key="deals_origin",
        )
    with filter_columns[3]:
        sort_by = st.selectbox(
            "Sort by",
            [
                "Deal score",
                "Biggest discount",
                "Biggest saving",
                "Lowest price",
                "Price trend",
            ],
            key="deals_sort",
        )

    score_floor = st.slider(
        "Minimum deal score",
        min_value=0,
        max_value=100,
        value=0,
        step=5,
        key="deals_score_floor",
    )
    below_average = st.checkbox(
        "Only products below their recorded average",
        key="deals_below_average",
    )

    filtered = []
    for snapshot in snapshots:
        if snapshot["deal"]["score"] < score_floor:
            continue
        if category != "All categories" and snapshot["category"] != category:
            continue
        if origin == "Live quotes" and not snapshot.get("is_live"):
            continue
        if origin == "Demo catalog" and snapshot.get("is_live"):
            continue
        if below_average and snapshot["savings"]["vs_average_pct"] <= 0:
            continue
        filtered.append(snapshot)
    filtered = _filter_by_budget(filtered, budget)
    filtered.sort(key=lambda item: snapshot_sort_key(item, sort_by))

    priced = [item for item in filtered if item.get("has_list_price")]
    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("Matching products", str(len(filtered)), budget)
    with metric_columns[1]:
        st.metric(
            "Best score",
            f"{max((item['deal']['score'] for item in filtered), default=0)}/100",
            "within this filter",
        )
    with metric_columns[2]:
        st.metric(
            "Average discount",
            f"{_average(item['savings']['vs_list_pct'] for item in priced):.1f}%",
            "of detected MRP",
        )
    with metric_columns[3]:
        st.metric(
            "Potential saving",
            format_inr(sum(item["savings"]["vs_list_price"] for item in priced)),
            "vs detected MRP",
        )

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)
    if not filtered:
        empty_state(
            "🎯",
            "No deals match those filters",
            "Raise the budget, lower the minimum score, or switch the data source.",
        )
        return

    top = filtered[0]
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        with st.container(border=True):
            st.markdown(product_card_html(top), unsafe_allow_html=True)
            st.markdown(
                f'<div class="sd-muted" style="font-size:.76rem;line-height:1.55;margin-top:.45rem">'
                f"**Why it ranks first:** {e(top['deal']['summary'])}</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "View full analysis",
                key="deals_top_open",
                width="stretch",
                type="primary",
            ):
                _open_product(top["id"])
    with right:
        st.markdown(
            f"""
            <div class="sd-panel">
              <div class="sd-panel-title">Deal snapshot</div>
              <div class="sd-kpi-row" style="margin-top:.4rem">
                <div class="sd-kpi"><div class="sd-kpi-label">Current</div><div class="sd-kpi-value">{e(format_inr(top['current_price']))}</div></div>
                <div class="sd-kpi"><div class="sd-kpi-label">Recorded low</div><div class="sd-kpi-value">{e(format_inr(top['stats'].get('minimum_price')))}</div></div>
                <div class="sd-kpi"><div class="sd-kpi-label">7-day estimate</div><div class="sd-kpi-value">{e(format_inr(top['forecast'].get('predicted_price_7d')) if top['forecast'].get('available') else '—')}</div></div>
              </div>
              <div class="sd-small sd-muted" style="margin-top:.55rem;line-height:1.55">
                {e(top['forecast'].get('disclaimer') if top['forecast'].get('available') else 'A forecast needs at least seven recorded observations.')}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(
            "✦ Ask about this deal",
            key="deals_top_ask",
            width="stretch",
        ):
            st.session_state.selected_product_id = top["id"]
            open_copilot("Is this a good deal?")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    section_title(
        f"{len(filtered)} matching products",
        "Open any product to see its history, offer comparison, and watch level",
    )
    _product_grid(filtered, "deals")

    with st.expander("How to read a deal score"):
        st.markdown(
            """
            A high score means the current price looks strong **against that
            product's own recorded range** and detected MRP. It does not mean the
            product is better than another product, and it does not promise that the
            price will stay low. Compare features, seller reliability, and return
            terms before buying.
            """
        )


def _product_grid(
    snapshots: list[dict[str, Any]],
    key_prefix: str,
    columns: int = 3,
) -> None:
    grid = st.columns(columns)
    for index, snapshot in enumerate(snapshots):
        with grid[index % columns]:
            with st.container(border=True):
                st.markdown(product_card_html(snapshot), unsafe_allow_html=True)
                if st.button(
                    "View analysis →",
                    key=f"{key_prefix}_view_{snapshot['id']}",
                    width="stretch",
                ):
                    _open_product(snapshot["id"])


def _target_form(
    db: Database, snapshot: dict[str, Any], settings: Settings
) -> None:
    existing = snapshot.get("watchlist")
    suggested = snapshot.get("suggested_target") or {}
    default_target = int(
        (existing or {}).get("target_price")
        or suggested.get("target_price")
        or snapshot["current_price"] * 0.95
    )
    live = snapshot.get("live") or {}
    help_text = (
        "You will be alerted in the Watchlist page when the latest recorded price "
        "is at or below this level."
    )
    if snapshot.get("is_live"):
        help_text += (
            " This product uses a live quote; a stale quote is labelled before you rely on it."
        )
    with st.form(f"target_form_{snapshot['id']}", clear_on_submit=False, border=False):
        target = st.number_input(
            "Target price (₹)",
            min_value=1,
            max_value=100_000_000,
            value=max(1, default_target),
            step=100,
            format="%d",
            help=help_text,
        )
        submitted = st.form_submit_button(
            "Update target" if existing else "Set target",
            type="primary",
            width="stretch",
        )
    if submitted:
        try:
            db.upsert_watchlist(int(snapshot["id"]), float(target))
        except ValueError as exc:
            st.error(str(exc))
        else:
            _flash(
                f"Target price for {snapshot['name']} saved at {format_inr(target)}."
            )
            st.rerun()

    if existing:
        if st.button(
            "Remove target",
            key=f"remove_target_{snapshot['id']}",
            width="stretch",
        ):
            db.remove_watchlist(int(snapshot["id"]))
            _flash(f"Removed the target price for {snapshot['name']}.")
            st.rerun()

    if snapshot.get("is_live") and live.get("status") == "stale":
        st.caption(
            "This target is compared with the last successful live quote, which is stale."
        )


def _purchase_form(db: Database, snapshot: dict[str, Any]) -> None:
    purchase = snapshot.get("purchase")
    product_id = int(snapshot["id"])
    if purchase:
        difference = float(purchase["difference_vs_current"])
        if purchase.get("below_current"):
            difference_text = (
                f"{format_inr(abs(difference))} below the latest recorded price"
            )
        elif purchase.get("at_current"):
            difference_text = "the same as the latest recorded price"
        else:
            difference_text = (
                f"{format_inr(difference)} above the latest recorded price"
            )
        retailer = purchase.get("retailer") or "Retailer not recorded"
        notes = purchase.get("notes") or ""
        notes_html = (
            f'<div class="sd-muted" style="font-size:.74rem;margin-top:.35rem">{e(notes)}</div>'
            if notes
            else ""
        )
        st.markdown(
            compact_html(
                f"""
            <div class="sd-panel">
              <div class="sd-panel-title">Your purchase</div>
              <div style="font-size:.86rem;line-height:1.6">
                You paid <strong>{e(format_inr(purchase['price_paid']))}</strong>
                on {e(purchase.get('purchased_on') or 'an unrecorded date')}
                · {e(retailer)}.
              </div>
              <div class="sd-muted" style="font-size:.75rem;line-height:1.55;margin-top:.25rem">
                Latest recorded price: {e(format_inr(purchase['current_price']))}.
                Your purchase is {e(difference_text)}.
              </div>
              {notes_html}
              <div class="sd-small sd-muted" style="margin-top:.45rem">
                This is your own purchase record, not a marketplace quote or a
                resale valuation.
              </div>
            </div>
            """
            ),
            unsafe_allow_html=True,
        )

    default_date = date.today()
    if purchase:
        try:
            parsed_date = date.fromisoformat(
                str(purchase.get("purchased_on") or "")[:10]
            )
            default_date = min(parsed_date, date.today())
        except ValueError:
            default_date = date.today()

    with st.expander(
        "Edit your purchase record" if purchase else "Record what you paid",
        expanded=False,
    ):
        st.caption(
            "Save the amount you actually paid. The app compares it with the "
            "latest recorded price but does not treat it as a market quote."
        )
        with st.form(f"purchase_form_{product_id}", border=False):
            price_paid = st.number_input(
                "Price paid (₹)",
                min_value=1.0,
                max_value=100_000_000.0,
                value=float(
                    purchase["price_paid"]
                    if purchase
                    else snapshot["current_price"]
                ),
                step=100.0,
                format="%.0f",
            )
            purchased_on = st.date_input(
                "Purchase date",
                value=default_date,
                max_value=date.today(),
            )
            retailer = st.text_input(
                "Retailer (optional)",
                value=str(purchase.get("retailer") or "") if purchase else "",
                max_chars=120,
            )
            notes = st.text_area(
                "Notes (optional)",
                value=str(purchase.get("notes") or "") if purchase else "",
                max_chars=500,
                height=80,
            )
            submitted = st.form_submit_button(
                "Update purchase" if purchase else "Save purchase",
                type="primary",
                width="stretch",
            )
        if submitted:
            try:
                db.upsert_purchase(
                    product_id,
                    float(price_paid),
                    purchased_on=purchased_on,
                    retailer=retailer,
                    notes=notes,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                _flash(f"Saved your purchase record for {snapshot['name']}.")
                st.rerun()
        if purchase and st.button(
            "Remove purchase record",
            key=f"remove_purchase_{product_id}",
            width="stretch",
        ):
            db.remove_purchase(product_id)
            _flash(f"Removed your purchase record for {snapshot['name']}.")
            st.rerun()


def _refresh_live_product(db: Database, settings: Settings, snapshot: dict[str, Any]) -> None:
    service = LiveService(db, settings)
    with st.spinner("Checking the product page…"):
        try:
            result = service.refresh_product(int(snapshot["id"]))
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception:
            st.error(
                "The live check could not be completed. The last successful quote "
                "was kept and no new price was recorded."
            )
            return
    warnings = []
    if not result.get("ok"):
        warnings = result.get("errors") or [
            "The page could not be refreshed. The last successful quote was kept."
        ]
    _flash(
        f"Checked {snapshot['name']}: {result.get('status', 'updated').replace('_', ' ')}.",
        warnings,
    )
    st.rerun()


def render_product_detail(
    db: Database,
    snapshot: dict[str, Any],
    settings: Settings,
) -> None:
    if st.button("← Back to all products", key="back_to_products"):
        st.session_state.view = "catalog"
        st.rerun()

    product_detail_header(snapshot)

    if snapshot.get("is_live"):
        action_columns = st.columns([1.0, 1.0, 1.25])
        with action_columns[0]:
            if st.button(
                "↻ Refresh live quote",
                key="detail_refresh_live",
                width="stretch",
                type="primary",
            ):
                _refresh_live_product(db, settings, snapshot)
        with action_columns[1]:
            if st.button(
                "Manage sources",
                key="detail_manage_sources",
                width="stretch",
            ):
                _go_to_page("Live quotes")
        with action_columns[2]:
            live = snapshot.get("live") or {}
            st.markdown(
                f'<div class="sd-small sd-muted" style="padding-top:.55rem">'
                f"Last checked {e(short_timestamp(live.get('last_checked_at')))} · "
                f"{e(live.get('status_label') or 'Live quote')}</div>",
                unsafe_allow_html=True,
            )

    ask_columns = st.columns(2)
    with ask_columns[0]:
        if st.button(
            "✦  Is this a good deal?",
            key="detail_ask_deal",
            width="stretch",
            type="primary",
        ):
            open_copilot("Is this a good deal?")
    with ask_columns[1]:
        if st.button(
            "✦  Should I buy now or wait?",
            key="detail_ask_timing",
            width="stretch",
        ):
            open_copilot("Should I buy now or wait?")

    section_title(
        "Recorded history and estimate",
        "Violet line = recorded observations · dashed blue = 7-day estimate",
    )
    with st.container(border=True):
        render_price_chart(snapshot, height=330)

    left, right = st.columns([1.12, 1], gap="large")
    with left:
        st.markdown(score_breakdown_html(snapshot), unsafe_allow_html=True)
    with right:
        st.markdown(forecast_panel_html(snapshot), unsafe_allow_html=True)

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    offers_column, watch_column = st.columns([1.4, 1], gap="large")
    with offers_column:
        st.markdown(offers_table_html(snapshot), unsafe_allow_html=True)
        if snapshot.get("is_live"):
            st.markdown(
                live_sources_html(snapshot),
                unsafe_allow_html=True,
            )
    with watch_column:
        st.markdown(watchlist_panel_html(snapshot), unsafe_allow_html=True)
        _target_form(db, snapshot, settings)
        st.markdown(
            "<div style='height:.7rem'></div>", unsafe_allow_html=True
        )
        _purchase_form(db, snapshot)

    with st.expander("Share this product analysis"):
        st.caption(
            "This link opens the same product analysis in a new browser session."
        )
        st.code(
            share_url("Products", product_id=int(snapshot["id"])),
            language=None,
        )

    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    with st.expander("View all recorded price observations"):
        history = pd.DataFrame(snapshot.get("history") or [])
        if history.empty:
            st.info("No price observations are recorded yet.")
        else:
            history = history.rename(
                columns={
                    "observed_on": "Date",
                    "price": "Price (₹)",
                    "source": "Source",
                }
            )
            st.dataframe(
                history.sort_values("Date", ascending=False),
                hide_index=True,
                width="stretch",
                column_config={
                    "Price (₹)": st.column_config.NumberColumn(format="₹%d"),
                },
            )
    if snapshot.get("is_live"):
        st.caption(
            "Live history starts with the first successful import or refresh. It is "
            "not backfilled from the marketplace. A failed check keeps the last "
            "successful quote and labels it stale. Forecasts are estimates, not promises."
        )
    else:
        st.caption(
            "These are synthetic demo observations. The forecast is a regression "
            "estimate, not a guarantee."
        )


def render_products(
    db: Database,
    snapshots: list[dict[str, Any]],
    settings: Settings,
) -> None:
    selected_id = st.session_state.get("selected_product_id")
    if st.session_state.get("view") == "detail" and selected_id is not None:
        snapshot = next(
            (item for item in snapshots if item["id"] == int(selected_id)), None
        )
        if snapshot:
            render_product_detail(db, snapshot, settings)
            return
        st.session_state.selected_product_id = None
        st.session_state.view = "catalog"

    hero(
        "Product catalog",
        "Search the catalog. <span class='gradient-text'>Read the deal, not just the discount.</span>",
        "Every product has recorded history, a deal score, seller or marketplace "
        "offers, and a 7-day estimate. Live quotes and demo rows stay clearly labelled.",
    )

    categories = sorted({item["category"] for item in snapshots})
    filter_columns = st.columns([1.8, 0.9, 0.95, 1.0])
    with filter_columns[0]:
        search = st.text_input(
            "Search products",
            placeholder="Search by name, brand, or category…",
            key="catalog_search",
        )
    with filter_columns[1]:
        category = st.selectbox(
            "Category", ["All categories", *categories], key="catalog_category"
        )
    with filter_columns[2]:
        origin = st.selectbox(
            "Data source",
            ["All products", "Live quotes", "Demo catalog"],
            key="catalog_origin",
        )
    with filter_columns[3]:
        sort_by = st.selectbox(
            "Sort by",
            [
                "Deal score",
                "Lowest price",
                "Biggest discount",
                "Biggest saving",
                "Price trend",
            ],
            key="catalog_sort",
        )

    needle = search.strip().lower()
    filtered = []
    for snapshot in snapshots:
        haystack = f"{snapshot['name']} {snapshot['brand']} {snapshot['category']}".lower()
        if needle and needle not in haystack:
            continue
        if category != "All categories" and snapshot["category"] != category:
            continue
        if origin == "Live quotes" and not snapshot.get("is_live"):
            continue
        if origin == "Demo catalog" and snapshot.get("is_live"):
            continue
        filtered.append(snapshot)
    filtered.sort(key=lambda item: snapshot_sort_key(item, sort_by))

    st.markdown(
        f'<div class="sd-muted sd-small" style="margin:.2rem 0 .8rem">'
        f"{len(filtered)} of {len(snapshots)} products</div>",
        unsafe_allow_html=True,
    )

    if not filtered:
        empty_state(
            "🔎",
            "No products match that filter",
            "Try a broader search or choose a different category or data source.",
        )
        return

    _product_grid(filtered, "catalog")


def _compare_table(snapshots: list[dict[str, Any]]) -> str:
    header = "".join(f"<th>{e(item['name'])}</th>" for item in snapshots)
    rows = [
        ("Current price", lambda item: e(format_inr(item["current_price"]))),
        (
            "Detected MRP",
            lambda item: e(format_inr(item["list_price"]))
            if item.get("has_list_price")
            else '<span class="sd-muted">Not detected</span>',
        ),
        (
            "Discount",
            lambda item: f"{item['savings']['vs_list_pct']:.1f}%"
            if item.get("has_list_price")
            else "—",
        ),
        ("Deal score", lambda item: f"{item['deal']['score']}/100 · {e(item['deal']['label'])}"),
        (
            "Recorded low",
            lambda item: e(format_inr(item["stats"].get("minimum_price"))),
        ),
        (
            "Recorded average",
            lambda item: e(format_inr(item["stats"].get("average_price"))),
        ),
        (
            "7-day estimate",
            lambda item: e(format_inr(item["forecast"].get("predicted_price_7d")))
            if item["forecast"].get("available")
            else "Not enough history",
        ),
        (
            "Watch target",
            lambda item: e(format_inr(item["watchlist"]["target_price"]))
            if item.get("watchlist")
            else "Not set",
        ),
        (
            "Data source",
            lambda item: _status_pill(item),
        ),
    ]
    body = "".join(
        f"<tr><th>{e(label)}</th>{''.join(f'<td>{formatter(item)}</td>' for item in snapshots)}</tr>"
        for label, formatter in rows
    )
    return f"""
    <div class="sd-panel">
      <div class="sd-panel-title">Side-by-side comparison</div>
      <div style="overflow-x:auto">
        <table class="compare-table">
          <thead><tr><th>Measure</th>{header}</tr></thead>
          <tbody>{body}</tbody>
        </table>
      </div>
      <div class="sd-small sd-muted" style="margin-top:.55rem">
        Compare deal strength against each product's own history. A lower price is not
        automatically a better deal, and different products have different value.
      </div>
    </div>
    """


def _comparison_chart(snapshots: list[dict[str, Any]]) -> alt.Chart | None:
    rows = []
    for snapshot in snapshots:
        for observation in (snapshot.get("history") or [])[-90:]:
            rows.append(
                {
                    "date": pd.to_datetime(observation["observed_on"]),
                    "price": float(observation["price"]),
                    "product": snapshot["name"],
                }
            )
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    return (
        alt.Chart(frame)
        .mark_line(strokeWidth=2.2, interpolate="monotone")
        .encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%b %d", grid=False)),
            y=alt.Y(
                "price:Q",
                title="Recorded price (₹)",
                scale=alt.Scale(zero=False),
                axis=alt.Axis(gridColor="rgba(148,163,184,0.08)"),
            ),
            color=alt.Color("product:N", title=None),
            tooltip=[
                alt.Tooltip("product:N", title="Product"),
                alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
                alt.Tooltip("price:Q", title="Price", format=",.0f"),
            ],
        )
        .properties(height=320, background="transparent")
        .configure_view(strokeOpacity=0)
        .configure_axis(labelColor="#8F98B5", titleColor="#8F98B5")
        .configure_legend(labelColor="#C9D0E6", orient="top")
    )


def render_compare(db: Database, snapshots: list[dict[str, Any]]) -> None:
    hero(
        "Compare products",
        "Put two or three products side by side. <span class='gradient-text'>See the trade-offs.</span>",
        "Compare deal strength, recorded ranges, estimates, watch levels, and data "
        "source. The comparison is grounded in each product's own history.",
    )

    if not snapshots:
        empty_state("⇄", "Nothing to compare yet", "Add products first.")
        return

    by_id = {item["id"]: item for item in snapshots}
    top_ids = [
        item["id"]
        for item in sorted(snapshots, key=lambda item: -item["deal"]["score"])[:3]
    ]
    selected_ids = st.multiselect(
        "Choose up to three products",
        options=list(by_id),
        default=top_ids,
        format_func=lambda product_id: by_id[product_id]["name"],
        max_selections=3,
        key="compare_selection",
    )
    selected = [by_id[product_id] for product_id in selected_ids]

    if len(selected) < 2:
        empty_state(
            "⇄",
            "Pick at least two products",
            "Choose two or three products above to see a grounded comparison.",
        )
        return

    st.markdown(_compare_table(selected), unsafe_allow_html=True)

    with st.expander("Share this comparison"):
        st.caption(
            "This link opens the same product comparison in a new browser session."
        )
        st.code(
            share_url("Compare", compare_ids=selected_ids),
            language=None,
        )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    section_title(
        "Recorded price paths",
        "Last 90 recorded observations for each selected product",
    )
    chart = _comparison_chart(selected)
    if chart is not None:
        with st.container(border=True):
            st.altair_chart(chart, width="stretch")
    else:
        st.info("None of the selected products has recorded observations yet.")

    strongest = max(selected, key=lambda item: item["deal"]["score"])
    cheapest = min(selected, key=lambda item: item["current_price"])
    best_discount = max(
        selected,
        key=lambda item: item["savings"]["vs_list_pct"]
        if item.get("has_list_price")
        else -1,
    )
    columns = st.columns(3)
    cards = [
        ("Strongest deal score", strongest, f"{strongest['deal']['score']}/100"),
        ("Lowest current price", cheapest, format_inr(cheapest["current_price"])),
        (
            "Biggest detected discount",
            best_discount,
            f"{best_discount['savings']['vs_list_pct']:.1f}%"
            if best_discount.get("has_list_price")
            else "MRP not detected",
        ),
    ]
    for column, (label, snapshot, value) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <div class="sd-panel" style="min-height:110px">
                  <div class="sd-kpi-label">{e(label)}</div>
                  <div class="sd-detail-price" style="font-size:1.35rem">{e(value)}</div>
                  <div class="sd-muted" style="font-size:.72rem">{e(snapshot['name'])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    button_columns = st.columns(len(selected))
    for column, snapshot in zip(button_columns, selected):
        with column:
            if st.button(
                f"Open {snapshot['name'][:26]}…",
                key=f"compare_open_{snapshot['id']}",
                width="stretch",
            ):
                _open_product(snapshot["id"])


def _handle_import(
    service: LiveService,
    url: str,
    label: str,
    category: str,
) -> None:
    try:
        result = service.import_product(url, label=label, category=category)
    except ScrapeError as exc:
        st.error(exc.message)
        st.caption("No price was saved. Check the URL or try again later.")
    except ValueError as exc:
        st.error(str(exc))
    except Exception:
        st.error(
            "The quote could not be imported. The page may be unavailable or the "
            "address may not be a single product page."
        )
    else:
        _flash(result["message"], result.get("warnings") or ())
        st.rerun()


def _live_source_rows(
    db: Database,
    settings: Settings,
    snapshot: dict[str, Any],
) -> None:
    service = LiveService(db, settings)
    sources = snapshot.get("sources") or []
    if not sources:
        st.info(
            "No source URLs are attached. Add one below or remove the product and "
            "import it again."
        )
        return
    for source in sources:
        columns = st.columns([2.2, 1.0, 1.15, 1.1, 0.7])
        with columns[0]:
            label = source.get("label") or source.get("retailer") or "Marketplace"
            url = str(source.get("url") or "")
            link = (
                f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">Open source ↗</a>'
                if url.startswith(("http://", "https://"))
                else ""
            )
            st.markdown(
                f'<div style="font-size:.8rem"><strong>{e(label)}</strong></div>'
                f'<div class="sd-muted" style="font-size:.65rem">{link}</div>',
                unsafe_allow_html=True,
            )
        with columns[1]:
            st.markdown(
                f'<div class="sd-kpi-label">Last quote</div>'
                f'<div style="font-size:.85rem">{e(format_inr(source.get("last_price")) if source.get("last_price") is not None else "—")}</div>',
                unsafe_allow_html=True,
            )
        with columns[2]:
            st.markdown(
                f'<span class="sd-pill {e(source.get("status_tone") or "amber")}">'
                f'{e(source.get("status_label") or "Not checked")}</span>',
                unsafe_allow_html=True,
            )
        with columns[3]:
            st.markdown(
                f'<div class="sd-muted" style="font-size:.68rem">'
                f'{e(short_timestamp(source.get("last_checked_at")))}</div>',
                unsafe_allow_html=True,
            )
        with columns[4]:
            if st.button(
                "Remove",
                key=f"live_remove_source_{source['id']}",
                help="Remove this source and its last recorded quote",
            ):
                result = service.remove_source(int(source["id"]))
                _flash(result["message"])
                st.rerun()

    add_url = st.text_input(
        "Add another product page",
        placeholder="https://www.flipkart.com/…/p/…",
        key=f"live_add_url_{snapshot['id']}",
    )
    add_label = st.text_input(
        "Source label (optional)",
        placeholder="e.g. Flipkart listing",
        key=f"live_add_label_{snapshot['id']}",
    )
    add_columns = st.columns([1, 1])
    with add_columns[0]:
        if st.button(
            "Add source",
            key=f"live_add_source_{snapshot['id']}",
            width="stretch",
        ):
            if not add_url.strip():
                st.warning("Paste one product-page URL first.")
            else:
                try:
                    result = service.add_source(
                        int(snapshot["id"]), add_url.strip(), label=add_label.strip()
                    )
                except ScrapeError as exc:
                    st.error(exc.message)
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("That source could not be added. No quote was saved.")
                else:
                    _flash(result["message"], result.get("warnings") or ())
                    st.rerun()
    with add_columns[1]:
        if st.button(
            "↻ Refresh this product",
            key=f"live_refresh_product_{snapshot['id']}",
            width="stretch",
        ):
            _refresh_live_product(db, settings, snapshot)


def render_live_quotes(db: Database, snapshots: list[dict[str, Any]], settings: Settings) -> None:
    hero(
        "Live quote workspace",
        "Bring a product page in. <span class='gradient-text'>Keep the quote honest.</span>",
        "Paste one public product-detail URL. The app reads the listed price, "
        "retailer, seller, and availability the page shows. Missing details stay "
        "missing; nothing is guessed.",
    )

    service = LiveService(db, settings)
    import_column, guide_column = st.columns([1.3, 1], gap="large")
    with import_column:
        with st.container(border=True):
            st.markdown(
                '<div class="sd-panel-title">Add a live product</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="sd-muted" style="font-size:.76rem;line-height:1.55;margin-bottom:.7rem">'
                "Use the address-bar URL of one item, not a search, category, store, "
                "or cart page. Amazon.in links contain <strong>/dp/</strong>; Flipkart "
                "links contain <strong>/p/</strong>.</div>",
                unsafe_allow_html=True,
            )
            with st.form("live_import_form", clear_on_submit=True):
                url = st.text_input(
                    "Product page URL",
                    placeholder="https://www.amazon.in/dp/…",
                )
                label = st.text_input(
                    "Your label (optional)",
                    placeholder="e.g. Birthday gift shortlist",
                )
                category = st.selectbox("Category", LIVE_CATEGORIES)
                submitted = st.form_submit_button(
                    "Import live quote",
                    type="primary",
                    width="stretch",
                )
            if submitted:
                if not url.strip():
                    st.warning("Paste one product-page URL first.")
                else:
                    with st.spinner("Reading the product page…"):
                        _handle_import(service, url.strip(), label.strip(), category)
    with guide_column:
        st.markdown(
            """
            <div class="sd-panel">
              <div class="sd-panel-title">What this workspace does</div>
              <div class="sd-small sd-muted" style="line-height:1.7">
                <strong style="color:#DDD6FE">Records one quote per source.</strong>
                The current price is the lowest in-stock quote across the attached sources.<br><br>
                <strong style="color:#DDD6FE">Keeps the last good quote.</strong>
                If a refresh is blocked or the page changes, the last successful price
                stays visible and is marked stale.<br><br>
                <strong style="color:#DDD6FE">Does not guess.</strong>
                No coupon, delivery fee, seller, MRP, or availability is invented. Only
                INR quotes are accepted.<br><br>
                <strong style="color:#DDD6FE">Does not bypass access controls.</strong>
                CAPTCHAs, logins, and anti-bot pages are reported, never worked around.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.expander("Which links work?"):
            st.markdown(
                "- **Amazon.in** — a product page with `/dp/` or `/gp/aw/d/` in "
                "the address bar.\n"
                "- **Flipkart** — a product page with `/p/itm…`; sell-back or "
                "exchange listings are not normal product offers.\n"
                "- **Reliance Digital** — a product page with `/product/` in "
                "the address bar; its listed price and stock are readable.\n"
                "- **INR only** — the page must show ₹. Prices in other "
                "currencies are rejected, never converted.\n"
                "- **One item, not a list** — search, category, store, cart, and "
                "wishlist pages are rejected.\n"
                "- **No bot checks** — some retailers (for example Croma) return "
                "an access-denied page; the app never bypasses it.\n"
                "- **Public app limits** — Flipkart may rate-limit the cloud "
                "server. Amazon.in and Reliance Digital links are the most "
                "reliable there; the local app can read all three."
            )

    live_snapshots = [item for item in snapshots if item.get("is_live")]
    if not live_snapshots:
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        empty_state(
            "◉",
            "No live products yet",
            "Import one product page above to start a live quote. Demo products stay separate.",
        )
        return

    all_sources = [
        source
        for snapshot in live_snapshots
        for source in (snapshot.get("sources") or [])
    ]
    fresh = sum(1 for source in all_sources if source.get("status") == "ok")
    needs_attention = len(all_sources) - fresh
    last_checked = max(
        (
            str(source.get("last_checked_at") or "")
            for source in all_sources
            if source.get("last_checked_at")
        ),
        default="",
    )
    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("Live products", str(len(live_snapshots)), f"{len(all_sources)} source URLs")
    with metric_columns[1]:
        st.metric("Fresh sources", str(fresh), "within the freshness window")
    with metric_columns[2]:
        st.metric("Need attention", str(needs_attention), "stale or failed")
    with metric_columns[3]:
        st.metric("Last check", short_timestamp(last_checked) if last_checked else "—", "")

    action_columns = st.columns([1, 1, 1.6])
    with action_columns[0]:
        if st.button(
            "↻ Refresh all live quotes",
            key="live_refresh_all",
            type="primary",
            width="stretch",
        ):
            with st.spinner("Checking every attached product page…"):
                try:
                    result = service.refresh_all()
                except Exception:
                    st.error(
                        "The refresh could not be completed. Existing quotes were kept."
                    )
                else:
                    _flash(
                        f"Checked {result['total']} live products: "
                        f"{result['refreshed']} refreshed, {result['failed']} need attention."
                    )
                    st.rerun()
    with action_columns[1]:
        if st.button(
            "↻ Refresh stale only",
            key="live_refresh_stale",
            width="stretch",
        ):
            with st.spinner("Checking stale quotes…"):
                try:
                    result = service.refresh_stale()
                except Exception:
                    st.error(
                        "The stale refresh could not be completed. Existing quotes were kept."
                    )
                else:
                    checked = result["total"] - result["skipped"]
                    if checked == 0:
                        _flash("Every live quote is already fresh. No checks were needed.")
                    else:
                        _flash(
                            f"Checked {checked} stale product(s): "
                            f"{result['refreshed']} refreshed, "
                            f"{result['failed']} need attention. "
                            f"{result['skipped']} already fresh."
                        )
                    st.rerun()
    with action_columns[2]:
        st.markdown(
            '<div class="sd-small sd-muted" style="padding-top:.55rem">'
            "Refreshes respect each retailer’s access rules and may be rate-limited. "
            "A failed check never creates a new price point.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    section_title(
        "Your live products",
        "Expand a product to manage its sources, refresh it, or remove a source",
    )
    for snapshot in live_snapshots:
        live = snapshot.get("live") or {}
        status = live.get("status_label") or "Live"
        with st.expander(
            f"{snapshot['emoji']} {snapshot['name']} · {format_inr(snapshot['current_price'])} · {status}",
            expanded=False,
        ):
            columns = st.columns(4)
            with columns[0]:
                st.markdown(
                    f'<div class="sd-kpi"><div class="sd-kpi-label">Current quote</div>'
                    f'<div class="sd-kpi-value">{e(format_inr(snapshot["current_price"]))}</div></div>',
                    unsafe_allow_html=True,
                )
            with columns[1]:
                st.markdown(
                    f'<div class="sd-kpi"><div class="sd-kpi-label">Sources</div>'
                    f'<div class="sd-kpi-value">{len(snapshot.get("sources") or [])}</div></div>',
                    unsafe_allow_html=True,
                )
            with columns[2]:
                st.markdown(
                    f'<div class="sd-kpi"><div class="sd-kpi-label">Last checked</div>'
                    f'<div class="sd-kpi-value" style="font-size:.8rem">{e(short_timestamp(live.get("last_checked_at")))}</div></div>',
                    unsafe_allow_html=True,
                )
            with columns[3]:
                st.markdown(
                    f'<div class="sd-kpi"><div class="sd-kpi-label">Status</div>'
                    f'<div style="margin-top:.2rem"><span class="sd-pill {e(live.get("status_tone") or "amber")}">'
                    f'{e(status)}</span></div></div>',
                    unsafe_allow_html=True,
                )
            if live.get("error"):
                st.warning(live["error"], icon="⚠️")
            _live_source_rows(db, settings, snapshot)
            if st.button(
                "Open product analysis",
                key=f"live_open_{snapshot['id']}",
                width="stretch",
            ):
                _open_product(snapshot["id"])

            with st.container(border=True):
                st.markdown(
                    '<div class="sd-panel-title" style="font-size:.82rem">'
                    "Remove this live product</div>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    "This removes the product, its source URLs, recorded live "
                    "quotes, history, and any watch target. Demo products are "
                    "unaffected. This cannot be undone."
                )
                confirmed = st.checkbox(
                    "I understand this cannot be undone",
                    key=f"live_remove_confirm_{snapshot['id']}",
                )
                if st.button(
                    "Remove live product",
                    key=f"live_remove_product_{snapshot['id']}",
                    disabled=not confirmed,
                ):
                    try:
                        result = service.remove_product(int(snapshot["id"]))
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        _flash(result["message"])
                        st.rerun()

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.expander("Why demo products are not mixed with live quotes"):
        st.markdown(
            """
            Demo products are synthetic samples. Live products are built from a
            specific public product page. Mixing them would make the history and
            offer comparison misleading, so a live quote can only be attached to a
            live-imported product. The catalog keeps both groups clearly labelled.
            """
        )


def render_watchlist(db: Database, snapshots: list[dict[str, Any]]) -> None:
    hero(
        "Your targets",
        "Let the app watch. <span class='gradient-text'>You decide when to buy.</span>",
        "Targets compare against the newest recorded price. A target being reached "
        "is information, not a guarantee of future availability or price.",
    )

    watched = [item for item in snapshots if item.get("watchlist")]
    if not watched:
        empty_state(
            "🎯",
            "No target prices yet",
            "Open any product and use its Watch this price form to start tracking a level.",
        )
        if st.button("Browse products", key="watchlist_browse", type="primary"):
            _go_to_page("Products")
        return

    reached_count = sum(1 for item in watched if item["watchlist"].get("reached"))
    live_watched = sum(1 for item in watched if item.get("is_live"))
    columns = st.columns(4)
    with columns[0]:
        st.metric("Active targets", str(len(watched)))
    with columns[1]:
        st.metric("Targets reached", str(reached_count))
    with columns[2]:
        st.metric("Live targets", str(live_watched), "with a live quote attached")
    with columns[3]:
        closest = min(
            watched,
            key=lambda item: (
                0
                if item["watchlist"].get("reached")
                else item["watchlist"].get("gap_to_target", 10**12)
            ),
        )
        st.metric(
            "Closest target",
            closest["name"].split()[0],
            format_inr(closest["watchlist"].get("gap_to_target")),
        )

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
    for snapshot in watched:
        watchlist = snapshot["watchlist"]
        reached = watchlist.get("reached")
        status = (
            '<span class="sd-pill green">Target reached</span>'
            if reached
            else '<span class="sd-pill amber">Watching</span>'
        )
        gap_label = (
            "Current price is at or below target"
            if reached
            else f"{format_inr(watchlist.get('gap_to_target'))} to go"
        )
        with st.container(border=True):
            top_left, top_mid, top_right = st.columns([1.5, 0.85, 0.85])
            with top_left:
                st.markdown(
                    f"""
                    <div style="display:flex;align-items:center;gap:.7rem">
                      <div style="font-size:1.6rem">{e(snapshot['emoji'])}</div>
                      <div>
                        <div style="font-family:'Space Grotesk';font-weight:650;font-size:.98rem">{e(snapshot['name'])}</div>
                        <div class="sd-muted" style="font-size:.7rem">{e(snapshot['category'])} · deal score {snapshot['deal']['score']}/100</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with top_mid:
                st.markdown(
                    f'<div class="sd-kpi"><div class="sd-kpi-label">Current</div><div class="sd-kpi-value">{e(format_inr(snapshot["current_price"]))}</div></div>',
                    unsafe_allow_html=True,
                )
            with top_right:
                st.markdown(
                    f'<div class="sd-kpi"><div class="sd-kpi-label">Target</div><div class="sd-kpi-value">{e(format_inr(watchlist["target_price"]))}</div></div>',
                    unsafe_allow_html=True,
                )
            st.markdown(
                f'<div style="margin:.45rem 0 .7rem">{status} <span class="sd-muted sd-small" style="margin-left:.4rem">{e(gap_label)}</span> {_status_pill(snapshot)}</div>',
                unsafe_allow_html=True,
            )
            if snapshot.get("is_live"):
                live = snapshot.get("live") or {}
                if live.get("status") in {"stale", "error", "partial", "no_sources"}:
                    st.warning(
                        live.get("error")
                        or "The live quote needs attention; this target uses the last known price.",
                        icon="⚠️",
                    )
                elif live.get("status") == "out_of_stock":
                    st.info(
                        "All attached live sources currently show out of stock.",
                        icon="ℹ️",
                    )
            action_left, action_mid, action_right = st.columns([1.1, 1.1, 0.9])
            with action_left:
                if st.button(
                    "Open analysis",
                    key=f"watch_open_{snapshot['id']}",
                    width="stretch",
                ):
                    _open_product(snapshot["id"])
            with action_mid:
                new_target = st.number_input(
                    "New target",
                    min_value=1,
                    max_value=100_000_000,
                    value=max(1, int(watchlist["target_price"])),
                    step=100,
                    format="%d",
                    key=f"watch_target_{snapshot['id']}",
                    label_visibility="collapsed",
                )
            with action_right:
                if st.button(
                    "Update",
                    key=f"watch_update_{snapshot['id']}",
                    width="stretch",
                    type="primary",
                ):
                    db.upsert_watchlist(int(snapshot["id"]), float(new_target))
                    _flash(f"Target updated to {format_inr(new_target)}.")
                    st.rerun()
            if st.button(
                "Remove from watchlist", key=f"watch_remove_{snapshot['id']}"
            ):
                db.remove_watchlist(int(snapshot["id"]))
                _flash(f"Removed {snapshot['name']} from the watchlist.")
                st.rerun()


def render_alerts(db: Database, snapshots: list[dict[str, Any]]) -> None:
    hero(
        "Alert inbox",
        "Every saved signal. <span class='gradient-text'>One place to act.</span>",
        "Alerts are saved when a target is reached, a live price moves, stock "
        "changes, or a quote needs attention. They are records of past checks, "
        "not predictions.",
    )

    counts = db.get_alert_counts()
    metric_columns = st.columns(5)
    with metric_columns[0]:
        st.metric("Unread", str(counts["unread"]), f"{counts['active']} active")
    with metric_columns[1]:
        st.metric("Target reached", str(counts["target"]), "watch levels")
    with metric_columns[2]:
        st.metric("Price & stock", str(counts["price"]), "recorded changes")
    with metric_columns[3]:
        st.metric("Quote checks", str(counts["quote"]), "needs attention")
    with metric_columns[4]:
        st.metric("Dismissed", str(counts["dismissed"]), "saved history")

    filters = ["Unread", "All active", "Target", "Price & stock", "Quote", "Dismissed"]
    filter_choice = st.radio(
        "Show alerts",
        filters,
        horizontal=True,
        key="alert_filter",
    )
    include_dismissed = filter_choice == "Dismissed"
    alerts = db.get_alerts(include_dismissed=include_dismissed, limit=200)
    if filter_choice == "Unread":
        alerts = [alert for alert in alerts if not alert.get("read_at")]
    elif filter_choice == "Target":
        alerts = [
            alert
            for alert in alerts
            if alert_kind_group(str(alert.get("kind") or "")) == "target"
        ]
    elif filter_choice == "Price & stock":
        alerts = [
            alert
            for alert in alerts
            if alert_kind_group(str(alert.get("kind") or "")) == "price"
        ]
    elif filter_choice == "Quote":
        alerts = [
            alert
            for alert in alerts
            if alert_kind_group(str(alert.get("kind") or "")) == "quote"
        ]

    action_columns = st.columns([1.1, 1.1, 2.2])
    with action_columns[0]:
        if st.button(
            "Mark all read",
            key="alerts_mark_all_read",
            disabled=counts["unread"] == 0,
            width="stretch",
        ):
            changed = db.mark_all_alerts_read()
            _flash(f"Marked {changed} alert(s) as read.")
            st.rerun()
    with action_columns[1]:
        if st.button(
            "Clear dismissed",
            key="alerts_clear_dismissed",
            disabled=counts["dismissed"] == 0,
            width="stretch",
        ):
            changed = db.clear_dismissed_alerts()
            _flash(f"Cleared {changed} dismissed alert(s).")
            st.rerun()
    with action_columns[2]:
        st.markdown(
            '<div class="sd-small sd-muted" style="padding-top:.55rem">'
            "Dismissing an alert keeps its dedupe history, so the same event "
            "does not immediately reappear.</div>",
            unsafe_allow_html=True,
        )

    if not alerts:
        empty_state(
            "◉",
            "No alerts in this view",
            "New target, price, stock, and quote alerts will appear here after "
            "the app records a change.",
        )
        return

    for alert in alerts:
        kind = str(alert.get("kind") or "")
        label = alert_kind_label(kind)
        tone = alert_kind_tone(kind)
        unread = not alert.get("read_at")
        dismissed = bool(alert.get("dismissed_at"))
        with st.container(border=True):
            st.markdown(
                compact_html(
                    f"""
                <div style="display:flex;align-items:center;gap:.45rem;flex-wrap:wrap">
                  <span class="sd-pill {e(tone)}">{e(label)}</span>
                  {'<span class="sd-pill blue">New</span>' if unread else ''}
                  <strong style="font-size:.92rem">{e(alert.get('title') or '')}</strong>
                </div>
                <div class="sd-muted" style="font-size:.8rem;line-height:1.55;margin-top:.35rem">
                  {e(alert.get('message') or '')}
                </div>
                <div class="sd-small sd-muted" style="margin-top:.4rem">
                  {e(alert.get('product_name') or 'Catalog')} ·
                  {e(short_timestamp(alert.get('created_at')))}
                  {(' · dismissed ' + e(short_timestamp(alert.get('dismissed_at')))) if dismissed else ''}
                </div>
                """
                ),
                unsafe_allow_html=True,
            )
            product_id = alert.get("product_id")
            action_columns = st.columns([1, 1, 1, 2])
            with action_columns[0]:
                if product_id is not None and any(
                    item["id"] == int(product_id) for item in snapshots
                ):
                    if st.button(
                        "Open product",
                        key=f"alert_open_{alert['id']}",
                        width="stretch",
                    ):
                        _open_product(int(product_id))
            with action_columns[1]:
                if unread and not dismissed:
                    if st.button(
                        "Mark read",
                        key=f"alert_read_{alert['id']}",
                        width="stretch",
                    ):
                        db.mark_alert_read(int(alert["id"]))
                        st.rerun()
            with action_columns[2]:
                if not dismissed:
                    if st.button(
                        "Dismiss",
                        key=f"alert_dismiss_{alert['id']}",
                        width="stretch",
                    ):
                        db.dismiss_alert(int(alert["id"]))
                        _flash("Alert dismissed. Its history is kept.")
                        st.rerun()

    st.caption(
        "Alerts describe recorded changes only. A reached target is information, "
        "not a promise that the price will stay there."
    )


def render_purchases(db: Database, snapshots: list[dict[str, Any]]) -> None:
    hero(
        "Purchase tracker",
        "What you paid. <span class='gradient-text'>What the latest quote says.</span>",
        "Keep one private purchase record per product. The comparison uses the "
        "latest recorded price and is not a resale valuation.",
    )

    if not snapshots:
        empty_state(
            "▣",
            "No products to track",
            "Add a product before recording a purchase.",
        )
        return

    summary = summarise_purchases(snapshots)
    difference = summary["difference"]
    if difference < 0:
        difference_note = "less than the latest quotes"
    elif difference > 0:
        difference_note = "more than the latest quotes"
    else:
        difference_note = "equal to the latest quotes"

    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("Purchases tracked", str(summary["count"]))
    with metric_columns[1]:
        st.metric("Total paid", format_inr(summary["total_paid"]))
    with metric_columns[2]:
        st.metric("Latest quote value", format_inr(summary["current_value"]))
    with metric_columns[3]:
        st.metric(
            "Paid vs latest",
            format_inr(abs(difference)),
            difference_note,
        )

    section_title(
        "Record a purchase",
        "Choose a product, then save the amount you actually paid",
    )
    by_id = {int(item["id"]): item for item in snapshots}
    selected_id = st.selectbox(
        "Product",
        options=list(by_id),
        format_func=lambda product_id: by_id[product_id]["name"],
        key="purchase_product_select",
    )
    _purchase_form(db, by_id[int(selected_id)])

    if not summary["count"]:
        empty_state(
            "▣",
            "No purchases recorded yet",
            "Use the form above to save what you paid for any product. The app "
            "will compare it with the latest recorded price.",
        )
        return

    section_title(
        "Your purchases",
        "User-provided records compared with the latest recorded quotes",
    )
    rows = []
    for item in summary["products"]:
        purchase = item["purchase"]
        item_difference = float(purchase["difference_vs_current"])
        if item_difference < 0:
            difference_html = (
                f'<span style="color:#6EE7B7">{e(format_inr(abs(item_difference)))} less</span>'
            )
        elif item_difference > 0:
            difference_html = (
                f'<span style="color:#FCA5A5">{e(format_inr(item_difference))} more</span>'
            )
        else:
            difference_html = "Same"
        notes = str(purchase.get("notes") or "")
        if len(notes) > 60:
            notes = notes[:57] + "…"
        link = share_url("Products", product_id=int(item["id"]))
        rows.append(
            compact_html(
                f"""
            <tr>
              <td><strong>{e(item['name'])}</strong></td>
              <td>{e(format_inr(purchase['price_paid']))}</td>
              <td>{e(purchase.get('purchased_on') or '—')}</td>
              <td>{e(purchase.get('retailer') or '—')}</td>
              <td>{e(format_inr(item['current_price']))}</td>
              <td>{difference_html}</td>
              <td>{e(notes) if notes else '—'}</td>
              <td><a href="{e(link)}" target="_blank" rel="noopener noreferrer">Open ↗</a></td>
            </tr>
            """
            )
        )
    st.markdown(
        compact_html(
            f"""
        <div class="sd-panel">
          <div style="overflow-x:auto">
            <table class="offer-table">
              <thead><tr><th>Product</th><th>Paid</th><th>Date</th><th>Retailer</th><th>Latest quote</th><th>Paid vs latest</th><th>Notes</th><th>Analysis</th></tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
          </div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        "Purchase records are supplied by you. The latest quote may be stale or "
        "from the demo catalog; check its label before relying on the comparison."
    )


def _insight_rows(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in snapshots:
        forecast = item.get("forecast") or {}
        rows.append(
            {
                "Product": item["name"],
                "Category": item["category"],
                "Current": item["current_price"],
                "Recorded low": item["stats"].get("minimum_price"),
                "Deal score": item["deal"]["score"],
                "30-day change": item["stats"].get("change_30d_pct"),
                "7-day estimate": forecast.get("predicted_price_7d")
                if forecast.get("available")
                else None,
                "Estimated change": forecast.get("predicted_change_pct")
                if forecast.get("available")
                else None,
                "Source": _provenance_text(item),
            }
        )
    return rows


def render_insights(db: Database, snapshots: list[dict[str, Any]]) -> None:
    hero(
        "Catalog insights",
        "See the shape of the market you are tracking. <span class='gradient-text'>Then choose with context.</span>",
        "Category coverage, price movement, budget distribution, and forecast "
        "outlook — all calculated from the records shown on the product pages.",
    )

    if not snapshots:
        empty_state("◇", "No insights yet", "Add products first.")
        return

    live_count = _live_count(snapshots)
    observation_count = sum(item["stats"].get("observations", 0) for item in snapshots)
    offer_count = sum(len(item.get("offers") or []) for item in snapshots)
    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("Products analysed", str(len(snapshots)))
    with metric_columns[1]:
        st.metric("Live products", str(live_count), f"{len(snapshots) - live_count} demo")
    with metric_columns[2]:
        st.metric("Recorded observations", str(observation_count))
    with metric_columns[3]:
        st.metric("Offers recorded", str(offer_count))

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    section_title("Category strength", "Average deal score and coverage by category")
    category_rows = _category_summary(snapshots)
    frame = pd.DataFrame(category_rows)
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X("category:N", title=None, sort="-y", axis=alt.Axis(labelAngle=-20)),
            y=alt.Y("average_score:Q", title="Average deal score", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color(
                "average_score:Q",
                scale=alt.Scale(scheme="purpleblue"),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("count:Q", title="Products"),
                alt.Tooltip("average_score:Q", title="Avg score", format=".0f"),
                alt.Tooltip("average_discount:Q", title="Avg discount", format=".1f"),
            ],
        )
        .properties(height=280, background="transparent")
        .configure_view(strokeOpacity=0)
        .configure_axis(labelColor="#8F98B5", gridColor="rgba(148,163,184,0.08)")
    )
    with st.container(border=True):
        st.altair_chart(chart, width="stretch")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        section_title("Falling fastest", "Largest negative 30-day recorded change")
        falling = sorted(
            snapshots,
            key=lambda item: item["stats"].get("change_30d_pct", 0.0),
        )[:5]
        rows = "".join(
            f"<tr><td><strong>{e(item['name'])}</strong></td>"
            f"<td>{item['stats'].get('change_30d_pct', 0):+.1f}%</td>"
            f"<td>{e(format_inr(item['current_price']))}</td>"
            f"<td><span class=\"sd-pill {score_tone(item['deal']['score'])}\">{item['deal']['score']}/100</span></td></tr>"
            for item in falling
        )
        st.markdown(
            f'<div class="sd-panel"><table class="offer-table"><thead><tr><th>Product</th><th>30-day</th><th>Current</th><th>Deal</th></tr></thead><tbody>{rows}</tbody></table></div>',
            unsafe_allow_html=True,
        )
    with right:
        section_title("Forecast outlook", "Products whose 7-day estimate points lower")
        forecasted = [
            item
            for item in snapshots
            if item["forecast"].get("available")
            and item["forecast"].get("predicted_change_pct", 0) < 0
        ]
        forecasted.sort(key=lambda item: item["forecast"].get("predicted_change_pct", 0))
        if forecasted:
            rows = "".join(
                f"<tr><td><strong>{e(item['name'])}</strong></td>"
                f"<td>{item['forecast'].get('predicted_change_pct', 0):+.1f}%</td>"
                f"<td>{e(format_inr(item['forecast'].get('predicted_price_7d')))}</td>"
                f"<td>{e(item['forecast'].get('confidence', 'low'))}</td></tr>"
                for item in forecasted[:5]
            )
            st.markdown(
                f'<div class="sd-panel"><table class="offer-table"><thead><tr><th>Product</th><th>Est. change</th><th>Est. price</th><th>Confidence</th></tr></thead><tbody>{rows}</tbody></table></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No product currently has a 7-day estimate pointing lower.")

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    section_title("Budget map", "Where the catalog sits by current price")
    budget_rows = []
    for label, (low, high) in BUDGET_BANDS.items():
        if label == "Any budget":
            continue
        items = _filter_by_budget(snapshots, label)
        best = max(items, key=lambda item: item["deal"]["score"]) if items else None
        budget_rows.append(
            compact_html(
                f"""
            <tr>
              <td><strong>{e(label)}</strong></td>
              <td>{len(items)}</td>
              <td>{e(format_inr(_average(item['current_price'] for item in items)) if items else '—')}</td>
              <td>{e(best['name']) if best else '—'}</td>
              <td>{f"{best['deal']['score']}/100" if best else '—'}</td>
            </tr>
            """
            )
        )
    st.markdown(
        compact_html(
            f"""
        <div class="sd-panel">
          <div style="overflow-x:auto">
            <table class="offer-table">
              <thead><tr><th>Budget band</th><th>Products</th><th>Average price</th><th>Best deal</th><th>Score</th></tr></thead>
              <tbody>{''.join(budget_rows)}</tbody>
            </table>
          </div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    with st.expander("How to use these insights"):
        st.markdown(
            """
            These views describe the records in this app. A category with a higher
            average score is not automatically a better place to shop; it means the
            current prices in that category sit relatively low against their own
            histories. Forecast rows are estimates with uncertainty, not promises.
            """
        )


def render_how_it_works(
    db: Database,
    snapshots: list[dict[str, Any]],
    settings: Settings,
) -> None:
    hero(
        "Transparent by design",
        "Understand the number. <span class='gradient-text'>Trust the reasoning.</span>",
        "Every quote is labelled, every calculation is visible, and the copilot is "
        "grounded in the same records you see on the product pages.",
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(
            """
            <div class="sd-panel" style="min-height:255px">
              <div class="sd-panel-title">Deal score · 0–100</div>
              <p class="sd-muted" style="font-size:.8rem;line-height:1.6">
                The score compares a price with the product's own recorded history.
                It is not a cross-product quality rating.
              </p>
              <div style="font-size:.78rem;line-height:1.9;margin-top:.5rem">
                <div><strong>40%</strong> · price position between recorded low and high</div>
                <div><strong>25%</strong> · discount against detected MRP</div>
                <div><strong>20%</strong> · direction of the latest 30 observations</div>
                <div><strong>15%</strong> · effective seller offer after coupon and delivery</div>
              </div>
              <div class="sd-muted" style="font-size:.72rem;margin-top:.75rem">
                Labels: Excellent ≥78 · Good ≥62 · Fair ≥45 · Wait &lt;45
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="sd-panel" style="min-height:255px">
              <div class="sd-panel-title">7-day estimate</div>
              <p class="sd-muted" style="font-size:.8rem;line-height:1.6">
                A trend line fits the latest recorded observations and projects the
                next seven days. The dashed band widens with the model's uncertainty,
                so you see a range instead of a single “certain” number.
              </p>
              <p class="sd-muted" style="font-size:.8rem;line-height:1.6">
                Confidence reflects fit quality, residual size, and the number of
                observations. A forecast is a planning estimate, not a promise.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    live_count = _live_count(snapshots)
    observation_count = sum(item["stats"].get("observations", 0) for item in snapshots)
    offer_count = sum(len(item.get("offers") or []) for item in snapshots)
    source_count = sum(len(item.get("sources") or []) for item in snapshots)
    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric("Products", str(len(snapshots)), f"{live_count} live")
    with metric_columns[1]:
        st.metric("Marketplace sources", str(source_count))
    with metric_columns[2]:
        st.metric("Recorded observations", str(observation_count))
    with metric_columns[3]:
        st.metric("Offers recorded", str(offer_count))

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(
            """
            <div class="sd-panel">
              <div class="sd-panel-title">How live quotes work</div>
              <div class="sd-small sd-muted" style="line-height:1.75">
                1. Paste one public product-detail page from Amazon.in, Flipkart, or
                another retailer with readable product metadata.<br>
                2. The app records the listed price, retailer, seller, MRP if shown,
                and availability. Coupons and delivery fees are not inferred.<br>
                3. One quote is kept per source. The product's current price is the
                lowest in-stock quote across its attached sources.<br>
                4. A refresh replaces the last quote for that source. A failed refresh
                keeps the last successful price and marks it stale.<br>
                5. The app respects access rules and never bypasses CAPTCHAs, logins,
                or anti-bot controls. Only INR quotes are accepted.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="sd-panel">
              <div class="sd-panel-title">What the labels mean</div>
              <div class="sd-small sd-muted" style="line-height:1.75">
                <strong style="color:#A7F3D0">Live quote</strong> — the last successful
                reading of a specific product page. It can still be stale.<br>
                <strong style="color:#FDE68A">Stale quote</strong> — the last good quote
                is older than the freshness window; refresh before relying on it.<br>
                <strong style="color:#FDE68A">Demo data</strong> — synthetic sample rows
                for exploring the app. Never presented as a live price.<br>
                <strong style="color:#BFDBFE">App calculation</strong> — deal score and
                savings computed from recorded rows.<br>
                <strong style="color:#BFDBFE">Estimate</strong> — the 7-day trend range,
                with uncertainty.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="sd-panel">
          <div class="sd-panel-title">Try the copilot</div>
          <div class="sd-muted" style="font-size:.8rem;line-height:1.7">
            1. Open <strong>Products</strong> and choose a product.<br>
            2. Press <strong>✦ Copilot</strong> at the bottom-right.<br>
            3. Try <em>Is this a good deal?</em>, <em>Should I buy now or wait?</em>,
            <em>Find the best available offer</em>, or ask it to
            <em>set a target at ₹22,000</em>.<br>
            4. Use <strong>Enter</strong> to send and <strong>Shift+Enter</strong> for a new line.<br>
            5. The copilot follows the product you open and labels live, demo,
            calculated, and estimated information.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if settings.ai_configured:
        st.caption(
            "Smart explanations are enabled. They are grounded in the same product "
            "records and always fall back to built-in analysis if a response is unavailable."
        )
    else:
        st.caption(
            "Guided analysis is active. The copilot answers from the app's recorded "
            "prices, calculations, and watchlist without calling an external service."
        )


def render_footer() -> None:
    st.markdown(
        """
        <div style="margin-top:2.5rem;padding-top:1rem;border-top:1px solid rgba(167,139,250,.10);
          display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
          color:#6F7898;font-size:.68rem">
          <span>✦ AI Smart Deal Predictor · live quotes + demo catalog</span>
          <span>Facts labelled · calculations transparent · estimates bounded</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
