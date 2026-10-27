"""Deterministic, grounded answers available without an AI model.

These answers are also used as a transparent fallback when OpenRouter is not
configured or a request fails. They only read facts from the shopping context.
"""

from __future__ import annotations

import re
from typing import Any

from ..analytics import format_inr


QUICK_PROMPTS = (
    "Is this a good deal?",
    "Should I buy now or wait?",
    "Explain the price history.",
    "Find the best available offer.",
    "Help me save money.",
    "Compare products.",
)


def _money(value: Any) -> str:
    try:
        return format_inr(float(value))
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any, digits: int = 1, signed: bool = True) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if signed:
        return f"{number:+.{digits}f}%"
    return f"{number:.{digits}f}%"


def _confidence_text(confidence: str | None) -> str:
    return {
        "high": "relatively consistent recent trend",
        "medium": "moderate confidence",
        "low": "low confidence",
    }.get(str(confidence or "").lower(), "uncertain")


def _product(context: dict[str, Any]) -> dict[str, Any] | None:
    if context.get("selected_product"):
        return context["selected_product"]
    mentioned = context.get("mentioned_products_from_question") or []
    return mentioned[0] if mentioned else None


def _detailed_products(context: dict[str, Any]) -> list[dict[str, Any]]:
    products = []
    if context.get("selected_product"):
        products.append(context["selected_product"])
    products.extend(context.get("mentioned_products_from_question") or [])
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in products:
        if product["name"] not in seen:
            seen.add(product["name"])
            unique.append(product)
    return unique


def _forecast_sentence(product: dict[str, Any]) -> str:
    forecast = product.get("forecast") or {}
    if not forecast.get("available"):
        return (
            "A forecast is not available because there are not enough recorded "
            "observations. I can still use the recorded price history."
        )
    estimated = _money(forecast.get("estimated_price_7d"))
    low = _money(forecast.get("uncertainty_range_7d", [None, None])[0])
    high = _money(forecast.get("uncertainty_range_7d", [None, None])[1])
    direction = forecast.get("direction", "stable")
    change = _pct(forecast.get("predicted_change_pct"))
    return (
        f"The 7-day trend estimate is **{estimated}** ({change}) with a range of "
        f"**{low}–{high}** and {_confidence_text(forecast.get('confidence'))}. "
        "This is an estimate, not a guarantee."
    )


def _provenance_sentence(product: dict[str, Any]) -> str:
    if product.get("data_origin") == "live":
        status = str(product.get("live_status") or "recorded live quote")
        checked = str(product.get("live_checked_at") or "").replace("T", " ")[:16]
        checked_text = f" Last checked: {checked}." if checked else ""
        warning = (
            " Treat it as stale and refresh before relying on it."
            if "stale" in status.lower() or "failed" in status.lower()
            else " It can change at any time."
        )
        return (
            f"This is a live marketplace quote recorded by the app ({status})."
            f"{checked_text}{warning} It is not a guaranteed current price."
        )
    return (
        "This is demo catalog data, not a live marketplace price. "
        "Use it to explore the calculations, not as a buying quote."
    )


def _price_position_sentence(product: dict[str, Any]) -> str:
    facts = product["recorded_facts"]
    current = float(product["current_price"])
    minimum = facts.get("minimum_price")
    average = product.get("average_recorded_price")
    parts = []
    if minimum is not None:
        if current <= float(minimum) * 1.005:
            parts.append(f"at its lowest recorded price ({_money(minimum)})")
        else:
            parts.append(
                f"{_pct(facts.get('current_vs_minimum_pct'), signed=False)} "
                f"above its lowest recorded price ({_money(minimum)})"
            )
    if average is not None:
        difference = (current - float(average)) / float(average) * 100
        if difference < -0.5:
            parts.append(f"about {abs(difference):.1f}% below the recorded average")
        elif difference > 0.5:
            parts.append(f"about {difference:.1f}% above the recorded average")
        else:
            parts.append("in line with the recorded average")
    return "The current price is " + " and ".join(parts) + "." if parts else ""


