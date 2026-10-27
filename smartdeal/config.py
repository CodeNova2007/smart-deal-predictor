"""Application configuration and secure secret loading.

The OpenRouter key is only ever read in the Python process. It is never sent to
the browser, written to the database, or included in prompts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Load once, without overriding variables already supplied by the host.
load_dotenv(ENV_FILE, override=False)

DEFAULT_MODEL = "openrouter/auto"
_PLACEHOLDER_KEYS = {
    "",
    "your-openrouter-api-key",
    "your_openrouter_api_key",
    "replace-me",
    "changeme",
}


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the shopping app and AI copilot."""

    db_path: Path
    openrouter_api_key: str | None
    openrouter_model: str
    openrouter_site_url: str
    openrouter_app_name: str
    openrouter_api_url: str
    ai_timeout_seconds: int = 45
    live_timeout_seconds: int = 15
    live_min_interval_seconds: float = 2.0
    live_max_bytes: int = 3_000_000
    live_stale_hours: int = 24
    live_check_robots: bool = True
    live_user_agent: str = ""

    @property
    def ai_configured(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def ai_mode_label(self) -> str:
        return "AI connected" if self.ai_configured else "Local analysis"


def _clean_key(raw: str | None) -> str | None:
    key = (raw or "").strip()
    if key.lower() in _PLACEHOLDER_KEYS:
        return None
    return key or None


def _resolve_db_path(raw: str | None) -> Path:
    value = (raw or "data/shopping.db").strip()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _resolve_timeout(raw: str | None) -> int:
    try:
        seconds = int(raw) if raw else 45
    except ValueError:
        seconds = 45
    return max(5, min(seconds, 120))


def _resolve_int(raw: str | None, default: int, low: int, high: int) -> int:
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(low, min(value, high))


def _resolve_float(raw: str | None, default: float, low: float, high: float) -> float:
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    return max(low, min(value, high))


def _resolve_bool(raw: str | None, default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def load_settings() -> Settings:
    """Read settings from environment variables on every call.

    Reading dynamically keeps tests and local configuration changes reliable.
    """

    return Settings(
        db_path=_resolve_db_path(os.getenv("SHOPPING_DB_PATH")),
        openrouter_api_key=_clean_key(os.getenv("OPENROUTER_API_KEY")),
        openrouter_model=(os.getenv("OPENROUTER_MODEL") or DEFAULT_MODEL).strip()
        or DEFAULT_MODEL,
        openrouter_site_url=(
            os.getenv("OPENROUTER_SITE_URL") or "http://localhost:8501"
        ).strip(),
        openrouter_app_name=(
            os.getenv("OPENROUTER_APP_NAME") or "AI Smart Deal Predictor"
        ).strip(),
        openrouter_api_url=(
            os.getenv("OPENROUTER_API_URL")
            or "https://openrouter.ai/api/v1/chat/completions"
        ).strip(),
        ai_timeout_seconds=_resolve_timeout(os.getenv("AI_COPILOT_TIMEOUT")),
        live_timeout_seconds=_resolve_int(
            os.getenv("LIVE_SCRAPER_TIMEOUT"), 15, 5, 60
        ),
        live_min_interval_seconds=_resolve_float(
            os.getenv("LIVE_SCRAPER_MIN_INTERVAL"), 2.0, 0.0, 60.0
        ),
        live_max_bytes=_resolve_int(
            os.getenv("LIVE_SCRAPER_MAX_BYTES"), 3_000_000, 100_000, 10_000_000
        ),
        live_stale_hours=_resolve_int(
            os.getenv("LIVE_QUOTE_STALE_HOURS"), 24, 1, 168
        ),
        live_check_robots=_resolve_bool(
            os.getenv("LIVE_SCRAPER_CHECK_ROBOTS"), True
        ),
        live_user_agent=(os.getenv("LIVE_SCRAPER_USER_AGENT") or "").strip(),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings for normal Streamlit reruns."""

    return load_settings()


def clear_settings_cache() -> None:
    """Used by tests after changing environment variables."""

    get_settings.cache_clear()
