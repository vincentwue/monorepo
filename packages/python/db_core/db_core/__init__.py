"""Minimal MongoDB helpers shared across domain repositories.

Example usage in a domain repository:

    from db_core import get_db

    async def list_items():
        db = get_db()
        cursor = db["ideas"].find({"owner_id": "user-123"}).sort("rank", 1)
        return await cursor.to_list(length=100)
"""

from .settings import MongoSettings, settings
from .mongo import get_mongo_client, get_db, ping

__all__ = [
    "MongoSettings",
    "settings",
    "get_mongo_client",
    "get_db",
    "ping",
]