def _watchlist_sentence(product: dict[str, Any]) -> str:
    watchlist = product.get("watchlist")
    if not watchlist:
        target = (product.get("suggested_target") or {}).get("target_price")
        return (
            f"No target price is set. A data-anchored watch level would be "
            f"**{_money(target)}**; you can set it on the product panel or by "
            "asking me to set a target."
        )
    target = watchlist["target_price"]
    if watchlist.get("reached"):
        return (
            f"Your target of **{_money(target)}** has been reached "
            f"(current price {_money(product['current_price'])})."
        )
    return (
        f"Your target is **{_money(target)}**, which is "
        f"**{_money(watchlist.get('gap_to_target'))} below** the current price."
    )


def _deal_answer(product: dict[str, Any]) -> str:
    deal = product["deal_analysis"]
    components = deal.get("component_scores", {})
    offers = product.get("seller_offers") or []
    best = next((offer for offer in offers if offer.get("best_available")), None)
    offer_line = (
        f"Best recorded offer: **{best['seller']} at {_money(best['effective_total'])}** "
        f"including recorded coupon and delivery."
        if best
        else "No in-stock seller offer is recorded."
    )
    return (
        f"### {product.get('name')}\n"
        f"**Deal score: {deal.get('score')}/100 — {deal.get('label')}**\n\n"
        f"**Current recorded price: {_money(product.get('current_price'))}**\n\n"
        f"{_price_position_sentence(product)}\n\n"
        f"- List price: {_money(product.get('list_price'))} "
        f"(recorded discount {_pct(product.get('discount_pct'), signed=False)})\n"
        f"- 30-day change: {_pct(product.get('trend_30d_pct'))} "
        f"({product.get('trend', 'stable')} trend)\n"
        f"- {offer_line}\n"
        f"- {_watchlist_sentence(product)}\n\n"
        f"**Why the score landed there:** price position "
        f"{components.get('price_position', '—')}/100, discount "
        f"{components.get('discount', '—')}/100, recent trend "
        f"{components.get('trend', '—')}/100, and seller offer "
        f"{components.get('offer', '—')}/100.\n\n"
        f"**Simple read:** {deal.get('summary')}"
        f"{' This is a strong recorded deal.' if deal.get('score', 0) >= 78 else ' It is not a clear all-time bargain.' if deal.get('score', 0) < 62 else ''}\n\n"
        "**Recorded facts** are the current price, history statistics, and seller "
        "offers. The **deal score** is this app's calculation, and the forecast is "
        "an estimate — neither guarantees a future price.\n\n"
        f"{_provenance_sentence(product)}"
    )


def _timing_answer(product: dict[str, Any]) -> str:
    deal = product["deal_analysis"]
    forecast = product.get("forecast") or {}
    score = int(deal.get("score", 0))
    direction = forecast.get("direction", "unknown") if forecast.get("available") else "unknown"

    if score >= 78:
        verdict = (
            "The recorded price is already in a strong zone for this product. "
            "If you need it now, buying at this level is reasonable."
        )
    elif direction == "falling" and forecast.get("predicted_change_pct", 0) <= -1:
        verdict = (
            "The trend estimate points lower over the next week, so waiting has "
            "some support. The forecast is uncertain, though, and a sudden seller "
            "change is always possible."
        )
    elif score >= 62:
        verdict = (
            "This is a good-but-not-exceptional recorded deal. Buying is reasonable "
            "if you need the product; otherwise a target watch gives you discipline."
        )
    elif direction == "rising":
        verdict = (
            "The recent trend is rising and the deal score is not strong. If you "
            "can wait, watch for a pullback before buying."
        )
    else:
        verdict = (
            "The recorded price is not especially attractive versus this product's "
            "own history. I would watch for a lower level before buying."
        )

    return (
        f"### Buy now or wait?\n"
        f"**Deal score:** {score}/100 — {deal.get('label')}  \n"
        f"**Current price:** {_money(product['current_price'])}  \n"
        f"**Recent trend:** {product.get('trend', 'stable')} "
        f"({_pct(product.get('trend_30d_pct'))} over 30 days)\n\n"
        f"{_forecast_sentence(product)}\n\n"
        f"**What I would do:** {verdict}\n\n"
        f"{_watchlist_sentence(product)}\n\n"
        "I cannot guarantee that the price will rise or fall. This is a decision "
        "framework based on recorded data, not financial advice.\n\n"
        f"{_provenance_sentence(product)}"
    )


