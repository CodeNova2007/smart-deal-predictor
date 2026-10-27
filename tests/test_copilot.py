"""Copilot behavior: grounding, local fallback, AI failures, and actions."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from smartdeal.config import Settings
from smartdeal.copilot import (
    QUICK_PROMPTS,
    CopilotAnswer,
    ModelResult,
    OpenRouterClient,
    ask_copilot,
)
from smartdeal.copilot.context import build_shopping_context
from smartdeal.database import Database


class StubClient:
    def __init__(self, result: ModelResult):
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def complete(self, prompt: str, messages: list[dict[str, str]], **kwargs: Any):
        self.calls.append({"prompt": prompt, "messages": messages, **kwargs})
        return self.result


class ExplodingClient:
    def complete(self, *args: Any, **kwargs: Any):
        raise AssertionError("The AI client must not be called without an API key.")


def _product_id(db: Database, name: str) -> int:
    product = next(item for item in db.list_products() if item["name"] == name)
    return int(product["id"])


def test_quick_prompts_are_exact_and_in_order():
    assert list(QUICK_PROMPTS) == [
        "Is this a good deal?",
        "Should I buy now or wait?",
        "Explain the price history.",
        "Find the best available offer.",
        "Help me save money.",
        "Compare products.",
    ]


def test_every_quick_prompt_works_locally_without_an_api_key(
    db: Database, settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    for prompt in QUICK_PROMPTS:
        answer = ask_copilot(
            db, prompt, selected_product_id=product_id, settings=settings
        )
        assert isinstance(answer, CopilotAnswer)
        assert answer.source == "local"
        assert answer.text.strip()
        assert answer.error_kind == "not_configured"
        assert "No model was called" in answer.notice
        assert answer.used_ai is False


def test_local_deal_answer_uses_recorded_values(db: Database, settings: Settings):
    product_id = _product_id(db, "EchoBuds Pro")
    answer = ask_copilot(
        db, "Is this a good deal?", selected_product_id=product_id, settings=settings
    )
    assert "EchoBuds Pro" in answer.text
    assert "₹8,999" in answer.text
    assert "74/100" in answer.text
    assert "TechNest" in answer.text
    assert "Recorded facts" in answer.text
    assert answer.data_used["selected_product"] == "EchoBuds Pro"
    assert answer.data_used["catalog_products"] == 40
    assert answer.data_used["recorded_observations"] == 120
    assert answer.data_used["seller_offers"] == 4


def test_missing_product_context_asks_for_clarification(
    db: Database, settings: Settings
):
    answer = ask_copilot(db, "Is this a good deal?", settings=settings)
    assert answer.source == "local"
    assert "Which product should I look at?" in answer.text
    assert "No product is currently selected" in answer.text


def test_compare_without_two_products_asks_for_the_second(
    db: Database, settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    answer = ask_copilot(
        db, "Compare products.", selected_product_id=product_id, settings=settings
    )
    assert "Which second product" in answer.text
    assert "EchoBuds Pro" in answer.text


def test_compare_two_named_products_builds_a_grounded_table(
    db: Database, settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    answer = ask_copilot(
        db,
        "Compare EchoBuds Pro and Aurora X5 ANC Headphones.",
        selected_product_id=product_id,
        settings=settings,
    )
    assert "Side-by-side comparison" in answer.text
    assert "EchoBuds Pro" in answer.text
    assert "Aurora X5 ANC Headphones" in answer.text
    assert "Recorded facts" in answer.text


def test_budget_question_uses_catalog_prices(db: Database, settings: Settings):
    answer = ask_copilot(
        db, "What is the best deal under ₹20,000?", settings=settings
    )
    assert "Options at or below ₹20,000" in answer.text
    assert "EchoBuds Pro" in answer.text
    assert "₹8,999" in answer.text


def test_product_without_history_or_offers_is_handled_honestly(
    db: Database, settings: Settings
):
    with db.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO products
                (name, brand, category, description, emoji, current_price,
                 list_price, currency)
            VALUES ('Empty Data Product', 'Test', 'Other', 'No records yet.',
                    '🧪', 1000, 1200, 'INR')
            """
        )
        product_id = int(cursor.lastrowid)
        connection.commit()

    offer_answer = ask_copilot(
        db,
        "Find the best available offer.",
        selected_product_id=product_id,
        settings=settings,
    )
    assert "No seller offers are recorded" in offer_answer.text
    assert "won't invent" in offer_answer.text

    history_answer = ask_copilot(
        db,
        "Explain the price history.",
        selected_product_id=product_id,
        settings=settings,
    )
    assert "0 observations" in history_answer.text
    assert "A forecast is not available" in history_answer.text


