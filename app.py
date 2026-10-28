"""AI Smart Deal Predictor — Streamlit entry point.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from smartdeal.alerts import sync_target_alerts
from smartdeal.analytics import build_all_snapshots
from smartdeal.config import get_settings
from smartdeal.database import Database
from smartdeal.live.seed import seed_recorded_live_quotes
from smartdeal.ui.copilot import render_copilot
from smartdeal.ui.deep_links import apply_deep_link, sync_deep_link
from smartdeal.ui.theme import inject_theme
from smartdeal.ui.views import (
    render_alerts,
    render_compare,
    render_dashboard,
    render_deals,
    render_footer,
    render_how_it_works,
    render_insights,
    render_live_quotes,
    render_products,
    render_purchases,
    render_sidebar,
    render_watchlist,
    show_flash,
)


def _init_session_state() -> None:
    defaults = {
        "selected_product_id": None,
        "view": "catalog",
        "nav_page": "Dashboard",
        "pending_nav_page": None,
        "copilot_open": False,
        "copilot_messages": [],
        "copilot_pending": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def main() -> None:
    st.set_page_config(
        page_title="AI Smart Deal Predictor",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            "About": (
                "AI Smart Deal Predictor — grounded shopping intelligence with live "
                "marketplace quotes, a demo catalog, and a context-aware copilot."
            )
        },
    )
    inject_theme()
    _init_session_state()

    settings = get_settings()
    db = Database(settings.db_path)
    try:
        db.initialize()
    except Exception:
        st.error(
            "The shopping data could not be loaded. Check that the application can "
            "write to its data folder and restart."
        )
        st.stop()

    # Community Cloud resets local files on restart. Re-attach the verified
    # recorded quotes so the live workspace is never empty; existing imports
    # and user removals are left alone.
    if settings.seed_live_demo:
        try:
            seed_recorded_live_quotes(db)
        except Exception:
            pass

    try:
        snapshots = build_all_snapshots(db, stale_hours=settings.live_stale_hours)
    except Exception:
        st.error("The recorded shopping data could not be loaded. Please restart the app.")
        st.stop()

    # A deleted/renamed product should not leave a stale copilot context.
    selected_id = st.session_state.get("selected_product_id")
    if selected_id is not None and not any(
        item["id"] == int(selected_id) for item in snapshots
    ):
        st.session_state.selected_product_id = None
        st.session_state.view = "catalog"

    try:
        sync_target_alerts(db, snapshots)
    except Exception:
        # Alerting is supplementary and must never prevent the catalog loading.
        pass

    apply_deep_link(snapshots)
    live_count = sum(1 for item in snapshots if item.get("is_live"))
    page = render_sidebar(db, settings, len(snapshots), live_count)
    show_flash()

    if page == "Dashboard":
        render_dashboard(db, snapshots, settings)
    elif page == "Deals":
        render_deals(db, snapshots)
    elif page == "Products":
        render_products(db, snapshots, settings)
    elif page == "Compare":
        render_compare(db, snapshots)
    elif page == "Live quotes":
        render_live_quotes(db, snapshots, settings)
    elif page == "Watchlist":
        render_watchlist(db, snapshots)
    elif page == "Alerts":
        render_alerts(db, snapshots)
    elif page == "Purchases":
        render_purchases(db, snapshots)
    elif page == "Insights":
        render_insights(db, snapshots)
    else:
        render_how_it_works(db, snapshots, settings)

    sync_deep_link(page, snapshots)
    render_footer()
    render_copilot(db, settings)


if __name__ == "__main__":
    main()