def _history_answer(product: dict[str, Any]) -> str:
    facts = product["recorded_facts"]
    observations = product.get("recent_observations") or []
    recent_lines = "\n".join(
        f"| {row['date']} | {_money(row['price'])} |" for row in observations[-5:]
    )
    forecast_line = _forecast_sentence(product)
    return (
        f"### Recorded price history for {product['name']}\n"
        f"There are **{facts.get('observations', 0)} observations** from "
        f"{facts.get('first_observation')} to {facts.get('last_observation')}.\n\n"
        f"- Current: **{_money(product['current_price'])}**\n"
        f"- Average: {_money(product.get('average_recorded_price'))}\n"
        f"- Lowest: {_money(facts.get('minimum_price'))} "
        f"(recorded on {facts.get('minimum_date')})\n"
        f"- Highest: {_money(facts.get('maximum_price'))} "
        f"(recorded on {facts.get('maximum_date')})\n"
        f"- 30-day change: {_pct(product.get('trend_30d_pct'))}\n"
        f"- Recent trend: {product.get('trend', 'stable')} "
        f"({_pct(product.get('trend_weekly_pct'))} per week)\n\n"
        f"The latest recorded observations:\n\n"
        "| Date | Price |\n|---|---|\n"
        f"{recent_lines}\n\n"
        f"{forecast_line}\n\n"
        "The chart on the product page shows the full series, including the "
        f"forecast band.\n\n{_provenance_sentence(product)}"
    )


def _offer_answer(product: dict[str, Any]) -> str:
    offers = product.get("seller_offers") or []
    if not offers:
        return (
            f"No seller offers are recorded for **{product['name']}**. "
            "I won't invent a seller or coupon. Add a live product page from "
            "**Live quotes** and ask again."
        )

    live_offers = [offer for offer in offers if offer.get("is_live")]
    if live_offers:
        rows = []
        for offer in offers:
            mrp = offer.get("mrp")
            mrp_text = (
                _money(mrp)
                if mrp is not None and float(mrp) > float(offer["listed_price"])
                else "—"
            )
            stock = "Stale" if offer.get("stale") else (
                "In stock" if offer.get("in_stock") else "Out of stock"
            )
            best = " ✅" if offer.get("best_available") else ""
            rows.append(
                f"| {offer.get('retailer') or offer['seller']}{best} | "
                f"{_money(offer['listed_price'])} | {mrp_text} | "
                f"{offer.get('availability') or 'Not confirmed'} | {stock} |"
            )
        best = next((offer for offer in offers if offer.get("best_available")), None)
        conclusion = (
            f"### Best live quote\n"
            f"**{best.get('retailer') or best['seller']} — "
            f"{_money(best['listed_price'])}.** This is the lowest in-stock live "
            "quote recorded across the attached sources.\n\n"
            if best
            else "### No in-stock live quote\n"
            "All attached sources currently show out of stock. I won't invent one.\n\n"
        )
        return (
            f"{conclusion}"
            "| Retailer | Listed | MRP | Availability | Status |\n"
            "|---|---:|---:|---|---|\n"
            + "\n".join(rows)
            + "\n\nLive quotes record only the listed price, retailer, detected MRP, "
            "and availability. Coupons and delivery fees are not inferred; confirm "
            "them on the retailer page. A stale quote is the last successful reading, "
            "not a fresh check.\n\n"
            f"{_provenance_sentence(product)}"
        )

    rows = []
    for offer in offers:
        coupon = offer.get("coupon_code") or "—"
        stock = "In stock" if offer.get("in_stock") else "Out of stock"
        best = " ✅" if offer.get("best_available") else ""
        rows.append(
            f"| {offer['seller']}{best} | {_money(offer['listed_price'])} | "
            f"{coupon} | {_money(offer.get('delivery_fee'))} | "
            f"**{_money(offer['effective_total'])}** | {stock} |"
        )

    best = next((offer for offer in offers if offer.get("best_available")), None)
    if best:
        savings = float(product["current_price"]) - float(best["effective_total"])
        comparison = (
            f"It is **{_money(savings)} cheaper** than the recorded current price."
            if savings > 0
            else "It is not cheaper than the recorded current price."
        )
        conclusion = (
            f"### Best available offer\n"
            f"**{best['seller']} — {_money(best['effective_total'])} total.** "
            f"{comparison}\n\n"
        )
    else:
        conclusion = (
            "### No in-stock offer\n"
            "All recorded sellers are currently out of stock. I won't invent one.\n\n"
        )

    return (
        f"{conclusion}"
        "| Seller | Listed | Coupon | Delivery | Effective total | Status |\n"
        "|---|---:|---|---:|---:|---|\n"
        + "\n".join(rows)
        + "\n\nEffective total = listed price minus the recorded coupon plus delivery. "
        "Coupons are recorded app data; confirm them at checkout. If you want, I can "
        "compare this offer with a target price.\n\n"
        f"{_provenance_sentence(product)}"
    )


