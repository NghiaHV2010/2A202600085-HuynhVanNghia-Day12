"""Configuration for the Day 12 production-ready agent."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_csv(value: str | None, fallback: str = "*") -> list[str]:
    raw = value if value is not None else fallback
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or ["*"]


def _resolve_redis_url() -> str:
    # Render users sometimes store Redis URL under different variable names.
    # Prioritize dedicated internal URL vars so they can override a wrong REDIS_URL.
    for key in ("REDIS_INTERNAL_URL", "RENDER_REDIS_URL", "REDIS_URL"):
        value = (os.getenv(key) or "").strip()
        if value:
            return value

    environment = (os.getenv("ENVIRONMENT") or "development").strip().lower()
    if environment == "production":
        return ""
    return "redis://redis:6379/0"


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _as_bool(os.getenv("DEBUG"), False))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Production AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))

    # LLM
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # Security
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me"))
    allowed_origins: list[str] = field(
        default_factory=lambda: _split_csv(os.getenv("ALLOWED_ORIGINS"), "*")
    )

    # Reliability and state
    redis_url: str = field(default_factory=_resolve_redis_url)
    require_redis: bool = field(default_factory=lambda: _as_bool(os.getenv("REQUIRE_REDIS"), True))
    history_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("HISTORY_TTL_SECONDS", "86400")))
    max_history_messages: int = field(default_factory=lambda: int(os.getenv("MAX_HISTORY_MESSAGES", "20")))

    # Controls
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0"))
    )

    def validate(self) -> "Settings":
        logger = logging.getLogger(__name__)
        environment = self.environment.strip().lower()
        default_agent_keys = {"dev-key-change-me"}

        if environment == "production" and self.agent_api_key in default_agent_keys:
            raise ValueError("AGENT_API_KEY must be set to a non-default value in production.")
        if environment == "production" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set in production.")
        if self.rate_limit_per_minute <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be > 0.")
        if self.monthly_budget_usd <= 0:
            raise ValueError("MONTHLY_BUDGET_USD must be > 0.")
        if self.max_history_messages < 2:
            raise ValueError("MAX_HISTORY_MESSAGES must be >= 2.")
        if self.require_redis and self.redis_url and not self.redis_url.startswith(("redis://", "rediss://")):
            logger.warning(
                "REDIS_URL does not look like a Redis connection string. "
                "On Render, use Internal Redis URL (redis:// or rediss://)."
            )
        if self.require_redis and not self.redis_url:
            logger.warning("REQUIRE_REDIS=true but REDIS_URL is empty.")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY is not set; mock LLM will be used.")
        return self


settings = Settings().validate()
