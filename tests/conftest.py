"""Shared pytest fixtures for deterministic, offline tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from smartdeal.config import Settings
from smartdeal.database import Database


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """Settings that keep all tests local and offline."""

    return Settings(
        db_path=tmp_path / "shopping.db",
        openrouter_api_key=None,
        openrouter_model="openrouter/auto",
        openrouter_site_url="http://localhost:8501",
        openrouter_app_name="AI Smart Deal Predictor (test)",
        openrouter_api_url="https://openrouter.invalid/api/v1/chat/completions",
        ai_timeout_seconds=5,
    )


@pytest.fixture()
def db(settings: Settings) -> Database:
    database = Database(settings.db_path)
    database.initialize()
    return database


@pytest.fixture()
def ai_settings(settings: Settings) -> Settings:
    return replace(settings, openrouter_api_key="sk-test-secret-key")