def _extract_budget(message: str) -> float | None:
    lowered = message.lower()
    if not any(word in lowered for word in ("under", "below", "within", "budget")):
        return None
    match = re.search(
        r"(?:under|below|within|budget(?:\s+of|\s+is)?)[^\d₹]{0,15}[₹rs.\s]*([\d,]+(?:\.\d{1,2})?)",
        lowered,
    )
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _save_answer(message: str, context: dict[str, Any]) -> str:
    product = _product(context)
    budget = _extract_budget(message)

    if budget is not None and not product:
        catalog = context.get("catalog_overview") or []
        options = [
            item for item in catalog if float(item["current_price"]) <= budget
        ]
        options.sort(key=lambda item: -int(item["deal_score"]))
        if not options:
            return (
                f"No catalog products currently record a price at or below "
                f"**{_money(budget)}**. The lowest recorded price is "
                f"{_money(min((item['current_price'] for item in catalog), default=0))}."
            )
        lines = "\n".join(
            f"- **{item['name']}** — {_money(item['current_price'])}, "
            f"deal score {item['deal_score']}/100 ({item['deal_label']})"
            for item in options[:4]
        )
        return (
            f"### Options at or below {_money(budget)}\n{lines}\n\n"
            "These are ranked by this app's deal score, not just by the lowest "
            "price. Tell me which one you want to inspect, or ask which has the "
            "best recorded offer."
        )

    if not product:
        return (
            "### Let's make the saving concrete\n"
            "To suggest a realistic target, tell me:\n\n"
            "1. Which product you are considering, and\n"
            "2. Your budget or the price you would be happy to pay.\n\n"
            "You can also open a product from **Products**; I will then use its "
            "recorded price history automatically."
        )

    suggested = product.get("suggested_target") or {}
    forecast = product.get("forecast") or {}
    offer = next(
        (item for item in (product.get("seller_offers") or []) if item.get("best_available")),
        None,
    )
    tips = []
    if suggested.get("target_price"):
        tips.append(
            f"Set a target at **{_money(suggested['target_price'])}** — "
            f"{suggested.get('rationale', 'anchored to recorded lower prices.')}"
        )
    if offer:
        tips.append(
            f"Use **{offer['seller']}'s** recorded offer at "
            f"**{_money(offer['effective_total'])} total** rather than comparing "
            "listed prices alone; delivery and coupons change the ranking."
        )
    if forecast.get("available"):
        tips.append(
            f"The 7-day estimate is {_money(forecast.get('estimated_price_7d'))} "
            f"with a range of {_money(forecast.get('uncertainty_range_7d', [None, None])[0])}–"
            f"{_money(forecast.get('uncertainty_range_7d', [None, None])[1])}. "
            "Treat it as a planning range, not a promise."
        )
    tips.append(
        "If you do not need it immediately, let the target watchlist do the waiting "
        "instead of checking prices every day."
    )

    return (
        f"### Saving plan for {product['name']}\n"
        f"Current recorded price: **{_money(product['current_price'])}**  \n"
        f"Deal score: **{product['deal_score']}/100 — {product['deal_label']}**\n\n"
        + "\n".join(f"{index}. {tip}" for index, tip in enumerate(tips, start=1))
        + "\n\nYou can say **“set target at ₹22,000”** while this product is selected, "
        "or use the Watch this price form on its page."
    )


