"""Redis-backed sliding window rate limiter with in-memory fallback."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException


class RateLimiter:
    """Apply a per-key request limit inside a rolling window."""

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        redis_client: Any | None = None,
        key_prefix: str = "rate",
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self._windows: dict[str, deque[float]] = defaultdict(deque)

    def set_redis_client(self, redis_client: Any | None) -> None:
        self.redis_client = redis_client

    def check(self, bucket_key: str) -> dict[str, int]:
        """Raise HTTP 429 when the key exceeds limit."""
        if self.redis_client is not None:
            try:
                return self._check_redis(bucket_key)
            except Exception:
                # Fallback keeps service available if Redis has a transient issue.
                return self._check_memory(bucket_key)
        return self._check_memory(bucket_key)

    def _check_redis(self, bucket_key: str) -> dict[str, int]:
        now = time.time()
        window_start = now - self.window_seconds
        redis_key = f"{self.key_prefix}:{bucket_key}"
        member = f"{now:.6f}-{time.monotonic_ns()}"

        pipeline = self.redis_client.pipeline(transaction=True)
        pipeline.zremrangebyscore(redis_key, 0, window_start)
        pipeline.zcard(redis_key)
        pipeline.zadd(redis_key, {member: now})
        pipeline.expire(redis_key, self.window_seconds + 5)
        _, count_before, _, _ = pipeline.execute()

        current_count = int(count_before) + 1
        if int(count_before) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.max_requests} req/{self.window_seconds}s",
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        remaining = self.max_requests - current_count
        return {
            "limit": self.max_requests,
            "remaining": max(0, remaining),
            "window_seconds": self.window_seconds,
        }

    def _check_memory(self, bucket_key: str) -> dict[str, int]:
        now = time.time()
        window = self._windows[bucket_key]
        while window and window[0] < now - self.window_seconds:
            window.popleft()

        if len(window) >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.max_requests} req/{self.window_seconds}s",
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        window.append(now)
        remaining = self.max_requests - len(window)
        return {
            "limit": self.max_requests,
            "remaining": max(0, remaining),
            "window_seconds": self.window_seconds,
        }