def test_watchlist_action_sets_and_removes_a_target(
    db: Database, settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    answer = ask_copilot(
        db,
        "set target at ₹8,500",
        selected_product_id=product_id,
        settings=settings,
    )
    assert answer.source == "action"
    assert "Target price set" in answer.text
    assert "₹8,500" in answer.text
    assert db.get_watchlist_item(product_id)["target_price"] == 8_500

    removed = ask_copilot(
        db, "remove my target", selected_product_id=product_id, settings=settings
    )
    assert removed.source == "action"
    assert "removed the target price" in removed.text
    assert db.get_watchlist_item(product_id) is None


def test_watchlist_action_requires_a_product(db: Database, settings: Settings):
    before = len(db.get_watchlist_details())
    answer = ask_copilot(db, "set target at ₹8,500", settings=settings)
    assert answer.source == "action"
    assert "Which product should I watch?" in answer.text
    assert "was not changed" in answer.notice
    assert len(db.get_watchlist_details()) == before


def test_watchlist_action_can_use_a_product_named_in_the_question(
    db: Database, settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    answer = ask_copilot(
        db, "set target at ₹8,500 for EchoBuds Pro", settings=settings
    )
    assert answer.source == "action"
    assert "Target price set" in answer.text
    assert db.get_watchlist_item(product_id)["target_price"] == 8_500
    db.remove_watchlist(product_id)


def test_ai_success_is_labelled_and_grounded(
    db: Database, ai_settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    client = StubClient(
        ModelResult(ok=True, text="AI explanation of the recorded price.", model="test/model")
    )
    answer = ask_copilot(
        db,
        "Is this a good deal?",
        selected_product_id=product_id,
        settings=ai_settings,
        client=client,
    )
    assert answer.source == "ai"
    assert answer.model == "test/model"
    assert answer.used_ai is True
    assert answer.notice == ""
    assert answer.text == "AI explanation of the recorded price."
    assert client.calls
    prompt = client.calls[0]["prompt"]
    assert "SHOPPING_DATA" in prompt
    assert "EchoBuds Pro" in prompt
    assert "sk-test-secret-key" not in prompt
    assert client.calls[0]["messages"][-1] == {
        "role": "user",
        "content": "Is this a good deal?",
    }


def test_ai_failure_falls_back_to_local_analysis_with_clear_notice(
    db: Database, ai_settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    client = StubClient(
        ModelResult(
            ok=False,
            error_kind="rate_limit",
            error_message="OpenRouter is rate-limiting requests right now.",
        )
    )
    answer = ask_copilot(
        db,
        "Should I buy now or wait?",
        selected_product_id=product_id,
        settings=ai_settings,
        client=client,
    )
    assert answer.source == "fallback"
    assert answer.used_ai is False
    assert "rate-limiting" in answer.notice
    assert "not an AI-generated response" in answer.notice
    assert "Buy now or wait?" in answer.text


def test_ai_answer_redacts_the_api_key(db: Database, ai_settings: Settings):
    product_id = _product_id(db, "EchoBuds Pro")
    client = StubClient(
        ModelResult(
            ok=True,
            text="The key sk-test-secret-key must never appear.",
            model="test/model",
        )
    )
    answer = ask_copilot(
        db,
        "Is this a good deal?",
        selected_product_id=product_id,
        settings=ai_settings,
        client=client,
    )
    assert "sk-test-secret-key" not in answer.text
    assert "[redacted]" in answer.text


def test_no_key_never_calls_the_ai_client(db: Database, settings: Settings):
    product_id = _product_id(db, "EchoBuds Pro")
    answer = ask_copilot(
        db,
        "Is this a good deal?",
        selected_product_id=product_id,
        settings=settings,
        client=ExplodingClient(),
    )
    assert answer.source == "local"
    assert answer.error_kind == "not_configured"


def test_history_is_trimmed_and_kept_out_of_the_system_prompt(
    db: Database, ai_settings: Settings
):
    product_id = _product_id(db, "EchoBuds Pro")
    client = StubClient(ModelResult(ok=True, text="ok", model="test/model"))
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": f"message {index}"}
        for index in range(14)
    ]
    ask_copilot(
        db,
        "Is this a good deal?",
        history=history,
        selected_product_id=product_id,
        settings=ai_settings,
        client=client,
    )
    messages = client.calls[0]["messages"]
    assert len(messages) == 9  # last 8 history messages + the new question
    assert messages[-1]["content"] == "Is this a good deal?"
    assert messages[0]["content"] == "message 6"
    assert "message 6" not in client.calls[0]["prompt"]


def test_openrouter_client_is_not_called_without_a_key(settings: Settings):
    client = OpenRouterClient(settings, post=ExplodingClient().complete)
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is False
    assert result.error_kind == "not_configured"