def _comparison_row(product: dict[str, Any]) -> str:
    forecast = product.get("forecast") or {}
    estimate = (
        _money(forecast.get("estimated_price_7d"))
        if forecast.get("available")
        else "—"
    )
    offers = product.get("seller_offers") or []
    best = next((offer for offer in offers if offer.get("best_available")), None)
    return (
        f"| **{product['name']}** | {_money(product['current_price'])} | "
        f"{_money(product.get('average_recorded_price'))} | "
        f"{_money(product.get('minimum_recorded_price'))} | "
        f"{_pct(product.get('discount_pct'), signed=False)} | "
        f"{product['deal_score']}/100 | {estimate} | "
        f"{_money(best['effective_total']) if best else '—'} |"
    )


def _compare_answer(context: dict[str, Any]) -> str:
    products = _detailed_products(context)
    if len(products) < 2:
        catalog = context.get("catalog_overview") or []
        suggestions = ", ".join(f"**{item['name']}**" for item in catalog[:6])
        if not products:
            return (
                "### Let's compare two products\n"
                "I can compare any products in the catalog. Which two would you "
                f"like? For example: {suggestions}."
            )
        return (
            f"I have **{products[0]['name']}** in context. Which second product "
            f"should I compare it with? Some options: {suggestions}."
        )

    first, second = products[0], products[1]
    rows = "\n".join(_comparison_row(item) for item in (first, second))
    score_gap = int(first["deal_score"]) - int(second["deal_score"])
    if score_gap > 4:
        read = (
            f"**{first['name']}** has the stronger deal score against its own "
            "price history. That does not automatically make it the better product; "
            "compare the features you need too."
        )
    elif score_gap < -4:
        read = (
            f"**{second['name']}** has the stronger deal score against its own "
            "price history. That does not automatically make it the better product; "
            "compare the features you need too."
        )
    else:
        read = (
            "The deal scores are close, so the decision is more about features, "
            "seller reliability, and which price is easier to justify for you."
        )

    return (
        "### Side-by-side comparison\n"
        "| Product | Current | Recorded avg | Recorded low | Discount | Deal score | 7-day estimate | Best offer |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
        f"{rows}\n\n"
        f"{read}\n\n"
        "**Recorded facts:** current, average, low, discount, and offers. "
        "**Estimate:** the 7-day trend value. Different products have different "
        "value, so a lower price is not automatically a better deal. Check the "
        "live-or-demo label before treating a quote as current."
    )


