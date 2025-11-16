"""Configuration helpers for MongoDB connections used by db_core.

Applications can create a new ``MongoSettings`` instance at startup and assign
it to ``db_core.settings`` before the first call to ``get_db`` to override the
defaults. If not overridden, the defaults below are used.
"""
from loguru import logger
import os

from pydantic import BaseModel, Field


class MongoSettings(BaseModel):
    """Basic MongoDB configuration that domain apps can extend if needed."""

    uri: str = Field(
        default_factory=lambda: os.getenv("MONGO_URI", "mongodb://mongo_default:27017")
    )
    db_name: str = Field(default_factory=lambda: os.getenv("MONGO_DB_NAME", "ideas"))
    


def _default_settings() -> "MongoSettings":
    """Provide a factory to keep settings override logic simple in the future."""

    return MongoSettings()


settings: MongoSettings = _default_settings()
logger.info(f"MongoSettings initialized with uri={settings.uri} db_name={settings.db_name}")
