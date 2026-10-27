"""Reusable visual components for the deal dashboard and product pages."""

from __future__ import annotations

import html
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from ..analytics import format_inr
from ..live.status import parse_timestamp


def e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def compact_html(value: str) -> str:
    """Collapse HTML whitespace so Streamlit never renders indented rows as code."""

    return " ".join(str(value).split())


def short_timestamp(value: Any) -> str:
    parsed = parse_timestamp(value)
    if parsed is None:
        return "—"
    return parsed.astimezone().strftime("%d %b %Y, %H:%M")


def provenance_pill(snapshot: dict[str, Any]) -> str:
    live = snapshot.get("live") or {}
    if snapshot.get("is_live"):
        tone = str(live.get("status_tone") or "green")
        label = str(live.get("status_label") or "Live")
        return f'<span class="sd-pill {tone}">{e(label)}</span>'
    return '<span class="sd-pill amber">Demo data</span>'


def _source_count_text(snapshot: dict[str, Any]) -> str:
    live = snapshot.get("live") or {}
    count = int(live.get("source_count") or 0)
    if not snapshot.get("is_live"):
        return ""
    if count == 0:
        return "No source URLs"
    return f"{count} source{'s' if count != 1 else ''}"


def _live_warning(snapshot: dict[str, Any]) -> str:
    live = snapshot.get("live") or {}
    if not snapshot.get("is_live"):
        return ""
    status = str(live.get("status") or "")
    if status == "ok":
        return ""
    if status == "out_of_stock":
        return "All live sources currently show out of stock."
    if status == "stale":
        return (
            "This quote is stale. The last successful price is shown; refresh "
            "before relying on it."
        )
    if status in {"partial", "error", "no_sources"}:
        return str(live.get("error") or "Some live sources could not be checked.")
    return ""


def score_tone(score: int) -> str:
    if score >= 78:
        return "green"
    if score >= 62:
        return "blue"
    if score >= 45:
        return "amber"
    return "rose"


def score_fill_class(score: int) -> str:
    if score >= 78:
        return "good"
    if score < 45:
        return "warm"
    return ""