def _target_answer(product: dict[str, Any]) -> str:
    watchlist = product.get("watchlist")
    suggested = product.get("suggested_target") or {}
    current = _money(product["current_price"])
    if watchlist:
        state = (
            "✅ **Target reached.** The current recorded price is at or below your target."
            if watchlist.get("reached")
            else f"⏳ Not reached yet — you need another "
            f"**{_money(watchlist.get('gap_to_target'))}** drop."
        )
        return (
            f"### Target-price watch for {product['name']}\n"
            f"Current price: **{current}**  \n"
            f"Your target: **{_money(watchlist['target_price'])}**  \n"
            f"{state}\n\n"
            "The watchlist compares the latest recorded price with your target. It "
            f"does not guarantee that price will arrive. A data-anchored suggestion "
            f"is **{_money(suggested.get('target_price'))}** "
            f"({suggested.get('rationale', 'based on recorded history')}).\n\n"
            "To change it, say **“set target at ₹22,000”**, or use the form on the "
            "product page. To stop watching, say **“remove my target”**.\n\n"
            f"{_provenance_sentence(product)}"
        )

    return (
        f"### Target-price watch for {product['name']}\n"
        f"Current price: **{current}**  \n"
        f"A suggested target is **{_money(suggested.get('target_price'))}** — "
        f"{suggested.get('rationale', 'anchored to recorded lower prices.')}\n\n"
        "The app will mark the target as reached when the newest recorded price is "
        "at or below it. This is a watch level, not a promised future price.\n\n"
        "You can say **“set target at ₹22,000”** while this product is selected, or "
        "use the form on the product page.\n\n"
        f"{_provenance_sentence(product)}"
    )


def _navigate_answer(message: str) -> str:
    lowered = message.lower()
    if "target" in lowered or "watch" in lowered or "alert" in lowered:
        detail = (
            "Open **Products → a product → Watch this price**, enter a target, and "
            "press Set target. The **Watchlist** page shows all targets and whether "
            "they are met."
        )
    elif "history" in lowered or "chart" in lowered:
        detail = (
            "Open a product from **Products**. Its recorded price chart, 7-day "
            "forecast band, deal-score breakdown, and seller offers appear on the "
            "product detail page."
        )
    elif "score" in lowered or "deal" in lowered:
        detail = (
            "The deal score is on every product card and detail page. Open "
            "**How it works** in the sidebar for the four components and weights."
        )
    elif "ai" in lowered or "copilot" in lowered or "chat" in lowered:
        detail = (
            "Use the **✦ Copilot** button at the bottom-right. Product context is "
            "attached automatically when a product is open, and quick prompts are "
            "available in an empty chat."
        )
    else:
        detail = (
            "Use the sidebar to move between **Dashboard**, **Deals**, **Products**, "
            "**Compare**, **Live quotes**, **Watchlist**, **Alerts**, **Purchases**, "
            "**Insights**, and **How it works**. Open a product to see its full "
            "history, offers, target, and purchase record. The copilot follows you "
            "across pages."
        )
    return (
        "### Finding your way around\n"
        f"{detail}\n\n"
        "Useful shortcuts:\n"
        "- **Deals** — filter by budget, category, and deal score\n"
        "- **Products** — search, filter, and open a product\n"
        "- **Compare** — put two or three products side by side\n"
        "- **Live quotes** — import a product page and refresh quotes\n"
        "- **Watchlist** — review target prices\n"
        "- **Alerts** — review saved target, price, stock, and quote signals\n"
        "- **Purchases** — record what you paid and compare it with the latest quote\n"
        "- **✦ Copilot** — ask about the product currently open\n"
        "- **How it works** — understand scores, forecasts, and data labels"
    )


