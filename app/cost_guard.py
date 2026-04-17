"""Monthly budget guard for LLM usage, backed by Redis when available."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

# Approximate GPT-4o-mini pricing.
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006


class CostGuard:
    """Track spending and block traffic when monthly budget is exhausted."""

    def __init__(
        self,
        monthly_budget_usd: float = 10.0,
        redis_client: Any | None = None,
        key_prefix: str = "cost",
    ) -> None:
        self.monthly_budget_usd = monthly_budget_usd
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self._memory_spend: dict[str, float] = {}

    def set_redis_client(self, redis_client: Any | None) -> None:
        self.redis_client = redis_client

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        output_cost = (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)

    def check_budget(self) -> float:
        spent = self.get_monthly_spend()
        if spent >= self.monthly_budget_usd:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "Monthly budget exhausted",
                    "spent_usd": round(spent, 4),
                    "budget_usd": self.monthly_budget_usd,
                },
            )
        return spent

    def record_usage(self, input_tokens: int, output_tokens: int) -> dict[str, float | str]:
        cost = self.estimate_cost(input_tokens, output_tokens)
        month_key = self._month_key()
        if self.redis_client is not None:
            try:
                redis_key = f"{self.key_prefix}:{month_key}"
                spent = float(self.redis_client.incrbyfloat(redis_key, cost))
                self.redis_client.expire(redis_key, 60 * 60 * 24 * 40)
                return {
                    "month": month_key,
                    "cost_added_usd": round(cost, 6),
                    "monthly_spent_usd": round(spent, 6),
                    "monthly_budget_usd": self.monthly_budget_usd,
                }
            except Exception:
                pass

        spent = self._memory_spend.get(month_key, 0.0) + cost
        self._memory_spend[month_key] = spent
        return {
            "month": month_key,
            "cost_added_usd": round(cost, 6),
            "monthly_spent_usd": round(spent, 6),
            "monthly_budget_usd": self.monthly_budget_usd,
        }

    def get_monthly_spend(self) -> float:
        month_key = self._month_key()
        if self.redis_client is not None:
            try:
                redis_key = f"{self.key_prefix}:{month_key}"
                value = self.redis_client.get(redis_key)
                return float(value) if value else 0.0
            except Exception:
                pass
        return float(self._memory_spend.get(month_key, 0.0))

    @staticmethod
    def _month_key() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")
