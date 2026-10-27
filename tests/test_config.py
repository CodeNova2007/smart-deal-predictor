"""Configuration loading and secret hygiene tests."""

from __future__ import annotations

from pathlib import Path

from smartdeal.config import (
    DEFAULT_MODEL,
    PROJECT_ROOT,
    _clean_key,
    clear_settings_cache,
    load_settings,
)


def test_placeholder_keys_are_treated_as_not_configured():
    for value in (None, "", "   ", "your-openrouter-api-key", "changeme"):
        assert _clean_key(value) is None
    assert _clean_key("sk-or-v1-real") == "sk-or-v1-real"
    assert _clean_key("  sk-or-v1-real  ") == "sk-or-v1-real"


def test_load_settings_defaults_and_timeout_clamping(monkeypatch):
    for name in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_SITE_URL",
        "OPENROUTER_APP_NAME",
        "OPENROUTER_API_URL",
        "SHOPPING_DB_PATH",
        "AI_COPILOT_TIMEOUT",
    ):
        monkeypatch.delenv(name, raising=False)
    clear_settings_cache()

    settings = load_settings()
    assert settings.openrouter_api_key is None
    assert settings.openrouter_model == DEFAULT_MODEL
    assert settings.ai_configured is False
    assert settings.ai_mode_label == "Local analysis"
    assert settings.db_path == PROJECT_ROOT / "data" / "shopping.db"
    assert settings.ai_timeout_seconds == 45

    monkeypatch.setenv("AI_COPILOT_TIMEOUT", "1")
    assert load_settings().ai_timeout_seconds == 5
    monkeypatch.setenv("AI_COPILOT_TIMEOUT", "9999")
    assert load_settings().ai_timeout_seconds == 120
    monkeypatch.setenv("AI_COPILOT_TIMEOUT", "not-a-number")
    assert load_settings().ai_timeout_seconds == 45


def test_load_settings_accepts_a_custom_db_path(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SHOPPING_DB_PATH", str(tmp_path / "custom.db"))
    settings = load_settings()
    assert settings.db_path == tmp_path / "custom.db"
    clear_settings_cache()


def test_ai_mode_label_reflects_key_presence(ai_settings):
    assert ai_settings.ai_configured is True
    assert ai_settings.ai_mode_label == "AI connected"