def _general_answer(context: dict[str, Any]) -> str:
    product = _product(context)
    top = context.get("top_deals_by_score") or []
    top_lines = "\n".join(
        f"- **{item['name']}** — {_money(item['current_price'])}, "
        f"deal score {item['deal_score']}/100 ({item['deal_label']})"
        for item in top[:3]
    )
    if product:
        return (
            f"I'm looking at **{product['name']}** at "
            f"**{_money(product['current_price'])}**. Its deal score is "
            f"**{product['deal_score']}/100 — {product['deal_label']}**.\n\n"
            f"{_forecast_sentence(product)}\n\n"
            "You can ask me whether it is a good deal, whether to wait, to explain "
            "the history, compare sellers, or suggest a target price. If you want "
            "another product, tell me its name or clear the product context.\n\n"
            f"{_provenance_sentence(product)}"
        )

    return (
        "### Your shopping snapshot\n"
        f"I can see {len(context.get('catalog_overview') or [])} products with "
        "recorded price histories, mixing live-imported quotes and clearly labelled "
        "demo rows. The strongest deal scores right now:\n\n"
        f"{top_lines or 'No product data is available.'}\n\n"
        "Tell me what you are shopping for, your budget, or the product you want to "
        "inspect. For example: **“What is the best deal under ₹20,000?”** or "
        "**“Compare Aurora X5 and EchoBuds Pro.”**"
    )


def detect_intent(message: str) -> str:
    text = message.lower().strip()
    if re.search(r"\b(compare|versus|vs\.?|difference between)\b", text):
        return "compare"
    if re.search(r"\b(seller|offer|coupon|cheapest|discount code)\b", text):
        return "offer"
    if re.search(r"\b(history|trend|chart|past price|price movement)\b", text):
        return "history"
    if re.search(r"\b(target|watch|alert|notify)\b", text):
        return "target"
    if _extract_budget(message) is not None:
        return "save"
    if re.search(r"\b(save|saving|budget|cheaper|money)\b", text):
        return "save"
    if re.search(r"\b(buy now|wait|should i buy|when to buy|timing)\b", text):
        return "timing"
    if re.search(r"\b(good deal|worth it|worth buying|overpriced)\b", text):
        return "deal"
    if re.search(r"\b(where|how do i|how to|navigate|page|feature|find)\b", text):
        return "navigate"
    if re.search(r"\b(hello|hi|hey|thanks|thank you)\b", text):
        return "social"
    if re.search(r"\b(what can you do|help me|capabilit|who are you)\b", text):
        return "capabilities"
    return "general"


def answer_locally(message: str, context: dict[str, Any]) -> str:
    """Return a helpful answer built only from the supplied shopping context."""

    message = message.strip()
    intent = detect_intent(message)
    product = _product(context)

    if intent == "social":
        return (
            "Hi! I'm your shopping copilot. I can explain a product's recorded "
            "price history, interpret its deal score, compare sellers, and suggest "
            "a target price. What are you shopping for?"
        )
    if intent == "capabilities":
        return (
            "### What I can do\n"
            "- Interpret the current price, discount, and **deal score**\n"
            "- Explain **recorded price history** and recent trend\n"
            "- Compare **seller offers**, coupons, and delivery costs\n"
            "- Discuss the **7-day forecast** and its uncertainty\n"
            "- Suggest and set a **target-price watch**\n"
            "- Help you navigate the app\n\n"
            "I answer from this app's recorded data, with live and demo records "
            "clearly labelled. When smart explanations are enabled, the AI explains "
            "those facts; it does not invent prices or sellers."
        )
    if intent == "navigate":
        return _navigate_answer(message)
    if intent == "compare":
        return _compare_answer(context)
    if intent == "deal" and product:
        return _deal_answer(product)
    if intent == "timing" and product:
        return _timing_answer(product)
    if intent == "history" and product:
        return _history_answer(product)
    if intent == "offer" and product:
        return _offer_answer(product)
    if intent == "save":
        return _save_answer(message, context)
    if intent == "target" and product:
        return _target_answer(product)
    if product and intent in {"deal", "timing", "history", "offer", "target"}:
        return _general_answer(context)

    if intent in {"good deal", "deal", "timing", "history", "offer", "target"}:
        return (
            "### Which product should I look at?\n"
            "No product is currently selected, so I do not want to guess. Open a "
            "product from **Products**, or tell me its name. Then I can use its "
            "recorded prices, deal score, forecast, and seller offers.\n\n"
            f"{_general_answer(context)}"
        )
    return _general_answer(context)
