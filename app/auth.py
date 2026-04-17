"""Authentication helpers for API key protected endpoints."""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Validate the API key from X-API-Key header."""
    expected = settings.agent_api_key
    if not api_key or not expected or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header X-API-Key.",
        )
    return api_key
