"""Async MongoDB helpers built on top of Motor.

Only generic utilities live here; domain repositories import these helpers and
build their own repositories, schemas, and permission checks on top."""

from functools import lru_cache
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .settings import settings


@lru_cache
def get_mongo_client() -> AsyncIOMotorClient:
    """Return a cached Motor client configured via ``db_core.settings``."""

    return AsyncIOMotorClient(settings.uri)


def get_db() -> AsyncIOMotorDatabase:
    """Return the main application database defined by ``settings.db_name``."""

    client = get_mongo_client()
    return client[settings.db_name]


async def ping() -> dict[str, Any]:
    """Run a simple ``ping`` command against the configured MongoDB server."""

    db = get_db()
    await db.command("ping")
    return {"ok": True}
