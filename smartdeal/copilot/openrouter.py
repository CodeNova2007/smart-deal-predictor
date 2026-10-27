"""Server-side OpenRouter client with explicit, user-safe failure handling."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from ..config import Settings


@dataclass(frozen=True)
class ModelResult:
    ok: bool
    text: str = ""
    model: str = ""
    error_kind: str = ""
    error_message: str = ""
    status_code: int | None = None
    retry_after_seconds: float | None = None


_ERROR_MESSAGES = {
    "not_configured": (
        "AI is not configured. Add OPENROUTER_API_KEY on the server to enable "
        "AI-written explanations."
    ),
    "auth": (
        "OpenRouter rejected the API credentials (HTTP 401/403). Check that the "
        "server-side OPENROUTER_API_KEY is valid and has access to the selected model."
    ),
    "credits": (
        "The OpenRouter account cannot complete this request (HTTP 402). Check the "
        "account credits or choose a different model."
    ),
    "rate_limit": (
        "OpenRouter is rate-limiting requests right now. Please wait a moment and "
        "try again."
    ),
    "timeout": "The AI request timed out. The local shopping analysis is still available.",
    "network": (
        "The AI service could not be reached. Check the server's network connection "
        "and try again."
    ),
    "provider": (
        "The AI provider returned an error. Try again in a moment or use the local "
        "shopping analysis."
    ),
    "bad_response": (
        "The AI provider returned an unexpected response, so no AI answer was used."
    ),
}


class OpenRouterClient:
    """Small client that never logs or returns the API key."""

    def __init__(
        self,
        settings: Settings,
        *,
        post: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        self.settings = settings
        self._post = post or requests.post
        self._sleep = sleep or time.sleep

    def _sanitize(self, value: str) -> str:
        key = self.settings.openrouter_api_key
        text = (value or "").strip()
        if key and key in text:
            text = text.replace(key, "[redacted]")
        return text[:400]

    def _failure(
        self,
        kind: str,
        *,
        status_code: int | None = None,
        detail: str = "",
        retry_after: float | None = None,
    ) -> ModelResult:
        message = _ERROR_MESSAGES.get(kind, _ERROR_MESSAGES["provider"])
        safe_detail = self._sanitize(detail)
        if safe_detail and kind in {"provider", "bad_response"}:
            message = f"{message} ({safe_detail})"
        return ModelResult(
            ok=False,
            model=self.settings.openrouter_model,
            error_kind=kind,
            error_message=message,
            status_code=status_code,
            retry_after_seconds=retry_after,
        )

    def complete(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 900,
        temperature: float = 0.25,
    ) -> ModelResult:
        if not self.settings.ai_configured:
            return self._failure("not_configured")

        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": 0.9,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.openrouter_site_url,
            "X-Title": self.settings.openrouter_app_name,
        }

        last_error: ModelResult | None = None
        for attempt in range(2):
            try:
                response = self._post(
                    self.settings.openrouter_api_url,
                    headers=headers,
                    json=payload,
                    timeout=(10, self.settings.ai_timeout_seconds),
                )
            except requests.Timeout:
                return self._failure("timeout")
            except requests.RequestException as exc:
                return self._failure("network", detail=str(exc))

            status = int(getattr(response, "status_code", 500))
            if status in (401, 403):
                return self._failure(
                    "auth", status_code=status, detail=self._body_error(response)
                )
            if status == 402:
                return self._failure(
                    "credits", status_code=status, detail=self._body_error(response)
                )
            if status == 429:
                retry_after = self._retry_after(response)
                last_error = self._failure(
                    "rate_limit",
                    status_code=status,
                    retry_after=retry_after,
                    detail=self._body_error(response),
                )
                if attempt == 0:
                    self._sleep(min(retry_after if retry_after is not None else 1.5, 5.0))
                    continue
                return last_error
            if status >= 500:
                last_error = self._failure(
                    "provider",
                    status_code=status,
                    detail=self._body_error(response),
                )
                if attempt == 0:
                    self._sleep(1.0)
                    continue
                return last_error
            if status >= 400:
                return self._failure(
                    "provider",
                    status_code=status,
                    detail=self._body_error(response),
                )

            try:
                data = response.json()
            except (ValueError, json.JSONDecodeError):
                return self._failure("bad_response", status_code=status)

            choices = data.get("choices") if isinstance(data, dict) else None
            if not choices:
                return self._failure(
                    "bad_response",
                    status_code=status,
                    detail=str((data or {}).get("error", {}).get("message", "")),
                )

            content = (choices[0].get("message") or {}).get("content")
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict)
                )
            if not isinstance(content, str) or not content.strip():
                return self._failure("bad_response", status_code=status)

            return ModelResult(
                ok=True,
                text=self._sanitize(content),
                model=str(data.get("model") or self.settings.openrouter_model),
                status_code=status,
            )

        return last_error or self._failure("provider")

    @staticmethod
    def _retry_after(response: Any) -> float | None:
        raw = (getattr(response, "headers", {}) or {}).get("Retry-After")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _body_error(response: Any) -> str:
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError):
            return ""
        if not isinstance(data, dict):
            return ""
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or "")
        return str(error or "")
