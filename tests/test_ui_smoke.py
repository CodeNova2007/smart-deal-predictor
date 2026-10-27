"""Optional Playwright smoke tests for the floating shopping copilot.

The tests are skipped unless a running Streamlit instance is supplied:

    $env:COPILOT_BASE_URL = "http://localhost:8501"
    .\\.venv\\Scripts\\pytest.exe tests/test_ui_smoke.py -q

To exercise the failed-request warning, start a second app instance with a
deliberately failing OpenRouter endpoint and set ``COPILOT_FAILURE_BASE_URL``.
The regular pytest suite remains offline and does not require a browser.
"""

from __future__ import annotations

import os

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_api.sync_playwright

BASE_URL = os.getenv("COPILOT_BASE_URL", "").rstrip("/")
FAILURE_URL = os.getenv("COPILOT_FAILURE_BASE_URL", "").rstrip("/")
BROWSER_CHANNEL = os.getenv("COPILOT_BROWSER_CHANNEL", "msedge")

QUICK_PROMPTS = (
    "Is this a good deal?",
    "Should I buy now or wait?",
    "Explain the price history.",
    "Find the best available offer.",
    "Help me save money.",
    "Compare products.",
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        launched = playwright.chromium.launch(
            channel=BROWSER_CHANNEL,
            headless=True,
        )
        yield launched
        launched.close()


def _new_page(browser, *, width: int = 1440, height: int = 1000, mobile: bool = False):
    page = browser.new_page(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
        is_mobile=mobile,
        has_touch=mobile,
    )
    page.set_default_timeout(30_000)
    return page


def _goto(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.locator(".stApp").wait_for(state="visible")
    page.wait_for_timeout(2_000)


def _open_copilot(page) -> None:
    page.get_by_role("button", name="✦ Copilot").click()
    page.locator(".st-key-copilot_panel").wait_for(state="visible")
    page.wait_for_timeout(900)


def _message_count(page) -> int:
    return page.locator('[data-testid="stChatMessage"]').count()


def _send(page, text: str) -> None:
    textarea = page.locator(".st-key-copilot_composer textarea")
    textarea.wait_for(state="visible")
    before = _message_count(page)
    textarea.fill(text)
    textarea.press("Enter")
    page.wait_for_function(
        "count => document.querySelectorAll("
        "'[data-testid=\"stChatMessage\"]').length >= count",
        arg=before + 2,
        timeout=45_000,
    )
    page.wait_for_timeout(1_200)


@pytest.mark.skipif(not BASE_URL, reason="Set COPILOT_BASE_URL to run browser smoke tests")
def test_panel_open_close_quick_prompts_and_session_history(browser):
    page = _new_page(browser)
    try:
        _goto(page, BASE_URL)
        _open_copilot(page)

        page.get_by_role(
            "heading", name="Your Personal Shopping Copilot", exact=True
        ).wait_for(state="visible")
        for prompt in QUICK_PROMPTS:
            assert page.get_by_role("button", name=prompt, exact=True).is_visible()

        _send(page, "Is this a good deal?")
        history_text = page.locator(".st-key-copilot_history").inner_text()
        assert "Which product should I look at?" in history_text
        count_before_close = _message_count(page)

        page.get_by_role("button", name="×", exact=True).click()
        page.locator(".st-key-copilot_panel").wait_for(state="detached", timeout=15_000)
        assert page.locator(".st-key-copilot_panel").count() == 0
        assert page.get_by_role("button", name="✦ Copilot").is_visible()

        page.get_by_role("button", name="✦ Copilot").click()
        page.locator(".st-key-copilot_panel").wait_for(state="visible")
        page.wait_for_timeout(1_000)
        assert _message_count(page) == count_before_close
        assert page.locator(".st-key-copilot_composer textarea").is_visible()
    finally:
        page.close()


@pytest.mark.skipif(not BASE_URL, reason="Set COPILOT_BASE_URL to run browser smoke tests")
def test_product_context_produces_a_grounded_answer(browser):
    page = _new_page(browser)
    try:
        _goto(page, BASE_URL)
        page.get_by_role("button", name="View full analysis").click()
        page.wait_for_timeout(2_200)
        _open_copilot(page)

        context = page.locator(".sd-copilot-context").inner_text()
        assert "Context" in context
        assert "₹" in context

        _send(page, "Is this a good deal?")
        answer = page.locator(".st-key-copilot_history").inner_text()
        assert "Deal score" in answer
        assert "Current recorded price" in answer
        assert "₹" in answer
        assert "Recorded facts" in answer
    finally:
        page.close()


@pytest.mark.skipif(not BASE_URL, reason="Set COPILOT_BASE_URL to run browser smoke tests")
def test_mobile_panel_fits_viewport_and_keeps_composer_visible(browser):
    page = _new_page(browser, width=390, height=844, mobile=True)
    try:
        _goto(page, BASE_URL)
        _open_copilot(page)
        panel = page.locator(".st-key-copilot_panel")
        box = panel.bounding_box()
        assert box is not None
        assert box["x"] >= 0
        assert box["y"] >= 0
        assert box["x"] + box["width"] <= 390.5
        assert box["y"] + box["height"] <= 844.5
        assert page.locator(".st-key-copilot_composer textarea").is_visible()
        assert page.get_by_role("button", name="Send ↑").is_visible()
        assert page.locator(".st-key-copilot_quick_prompts button").count() == 6
    finally:
        page.close()


@pytest.mark.skipif(
    not FAILURE_URL,
    reason="Set COPILOT_FAILURE_BASE_URL to a running app with a failing AI endpoint",
)
def test_failed_ai_request_shows_a_local_fallback_warning(browser):
    page = _new_page(browser)
    try:
        _goto(page, FAILURE_URL)
        page.get_by_role("button", name="View full analysis").click()
        page.wait_for_timeout(2_200)
        _open_copilot(page)

        textarea = page.locator(".st-key-copilot_composer textarea")
        textarea.fill("Is this a good deal?")
        textarea.press("Enter")

        page.get_by_text("Reading recorded prices", exact=False).first.wait_for(
            state="visible", timeout=15_000
        )
        page.get_by_text("busy right now", exact=False).first.wait_for(
            state="visible", timeout=45_000
        )
        history_text = page.locator(".st-key-copilot_history").inner_text()
        assert "not a model-written response" in history_text
        assert "Built-in analysis" in history_text
        assert "smart explanation unavailable" in history_text
        assert "Deal score" in history_text
    finally:
        page.close()
