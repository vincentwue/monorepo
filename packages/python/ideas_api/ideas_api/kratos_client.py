"""Kratos integration helpers for FastAPI dependencies."""

from fastapi import Depends, HTTPException, Request
import httpx

from .config import settings


async def get_current_identity(request: Request) -> dict:
    """Retrieve the current identity via Kratos sessions API."""

    cookies = request.headers.get("cookie")
    if not cookies:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.kratos_public_url}/sessions/whoami",
                headers={"Cookie": cookies},
                timeout=5.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="Identity service unavailable") from exc

    if resp.status_code == 200:
        return resp.json()

    if resp.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Not authenticated")

    raise HTTPException(status_code=502, detail="Identity service error")