def hero(eyebrow: str, title_html: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="sd-hero">
          <div class="sd-eyebrow">{e(eyebrow)}</div>
          <div class="sd-hero-title">{title_html}</div>
          <p class="sd-hero-sub">{e(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, subtitle: str | None = None) -> None:
    sub = f'<div class="sd-muted sd-small">{e(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f'<div class="sd-section-title">{e(title)}</div>{sub}',
        unsafe_allow_html=True,
    )


def product_card_html(snapshot: dict[str, Any]) -> str:
    deal = snapshot["deal"]
    savings = snapshot["savings"]
    stats = snapshot["stats"]
    live = snapshot.get("live") or {}
    trend = stats.get("trend_direction", "stable")
    trend_icon = {"falling": "↘", "rising": "↗", "stable": "→"}.get(trend, "→")
    score = int(deal["score"])
    source_count = _source_count_text(snapshot)
    meta = f"{e(snapshot['category'])} &nbsp;·&nbsp; {trend_icon} {e(trend)} trend"
    if source_count:
        meta += f" &nbsp;·&nbsp; {e(source_count)}"
    if snapshot.get("has_list_price"):
        list_html = (
            f'<span class="product-list-price">'
            f'{e(format_inr(snapshot["list_price"]))}</span>'
        )
        saving_html = (
            f'<div class="product-saving">Save '
            f'{e(format_inr(savings["vs_list_price"]))} '
            f'({savings["vs_list_pct"]:.1f}% off list)</div>'
        )
    else:
        list_html = (
            '<span class="sd-muted" style="font-size:.66rem">MRP not detected</span>'
        )
        saving_html = (
            '<div class="sd-muted" style="font-size:.66rem;margin-top:.15rem">'
            "Discount unavailable without a detected MRP</div>"
        )
    warning = _live_warning(snapshot)
    warning_html = (
        f'<div class="sd-muted" style="font-size:.64rem;line-height:1.45;'
        f'margin-top:.45rem;color:#FDE68A">{e(warning)}</div>'
        if warning
        else ""
    )
    return f"""
    <div class="product-card">
      <div class="product-card-top">
        <div class="product-emoji">{e(snapshot['emoji'])}</div>
        <div style="display:flex;gap:.35rem;flex-wrap:wrap;justify-content:flex-end">
          {provenance_pill(snapshot)}
          <span class="sd-pill {score_tone(score)}">{score}/100 · {e(deal['label'])}</span>
        </div>
      </div>
      <div class="product-name">{e(snapshot['name'])}</div>
      <div class="product-meta">{meta}</div>
      <div class="product-price-row">
        <span class="product-price">{e(format_inr(snapshot['current_price']))}</span>
        {list_html}
      </div>
      {saving_html}
      {warning_html}
      <div class="score-row">
        <div class="score-track"><div class="score-fill {score_fill_class(score)}" style="width:{max(3, score)}%"></div></div>
        <div class="score-value">{score}/100</div>
      </div>
    </div>
    """


def product_detail_header(snapshot: dict[str, Any]) -> None:
    deal = snapshot["deal"]
    savings = snapshot["savings"]
    stats = snapshot["stats"]
    live = snapshot.get("live") or {}
    score = int(deal["score"])
    trend = stats.get("trend_direction", "stable")
    trend_icon = {"falling": "↘", "rising": "↗", "stable": "→"}.get(trend, "→")
    has_history = bool(stats.get("available"))
    source_count = _source_count_text(snapshot)
    if snapshot.get("has_list_price"):
        price_detail = (
            f'<span class="sd-muted" style="text-decoration:line-through">'
            f'{e(format_inr(snapshot["list_price"]))}</span>'
            f'<span class="product-saving">Save '
            f'{e(format_inr(savings["vs_list_price"]))} '
            f'({savings["vs_list_pct"]:.1f}%)</span>'
        )
    else:
        price_detail = (
            '<span class="sd-muted" style="font-size:.76rem">'
            "MRP not detected, so no discount is shown</span>"
        )
    if snapshot.get("is_live"):
        provenance_detail = (
            f"{provenance_pill(snapshot)} "
            f'<span class="sd-muted" style="font-size:.68rem;margin-left:.35rem">'
            f"{e(source_count)} · last checked {e(short_timestamp(live.get('last_checked_at')))}"
            "</span>"
        )
    else:
        provenance_detail = (
            '<span class="sd-pill amber">Demo data</span> '
            '<span class="sd-muted" style="font-size:.68rem;margin-left:.35rem">'
            "Synthetic catalog · not live marketplace prices</span>"
        )
    warning = _live_warning(snapshot)
    warning_html = (
        f'<div class="sd-muted" style="font-size:.72rem;line-height:1.5;'
        f'margin-top:.55rem;color:#FDE68A">{e(warning)}</div>'
        if warning
        else ""
    )
    change_html = (
        f"{stats.get('change_30d_pct', 0):+.1f}%" if has_history else "—"
    )
    st.markdown(
        f"""
        <div class="sd-hero">
          <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap">
            <div>
              <div class="sd-eyebrow">{e(snapshot['category'])} · {e(snapshot['brand'])}</div>
              <div class="sd-hero-title" style="font-size:clamp(1.55rem,3vw,2.35rem);margin-bottom:.25rem">
                {e(snapshot['emoji'])} {e(snapshot['name'])}
              </div>
              <p class="sd-hero-sub" style="margin-bottom:.8rem">{e(snapshot['description'])}</p>
            </div>
            <div style="display:flex;gap:.35rem;flex-wrap:wrap;justify-content:flex-end">
              {provenance_pill(snapshot)}
              <span class="sd-pill {score_tone(score)}">{score}/100 · {e(deal['label'])}</span>
            </div>
          </div>
          <div style="display:flex;gap:1.15rem;align-items:baseline;flex-wrap:wrap">
            <span class="sd-detail-price">{e(format_inr(snapshot['current_price']))}</span>
            {price_detail}
          </div>
          <div style="margin-top:.55rem">{provenance_detail}</div>
          {warning_html}
          <div class="sd-kpi-row">
            <div class="sd-kpi"><div class="sd-kpi-label">Recorded low</div><div class="sd-kpi-value">{e(format_inr(stats.get('minimum_price')))}</div></div>
            <div class="sd-kpi"><div class="sd-kpi-label">Recorded average</div><div class="sd-kpi-value">{e(format_inr(stats.get('average_price')))}</div></div>
            <div class="sd-kpi"><div class="sd-kpi-label">30-day change</div><div class="sd-kpi-value">{change_html}</div></div>
            <div class="sd-kpi"><div class="sd-kpi-label">Trend</div><div class="sd-kpi-value">{trend_icon} {e(trend) if has_history else '—'}</div></div>
            <div class="sd-kpi"><div class="sd-kpi-label">Observations</div><div class="sd-kpi-value">{stats.get('observations', 0)}</div></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def price_history_chart(
    snapshot: dict[str, Any], height: int = 320, compact: bool = False
) -> alt.Chart:
    history = pd.DataFrame(snapshot.get("history") or [])
    if history.empty:
        raise ValueError("No history available for chart")
    history["date"] = pd.to_datetime(history["observed_on"])
    history["price"] = pd.to_numeric(history["price"], errors="coerce")
    history = history.dropna(subset=["date", "price"])

    base = alt.Chart(history)
    line = base.mark_line(
        color="#A78BFA",
        strokeWidth=2.3 if not compact else 1.8,
        interpolate="monotone",
    ).encode(
        x=alt.X(
            "date:T",
            title=None,
            axis=alt.Axis(
                format="%b %d",
                labelColor="#8F98B5",
                grid=False,
                tickCount=5 if compact else 8,
                labels=not compact,
            ),
        ),
        y=alt.Y(
            "price:Q",
            title=None,
            scale=alt.Scale(zero=False),
            axis=alt.Axis(
                labelColor="#8F98B5",
                gridColor="rgba(148,163,184,0.08)",
                domain=False,
                labels=not compact,
                tickCount=4,
            ),
        ),
        tooltip=[
            alt.Tooltip("date:T", title="Date", format="%b %d, %Y"),
            alt.Tooltip("price:Q", title="Price", format=",.0f"),
        ],
    )

    layers: list[alt.Chart] = [
        base.mark_area(
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#8B5CF6", offset=0),
                    alt.GradientStop(color="rgba(139,92,246,0)", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
            opacity=0.16,
            interpolate="monotone",
        ).encode(
            x="date:T",
            y=alt.Y("price:Q", scale=alt.Scale(zero=False)),
        ),
        line,
    ]

    forecast = snapshot.get("forecast") or {}
    if forecast.get("available") and not compact:
        predictions = pd.DataFrame(forecast.get("predictions") or [])
        if not predictions.empty:
            predictions["date"] = pd.to_datetime(predictions["date"])
            predictions["predicted_price"] = pd.to_numeric(
                predictions["predicted_price"], errors="coerce"
            )
            predictions["lower_bound"] = pd.to_numeric(
                predictions["lower_bound"], errors="coerce"
            )
            predictions["upper_bound"] = pd.to_numeric(
                predictions["upper_bound"], errors="coerce"
            )
            band = (
                alt.Chart(predictions)
                .mark_area(color="#38BDF8", opacity=0.13)
                .encode(
                    x="date:T",
                    y=alt.Y("lower_bound:Q", scale=alt.Scale(zero=False)),
                    y2="upper_bound:Q",
                )
            )
            forecast_line = (
                alt.Chart(predictions)
                .mark_line(
                    color="#38BDF8", strokeWidth=2, strokeDash=[5, 4], interpolate="monotone"
                )
                .encode(
                    x="date:T",
                    y=alt.Y("predicted_price:Q", scale=alt.Scale(zero=False)),
                    tooltip=[
                        alt.Tooltip("date:T", title="Forecast date", format="%b %d, %Y"),
                        alt.Tooltip(
                            "predicted_price:Q", title="Estimate", format=",.0f"
                        ),
                    ],
                )
            )
            connect = pd.DataFrame(
                {
                    "date": [history["date"].iloc[-1], predictions["date"].iloc[0]],
                    "price": [
                        history["price"].iloc[-1],
                        predictions["predicted_price"].iloc[0],
                    ],
                }
            )
            connector = (
                alt.Chart(connect)
                .mark_line(
                    color="#38BDF8", strokeWidth=2, strokeDash=[5, 4]
                )
                .encode(x="date:T", y="price:Q")
            )
            layers.extend([band, forecast_line, connector])

    latest = history.tail(1)
    point = (
        alt.Chart(latest)
        .mark_circle(size=65, color="#F4F5FF", stroke="#8B5CF6", strokeWidth=3)
        .encode(
            x="date:T",
            y="price:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Latest record", format="%b %d, %Y"),
                alt.Tooltip("price:Q", title="Price", format=",.0f"),
            ],
        )
    )
    layers.append(point)

    return (
        alt.layer(*layers)
        .properties(height=height, background="transparent")
        .configure_view(strokeOpacity=0)
        .configure_axis(
            labelFont="Manrope",
            labelFontSize=10,
            titleFont="Manrope",
            gridOpacity=1,
        )
        .configure_legend(disable=True)
        .interactive()
    )


def render_price_chart(
    snapshot: dict[str, Any], height: int = 320, compact: bool = False
) -> None:
    try:
        chart = price_history_chart(snapshot, height=height, compact=compact)
    except (ValueError, KeyError):
        st.info("Price history is not available for this product yet.")
        return
    st.altair_chart(chart, width="stretch")


def score_breakdown_html(snapshot: dict[str, Any]) -> str:
    deal = snapshot["deal"]
    labels = {
        "price_position": "Price position",
        "discount": "Discount vs list",
        "trend": "Recent trend",
        "offer": "Seller offer",
    }
    rows = []
    for key, label in labels.items():
        value = float(deal["components"].get(key, 0))
        weight = int(float(deal["weights"].get(key, 0)) * 100)
        rows.append(
            compact_html(
                f"""
            <div style="margin-bottom:.65rem">
              <div style="display:flex;justify-content:space-between;font-size:.75rem;margin-bottom:.28rem">
                <span>{e(label)} <span class="sd-muted">· {weight}% weight</span></span>
                <strong>{value:.0f}/100</strong>
              </div>
              <div class="score-track" style="height:5px"><div class="score-fill {score_fill_class(int(value))}" style="width:{max(2, value)}%"></div></div>
            </div>
            """
            )
        )
    score = int(deal["score"])
    provenance_note = (
        "Calculated from live quote observations recorded by this app."
        if snapshot.get("is_live")
        else "Calculated from synthetic demo observations."
    )
    return compact_html(
        f"""
    <div class="sd-panel">
      <div style="display:flex;gap:1rem;align-items:center;margin-bottom:.9rem">
        <div style="width:92px;height:92px;border-radius:50%;flex:0 0 auto;
          background:conic-gradient(#8B5CF6 0 {score}%, rgba(255,255,255,.06) {score}% 100%);
          display:grid;place-items:center;box-shadow:0 0 32px rgba(139,92,246,.20)">
          <div style="width:72px;height:72px;border-radius:50%;background:#10142a;display:grid;place-items:center;text-align:center">
            <div>
              <div style="font-family:'Space Grotesk';font-size:1.35rem;font-weight:700;line-height:1">{score}</div>
              <div style="font-size:.55rem;color:#9AA3C0;text-transform:uppercase;letter-spacing:.08em">of 100</div>
            </div>
          </div>
        </div>
        <div>
          <div class="sd-panel-title" style="margin-bottom:.15rem">{e(deal['label'])}</div>
          <div class="sd-muted" style="font-size:.75rem;line-height:1.45">{e(deal['summary'])}</div>
        </div>
      </div>
      {''.join(rows)}
      <div class="sd-small sd-muted" style="margin-top:.55rem">{e(provenance_note)}</div>
    </div>
    """
    )


def forecast_panel_html(snapshot: dict[str, Any]) -> str:
    forecast = snapshot.get("forecast") or {}
    live_note = (
        '<div class="sd-small sd-muted" style="margin-top:.55rem;line-height:1.45">'
        "Live history starts when you import or refresh this product. It is not "
        "backfilled from the marketplace.</div>"
        if snapshot.get("is_live")
        else ""
    )
    if not forecast.get("available"):
        return f"""
        <div class="sd-panel">
          <div class="sd-panel-title">7-day estimate</div>
          <div class="sd-muted" style="font-size:.78rem">{e(forecast.get('reason', 'Not enough recorded history for a forecast.'))}</div>
          {live_note}
        </div>
        """
    direction = forecast.get("direction", "stable")
    arrow = {"falling": "↘", "rising": "↗", "stable": "→"}.get(direction, "→")
    confidence = forecast.get("confidence", "low")
    tone = {"high": "green", "medium": "blue", "low": "amber"}.get(confidence, "amber")
    return f"""
    <div class="sd-panel">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
        <div class="sd-panel-title" style="margin:0">7-day trend estimate</div>
        <span class="sd-pill {tone}">{e(confidence)} confidence</span>
      </div>
      <div style="display:flex;align-items:baseline;gap:.55rem;margin:.7rem 0 .15rem">
        <span class="sd-detail-price" style="font-size:1.65rem">{e(format_inr(forecast.get('predicted_price_7d')))}</span>
        <span class="sd-muted" style="font-size:.76rem">{arrow} {forecast.get('predicted_change_pct', 0):+.1f}%</span>
      </div>
      <div class="sd-muted" style="font-size:.74rem">
        Likely range: {e(format_inr(forecast.get('lower_bound_7d')))} – {e(format_inr(forecast.get('upper_bound_7d')))}
      </div>
      <div class="sd-small sd-muted" style="margin-top:.65rem;line-height:1.5">
        {e(forecast.get('method'))}. R² {forecast.get('r_squared')}. This is an estimate,
        not a promise that the price will move in this direction.
      </div>
      {live_note}
    </div>
    """


def offers_table_html(snapshot: dict[str, Any]) -> str:
    offers = snapshot.get("offers") or []
    if snapshot.get("is_live"):
        if not offers:
            return (
                '<div class="sd-panel"><div class="sd-panel-title">Live marketplace quotes</div>'
                '<div class="sd-muted sd-small">No live quote is recorded yet. '
                "Refresh the sources or add another product URL.</div></div>"
            )
        rows = []
        for offer in offers:
            best = "best-row" if offer.get("is_best") else ""
            if offer.get("stale"):
                status = '<span class="sd-pill amber">Stale</span>'
            elif offer.get("in_stock"):
                status = '<span class="sd-pill green">In stock</span>'
            else:
                status = '<span class="sd-pill rose">Out of stock</span>'
            mrp = (
                e(format_inr(offer.get("list_price")))
                if float(offer.get("list_price") or 0) > float(offer["price"])
                else "—"
            )
            url = str(offer.get("source_url") or "")
            link = (
                f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>'
                if url.startswith(("http://", "https://"))
                else "—"
            )
            rows.append(
                compact_html(
                    f"""
                <tr class="{best}">
                  <td><strong>{e(offer.get('retailer') or offer['seller'])}</strong>{' <span class="sd-pill green" style="font-size:.58rem">Best</span>' if offer.get('is_best') else ''}<br><span class="sd-muted" style="font-size:.64rem">{e(offer['seller'])}</span></td>
                  <td>{e(format_inr(offer['price']))}</td>
                  <td>{mrp}</td>
                  <td>{e(offer.get('availability') or 'Not confirmed')}</td>
                  <td>{e(str(offer.get('last_seen') or '')[:10])}</td>
                  <td>{link}</td>
                  <td>{status}</td>
                </tr>
                """
                )
            )
        return compact_html(
            f"""
        <div class="sd-panel">
          <div class="sd-panel-title">Live marketplace quotes</div>
          <div class="sd-muted sd-small" style="margin-bottom:.45rem">
            One quote per source URL. Coupons and delivery fees are not inferred;
            confirm them on the retailer page.
          </div>
          <div style="overflow-x:auto">
            <table class="offer-table">
              <thead><tr><th>Retailer / seller</th><th>Listed</th><th>MRP</th><th>Availability</th><th>Last seen</th><th>Source</th><th>Status</th></tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
          </div>
        </div>
        """
        )

    if not offers:
        return '<div class="sd-muted sd-small">No seller offers are recorded for this product.</div>'
    rows = []
    for offer in offers:
        best = "best-row" if offer.get("is_best") else ""
        stock = (
            '<span class="sd-pill green">In stock</span>'
            if offer.get("in_stock")
            else '<span class="sd-pill rose">Out of stock</span>'
        )
        coupon = offer.get("coupon_code") or "—"
        rows.append(
            compact_html(
                f"""
            <tr class="{best}">
              <td><strong>{e(offer['seller'])}</strong>{' <span class="sd-pill green" style="font-size:.58rem">Best</span>' if offer.get('is_best') else ''}</td>
              <td>{e(format_inr(offer['price']))}</td>
              <td>{e(coupon)}</td>
              <td>{e(format_inr(offer.get('delivery_fee')))}</td>
              <td><strong>{e(format_inr(offer['total_price']))}</strong></td>
              <td>{stock}</td>
            </tr>
            """
            )
        )
    return compact_html(
        f"""
    <div class="sd-panel">
      <div class="sd-panel-title">Recorded seller offers · demo</div>
      <div class="sd-muted sd-small" style="margin-bottom:.45rem">
        Synthetic sample offers. Effective total includes the recorded coupon and delivery fee.
      </div>
      <div style="overflow-x:auto">
        <table class="offer-table">
          <thead><tr><th>Seller</th><th>Listed</th><th>Coupon</th><th>Delivery</th><th>Total</th><th>Status</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </div>
    """
    )


def live_sources_html(snapshot: dict[str, Any]) -> str:
    if not snapshot.get("is_live"):
        return ""
    live = snapshot.get("live") or {}
    sources = live.get("sources") or []
    if not sources:
        return (
            '<div class="sd-panel"><div class="sd-panel-title">Marketplace sources</div>'
            '<div class="sd-muted sd-small">No source URLs are attached yet. '
            "Add one from the Live quotes page.</div></div>"
        )
    rows = []
    for source in sources:
        price = (
            e(format_inr(source.get("last_price")))
            if source.get("last_price") is not None
            else "—"
        )
        list_price = source.get("last_list_price")
        mrp = (
            e(format_inr(list_price))
            if list_price is not None
            and source.get("last_price") is not None
            and float(list_price) > float(source["last_price"])
            else "—"
        )
        url = str(source.get("url") or "")
        link = (
            f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>'
            if url.startswith(("http://", "https://"))
            else "—"
        )
        label = source.get("label") or ""
        label_html = (
            f'<br><span class="sd-muted" style="font-size:.64rem">{e(label)}</span>'
            if label
            else ""
        )
        rows.append(
            compact_html(
                f"""
            <tr>
              <td><strong>{e(source.get('retailer') or 'Marketplace')}</strong>{label_html}</td>
              <td>{price}</td>
              <td>{mrp}</td>
              <td>{e(short_timestamp(source.get('last_checked_at')))}</td>
              <td><span class="sd-pill {e(source.get('status_tone') or 'amber')}">{e(source.get('status_label') or 'Not checked')}</span></td>
              <td>{link}</td>
            </tr>
            """
            )
        )
    error = str(live.get("error") or "").strip()
    error_html = (
        f'<div class="sd-small" style="margin-top:.55rem;color:#FCA5A5;line-height:1.45">{e(error)}</div>'
        if error
        else ""
    )
    return compact_html(
        f"""
    <div class="sd-panel">
      <div class="sd-panel-title">Marketplace sources</div>
      <div class="sd-muted sd-small" style="margin-bottom:.45rem">
        A failed refresh keeps the last successful price and marks it stale.
      </div>
      <div style="overflow-x:auto">
        <table class="offer-table">
          <thead><tr><th>Retailer</th><th>Last quote</th><th>MRP</th><th>Last checked</th><th>Status</th><th>Source</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
      {error_html}
    </div>
    """
    )


def watchlist_panel_html(snapshot: dict[str, Any]) -> str:
    watchlist = snapshot.get("watchlist")
    suggested = snapshot.get("suggested_target") or {}
    live_note = ""
    if snapshot.get("is_live"):
        live_status = str((snapshot.get("live") or {}).get("status") or "")
        if live_status == "stale":
            live_note = "This gap is based on a stale live quote. Refresh before relying on it."
        elif live_status in {"error", "no_sources"}:
            live_note = "The gap uses the last known price because the live refresh failed."
        else:
            live_note = "The gap uses the latest live quote recorded by this app."
    live_note_html = (
        f'<div class="sd-small" style="margin-top:.45rem;color:#FDE68A;line-height:1.45">{e(live_note)}</div>'
        if live_note
        else ""
    )
    if watchlist:
        reached = watchlist.get("reached")
        status = (
            '<span class="sd-pill green">Target reached</span>'
            if reached
            else '<span class="sd-pill amber">Watching</span>'
        )
        detail = (
            "Current price is at or below your target."
            if reached
            else f"Need another {format_inr(watchlist.get('gap_to_target'))} drop."
        )
        return f"""
        <div class="sd-panel">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem">
            <div class="sd-panel-title" style="margin:0">Your target</div>{status}
          </div>
          <div class="sd-detail-price" style="font-size:1.5rem;margin-top:.5rem">{e(format_inr(watchlist['target_price']))}</div>
          <div class="sd-muted sd-small">{e(detail)}</div>
          <div class="sd-small sd-muted" style="margin-top:.45rem">Data-anchored suggestion: {e(format_inr(suggested.get('target_price')))}</div>
          {live_note_html}
        </div>
        """
    return f"""
    <div class="sd-panel">
      <div class="sd-panel-title">Target-price watch</div>
      <div class="sd-muted sd-small" style="line-height:1.55">
        A data-anchored suggestion is <strong>{e(format_inr(suggested.get('target_price')))}</strong>.
        {e(suggested.get('rationale'))} Set a target and the Watchlist page will track it.
      </div>
      {live_note_html}
    </div>
    """


def empty_state(icon: str, title: str, caption: str) -> None:
    st.markdown(
        f"""
        <div class="sd-empty">
          <div class="sd-empty-icon">{e(icon)}</div>
          <div class="sd-section-title">{e(title)}</div>
          <div class="sd-muted sd-small">{e(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def source_badge(source: str, model: str = "") -> str:
    if source == "ai":
        label = "AI-written explanation · grounded in app data"
        tone = ""
    elif source == "action":
        label = "Watchlist updated · verified in app"
        tone = ""
    else:
        label = (
            "Built-in analysis · no external service"
            if source == "local"
            else "Built-in analysis · smart explanation unavailable"
        )
        tone = "local" if source == "local" else "error"
    return (
        f'<div class="sd-source-badge"><span class="dot {tone}"></span>{e(label)}</div>'
    )
