"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def _get_env(key: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value or ""


@dataclass(frozen=True)
class Settings:
    # API Keys
    openai_api_key: str = field(default_factory=lambda: _get_env("OPENAI_API_KEY", required=True))
    news_api_key: str = field(default_factory=lambda: _get_env("NEWS_API_KEY", required=True))
    brave_api_key: str = field(default_factory=lambda: _get_env("BRAVE_API_KEY", ""))

    # Stripe
    stripe_secret_key: str = field(default_factory=lambda: _get_env("STRIPE_SECRET_KEY", ""))
    stripe_publishable_key: str = field(default_factory=lambda: _get_env("STRIPE_PUBLISHABLE_KEY", ""))
    stripe_webhook_secret: str = field(default_factory=lambda: _get_env("STRIPE_WEBHOOK_SECRET", ""))

    # Interactive Brokers
    ibkr_host: str = field(default_factory=lambda: _get_env("IBKR_HOST", "127.0.0.1"))
    ibkr_port: int = field(default_factory=lambda: int(_get_env("IBKR_PORT", "7497")))
    ibkr_client_id: int = field(default_factory=lambda: int(_get_env("IBKR_CLIENT_ID", "1")))
    ibkr_mode: str = field(default_factory=lambda: _get_env("IBKR_MODE", "paper"))  # paper | live

    # Database
    database_url: str = field(
        default_factory=lambda: _get_env(
            "DATABASE_URL",
            "postgresql+asyncpg://trading_user:trading_pass@localhost:5432/trading_db",
        )
    )
    redis_url: str = field(default_factory=lambda: _get_env("REDIS_URL", "redis://localhost:6379/0"))

    # App
    app_env: str = field(default_factory=lambda: _get_env("APP_ENV", "development"))
    log_level: str = field(default_factory=lambda: _get_env("LOG_LEVEL", "INFO"))
    secret_key: str = field(default_factory=lambda: _get_env("SECRET_KEY", "change-me"))

    # Scheduler
    scheduler_interval: int = field(
        default_factory=lambda: int(_get_env("SCHEDULER_INTERVAL", "30"))
    )
    watchlist: list[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in _get_env("WATCHLIST", "AAPL,MSFT,GOOGL,AMZN,TSLA").split(",")
        ]
    )

    # LLM
    llm_model: str = field(default_factory=lambda: _get_env("LLM_MODEL", "gpt-4o-mini"))
    llm_temperature: float = field(
        default_factory=lambda: float(_get_env("LLM_TEMPERATURE", "0.2"))
    )
    llm_max_tokens: int = field(
        default_factory=lambda: int(_get_env("LLM_MAX_TOKENS", "2048"))
    )

    # Risk Management
    max_loss_per_trade_pct: float = field(
        default_factory=lambda: float(_get_env("MAX_LOSS_PER_TRADE_PCT", "2.0"))
    )
    daily_loss_limit_pct: float = field(
        default_factory=lambda: float(_get_env("DAILY_LOSS_LIMIT_PCT", "5.0"))
    )
    max_position_pct: float = field(
        default_factory=lambda: float(_get_env("MAX_POSITION_PCT", "10.0"))
    )
    auto_stop_loss_pct: float = field(
        default_factory=lambda: float(_get_env("AUTO_STOP_LOSS_PCT", "3.0"))
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def ibkr_available(self) -> bool:
        return bool(self.ibkr_host and self.ibkr_port)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    # Warn about missing/placeholder API keys at startup
    import logging
    _logger = logging.getLogger(__name__)
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        _logger.critical("OPENAI_API_KEY is missing or placeholder — LLM calls will fail!")
    if not settings.news_api_key or settings.news_api_key == "your-newsapi-key-here":
        _logger.warning("NEWS_API_KEY is missing or placeholder — news fetching will be disabled")
    if not settings.brave_api_key:
        _logger.info("BRAVE_API_KEY not set — web search will use DuckDuckGo fallback")
    return settings
