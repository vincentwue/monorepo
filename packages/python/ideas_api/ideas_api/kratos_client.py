"""Kratos integration helpers for FastAPI dependencies."""

from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException, Request
import httpx
from loguru import logger

from .config import settings

# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _timeout_value(timeout: Optional[float]) -> float:
    # Reuse your global timeout setting if present, otherwise fall back to 5s.
    if timeout is not None:
        return timeout
    return getattr(settings, "timeout_seconds", 5.0)


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_current_identity(request: Request, *, timeout: Optional[float] = None) -> dict:
    """Retrieve the current identity via Kratos sessions API."""

    cookies = request.headers.get("cookie")
    if not cookies:
        raise HTTPException(status_code=401, detail="Not authenticated")

    url = f"{settings.kratos_public_url.rstrip('/')}/sessions/whoami"

    client = _get_client()
    start = time.perf_counter()
    try:
        resp = await client.get(
            url,
            headers={"Cookie": cookies},
            timeout=_timeout_value(timeout),
        )
    except httpx.RequestError as exc:
        duration = (time.perf_counter() - start) * 1000
        logger.warning(
            "Kratos whoami request failed after {duration:.2f} ms: {error}",
            duration=duration,
            error=exc,
        )
        raise HTTPException(status_code=502, detail="Identity service unavailable") from exc

    duration = (time.perf_counter() - start) * 1000
    logger.debug(
        "Kratos whoami responded with {status} in {duration:.2f} ms",
        status=resp.status_code,
        duration=duration,
    )

    if resp.status_code == 200:
        payload = resp.json()
        identity = payload.get("identity")
        if isinstance(identity, dict):
            return identity
        raise HTTPException(status_code=502, detail="Identity response missing identity")

    if resp.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Not authenticated")

    raise HTTPException(status_code=502, detail="Identity service error")


async def get_identity(request: Request):
    """
    Dependency wrapper that caches the identity on the request state so
    subsequent dependencies can reuse it.
    """

    cached = getattr(request.state, "identity", None)
    if cached is not None:
        return cached

    identity = await get_current_identity(request)
    request.state.identity = identity
    return identity
