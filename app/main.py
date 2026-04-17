"""Production AI agent combining security, reliability, and deployment practices."""
from __future__ import annotations

import json
import logging
import os
import signal
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import CostGuard
from app.rate_limiter import RateLimiter
from utils.mock_llm import ask as llm_ask

try:
    import redis
except Exception:
    redis = None


def _configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
    )


_configure_logging()
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID", f"agent-{uuid.uuid4().hex[:8]}")
_is_ready = False
_request_count = 0
_error_count = 0
_shutdown_signal: int | None = None

redis_client: Any | None = None
rate_limiter = RateLimiter(max_requests=settings.rate_limit_per_minute, window_seconds=60)
cost_guard = CostGuard(monthly_budget_usd=settings.monthly_budget_usd)
_memory_history: dict[str, list[dict[str, str]]] = {}


def _connect_redis() -> Any | None:
    if redis is None or not settings.redis_url:
        return None
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:
        logger.warning(json.dumps({"event": "redis_unavailable", "detail": str(exc)}))
        return None


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 2)


def _load_history(user_id: str) -> list[dict[str, str]]:
    if redis_client is not None:
        try:
            raw_messages = redis_client.lrange(_history_key(user_id), 0, -1)
            return [json.loads(item) for item in raw_messages]
        except Exception:
            pass
    return list(_memory_history.get(user_id, []))


def _append_history(user_id: str, role: str, content: str) -> None:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if redis_client is not None:
        try:
            key = _history_key(user_id)
            pipeline = redis_client.pipeline(transaction=True)
            pipeline.rpush(key, json.dumps(message))
            pipeline.ltrim(key, -settings.max_history_messages, -1)
            pipeline.expire(key, settings.history_ttl_seconds)
            pipeline.execute()
            return
        except Exception:
            pass

    history = _memory_history.setdefault(user_id, [])
    history.append(message)
    if len(history) > settings.max_history_messages:
        _memory_history[user_id] = history[-settings.max_history_messages:]


def _answer_with_context(question: str, history: list[dict[str, str]]) -> str:
    lower_question = question.lower().strip()
    context_triggers = {
        "what did i just say",
        "what was my previous message",
        "nhac lai tin nhan truoc",
        "toi vua noi gi",
    }
    if any(trigger in lower_question for trigger in context_triggers):
        for item in reversed(history):
            if item.get("role") == "user":
                return f'Your previous message was: "{item.get("content", "")}"'
        return "I do not have previous user messages in this session yet."
    return llm_ask(question)


def _redis_is_healthy() -> bool:
    if redis_client is None:
        return False
    try:
        redis_client.ping()
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready, redis_client

    logger.info(
        json.dumps(
            {
                "event": "startup",
                "app": settings.app_name,
                "version": settings.app_version,
                "environment": settings.environment,
                "instance_id": INSTANCE_ID,
            }
        )
    )

    redis_client = _connect_redis()
    rate_limiter.set_redis_client(redis_client)
    cost_guard.set_redis_client(redis_client)

    if settings.require_redis and redis_client is None:
        logger.error(json.dumps({"event": "startup_failed", "detail": "Redis is required"}))
        _is_ready = False
    else:
        _is_ready = True
        logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    if redis_client is not None:
        try:
            redis_client.close()
        except Exception:
            pass
    logger.info(json.dumps({"event": "shutdown", "signal": _shutdown_signal}))


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count

    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        _error_count += 1
        raise

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    if "server" in response.headers:
        del response.headers["server"]

    duration_ms = round((time.time() - start) * 1000, 1)
    logger.info(
        json.dumps(
            {
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": duration_ms,
            }
        )
    )
    return response


class AskRequest(BaseModel):
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9_:\-.]+$",
        description="Stable user identifier to keep conversation state in Redis",
    )
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    timestamp: str
    turn: int
    served_by: str


@app.get("/", tags=["Info"])
def root() -> dict[str, Any]:
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)",
        },
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    response: Response,
    request: Request,
    _api_key: str = Depends(verify_api_key),
) -> AskResponse:
    rate_info = rate_limiter.check(body.user_id)
    cost_guard.check_budget()

    history_before = _load_history(body.user_id)
    answer = _answer_with_context(body.question, history_before)

    _append_history(body.user_id, "user", body.question)
    _append_history(body.user_id, "assistant", answer)

    input_tokens = _estimate_tokens(body.question)
    output_tokens = _estimate_tokens(answer)
    usage = cost_guard.record_usage(input_tokens=input_tokens, output_tokens=output_tokens)

    remaining_budget = max(0.0, settings.monthly_budget_usd - float(usage["monthly_spent_usd"]))
    response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
    response.headers["X-Monthly-Budget-Remaining"] = f"{remaining_budget:.4f}"

    history_after = _load_history(body.user_id)
    user_turns = len([item for item in history_after if item.get("role") == "user"])

    logger.info(
        json.dumps(
            {
                "event": "agent_call",
                "user_id": body.user_id,
                "q_len": len(body.question),
                "client": str(request.client.host) if request.client else "unknown",
            }
        )
    )

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
        turn=user_turns,
        served_by=INSTANCE_ID,
    )


@app.get("/history/{user_id}", tags=["Agent"])
def get_history(user_id: str, _api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    history = _load_history(user_id)
    return {
        "user_id": user_id,
        "messages": history,
        "count": len(history),
    }


@app.get("/health", tags=["Operations"])
def health() -> dict[str, Any]:
    redis_ok = _redis_is_healthy()
    redis_required = bool(settings.require_redis)
    status = "ok"
    if redis_required and not redis_ok:
        status = "degraded"

    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": {
            "redis": redis_ok,
            "redis_required": redis_required,
            "llm": "mock" if not settings.openai_api_key else "configured",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready() -> dict[str, Any]:
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Service is not initialized")
    if settings.require_redis and not _redis_is_healthy():
        raise HTTPException(status_code=503, detail="Redis is not available")
    return {"ready": True, "instance_id": INSTANCE_ID}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    spent = cost_guard.get_monthly_spend()
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "monthly_spent_usd": round(spent, 6),
        "monthly_budget_usd": settings.monthly_budget_usd,
        "budget_used_pct": round((spent / settings.monthly_budget_usd) * 100, 2),
        "redis_connected": _redis_is_healthy(),
    }


def _handle_signal(signum: int, _frame: Any) -> None:
    global _is_ready, _shutdown_signal
    _shutdown_signal = signum
    _is_ready = False
    logger.info(json.dumps({"event": "signal", "signum": signum}))


if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _handle_signal)
if hasattr(signal, "SIGINT"):
    signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(
        json.dumps(
            {
                "event": "boot",
                "app": settings.app_name,
                "host": settings.host,
                "port": settings.port,
            }
        )
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
