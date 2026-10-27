"""OpenRouter client tests with no real network access."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from smartdeal.config import Settings
from smartdeal.copilot.openrouter import OpenRouterClient


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        *,
        headers: dict[str, str] | None = None,
        invalid_json: bool = False,
    ):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}
        self.invalid_json = invalid_json

    def json(self):
        if self.invalid_json:
            raise ValueError("not json")
        return self.payload


def _success_payload(text: str = "Grounded answer") -> dict[str, Any]:
    return {
        "model": "test/model-1",
        "choices": [{"message": {"content": text}}],
    }


def test_missing_key_returns_not_configured_without_a_request(settings: Settings):
    calls = []

    def post(*args: Any, **kwargs: Any):
        calls.append((args, kwargs))
        return FakeResponse(200, _success_payload())

    client = OpenRouterClient(settings, post=post)
    result = client.complete("system", [{"role": "user", "content": "hello"}])
    assert result.ok is False
    assert result.error_kind == "not_configured"
    assert calls == []


def test_successful_completion_sends_auth_header_and_parses_content(
    ai_settings: Settings,
):
    captured: dict[str, Any] = {}

    def post(url: str, **kwargs: Any):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(200, _success_payload("The recorded price is ₹8,999."))

    client = OpenRouterClient(ai_settings, post=post)
    result = client.complete(
        "SYSTEM PROMPT", [{"role": "user", "content": "Is this a good deal?"}]
    )

    assert result.ok is True
    assert result.text == "The recorded price is ₹8,999."
    assert result.model == "test/model-1"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-secret-key"
    assert captured["json"]["model"] == "openrouter/auto"
    assert captured["json"]["messages"][0] == {
        "role": "system",
        "content": "SYSTEM PROMPT",
    }
    assert captured["json"]["messages"][1]["content"] == "Is this a good deal?"
    assert captured["timeout"] == (10, 5)


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "auth"), (403, "auth"), (402, "credits")],
)
def test_auth_and_credit_errors_are_classified(
    ai_settings: Settings, status: int, kind: str
):
    client = OpenRouterClient(
        ai_settings,
        post=lambda *args, **kwargs: FakeResponse(
            status, {"error": {"message": "denied"}}
        ),
    )
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is False
    assert result.error_kind == kind
    assert result.status_code == status
    assert "OPENROUTER_API_KEY" in result.error_message or "credits" in result.error_message


def test_rate_limit_retries_once_then_succeeds(ai_settings: Settings):
    responses = [
        FakeResponse(429, {"error": {"message": "slow down"}}, headers={"Retry-After": "0.25"}),
        FakeResponse(200, _success_payload()),
    ]
    sleeps: list[float] = []
    client = OpenRouterClient(
        ai_settings,
        post=lambda *args, **kwargs: responses.pop(0),
        sleep=sleeps.append,
    )
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is True
    assert sleeps == [0.25]


def test_rate_limit_twice_returns_a_safe_rate_limit_error(ai_settings: Settings):
    sleeps: list[float] = []
    client = OpenRouterClient(
        ai_settings,
        post=lambda *args, **kwargs: FakeResponse(429, {"error": {"message": "slow"}}),
        sleep=sleeps.append,
    )
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is False
    assert result.error_kind == "rate_limit"
    assert "rate-limiting" in result.error_message
    assert sleeps == [1.5]


def test_server_errors_retry_once_then_fail(ai_settings: Settings):
    sleeps: list[float] = []
    client = OpenRouterClient(
        ai_settings,
        post=lambda *args, **kwargs: FakeResponse(503, {"error": {"message": "down"}}),
        sleep=sleeps.append,
    )
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is False
    assert result.error_kind == "provider"
    assert result.status_code == 503
    assert sleeps == [1.0]


def test_timeout_and_network_failures_are_reported(ai_settings: Settings):
    timeout_client = OpenRouterClient(
        ai_settings, post=lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout())
    )
    timeout_result = timeout_client.complete(
        "system", [{"role": "user", "content": "hi"}]
    )
    assert timeout_result.error_kind == "timeout"
    assert "timed out" in timeout_result.error_message

    network_client = OpenRouterClient(
        ai_settings,
        post=lambda *args, **kwargs: (_ for _ in ()).throw(
            requests.ConnectionError("no route")
        ),
    )
    network_result = network_client.complete(
        "system", [{"role": "user", "content": "hi"}]
    )
    assert network_result.error_kind == "network"
    assert "could not be reached" in network_result.error_message


def test_invalid_json_and_missing_choices_are_bad_responses(ai_settings: Settings):
    invalid = OpenRouterClient(
        ai_settings, post=lambda *args, **kwargs: FakeResponse(200, invalid_json=True)
    )
    assert (
        invalid.complete("system", [{"role": "user", "content": "hi"}]).error_kind
        == "bad_response"
    )

    empty = OpenRouterClient(
        ai_settings, post=lambda *args, **kwargs: FakeResponse(200, {"choices": []})
    )
    assert (
        empty.complete("system", [{"role": "user", "content": "hi"}]).error_kind
        == "bad_response"
    )


def test_list_content_parts_are_joined(ai_settings: Settings):
    payload = {
        "model": "test/model-1",
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "Part one."},
                        {"type": "text", "text": "Part two."},
                    ]
                }
            }
        ],
    }
    client = OpenRouterClient(
        ai_settings, post=lambda *args, **kwargs: FakeResponse(200, payload)
    )
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is True
    assert result.text == "Part one. Part two."


def test_error_detail_never_leaks_the_api_key(ai_settings: Settings):
    client = OpenRouterClient(
        ai_settings,
        post=lambda *args, **kwargs: FakeResponse(
            500, {"error": {"message": "bad sk-test-secret-key"}}
        ),
        sleep=lambda seconds: None,
    )
    result = client.complete("system", [{"role": "user", "content": "hi"}])
    assert result.ok is False
    assert "sk-test-secret-key" not in result.error_message
    assert "[redacted]" in result.error_message
